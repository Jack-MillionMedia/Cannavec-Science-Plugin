"""CLI tests for the curation flywheel subcommands.

Every test redirects the curation stores to a tmp dir via
``CANNAVEC_CURATION_DIR`` so the shipped ``data/`` is never touched, and runs
fully offline (the index pre-filter needs no network; promotions are seeded
through the library API with injected fixtures).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import demand, flywheel as fw  # noqa: E402
from cannavec_science.__main__ import main  # noqa: E402
from cannavec_science.ranker import Candidate  # noqa: E402


def _esummary(pmid: str) -> str:
    return json.dumps({"result": {"uids": [pmid], pmid: {
        "uid": pmid, "pubdate": "2019 Jan 1", "source": "N Engl J Med",
        "authors": [{"name": "Devinsky O", "authtype": "Author"}],
        "title": "Trial of Cannabidiol for Seizures",
        "pubtype": ["Journal Article", "Randomized Controlled Trial"],
    }}})


_ABSTRACT = ("In this randomized controlled trial, cannabidiol reduced the frequency "
             "of convulsive seizures compared with placebo.")
_CLAIM = "Cannabidiol reduced convulsive seizure frequency versus placebo in an RCT."


def _run(argv: list[str]) -> tuple[int, str]:
    """Run the CLI, returning ``(exit_code, stdout)``."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


class CurateCLITest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("CANNAVEC_CURATION_DIR")
        os.environ["CANNAVEC_CURATION_DIR"] = self._tmp.name
        self.dir = self._tmp.name

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("CANNAVEC_CURATION_DIR", None)
        else:
            os.environ["CANNAVEC_CURATION_DIR"] = self._prev
        self._tmp.cleanup()

    def _seed_basic(self, ident="30000001"):
        c = Candidate(identifier=ident, title="Cannabidiol for seizures",
                      abstract=_ABSTRACT, study_types=("Randomized Controlled Trial",),
                      topic="epilepsy")
        g = fw.gate(c, claim_text=_CLAIM, abstract=_ABSTRACT,
                    verify_fetcher=lambda u: _esummary(ident))
        return fw.stage(c, g, store_dir=self.dir)

    # ── scan ───────────────────────────────────────────────────────────────
    def test_scan_index_offline_stages_needs_expert(self) -> None:
        code, _ = _run(["curate-scan", "cannabis inflammatory bowel disease",
                        "--index-topic", "Guts", "--max", "4"])
        self.assertEqual(code, 0)
        pending = fw.queue(store_dir=self.dir)
        self.assertGreaterEqual(len(pending), 1)
        # Offline, un-verifiable, abstract-less index rows are correctly held.
        self.assertTrue(all(r["lane"] == "needs_expert" for r in pending))

    def test_scan_json_emits_report(self) -> None:
        code, out = _run(["curate-scan", "cannabis crohn colitis",
                          "--index-topic", "Guts", "--max", "2", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("candidates", payload)
        self.assertIn("staged", payload)

    # ── queue + stats ────────────────────────────────────────────────────────
    def test_queue_and_stats(self) -> None:
        self._seed_basic()
        code, out = _run(["curate-queue", "--lane", "basic_approvable"])
        self.assertEqual(code, 0)
        self.assertIn("30000001", out)

        code, out = _run(["curate-stats", "--json"])
        self.assertEqual(code, 0)
        stats = json.loads(out)
        self.assertEqual(stats["queue_pending_basic_approvable"], 1)
        self.assertEqual(stats["target"], 1500)

    # ── apply / reject / revoke ──────────────────────────────────────────────
    def test_apply_promotes_basic(self) -> None:
        self._seed_basic()
        code, out = _run(["curate-apply", "--id", "30000001",
                          "--approver", "curator@cannavec", "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])
        self.assertEqual(len(fw.verified_sources(store_dir=self.dir)), 1)

    def test_apply_unknown_identifier_exits_nonzero(self) -> None:
        code, _ = _run(["curate-apply", "--id", "00000000", "--approver", "x"])
        self.assertEqual(code, 1)

    def test_apply_reject_path(self) -> None:
        self._seed_basic()
        code, _ = _run(["curate-apply", "--id", "30000001", "--approver", "c",
                        "--reject", "--reason", "off-topic"])
        self.assertEqual(code, 0)
        self.assertEqual(fw.queue(store_dir=self.dir), [])
        self.assertEqual(len(fw.queue(status="rejected", store_dir=self.dir)), 1)

    def test_apply_requires_approver_argparse(self) -> None:
        # --approver is argparse-required → SystemExit(2) before the handler.
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                main(["curate-apply", "--id", "30000001"])

    # ── demand-report ────────────────────────────────────────────────────────
    def test_demand_report(self) -> None:
        demand.record_demand("fibromyalgia cannabis", n_curated_claims=0,
                             store_dir=self.dir)
        demand.record_demand("crohn's cannabidiol", n_curated_claims=0,
                             store_dir=self.dir)
        code, out = _run(["demand-report", "--json"])
        self.assertEqual(code, 0)
        topics = [t["topic"] for t in json.loads(out)]
        self.assertIn("fibromyalgia", topics)
        self.assertIn("ibd", topics)


if __name__ == "__main__":
    unittest.main()
