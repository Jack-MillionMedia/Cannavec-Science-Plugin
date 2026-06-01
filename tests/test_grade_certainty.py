"""Tests for the GRADE certainty rating of a meta pool (spec 016).

The pooled-evidence scenarios are numerically pinned (verified against
meta_analyze): (a) strong/consistent RR, CI excludes null → High; (b) near-null
RR, CI crosses null → +1 imprecision → Moderate; (c) high-I² generic body,
CI excludes null → +2 inconsistency → Low.
"""

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import grade_profile as gp
from cannavec_science import meta_analysis as ma
from cannavec_science.evidence import EvidenceLevel


def _strong_consistent():
    return ma.meta_analyze([
        ma.binary_effect("Devinsky 2017", events_t=20, n_t=100,
                         events_c=40, n_c=100, measure="RR", pmid="28538134"),
        ma.binary_effect("Thiele 2018", events_t=25, n_t=110,
                         events_c=45, n_c=110, measure="RR", pmid="29642420"),
        ma.binary_effect("Miller 2020", events_t=18, n_t=90,
                         events_c=38, n_c=95, measure="RR", pmid="32444460"),
    ], measure="RR")


def _near_null():
    return ma.meta_analyze([
        ma.binary_effect("A", events_t=22, n_t=100, events_c=25, n_c=100,
                         measure="RR", pmid="1"),
        ma.binary_effect("B", events_t=24, n_t=110, events_c=26, n_c=110,
                         measure="RR", pmid="2"),
        ma.binary_effect("C", events_t=20, n_t=90, events_c=19, n_c=95,
                         measure="RR", pmid="3"),
    ], measure="RR")


def _high_i2_same_sign():
    return ma.meta_analyze([
        ma.EffectSize(study_id="S1", yi=0.5, vi=0.02, pmid="1"),
        ma.EffectSize(study_id="S2", yi=1.5, vi=0.02, pmid="2"),
        ma.EffectSize(study_id="S3", yi=2.5, vi=0.02, pmid="3"),
    ], measure="generic")


class HighCertaintyTests(unittest.TestCase):
    def test_strong_consistent_rct_is_high(self):
        mc = gp.certainty_from_meta(_strong_consistent())
        self.assertEqual(mc.level, EvidenceLevel.A.value)
        self.assertEqual(mc.grade_word, "High")
        self.assertEqual(mc.glyph, "⊕⊕⊕⊕")
        self.assertEqual(mc.total_steps, 0)

    def test_observational_base_starts_low(self):
        mc = gp.certainty_from_meta(_strong_consistent(),
                                    evidence_base="observational")
        self.assertEqual(mc.base_grade, EvidenceLevel.C.value)
        self.assertEqual(mc.level, EvidenceLevel.C.value)
        self.assertEqual(mc.grade_word, "Low")


class ImprecisionTests(unittest.TestCase):
    def test_ci_crossing_null_adds_one_imprecision_step(self):
        mc = gp.certainty_from_meta(_near_null())
        imp = {d.name: d for d in mc.domains}["Imprecision"]
        self.assertEqual(imp.steps, 1)
        self.assertIn("crosses the null", imp.assessment)
        self.assertIn("computed", imp.basis)
        # A → B (Moderate)
        self.assertEqual(mc.level, EvidenceLevel.B.value)
        self.assertEqual(mc.grade_word, "Moderate")
        self.assertEqual(mc.glyph, "⊕⊕⊕⊝")

    def test_strong_pool_is_not_imprecise(self):
        mc = gp.certainty_from_meta(_strong_consistent())
        imp = {d.name: d for d in mc.domains}["Imprecision"]
        self.assertEqual(imp.steps, 0)
        self.assertEqual(imp.assessment, "not serious")


def _small_smd():
    """SMD ≈ 0.58 from 84 participants: CI excludes 0 but below OIS 96."""
    return ma.meta_analyze([
        ma.continuous_effect("S1", mean_t=0.60, sd_t=1.0, n_t=14,
                             mean_c=0.0, sd_c=1.0, n_c=14, measure="SMD", pmid="1"),
        ma.continuous_effect("S2", mean_t=0.62, sd_t=1.0, n_t=15,
                             mean_c=0.0, sd_c=1.0, n_c=15, measure="SMD", pmid="2"),
        ma.continuous_effect("S3", mean_t=0.58, sd_t=1.0, n_t=13,
                             mean_c=0.0, sd_c=1.0, n_c=13, measure="SMD", pmid="3"),
    ], measure="SMD")


