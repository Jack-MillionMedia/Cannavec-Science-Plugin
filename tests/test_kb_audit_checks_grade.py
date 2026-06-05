# tests/test_kb_audit_checks_grade.py
import unittest
from cannavec_science.kb_audit import checks


class GradeGateTests(unittest.TestCase):
    def test_level_a_with_only_observational_is_inflated(self):
        out = checks.check_grade("Level A", {"observational_cohort": 2, "case_series": 1})
        self.assertEqual(out.verdict, "inflated")
        self.assertEqual(out.route, "quick_fix")
        self.assertIn("Level C", out.recommended_action)  # the ceiling

    def test_level_b_with_rct_is_ok(self):
        self.assertIsNone(checks.check_grade("Level B", {"feasibility_rct": 1}))

    def test_canonical_sr_floor_allows_level_a(self):
        self.assertIsNone(checks.check_grade("Level A", {"systematic_reviews": 1}))

    def test_missing_grade_no_finding(self):
        self.assertIsNone(checks.check_grade(None, {"observational_cohort": 1}))

    def test_unparseable_grade_is_flagged(self):
        out = checks.check_grade("Strong", {"observational_cohort": 1})
        self.assertEqual(out.verdict, "inflated")
        self.assertIn("unparseable", out.issue.lower())


if __name__ == "__main__":
    unittest.main()
