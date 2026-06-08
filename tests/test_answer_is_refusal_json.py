"""``to_dict`` must expose ``is_refusal`` — the contract a /cv output skill reads.

A safety/individualized refusal still serializes its citations (reference
context), so a JSON consumer that only checked for an empty ``citations`` list
would mistake a refusal for an answerable brief and weave those references as
evidence. ``is_refusal`` makes the refusal state a first-class, machine-readable
field so an output skill (/cv:cite, /cv:pdf, …) can detect it without re-deriving
it from ``refusal_reason`` text or the safety verdict.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import compose_answer


class TestIsRefusalInJson(unittest.TestCase):
    def test_curated_answer_is_not_refusal(self) -> None:
        d = compose_answer("CBD evidence in Dravet syndrome").to_dict()
        self.assertIn("is_refusal", d)
        self.assertFalse(d["is_refusal"])

    def test_refusal_answer_flags_is_refusal_true(self) -> None:
        a = compose_answer("How much CBD should I take for my anxiety every day?")
        self.assertTrue(a.is_refusal, "expected an individualized-dosing refusal")
        d = a.to_dict()
        self.assertIn("is_refusal", d)
        self.assertTrue(
            d["is_refusal"],
            "to_dict must report is_refusal=True so a skill cannot mistake a "
            "refusal (which still carries reference citations) for a brief",
        )

    def test_is_refusal_matches_the_property(self) -> None:
        for q in (
            "CBD evidence in Dravet syndrome",
            "How much CBD should I take for my anxiety every day?",
            "What is the evidence for cannabis in chronic pain?",
        ):
            a = compose_answer(q)
            self.assertEqual(a.to_dict()["is_refusal"], a.is_refusal, q)


if __name__ == "__main__":
    unittest.main()
