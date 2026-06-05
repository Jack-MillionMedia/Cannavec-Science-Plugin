"""Deterministic cross-source synthesizer — the elite-tier deliverable.

Spec 002 User Story 5 (Wave C). Pure function — NO I/O, NO LLM, NO
randomness. Same input → same output, every time.

Inputs: a ``per_source_rows`` dict mapping each source name to:

- ``list`` of row dicts/dataclasses on success (possibly empty), or
- ``None`` to mark the source unreachable.

Sources: ``"pubmed"``, ``"chembl"``, ``"ctgov"``, ``"preprint"``,
``"courtlistener"``.

Outputs: a :class:`SynthesisBlock` with:

- per-source row counts,
- convergence flag (STRONG / MIXED / WEAK / NONE),
- one-line disagreement description (or ``None``),
- unreachable-sources tuple,
- ``incomplete`` flag (True iff any source was unreachable).

## Convergence algorithm

1. Group rows into "claim clusters" by normalised
   ``(compound, condition)`` signature.
2. For each cluster, count distinct sources that contribute. A row is
   de-duplicated by its citation key (PMID / DOI / NCT) BEFORE
   counting — so the same RCT cited by both PubMed and CT.gov counts
   as ONE source-distinct supporter.
3. Convergence = max distinct-source-count across clusters.

   - >= 3 → STRONG
   - == 2 → MIXED
   - == 1 → WEAK
   - == 0 → NONE

## Disagreement algorithm

For each cluster, if the set of row directions includes both
``"supports"`` AND ``"refutes"``, emit a one-line disagreement note
listing supporters vs refuters.

Direction is inferred per-source:

- PubMed / preprint: parse abstract sentiment via the rule-based
  ``pubmed_sentiment()`` helper ("did not improve" → refutes,
  "significantly improved" / "efficacious" → supports, else neutral).
- ChEMBL: neutral (binding ≠ clinical claim).
- CT.gov: neutral by default; completed-with-posted-results trials
  parse sentiment from the results text. (Conservative for now —
  the row shape from ctgov_discover.py doesn't carry results text.)
- CourtListener: neutral (a court ruling is not evidence of efficacy).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


__all__ = [
    "ClaimCluster",
    "Convergence",
    "SynthesisBlock",
    "build_claim_clusters",
    "pubmed_sentiment",
    "render_json",
    "render_markdown",
    "synthesize",
]


# ── Constants ────────────────────────────────────────────────────────


_SOURCE_KEYS = (
    "pubmed",
    "chembl",
    "ctgov",
    "preprint",
    "courtlistener",
    # Cannabis-primary-source widening (life-science skill layer).
    "pubchem",
    "pharmgkb",
    "rcsb",
    "opentargets",
    "gwas",
    "bindingdb",
    # Spec 002 US1 — preprint lanes treated as distinct sources for
    # the cross-source convergence verdict. The generic "preprint"
    # key above stays for back-compat (legacy fixtures); biorxiv +
    # medrxiv are the per-server lanes.
    "biorxiv",
    "medrxiv",
    # Spec 005 US6 — Europe PMC twelfth primary-source live lane.
    "europepmc",
    # Spec 029 — EBI chemical-ontology + functional-annotation lanes. These
    # are context lanes: a ChEBI row clusters on its compound (like PubChem),
    # a QuickGO row carries no clinical condition, so neither manufactures a
    # clinical convergence verdict — they appear in the per-source counts.
    "chebi",
    "quickgo",
    # Spec 030 — pathway + disease-ontology context lanes. Reactome rows cluster
    # on the pathway name's first token, EFO rows on the indication phrase — both
    # off the cannabinoid axis, so neither manufactures a cannabinoid convergence
    # verdict; they appear in the per-source counts.
    "reactome",
    "efo",
)


# Direction-classification regexes. Order matters: a single abstract
# can match BOTH a "did not improve" refutation AND a "significantly"
# support, so we test refutation first (most cautious).
_REFUTE_RE = re.compile(
    r"\b("
    r"no significant difference|"
    r"did not improve|"
    r"did not differ|"
    r"failed to show|"
    r"no benefit|"
    r"not efficacious|"
    r"non-?inferior(?! to)|"
    r"adverse effect outweighed|"
    r"increased adverse"
    r")\b",
    re.IGNORECASE,
)

_SUPPORT_RE = re.compile(
    r"\b("
    r"significantly improved|"
    r"significantly reduced|"
    r"significant improvement|"
    r"significant reduction|"
    r"efficacious|"
    r"efficacy was demonstrated|"
    r"clinically meaningful improvement"
    r")\b",
    re.IGNORECASE,
)


_DISCLAIMER = (
    "Deterministic rule-based synthesis. Read the per-source sections "
    "below for the underlying evidence."
)


# ── Enums ────────────────────────────────────────────────────────────


class Convergence(str, Enum):
    STRONG = "STRONG"
    MIXED = "MIXED"
    WEAK = "WEAK"
    NONE = "NONE"


# ── Dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClaimCluster:
    compound: str
    condition: str
    members: tuple[tuple[str, dict], ...]  # (source_name, normalised_row)

    @property
    def distinct_sources(self) -> set[str]:
        return {src for src, _ in self.members}


@dataclass(frozen=True)
class SynthesisBlock:
    per_source_counts: dict
    convergence: Convergence
    disagreement: Optional[str]
    unreachable_sources: tuple[str, ...] = ()
    incomplete: bool = False
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "per_source_counts": dict(self.per_source_counts),
            "convergence": self.convergence.value,
            "disagreement": self.disagreement,
            "unreachable_sources": list(self.unreachable_sources),
            "incomplete": self.incomplete,
            "disclaimer": self.disclaimer,
        }


# ── Direction inference ──────────────────────────────────────────────


def pubmed_sentiment(text: str) -> str:
    """Rule-based sentiment direction for a PubMed/preprint abstract.

    Returns one of ``"supports"``, ``"refutes"``, ``"neutral"``.

    Refutation patterns are checked FIRST (conservative). When both
    fire, refutation wins to surface the disagreement signal.
    """
    if not text:
        return "neutral"
    if _REFUTE_RE.search(text):
        return "refutes"
    if _SUPPORT_RE.search(text):
        return "supports"
    return "neutral"


def _row_direction(source: str, row: dict) -> str:
    """Direction for one row, dispatched on source."""
    if source in ("pubmed", "preprint", "biorxiv", "medrxiv"):
        text = row.get("abstract") or row.get("title") or ""
        return pubmed_sentiment(text)
    if source == "ctgov":
        # The current CT.gov shape carries only protocol-level fields;
        # results text isn't surfaced. Neutral until results are
        # available.
        text = row.get("results_text") or ""
        if text:
            return pubmed_sentiment(text)
        return "neutral"
    # ChEMBL and CourtListener are neutral with respect to clinical
    # direction by source nature.
    return "neutral"


# ── Citation-key extraction ──────────────────────────────────────────


def _citation_key(source: str, row: dict) -> str:
    """The canonical identifier used for cross-source de-duplication.

    A PubMed-cited-by-CT.gov trial whose results-paper is in PubMed
    should NOT look like cross-source convergence; this key collapses
    such rows.

    Resolution order:
    1. ``pmid`` (any source that carries it)
    2. ``doi`` (preprints, some PubMed)
    3. ``nct_id`` (CT.gov)
    4. ``opinion_id`` (CourtListener)
    5. ``chembl_id`` (ChEMBL)
    6. ``native_id`` (fallback)
    7. ``source:title`` (last-resort fallback)
    """
    for k in (
        "pmid",
        "doi",
        "nct_id",
        "opinion_id",
        "chembl_id",
        # Cannabis-primary-source widening: each life-science source
        # contributes a canonical identifier so cross-source de-dup
        # collapses two rows that cite the same primary record.
        "cid",
        "accession_id",
        "pdb_id",
        "ensembl_id",
        "monomer_id",
        "native_id",
    ):
        v = row.get(k)
        if v:
            return f"{k}:{v}"
    title = row.get("title") or ""
    return f"{source}:{title}"


# ── Cluster signature ────────────────────────────────────────────────


_WS_RE = re.compile(r"\s+")


def _normalise(s: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation we don't care
    about."""
    s = (s or "").lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = _WS_RE.sub(" ", s)
    return s


