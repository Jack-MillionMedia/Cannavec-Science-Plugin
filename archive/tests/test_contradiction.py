"""Tests for cannavec.contradiction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.contradiction import (   # noqa: E402
    ContradictionType,
    compare_claims,
    scan_claims,
)


class TestDirectional(unittest.TestCase):
    def test_increase_vs_reduce_same_compound_outcome(self) -> None:
        a = "CBD reduces anxiety in healthy adults."
        b = "CBD increases anxiety in healthy adults at high doses."
        out = compare_claims(a, b)
        self.assertTrue(out)
        self.assertEqual(out[0].kind, ContradictionType.DIRECTIONAL)

    def test_no_shared_anchor_no_contradiction(self) -> None:
        a = "CBD reduces seizures in Dravet syndrome."
        b = "Δ⁹-THC reduces nausea in CINV."
        out = compare_claims(a, b)
        self.assertEqual(out, ())


class TestNumeric(unittest.TestCase):
    def test_disjoint_ranges_same_compound_metric_flag(self) -> None:
        a = "CBD oral bioavailability is 6-20%."
        b = "CBD oral bioavailability is 35-50%."
        out = compare_claims(a, b)
        self.assertTrue(any(c.kind == ContradictionType.NUMERIC for c in out))

    def test_overlapping_ranges_do_not_flag(self) -> None:
        a = "CBD oral bioavailability is 6-20%."
        b = "CBD oral bioavailability is 15-30%."
        out = compare_claims(a, b)
        self.assertFalse(any(c.kind == ContradictionType.NUMERIC for c in out))

    def test_different_units_do_not_compare(self) -> None:
        a = "Total THC was 10-15%."
        b = "Total THC was 100-150 mg."
        out = compare_claims(a, b)
        self.assertFalse(any(c.kind == ContradictionType.NUMERIC for c in out))


class TestAffirmDeny(unittest.TestCase):
    def test_affirm_vs_deny_same_anchor(self) -> None:
        a = "Cannabis is legal in California."
        b = "Cannabis is not legal in California."
        out = compare_claims(a, b)
        self.assertTrue(any(c.kind == ContradictionType.AFFIRM_DENY for c in out))


class TestScan(unittest.TestCase):
    def test_scan_finds_pairwise_contradictions(self) -> None:
        claims = [
            "CBD reduces seizures in Dravet syndrome.",
            "CBD increases seizures in Dravet syndrome.",
            "Nabiximols reduces spasticity.",
        ]
        out = scan_claims(claims)
        self.assertGreaterEqual(len(out), 1)

    def test_scan_empty_returns_empty(self) -> None:
        self.assertEqual(scan_claims([]), ())
        self.assertEqual(scan_claims(["one claim"]), ())


class TestOutcomeAnchorRequired(unittest.TestCase):
    """Directional and numeric contradictions require BOTH the
    compound AND the outcome anchor to be shared. Two claims on the
    same compound but different outcomes (e.g. 'CBD reduces seizures'
    vs 'CBD elevates ALT') are not contradictions — they are about
    different things. The docstring promised this; the implementation
    used to violate it."""

    def test_different_outcomes_same_compound_not_directional(self) -> None:
        a = "CBD reduces convulsive seizures in Dravet syndrome."
        b = "CBD elevates ALT/AST in valproate co-treated patients."
        out = compare_claims(a, b)
        self.assertEqual(
            [c for c in out if c.kind == ContradictionType.DIRECTIONAL],
            [],
            "'reduces seizures' vs 'elevates ALT' must not be a "
            "directional contradiction — different outcomes.",
        )

    def test_different_outcomes_same_compound_not_numeric(self) -> None:
        a = "Oral THC bioavailability is 6-20%."
        b = "THC half-life is 25-36 hours after chronic use."
        out = compare_claims(a, b)
        self.assertEqual(
            [c for c in out if c.kind == ContradictionType.NUMERIC],
            [],
            "Different outcomes with disjoint numeric ranges must not "
            "be a numeric contradiction.",
        )

    def test_true_directional_with_shared_outcome_still_fires(self) -> None:
        a = "CBD reduces convulsive seizures in Dravet syndrome."
        b = "CBD increases convulsive seizures in Dravet syndrome."
        out = compare_claims(a, b)
        self.assertTrue(
            any(c.kind == ContradictionType.DIRECTIONAL for c in out),
            "True directional contradiction (same compound + outcome, "
            "opposite directions) must still fire.",
        )

    def test_true_numeric_with_shared_outcome_still_fires(self) -> None:
        a = "Oral THC bioavailability is 6-20%."
        b = "Oral THC bioavailability is 35-50%."
        out = compare_claims(a, b)
        self.assertTrue(
            any(c.kind == ContradictionType.NUMERIC for c in out),
            "True numeric contradiction (same compound + outcome, "
            "disjoint ranges) must still fire.",
        )

    def test_seizure_plural_matches_outcome_anchor(self) -> None:
        # Regression: the seizures outcome alias was previously
        # singular-only, which meant directional contradictions with
        # plural 'seizures' wording silently dropped.
        a = "CBD reduces seizures in Dravet."
        b = "CBD increases seizures in Dravet."
        out = compare_claims(a, b)
        self.assertTrue(
            any(c.kind == ContradictionType.DIRECTIONAL for c in out)
        )


if __name__ == "__main__":
    unittest.main()
