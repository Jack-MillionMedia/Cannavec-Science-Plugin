"""Tests for the GRADE evidence-profile table (spec 002 US2)."""

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.grade_profile import (
    GradeProfile,
    GradeProfileRow,
    build_profile,
    render_csv,
    render_markdown,
)


class GradeProfileBuildTests(unittest.TestCase):
    def test_returns_typed_profile(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        p = build_profile(a)
        self.assertIsInstance(p, GradeProfile)
        self.assertGreater(len(p.rows), 0)

    def test_zero_claims_returns_no_admissible_row(self):
        a = compose_answer("What is the weather today?")
        # Force zero claims by clearing.
        a.claims = []
        p = build_profile(a)
        self.assertEqual(len(p.rows), 1)
        self.assertEqual(p.rows[0].outcome, "No admissible evidence")
        self.assertEqual(p.rows[0].certainty, "Unsupported")

    def test_per_claim_row_alignment(self):
        a = compose_answer("CBD Dravet syndrome")
        p = build_profile(a)
        # One row per claim (when claims exist).
        if a.claims:
            self.assertEqual(len(p.rows), len(a.claims))

    def test_each_row_has_certainty(self):
        a = compose_answer("CBD Dravet syndrome")
        p = build_profile(a)
        valid_grades = {
            "Level A", "Level B", "Level C", "Level D", "Level E",
            "Unsupported",
        }
        for r in p.rows:
            self.assertIn(r.certainty, valid_grades)


class RenderTests(unittest.TestCase):
    def test_markdown_header_columns(self):
        a = compose_answer("CBD Dravet syndrome")
        p = build_profile(a)
        md = render_markdown(p)
        for col in (
            "Outcome", "#studies", "Risk of bias", "Inconsistency",
            "Indirectness", "Imprecision", "Publication bias",
            "Effect", "Certainty",
        ):
            self.assertIn(col, md)

    def test_csv_header_row(self):
        a = compose_answer("CBD Dravet syndrome")
        p = build_profile(a)
        csv_text = render_csv(p)
        first_line = csv_text.splitlines()[0]
        self.assertIn("outcome", first_line)
        self.assertIn("certainty", first_line)
        self.assertIn("n_studies", first_line)


class EdgeCaseTests(unittest.TestCase):
    def test_to_dict_round_trip(self):
        a = compose_answer("CBD Dravet syndrome")
        p = build_profile(a)
        d = p.to_dict()
        self.assertEqual(len(d["rows"]), len(p.rows))

    def test_pipe_character_escaped_in_markdown(self):
        # Force a row with a pipe in the outcome to ensure escape.
        row = GradeProfileRow(
            outcome="A | B",
            n_studies=1,
            study_designs=("RCT",),
        )
        p = GradeProfile(rows=(row,))
        md = render_markdown(p)
        # Pipe is escaped so the markdown table doesn't break.
        self.assertIn(r"A \| B", md)


if __name__ == "__main__":
    unittest.main()
