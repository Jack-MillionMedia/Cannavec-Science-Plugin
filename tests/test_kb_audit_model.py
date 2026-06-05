import unittest
from cannavec_science.kb_audit.model import Citation, FileRecord, Finding, FileVerdict


class ModelTests(unittest.TestCase):
    def test_citation_is_frozen_and_typed(self):
        c = Citation(identifier="28538134", id_type="PMID", claim="CBD reduces seizures.")
        self.assertEqual(c.identifier, "28538134")
        with self.assertRaises(Exception):
            c.identifier = "x"  # frozen

    def test_verdict_carries_routing_and_findings(self):
        f = Finding(gate="citation", issue="retracted", evidence="local registry",
                    verdict="retracted", recommended_action="find superseder",
                    route="improve_agent")
        v = FileVerdict(path="a.md", in_scope=True, routing="IMPROVE", status="FAIL",
                        priority=1, credibility={"citations_clean": 0, "citations_total": 1,
                        "open_findings": 1}, findings=(f,))
        self.assertEqual(v.findings[0].route, "improve_agent")
        self.assertEqual(v.routing, "IMPROVE")


if __name__ == "__main__":
    unittest.main()
