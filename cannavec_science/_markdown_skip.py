"""Helpers for skipping markdown inline-code and fenced-code regions.

Banned-pattern and wording-vs-grade detectors operate on prose.
They are fooled when a brief's audit / discussion section *names* the
pattern in inline-code spans (e.g. mentioning ``cure`` as a banned-verb
example) or inside fenced code blocks (e.g. showing a CLI invocation
that prints "Cures cancer").

This module compiles the span list once per text and exposes a fast
"is this offset inside code?" check that the detectors apply to every
candidate match before recording a hit.

Coverage: single-backtick inline code (``` `code` ```) and
triple-backtick fenced code blocks (``` ```...``` ```). Indented
4-space code blocks are not recognised — they are rare in Cannavec
briefs and the surrounding-prose tests catch their content anyway.
"""

from __future__ import annotations

import re

# Inline code: a backtick, one-or-more non-backtick chars, a backtick.
# Non-greedy is unnecessary because the body is `[^`]+`.
_INLINE_CODE = re.compile(r"`[^`\n]+`")

# Fenced code: ``` (optionally followed by a language tag and newline)
# through the next matching ```. DOTALL so newlines are part of the body.
_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)


def code_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Return every inline-code and fenced-code span as (start, end) tuples.

    Fenced spans are computed first; inline spans that fall entirely
    inside a fenced span are skipped, so a single offset can never match
    twice.
    """
    fenced = tuple((m.start(), m.end()) for m in _FENCED_CODE.finditer(text))
    inline: list[tuple[int, int]] = []
    for m in _INLINE_CODE.finditer(text):
        s, e = m.span()
        if any(fs <= s and e <= fe for fs, fe in fenced):
            continue
        inline.append((s, e))
    return fenced + tuple(inline)


def is_in_code(spans: tuple[tuple[int, int], ...], position: int) -> bool:
    """True if ``position`` lies inside any of the supplied spans."""
    for s, e in spans:
        if s <= position < e:
            return True
    return False
