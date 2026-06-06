# tests/test_kb_audit_verdict.py
import unittest
from cannavec_science.kb_audit.model import Citation, FileRecord
from cannavec_science.kb_audit.verdict import audit_record


def _verify(name):
    class _R:
        def __init__(self): self.verdict = type("V", (), {"name": name})
    return lambda ident, id_type: _R()


class VerdictTests(unittest.TestCase):
    def _rec(self, **kw):
        base = dict(path="f.md", in_scope=True, declared_grade=None, study_counts={}, citations=())
        base.update(kw); return FileRecord(**base)

    def test_clean_file_passes(self):
        rec = self._rec(citations=(Citation("28538134", "PMID", "c"),))
        v = audit_record(rec, verify_fn=_verify("MATCH"), retracted_fn=lambda **k: None,
                         abstract_fn=lambda p: None)
        self.assertEqual(v.routing, "PASS")
        self.assertEqual(v.status, "PASS")
        self.assertEqual(v.credibility["citations_clean"], 1)

    def test_retracted_file_is_improve_fail(self):
        rec = self._rec(citations=(Citation("32060308", "PMID", "c"),))
        v = audit_record(rec, verify_fn=_verify("MATCH"), retracted_fn=lambda **k: object(),
                         abstract_fn=lambda p: None)
        self.assertEqual(v.routing, "IMPROVE")
        self.assertEqual(v.status, "FAIL")
        self.assertEqual(v.priority, 1)

    def test_grade_only_inflation_is_ready_quickfix(self):
        rec = self._rec(declared_grade="Level A", study_counts={"observational_cohort": 1})
        v = audit_record(rec, verify_fn=_verify("MATCH"), retracted_fn=lambda **k: None,
                         abstract_fn=lambda p: None)
        self.assertEqual(v.routing, "READY")
        self.assertEqual(v.status, "FLAG")
        self.assertEqual(v.priority, 0)

    def test_parse_error_file_is_flagged_not_passed(self):
        # An unparseable file must never be a silent PASS (spec §Reliability).
        rec = self._rec(parse_error="'utf-8' codec can't decode byte")
        v = audit_record(rec, verify_fn=_verify("MATCH"), retracted_fn=lambda **k: None,
                         abstract_fn=lambda p: None)
        self.assertEqual(v.routing, "IMPROVE")
        self.assertEqual(v.status, "FLAG")
        self.assertEqual(len(v.findings), 1)
        self.assertIn("could not be parsed", v.findings[0].issue)


if __name__ == "__main__":
    unittest.main()
