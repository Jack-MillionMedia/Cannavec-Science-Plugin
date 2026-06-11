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


class GroundingScores(unittest.TestCase):
    """'Plugin scores answer quality' — honest precision/coverage over the audit
    counts, so the model can gate on how credible the KB's sources were."""

    def test_precision_and_coverage_from_counts(self):
        table = {"1": ("PASS", "ok"), "2": ("PASS", "ok"), "3": ("PASS", "ok"),
                 "8": ("FAIL", "not found"), "9": ("FAIL", "retracted")}
        with tempfile.TemporaryDirectory() as d:
            res = sa.audit_sources(
                "q", list(table.keys()), verifier=_verifier_from(table),
                discoverer=lambda q: ["1", "100", "200", "300"],  # 100/200/300 missing
                store_dir=d)
        sc = res.grounding_scores()
        self.assertEqual((sc["elite"], sc["false"], sc["missing"]), (3, 2, 3))
        self.assertEqual(sc["precision"], 0.6)   # 3 elite / (3 elite + 2 false)
        self.assertEqual(sc["coverage"], 0.5)    # 3 elite / (3 elite + 3 missing)

    def test_none_not_zero_when_nothing_verifiable(self):
        # KB returned only a network-unverified source: not the KB's fault, so the
        # score is undefined (None), never a misleading 0.0.
        with tempfile.TemporaryDirectory() as d:
            res = sa.audit_sources(
                "q", ["5"], verifier=_verifier_from({"5": ("UNVERIFIED", "net")}),
                discoverer=lambda q: [], store_dir=d)
        sc = res.grounding_scores()
        self.assertIsNone(sc["precision"])
        self.assertIsNone(sc["coverage"])


class SummarizeImproveQueue(unittest.TestCase):
    """The operator review tail of the flywheel: rank logged gaps by how often
    they recur (highest-impact first), deterministically."""

    def _write(self, d, rows):
        p = Path(d) / "improve_queue.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return p

    def test_ranks_missing_false_and_queries_by_frequency_desc(self):
        rows = [
            {"ts": "t1", "query": "cbd epilepsy",
             "false_sources": [{"identifier": "999", "reason": "not found"}],
             "missing_sources": ["NCT01", "NCT02"]},
            {"ts": "t2", "query": "cbd epilepsy",
             "false_sources": [], "missing_sources": ["NCT01"]},
            {"ts": "t3", "query": "thc pain",
             "false_sources": [{"identifier": "999", "reason": "not found"}],
             "missing_sources": ["NCT03"]},
        ]
        with tempfile.TemporaryDirectory() as d:
            self._write(d, rows)
            s = sa.summarize_improve_queue(store_dir=d)
        self.assertEqual(s.entries, 3)
        # NCT01 twice → first; ties broken alphabetically → stable, no flakes
        self.assertEqual(s.missing_by_id[0], ("NCT01", 2))
        self.assertEqual([m[0] for m in s.missing_by_id], ["NCT01", "NCT02", "NCT03"])
        self.assertEqual(s.false_by_id[0], ("999", 2, "not found"))
        self.assertEqual(s.queries_by_count[0], ("cbd epilepsy", 2))

    def test_missing_file_is_empty_summary_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            s = sa.summarize_improve_queue(store_dir=d)
        self.assertEqual(s.entries, 0)
        self.assertEqual(s.missing_by_id, ())
        self.assertEqual(s.false_by_id, ())

    def test_malformed_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "improve_queue.jsonl"
            p.write_text('{"query":"q","false_sources":[],"missing_sources":["A"]}\n'
                         'not json at all\n\n', encoding="utf-8")
            s = sa.summarize_improve_queue(store_dir=d)
        self.assertEqual(s.entries, 1)
        self.assertEqual(s.missing_by_id, (("A", 1),))


if __name__ == "__main__":
    unittest.main()
