"""Optional LLM reranking backend for :mod:`cannavec_science.ranker`.

This is the "Augment" layer: an LLM applies semantic judgement to reorder a
small shortlist of **already-verified** discovery candidates. It is held to
three structural rules that make it incapable of harming accuracy:

1. **Never a source of citations.** The model is shown an *identifier-free*
   shortlist and may only return integer **indices** into that list. It
   literally never sees or emits a PMID/DOI, so it cannot invent one
   (Constitution §I / §IX). The ranker pipeline additionally provenance-gates
   the result.
2. **Never assigns a grade.** The output schema has no grade field and the
   rubric forbids it (Constitution §VII). GRADE stays with the deterministic
   verify gate downstream.
3. **Reorders only.** Retracted rows are pinned last by the pipeline
   regardless of what the model says, and the deterministic score remains the
   visible floor.

Cost-efficiency is architectural: the pipeline calls this backend *only* when
the deterministic order is genuinely uncertain; the payload is a tiny
identifier-free shortlist with truncated abstracts; and the static rubric is
marked for **prompt caching**. The model defaults to ``claude-sonnet-4-6`` (the
operator's chosen rerank model — accuracy-equivalent to Opus for a bounded
rerank at lower cost and latency); override per call via ``model=``.

Stdlib-only at import time — the ``anthropic`` SDK is imported lazily, and
only when no client is injected — so the core ranker and the offline test
suite never depend on it. Pass a duck-typed ``client`` (anything exposing
``messages.create(...)``) to run fully offline.
"""

from __future__ import annotations

import json
from typing import Optional, Sequence

from cannavec_science.ranker import Candidate, RankPlan

__all__ = ["LLMReranker", "RUBRIC", "build_payload"]


# Default model — the skill's standard. NOT downgraded for cost; the savings
# come from the architecture (short-circuit, tiny payload, prompt caching).
_DEFAULT_MODEL = "claude-sonnet-4-6"


# The static, cacheable ranking rubric. Stable across every request, so it is
# sent with ``cache_control: {"type": "ephemeral"}`` and re-read cheaply on
# subsequent calls. Deliberately explicit about the hard rules.
RUBRIC = """\
You are the reranking stage of a cannabis-science research tool. You are given \
a QUERY and a numbered SHORTLIST of candidate primary-research papers that have \
already been discovered and verified by deterministic code. Your only job is to \
reorder the shortlist so the most useful papers come first.

You are NOT a source of citations. The shortlist is identifier-free on purpose. \
You may ONLY refer to papers by their integer index. Never output a PMID, DOI, \
title, author, or any identifier. Never add a paper that is not in the list. \
Never invent or guess a paper.

You do NOT assign evidence grades. Ranking is not grading. Do not output any \
GRADE level, certainty rating, or recommendation — a separate deterministic \
stage handles grading.

Rank by, in priority order:
1. Topical relevance — how directly the paper answers the QUERY.
2. Study-design strength — meta-analysis / systematic review > randomized \
controlled trial > cohort / observational > case report / narrative review.
3. Recency — used only to break ties between otherwise-equal papers.
4. Directness — human clinical evidence over mechanism/animal for a clinical \
query (and vice-versa for a mechanism query).

Any paper flagged "RETRACTED" must be ranked last.

Return ONLY a JSON object of this exact shape, covering EVERY index from the \
shortlist exactly once, best first. Every item MUST include a brief reason \
(<=12 words) naming the evidence type and why it ranks where it does:
{"ranking": [{"index": <int>, "reason": "<=12 words"}, ...]}
"""

