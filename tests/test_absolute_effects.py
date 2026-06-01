"""Tests for absolute effects & Number-Needed-to-Treat (spec 015).

Every reference value is hand-derived in the docstrings (Constitution §III:
positive + negative + refusal for every public function). The honesty
centrepiece is the Altman (1998) null-crossing NNT convention.
"""

import contextlib
import io
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import absolute_effects as ae
from cannavec_science import meta_analysis as ma


class RiskProvenanceTests(unittest.TestCase):
    def test_sourced_when_identifier_present(self):
        p = ae.RiskProvenance(label="pooled placebo arms", pmid="28538134")
        self.assertTrue(p.sourced)
        self.assertEqual(p.identifier, "PMID:28538134")
        self.assertEqual(p.to_dict()["identifier"], "PMID:28538134")

    def test_unsourced_when_no_identifier(self):
        p = ae.RiskProvenance(label="assumed 20% per year")
        self.assertFalse(p.sourced)
        self.assertIsNone(p.identifier)

    def test_identifier_scheme_priority(self):
        p = ae.RiskProvenance(label="x", doi="10.1/x", nct="NCT01")
        self.assertEqual(p.identifier, "DOI:10.1/x")


class RiskRatioReferenceTests(unittest.TestCase):
    """RR = 0.50, CI (0.40, 0.625), ACR = 0.20, undesirable outcome.

      EER  = 0.50·0.20 = 0.10
      RD   = 0.10 − 0.20 = −0.10           → NNTB = 10
      EER_lo = 0.40·0.20 = 0.08 → RD −0.12 → 1/0.12 = 8.333…
      EER_hi = 0.625·0.20 = 0.125 → RD −0.075 → 1/0.075 = 13.333…
      CI does not cross null → NNTB 8.33 to 13.33
    """

    def _ae(self):
        return ae.absolute_effect(
            measure="RR", estimate=0.5, ci=(0.4, 0.625), acr=0.20,
            outcome="convulsive seizures", outcome_desirable=False,
        )

    def test_eer_and_rd(self):
        e = self._ae()
        self.assertAlmostEqual(e.eer, 0.10, places=6)
        self.assertAlmostEqual(e.rd, -0.10, places=6)
        self.assertFalse(e.eer_clamped)

    def test_rd_ci(self):
        e = self._ae()
        self.assertAlmostEqual(e.rd_ci[0], -0.12, places=6)
        self.assertAlmostEqual(e.rd_ci[1], -0.075, places=6)

    def test_nnt_point_and_ci(self):
        e = self._ae()
        self.assertEqual(e.nnt_kind, "NNTB")
        self.assertTrue(e.benefit)
        self.assertAlmostEqual(e.nnt, 10.0, places=6)
        self.assertFalse(e.nnt_crosses_null)
        self.assertIsNotNone(e.nnt_ci)
        self.assertAlmostEqual(e.nnt_ci[0], 1 / 0.12, places=4)
        self.assertAlmostEqual(e.nnt_ci[1], 1 / 0.075, places=4)

    def test_render_has_sof_columns(self):
        text = ae.render_markdown(self._ae())
        self.assertIn("per 1000", text)
        self.assertIn("NNTB", text)
        self.assertIn("100 fewer", text)  # |RD|·1000 = 100, undesirable → fewer

    def test_unsourced_baseline_caveat(self):
        e = self._ae()
        self.assertFalse(e.acr_sourced)
        self.assertIn("assumed", ae.render_markdown(e).lower())
        self.assertFalse(e.to_dict()["acr_sourced"])

    def test_sourced_baseline_no_caveat_shows_identifier(self):
        e = ae.absolute_effect(
            measure="RR", estimate=0.5, ci=(0.4, 0.625), acr=0.20,
            outcome="seizures", outcome_desirable=False,
            acr_provenance=ae.RiskProvenance(label="Devinsky 2017 placebo arm",
                                             pmid="28538134"),
        )
        self.assertTrue(e.acr_sourced)
        self.assertIn("PMID:28538134", ae.render_markdown(e))


