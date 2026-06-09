"""Offline, substring-verified snippet extraction for live findings (spec 036).

A live finding becomes *informative* when it can show a short piece of its
source — but the project's evidence floor (Constitution §I / M5) forbids any
paraphrase: surfaced source text must be a TRUE substring of the abstract, never
a model reflow. This module ports the archived flywheel's deterministic
``_supporting_sentence`` extractor and keeps its hard guarantee — it picks the
abstract sentence with the most content-word overlap with an anchor (the title
or query), then confirms it is a literal substring via
:func:`cannavec_science.claim_support.verify_quote`. A candidate that is not a
verbatim slice is dropped: the caller gets **no** snippet rather than a
fabrication.

Pure stdlib, no network, no LLM — the same offline determinism the curated core
demands (Constitution §X).
"""

from __future__ import annotations

import re

__all__ = ["supporting_snippet"]

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]{3,}")
_STOP = frozenset(
    "with that this from were have been into than then they them their there "
    "which while about against between compared placebo patients study trial "
    "results conclusion methods background versus among".split()
)
# A direction term (reduced / increased / no effect / …) breaks ties so the
# surfaced sentence is the one that actually carries a finding, not a methods
# line — exactly the archived extractor's heuristic.
_DIRECTION = ("reduc", "decreas", "increas", "improv", "lower", "raise",
              "inhibit", "induc", "no effect", "no significant", "worsen")


def _content_words(text: str) -> list[str]:
    return [w for w in (m.group(0).lower() for m in _WORD.finditer(text))
            if w not in _STOP]


def supporting_snippet(anchor: str, abstract: str) -> str:
    """Verbatim abstract sentence that best anchors ``anchor`` (title/query).

    Scores each abstract sentence by shared content words with ``anchor`` (a
    direction term breaks ties), and returns the best sentence ONLY after
    confirming it is a literal substring of ``abstract`` via
    :func:`~cannavec_science.claim_support.verify_quote`. A fabricated or
    paraphrased candidate can never slip through — the function returns ``""``
    rather than a non-verbatim span (Constitution §I / M5).
    """
    from cannavec_science.claim_support import verify_quote

    if not abstract or not anchor:
        return ""
    anchor_terms = set(_content_words(anchor))
    if not anchor_terms:
        return ""
    best, best_score = "", 0.0
    for sent in (s.strip() for s in _SENT_SPLIT.split(abstract)):
        if not sent:
            continue
        low = sent.lower()
        overlap = len(anchor_terms & set(_content_words(sent)))
        if overlap == 0:
            continue
        score = overlap + (0.5 if any(d in low for d in _DIRECTION) else 0.0)
        if score > best_score:
            best, best_score = sent, score
    return best if best and verify_quote(best, abstract) else ""
