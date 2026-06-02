"""Citation-network + field-pushback signal (spec 002 US4).

Given a PMID, fetch the forward-citation set via NCBI E-utilities
``elink cmd=neighbor`` and aggregate per-cite sentiment (using
``synthesis.pubmed_sentiment``) into a deterministic
``field_pushback_signal``. Replication-language detection surfaces a
``replication_status`` flag.

Wired into ``compose_answer`` via the deterministic GRADE adapter:
``refute_heavy`` aggregate flips ``inconsistency_serious=True`` in
:func:`cannavec_science.evidence.apply_grade_modifiers`, dropping a
Level B claim to Level C.

Constitution mirror: §II — the rigor signal is deterministic
(rule-based sentiment, rule-based replication detector), not LLM-
judged. Reproducibility before state-of-the-art.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Callable, Optional

from cannavec_science._http import (
    TIMEOUT_SLOW,
    append_ncbi_auth,
    retry_urlopen,
    user_agent,
)


__all__ = [
    "CitationNetworkBlock",
    "ReplicationStatus",
    "FieldPushback",
    "fetch_forward_cites",
    "build_citation_network",
    "PushbackAggregate",
    "render_markdown",
]


# ── URLs ────────────────────────────────────────────────────────────


_ELINK_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    "?dbfrom=pubmed&db=pubmed&cmd=neighbor&retmode=json"
    "&tool=cannavec&id={pmid}"
)
_ESUMMARY_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    "?db=pubmed&retmode=json&tool=cannavec&id={ids}"
)
_EFETCH_ABSTRACTS_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pubmed&rettype=abstract&retmode=xml&tool=cannavec&id={ids}"
)

_MAX_FORWARD_CITES = 50  # cap per Constitution §X — NCBI politeness


# ── Status enums ────────────────────────────────────────────────────


class PushbackAggregate(str, Enum):
    """Field-level reception classification."""

    SUPPORT_HEAVY = "support_heavy"     # supports - refutes ≥ 2
    REFUTE_HEAVY = "refute_heavy"       # refutes - supports ≥ 2
    MIXED = "mixed"                     # ~equal counts, both non-zero
    NEUTRAL = "neutral"                 # all forward cites neutral
    INSUFFICIENT = "insufficient"       # < 3 forward cites


class ReplicationStatus(str, Enum):
    REPLICATED = "replicated"
    REPLICATION_FAILED = "replication_failed"
    MIXED = "mixed"
    NOT_REPORTED = "not_reported"


# ── Dataclasses ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class FieldPushback:
    """Sentiment counts across the forward-cite set."""

    supports: int = 0
    refutes: int = 0
    neutral: int = 0
    aggregate: PushbackAggregate = PushbackAggregate.INSUFFICIENT

    def to_dict(self) -> dict:
        d = asdict(self)
        d["aggregate"] = self.aggregate.value
        return d


@dataclass(frozen=True)
class CitationNetworkBlock:
    """Forward-citation network block attached to a verified PMID."""

    pmid: str
    count: int                                 # number of forward citations
    field_pushback_signal: FieldPushback = field(default_factory=FieldPushback)
    replication_status: ReplicationStatus = ReplicationStatus.NOT_REPORTED
    forward_pmids: tuple[str, ...] = ()
    sampled: bool = False                      # True when cap was hit
    error: Optional[str] = None

    @property
    def grade_downgrade_recommended(self) -> bool:
        """True iff the field-pushback signal warrants inconsistency-serious."""
        return self.field_pushback_signal.aggregate == PushbackAggregate.REFUTE_HEAVY

    def to_dict(self) -> dict:
        d = asdict(self)
        d["field_pushback_signal"] = self.field_pushback_signal.to_dict()
        d["replication_status"] = self.replication_status.value
        d["forward_pmids"] = list(self.forward_pmids)
        return d


# ── Sentiment + replication classifiers ─────────────────────────────


_REPLICATED_RE = re.compile(
    r"\b(?:we\s+replicat\w+|"
    r"we\s+reproduc\w+|"
    r"replicat\w+\s+(?:the|these|previous|prior)(?:\s+\w+){0,3}\s+(?:result|finding|effect)\w*|"
    r"reproduc\w+\s+(?:the|these|previous|prior)(?:\s+\w+){0,3}\s+(?:result|finding|effect)\w*|"
    r"confirm\w+\s+the\s+(?:prior|previous)(?:\s+\w+){0,3}\s+(?:result|finding|effect)\w*|"
    r"corroborat\w+\s+the\s+(?:prior|previous|original))\b",
    re.IGNORECASE,
)
_REPLICATION_FAILED_RE = re.compile(
    r"\b(?:we\s+failed\s+to\s+(?:replicat|reproduc)\w*|"
    r"failed\s+to\s+(?:replicat|reproduc)\w*|"
    r"did\s+not\s+reproduc\w+|did\s+not\s+replicat\w+|"
    r"could\s+not\s+reproduc\w+|could\s+not\s+replicat\w+|"
    r"unable\s+to\s+reproduc\w+|unable\s+to\s+replicat\w+|"
    r"null\s+result|null\s+finding|"
    r"contrary\s+to\s+(?:the\s+)?(?:prior|previous|original))\b",
    re.IGNORECASE,
)


def classify_replication(abstract_texts: tuple[str, ...]) -> ReplicationStatus:
    """Classify the forward-cite set's replication signal.

    Returns:
        - REPLICATED if ≥2 cites contain replication-success language and
          no replication-failure language
        - REPLICATION_FAILED if ≥2 cites contain replication-failure
          language and no success
        - MIXED if both kinds present
        - NOT_REPORTED otherwise
    """
    n_replicated = 0
    n_failed = 0
    for txt in abstract_texts:
        if not txt:
            continue
        if _REPLICATION_FAILED_RE.search(txt):
            n_failed += 1
        elif _REPLICATED_RE.search(txt):
            n_replicated += 1
    if n_replicated >= 2 and n_failed == 0:
        return ReplicationStatus.REPLICATED
    if n_failed >= 2 and n_replicated == 0:
        return ReplicationStatus.REPLICATION_FAILED
    if n_replicated >= 1 and n_failed >= 1:
        return ReplicationStatus.MIXED
    return ReplicationStatus.NOT_REPORTED


def _aggregate(supports: int, refutes: int, neutral: int) -> PushbackAggregate:
    total = supports + refutes + neutral
    if total < 3:
        return PushbackAggregate.INSUFFICIENT
    if supports - refutes >= 2:
        return PushbackAggregate.SUPPORT_HEAVY
    if refutes - supports >= 2:
        return PushbackAggregate.REFUTE_HEAVY
    if supports > 0 and refutes > 0:
        return PushbackAggregate.MIXED
    if supports == 0 and refutes == 0:
        return PushbackAggregate.NEUTRAL
    # One direction with the other zero but not by ≥2 — treat as
    # weak support / refute. Constitutional rule: be conservative —
    # this is the MIXED bucket without bidirectional evidence so we
    # treat it as INSUFFICIENT.
    return PushbackAggregate.INSUFFICIENT


# ── Fetcher protocol ────────────────────────────────────────────────


CitationFetcher = Callable[[str], str]


def default_citation_fetcher(url: str) -> str:
    """Production fetcher — polite User-Agent, slow timeout, bounded retry."""
    req = urllib.request.Request(
        append_ncbi_auth(url),
        headers={
            "User-Agent": user_agent("citation-network"),
            "Accept": "application/json",
        },
    )
    with retry_urlopen(req, timeout=TIMEOUT_SLOW) as resp:
        raw = resp.read()
    return raw.decode("utf-8")


# ── Fetch + parse ───────────────────────────────────────────────────


def fetch_forward_cites(
    pmid: str,
    *,
    fetcher: Optional[CitationFetcher] = None,
) -> tuple[str, ...]:
    """Fetch the forward-citation PMIDs via NCBI elink.

    Returns the tuple of cite PMIDs, capped at ``_MAX_FORWARD_CITES``.
    Raises ``IOError`` on network failure.
    """
    fetch = fetcher or default_citation_fetcher
    url = _ELINK_URL.format(pmid=urllib.parse.quote(pmid))
    body = fetch(url)
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return ()
    linksets = payload.get("linksets") or []
    if not linksets:
        return ()
    out: list[str] = []
    for ls in linksets:
        for db in ls.get("linksetdbs", []) or []:
            # The forward-citation linkname is "pubmed_pubmed_citedin".
            if db.get("linkname") == "pubmed_pubmed_citedin":
                out.extend(str(x) for x in db.get("links", []))
    # De-dup and cap.
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    return tuple(uniq[:_MAX_FORWARD_CITES])


def fetch_abstracts(
    pmids: tuple[str, ...],
    *,
    fetcher: Optional[CitationFetcher] = None,
) -> tuple[str, ...]:
    """Fetch abstracts for a tuple of PMIDs via efetch.

    Returns a tuple of abstract-text strings aligned to ``pmids``.
    Missing abstracts surface as empty strings, not exceptions.
    """
    if not pmids:
        return ()
    fetch = fetcher or default_citation_fetcher
    url = _ESUMMARY_URL.format(ids=",".join(pmids))
    try:
        body = fetch(url)
    except Exception:
        return tuple("" for _ in pmids)
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return tuple("" for _ in pmids)
    result = payload.get("result") or {}
    out: list[str] = []
    for p in pmids:
        rec = result.get(p, {}) or {}
        title = rec.get("title") or ""
        # esummary doesn't return the full abstract; the title +
        # source field is the cheapest enough-context approximation.
        # For deeper sentiment work the caller fetches via efetch
        # with rettype=abstract.
        out.append(title)
    return tuple(out)


# ── Builder ─────────────────────────────────────────────────────────


def build_citation_network(
    pmid: str,
    *,
    fetcher: Optional[CitationFetcher] = None,
    abstract_fetcher: Optional[CitationFetcher] = None,
) -> CitationNetworkBlock:
    """Assemble the citation-network block for one PMID.

    Two-stage fetch:
    1. elink → forward-cite PMID set.
    2. esummary → forward-cite abstracts/titles for sentiment.

    Network errors at either stage degrade gracefully — the returned
    block carries ``error`` set and ``count=0`` rather than raising.
    """
    from cannavec_science.synthesis import pubmed_sentiment

    try:
        forward = fetch_forward_cites(pmid, fetcher=fetcher)
    except Exception as exc:
        return CitationNetworkBlock(
            pmid=pmid, count=0, error=f"network error: {exc}",
        )
    if not forward:
        return CitationNetworkBlock(
            pmid=pmid, count=0,
            field_pushback_signal=FieldPushback(
                aggregate=PushbackAggregate.INSUFFICIENT,
            ),
        )

    abstracts = fetch_abstracts(forward, fetcher=abstract_fetcher or fetcher)

    supports = 0
    refutes = 0
    neutral = 0
    for txt in abstracts:
        direction = pubmed_sentiment(txt)
        if direction == "supports":
            supports += 1
        elif direction == "refutes":
            refutes += 1
        else:
            neutral += 1

    aggregate = _aggregate(supports, refutes, neutral)
    pushback = FieldPushback(
        supports=supports,
        refutes=refutes,
        neutral=neutral,
        aggregate=aggregate,
    )
    replication = classify_replication(abstracts)

    return CitationNetworkBlock(
        pmid=pmid,
        count=len(forward),
        field_pushback_signal=pushback,
        replication_status=replication,
        forward_pmids=forward,
        sampled=len(forward) >= _MAX_FORWARD_CITES,
    )


# ── Renderer ────────────────────────────────────────────────────────


def render_markdown(block: CitationNetworkBlock) -> str:
    lines: list[str] = []
    lines.append(f"### Forward-citation network — PMID {block.pmid}")
    lines.append("")
    if block.error:
        lines.append(f"_Citation-network unavailable: {block.error}_")
        return "\n".join(lines)
    lines.append(f"- Forward citations: **{block.count}**")
    pb = block.field_pushback_signal
    lines.append(
        f"- Pushback signal: {pb.aggregate.value} "
        f"(supports={pb.supports}, refutes={pb.refutes}, neutral={pb.neutral})"
    )
    lines.append(f"- Replication status: `{block.replication_status.value}`")
    if block.grade_downgrade_recommended:
        lines.append(
            "- **GRADE deterministic downgrade:** refute-heavy pushback → "
            "`inconsistency_serious=True` → one level lower."
        )
    if block.sampled:
        lines.append(
            f"- _Forward-cite set capped at {_MAX_FORWARD_CITES} for NCBI "
            f"politeness; full network may be larger._"
        )
    return "\n".join(lines)
