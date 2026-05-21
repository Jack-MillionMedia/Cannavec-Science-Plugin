"""Tests for cannavec.intent."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.intent import Intent, classify_intent   # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
