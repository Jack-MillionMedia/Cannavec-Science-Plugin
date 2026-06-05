"""Tests for single-arm proportion meta-analysis (Freeman-Tukey, spec 019).

Values are numerically pinned against a direct implementation of the
double-arcsine transform + DerSimonian-Laird pooling + Miller (1978) inverse.
"""

import contextlib
import io
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import meta_analysis as ma


def _somnolence():
    """Four single-arm event counts — the pinned reference pool."""
    return [
        ma.proportion_effect("S1", events=36, n=61, pmid="1"),
        ma.proportion_effect("S2", events=30, n=86, pmid="2"),
        ma.proportion_effect("S3", events=25, n=76, pmid="3"),
        ma.proportion_effect("S4", events=23, n=65, pmid="4"),
    ]


class TransformTests(unittest.TestCase):
    def test_ft_transform_matches_definition(self):
        es = ma.proportion_effect("x", events=40, n=100, pmid="1")
        expect = (math.asin(math.sqrt(40 / 101))
                  + math.asin(math.sqrt(41 / 101)))
        self.assertAlmostEqual(es.yi, expect, places=12)
        self.assertAlmostEqual(es.vi, 1.0 / 101, places=12)
        self.assertEqual(es.measure, "PFT")
        self.assertEqual(es.events, 40)
        self.assertEqual(es.n, 100)

    def test_single_study_round_trips(self):
        # FT then back-transform with the study's own n recovers the rate.
        for e, n in [(40, 100), (1, 200), (23, 65), (5, 9)]:
            es = ma.proportion_effect("x", events=e, n=n, pmid="1")
            back = ma._ft_back_transform(es.yi, n)
            self.assertAlmostEqual(back, e / n, places=3)

    def test_boundary_zero_and_one(self):
        # The double arcsine is defined at 0% and 100% (logit is not).
        z = ma._ft_back_transform(ma.proportion_effect("z", events=0, n=50, pmid="1").yi, 50)
        one = ma._ft_back_transform(ma.proportion_effect("o", events=50, n=50, pmid="1").yi, 50)
        self.assertAlmostEqual(z, 0.0, places=3)
        self.assertAlmostEqual(one, 1.0, places=3)


class PoolingTests(unittest.TestCase):
    def test_pooled_rate_matches_reference(self):
        res = ma.proportion_meta_analyze(_somnolence())
        self.assertEqual(res.k, 4)
        self.assertAlmostEqual(res.random_proportion, 0.4016, places=3)
        self.assertAlmostEqual(res.random_ci[0], 0.2909, places=3)
        self.assertAlmostEqual(res.random_ci[1], 0.5175, places=3)
        self.assertAlmostEqual(res.i_squared, 74.9, places=0)
        self.assertAlmostEqual(res.harmonic_n, 70.717, places=2)

    def test_prediction_interval_back_transformed(self):
        res = ma.proportion_meta_analyze(_somnolence())
        self.assertIsNotNone(res.prediction_interval)
        lo, hi = res.prediction_interval
        # High I² → a wide, honest prediction interval.
        self.assertLess(lo, 0.10)
        self.assertGreater(hi, 0.80)

    def test_inconsistency_verdict_flows(self):
        res = ma.proportion_meta_analyze(_somnolence())
        self.assertEqual(res.inconsistency, "serious")   # I² ≈ 75%
        self.assertEqual(res.downgrade_steps, 1)

    def test_all_zero_events_pools_at_zero(self):
        res = ma.proportion_meta_analyze([
            ma.proportion_effect("Z1", events=0, n=40, pmid="1"),
            ma.proportion_effect("Z2", events=0, n=50, pmid="2"),
        ])
        self.assertAlmostEqual(res.random_proportion, 0.0, places=3)
        self.assertEqual(res.random_ci[0], 0.0)
        self.assertGreater(res.random_ci[1], 0.0)        # one-sided upper bound

    def test_single_study_has_no_prediction_interval(self):
        res = ma.proportion_meta_analyze([
            ma.proportion_effect("Solo", events=20, n=80, pmid="1"),
        ])
        self.assertEqual(res.k, 1)
        self.assertIsNone(res.prediction_interval)
        self.assertAlmostEqual(res.random_proportion, 0.25, places=2)