class OddsRatioTransformTests(unittest.TestCase):
    """OR = 0.50, ACR = 0.20 — verifies the odds→risk transform differs
    from the RR path.

      EER = (0.5·0.2) / (1 − 0.2 + 0.5·0.2) = 0.10 / 0.90 = 0.11111…
      RD  = 0.11111 − 0.20 = −0.08889 → NNTB = 11.25
    """

    def test_or_eer_uses_odds_transform(self):
        e = ae.absolute_effect(
            measure="OR", estimate=0.5, ci=(0.3, 0.8), acr=0.20,
            outcome="relapse", outcome_desirable=False,
        )
        self.assertAlmostEqual(e.eer, 0.1111111, places=6)
        self.assertAlmostEqual(e.rd, -0.0888889, places=6)
        self.assertAlmostEqual(e.nnt, 11.25, places=4)
        self.assertEqual(e.nnt_kind, "NNTB")


class AltmanNullCrossingTests(unittest.TestCase):
    """RR = 0.80, CI (0.60, 1.0671875), ACR = 0.25, undesirable.

      EER = 0.80·0.25 = 0.20 → RD = −0.05 → point NNTB = 20
      EER_lo = 0.60·0.25 = 0.15  → RD −0.10 (benefit) → 1/0.10 = 10
      EER_hi = 1.0671875·0.25 = 0.266796… → RD +0.016796… (harm) → 59.53
      RD CI spans 0 → Altman: NNTB 10 to ∞ to NNTH 59.53
    """

    def _ae(self):
        return ae.absolute_effect(
            measure="RR", estimate=0.8, ci=(0.6, 1.0671875), acr=0.25,
            outcome="psychotic events", outcome_desirable=False,
        )

    def test_point_estimate_still_nntb(self):
        e = self._ae()
        self.assertAlmostEqual(e.nnt, 20.0, places=4)
        self.assertEqual(e.nnt_kind, "NNTB")

    def test_crosses_null_flag_and_bounds(self):
        e = self._ae()
        self.assertTrue(e.nnt_crosses_null)
        self.assertIsNone(e.nnt_ci)
        self.assertAlmostEqual(e.nnt_benefit_bound, 10.0, places=4)
        self.assertAlmostEqual(e.nnt_harm_bound, 59.5349, places=3)

    def test_render_contains_infinity_and_both_kinds(self):
        text = ae.render_markdown(self._ae())
        self.assertIn("∞", text)
        self.assertIn("NNTB", text)
        self.assertIn("NNTH", text)

    def test_to_dict_round_trips_altman(self):
        d = self._ae().to_dict()
        self.assertTrue(d["nnt"]["crosses_null"])
        self.assertAlmostEqual(d["nnt"]["benefit_bound"], 10.0, places=4)
        self.assertAlmostEqual(d["nnt"]["harm_bound"], 59.5349, places=3)


class DesirableOutcomeTests(unittest.TestCase):
    """RR = 1.50 (response), ACR = 0.30, desirable outcome.

      EER = 0.45 → RD = +0.15 → benefit (desirable, RD>0) → NNTB = 6.667
    The same RD sign would be NNTH for an undesirable outcome — direction
    is not guessed.
    """

    def test_desirable_rd_positive_is_benefit(self):
        e = ae.absolute_effect(
            measure="RR", estimate=1.5, ci=(1.2, 1.9), acr=0.30,
            outcome="≥50% responders", outcome_desirable=True,
        )
        self.assertAlmostEqual(e.rd, 0.15, places=6)
        self.assertEqual(e.nnt_kind, "NNTB")
        self.assertAlmostEqual(e.nnt, 1 / 0.15, places=4)

    def test_same_rd_sign_flips_to_harm_when_undesirable(self):
        e = ae.absolute_effect(
            measure="RR", estimate=1.5, ci=(1.2, 1.9), acr=0.30,
            outcome="adverse events", outcome_desirable=False,
        )
        self.assertEqual(e.nnt_kind, "NNTH")
        self.assertFalse(e.benefit)
        self.assertIn("more", ae.render_markdown(e))