def _row_compound(source: str, row: dict) -> str:
    """The compound this row makes a claim about."""
    explicit = row.get("_compound")
    if explicit:
        return _normalise(explicit)
    # Heuristic: pull from title.
    title = row.get("title") or ""
    title = title.lower()
    for needle in ("cbd", "cannabidiol", "thc", "tetrahydrocannabinol",
                   "cbg", "cbn", "cbc", "thcv", "cbdv"):
        if needle in title:
            return needle
    return _normalise(title.split()[0]) if title else ""


def _row_condition(source: str, row: dict) -> str:
    """The condition this row claims about (or '' for non-clinical sources)."""
    explicit = row.get("_condition")
    if explicit is not None:
        return _normalise(explicit)
    # Heuristic from title.
    title = row.get("title") or ""
    title = title.lower()
    for needle in ("epilepsy", "seizure", "anxiety", "sleep", "insomnia",
                   "pain", "ptsd", "cancer", "nausea", "spasticity"):
        if needle in title:
            return needle
    return ""


# ── Cluster builder ──────────────────────────────────────────────────


def build_claim_clusters(
    per_source_rows: dict,
) -> list[ClaimCluster]:
    """Group rows into (compound, condition) clusters.

    The returned clusters' ``members`` carry the source name + a
    normalised row dict including the ``direction`` field.

    De-duplication: within a single cluster, rows that share a
    citation key collapse to ONE member. The source of that surviving
    member is the LEXICOGRAPHICALLY FIRST source name — a deterministic
    tiebreak that matches the test-suite expectations.
    """
    # Collect (source, citation_key) → (compound, condition, direction, row).
    # Then group by (compound, condition).
    by_cluster: dict[tuple[str, str], dict[str, tuple[str, dict]]] = {}
    # The inner key is the citation_key → (source, row). When two sources
    # cite the same key, the lexicographically first source wins.
    for source in _SOURCE_KEYS:
        rows = per_source_rows.get(source) or []
        for raw in rows:
            row = dict(raw) if isinstance(raw, dict) else _row_to_dict(raw)
            compound = _row_compound(source, row)
            condition = _row_condition(source, row)
            cluster_key = (compound, condition)
            cit_key = _citation_key(source, row)
            row["direction"] = _row_direction(source, row)
            inner = by_cluster.setdefault(cluster_key, {})
            existing = inner.get(cit_key)
            if existing is None or source < existing[0]:
                inner[cit_key] = (source, row)

    clusters: list[ClaimCluster] = []
    for (compound, condition), inner in sorted(by_cluster.items()):
        members = tuple(sorted(inner.values(), key=lambda sr: (sr[0], _citation_key(sr[0], sr[1]))))
        clusters.append(
            ClaimCluster(
                compound=compound, condition=condition, members=members,
            )
        )
    return clusters


