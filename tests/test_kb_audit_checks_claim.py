# tests/test_kb_audit_checks_claim.py
import unittest
from cannavec_science.kb_audit.model import Citation
from cannavec_science.kb_audit import checks


class ClaimGateTests(unittest.TestCase):
    def test_contradiction_is_fail(self):
        c = Citation("1", "PMID", "CBD increases seizure frequency in Dravet syndrome.")
        # abstract asserts the opposite direction
        abstract = "Cannabidiol reduced convulsive seizure frequency in Dravet syndrome."
        out = checks.check_claim(c, abstract_fn=lambda pmid: abstract)
        self.assertEqual(out.verdict, "contradiction")
        self.assertEqual(out.route, "improve_agent")

    def test_no_abstract_is_inconclusive_no_finding(self):
        c = Citation("1", "PMID", "Some claim.")
        out = checks.check_claim(c, abstract_fn=lambda pmid: None)
        self.assertIsNone(out)

    def test_non_pmid_citation_skipped(self):
        c = Citation("NCT05076903", "NCT", "A claim.")
        self.assertIsNone(checks.check_claim(c, abstract_fn=lambda pmid: "text"))


if __name__ == "__main__":
    unittest.main()