class EdgeCaseTests(unittest.TestCase):
    def test_no_effect_rr_one_has_no_finite_nnt(self):
        e = ae.absolute_effect(
            measure="RR", estimate=1.0, ci=(0.9, 1.1), acr=0.20,
            outcome="seizures", outcome_desirable=False,
        )
        self.assertEqual(e.rd, 0.0)
        self.assertIsNone(e.nnt)
        self.assertEqual(e.nnt_kind, "none")
        self.assertIn("not estimable", ae.render_markdown(e).lower())

    def test_eer_clamped_to_unit_interval(self):
        # RR=5 on ACR=0.30 → raw EER 1.5, clamps to 1.0.
        e = ae.absolute_effect(
            measure="RR", estimate=5.0, ci=(4.0, 6.0), acr=0.30,
            outcome="response", outcome_desirable=True,
        )
        self.assertTrue(e.eer_clamped)
        self.assertEqual(e.eer, 1.0)
        self.assertAlmostEqual(e.rd, 0.70, places=6)


class RefusalTests(unittest.TestCase):
    def test_acr_must_be_proper_probability(self):
        for bad in (0.0, 1.0, -0.1, 1.5, float("nan")):
            with self.assertRaises(ae.AbsoluteEffectError):
                ae.absolute_effect(measure="RR", estimate=0.5, ci=(0.4, 0.6),
                                   acr=bad, outcome="x", outcome_desirable=False)

    def test_measure_must_be_ratio(self):
        with self.assertRaises(ae.AbsoluteEffectError):
            ae.absolute_effect(measure="MD", estimate=0.5, ci=(0.4, 0.6),
                               acr=0.2, outcome="x", outcome_desirable=False)

    def test_estimate_and_ci_must_be_positive(self):
        with self.assertRaises(ae.AbsoluteEffectError):
            ae.absolute_effect(measure="RR", estimate=0.0, ci=(0.4, 0.6),
                               acr=0.2, outcome="x", outcome_desirable=False)
        with self.assertRaises(ae.AbsoluteEffectError):
            ae.absolute_effect(measure="RR", estimate=0.5, ci=(0.6, 0.4),
                               acr=0.2, outcome="x", outcome_desirable=False)


class FromMetaTests(unittest.TestCase):
    """absolute_from_meta consumes a §I-anchored ratio meta result."""

    def _rr_result(self):
        studies = [
            ma.binary_effect("Devinsky 2017", events_t=20, n_t=100,
                             events_c=40, n_c=100, measure="RR", pmid="28538134"),
            ma.binary_effect("Thiele 2018", events_t=25, n_t=110,
                             events_c=45, n_c=110, measure="RR", pmid="29642420"),
            ma.binary_effect("Miller 2020", events_t=18, n_t=90,
                             events_c=38, n_c=95, measure="RR", pmid="32444460"),
        ]
        return ma.meta_analyze(studies, measure="RR")

    def test_absolute_matches_pooled_display_estimate(self):
        res = self._rr_result()
        e = ae.absolute_from_meta(
            res, acr=0.40, outcome="≥1 convulsive seizure",
            outcome_desirable=False, model="random",
        )
        # EER must equal pooled-RR(display) · ACR exactly.
        self.assertAlmostEqual(e.eer, res.random_estimate_display * 0.40, places=9)
        self.assertEqual(e.measure, "RR")
        self.assertEqual(e.nnt_kind, "NNTB")  # RR<1, undesirable
        self.assertIsNotNone(e.certainty_note)
        self.assertEqual(e.confidence, res.confidence)

    def test_fixed_model_selectable(self):
        res = self._rr_result()
        e = ae.absolute_from_meta(res, acr=0.40, outcome="x",
                                  outcome_desirable=False, model="fixed")
        self.assertAlmostEqual(e.eer, res.fixed_estimate_display * 0.40, places=9)

    def test_refuses_continuous_meta(self):
        studies = [
            ma.continuous_effect("A", mean_t=1.0, sd_t=2.0, n_t=30,
                                 mean_c=2.0, sd_c=2.0, n_c=30, measure="MD", pmid="1"),
            ma.continuous_effect("B", mean_t=1.2, sd_t=2.1, n_t=30,
                                 mean_c=2.1, sd_c=2.0, n_c=30, measure="MD", pmid="2"),
            ma.continuous_effect("C", mean_t=0.9, sd_t=1.9, n_t=30,
                                 mean_c=2.0, sd_c=2.1, n_c=30, measure="MD", pmid="3"),
        ]
        res = ma.meta_analyze(studies, measure="MD")
        with self.assertRaises(ae.AbsoluteEffectError):
            ae.absolute_from_meta(res, acr=0.2, outcome="x",
                                  outcome_desirable=False)

    def test_bad_model_refused(self):
        with self.assertRaises(ae.AbsoluteEffectError):
            ae.absolute_from_meta(self._rr_result(), acr=0.2, outcome="x",
                                  outcome_desirable=False, model="bayes")


