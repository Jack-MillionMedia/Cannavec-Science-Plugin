"""Cross-registry semantic retrieval over the curated knowledge base.

Why this module exists
----------------------
The composer (:func:`cannavec_science.answer.compose_answer`) routes a prompt
to curated rows through ~20 per-registry keyword/regex detectors. Those
detectors are high-precision but brittle: they are word-order- and
phrasing-sensitive, so a question like *"how does THC impair driving"* misses
the driving registry entirely (its detector wants the tokens ``thc driving
impair`` contiguous and in that order), and *"what CYP enzymes does CBD
inhibit"* misses the 100+ CYP interaction rows. The product then returns
**zero claims for knowledge it already holds** — the "we have it but didn't
find it" failure called out in the Improvement Plan §1.

This module fixes that by scoring **every curated row** against the prompt with
the same tested Okapi-BM25 engine the discovery ranker uses
(:mod:`cannavec_science.ranker`) and returning the best lexical matches
regardless of phrasing. BM25's inverse-document-frequency weighting does the
heavy lifting for free: generic tokens (``cannabis``, ``cbd``) are common
across the corpus and contribute little, so a bare definitional query stays
below threshold, while a rare, specific token (``bioavailability``,
``driving``, ``cyp2c19``) lights up exactly the rows that carry it.

Constitution fit
----------------
- **§X Stdlib-Only.** Pure stdlib; the BM25 math is reused from ``ranker``
  (also stdlib). The optional embedding / LLM *rerank* stage is **injected**
  (duck-typed, exactly like :mod:`cannavec_science.ranker_llm`) — the core and
  the offline test suite never need a third-party package. The embeddings
  layer the plan describes lives in the optional/website tier; this core layer
  is the always-available, deterministic floor it would reorder.
- **§I / §IX.** Retrieval surfaces **curated** rows only. Each surfaced row
  keeps its own identifier-anchored citations and deterministic GRADE; nothing
  is invented and nothing is promoted. Retrieval changes *which curated rows
  are found*, never *what counts as evidence*.
- **§VII.** Retrieval never assigns or alters a grade — the row's
  ``to_claim()`` carries its grade exactly as a detector hit would.

The module is read-only at runtime and offline-testable: the corpus is built
once from the curated registries and cached.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Sequence

from cannavec_science.ranker import Candidate, provenance_gate, score_candidates
# ``_tokens`` is ranker's internal tokenizer. We reuse it so the query-coverage
# gate tokenizes identically to the BM25 corpus (same stoplist + plural fold);
# any divergence would make the coverage fraction meaningless.
from cannavec_science.ranker import _tokens as _rank_tokens

__all__ = [
    "RetrievedRow",
    "retrieve",
    "corpus_size",
    "clear_corpus_cache",
    "DEFAULT_MIN_BM25",
    "DEFAULT_STRONG_BM25",
    "DEFAULT_MIN_COVERAGE",
]


# ── Tunable retrieval gates ────────────────────────────────────────────────
#
# A row is surfaced only when it clears these gates. The defaults were tuned on
# the canonical "we have it but didn't find it" misses (driving / CBD-PK / CYP /
# CHS) versus generic-definition and off-domain junk queries, so that the
# specific topical queries fire and the generic ones do not. See
# ``tests/test_retrieval.py`` for the pinned behaviour.
#
# ``DEFAULT_MIN_BM25``  — lexical-relevance floor for a multi-term match.
# ``DEFAULT_STRONG_BM25`` — a single, decisive term may pass on its own above
#                           this higher floor (so "tacrolimus" still works).
# ``DEFAULT_MIN_COVERAGE`` — at least this fraction of the query's distinct
#                            content tokens must appear in the row, which
#                            rejects an off-topic query that coincidentally
#                            shares one rare token with some row.
DEFAULT_MIN_BM25 = 6.0
DEFAULT_STRONG_BM25 = 11.0
DEFAULT_MIN_COVERAGE = 0.34


# ── Curated registries with row-level ``to_claim()`` ───────────────────────
#
# These are exactly the registries the composer threads through
# ``_attach_claim_safely`` — every row exposes ``to_claim()`` and
# identifier-anchored citations. The cannabinoid monographs (major/minor) and
# the eCBome reference render as *sections* rather than typed claims and fire
# reliably on the cannabinoid name already, so they are intentionally excluded
# here; retrieval's job is to catch the topical/claim registries the keyword
# detectors miss.
_CLAIM_REGISTRIES: tuple[tuple[str, str, str], ...] = (
    ("populations", "cannavec_science.populations", "all_populations"),
    ("interactions", "cannavec_science.interactions", "all_interactions"),
    ("adverse_events", "cannavec_science.adverse_events", "all_adverse_events"),
    ("contraindications", "cannavec_science.contraindications",
     "all_contraindications"),
    ("terpenes", "cannavec_science.terpenes", "all_terpenes"),
    ("pharmacogenomics", "cannavec_science.pharmacogenomics", "all_pgx_records"),
    ("analytical_chemistry", "cannavec_science.analytical_chemistry",
     "all_analytical_chemistry_rows"),
    ("cultivation_science", "cannavec_science.cultivation_science",
     "all_cultivation_science_rows"),
    ("pharmacokinetics", "cannavec_science.pharmacokinetics",
     "all_pharmacokinetics_rows"),
    ("use_disorder", "cannavec_science.use_disorder", "all_use_disorder_rows"),
    ("hyperemesis_syndrome", "cannavec_science.hyperemesis_syndrome",
     "all_hyperemesis_syndrome_rows"),
    ("ecbome_inhibitors", "cannavec_science.ecbome_inhibitors",
     "all_ecbome_inhibitor_rows"),
    ("biosynthesis", "cannavec_science.biosynthesis", "all_biosynthesis_rows"),
    ("pain_medicine", "cannavec_science.pain_medicine", "all_pain_medicine_rows"),
    ("psychiatry", "cannavec_science.psychiatry", "all_psychiatry_rows"),
    ("driving_impairment", "cannavec_science.driving_impairment",
     "all_driving_impairment_rows"),
    ("ptsd_anxiety_sleep", "cannavec_science.ptsd_anxiety_sleep",
     "all_ptsd_anxiety_sleep_rows"),
    ("endocrine", "cannavec_science.endocrine", "all_endocrine_rows"),
)


# ── Result type ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RetrievedRow:
    """One retrieved curated row, with its match diagnostics.

    ``row`` is the live registry object (carrying ``to_claim()`` + citations);
    callers attach it through the composer's normal claim path so retraction,
    GRADE, and wording checks all still apply.
    """

    registry: str
    row: object
    score: float          # final ranker score (BM25 × design × recency)
    bm25: float           # pure lexical relevance — the gate signal
    coverage: float       # fraction of distinct query tokens matched
    matched_terms: int    # count of distinct query tokens matched
    identifier: str       # synthetic corpus key (registry#index)


# ── Corpus construction (cached) ───────────────────────────────────────────

def _flatten_strings(obj, out: list) -> None:
    """Collect every string reachable in a nested dict / list / tuple."""
    if isinstance(obj, str):
        if obj:
            out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten_strings(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten_strings(v, out)
    # numbers / bools / None carry no retrievable text — skip.


def _row_name(row) -> str:
    """A human title for the row (used as the candidate ``title``)."""
    for attr in ("name", "label", "compound", "title"):
        v = getattr(row, attr, None)
        if isinstance(v, str) and v:
            return v
        # Some registries (e.g. terpenes) name rows with an Enum.
        if v is not None and hasattr(v, "value") and isinstance(v.value, str):
            return v.value
    return ""


def _row_text(row) -> str:
    """Build the searchable text for a row: every string field, the citation
    labels, and the claim text + source titles (the richest signal)."""
    parts: list[str] = []
    if hasattr(row, "to_dict"):
        try:
            _flatten_strings(row.to_dict(), parts)
        except Exception:  # noqa: BLE001 — a misbehaving row must not break the index
            parts = []
    if not parts:
        _flatten_strings(dict(getattr(row, "__dict__", {})), parts)
    # Defensively fold in the claim text + source titles even if to_dict()
    # omitted them, so a query always sees the full claim language.
    if hasattr(row, "to_claim"):
        try:
            claim = row.to_claim()
        except Exception:  # noqa: BLE001
            claim = None
        if claim is not None:
            if getattr(claim, "text", ""):
                parts.append(claim.text)
            for s in getattr(claim, "sources", ()) or ():
                if getattr(s, "title", ""):
                    parts.append(s.title)
    return " ".join(parts)


@dataclass(frozen=True)
class _Doc:
    identifier: str
    registry: str
    row: object
    candidate: Candidate
    token_set: frozenset


@lru_cache(maxsize=1)
def _corpus() -> tuple[_Doc, ...]:
    """Harvest one document per curated claim-bearing row. Built once."""
    docs: list[_Doc] = []
    idx = 0
    for registry, module_path, func_name in _CLAIM_REGISTRIES:
        try:
            module = importlib.import_module(module_path)
            rows = getattr(module, func_name)()
        except Exception:  # noqa: BLE001 — a missing registry must not break retrieval
            continue
        for row in rows:
            if not hasattr(row, "to_claim"):
                continue
            title = _row_name(row)
            abstract = _row_text(row)
            topic = getattr(row, "topic", "") or ""
            if not isinstance(topic, str):
                topic = str(topic)
            identifier = f"{registry}#{idx}"
            idx += 1
            candidate = Candidate(
                identifier=identifier,
                title=title,
                abstract=abstract,
                topic=topic,
                curated=True,
            )
            # Tokenise the SAME string ranker scores, so coverage is consistent
            # with the BM25 signal.
            token_set = frozenset(
                _rank_tokens(f"{title} {abstract} {topic}")
            )
            docs.append(_Doc(
                identifier=identifier,
                registry=registry,
                row=row,
                candidate=candidate,
                token_set=token_set,
            ))
    return tuple(docs)


def corpus_size() -> int:
    """Number of curated rows in the retrieval corpus."""
    return len(_corpus())


def clear_corpus_cache() -> None:
    """Drop the cached corpus (tests that mutate registries call this)."""
    _corpus.cache_clear()


# ── Retrieval ──────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    *,
    k: int = 8,
    min_bm25: float = DEFAULT_MIN_BM25,
    strong_bm25: float = DEFAULT_STRONG_BM25,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    reranker=None,
    now_year: Optional[int] = None,
) -> list[RetrievedRow]:
    """Return the best-matching curated rows for ``query``, best first.

    A row is surfaced only when it clears the lexical gates (a multi-term match
    above ``min_bm25`` with ``min_coverage`` query coverage, or a single
    decisive term above ``strong_bm25``) — so a generic definitional prompt or
    an off-domain query returns ``[]`` rather than a spurious claim.

    Parameters
    ----------
    k:
        Maximum rows to return.
    reranker:
        Optional duck-typed :class:`cannavec_science.ranker.RankerBackend`
        (e.g. :class:`cannavec_science.ranker_llm.LLMReranker`). When supplied,
        it reorders the gated shortlist (the deterministic order is the floor;
        the rerank is provenance-gated so it can only permute, never inject).
        Defaults to ``None`` — pure, offline, deterministic BM25.
    now_year:
        Passed through to the ranker's recency factor for determinism.
    """
    if not query or not query.strip():
        return []
    docs = _corpus()
    if not docs:
        return []

    qtokens = frozenset(_rank_tokens(query))
    if not qtokens:
        return []

    scores = score_candidates(
        query, [d.candidate for d in docs], now_year=now_year
    )

    gated: list[tuple[_Doc, float, float, float, int]] = []
    for d in docs:
        sb = scores.get(d.identifier)
        if sb is None:
            continue
        bm25 = sb.bm25
        if bm25 <= 0.0:
            continue
        matched = qtokens & d.token_set
        n_matched = len(matched)
        coverage = n_matched / len(qtokens)
        strong_single = n_matched >= 1 and bm25 >= strong_bm25
        multi_term = (
            n_matched >= 2 and bm25 >= min_bm25 and coverage >= min_coverage
        )
        if strong_single or multi_term:
            gated.append((d, sb.final, bm25, coverage, n_matched))

    # Deterministic order: final score desc, identifier asc as a stable tie-break.
    gated.sort(key=lambda t: (-t[1], t[0].identifier))
    shortlist = gated[:k]

    if reranker is not None and len(shortlist) > 1:
        shortlist = _apply_reranker(query, shortlist, reranker)

    return [
        RetrievedRow(
            registry=d.registry,
            row=d.row,
            score=final,
            bm25=bm25,
            coverage=coverage,
            matched_terms=n_matched,
            identifier=d.identifier,
        )
        for (d, final, bm25, coverage, n_matched) in shortlist
    ]


def _apply_reranker(
    query: str,
    shortlist: list,
    reranker,
) -> list:
    """Reorder the gated shortlist with an injected reranker, provenance-gated.

    The deterministic order is the floor: a backend may only permute the
    shortlist's own identifiers (an unknown identifier is dropped), so the LLM
    can never introduce a row the lexical stage did not surface (§I / §IX).
    """
    by_id = {t[0].identifier: t for t in shortlist}
    cands: Sequence[Candidate] = [t[0].candidate for t in shortlist]
    try:
        plan = reranker.plan(query, cands)
    except Exception:  # noqa: BLE001 — degrade to the deterministic floor
        return shortlist
    ordered_ids = provenance_gate(plan.order, set(by_id))
    reordered = [by_id[i] for i in ordered_ids]
    # Append any shortlist entry the backend omitted, in deterministic order.
    seen = set(ordered_ids)
    for t in shortlist:
        if t[0].identifier not in seen:
            reordered.append(t)
    return reordered
