"""Live ClinicalTrials.gov v2 discovery — trials + investigators + endpoints.

Spec 002 User Story 2. Mirrors the cannavec.chembl_discover and
cannavec.pubmed_search patterns: stdlib-only urllib transport,
injected ``Fetcher`` for offline tests, safety + banned-pattern
preflight via cannavec.discover_guard BEFORE any network call.

ClinicalTrials.gov v2 public REST endpoints used:

- ``…/api/v2/studies?query.term={q}&format=json&pageSize={n}``
  — trial search by free-text query.
- ``…/api/v2/studies?query.cond={c}&query.intr={i}&...``
  — query.cond + query.intr + filter.overallStatus + filter.start
  for richer filtering.
- ``…/api/v2/studies/{nct}?format=json``
  — single-trial detail (used by compare_endpoints).

Each emitted row carries ``provenance=live_ctgov`` and never
auto-promotes to the curated registry (FR-018).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from cannavec_science._http import TIMEOUT_FAST, retry_urlopen, user_agent
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "CTGovSearcher",
    "CTGovTrialRow",
    "NetworkError",
    "default_ctgov_fetcher",
    "render_endpoint_comparison",
    "render_json",
    "render_markdown",
]


# ── URLs ──────────────────────────────────────────────────────────────


_CTGOV_BASE = "https://clinicaltrials.gov/api/v2"
_CTGOV_SEARCH_URL = _CTGOV_BASE + "/studies?{query}"
_CTGOV_DETAIL_URL = _CTGOV_BASE + "/studies/{nct_id}?format=json"
_CTGOV_PUBLIC_LINK = "https://clinicaltrials.gov/study/{nct_id}"

_MAX_RESULTS_CEILING = 50

# CT.gov status precedence for sort order. Active recruiting first;
# terminated / withdrawn last. Any unknown status sinks to the bottom.
_STATUS_RANK = {
    "RECRUITING": 0,
    "ENROLLING_BY_INVITATION": 1,
    "NOT_YET_RECRUITING": 2,
    "ACTIVE_NOT_RECRUITING": 3,
    "COMPLETED": 4,
    "SUSPENDED": 5,
    "TERMINATED": 6,
    "WITHDRAWN": 7,
    "UNKNOWN": 8,
}

# A CT.gov trial is Level B at best for clinical evidence (RCT), but
# we cannot reliably distinguish phase/design without parsing more
# fields. Level B is the honest provisional grade with the explicit
# live_ctgov suffix per Constitution Principle VI.
_SUGGESTED_GRADE = "Level B (provisional, live_ctgov)"

_NCT_RE = re.compile(r"^NCT\d{8}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Exceptions ────────────────────────────────────────────────────────


class NetworkError(Exception):
    """Raised when a CT.gov fetch fails (HTTP error, timeout, JSON
    parse error). Distinct from DiscoverRefused (preflight refusal)."""


# ── Fetcher ───────────────────────────────────────────────────────────


Fetcher = Callable[[str], str]


def default_ctgov_fetcher(url: str) -> str:
    """Production fetcher — polite User-Agent, fast timeout, bounded retry."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent("ctgov-discover"),
            "Accept": "application/json",
        },
    )
    with retry_urlopen(req, timeout=TIMEOUT_FAST) as resp:
        raw = resp.read()
    return raw.decode("utf-8")


# ── Row dataclasses ───────────────────────────────────────────────────