class GuardTests(unittest.TestCase):
    def test_missing_identifier_refuses(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.proportion_effect("noid", events=5, n=10)

    def test_events_out_of_range_refuses(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.proportion_effect("x", events=11, n=10, pmid="1")

    def test_zero_n_refuses(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.proportion_effect("x", events=0, n=0, pmid="1")

    def test_empty_pool_refuses(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.proportion_meta_analyze([])

    def test_non_pft_effects_refused(self):
        ratio = ma.binary_effect("x", events_t=5, n_t=10, events_c=3, n_c=10,
                                 measure="RR", pmid="1")
        with self.assertRaises(ma.MetaAnalysisError):
            ma.proportion_meta_analyze([ratio])


class RecordsParserTests(unittest.TestCase):
    def test_effects_from_records_prop(self):
        effs = ma.effects_from_records(
            [{"study_id": "A", "events": 10, "n": 40, "pmid": "1"}],
            measure="prop",
        )
        self.assertEqual(effs[0].measure, "PFT")
        self.assertEqual(effs[0].events, 10)

    def test_records_accept_aliases(self):
        effs = ma.effects_from_records(
            [{"study_id": "A", "cases": 10, "total": 40, "pmid": "1"}],
            measure="proportion",
        )
        self.assertEqual(effs[0].events, 10)
        self.assertEqual(effs[0].n, 40)

    def test_records_missing_field_raises(self):
        with self.assertRaises(KeyError):
            ma.effects_from_records(
                [{"study_id": "A", "events": 10, "pmid": "1"}], measure="prop")


class ShapeTests(unittest.TestCase):
    def test_to_dict_deterministic(self):
        a = ma.proportion_meta_analyze(_somnolence()).to_dict()
        b = ma.proportion_meta_analyze(_somnolence()).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertEqual(a["measure"], "PFT")
        self.assertEqual(len(a["studies"]), 4)
        self.assertAlmostEqual(a["studies"][0]["proportion"], 36 / 61, places=6)

    def test_render_has_rate_and_footnote(self):
        text = ma.render_proportion(ma.proportion_meta_analyze(_somnolence()))
        self.assertIn("Single-arm proportion meta-analysis", text)
        self.assertIn("Pooled rate (random)", text)
        self.assertIn("40.2%", text)
        self.assertIn("not a treatment effect", text)


class CliTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def _spec(self, tmp):
        spec = {"measure": "prop", "studies": [
            {"study_id": "S1", "events": 36, "n": 61, "pmid": "1"},
            {"study_id": "S2", "events": 30, "n": 86, "pmid": "2"},
            {"study_id": "S3", "events": 25, "n": 76, "pmid": "3"},
            {"study_id": "S4", "events": 23, "n": 65, "pmid": "4"},
        ]}
        p = Path(tmp) / "prop.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        return str(p)

    def test_cli_markdown(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure", "prop"])
        self.assertEqual(code, 0)
        self.assertIn("Single-arm proportion meta-analysis", out)
        self.assertIn("40.2%", out)

    def test_cli_json_with_diagnostics(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure", "prop",
                                   "--diagnostics", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["measure"], "PFT")
        self.assertIn("egger", payload)
        self.assertAlmostEqual(payload["random"]["proportion"], 0.4016, places=3)

    def test_cli_refuses_missing_identifier(self):
        with TemporaryDirectory() as tmp:
            spec = {"measure": "prop",
                    "studies": [{"study_id": "X", "events": 5, "n": 10}]}
            p = Path(tmp) / "bad.json"
            p.write_text(json.dumps(spec), encoding="utf-8")
            code, _ = self._run(["meta", str(p), "--measure", "prop"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
