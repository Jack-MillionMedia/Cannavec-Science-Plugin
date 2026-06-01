"""Tests for meta-analysis robustness diagnostics (spec 012).

Egger's test reference example is hand-verified in the docstring so a
reviewer can re-derive every assertion. Constitution §III: positive +
negative + refusal cases for every public function.
"""

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import meta_analysis as ma


class EggerReferenceTests(unittest.TestCase):
    """Hand-verified worked example.

    Three studies chosen so the (precision, SND) points are exactly
    (1, 1), (2, 2), (3, 2):

      A: yi=1.0,    vi=1.0    → se=1,    x=1, snd=1
      B: yi=1.0,    vi=0.25   → se=0.5,  x=2, snd=2
      C: yi=2/3,    vi=1/9    → se=1/3,  x=3, snd=2

    OLS of SND on precision:
      x̄=2, ȳ=5/3, Sxx=2, Sxy=1 → slope=0.5, intercept=2/3
      residuals (−1/6, 1/3, −1/6); Σe²=1/6; s²=1/6 (df=1)
      SE(a)=sqrt((1/6)(1/3 + 4/2))=sqrt(7/18)=0.623610
      t=（2/3)/0.623610=1.069045, df=1
      two-sided p (Cauchy) = 1 − (2/π)·atan(1.069045) = 0.47879
    """

    def setUp(self):
        self.effects = [
            ma.EffectSize(study_id="A", yi=1.0, vi=1.0, pmid="1"),
            ma.EffectSize(study_id="B", yi=1.0, vi=0.25, pmid="2"),
            ma.EffectSize(study_id="C", yi=2.0 / 3.0, vi=1.0 / 9.0, pmid="3"),
        ]
        self.res = ma.egger_test(self.effects)

    def test_intercept_and_slope(self):
        self.assertAlmostEqual(self.res.intercept, 2.0 / 3.0, places=5)
        self.assertAlmostEqual(self.res.slope, 0.5, places=5)

    def test_intercept_se(self):
        self.assertAlmostEqual(self.res.intercept_se, (7.0 / 18.0) ** 0.5, places=5)

    def test_t_and_df(self):
        self.assertEqual(self.res.df, 1)
        self.assertAlmostEqual(self.res.t, 1.069045, places=4)

    def test_p_value(self):
        self.assertAlmostEqual(self.res.p_value, 0.47879, places=3)

    def test_k_below_10_never_triggers_downgrade(self):
        # This example has p ≈ 0.48 → "undetected"; and with only k=3 a
        # serious downgrade can never be triggered regardless (Sterne 2011).
        self.assertFalse(self.res.bias_serious)
        self.assertEqual(self.res.bias_label, "undetected")

    def test_requires_three_studies(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.egger_test(self.effects[:2])


class EggerRegimeTests(unittest.TestCase):
    def _ladder(self, asymmetric: bool):
        # 10 studies; se = 0.1..1.0. Symmetric: yi constant (effect ⟂
        # precision). Asymmetric: small studies (large se) show larger effects.
        effects = []
        for i in range(1, 11):
            se = i / 10.0
            vi = se * se
            if asymmetric:
                yi = 0.2 + 0.8 * se + 0.01 * (1 if i % 2 else -1)
            else:
                yi = 0.3 + 0.01 * (1 if i % 2 else -1)
            effects.append(ma.EffectSize(study_id=f"S{i}", yi=yi, vi=vi, pmid=str(i)))
        return effects

    def test_strong_asymmetry_k10_is_serious(self):
        res = ma.egger_test(self._ladder(asymmetric=True))
        self.assertEqual(res.k, 10)
        self.assertLess(res.p_value, 0.10)
        self.assertTrue(res.bias_serious)
        self.assertEqual(res.bias_label, "strongly suspected")

    def test_symmetric_is_undetected(self):
        res = ma.egger_test(self._ladder(asymmetric=False))
        self.assertGreaterEqual(res.p_value, 0.10)
        self.assertFalse(res.bias_serious)
        self.assertEqual(res.bias_label, "undetected")


class PublicationBiasMappingTests(unittest.TestCase):
    def test_verdict_thresholds(self):
        self.assertEqual(ma._pubbias_verdict(0.05, 12)[0], "strongly suspected")
        self.assertTrue(ma._pubbias_verdict(0.05, 12)[1])
        self.assertEqual(
            ma._pubbias_verdict(0.05, 5)[0], "small-study effects detected (underpowered)"
        )
        self.assertFalse(ma._pubbias_verdict(0.05, 5)[1])
        self.assertEqual(ma._pubbias_verdict(0.5, 12)[0], "undetected")
        self.assertIn("not assessable", ma._pubbias_verdict(0.05, 2)[0])

    def test_grade_publication_bias_accessor(self):
        res = ma.EggerResult(
            k=12, intercept=1.5, intercept_se=0.4, t=3.75, df=10,
            p_value=0.004, slope=0.1, bias_label="strongly suspected",
            bias_serious=True, rationale="…",
        )
        label, serious, _ = ma.grade_publication_bias(res)
        self.assertEqual(label, "strongly suspected")
        self.assertTrue(serious)


class StudentTAndBetaNumericsTests(unittest.TestCase):
    def test_incomplete_beta_known_values(self):
        self.assertAlmostEqual(ma._betai(0.5, 0.5, 0.5), 0.5, places=6)  # arcsine
        self.assertAlmostEqual(ma._betai(2.0, 2.0, 0.5), 0.5, places=6)  # symmetric
        self.assertEqual(ma._betai(2.0, 3.0, 0.0), 0.0)
        self.assertEqual(ma._betai(2.0, 3.0, 1.0), 1.0)

    def test_t_two_sided_known_critical_values(self):
        self.assertAlmostEqual(ma._t_sf_two_sided(0.0, 5), 1.0, places=9)
        self.assertAlmostEqual(ma._t_sf_two_sided(2.570582, 5), 0.05, places=4)
        self.assertAlmostEqual(ma._t_sf_two_sided(2.228139, 10), 0.05, places=4)
        self.assertAlmostEqual(ma._t_sf_two_sided(12.706205, 1), 0.05, places=4)


class LeaveOneOutTests(unittest.TestCase):
    def test_requires_two_studies(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.leave_one_out([ma.EffectSize(study_id="A", yi=0.2, vi=0.01, pmid="1")])

    def test_row_shape_and_dropped_ids(self):
        effects = [
            ma.EffectSize(study_id="A", yi=0.1, vi=0.01, pmid="1"),
            ma.EffectSize(study_id="B", yi=0.2, vi=0.01, pmid="2"),
            ma.EffectSize(study_id="C", yi=0.15, vi=0.01, pmid="3"),
        ]
        rows = ma.leave_one_out(effects)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r.dropped_study_id for r in rows], ["A", "B", "C"])
        for r in rows:
            self.assertEqual(r.k_remaining, 2)
            self.assertEqual(r.dropped_identifier[:4], "PMID")

    def test_outlier_has_largest_influence(self):
        # Two studies agree at 0.0; one outlier at 1.0. Dropping the outlier
        # moves the pooled estimate the most.
        effects = [
            ma.EffectSize(study_id="agree1", yi=0.0, vi=0.01, pmid="1"),
            ma.EffectSize(study_id="agree2", yi=0.0, vi=0.01, pmid="2"),
            ma.EffectSize(study_id="outlier", yi=1.0, vi=0.01, pmid="3"),
        ]
        rows = ma.leave_one_out(effects)
        most_influential = max(rows, key=lambda r: r.influence)
        self.assertEqual(most_influential.dropped_study_id, "outlier")

    def test_determinism(self):
        effects = [
            ma.EffectSize(study_id="A", yi=0.1, vi=0.02, pmid="1"),
            ma.EffectSize(study_id="B", yi=0.3, vi=0.03, pmid="2"),
        ]
        self.assertEqual(
            [r.to_dict() for r in ma.leave_one_out(effects)],
            [r.to_dict() for r in ma.leave_one_out(effects)],
        )