@dataclass(frozen=True)
class CTGovTrialRow:
    nct_id: str
    status: str
    phase: str
    sponsor: str
    pi_name: Optional[str]
    condition: tuple[str, ...] = ()
    intervention: tuple[str, ...] = ()
    primary_endpoints: tuple[str, ...] = ()
    enrollment_count: Optional[int] = None
    site_jurisdictions: tuple[str, ...] = ()
    start_date: Optional[str] = None
    pi_retraction_status: str = "ok"
    source: Provenance = Provenance.LIVE_CTGOV
    suggested_grade: str = _SUGGESTED_GRADE
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(self, "native_id", self.nct_id)
        if not self.url:
            object.__setattr__(
                self, "url", _CTGOV_PUBLIC_LINK.format(nct_id=self.nct_id)
            )
        if not self.title:
            ttl = ", ".join(self.intervention) if self.intervention else self.nct_id
            cond_str = ", ".join(self.condition) if self.condition else "trial"
            object.__setattr__(
                self, "title", f"{ttl} in {cond_str}"
            )
        if not self.citation:
            object.__setattr__(self, "citation", f"NCT {self.nct_id}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        # Tuples → lists for JSON friendliness.
        for k in ("condition", "intervention", "primary_endpoints", "site_jurisdictions"):
            d[k] = list(d[k])
        return d


# ── Searcher ──────────────────────────────────────────────────────────


# CT.gov free-text relevance is broad: a query like "cannabis insulin
# metabolic syndrome" can return trials that match "insulin"/"metabolic" but
# have nothing to do with cannabinoids. For a cannabis-science surface, the
# CT.gov lane should only surface trials whose intervention / condition /
# title is actually cannabinoid-related. This regex is the relevance gate.
_CANNABIS_RELEVANCE_RE = re.compile(
    r"cannab\w*|marij\w*|marih\w*|\bthc\b|\bthca\b|tetrahydrocannabinol|"
    r"\bcbd\b|\bcbda\b|cannabidiol|\bcbn\b|cannabinol|\bcbg\b|cannabigerol|"
    r"\bthcv\b|nabilone|nabiximols|dronabinol|epidiolex|epidyolex|sativex|"
    r"endocannabinoid\w*|\bhemp\b",
    re.IGNORECASE,
)


def _trial_is_cannabis_relevant(row: "CTGovTrialRow") -> bool:
    """True if a trial's intervention / condition / title mentions a
    cannabinoid — the per-source relevance filter for the CT.gov lane."""
    haystack = " ".join(
        [row.title or ""]
        + list(row.intervention or ())
        + list(row.condition or ())
    )
    return bool(_CANNABIS_RELEVANCE_RE.search(haystack))


# Cannabis OR-group sent to CT.gov's intervention field so the API returns
# cannabinoid-intervention trials directly (recall), instead of fetching a
# broad free-text page and post-filtering it to empty.
_CANNABIS_INTR_QUERY = (
    "cannabis OR cannabidiol OR cannabinoid OR marijuana OR THC OR CBD OR "
    "tetrahydrocannabinol OR nabiximols OR dronabinol OR nabilone OR hemp"
)


def _strip_cannabis_terms(query: str) -> str:
    """Remove cannabinoid tokens from a query so the remainder can be used as
    the CT.gov ``query.term`` (the condition/topic) while the cannabinoid
    constraint moves to ``query.intr``. Falls back to the original query if
    stripping leaves nothing."""
    stripped = _CANNABIS_RELEVANCE_RE.sub(" ", query)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped or query


class CTGovSearcher:
    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_ctgov_fetcher

    # ── Public API ───────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        condition: Optional[str] = None,
        intervention: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[str] = None,
        max_results: int = 10,
        cannabis_relevant_only: bool = False,
    ) -> list[CTGovTrialRow]:
        """Run a CT.gov search and return typed trial rows.

        When ``cannabis_relevant_only`` is set, trials whose
        intervention / condition / title do not mention a cannabinoid are
        dropped — sharpening the lane for the cannabis-science surface so a
        broad free-text match cannot surface unrelated trials.

        Raises DiscoverRefused on preflight refusal (no network call).
        Raises ValueError on invalid arguments.
        Raises NetworkError on transport / parse failure.
        """
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )
        if since is not None and not _DATE_RE.match(since):
            raise ValueError(f"since must be YYYY-MM-DD; got {since!r}")

        preflight(query)

        # Cannabis relevance gate (recall + precision): push the cannabinoid
        # constraint into CT.gov's intervention field so the API returns
        # cannabinoid trials directly, and use the cannabis-stripped remainder
        # as the topic term. The post-filter below is the safety net.
        eff_query = query
        eff_intervention = intervention
        if cannabis_relevant_only and not intervention:
            eff_intervention = _CANNABIS_INTR_QUERY
            eff_query = _strip_cannabis_terms(query)

        url = self._build_search_url(
            query=eff_query,
            condition=condition,
            intervention=eff_intervention,
            status=status,
            since=since,
            page_size=max_results,
        )
        data = self._fetch_json(url)
        studies = data.get("studies") or []
        rows = [_parse_study(s) for s in studies]
        rows = [r for r in rows if r is not None]
        if cannabis_relevant_only:
            rows = [r for r in rows if _trial_is_cannabis_relevant(r)]
        rows.sort(key=_row_sort_key)
        return rows[:max_results]

    def search_investigator(
        self,
        name: str,
        *,
        max_results: int = 10,
    ) -> list[CTGovTrialRow]:
        """Find trials whose PI matches a name (substring, case-insensitive).

        Runs the standard preflight on the name itself so a banned-
        pattern name (e.g., a cultivar passed in error) is refused.
        """
        if not name or not name.strip():
            raise ValueError("name must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )
        preflight(name)

        # The CT.gov v2 API doesn't have a clean investigator filter,
        # so we search by free-text term + client-side filter.
        url = self._build_search_url(
            query=name, page_size=max(max_results * 3, 30)
        )
        data = self._fetch_json(url)
        studies = data.get("studies") or []
        needle = name.strip().lower()
        rows = []
        for s in studies:
            row = _parse_study(s)
            if row is None:
                continue
            if row.pi_name and needle in row.pi_name.lower():
                rows.append(row)
        rows.sort(key=_row_sort_key)
        return rows[:max_results]

    def fetch_trial(self, nct_id: str) -> Optional[CTGovTrialRow]:
        """Fetch a single trial by NCT ID (spec 003 US5 / FR-005).

        Returns ``None`` when the trial does not resolve. Preflight is
        run on the NCT ID itself (safe — a bare NCT never trips banned
        patterns). Raises ``ValueError`` for malformed NCT IDs.
        """
        if not _NCT_RE.match(nct_id or ""):
            raise ValueError(
                f"NCT IDs must match ^NCT\\d{{8}}$; got {nct_id!r}"
            )
        preflight(nct_id)
        url = _CTGOV_DETAIL_URL.format(nct_id=nct_id)
        try:
            data = self._fetch_json(url)
        except NetworkError:
            return None
        return _parse_study(data)

    def compare_endpoints(self, nct_a: str, nct_b: str) -> dict:
        """Fetch two trials and emit a side-by-side endpoint payload.

        Generalises the comparative-prompt renderer from spec 001 US4
        to CT.gov trial endpoints. Useful for trial designers
        benchmarking primary outcomes.
        """
        for nct in (nct_a, nct_b):
            if not _NCT_RE.match(nct or ""):
                raise ValueError(
                    f"NCT IDs must match ^NCT\\d{{8}}$; got {nct!r}"
                )

        url_a = _CTGOV_DETAIL_URL.format(nct_id=nct_a)
        url_b = _CTGOV_DETAIL_URL.format(nct_id=nct_b)
        data_a = self._fetch_json(url_a)
        data_b = self._fetch_json(url_b)

        side_a = _extract_side(data_a)
        side_b = _extract_side(data_b)

        endpoints_a = set(side_a["endpoints"])
        endpoints_b = set(side_b["endpoints"])
        shared = sorted(endpoints_a & endpoints_b)
        divergent = sorted(endpoints_a ^ endpoints_b)

        return {
            "nct_a": side_a,
            "nct_b": side_b,
            "shared_endpoints": shared,
            "divergent_endpoints": divergent,
        }

    # ── Internals ────────────────────────────────────────────────────

    def _build_search_url(
        self,
        *,
        query: str,
        condition: Optional[str] = None,
        intervention: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[str] = None,
        page_size: int = 10,
    ) -> str:
        params: list[tuple[str, str]] = [
            ("query.term", query),
            ("pageSize", str(page_size)),
            ("format", "json"),
        ]
        if condition:
            params.append(("query.cond", condition))
        if intervention:
            params.append(("query.intr", intervention))
        if status:
            params.append(("filter.overallStatus", status))
        if since:
            params.append(("filter.advanced", f"AREA[StartDate]RANGE[{since}, MAX]"))
        qs = urllib.parse.urlencode(params)
        return _CTGOV_SEARCH_URL.format(query=qs)

    def _fetch_json(self, url: str) -> dict:
        try:
            body = self._fetcher(url)
        except DiscoverRefused:
            raise
        except Exception as exc:
            raise NetworkError(f"fetch failed: {url}: {exc}") from exc

        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NetworkError(
                f"CT.gov response is not valid JSON for {url}: {exc}"
            ) from exc


# ── Parsing helpers ───────────────────────────────────────────────────


def _parse_study(study: dict) -> Optional[CTGovTrialRow]:
    """Build a CTGovTrialRow from one /studies row.

    Defensive: every nested module is accessed with .get() so a
    missing field surfaces as the appropriate default rather than
    KeyError.
    """
    proto = study.get("protocolSection") or {}
    ident = proto.get("identificationModule") or {}
    nct_id = ident.get("nctId")
    if not nct_id:
        return None

    status_module = proto.get("statusModule") or {}
    overall_status = status_module.get("overallStatus") or "UNKNOWN"
    start_date_struct = status_module.get("startDateStruct") or {}
    start_date = start_date_struct.get("date")

    design = proto.get("designModule") or {}
    phases = design.get("phases") or []
    phase = phases[0] if phases else "UNKNOWN"
    enrolment_info = design.get("enrollmentInfo") or {}
    enrollment_count = enrolment_info.get("count")
    if enrollment_count is not None:
        try:
            enrollment_count = int(enrollment_count)
        except (TypeError, ValueError):
            enrollment_count = None

    sponsor_module = proto.get("sponsorCollaboratorsModule") or {}
    lead_sponsor = sponsor_module.get("leadSponsor") or {}
    sponsor = lead_sponsor.get("name") or ""
    resp_party = sponsor_module.get("responsibleParty") or {}
    pi_name = resp_party.get("investigatorFullName")

    conditions_module = proto.get("conditionsModule") or {}
    conditions = tuple(conditions_module.get("conditions") or [])

    arms_module = proto.get("armsInterventionsModule") or {}
    interventions_raw = arms_module.get("interventions") or []
    interventions = tuple(i.get("name") or "" for i in interventions_raw if i.get("name"))

    outcomes_module = proto.get("outcomesModule") or {}
    primary_outcomes_raw = outcomes_module.get("primaryOutcomes") or []
    primary_endpoints = tuple(
        o.get("measure") or "" for o in primary_outcomes_raw if o.get("measure")
    )

    locations_module = proto.get("contactsLocationsModule") or {}
    locations_raw = locations_module.get("locations") or []
    site_juris_seen = []
    seen = set()
    for loc in locations_raw:
        country = loc.get("country")
        if country and country not in seen:
            seen.add(country)
            site_juris_seen.append(country)
    site_jurisdictions = tuple(site_juris_seen)

    return CTGovTrialRow(
        nct_id=nct_id,
        status=overall_status,
        phase=phase,
        sponsor=sponsor,
        pi_name=pi_name,
        condition=conditions,
        intervention=interventions,
        primary_endpoints=primary_endpoints,
        enrollment_count=enrollment_count,
        site_jurisdictions=site_jurisdictions,
        start_date=start_date,
    )


def _extract_side(study: dict) -> dict:
    """Reduce a full study payload to the comparison side-shape."""
    proto = study.get("protocolSection") or {}
    ident = proto.get("identificationModule") or {}
    design = proto.get("designModule") or {}
    outcomes = proto.get("outcomesModule") or {}

    phases = design.get("phases") or []
    primary_outcomes = outcomes.get("primaryOutcomes") or []
    endpoints = [o.get("measure") for o in primary_outcomes if o.get("measure")]

    arms_module = proto.get("armsInterventionsModule") or {}
    interventions_raw = arms_module.get("interventions") or []
    interventions = [i.get("name") for i in interventions_raw if i.get("name")]

    enrol_info = design.get("enrollmentInfo") or {}
    return {
        "nct": ident.get("nctId"),
        "phase": phases[0] if phases else "UNKNOWN",
        "indication": (
            proto.get("conditionsModule", {}).get("conditions", []) or [None]
        )[0],
        "interventions": interventions,
        "endpoints": endpoints,
        "enrollment": enrol_info.get("count"),
    }


def _row_sort_key(row: CTGovTrialRow):
    """Status rank asc, then start_date desc (newest first), then nct_id asc."""
    status_rank = _STATUS_RANK.get(row.status, 99)
    # Newest start first; rows without a start_date sort to the bottom
    # within their status group.
    if row.start_date:
        date_key = "0_" + row.start_date  # leading "0_" sorts before "1_"
    else:
        date_key = "1_zzzz"
    # We want date desc, so invert by mapping to a large complement.
    # Simpler approach: negate via tuple ordering by storing a reversed
    # string.
    # For lexicographic desc sort within asc tuple, we use complement:
    inverted_date = "".join(chr(255 - ord(c)) for c in date_key)
    return (status_rank, inverted_date, row.nct_id)


# ── Renderers ─────────────────────────────────────────────────────────


def render_markdown(query: str, rows: list[CTGovTrialRow]) -> str:
    lines: list[str] = []
    lines.append(f"## ClinicalTrials.gov (live_ctgov, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No matching trials found in ClinicalTrials.gov._")
        return "\n".join(lines)
    for r in rows:
        head = (
            f"- **{r.nct_id}** — *{r.title}*. Phase {r.phase}, "
            f"{r.status}, sponsor: {r.sponsor or 'unknown'}"
        )
        if r.pi_name:
            head += f", PI: {r.pi_name}"
        head += "."
        lines.append(head)
        if r.primary_endpoints:
            lines.append(
                f"  Primary endpoint: {', '.join(r.primary_endpoints)}."
            )
        if r.enrollment_count is not None:
            lines.append(f"  Enrolment: {r.enrollment_count}.")
        if r.start_date:
            lines.append(f"  Started {r.start_date}.")
        if r.site_jurisdictions:
            lines.append(
                f"  Sites: {', '.join(r.site_jurisdictions)}."
            )
        lines.append(f"  {r.url}")
    return "\n".join(lines)


def render_json(query: str, rows: list[CTGovTrialRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_CTGOV.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)


def render_endpoint_comparison(payload: dict) -> str:
    """Render the compare_endpoints() payload as a Markdown table."""
    side_a = payload.get("nct_a", {})
    side_b = payload.get("nct_b", {})
    shared = payload.get("shared_endpoints", [])
    divergent = payload.get("divergent_endpoints", [])

    lines: list[str] = []
    lines.append(
        f"## Endpoint comparison — {side_a.get('nct')} vs {side_b.get('nct')}"
    )
    lines.append("")
    lines.append("| Aspect       | " + str(side_a.get("nct", "A")) + " | " + str(side_b.get("nct", "B")) + " |")
    lines.append("|---           |---|---|")
    lines.append(
        f"| Phase        | {side_a.get('phase', '?')} | {side_b.get('phase', '?')} |"
    )
    lines.append(
        f"| Indication   | {side_a.get('indication', '?')} | {side_b.get('indication', '?')} |"
    )
    a_int = ", ".join(side_a.get("interventions", [])) or "?"
    b_int = ", ".join(side_b.get("interventions", [])) or "?"
    lines.append(f"| Intervention | {a_int} | {b_int} |")
    a_eps = ", ".join(side_a.get("endpoints", [])) or "—"
    b_eps = ", ".join(side_b.get("endpoints", [])) or "—"
    lines.append(f"| Endpoints    | {a_eps} | {b_eps} |")
    lines.append(
        f"| Enrolment    | {side_a.get('enrollment', '?')} | {side_b.get('enrollment', '?')} |"
    )
    lines.append("")
    if shared:
        lines.append(f"**Shared endpoints**: {', '.join(shared)}.")
    if divergent:
        lines.append(f"**Divergent endpoints**: {', '.join(divergent)}.")
    return "\n".join(lines)
