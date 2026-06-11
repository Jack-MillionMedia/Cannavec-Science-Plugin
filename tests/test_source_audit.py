"""The KB source-audit flywheel: every source the Cannavec MCP returns is run
through the §I/§VIII gate before the user sees it (elite vs FALSE), and primary
sources the engine's own discovery finds that the KB missed are flagged MISSING.
Both are appended to an operator improve-queue so the KB improves as it is used.

The audit LOGIC is deterministic and offline-testable — verifier and discoverer
are injected here, no network."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cannavec_science import source_audit as sa


def _verifier_from(table):
    """id -> (verdict, reason) from a dict; default PASS."""
    return lambda ident: table.get(ident, ("PASS", "ok"))


class AuditSplitsEliteFromFalse(unittest.TestCase):
    def test_pass_is_elite_fail_is_false_networkerror_is_unverified(self):
        table = {
            "28538134": ("PASS", "real"),
            "99999999": ("FAIL", "not found upstream (fabricated?)"),
            "32060308": ("FAIL", "retracted"),
            "40000000": ("UNVERIFIED", "could not reach upstream"),
        }
        with tempfile.TemporaryDirectory() as d:
            res = sa.audit_sources(
                "cbd epilepsy", list(table.keys()),
                verifier=_verifier_from(table),
                discoverer=lambda q: [],            # no missing
                store_dir=d, now="2026-06-10T00:00:00+00:00",
            )
        self.assertEqual([s.identifier for s in res.elite], ["28538134"])
        self.assertEqual(sorted(s.identifier for s in res.failed), ["32060308", "99999999"])
        self.assertEqual([s.identifier for s in res.unverified], ["40000000"])

    def test_duplicate_kb_ids_are_audited_once(self):
        with tempfile.TemporaryDirectory() as d:
            res = sa.audit_sources(
                "q", ["PMID:123", "123", "123"],
                verifier=_verifier_from({"123": ("PASS", "ok")}),
                discoverer=lambda q: [], store_dir=d,
            )
        self.assertEqual(len(res.elite), 1)


class MissingDetection(unittest.TestCase):
    def test_engine_found_but_kb_missed_is_missing(self):
        with tempfile.TemporaryDirectory() as d:
            res = sa.audit_sources(
                "thc tachycardia", ["111", "222"],
                verifier=_verifier_from({}),                      # all PASS
                discoverer=lambda q: ["111", "333", "444"],       # 333,444 not in KB
                store_dir=d,
            )
        self.assertEqual(sorted(res.missing), ["333", "444"])

    def test_missing_is_case_insensitive_against_kb(self):
        with tempfile.TemporaryDirectory() as d:
            res = sa.audit_sources(
                "q", ["10.1/AbC"],
                verifier=_verifier_from({}),
                discoverer=lambda q: ["10.1/abc", "10.2/new"],
                store_dir=d,
            )
        self.assertEqual(res.missing, ("10.2/new",))


class ImproveQueueFlywheel(unittest.TestCase):
    def test_false_and_missing_are_logged_clean_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            # clean run (all PASS, no missing) → nothing logged
            clean = sa.audit_sources(
                "q1", ["123"], verifier=_verifier_from({"123": ("PASS", "ok")}),
                discoverer=lambda q: ["123"], store_dir=d,
            )
            self.assertIsNone(clean.logged_path)
            # a run with a false + a missing → one queue line appended
            dirty = sa.audit_sources(
                "q2", ["999"], verifier=_verifier_from({"999": ("FAIL", "not found")}),
                discoverer=lambda q: ["777"], store_dir=d,
                now="2026-06-10T12:00:00+00:00",
            )
            self.assertIsNotNone(dirty.logged_path)
            lines = Path(dirty.logged_path).read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["query"], "q2")
            self.assertEqual([s["identifier"] for s in entry["false_sources"]], ["999"])
            self.assertEqual(entry["missing_sources"], ["777"])
            self.assertEqual(entry["ts"], "2026-06-10T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