def _row_to_dict(row) -> dict:
    """Coerce a dataclass or other row type to a dict."""
    try:
        return asdict(row)
    except TypeError:
        return dict(row.__dict__) if hasattr(row, "__dict__") else {}


# ── Convergence + disagreement rules ─────────────────────────────────


def _convergence_for_clusters(clusters: list[ClaimCluster]) -> Convergence:
    if not clusters:
        return Convergence.NONE
    # Only consider clusters that have at least one supporter (a "supports"
    # or default-direction member is enough — neutral rows count toward
    # presence but not direction conflict).
    max_distinct = 0
    for cluster in clusters:
        # A cluster with no extractable subject (empty compound AND empty
        # condition) is a sentinel: every row whose subject we could not parse
        # collapses here, so counting its distinct sources would manufacture
        # cross-source agreement among rows that share nothing. Exclude it from
        # the verdict (it still appears in per-source counts).
        if not cluster.compound and not cluster.condition:
            continue
        distinct = len(cluster.distinct_sources)
        if distinct > max_distinct:
            max_distinct = distinct
    if max_distinct >= 3:
        return Convergence.STRONG
    if max_distinct == 2:
        return Convergence.MIXED
    if max_distinct == 1:
        return Convergence.WEAK
    return Convergence.NONE


def _first_disagreement(
    clusters: list[ClaimCluster],
) -> Optional[str]:
    """Return the first cluster's disagreement description, or None."""
    for cluster in clusters:
        # Skip the ('', '') sentinel cluster for the same reason convergence
        # does: subjectless rows share no subject, so an apparent supports-vs-
        # refutes split among them is not a real disagreement.
        if not cluster.compound and not cluster.condition:
            continue
        directions = {row.get("direction", "neutral") for _, row in cluster.members}
        if {"supports", "refutes"}.issubset(directions):
            supporters = sorted({
                src for src, row in cluster.members
                if row.get("direction") == "supports"
            })
            refuters = sorted({
                src for src, row in cluster.members
                if row.get("direction") == "refutes"
            })
            label = cluster.compound or "?"
            condition_part = (
                f" for {cluster.condition}" if cluster.condition else ""
            )
            return (
                f"{label}{condition_part}: "
                f"{', '.join(supporters)} supports; "
                f"{', '.join(refuters)} refutes."
            )
    return None


