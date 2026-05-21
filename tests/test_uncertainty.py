"""Tests for cannavec.uncertainty."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.evidence import ClaimType, EvidenceLevel   # noqa: E402
from cannavec_science.uncertainty import (   # noqa: E402
    acceptable_verbs,
    confidence_band_for,
    confidence_consistent,
    detect_declared_level,
    grade_wording_consistency,
    pick_wording,
)


class TestAcceptableVerbs(unittest.TestCase):
    def test_level_a_has_strong_verbs(self) -> None:
        verbs = acceptable_verbs(EvidenceLevel.A)
        self.assertIn("established", verbs)

    def test_level_c_has_hedged_verbs(self) -> None:
        verbs = acceptable_verbs(EvidenceLevel.C)
        self.assertTrue(any("may" in v for v in verbs))


class TestPickWording(unittest.TestCase):
    def test_level_a_clinical_efficacy_is_strong(self) -> None:
        self.assertEqual(
            pick_wording(EvidenceLevel.A, ClaimType.CLINICAL_EFFICACY),
            "is effective for",
        )

    def test_level_c_clinical_efficacy_hedges(self) -> None:
        self.assertEqual(
            pick_wording(EvidenceLevel.C, ClaimType.CLINICAL_EFFICACY),
            "may reduce",
        )

    def test_unsupported_says_no_admissible(self) -> None:
        out = pick_wording(EvidenceLevel.UNSUPPORTED, ClaimType.MECHANISM)
        self.assertIn("no admissible", out)


class TestGradeWordingConsistency(unittest.TestCase):
    def test_level_c_with_established_verb_is_violation(self) -> None:
        text = "Cannabis is established to reduce chronic pain."
        violations = grade_wording_consistency(text, EvidenceLevel.C)
        self.assertGreaterEqual(len(violations), 1)
        self.assertTrue(any("established" in v.matched_phrase for v in violations))

    def test_level_b_with_established_verb_is_violation(self) -> None:
        # "established" implies Level A certainty; a Level B claim must not use it.
        # This guards against the most common grade-inflation pattern: a single
        # RCT labelled "established" when the evidence cap is Level B.
        text = "Nabiximols is established to reduce MS spasticity."
        violations = grade_wording_consistency(text, EvidenceLevel.B)
        self.assertGreaterEqual(len(violations), 1)
        self.assertTrue(any("established" in v.matched_phrase for v in violations))

    def test_level_b_with_is_effective_for_is_violation(self) -> None:
        # "is effective for" is a Level A verb; Level B must use "likely effective".
        text = "CBD is effective for generalised anxiety disorder."
        violations = grade_wording_consistency(text, EvidenceLevel.B)
        self.assertGreaterEqual(len(violations), 1)

    def test_level_a_with_established_is_not_violation(self) -> None:
        # At Level A, "established" is correct wording.
        text = "CBD is established to reduce convulsive-seizure frequency in Dravet."
        violations = grade_wording_consistency(text, EvidenceLevel.A)
        self.assertEqual(len(violations), 0)

    def test_level_a_with_may_reduce_is_not_violation(self) -> None:
        # Hedged wording at a stronger declared grade is always allowed.
        text = "Cannabis may reduce nausea in adults with CINV."
        violations = grade_wording_consistency(text, EvidenceLevel.A)
        self.assertEqual(len(violations), 0)

    def test_cure_claim_always_violates(self) -> None:
        text = "Cannabidiol cures epilepsy in paediatric patients."
        for level in (EvidenceLevel.A, EvidenceLevel.B, EvidenceLevel.C):
            violations = grade_wording_consistency(text, level)
            self.assertGreaterEqual(len(violations), 1)

    def test_clean_hedged_text_passes(self) -> None:
        text = (
            "Cannabidiol may reduce convulsive-seizure frequency in some "
            "patients; preliminary evidence at Level C."
        )
        violations = grade_wording_consistency(text, EvidenceLevel.C)
        self.assertEqual(len(violations), 0)

    def test_level_b_with_likely_effective_is_not_violation(self) -> None:
        # "likely effective" is the correct Level B verb.
        text = "Nabiximols is likely effective for reducing MS spasticity scores."
        violations = grade_wording_consistency(text, EvidenceLevel.B)
        self.assertEqual(len(violations), 0)

    def test_level_d_forbids_level_c_verbs(self) -> None:
        # "may reduce" is Level C wording — a Level D claim must not use it.
        violations = grade_wording_consistency(
            "Open-label observation: CBD may reduce anxiety in adults.",
            EvidenceLevel.D,
        )
        self.assertGreaterEqual(len(violations), 1)
        self.assertTrue(any("may" in v.matched_phrase for v in violations))

    def test_level_d_forbids_preliminary_evidence(self) -> None:
        # "preliminary evidence" is Level C phrasing — forbidden at Level D.
        violations = grade_wording_consistency(
            "Preliminary evidence suggests CBG reduces inflammation.",
            EvidenceLevel.D,
        )
        self.assertGreaterEqual(len(violations), 1)

    def test_level_c_forbids_likely_effective(self) -> None:
        # "likely effective" is Level B language — forbidden at Level C.
        violations = grade_wording_consistency(
            "CBD is likely effective for treatment-refractory epilepsy.",
            EvidenceLevel.C,
        )
        self.assertGreaterEqual(len(violations), 1)

    def test_level_c_forbids_is_associated_with(self) -> None:
        # "is associated with" is Level B phrasing — forbidden at Level C.
        violations = grade_wording_consistency(
            "THC is associated with reduced nausea in chemotherapy patients.",
            EvidenceLevel.C,
        )
        self.assertGreaterEqual(len(violations), 1)

    def test_level_d_allows_anecdotal_reports(self) -> None:
        # Level D's own acceptable wording must never be flagged.
        violations = grade_wording_consistency(
            "Anecdotal reports describe CBN as mildly sedating.",
            EvidenceLevel.D,
        )
        self.assertEqual(len(violations), 0)

    def test_level_b_forbids_established(self) -> None:
        # "established" is Level A language — forbidden at Level B.
        violations = grade_wording_consistency(
            "CBD is established to reduce seizure frequency.",
            EvidenceLevel.B,
        )
        self.assertGreaterEqual(len(violations), 1)


class TestDetectDeclaredLevel(unittest.TestCase):
    def test_picks_up_level_a_marker(self) -> None:
        self.assertEqual(
            detect_declared_level("Evidence grade: Level A (Cochrane SR)."),
            EvidenceLevel.A,
        )

    def test_picks_up_grade_low_marker(self) -> None:
        self.assertEqual(
            detect_declared_level("GRADE low for this outcome."),
            EvidenceLevel.C,
        )

    def test_picks_highest_when_multiple_mentioned(self) -> None:
        text = "Some claims at Level C; the strongest at Level A."
        self.assertEqual(detect_declared_level(text), EvidenceLevel.A)

    def test_none_when_no_marker(self) -> None:
        self.assertIsNone(detect_declared_level("Plain prose."))


class TestConfidenceBand(unittest.TestCase):
    def test_level_a_band_is_strong(self) -> None:
        lo, hi = confidence_band_for(EvidenceLevel.A)
        self.assertGreaterEqual(lo, 0.7)
        self.assertGreater(hi, 0.9)

    def test_level_e_band_is_weak(self) -> None:
        lo, hi = confidence_band_for(EvidenceLevel.E)
        self.assertLess(hi, 0.3)

    def test_unsupported_band_near_zero(self) -> None:
        lo, hi = confidence_band_for(EvidenceLevel.UNSUPPORTED)
        self.assertLess(hi, 0.2)

    def test_consistent_inside_band(self) -> None:
        self.assertTrue(confidence_consistent(0.85, EvidenceLevel.A))
        self.assertFalse(confidence_consistent(0.10, EvidenceLevel.A))
        self.assertTrue(confidence_consistent(0.10, EvidenceLevel.E))


class TestCuringFalsePositive(unittest.TestCase):
    """'curing' in cannabis cultivation must not trigger wording violations.

    Cultivation 'curing' (post-harvest drying/curing process) is a
    legitimate cannabis agronomy term. The wording checker bans 'curing'
    only in the medical therapeutic-claim sense ('cannabis is curing
    disease X'), not in the cultivation sense ('after curing, water
    activity should be <0.65').
    """

    def test_cultivation_curing_does_not_violate_level_a(self) -> None:
        text = "After curing, measure water activity to prevent mold."
        violations = grade_wording_consistency(text, EvidenceLevel.A)
        cultivation_violations = [
            v for v in violations if "curing" in v.matched_phrase.lower()
        ]
        self.assertEqual(
            len(cultivation_violations), 0,
            f"'curing' (cultivation) incorrectly flagged: {cultivation_violations}",
        )

    def test_cultivation_curing_does_not_violate_level_c(self) -> None:
        text = (
            "The curing process should last 2–4 weeks. During curing, "
            "open jars daily for the first week to release moisture."
        )
        violations = grade_wording_consistency(text, EvidenceLevel.C)
        cultivation_violations = [
            v for v in violations if "curing" in v.matched_phrase.lower()
        ]
        self.assertEqual(len(cultivation_violations), 0)

    def test_medical_curing_claim_still_violates(self) -> None:
        # 'curing [condition]' is still forbidden.
        text = "Cannabis is curing anxiety in many patients."
        violations = grade_wording_consistency(text, EvidenceLevel.A)
        self.assertGreaterEqual(
            len(violations), 1,
            "Medical 'curing' claim should still be flagged",
        )

    def test_cure_and_cured_still_violate(self) -> None:
        for phrase in ("Cannabis cures cancer.", "Pain was cured by CBD."):
            violations = grade_wording_consistency(phrase, EvidenceLevel.A)
            self.assertGreaterEqual(len(violations), 1, f"'{phrase}' was not flagged")


class TestInlineCodeSkipWording(unittest.TestCase):
    """Wording-vs-grade detector must skip matches inside markdown
    inline code (`` `cure` ``) and fenced code blocks so audit /
    discussion sections that name forbidden verbs do not fail.
    """

    def test_cure_in_inline_code_skipped(self) -> None:
        text = (
            "The audit avoids `cure` and `cures` claims in all prose. "
            "Effect sizes are reported with NRS reduction and 95% CI."
        )
        violations = grade_wording_consistency(text, EvidenceLevel.A)
        self.assertEqual(
            len(violations), 0,
            f"`cure`/`cures` inside inline code must not fire: {violations}",
        )

    def test_established_in_inline_code_skipped_at_level_b(self) -> None:
        text = (
            "Banned at Level B: the verb `established` implies Level A "
            "evidence. Effect size for this Level B claim: -0.6 NRS."
        )
        violations = grade_wording_consistency(text, EvidenceLevel.B)
        self.assertEqual(
            len(violations), 0,
            f"`established` inside inline code must not fire at Level B: {violations}",
        )

    def test_cure_outside_code_still_fires(self) -> None:
        text = (
            "We avoid the `cure` verb in audits.\n"
            "But this sentence claims that CBD cures epilepsy — that's the assertion."
        )
        violations = grade_wording_consistency(text, EvidenceLevel.A)
        self.assertGreaterEqual(
            len(violations), 1,
            "The unquoted prose 'cures epilepsy' must still fire",
        )

    def test_fenced_code_block_skipped(self) -> None:
        text = (
            "Example CLI output:\n\n"
            "```\n"
            "violation: `cure` implies a grade higher than Level A\n"
            "```\n"
            "End of example."
        )
        violations = grade_wording_consistency(text, EvidenceLevel.A)
        self.assertEqual(
            len(violations), 0,
            "Forbidden verbs inside fenced code blocks must not fire",
        )


if __name__ == "__main__":
    unittest.main()
