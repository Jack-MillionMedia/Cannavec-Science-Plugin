"""Tests for the 9-section IRB protocol skeleton (spec 002 US2)."""

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.pico import build_pico
from cannavec_science.protocol_skeleton import (
    ProtocolSkeleton,
    WATERMARK,
    build_skeleton,
    render_markdown,
)


class ProtocolSkeletonBuildTests(unittest.TestCase):
    def test_returns_typed_skeleton(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        sk = build_skeleton(a)
        self.assertIsInstance(sk, ProtocolSkeleton)

    def test_word_count_under_cap(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        sk = build_skeleton(a)
        self.assertLess(sk.word_count, 1500)

    def test_all_nine_sections_populated(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        sk = build_skeleton(a)
        for attr in (
            "background", "hypothesis", "specific_aims",
            "study_design", "population", "intervention",
            "endpoints", "statistical_analysis", "safety_monitoring",
        ):
            v = getattr(sk, attr)
            self.assertTrue(v, f"{attr} should be non-empty")

    def test_zero_claims_still_produces_skeleton(self):
        a = compose_answer("What is the weather today?")
        a.claims = []
        sk = build_skeleton(a)
        self.assertIsInstance(sk, ProtocolSkeleton)

    def test_pico_integration(self):
        a = compose_answer("CBD Dravet syndrome paediatric epilepsy")
        pico = build_pico(a)
        sk = build_skeleton(a, pico=pico)
        # PICO population should appear in the population section.
        if pico.population != "unresolved":
            self.assertIn(pico.population, sk.population)


class RenderTests(unittest.TestCase):
    def test_watermark_on_line_one(self):
        a = compose_answer("CBD Dravet syndrome")
        sk = build_skeleton(a)
        md = render_markdown(sk)
        lines = [ln for ln in md.split("\n") if ln.strip()]
        self.assertEqual(
            lines[0], WATERMARK,
            msg="Watermark MUST be the first non-empty line",
        )

    def test_exactly_nine_section_headers(self):
        a = compose_answer("CBD Dravet syndrome")
        sk = build_skeleton(a)
        md = render_markdown(sk)
        # Count "## " headers (not "###" or "#").
        n_h2 = sum(1 for ln in md.split("\n") if ln.startswith("## "))
        self.assertEqual(
            n_h2, 9,
            msg=f"Expected 9 sections, got {n_h2}",
        )

    def test_section_headers_in_order(self):
        a = compose_answer("CBD Dravet syndrome")
        sk = build_skeleton(a)
        md = render_markdown(sk)
        expected = [
            "Background", "Hypothesis", "Specific Aims",
            "Study Design", "Population", "Intervention",
            "Endpoints", "Statistical Analysis", "Safety Monitoring",
        ]
        positions = [md.find(f"## {h}") for h in expected]
        for i in range(1, len(positions)):
            self.assertGreater(
                positions[i], positions[i - 1],
                msg=f"Section {expected[i]} must come after {expected[i-1]}",
            )

    def test_render_word_count_close_to_compute(self):
        a = compose_answer("CBD Dravet syndrome")
        sk = build_skeleton(a)
        md = render_markdown(sk)
        # The rendered output is the skeleton + section headers + watermark;
        # the structural overhead is small relative to the section bodies.
        n_words = len(md.split())
        self.assertLess(n_words, 1500 + 200)  # render adds ~headers/watermark


class IntentBranchTests(unittest.TestCase):
    def test_interaction_intent_design(self):
        a = compose_answer("How does CBD interact with warfarin via CYP2C9?")
        sk = build_skeleton(a)
        self.assertIn("crossover", sk.study_design.lower())

    def test_efficacy_intent_design(self):
        a = compose_answer("Is CBD effective for Dravet syndrome?")
        sk = build_skeleton(a)
        self.assertIn("placebo-controlled", sk.study_design.lower())

    def test_mechanism_intent_design(self):
        a = compose_answer("What is the mechanism of CBD on the GABAA receptor?")
        sk = build_skeleton(a)
        self.assertIn("mechanism", sk.study_design.lower())


if __name__ == "__main__":
    unittest.main()