# ── Public entry point ───────────────────────────────────────────────


def synthesize(
    query: str,
    per_source_rows: dict,
) -> SynthesisBlock:
    """Compute the synthesis block for one cross-source fanout result.

    See module docstring for the deterministic algorithm.
    """
    unreachable = tuple(
        sorted(
            s for s in _SOURCE_KEYS
            if per_source_rows.get(s, []) is None
        )
    )
    counts = {
        s: (len(per_source_rows.get(s) or []))
        for s in _SOURCE_KEYS
    }

    # Build clusters only over reachable sources with rows.
    reachable_rows = {
        s: per_source_rows.get(s) or []
        for s in _SOURCE_KEYS
    }
    clusters = build_claim_clusters(reachable_rows)

    convergence = _convergence_for_clusters(clusters)
    disagreement = _first_disagreement(clusters)

    return SynthesisBlock(
        per_source_counts=counts,
        convergence=convergence,
        disagreement=disagreement,
        unreachable_sources=unreachable,
        incomplete=bool(unreachable),
    )


# ── Renderers ────────────────────────────────────────────────────────


_SOURCE_DISPLAY = {
    "pubmed": "PubMed",
    "chembl": "ChEMBL",
    "ctgov": "CT.gov",
    "preprint": "Preprints",
    "courtlistener": "CourtListener",
    "pubchem": "PubChem",
    "pharmgkb": "PharmGKB",
    "rcsb": "RCSB PDB",
    "opentargets": "Open Targets",
    "gwas": "GWAS Catalog",
    "bindingdb": "BindingDB",
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
    # Spec 005 US6 — Europe PMC.
    "europepmc": "Europe PMC",
    # Spec 029 — EBI chemical-ontology + functional-annotation lanes.
    "chebi": "ChEBI",
    "quickgo": "QuickGO",
    # Spec 030 — pathway + disease-ontology lanes.
    "reactome": "Reactome",
    "efo": "EFO",
}


def render_markdown(block: SynthesisBlock) -> str:
    lines: list[str] = []
    lines.append("SYNTHESIS")
    for s in _SOURCE_KEYS:
        count = block.per_source_counts.get(s, 0)
        label = _SOURCE_DISPLAY[s]
        if s in block.unreachable_sources:
            lines.append(f"- {label}: unreachable")
        else:
            lines.append(f"- {label}: {count}")
    lines.append(f"- Convergence: {block.convergence.value}")
    lines.append(
        f"- Disagreement: {block.disagreement or 'none flagged'}"
    )
    lines.append(
        f"- Unreachable: "
        f"{', '.join(block.unreachable_sources) if block.unreachable_sources else 'none'}"
    )
    lines.append(f"- Disclaimer: {block.disclaimer}")
    return "\n".join(lines)


def render_json(block: SynthesisBlock) -> str:
    return json.dumps(block.to_dict(), indent=2)
