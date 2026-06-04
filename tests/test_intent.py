"""Tests for cannavec.intent."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.intent import (  # noqa: E402
    Intent,
    classify_intent,
    indication_terms,
)


class TestIntentClassification(unittest.TestCase):
    def test_definition(self) -> None:
        self.assertEqual(classify_intent("What is CBG?"), Intent.DEFINITION)

    def test_dosing(self) -> None:
        self.assertEqual(
            classify_intent("What is the starting dose for CBD oil?"),
            Intent.DOSING,
        )

    def test_interaction(self) -> None:
        self.assertEqual(
            classify_intent("Does CBD interact with warfarin?"),
            Intent.INTERACTION,
        )

    def test_mechanism(self) -> None:
        self.assertEqual(
            classify_intent("What is the mechanism of CBD anticonvulsant action?"),
            Intent.MECHANISM,
        )

    def test_legal_status(self) -> None:
        self.assertEqual(
            classify_intent("Is THCA legal in New York?"),
            Intent.LEGAL_STATUS,
        )

    def test_comparison(self) -> None:
        self.assertEqual(
            classify_intent("CBD vs THC for anxiety — which is better?"),
            Intent.COMPARISON,
        )

    def test_safety(self) -> None:
        self.assertEqual(
            classify_intent("What are the side effects of inhaled THC?"),
            Intent.SAFETY_RISK,
        )

    def test_open_question_fallback(self) -> None:
        self.assertEqual(
            classify_intent("Cannabis."),
            Intent.OPEN_QUESTION,
        )

    def test_what_does_x_do_is_definition(self) -> None:
        # "what does" is the most common form of a definition question
        # after "what is" — must not fall through to OPEN_QUESTION.
        self.assertEqual(
            classify_intent("What does CBG do?"),
            Intent.DEFINITION,
        )

    def test_what_does_the_ecs_do_is_definition(self) -> None:
        self.assertEqual(
            classify_intent("What does the endocannabinoid system do?"),
            Intent.DEFINITION,
        )

    def test_what_do_terpenes_do_is_definition(self) -> None:
        self.assertEqual(
            classify_intent("What do terpenes do in cannabis?"),
            Intent.DEFINITION,
        )

    def test_mechanism_still_wins_over_definition(self) -> None:
        # "how does" + receptor/pathway language → MECHANISM takes priority
        # because MECHANISM comes before DEFINITION in _PATTERNS.
        result = classify_intent("How does CBD work at the receptor level?")
        self.assertEqual(result, Intent.MECHANISM)

    def test_dosing_still_wins_over_definition(self) -> None:
        # "what dose" → DOSING, not DEFINITION.
        result = classify_intent("What dose of CBD is used in trials?")
        self.assertEqual(result, Intent.DOSING)

    def test_evidence_for_in_is_efficacy(self) -> None:
        # The canonical research phrasing "<X> evidence in/for <condition>".
        self.assertEqual(
            classify_intent("CBD evidence in Dravet syndrome"),
            Intent.EFFICACY,
        )
        self.assertEqual(
            classify_intent("What is the evidence for THCV in appetite?"),
            Intent.EFFICACY,
        )

    def test_evidence_phrasing_does_not_steal_literature_review(self) -> None:
        # "state of the evidence" / "review the evidence" stay LITERATURE_REVIEW
        # — the efficacy trigger is anchored to "evidence for/in/base".
        self.assertEqual(
            classify_intent("Review the literature on CBD and epilepsy"),
            Intent.LITERATURE_REVIEW,
        )

    def test_plural_receptors_is_mechanism(self) -> None:
        # "receptors" (plural) must match the mechanism pattern too.
        self.assertEqual(
            classify_intent("How does CBD act on its receptors?"),
            Intent.MECHANISM,
        )


class TestIndicationTermsLaySynonyms(unittest.TestCase):
    """WS2 — indication_terms must tag lay/patient phrasings of MS spasticity
    and neuropathic pain so the lexicon stays in lockstep with the populations
    detector (a recalled row's condition tag must overlap the prompt's, or the
    wrong-indication gate would wrongly drop it). MS-gated so a generic muscle
    complaint with no MS context does not tag."""

    def test_limb_rigidity_in_ms_tags_spasticity(self) -> None:
        self.assertIn("spasticity", indication_terms("limb rigidity in MS"))

    def test_ms_muscle_spasms_tags_spasticity(self) -> None:
        self.assertIn("spasticity", indication_terms("MS muscle spasms"))

    def test_shooting_nerve_pain_tags_neuropathic(self) -> None:
        self.assertIn(
            "neuropathic_pain",
            indication_terms("weed for shooting nerve pain"),
        )

    def test_bare_muscle_stiffness_not_spasticity(self) -> None:
        self.assertNotIn(
            "spasticity", indication_terms("back muscle stiffness")
        )

    def test_leg_cramps_not_spasticity(self) -> None:
        self.assertNotIn("spasticity", indication_terms("leg cramps"))

    # ── Precision: "ms"/"Ms"/"GC-MS" must not tag spasticity (adversarial) ──

    def test_milliseconds_unit_not_spasticity(self) -> None:
        self.assertNotIn(
            "spasticity", indication_terms("muscle spasm 200 ms after dosing")
        )

    def test_gc_ms_technique_not_spasticity(self) -> None:
        self.assertNotIn(
            "spasticity",
            indication_terms("GC-MS assay of muscle spasm metabolites"),
        )

    def test_honorific_ms_not_spasticity(self) -> None:
        self.assertNotIn(
            "spasticity", indication_terms("Ms. Smith has muscle spasms")
        )


if __name__ == "__main__":
    unittest.main()
