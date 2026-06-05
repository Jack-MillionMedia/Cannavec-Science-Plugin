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


class MetaInconsistencyBridgeTests(unittest.TestCase):
    """Spec 011: a quantitative heterogeneity finding drives the
    inconsistency column and downgrades the certainty grade."""

    def _level_a_answer(self):
        from types import SimpleNamespace
        from cannavec_science.evidence import (
            Claim, ClaimType, Source, SourceTier,
        )
        # §VII: a Level-A body of evidence is ≥ 2 aligned pre-registered,
        # adequately-powered RCTs (or a canonical Cochrane/AHRQ/NICE SR).
        # Express the two RCTs as exactly that — a single non-canonical
        # flagship source no longer shortcuts to Level A (D5 fix).
        s1 = Source(title="RCT1", tier=SourceTier.JOURNAL_RCT, pmid="1",
                    year=2017, pre_registered=True, adequately_powered=True)
        s2 = Source(title="RCT2", tier=SourceTier.JOURNAL_RCT, pmid="2",
                    year=2018, pre_registered=True, adequately_powered=True)
        claim = Claim(
            text="Seizure frequency reduction",
            claim_type=ClaimType.EDUCATIONAL,   # no required-disclosure penalty
            sources=(s1, s2),
        )
        return SimpleNamespace(claims=[claim], prompt="p", generated_at="")

    def test_default_inconsistency_is_not_serious(self):
        p = build_profile(self._level_a_answer())
        self.assertEqual(p.rows[0].inconsistency, "not serious")
        self.assertEqual(p.rows[0].certainty, "Level A")

    def test_serious_meta_downgrades_certainty_one_level(self):
        from cannavec_science import meta_analysis as ma
        # I² = 68.75% → "serious" → one GRADE downgrade.
        res = ma.meta_analyze([
            ma.EffectSize(study_id="S1", yi=0.1, vi=0.01, pmid="1"),
            ma.EffectSize(study_id="S2", yi=0.5, vi=0.04, pmid="2"),
        ])
        self.assertEqual(res.inconsistency, "serious")
        p = build_profile(
            self._level_a_answer(),
            meta_by_outcome={"Seizure frequency reduction": res},
        )
        self.assertEqual(p.rows[0].inconsistency, "serious")
        self.assertEqual(p.rows[0].certainty, "Level B")

    def test_very_serious_meta_downgrades_two_levels(self):
        from cannavec_science import meta_analysis as ma
        # I² = 98% → "very serious" → two GRADE downgrades.
        res = ma.meta_analyze([
            ma.EffectSize(study_id="S1", yi=0.0, vi=0.01, pmid="1"),
            ma.EffectSize(study_id="S2", yi=1.0, vi=0.01, pmid="2"),
        ])
        self.assertEqual(res.inconsistency, "very serious")
        p = build_profile(
            self._level_a_answer(),
            meta_by_outcome={"Seizure frequency reduction": res},
        )
        self.assertEqual(p.rows[0].inconsistency, "very serious")
        self.assertEqual(p.rows[0].certainty, "Level C")


class PublicationBiasBridgeTests(unittest.TestCase):
    """Spec 012: an Egger result drives the publication-bias column and
    stacks with the inconsistency downgrade."""

    def _level_a_answer(self):
        from types import SimpleNamespace
        from cannavec_science.evidence import (
            Claim, ClaimType, Source, SourceTier,
        )
        # §VII: a Level-A body of evidence is ≥ 2 aligned pre-registered,
        # adequately-powered RCTs (or a canonical Cochrane/AHRQ/NICE SR).
        # Express the two RCTs as exactly that — a single non-canonical
        # flagship source no longer shortcuts to Level A (D5 fix).
        s1 = Source(title="RCT1", tier=SourceTier.JOURNAL_RCT, pmid="1",
                    year=2017, pre_registered=True, adequately_powered=True)
        s2 = Source(title="RCT2", tier=SourceTier.JOURNAL_RCT, pmid="2",
                    year=2018, pre_registered=True, adequately_powered=True)
        claim = Claim(
            text="Seizure frequency reduction",
            claim_type=ClaimType.EDUCATIONAL,
            sources=(s1, s2),
        )
        return SimpleNamespace(claims=[claim], prompt="p", generated_at="")

    def _serious_egger(self):
        from cannavec_science.meta_analysis import EggerResult
        return EggerResult(
            k=12, intercept=1.5, intercept_se=0.4, t=3.75, df=10,
            p_value=0.004, slope=0.1, bias_label="strongly suspected",
            bias_serious=True, rationale="Egger p = 0.004 (k = 12).",
        )

    def test_serious_pubbias_sets_column_and_downgrades(self):
        p = build_profile(
            self._level_a_answer(),
            pubbias_by_outcome={"Seizure frequency reduction": self._serious_egger()},
        )
        self.assertEqual(p.rows[0].publication_bias, "strongly suspected")
        self.assertEqual(p.rows[0].certainty, "Level B")

    def test_inconsistency_and_pubbias_stack(self):
        from cannavec_science import meta_analysis as ma
        meta = ma.meta_analyze([
            ma.EffectSize(study_id="S1", yi=0.1, vi=0.01, pmid="1"),
            ma.EffectSize(study_id="S2", yi=0.5, vi=0.04, pmid="2"),
        ])  # I²=68.75% → serious → one downgrade
        p = build_profile(
            self._level_a_answer(),
            meta_by_outcome={"Seizure frequency reduction": meta},
            pubbias_by_outcome={"Seizure frequency reduction": self._serious_egger()},
        )
        # Level A − 1 (inconsistency) − 1 (publication bias) = Level C.
        self.assertEqual(p.rows[0].inconsistency, "serious")
        self.assertEqual(p.rows[0].publication_bias, "strongly suspected")
        self.assertEqual(p.rows[0].certainty, "Level C")


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
