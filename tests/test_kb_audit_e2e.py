import os
import unittest
from cannavec_science.kb_audit.run import audit_path

_FX = os.path.join(os.path.dirname(__file__), "fixtures", "kb_audit")


def _stub_verify(ident, id_type):
    # offline engine stand-in keyed on the fixture identifiers
    name = "NOT_FOUND" if ident == "99999999" else "MATCH"
    class _R: pass
    r = _R(); r.verdict = type("V", (), {"name": name}); return r


def _stub_retracted(**kw):
    return object() if kw.get("pmid") == "32060308" else None


class E2ETests(unittest.TestCase):
    def setUp(self):
        self.verdicts = {os.path.basename(v.path): v for v in
                         audit_path(_FX, verify_fn=_stub_verify, retracted_fn=_stub_retracted,
                                    abstract_fn=lambda p: None)}

    def test_clean_passes(self):
        self.assertEqual(self.verdicts["clean.md"].routing, "PASS")

    def test_fabricated_fails_to_improve(self):
        v = self.verdicts["fabricated.md"]
        self.assertEqual(v.status, "FAIL")
        self.assertEqual(v.routing, "IMPROVE")

    def test_retracted_fails(self):
        self.assertEqual(self.verdicts["retracted.md"].status, "FAIL")

    def test_inflated_is_ready_quickfix(self):
        self.assertEqual(self.verdicts["inflated.md"].routing, "READY")

    def test_non_science_skipped(self):
        self.assertNotIn("x.md", self.verdicts)

    def test_identifiers_verified_once_per_corpus(self):
        # clean.md and inflated.md both cite PMID 28538134 — dedupe verifies it once.
        calls = {}

        def counting_verify(ident, id_type):
            calls[ident] = calls.get(ident, 0) + 1
            return _stub_verify(ident, id_type)

        audit_path(_FX, verify_fn=counting_verify, retracted_fn=_stub_retracted,
                   abstract_fn=lambda p: None)
        self.assertEqual(calls["28538134"], 1)


if __name__ == "__main__":
    unittest.main()