# JSON-schema for structured output. Indices only; no place to smuggle an
# identifier or a grade.
_SCHEMA = {
    "type": "object",
    "properties": {
        "ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    # Required so every reranked row carries the model's own
                    # justification; otherwise the model sometimes omits it and
                    # the row falls back to the deterministic BM25 rationale.
                    "reason": {"type": "string"},
                },
                "required": ["index", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["ranking"],
    "additionalProperties": False,
}


def _truncate(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_payload(
    query: str,
    candidates: Sequence[Candidate],
    *,
    max_abstract_chars: int = 400,
) -> str:
    """Render the identifier-free user message for the shortlist.

    Exposed for offline testing: the payload must never contain a candidate's
    identifier — the model ranks indices, not citations.
    """
    lines = [f"QUERY: {query.strip()}", "", "SHORTLIST:"]
    for idx, c in enumerate(candidates):
        design = ", ".join(c.study_types) if c.study_types else "unspecified design"
        flag = "" if c.retraction_status == "clean" else f" [{c.retraction_status.upper()}]"
        year = c.year or "n.d."
        lines.append(f"[{idx}] ({year}; {design}){flag} {_truncate(c.title, 200)}")
        if c.abstract:
            lines.append(f"     {_truncate(c.abstract, max_abstract_chars)}")
        if c.topic:
            lines.append(f"     topic: {_truncate(c.topic, 80)}")
    lines.append("")
    lines.append(
        "Return the JSON ranking object now. Include every index exactly once."
    )
    return "\n".join(lines)


class LLMReranker:
    """LLM-backed :class:`cannavec_science.ranker.RankerBackend`.

    Parameters
    ----------
    client:
        A duck-typed Anthropic client (anything with ``messages.create``).
        If ``None``, an ``anthropic.Anthropic()`` is constructed lazily on
        first use (resolving ``ANTHROPIC_API_KEY`` from the environment), so
        importing this module never requires the SDK.
    model:
        Defaults to ``claude-sonnet-4-6``.
    effort:
        ``output_config`` effort. Defaults to ``"low"``: reranking ~10 candidates
        against an explicit rubric is a bounded task, and the accuracy
        guarantees (provenance gate, never-invent, deterministic floor) are
        structural — not effort-dependent. Low effort keeps the call fast enough
        to finish well inside a serverless timeout.
    timeout:
        Per-request wall-clock budget (seconds). If the model does not respond
        in time the call raises and the pipeline degrades to the deterministic
        order — so a slow model never hangs the request. Default 15s leaves
        headroom under a 30s serverless ``maxDuration`` after the live fan-out.
    """

    name = "llm"

    def __init__(
        self,
        client=None,
        *,
        model: str = _DEFAULT_MODEL,
        effort: str = "low",
        max_abstract_chars: int = 400,
        max_tokens: int = 1024,
        timeout: float = 15.0,
    ) -> None:
        self._client = client
        self.model = model
        self.effort = effort
        self.max_abstract_chars = max_abstract_chars
        self.max_tokens = max_tokens
        self.timeout = timeout

    # ── client ─────────────────────────────────────────────────────────
    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic  # lazy — keeps the core import stdlib-only
        except ImportError as exc:  # pragma: no cover - exercised via injection
            raise RuntimeError(
                "LLMReranker requires the 'anthropic' package or an injected "
                "client. Install anthropic, or pass client=... ."
            ) from exc
        # max_retries=0 — fail fast to the deterministic floor rather than let
        # SDK retries eat the serverless time budget on a slow/erroring call.
        self._client = anthropic.Anthropic(max_retries=0)
        return self._client

    # ── RankerBackend ──────────────────────────────────────────────────
    def plan(self, query: str, candidates: Sequence[Candidate]) -> RankPlan:
        """Return an LLM-proposed ordering as identifiers.

        Indices from the model are mapped back to identifiers here; any
        out-of-range or duplicate index is dropped and any candidate the model
        omitted is appended in its original order, so the returned plan is
        always a complete, valid permutation. The pipeline still
        provenance-gates the result.
        """
        cands = list(candidates)
        if not cands:
            return RankPlan(order=(), rationales={}, backend="llm")

        user_text = build_payload(
            query, cands, max_abstract_chars=self.max_abstract_chars
        )
        client = self._get_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": RUBRIC,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_text}],
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            timeout=self.timeout,
        )

        ranking = _parse_ranking(resp)
        order: list[str] = []
        rationales: dict[str, str] = {}
        seen: set[int] = set()
        for item in ranking:
            idx = item.get("index")
            if not isinstance(idx, int) or idx < 0 or idx >= len(cands):
                continue
            if idx in seen:
                continue
            seen.add(idx)
            ident = cands[idx].identifier
            order.append(ident)
            reason = item.get("reason")
            if isinstance(reason, str) and reason.strip():
                rationales[ident] = reason.strip()
        # Append any omitted candidates in their original (deterministic) order.
        for idx, c in enumerate(cands):
            if idx not in seen:
                order.append(c.identifier)

        return RankPlan(order=tuple(order), rationales=rationales, backend="llm")


def _parse_ranking(resp) -> list[dict]:
    """Extract the ``ranking`` array from a (possibly messy) model response.

    Tolerant of the real SDK response shape and injected fakes: concatenates
    text blocks, then loads JSON (falling back to the first ``{...}`` slice).
    Returns ``[]`` on anything unparseable, so the pipeline degrades to the
    deterministic floor.
    """
    text = _extract_text(resp)
    if not text:
        return []
    data = _loads_lenient(text)
    if not isinstance(data, dict):
        return []
    ranking = data.get("ranking")
    return ranking if isinstance(ranking, list) else []


def _extract_text(resp) -> str:
    # Plain string (simplest fakes).
    if isinstance(resp, str):
        return resp
    content = getattr(resp, "content", None)
    if content is None and isinstance(resp, dict):
        content = resp.get("content")
    if content is None:
        return ""
    parts: list[str] = []
    for block in content:
        t = getattr(block, "text", None)
        if t is None and isinstance(block, dict):
            t = block.get("text")
        if isinstance(t, str):
            parts.append(t)
    return "".join(parts)


def _loads_lenient(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None
