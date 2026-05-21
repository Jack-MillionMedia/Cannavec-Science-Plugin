"""Regression tests for safety false-positive and new-flag behaviour.

These tests guard against:
1. Population-level dose questions being incorrectly refused as
   individualised medical questions (_DOSE_ASKING false-positive fix).
2. New SYNTHETIC_CANNABINOID and DELTA8_LEGAL_GRAY flag correctness.
3. Verify that genuinely individualised dose questions are still refused.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.safety import (
    SafetyAction,
    SafetyFlag,
    check_safety,
    is_individualized_medical_question,
)


class TestDoseAskingFalsePositiveFix(unittest.TestCase):
    """Population-level 'how much' / 'what dose' questions must not be refused."""

    def test_research_dose_question_proceeds(self) -> None:
        """'What dose was used in the Dravet trial?' is a research question, not personal care."""
        v = check_safety("What dose range was used in the Devinsky Dravet trial?")
        self.assertNotEqual(
            v.recommended_action,
            SafetyAction.REFUSE_INDIVIDUALIZED,
            "Research dose question was incorrectly refused as individualised",
        )
        self.assertTrue(v.proceed)

    def test_how_much_evidence_proceeds(self) -> None:
        """'How much evidence exists for CBD?' must not trigger dose-asking refusal."""
        v = check_safety("How much evidence exists for CBD in anxiety management?")
        self.assertNotEqual(
            v.recommended_action,
            SafetyAction.REFUSE_INDIVIDUALIZED,
        )
        self.assertTrue(v.proceed)

    def test_how_much_hempcrete_proceeds(self) -> None:
        """Non-medical 'how much' questions must proceed."""
        v = check_safety("How much does hempcrete weigh per cubic metre?")
        self.assertNotEqual(
            v.recommended_action,
            SafetyAction.REFUSE_INDIVIDUALIZED,
        )
        self.assertTrue(v.proceed)

    def test_clinical_trial_dose_range_question_proceeds(self) -> None:
        """Asking about trial-supported dose ranges is population education."""
        v = check_safety(
            "What dose range of nabiximols was used in MS spasticity trials?"
        )
        self.assertNotEqual(
            v.recommended_action,
            SafetyAction.REFUSE_INDIVIDUALIZED,
        )
        self.assertTrue(v.proceed)

    def test_what_dose_in_trial_proceeds(self) -> None:
        v = check_safety("What dose did the Epidiolex label specify for Lennox-Gastaut?")
        self.assertNotEqual(
            v.recommended_action,
            SafetyAction.REFUSE_INDIVIDUALIZED,
        )
        self.assertTrue(v.proceed)


class TestGenuinelyIndividualisedDoseStillRefused(unittest.TestCase):
    """Confirm that genuinely personal dose questions remain refused."""

    def test_personal_dose_refused(self) -> None:
        v = check_safety("I have arthritis — what dose of THC should I take?")
        self.assertEqual(v.recommended_action, SafetyAction.REFUSE_INDIVIDUALIZED)

    def test_how_much_should_i_take_refused(self) -> None:
        v = check_safety("I'm new to edibles. How much edible THC should I take?")
        self.assertEqual(v.recommended_action, SafetyAction.REFUSE_INDIVIDUALIZED)

    def test_my_dose_refused(self) -> None:
        v = check_safety("What dosage should I use for my anxiety?")
        self.assertEqual(v.recommended_action, SafetyAction.REFUSE_INDIVIDUALIZED)

    def test_pregnant_dose_refused(self) -> None:
        v = check_safety("I'm pregnant — how much THC can I safely take?")
        self.assertIn(
            v.recommended_action,
            (SafetyAction.REFUSE_INDIVIDUALIZED, SafetyAction.REFUSE_HARMFUL),
        )


class TestSyntheticCannabinoidFlag(unittest.TestCase):
    def test_k2_fires_caution(self) -> None:
        v = check_safety("What is K2 and is it related to cannabis?")
        self.assertTrue(
            any(f.flag == SafetyFlag.SYNTHETIC_CANNABINOID for f in v.flags),
            "SYNTHETIC_CANNABINOID flag did not fire for K2 mention",
        )

    def test_spice_fires_caution(self) -> None:
        v = check_safety("My patient was admitted after using spice — what are the risks?")
        self.assertTrue(
            any(f.flag == SafetyFlag.SYNTHETIC_CANNABINOID for f in v.flags),
        )

    def test_jwh_fires_caution(self) -> None:
        v = check_safety("What is JWH-018 and how does it differ from THC?")
        self.assertTrue(
            any(f.flag == SafetyFlag.SYNTHETIC_CANNABINOID for f in v.flags),
        )

    def test_synthetic_cannabinoid_does_not_refuse(self) -> None:
        """Synthetic cannabinoid mention should ADD_CAUTION, not REFUSE."""
        v = check_safety("What are the risks of synthetic cannabinoids like K2?")
        self.assertNotEqual(v.recommended_action, SafetyAction.REFUSE_HARMFUL)
        self.assertNotEqual(v.recommended_action, SafetyAction.REFUSE_INDIVIDUALIZED)

    def test_regular_cannabis_does_not_fire_synthetic_flag(self) -> None:
        v = check_safety("What is the evidence for CBD in chronic pain?")
        self.assertFalse(
            any(f.flag == SafetyFlag.SYNTHETIC_CANNABINOID for f in v.flags),
        )


class TestDelta8GrayAreaFlag(unittest.TestCase):
    def test_delta8_fires_caution(self) -> None:
        v = check_safety("Is delta-8 THC legal under the Farm Bill?")
        self.assertTrue(
            any(f.flag == SafetyFlag.DELTA8_LEGAL_GRAY for f in v.flags),
            "DELTA8_LEGAL_GRAY flag did not fire for delta-8 mention",
        )

    def test_delta10_fires_caution(self) -> None:
        v = check_safety("What is delta-10 THC and where can I find it?")
        self.assertTrue(
            any(f.flag == SafetyFlag.DELTA8_LEGAL_GRAY for f in v.flags),
        )

    def test_hhc_fires_caution(self) -> None:
        v = check_safety("How does HHC compare to delta-9 THC pharmacologically?")
        self.assertTrue(
            any(f.flag == SafetyFlag.DELTA8_LEGAL_GRAY for f in v.flags),
        )

    def test_delta8_caution_does_not_refuse(self) -> None:
        """Delta-8 questions should ADD_CAUTION, not refuse."""
        v = check_safety("What are the effects of delta-8 THC?")
        self.assertNotEqual(v.recommended_action, SafetyAction.REFUSE_HARMFUL)

    def test_regular_thc_does_not_fire_delta8_flag(self) -> None:
        v = check_safety("What is the pharmacology of THC at the CB1 receptor?")
        self.assertFalse(
            any(f.flag == SafetyFlag.DELTA8_LEGAL_GRAY for f in v.flags),
            "Delta-8 flag fired on regular THC question — too broad",
        )

    def test_thco_fires_caution(self) -> None:
        v = check_safety("Is THCO legal and what are its effects?")
        self.assertTrue(
            any(f.flag == SafetyFlag.DELTA8_LEGAL_GRAY for f in v.flags),
        )


if __name__ == "__main__":
    unittest.main()