class OisImprecisionTests(unittest.TestCase):
    """The second GRADE imprecision criterion — Optimal Information Size (spec 018)."""

    def test_below_ois_downgrades_even_when_ci_excludes_null(self):
        # The case the CI-only check missed: tight CI, but underpowered pool.
        res = _small_smd()
        lo, hi = res.random_ci_display
        self.assertFalse(lo <= 0.0 <= hi)               # CI excludes the null
        mc = gp.certainty_from_meta(res)                # SMD needs no baseline
        imp = {d.name: d for d in mc.domains}["Imprecision"]
        self.assertEqual(imp.steps, 1)
        self.assertIn("optimal information size", imp.assessment)
        self.assertIn("below", imp.basis)
        # An RCT body of SMD evidence drops High → Moderate purely on the OIS.
        self.assertEqual(mc.level, EvidenceLevel.B.value)
        self.assertEqual(mc.grade_word, "Moderate")

    def test_meeting_ois_keeps_high_with_baseline(self):
        # Strong RR pool (N=605, OIS≈202): a passed baseline must NOT regress it.
        mc = gp.certainty_from_meta(_strong_consistent(), baseline_risk=0.40)
        imp = {d.name: d for d in mc.domains}["Imprecision"]
        self.assertEqual(imp.steps, 0)
        self.assertEqual(imp.assessment, "not serious")
        self.assertIn("meets", imp.basis)
        self.assertEqual(mc.grade_word, "High")

    def test_crosses_null_and_below_ois_is_very_serious(self):
        # Near-null RR pool + baseline: CI crosses 1 AND N ≪ OIS → −2.
        mc = gp.certainty_from_meta(_near_null(), baseline_risk=0.40)
        imp = {d.name: d for d in mc.domains}["Imprecision"]
        self.assertEqual(imp.steps, 2)
        self.assertIn("very serious", imp.assessment)
        # A → C (Low): two imprecision steps.
        self.assertEqual(mc.level, EvidenceLevel.C.value)
        self.assertEqual(mc.grade_word, "Low")

    def test_binary_without_baseline_reports_ois_not_assessed(self):
        mc = gp.certainty_from_meta(_strong_consistent())
        imp = {d.name: d for d in mc.domains}["Imprecision"]
        self.assertEqual(imp.steps, 0)
        self.assertIn("OIS not assessed", imp.basis)


class InconsistencyTests(unittest.TestCase):
    def test_high_i2_downgrades_two_levels(self):
        res = _high_i2_same_sign()
        self.assertEqual(res.downgrade_steps, 2)            # guard the fixture
        mc = gp.certainty_from_meta(res)
        inc = {d.name: d for d in mc.domains}["Inconsistency"]
        self.assertEqual(inc.steps, 2)
        self.assertIn("I²=", inc.basis)
        # A → C (Low); CI excludes the null so imprecision is not serious.
        self.assertEqual(mc.level, EvidenceLevel.C.value)
        self.assertEqual(mc.grade_word, "Low")


class ReviewerInputTests(unittest.TestCase):
    def test_rob_and_indirectness_are_reviewer_inputs(self):
        mc = gp.certainty_from_meta(
            _strong_consistent(),
            risk_of_bias="serious", indirectness="serious",
        )
        by = {d.name: d for d in mc.domains}
        self.assertEqual(by["Risk of bias"].steps, 1)
        self.assertEqual(by["Risk of bias"].basis, "reviewer-assessed")
        self.assertEqual(by["Indirectness"].steps, 1)
        self.assertEqual(by["Indirectness"].basis, "reviewer-assessed")
        # A downgraded twice → C
        self.assertEqual(mc.level, EvidenceLevel.C.value)

    def test_very_serious_is_two_steps(self):
        mc = gp.certainty_from_meta(_strong_consistent(),
                                    risk_of_bias="very-serious")
        by = {d.name: d for d in mc.domains}
        self.assertEqual(by["Risk of bias"].steps, 2)
        self.assertEqual(mc.level, EvidenceLevel.C.value)

    def test_bad_seriousness_value_defaults_not_serious(self):
        mc = gp.certainty_from_meta(_strong_consistent(),
                                    risk_of_bias="catastrophic")
        by = {d.name: d for d in mc.domains}
        self.assertEqual(by["Risk of bias"].steps, 0)


