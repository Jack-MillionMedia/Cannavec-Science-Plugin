"""Tests for the Hartung-Knapp-Sidik-Jonkman interval (spec 021).

Pinned against the modified-HKSJ formula: variance scaled by the weighted
residual (clamped to ≥ 1) and a t-distribution with k−1 df.
"""

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import meta_analysis as ma


def _rr_k3():
    return ma.meta_analyze([
        ma.binary_effect("A", events_t=20, n_t=100, events_c=40, n_c=100,
                         measure="RR", pmid="1"),
        ma.binary_effect("B", events_t=25, n_t=110, events_c=45, n_c=110,
                         measure="RR", pmid="2"),
        ma.binary_effect("C", events_t=18, n_t=90, events_c=38, n_c=95,
                         measure="RR", pmid="3"),
    ], measure="RR")


def _heterogeneous():
    return ma.meta_analyze([
        ma.EffectSize(study_id="S1", yi=0.1, vi=0.01, pmid="1"),
        ma.EffectSize(study_id="S2", yi=1.2, vi=0.08, pmid="2"),
        ma.EffectSize(study_id="S3", yi=0.3, vi=0.02, pmid="3"),
        ma.EffectSize(study_id="S4", yi=0.9, vi=0.05, pmid="4"),
    ], measure="generic")


class IntervalTests(unittest.TestCase):
    def test_modified_clamps_when_studies_are_consistent(self):
        h = ma.hksj_interval(_rr_k3())
        self.assertAlmostEqual(h.q_factor, 0.0763, places=3)
        self.assertTrue(h.clamped)                      # q < 1 → raised to 1.0
        self.assertTrue(h.modified)
        self.assertAlmostEqual(h.ci_display[0], 0.2955, places=3)
        self.assertAlmostEqual(h.ci_display[1], 0.9194, places=3)

    def test_point_estimate_matches_dl_random(self):
        res = _rr_k3()
        h = ma.hksj_interval(res)
        self.assertAlmostEqual(h.estimate_display,
                               res.random_estimate_display, places=9)

    def test_modified_is_never_narrower_than_dl(self):
        for res in (_rr_k3(), _heterogeneous()):
            h = ma.hksj_interval(res)
            dl = res.random_ci_display
            self.assertGreaterEqual(h.ci_display[1] - h.ci_display[0],
                                    dl[1] - dl[0] - 1e-9)

    def test_raw_can_be_narrower(self):
        # The unmodified HKSJ understates uncertainty for a consistent pool —
        # exactly why the modified variant is the default.
        res = _rr_k3()
        raw = ma.hksj_interval(res, modified=False)
        dl = res.random_ci_display
        self.assertFalse(raw.clamped)
        self.assertLess(raw.ci_display[1] - raw.ci_display[0], dl[1] - dl[0])

    def test_heterogeneous_pool_not_clamped(self):
        h = ma.hksj_interval(_heterogeneous())
        self.assertGreater(h.q_factor, 1.0)
        self.assertFalse(h.clamped)

    def test_uses_t_with_k_minus_one_df(self):
        res = _heterogeneous()
        h = ma.hksj_interval(res)
        from cannavec_science.meta_analysis import _t_critical
        self.assertAlmostEqual(h.t_critical,
                               _t_critical(res.confidence, res.k - 1), places=9)

    def test_single_study_refuses(self):
        res = ma.meta_analyze([
            ma.EffectSize(study_id="solo", yi=0.5, vi=0.02, pmid="1")],
            measure="generic")
        with self.assertRaises(ma.MetaAnalysisError):
            ma.hksj_interval(res)


class ShapeTests(unittest.TestCase):
    def test_to_dict_deterministic_and_tagged(self):
        a = ma.hksj_interval(_rr_k3()).to_dict()
        b = ma.hksj_interval(_rr_k3()).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertEqual(a["method"], "hksj_modified")

    def test_render_has_interval_and_rationale(self):
        text = ma.render_hksj(ma.hksj_interval(_rr_k3()))
        self.assertIn("Hartung-Knapp-Sidik-Jonkman", text)
        self.assertIn("HKSJ CI", text)
        self.assertIn("t-distribution", text)


class CliTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def _spec(self, tmp):
        spec = {"measure": "RR", "studies": [
            {"study_id": "A", "events_t": 20, "n_t": 100,
             "events_c": 40, "n_c": 100, "pmid": "1"},
            {"study_id": "B", "events_t": 25, "n_t": 110,
             "events_c": 45, "n_c": 110, "pmid": "2"},
            {"study_id": "C", "events_t": 18, "n_t": 90,
             "events_c": 38, "n_c": 95, "pmid": "3"},
        ]}
        p = Path(tmp) / "rr.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        return str(p)

    def test_cli_knha_shows_hksj(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure", "RR",
                                   "--knha"])
        self.assertEqual(code, 0)
        self.assertIn("Hartung-Knapp-Sidik-Jonkman", out)

    def test_cli_without_knha_has_no_hksj(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure", "RR"])
        self.assertEqual(code, 0)
        self.assertNotIn("Hartung-Knapp", out)

    def test_cli_json_has_hksj(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run(["meta", self._spec(tmp), "--measure", "RR",
                                   "--knha", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("hksj", payload)
        self.assertEqual(payload["hksj"]["method"], "hksj_modified")


if __name__ == "__main__":
    unittest.main()
