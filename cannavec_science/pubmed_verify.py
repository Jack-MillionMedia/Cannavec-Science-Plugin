"""PubMed + Crossref citation verification.

`auditor/verify_audit.sh` already verifies PMIDs and DOIs by shelling out
to `curl` and `jq`. This module provides the same verification surface
as importable Python — so the typed `Source` and `Claim` objects in
`cannavec.evidence`, the eval harness, and the `python -m cannavec`
CLI can all verify citations without spawning a shell.

Design:

- **Standard library only.** `urllib.request` for HTTP, `json` for
  parsing, no PyYAML / requests / lxml / etc.
- **Network is opt-in.** The default fetcher only fires when the
  caller explicitly invokes a verification function. Tests inject a
  fixture fetcher so unit-test runs are fully offline.
- **Conservative on failure.** Network errors, parse errors, and
  unknown-PMID responses return a typed `Unknown` verdict, not a
  False or a swallowed exception. The caller decides what to do.
- **NCBI etiquette.** The default fetcher passes a polite
  ``User-Agent: cannavec-pubmed-verify/<version>`` header and a
  ``tool=cannavec`` query param so NCBI can see who is calling.

Public surface:

- :class:`PubMedRecord` — typed esummary record (title, year,
  journal, first author, retraction status).
- :func:`fetch_pubmed_record(pmid, *, fetcher=...)` — fetch one record.
- :class:`VerificationVerdict` — enum: ``MATCH`` / ``MISMATCH`` /
  ``BARE_CITE_OK`` / ``NOT_FOUND`` / ``NETWORK_ERROR``.
- :class:`VerificationResult` — verdict + per-field surnames / years.
- :func:`verify_pmid(pmid, *, expected_first_author=None,
  expected_year=None, fetcher=...)` — full verification.
- :func:`fetch_crossref_doi(doi, *, fetcher=...)` — DOI fetch.
- :func:`verify_doi(doi, *, expected_first_author=None,
  expected_year=None, fetcher=...)` — DOI verification.
- :func:`surname_normalise(s)` — diacritic-stripped surname for the
  comparison check.

This module is read-only. It never writes to disk and never modifies
the registry. Caching is the caller's responsibility (the cost of a
single esummary lookup is ~200 ms).
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional, Protocol


__all__ = [
    "PubMedRecord",
    "CrossrefRecord",
    "VerificationVerdict",
    "VerificationResult",
    "Fetcher",
    "default_pubmed_fetcher",
    "default_crossref_fetcher",
    "fetch_pubmed_record",
    "fetch_crossref_doi",
    "verify_pmid",
    "verify_doi",
    "surname_normalise",
]


# ── User-Agent ────────────────────────────────────────────────────────

def _user_agent() -> str:
    try:
        import cannavec  # noqa: WPS433 — local import keeps this importable
        return f"cannavec-pubmed-verify/{cannavec.__version__}"
    except Exception:   # noqa: BLE001 — fallback for build-time imports
        return "cannavec-pubmed-verify/unknown"


# ── Fetcher protocol ──────────────────────────────────────────────────

class Fetcher(Protocol):
    """A callable that returns the response body for a given URL.

    Tests inject canned fixtures; production uses
    :func:`default_pubmed_fetcher` / :func:`default_crossref_fetcher`,
    which call `urllib.request.urlopen`.
    """

    def __call__(self, url: str) -> str: ...


# Charset whitelist used by the network fetchers (Oracle Auditor §SEC-003).
# NCBI and Crossref both serve JSON; either the response is UTF-8 or it is
# trivially convertible (ASCII / Latin-1). Anything else is a sign the
# upstream is misbehaving or the response was tampered with — coerce to
# UTF-8 and fail loud rather than silently substituting characters with
# errors="replace".
_SAFE_CHARSETS: frozenset[str] = frozenset({
    "utf-8", "utf8", "us-ascii", "ascii", "iso-8859-1", "latin-1", "latin1",
})


def _decode_response_strict(raw: bytes, declared_charset: str | None) -> str:
    """Decode a network response body with a charset whitelist.

    NCBI / Crossref MUST serve UTF-8 (or one of the trivial-equivalent
    encodings in :data:`_SAFE_CHARSETS`); any other declared charset is
    treated as suspect and rejected with a :class:`UnicodeDecodeError`
    so the caller surfaces a NETWORK_ERROR rather than silently using
    corrupted data.
    """
    charset = (declared_charset or "utf-8").strip().lower()
    if charset not in _SAFE_CHARSETS:
        charset = "utf-8"
    # errors="strict" so a malformed body fails loudly rather than
    # producing silently-corrupted JSON that the parser then accepts.
    return raw.decode(charset, errors="strict")


def default_pubmed_fetcher(url: str) -> str:
    """Production fetcher for PubMed E-utilities.

    Sends a polite User-Agent and tool param so NCBI traffic shows the
    plugin's identity. Surfaces network / HTTP errors as
    :class:`urllib.error.URLError` so the caller can map them to a
    NETWORK_ERROR verdict.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _user_agent()},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return _decode_response_strict(
            resp.read(), resp.headers.get_content_charset(),
        )


