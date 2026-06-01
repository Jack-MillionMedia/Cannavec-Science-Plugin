"""Tests for the Summary-of-Findings composer + answer --sof weave (spec 017)."""

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import sof
from cannavec_science import meta_analysis as ma


def _rr_outcome(**over):
    o = {
        "outcome": "≥50% seizure reduction",
        "measure": "RR",
        "studies": [
            {"study_id": "Devinsky 2017", "events_t": 20, "n_t": 100,
             "events_c": 40, "n_c": 100, "pmid": "28538134"},
            {"study_id": "Thiele 2018", "events_t": 25, "n_t": 110,
             "events_c": 45, "n_c": 110, "pmid": "29642420"},
            {"study_id": "Miller 2020", "events_t": 18, "n_t": 90,
             "events_c": 38, "n_c": 95, "pmid": "32444460"},
        ],
        "baseline": {"risk": 0.40, "label": "pooled placebo arms",
                     "pmid": "28538134"},
        "outcome_desirable": False,
    }
    o.update(over)
    return o


class EffectsFromRecordsParityTests(unittest.TestCase):
    """The shared parser must match direct binary_effect construction."""

    def test_binary_records_match_direct(self):
        recs = _rr_outcome()["studies"]
        got = ma.effects_from_records(recs, measure="RR")
        direct = ma.binary_effect("Devinsky 2017", events_t=20, n_t=100,
                                  events_c=40, n_c=100, measure="RR", pmid="28538134")
        self.assertEqual(len(got), 3)
        self.assertAlmostEqual(got[0].yi, direct.yi, places=12)
        self.assertEqual(got[0].identifier, "PMID:28538134")

    def test_missing_field_raises_keyerror(self):
        with self.assertRaises(KeyError):
            ma.effects_from_records([{"study_id": "x", "events_t": 1, "n_t": 10,
                                      "pmid": "1"}], measure="RR")


class BuildSofTests(unittest.TestCase):
    def test_single_rr_outcome_has_certainty_and_absolute(self):
        s = sof.build_sof({"outcomes": [_rr_outcome()]})
        self.assertEqual(len(s.rows), 1)
        row = s.rows[0]
        self.assertEqual(row.result.measure, "RR")
        self.assertEqual(row.certainty.grade_word, "High")     # consistent, CI excl. null
        self.assertIsNotNone(row.absolute)
        self.assertEqual(row.absolute.nnt_kind, "NNTB")
        # absolute EER must equal pooled display RR × ACR
        self.assertAlmostEqual(
            row.absolute.eer, row.result.random_estimate_display * 0.40, places=9)

    def test_outcome_without_baseline_has_no_absolute(self):
        o = _rr_outcome()
        o.pop("baseline")
        row = sof.build_sof({"outcomes": [o]}).rows[0]
        self.assertIsNone(row.absolute)

    def test_continuous_outcome_certainty_but_no_absolute(self):
        o = {
            "outcome": "pain VAS (0-100)",
            "measure": "MD",
            "studies": [
                {"study_id": "A", "mean_t": 30, "sd_t": 18, "n_t": 60,
                 "mean_c": 42, "sd_c": 19, "n_c": 60, "pmid": "1"},
                {"study_id": "B", "mean_t": 28, "sd_t": 17, "n_t": 55,
                 "mean_c": 40, "sd_c": 18, "n_c": 58, "pmid": "2"},
                {"study_id": "C", "mean_t": 33, "sd_t": 20, "n_t": 50,
                 "mean_c": 41, "sd_c": 19, "n_c": 52, "pmid": "3"},
            ],
            "baseline": {"risk": 0.4},   # ignored: MD has no risk difference
        }
        row = sof.build_sof({"outcomes": [o]}).rows[0]
        self.assertEqual(row.result.measure, "MD")
        self.assertIsNone(row.absolute)
        self.assertIsNotNone(row.certainty)

    def test_two_outcomes_preserve_order(self):
        s = sof.build_sof({"outcomes": [
            _rr_outcome(outcome="seizures"),
            _rr_outcome(outcome="responders"),
        ]})
        self.assertEqual([r.outcome for r in s.rows], ["seizures", "responders"])

    def test_reviewer_domains_flow_through(self):
        row = sof.build_sof({"outcomes": [
            _rr_outcome(risk_of_bias="serious"),
        ]}).rows[0]
        rob = {d.name: d for d in row.certainty.domains}["Risk of bias"]
        self.assertEqual(rob.steps, 1)
        self.assertEqual(row.certainty.grade_word, "Moderate")


class RefusalTests(unittest.TestCase):
    def test_study_without_identifier_refuses(self):
        o = _rr_outcome()
        o["studies"][0].pop("pmid")               # strip §I identifier
        with self.assertRaises(sof.SoFError):
            sof.build_sof({"outcomes": [o]})

    def test_empty_outcomes_refuses(self):
        with self.assertRaises(sof.SoFError):
            sof.build_sof({"outcomes": []})

    def test_bad_baseline_refuses(self):
        with self.assertRaises(sof.SoFError):
            sof.build_sof({"outcomes": [_rr_outcome(baseline={"risk": 1.5})]})


class RenderTests(unittest.TestCase):
    def test_render_has_all_sof_columns(self):
        text = sof.render_markdown(sof.build_sof({"outcomes": [_rr_outcome()]}))
        self.assertIn("## Summary of Findings", text)
        self.assertIn("Relative effect (random)", text)
        self.assertIn("GRADE certainty of evidence", text)
        self.assertIn("⊕", text)
        self.assertIn("NNT", text)

    def test_deterministic(self):
        a = sof.build_sof({"outcomes": [_rr_outcome()]}).to_dict()
        b = sof.build_sof({"outcomes": [_rr_outcome()]}).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))


class CliWeaveTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def _sidecar(self, tmp):
        p = Path(tmp) / "sof.json"
        p.write_text(json.dumps({"outcomes": [_rr_outcome()]}), encoding="utf-8")
        return str(p)

    def test_answer_sof_markdown(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run([
                "answer", "CBD evidence in Dravet syndrome",
                "--sof", self._sidecar(tmp),
            ])
        self.assertEqual(code, 0)
        self.assertIn("Summary of Findings", out)
        self.assertIn("⊕", out)
        self.assertIn("NNTB", out)

    def test_answer_sof_json(self):
        with TemporaryDirectory() as tmp:
            code, out = self._run([
                "answer", "CBD evidence in Dravet syndrome",
                "--sof", self._sidecar(tmp), "--json",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("summary_of_findings", payload.get("scaffolders", {}))
        rows = payload["scaffolders"]["summary_of_findings"]["rows"]
        self.assertEqual(rows[0]["certainty"]["grade_word"], "High")

    def test_answer_sof_bad_file_nonzero(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{ not json", encoding="utf-8")
            code, _ = self._run([
                "answer", "CBD evidence in Dravet syndrome", "--sof", str(bad),
            ])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
