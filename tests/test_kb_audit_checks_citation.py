# tests/test_kb_audit_checks_citation.py
import unittest
from cannavec_science.kb_audit.model import Citation
from cannavec_science.kb_audit import checks


def _fake_verify(verdict):
    # stand-in for an engine verify result: object with .verdict.name
    class _R:
        def __init__(self, name): self.verdict = type("V", (), {"name": name})
    return lambda ident, id_type: _R(verdict)


class CitationGateTests(unittest.TestCase):
    def test_clean_pmid_no_finding(self):
        c = Citation("28538134", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("MATCH"),
                                    retracted_fn=lambda **k: None)
        self.assertIsNone(out)

    def test_retracted_is_fail_finding(self):
        c = Citation("32060308", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("MATCH"),
                                    retracted_fn=lambda **k: object())  # registry hit
        self.assertEqual(out.verdict, "retracted")
        self.assertEqual(out.route, "improve_agent")

    def test_not_found_is_fabricated(self):
        c = Citation("99999999", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("NOT_FOUND"),
                                    retracted_fn=lambda **k: None)
        self.assertEqual(out.verdict, "fabricated")

    def test_network_error_is_inconclusive(self):
        c = Citation("28538134", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("NETWORK_ERROR"),
                                    retracted_fn=lambda **k: None)
        self.assertEqual(out.verdict, "inconclusive")


if __name__ == "__main__":
    unittest.main()