class PublicationBiasTests(unittest.TestCase):
    def test_no_egger_is_not_assessed(self):
        mc = gp.certainty_from_meta(_strong_consistent())
        pb = {d.name: d for d in mc.domains}["Publication bias"]
        self.assertEqual(pb.steps, 0)
        self.assertEqual(pb.assessment, "not assessed")

    def test_underpowered_egger_does_not_downgrade(self):
        # k = 3 < 10 → Egger reported but never a downgrade (spec 012 honesty).
        res = _strong_consistent()
        egger = ma.egger_test(res.studies)
        mc = gp.certainty_from_meta(res, egger=egger)
        pb = {d.name: d for d in mc.domains}["Publication bias"]
        self.assertEqual(pb.steps, 0)
        self.assertIn("Egger", pb.basis)


class FloorAndRenderTests(unittest.TestCase):
    def test_four_serious_domains_floor_at_very_low(self):
        # inconsistency 2 + rob serious + indirectness serious = 4 steps → E.
        mc = gp.certainty_from_meta(
            _high_i2_same_sign(),
            risk_of_bias="serious", indirectness="serious",
        )
        self.assertEqual(mc.total_steps, 4)
        self.assertEqual(mc.level, EvidenceLevel.E.value)
        self.assertEqual(mc.grade_word, "Very Low")
        self.assertEqual(mc.glyph, "⊕⊝⊝⊝")

    def test_render_has_glyph_and_domain_table(self):
        text = gp.render_certainty(gp.certainty_from_meta(_near_null()))
        self.assertIn("GRADE certainty of evidence", text)
        self.assertIn("⊕", text)
        self.assertIn("| Domain | Assessment | Downgrade | Basis |", text)
        self.assertIn("reviewer-assessed", text)

    def test_deterministic_dict(self):
        a = gp.certainty_from_meta(_near_null()).to_dict()
        b = gp.certainty_from_meta(_near_null()).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))


class CliCertaintyTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def _spec(self, tmp):
        spec = {"measure": "RR", "studies": [
            {"study_id": "Devinsky 2017", "events_t": 20, "n_t": 100,
             "events_c": 40, "n_c": 100, "pmid": "28538134"},
            {"study_id": "Thiele 2018", "events_t": 25, "n_t": 110,
             "events_c": 45, "n_c": 110, "pmid": "29642420"},
            {"study_id": "Miller 2020", "events_t": 18, "n_t": 90,
             "events_c": 38, "n_c": 95, "pmid": "32444460"},
        ]}
        p = Path(tmp) / "rr.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        return str(p)

    def test_meta_certainty_markdown(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure", "RR",
                                   "--certainty"])
        self.assertEqual(code, 0)
        self.assertIn("GRADE certainty of evidence", out)
        self.assertIn("⊕⊕⊕⊕", out)

    def test_meta_certainty_json(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure", "RR",
                                   "--certainty", "--risk-of-bias", "serious",
                                   "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("certainty", payload)
        self.assertEqual(payload["certainty"]["grade_word"], "Moderate")

    def test_full_sof_certainty_plus_absolute(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run([
                "meta", self._spec(tmp), "--measure", "RR",
                "--certainty", "--baseline-risk", "0.40",
                "--outcome", "convulsive seizures",
            ])
        self.assertEqual(code, 0)
        self.assertIn("GRADE certainty of evidence", out)
        self.assertIn("Anticipated absolute effects", out)
        self.assertIn("NNT", out)

    def test_certainty_table_surfaces_ois(self):
        # --baseline-risk sizes both the absolute effect and the OIS (spec 018).
        with TemporaryDirectory() as tmp:
            code, out = self._run([
                "meta", self._spec(tmp), "--measure", "RR",
                "--certainty", "--baseline-risk", "0.40",
            ])
        self.assertEqual(code, 0)
        self.assertIn("OIS", out)
        self.assertIn("meets", out)        # strong RR pool meets its OIS

    def test_certainty_json_imprecision_basis_has_ois(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run([
                "meta", self._spec(tmp), "--measure", "RR",
                "--certainty", "--baseline-risk", "0.40", "--json",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        imp = {d["name"]: d for d in payload["certainty"]["domains"]}["Imprecision"]
        self.assertIn("OIS", imp["basis"])


if __name__ == "__main__":
    unittest.main()
