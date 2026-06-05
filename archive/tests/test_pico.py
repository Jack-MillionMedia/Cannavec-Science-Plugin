"""Tests for the PICO drafter (spec 002 US2)."""

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.pico import PICOBlock, build_pico, render_markdown


class PICOBuildTests(unittest.TestCase):
    def test_returns_pico_block(self):
        a = compose_answer("What is the evidence for cannabidiol in Dravet syndrome?")
        block = build_pico(a)
        self.assertIsInstance(block, PICOBlock)

    def test_intervention_picks_cbd(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        block = build_pico(a)
        self.assertEqual(block.intervention, "CBD")

    def test_intervention_picks_explicit_isomer(self):
        a = compose_answer("What is the evidence for Δ⁹-THC in nausea?")
        block = build_pico(a)
        self.assertIn("Δ⁹-THC", block.intervention)

    def test_intervention_picks_minor_cannabinoid(self):
        a = compose_answer("THCV in type 2 diabetes glycaemic control")
        block = build_pico(a)
        self.assertEqual(block.intervention, "THCV")

    def test_unresolved_intervention_for_unrelated_prompt(self):
        a = compose_answer("What is the weather today?")
        block = build_pico(a)
        # The composer should still produce a block even when nothing
        # cannabinoid-shaped is present.
        self.assertIsInstance(block, PICOBlock)
        self.assertEqual(block.intervention, "unresolved")

    def test_population_pulled_from_registry_hit(self):
        a = compose_answer("cannabidiol Dravet syndrome paediatric epilepsy")
        block = build_pico(a)
        self.assertNotEqual(block.population, "unresolved")

    def test_high_confidence_when_both_resolved(self):
        a = compose_answer("CBD in Dravet syndrome paediatric epilepsy")
        block = build_pico(a)
        self.assertEqual(block.confidence, "high")

    def test_low_confidence_when_both_unresolved(self):
        a = compose_answer("What is the weather today?")
        block = build_pico(a)
        self.assertEqual(block.confidence, "low")

    def test_comparator_default_for_efficacy(self):
        a = compose_answer("What is the efficacy of CBD for Dravet syndrome?")
        block = build_pico(a)
        self.assertIn("placebo", block.comparator)

    def test_comparator_default_for_interaction(self):
        a = compose_answer("How does CBD interact with warfarin via CYP2C9?")
        block = build_pico(a)
        self.assertIn("baseline", block.comparator.lower())

    def test_outcomes_non_empty(self):
        a = compose_answer("CBD Dravet syndrome")
        block = build_pico(a)
        self.assertGreater(len(block.outcomes), 0)

    def test_unresolved_isomer_emits_pi_note(self):
        a = compose_answer("THC in nausea")
        block = build_pico(a)
        # Bare "THC" without an isomer prefix produces the clarification note.
        self.assertTrue(
            any("isomer" in n.lower() for n in block.notes),
            f"expected isomer-clarification note; got {block.notes}",
        )


class PICORenderTests(unittest.TestCase):
    def test_markdown_includes_all_pico_fields(self):
        a = compose_answer("CBD Dravet syndrome")
        block = build_pico(a)
        md = render_markdown(block)
        for needle in ("Population", "Intervention", "Comparator", "Outcomes"):
            self.assertIn(needle, md)

    def test_markdown_includes_confidence_label(self):
        a = compose_answer("CBD Dravet syndrome")
        block = build_pico(a)
        md = render_markdown(block)
        self.assertIn("Confidence", md)


class PICOToDictTests(unittest.TestCase):
    def test_to_dict_round_trip(self):
        a = compose_answer("CBD Dravet syndrome")
        block = build_pico(a)
        d = block.to_dict()
        self.assertEqual(d["population"], block.population)
        self.assertEqual(d["intervention"], block.intervention)
        self.assertEqual(d["comparator"], block.comparator)
        self.assertEqual(list(d["outcomes"]), list(block.outcomes))


if __name__ == "__main__":
    unittest.main()
