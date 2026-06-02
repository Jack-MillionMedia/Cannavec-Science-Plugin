"""Tests for meta-regression on a continuous moderator (spec 020).

Pinned against a direct WLS + DerSimonian-Laird residual-τ² implementation;
the exact-linear case recovers the generating slope to machine precision.
"""

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import meta_analysis as ma


def _eff(i, yi, vi):
    return ma.EffectSize(study_id=f"S{i}", yi=yi, vi=vi, pmid=str(i))


def _trend():
    data = [(0.20, 0.02), (0.35, 0.015), (0.30, 0.02),
            (0.55, 0.01), (0.62, 0.012), (0.70, 0.02)]
    effs = [_eff(i, y, v) for i, (y, v) in enumerate(data)]
    xs = [10, 20, 30, 40, 50, 60]
    return effs, xs


class FitTests(unittest.TestCase):
    def test_exact_linear_recovers_slope(self):
        xs = [1, 2, 3, 4, 5]
        effs = [_eff(i, 1.0 + 0.5 * x, 0.1) for i, x in enumerate(xs)]
        r = ma.meta_regression(effs, xs, moderator_name="dose")
        self.assertAlmostEqual(r.slope, 0.5, places=9)
        self.assertAlmostEqual(r.intercept, 1.0, places=9)
        self.assertAlmostEqual(r.r_squared, 1.0, places=6)
        self.assertAlmostEqual(r.q_residual, 0.0, places=9)

    def test_trend_is_significant_wald(self):
        effs, xs = _trend()
        r = ma.meta_regression(effs, xs, moderator_name="THC")
        self.assertAlmostEqual(r.slope, 0.010188679, places=6)
        self.assertAlmostEqual(r.slope_stat, 3.2118589, places=4)   # Wald z
        self.assertLess(r.slope_p, 0.05)
        self.assertFalse(r.knha)

    def test_knha_uses_t(self):
        effs, xs = _trend()
        r = ma.meta_regression(effs, xs, moderator_name="THC", knha=True)
        self.assertTrue(r.knha)
        self.assertAlmostEqual(r.slope, 0.010188679, places=6)   # slope unchanged
        # KNHA t-stat differs from the Wald z on the same slope.
        self.assertNotAlmostEqual(r.slope_stat, 3.2118589, places=3)

    def test_flat_moderator_not_significant(self):
        xs = [1, 2, 3, 4, 5, 6]
        effs = [_eff(i, y, 0.01) for i, y in
                enumerate([0.40, 0.42, 0.39, 0.41, 0.40, 0.43])]
        r = ma.meta_regression(effs, xs)
        self.assertLess(abs(r.slope), 0.02)
        self.assertGreater(r.slope_p, 0.05)
        self.assertLess(r.r_squared, 0.5)

    def test_partial_r_squared(self):
        # A trend plus residual scatter → 0 < R² < 1 and residual I² > 0.
        xs = [10, 20, 30, 40, 50, 60, 70, 80]
        ys = [0.20, 0.50, 0.25, 0.62, 0.30, 0.70, 0.40, 0.85]
        effs = [_eff(i, y, 0.01) for i, y in enumerate(ys)]
        r = ma.meta_regression(effs, xs)
        self.assertGreater(r.r_squared, 0.0)
        self.assertLess(r.r_squared, 1.0)
        self.assertGreater(r.i_squared_residual, 0.0)

    def test_enough_studies_flag(self):
        xs = list(range(1, 13))
        effs = [_eff(i, 0.1 * x, 0.05) for i, x in enumerate(xs)]
        r = ma.meta_regression(effs, xs)
        self.assertTrue(r.enough_studies)             # k = 12 ≥ 10
        self.assertNotIn("CAUTION", r.rationale)
        small = ma.meta_regression(effs[:5], xs[:5])
        self.assertFalse(small.enough_studies)
        self.assertIn("CAUTION", small.rationale)


class GuardTests(unittest.TestCase):
    def test_too_few_studies_refuses(self):
        effs = [_eff(0, 0.1, 0.1), _eff(1, 0.2, 0.1)]
        with self.assertRaises(ma.MetaAnalysisError):
            ma.meta_regression(effs, [1, 2])

    def test_no_variance_moderator_refuses(self):
        effs, _ = _trend()
        with self.assertRaises(ma.MetaAnalysisError):
            ma.meta_regression(effs, [5, 5, 5, 5, 5, 5])

    def test_length_mismatch_refuses(self):
        effs, xs = _trend()
        with self.assertRaises(ma.MetaAnalysisError):
            ma.meta_regression(effs, xs[:-1])

    def test_missing_identifier_refuses_upstream(self):
        # §I is enforced at EffectSize construction, before regression can run —
        # no unanchored effect can reach the pipeline.
        with self.assertRaises(ma.MetaAnalysisError):
            ma.EffectSize(study_id="c", yi=0.3, vi=0.1)


class ShapeTests(unittest.TestCase):
    def test_to_dict_deterministic(self):
        effs, xs = _trend()
        a = ma.meta_regression(effs, xs).to_dict()
        b = ma.meta_regression(effs, xs).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertEqual(a["test"], "wald-z")

    def test_render_has_slope_and_r2(self):
        effs, xs = _trend()
        text = ma.render_meta_regression(
            ma.meta_regression(effs, xs, moderator_name="THC", knha=True))
        self.assertIn("Meta-regression on THC", text)
        self.assertIn("Slope", text)
        self.assertIn("R²", text)
        self.assertIn("Knapp-Hartung", text)


class CliTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def _spec(self, tmp):
        studies = [
            {"study_id": f"S{i}", "yi": y, "vi": 0.015, "dose": d, "pmid": str(i)}
            for i, (y, d) in enumerate(
                [(0.2, 10), (0.35, 20), (0.3, 30), (0.55, 40), (0.62, 50), (0.7, 60)])
        ]
        p = Path(tmp) / "mr.json"
        p.write_text(json.dumps({"measure": "generic", "studies": studies}),
                     encoding="utf-8")
        return str(p)

    def test_cli_markdown(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure",
                                   "generic", "--moderator-key", "dose", "--knha"])
        self.assertEqual(code, 0)
        self.assertIn("Meta-regression on dose", out)
        self.assertIn("R²", out)

    def test_cli_json(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure",
                                   "generic", "--moderator-key", "dose", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("meta_regression", payload)
        self.assertEqual(payload["meta_regression"]["moderator"], "dose")

    def test_cli_missing_field_nonzero(self):
        with TemporaryDirectory() as tmp:
            code, _ = self._run(["meta", self._spec(tmp), "--measure",
                                 "generic", "--moderator-key", "nope"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