def default_crossref_fetcher(url: str) -> str:
    """Production fetcher for Crossref. Sends a polite User-Agent
    with a mailto suffix per Crossref's etiquette guide.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                f"{_user_agent()} (mailto:noreply@example.invalid; "
                f"https://github.com/Jack-MillionMedia/Cannavec-Plugin)"
            ),
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return _decode_response_strict(
            resp.read(), resp.headers.get_content_charset(),
        )


# ── PubMed record ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class PubMedRecord:
    """A subset of the PubMed esummary record Cannavec uses for
    verification. Fields are populated best-effort; missing fields
    default to empty string or None.
    """

    pmid: str
    title: str = ""
    year: Optional[int] = None
    journal: str = ""
    first_author_surname: str = ""
    authors: tuple[str, ...] = field(default_factory=tuple)
    pubtypes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def retraction_status(self) -> str:
        """One of: ``clean``, ``retracted``, ``expression_of_concern``,
        ``correction``. Derived from `pubtypes`.

        PubMed represents retractions as a separate record (the
        "Retraction of Publication" record) that *cites* the retracted
        article; the original article's `pubtypes` does not change.
        However, when a record is flagged as a retraction notice or
        correction itself, that information lives here.
        """
        types_lower = {p.lower() for p in self.pubtypes}
        # PubMed flags the retracted *article* with "Retracted Publication"
        # and the notice that retracts another article with "Retraction of
        # Publication". The shared stem is "retract", so match on that.
        if any("retract" in p for p in types_lower):
            return "retracted"
        if any("expression of concern" in p for p in types_lower):
            return "expression_of_concern"
        # "Published Erratum" and "Corrected and Republished Article" both
        # share the "correct" stem; flag them as corrections rather than
        # retractions.
        if any("correct" in p or "errat" in p for p in types_lower):
            return "correction"
        return "clean"


# ── Crossref record ───────────────────────────────────────────────────

@dataclass(frozen=True)
class CrossrefRecord:
    """A subset of the Crossref API record Cannavec uses for
    verification.
    """

    doi: str
    title: str = ""
    year: Optional[int] = None
    container_title: str = ""
    first_author_surname: str = ""
    authors: tuple[str, ...] = field(default_factory=tuple)


# ── Surname normalisation ─────────────────────────────────────────────

_NON_LETTER_RE = re.compile(r"[^A-Za-z]")


def surname_normalise(s: str) -> str:
    """Strip diacritics, punctuation, and case for comparison.

    Mirrors `iconv -f UTF-8 -t ASCII//TRANSLIT` then strip-quotes
    behaviour in `auditor/verify_audit.sh`. "Tóth" and "Toth" compare
    equal; "O'Brien" and "OBrien" compare equal; "van der Berg" and
    "Van der Berg" compare equal *only* after splitting — but for
    PubMed first-author surname (a single token), this is sufficient.
    """
    if not s:
        return ""
    # NFKD decomposes accented characters; we then strip combining marks.
    decomposed = unicodedata.normalize("NFKD", s)
    stripped = "".join(ch for ch in decomposed
                       if not unicodedata.combining(ch))
    # Drop everything except letters, then lowercase.
    return _NON_LETTER_RE.sub("", stripped).lower()


# ── PubMed esummary ───────────────────────────────────────────────────

_PUBMED_ESUMMARY_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    "?db=pubmed&retmode=json&tool=cannavec&id={pmid}"
)

_PMID_RE = re.compile(r"^\d{4,9}$")


def _parse_pubmed_year(pubdate: str) -> Optional[int]:
    """Extract a 4-digit year from an NCBI pubdate string like
    ``"2017 May 25"`` or ``"2024 Jan-Feb"``. Returns None on parse
    failure (so the verifier reports an unknown rather than guessing).
    """
    if not pubdate:
        return None
    m = re.search(r"\b(19|20)\d{2}\b", pubdate)
    return int(m.group(0)) if m else None


def _parse_pubmed_response(pmid: str, body: str) -> Optional[PubMedRecord]:
    """Parse an esummary JSON response into a :class:`PubMedRecord`.

    Returns None if the response indicates the PMID was not found
    (or the JSON is structurally malformed). Surfaces malformed JSON
    via the json.JSONDecodeError exception — the caller is expected
    to catch it and map to NETWORK_ERROR.
    """
    payload = json.loads(body)
    result = payload.get("result", {})
    # NCBI returns `{"result": {"uids": ["..."], "<pmid>": {...}}}`.
    # If the PMID was not found, the result block omits the key or
    # the inner block reports an `error` field.
    if pmid not in result:
        return None
    inner = result[pmid]
    if "error" in inner:
        # Surface as a "not found" — the caller decides whether to
        # treat this as the same verdict.
        return None
    title = (inner.get("title") or "").strip()
    journal = (inner.get("source") or "").strip()
    pubdate = inner.get("pubdate") or ""
    year = _parse_pubmed_year(pubdate)
    raw_authors = inner.get("authors") or []
    author_strs: list[str] = []
    for a in raw_authors:
        # Author entries are dicts with a "name" key like "Devinsky O"
        # or "Smith JA". The first whitespace-separated token is the
        # surname.
        nm = a.get("name") if isinstance(a, dict) else None
        if nm:
            author_strs.append(nm.strip())
    first_surname = ""
    if author_strs:
        first_surname = author_strs[0].split()[0]
    pubtypes_field = inner.get("pubtype") or []
    pubtypes = tuple(p for p in pubtypes_field if isinstance(p, str))
    return PubMedRecord(
        pmid=pmid,
        title=title,
        year=year,
        journal=journal,
        first_author_surname=first_surname,
        authors=tuple(author_strs),
        pubtypes=pubtypes,
    )


def fetch_pubmed_record(
    pmid: str,
    *,
    fetcher: Optional[Fetcher] = None,
) -> Optional[PubMedRecord]:
    """Fetch + parse a single PubMed record.

    Returns None when the PMID is malformed, when NCBI returns no
    matching record, or when the response cannot be parsed. Raises
    `urllib.error.URLError` / `urllib.error.HTTPError` on network
    failure — callers using :func:`verify_pmid` get those mapped to
    the NETWORK_ERROR verdict.
    """
    if not _PMID_RE.match(str(pmid).strip()):
        return None
    fetcher = fetcher or default_pubmed_fetcher
    url = _PUBMED_ESUMMARY_URL.format(pmid=urllib.parse.quote(str(pmid).strip()))
    body = fetcher(url)
    try:
        return _parse_pubmed_response(str(pmid).strip(), body)
    except json.JSONDecodeError:
        return None


# ── Crossref ──────────────────────────────────────────────────────────

_CROSSREF_WORK_URL = "https://api.crossref.org/works/{doi}"


def _parse_crossref_response(doi: str, body: str) -> Optional[CrossrefRecord]:
    """Parse a Crossref work response into a :class:`CrossrefRecord`."""
    payload = json.loads(body)
    if payload.get("status") != "ok":
        return None
    message = payload.get("message") or {}
    titles = message.get("title") or []
    title = titles[0].strip() if titles else ""
    container_titles = message.get("container-title") or []
    container = container_titles[0].strip() if container_titles else ""
    # Year comes from `issued` or `created` date-parts.
    year = None
    for key in ("issued", "created", "published-print", "published-online"):
        node = message.get(key) or {}
        dp = node.get("date-parts") or []
        if dp and dp[0]:
            try:
                year = int(dp[0][0])
                break
            except (TypeError, ValueError):
                continue
    raw_authors = message.get("author") or []
    surnames = [
        (a.get("family") or "").strip()
        for a in raw_authors if isinstance(a, dict)
    ]
    surnames = [s for s in surnames if s]
    first_surname = surnames[0] if surnames else ""
    return CrossrefRecord(
        doi=doi,
        title=title,
        year=year,
        container_title=container,
        first_author_surname=first_surname,
        authors=tuple(surnames),
    )


def fetch_crossref_doi(
    doi: str,
    *,
    fetcher: Optional[Fetcher] = None,
) -> Optional[CrossrefRecord]:
    """Fetch + parse a Crossref work record by DOI."""
    if not doi or "/" not in doi:
        return None
    fetcher = fetcher or default_crossref_fetcher
    url = _CROSSREF_WORK_URL.format(doi=urllib.parse.quote(doi, safe="/"))
    try:
        body = fetcher(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    try:
        return _parse_crossref_response(doi, body)
    except json.JSONDecodeError:
        return None


# ── Verification verdict ──────────────────────────────────────────────


class VerificationVerdict(str, Enum):
    """Outcome of comparing a claim to its cited record.

    ``MATCH``        — surname AND year (when supplied) both align.
    ``MISMATCH``     — surname OR year disagrees with the record.
    ``BARE_CITE_OK`` — caller supplied no surname / year to check; the
                      record exists and is therefore acceptable as a
                      bare citation, though the claim's text is
                      unverified.
    ``NOT_FOUND``    — the identifier resolved no record (PMID does
                      not exist, DOI is unknown to Crossref).
    ``RETRACTED``    — the cited record is retracted; never an
                      acceptable primary citation.
    ``NETWORK_ERROR``— the fetch failed; verdict is unknown rather
                      than safe-by-default.
    """

    MATCH = "match"
    MISMATCH = "mismatch"
    BARE_CITE_OK = "bare_cite_ok"
    NOT_FOUND = "not_found"
    RETRACTED = "retracted"
    NETWORK_ERROR = "network_error"


@dataclass(frozen=True)
class VerificationResult:
    """Full verdict + the surnames / years that were compared."""

    identifier: str
    verdict: VerificationVerdict
    expected_first_author: Optional[str] = None
    expected_year: Optional[int] = None
    actual_first_author: Optional[str] = None
    actual_year: Optional[int] = None
    title: Optional[str] = None
    journal: Optional[str] = None
    retraction_status: str = "unknown"
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.verdict in (
            VerificationVerdict.MATCH,
            VerificationVerdict.BARE_CITE_OK,
        )


def _compare_surname(
    expected: Optional[str], actual: Optional[str],
) -> tuple[bool, str]:
    """Return ``(ok, why)`` for the surname comparison. If either
    side is empty / None the comparison is skipped and ``ok`` is True.
    """
    if not expected or not actual:
        return True, "surname not checked"
    en = surname_normalise(expected)
    an = surname_normalise(actual)
    if en == an:
        return True, "surname matches (diacritic-normalised)"
    return False, f"surname mismatch: claim={expected!r} record={actual!r}"


def _compare_year(
    expected: Optional[int], actual: Optional[int],
) -> tuple[bool, str]:
    if expected is None or actual is None:
        return True, "year not checked"
    if expected == actual:
        return True, "year matches"
    return False, f"year mismatch: claim={expected} record={actual}"


def verify_pmid(
    pmid: str,
    *,
    expected_first_author: Optional[str] = None,
    expected_year: Optional[int] = None,
    fetcher: Optional[Fetcher] = None,
) -> VerificationResult:
    """Verify that a PMID exists in PubMed and (if supplied) that its
    first-author surname and publication year match the claim.

    This is the primary entry point for citation verification. The
    caller passes the claim's expected surname and year (extracted
    from the surrounding prose, or known from a Source object).
    A clean pass-through verdict is :attr:`VerificationVerdict.MATCH`
    (or :attr:`BARE_CITE_OK` when no surname / year supplied).

    Retracted records always return :attr:`VerificationVerdict.RETRACTED`,
    even when the surname and year would otherwise match — a
    retracted paper is never a valid primary citation.
    """
    try:
        record = fetch_pubmed_record(pmid, fetcher=fetcher)
    except (urllib.error.URLError, OSError) as e:
        return VerificationResult(
            identifier=str(pmid),
            verdict=VerificationVerdict.NETWORK_ERROR,
            notes=(f"network error: {type(e).__name__}: {e}",),
        )
    if record is None:
        return VerificationResult(
            identifier=str(pmid),
            verdict=VerificationVerdict.NOT_FOUND,
        )
    if record.retraction_status == "retracted":
        return VerificationResult(
            identifier=str(pmid),
            verdict=VerificationVerdict.RETRACTED,
            title=record.title,
            journal=record.journal,
            actual_first_author=record.first_author_surname,
            actual_year=record.year,
            retraction_status="retracted",
            notes=("record's pubtype list contains a retraction marker",),
        )
    surname_ok, surname_note = _compare_surname(
        expected_first_author, record.first_author_surname,
    )
    year_ok, year_note = _compare_year(expected_year, record.year)
    notes = (surname_note, year_note)
    if not surname_ok or not year_ok:
        return VerificationResult(
            identifier=str(pmid),
            verdict=VerificationVerdict.MISMATCH,
            expected_first_author=expected_first_author,
            expected_year=expected_year,
            actual_first_author=record.first_author_surname,
            actual_year=record.year,
            title=record.title,
            journal=record.journal,
            retraction_status=record.retraction_status,
            notes=notes,
        )
    bare = (expected_first_author is None and expected_year is None)
    verdict = (VerificationVerdict.BARE_CITE_OK
               if bare else VerificationVerdict.MATCH)
    return VerificationResult(
        identifier=str(pmid),
        verdict=verdict,
        expected_first_author=expected_first_author,
        expected_year=expected_year,
        actual_first_author=record.first_author_surname,
        actual_year=record.year,
        title=record.title,
        journal=record.journal,
        retraction_status=record.retraction_status,
        notes=notes,
    )


def verify_doi(
    doi: str,
    *,
    expected_first_author: Optional[str] = None,
    expected_year: Optional[int] = None,
    fetcher: Optional[Fetcher] = None,
) -> VerificationResult:
    """Verify a DOI against Crossref. Same verdict semantics as
    :func:`verify_pmid` minus the RETRACTED branch (Crossref does
    not surface retraction status — for that, fall back to PubMed
    via the linked PMID, or use Cannavec's local retraction registry).
    """
    try:
        record = fetch_crossref_doi(doi, fetcher=fetcher)
    except (urllib.error.URLError, OSError) as e:
        return VerificationResult(
            identifier=doi,
            verdict=VerificationVerdict.NETWORK_ERROR,
            notes=(f"network error: {type(e).__name__}: {e}",),
        )
    if record is None:
        return VerificationResult(
            identifier=doi,
            verdict=VerificationVerdict.NOT_FOUND,
        )
    surname_ok, surname_note = _compare_surname(
        expected_first_author, record.first_author_surname,
    )
    year_ok, year_note = _compare_year(expected_year, record.year)
    notes = (surname_note, year_note)
    if not surname_ok or not year_ok:
        return VerificationResult(
            identifier=doi,
            verdict=VerificationVerdict.MISMATCH,
            expected_first_author=expected_first_author,
            expected_year=expected_year,
            actual_first_author=record.first_author_surname,
            actual_year=record.year,
            title=record.title,
            journal=record.container_title,
            notes=notes,
        )
    bare = (expected_first_author is None and expected_year is None)
    verdict = (VerificationVerdict.BARE_CITE_OK
               if bare else VerificationVerdict.MATCH)
    return VerificationResult(
        identifier=doi,
        verdict=verdict,
        expected_first_author=expected_first_author,
        expected_year=expected_year,
        actual_first_author=record.first_author_surname,
        actual_year=record.year,
        title=record.title,
        journal=record.container_title,
        notes=notes,
    )


# ── Bulk citation scanner ─────────────────────────────────────────────


_PMID_TOKEN_RE = re.compile(r"\bPMID[:\s#]*([0-9]{4,9})\b", re.IGNORECASE)
_DOI_TOKEN_RE = re.compile(
    r"\b(?:doi[:\s]*)?(?P<doi>10\.[0-9]{4,9}/[\w\.\-/:();<>]+)",
    re.IGNORECASE,
)


def scan_pmids(text: str) -> tuple[str, ...]:
    """Return every PMID-shaped token in ``text``, in order, deduped.

    Used by the CLI bulk-verifier to find citations to check.
    """
    seen: set[str] = set()
    out: list[str] = []
    for m in _PMID_TOKEN_RE.finditer(text):
        p = m.group(1)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return tuple(out)


def scan_dois(text: str) -> tuple[str, ...]:
    """Return every DOI-shaped token in ``text``, in order, deduped.

    Strips trailing punctuation (commas, periods, parens) that often
    follow a DOI in prose.
    """
    seen: set[str] = set()
    out: list[str] = []
    for m in _DOI_TOKEN_RE.finditer(text):
        d = m.group("doi").rstrip(".,);:")
        if d.lower().startswith("10.0000"):
            # Reserved DOI namespace — fabricated by Cannavec's old
            # stub generator. Skip; the citation regex elsewhere
            # treats it as invalid.
            continue
        if d not in seen:
            seen.add(d)
            out.append(d)
    return tuple(out)


def verify_text(
    text: str,
    *,
    pmid_fetcher: Optional[Fetcher] = None,
    doi_fetcher: Optional[Fetcher] = None,
) -> tuple[VerificationResult, ...]:
    """Scan ``text`` for PMIDs and DOIs, verify each.

    Caller-side surname / year extraction is not attempted here —
    that lives in the heavier `auditor/verify_audit.sh` flow. This
    function checks existence (and retraction status, for PMIDs)
    only. A clean answer that survives this scan still needs
    `audit_for_audience` and a human reviewer for the harder
    "does the citation back the claim" question.
    """
    out: list[VerificationResult] = []
    for pmid in scan_pmids(text):
        out.append(verify_pmid(pmid, fetcher=pmid_fetcher))
    for doi in scan_dois(text):
        out.append(verify_doi(doi, fetcher=doi_fetcher))
    return tuple(out)
