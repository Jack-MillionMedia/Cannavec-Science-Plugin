# tests/test_kb_audit_frontmatter.py
import unittest
from cannavec_science.kb_audit.frontmatter import parse_frontmatter

_DOC = '''---
id: epilepsy
evidence_grade: "Level B"
evidence_grade_notes: >
  A long block scalar that should be ignored
  across multiple lines.
study_counts:
  total: 17
  systematic_reviews: 1
  observational_cohort: 1
tags:
  - epilepsy
  - CBD
needs_review: false
---
# Body starts here
Some text.
'''


class FrontmatterTests(unittest.TestCase):
    def test_extracts_scalar_grade(self):
        fm = parse_frontmatter(_DOC)
        self.assertEqual(fm["evidence_grade"], "Level B")  # quotes stripped

    def test_extracts_nested_int_map(self):
        fm = parse_frontmatter(_DOC)
        self.assertEqual(fm["study_counts"]["systematic_reviews"], 1)
        self.assertEqual(fm["study_counts"]["total"], 17)

    def test_block_scalar_and_lists_are_not_int_polluted(self):
        fm = parse_frontmatter(_DOC)
        self.assertNotIn("epilepsy", fm.get("study_counts", {}))

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(parse_frontmatter("# just a body\n"), {})


if __name__ == "__main__":
    unittest.main()