class DeterminismTests(unittest.TestCase):
    def test_identical_input_identical_dict(self):
        kw = dict(measure="OR", estimate=0.6, ci=(0.45, 0.8), acr=0.18,
                  outcome="x", outcome_desirable=False)
        self.assertEqual(
            json.dumps(ae.absolute_effect(**kw).to_dict(), sort_keys=True),
            json.dumps(ae.absolute_effect(**kw).to_dict(), sort_keys=True),
        )


class CliIntegrationTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def _spec_path(self, tmp):
        spec = {
            "measure": "RR",
            "studies": [
                {"study_id": "Devinsky 2017", "events_t": 20, "n_t": 100,
                 "events_c": 40, "n_c": 100, "pmid": "28538134"},
                {"study_id": "Thiele 2018", "events_t": 25, "n_t": 110,
                 "events_c": 45, "n_c": 110, "pmid": "29642420"},
                {"study_id": "Miller 2020", "events_t": 18, "n_t": 90,
                 "events_c": 38, "n_c": 95, "pmid": "32444460"},
            ],
        }
        p = Path(tmp) / "rr.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        return str(p)

    def test_meta_baseline_risk_markdown(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run([
                "meta", self._spec_path(tmp), "--measure", "RR",
                "--baseline-risk", "0.40", "--outcome", "convulsive seizures",
            ])
        self.assertEqual(code, 0)
        self.assertIn("NNT", out)
        self.assertIn("per 1000", out)

    def test_meta_baseline_risk_json(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run([
                "meta", self._spec_path(tmp), "--measure", "RR",
                "--baseline-risk", "0.40", "--outcome", "seizures", "--json",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("absolute_effect", payload)
        self.assertAlmostEqual(payload["absolute_effect"]["acr"], 0.40, places=6)
        self.assertEqual(payload["absolute_effect"]["measure"], "RR")

    def test_meta_baseline_risk_rejected_for_continuous(self):
        with TemporaryDirectory() as tmp:
            spec = {"measure": "MD", "studies": [
                {"study_id": "A", "mean_t": 1.0, "sd_t": 2.0, "n_t": 30,
                 "mean_c": 2.0, "sd_c": 2.0, "n_c": 30, "pmid": "1"},
                {"study_id": "B", "mean_t": 1.2, "sd_t": 2.1, "n_t": 30,
                 "mean_c": 2.1, "sd_c": 2.0, "n_c": 30, "pmid": "2"},
                {"study_id": "C", "mean_t": 0.9, "sd_t": 1.9, "n_t": 30,
                 "mean_c": 2.0, "sd_c": 2.1, "n_c": 30, "pmid": "3"},
            ]}
            p = Path(tmp) / "md.json"
            p.write_text(json.dumps(spec), encoding="utf-8")
            code, out = self._run([
                "meta", str(p), "--measure", "MD", "--baseline-risk", "0.2",
            ])
        # Non-zero exit + a clear message; absolute risk is undefined for MD.
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
