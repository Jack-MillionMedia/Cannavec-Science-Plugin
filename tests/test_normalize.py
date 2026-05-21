"""Tests for cannavec._normalize cannabinoid-name normalisation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science._normalize import (   # noqa: E402
    normalize_cannabinoid_query,
    normalized_contains,
)


class TestNormalizeCannabinoidQuery(unittest.TestCase):
    """The normaliser flattens unicode superscript digits, canonicalises
    the delta prefix, and lowercases so substring matching across CLI
    inputs and registry values is robust."""

    def test_superscript_to_ascii_digit(self) -> None:
        self.assertEqual(
            normalize_cannabinoid_query("Δ⁹-THC"),
            normalize_cannabinoid_query("Δ9-THC"),
        )

    def test_delta_word_prefix_normalised(self) -> None:
        self.assertEqual(
            normalize_cannabinoid_query("delta-9-THC"),
            normalize_cannabinoid_query("Δ9-THC"),
        )
        self.assertEqual(
            normalize_cannabinoid_query("delta 9 THC"),
            normalize_cannabinoid_query("Δ9 THC"),
        )

    def test_idempotent(self) -> None:
        for s in ["Δ⁹-THC", "Δ9-THC", "delta-9-THC", "CBD", "Δ⁸-THC"]:
            once = normalize_cannabinoid_query(s)
            self.assertEqual(once, normalize_cannabinoid_query(once))

    def test_lowercases(self) -> None:
        self.assertEqual(
            normalize_cannabinoid_query("CBD"),
            normalize_cannabinoid_query("cbd"),
        )

    def test_empty_returns_empty(self) -> None:
        self.assertEqual(normalize_cannabinoid_query(""), "")


class TestNormalizedContains(unittest.TestCase):
    """The matching helper handles the substring contract with
    normalisation on both sides."""

    def test_none_needle_matches_all(self) -> None:
        self.assertTrue(normalized_contains("Δ⁹-THC", None))

    def test_ascii_query_matches_superscript_registry(self) -> None:
        # The original CLI bug: Δ9-THC (CLI input) failed to match
        # Δ⁹-THC (registry storage).
        self.assertTrue(normalized_contains("Δ⁹-THC", "Δ9-THC"))

    def test_delta_word_matches_symbol(self) -> None:
        self.assertTrue(normalized_contains("Δ⁹-THC", "delta-9-THC"))
        self.assertTrue(normalized_contains("Δ⁹-THC", "delta 9 THC"))

    def test_canonical_form_matches_itself(self) -> None:
        self.assertTrue(normalized_contains("Δ⁹-THC", "Δ⁹-THC"))

    def test_regular_compounds_still_match(self) -> None:
        # Backward compatibility: simple ASCII names must still match.
        self.assertTrue(normalized_contains("CBD", "CBD"))
        self.assertTrue(normalized_contains("CBD", "cbd"))


if __name__ == "__main__":
    unittest.main()
