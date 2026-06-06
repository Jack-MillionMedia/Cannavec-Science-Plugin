# tests/test_kb_audit_extract.py
import os
import tempfile
import unittest
from cannavec_science.kb_audit.extract import extract

_FILE = '''---
evidence_grade: "Level B"
study_counts:
  systematic_reviews: 1
---
# Epilepsy

CBD reduced convulsive seizures in Dravet syndrome (Devinsky 2017, PMID: 28538134).
The REFRACT trial is ongoing (NCT05076903).
'''


class ExtractTests(unittest.TestCase):
    def _write(self, d, text):
        p = os.path.join(d, "epilepsy.md")
        open(p, "w", encoding="utf-8").write(text)
        return p

    def test_pulls_declared_grade_and_counts(self):
        with tempfile.TemporaryDirectory() as d:
            rec = extract(self._write(d, _FILE))
            self.assertEqual(rec.declared_grade, "Level B")
            self.assertEqual(rec.study_counts["systematic_reviews"], 1)

    def test_finds_pmid_and_nct_with_types(self):
        with tempfile.TemporaryDirectory() as d:
            rec = extract(self._write(d, _FILE))
            ids = {(c.identifier, c.id_type) for c in rec.citations}
            self.assertIn(("28538134", "PMID"), ids)
            self.assertIn(("NCT05076903", "NCT"), ids)

    def test_citation_carries_its_claim_sentence(self):
        with tempfile.TemporaryDirectory() as d:
            rec = extract(self._write(d, _FILE))
            pmid = [c for c in rec.citations if c.identifier == "28538134"][0]
            self.assertIn("Dravet", pmid.claim)


if __name__ == "__main__":
    unittest.main()
