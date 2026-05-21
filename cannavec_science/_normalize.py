"""Cannabinoid-name normalisation for registry queries.

The curated registries store cannabinoid names with proper isomer
prefixes — `Δ⁹-THC`, `Δ⁸-THC`, `THCA`, `CBD` — using unicode super-
script digits. Users querying from the CLI typically type ASCII
forms like `Δ9-THC` or `delta-9-THC`. Without normalisation,
`--cannabinoid "Δ9-THC"` returns no hits because the substring
match never finds the superscript form.

This module exposes :func:`normalize_cannabinoid_query`, a pure
function that returns the lowercase, super-script-flattened,
delta-prefix-canonicalised form of a name. Apply it to both the
query AND the registry value before substring-matching.

Stdlib only. Idempotent.
"""

from __future__ import annotations

import re

# Map every unicode superscript digit to its ASCII counterpart.
_SUPERSCRIPT_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

# Canonicalise "delta-9 / delta 9 / Δ9 / Δ⁹" → "Δ" + digit so the
# substring "Δ9" inside the normalised form matches every variant.
_DELTA_PREFIX = re.compile(r"\b(?:delta[-\s]?|Δ\s*)", re.IGNORECASE)

# Collapse runs of internal whitespace and hyphens so that "Δ9 THC",
# "Δ9-THC", and "Δ⁹-THC" all collapse to the same key. Cannabinoid
# names are punctuation-irrelevant for matching purposes.
_INTERNAL_SEP = re.compile(r"[\s\-]+")


def normalize_cannabinoid_query(s: str) -> str:
    """Return the comparison-canonical form of a cannabinoid name.

    Applies, in order:

    1. Unicode superscript-digit flattening (⁹ → 9).
    2. ``delta-9`` / ``Δ9`` / ``Δ 9`` → ``Δ9`` (single canonical prefix).
    3. Internal whitespace and hyphens collapsed away so separator
       choice does not affect matching.
    4. Lowercase.

    The result is intended for substring matching only; it is not
    a display form.
    """
    if not s:
        return s
    flat = s.translate(_SUPERSCRIPT_DIGITS)
    canonical = _DELTA_PREFIX.sub("Δ", flat)
    collapsed = _INTERNAL_SEP.sub("", canonical)
    return collapsed.lower()


def normalized_contains(haystack: str, needle: str | None) -> bool:
    """Substring match after normalisation. ``None`` needle matches all."""
    if needle is None:
        return True
    return normalize_cannabinoid_query(needle) in normalize_cannabinoid_query(haystack)
