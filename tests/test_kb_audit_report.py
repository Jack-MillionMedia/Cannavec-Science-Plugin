# tests/test_kb_audit_report.py
import json
import unittest
from cannavec_science.kb_audit.model import Finding, FileVerdict
from cannavec_science.kb_audit.report import render


def _v(path, routing, status, priority, findings=()):
    return FileVerdict(path=path, in_scope=True, routing=routing, status=status,
                       priority=priority,
                       credibility={"citations_clean": 0, "citations_total": 0, "open_findings": len(findings)},
                       findings=findings)


class ReportTests(unittest.TestCase):
    def test_ready_quickwins_sorted_before_improve(self):
        verdicts = [_v("improve.md", "IMPROVE", "FAIL", 1),
                    _v("ready.md", "READY", "FLAG", 0)]
        md, _ = render(verdicts)
        self.assertLess(md.index("ready.md"), md.index("improve.md"))

    def test_json_is_machine_readable_queue(self):
        f = Finding("citation", "i", "e", "retracted", "fix", "improve_agent")
        _, js = render([_v("a.md", "IMPROVE", "FAIL", 1, (f,))])
        data = json.loads(js)
        self.assertEqual(data["files"][0]["findings"][0]["route"], "improve_agent")
        self.assertIn("summary", data)


if __name__ == "__main__":
    unittest.main()