class RenderTests(unittest.TestCase):
    def test_render_egger_contains_stats(self):
        res = ma.egger_test([
            ma.EffectSize(study_id="A", yi=1.0, vi=1.0, pmid="1"),
            ma.EffectSize(study_id="B", yi=1.0, vi=0.25, pmid="2"),
            ma.EffectSize(study_id="C", yi=0.6, vi=0.1, pmid="3"),
        ])
        md = ma.render_egger(res)
        self.assertIn("Egger", md)
        self.assertIn("Intercept", md)
        self.assertIn("Publication bias", md)

    def test_render_leave_one_out_table(self):
        rows = ma.leave_one_out([
            ma.EffectSize(study_id="Alpha", yi=0.1, vi=0.01, pmid="1"),
            ma.EffectSize(study_id="Beta", yi=0.2, vi=0.01, pmid="2"),
        ])
        md = ma.render_leave_one_out(rows)
        self.assertIn("Leave-one-out", md)
        self.assertIn("Alpha", md)
        self.assertIn("Influence", md)


class CliDiagnosticsTests(unittest.TestCase):
    def _run(self, argv):
        from cannavec_science.__main__ import main
        return main(argv)

    def _write(self, payload):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "studies.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_diagnostics_json_has_egger_and_loo(self):
        path = self._write({
            "measure": "generic",
            "studies": [
                {"study_id": "S1", "pmid": "1", "yi": 0.1, "vi": 0.02},
                {"study_id": "S2", "pmid": "2", "yi": 0.5, "vi": 0.04},
                {"study_id": "S3", "pmid": "3", "yi": 0.3, "vi": 0.03},
            ],
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run(["meta", path, "--diagnostics", "--json"])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertIn("egger", out)
        self.assertEqual(out["egger"]["k"], 3)
        self.assertIn("leave_one_out", out)
        self.assertEqual(len(out["leave_one_out"]), 3)

    def test_diagnostics_two_studies_egger_note(self):
        path = self._write({
            "measure": "generic",
            "studies": [
                {"study_id": "S1", "pmid": "1", "yi": 0.1, "vi": 0.02},
                {"study_id": "S2", "pmid": "2", "yi": 0.5, "vi": 0.04},
            ],
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run(["meta", path, "--diagnostics", "--json"])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertIn("note", out["egger"])  # < 3 studies
        self.assertEqual(len(out["leave_one_out"]), 2)

    def test_diagnostics_markdown_sections(self):
        path = self._write({
            "measure": "generic",
            "studies": [
                {"study_id": "S1", "pmid": "1", "yi": 0.1, "vi": 0.02},
                {"study_id": "S2", "pmid": "2", "yi": 0.5, "vi": 0.04},
                {"study_id": "S3", "pmid": "3", "yi": 0.3, "vi": 0.03},
            ],
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run(["meta", path, "--diagnostics"])
        self.assertEqual(rc, 0)
        text = buf.getvalue()
        self.assertIn("Egger", text)
        self.assertIn("Leave-one-out", text)


if __name__ == "__main__":
    unittest.main()
