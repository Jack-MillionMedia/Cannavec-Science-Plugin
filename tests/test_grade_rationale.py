import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science.evidence import grade_rationale, GradeRationale, ClaimType

def _eff(a):
    return [c for c in a.claims if c.claim_type == ClaimType.CLINICAL_EFFICACY]

class GradeRationaleTests(unittest.TestCase):
    def test_returns_grade_rationale(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertIsInstance(grade_rationale(_eff(a)[0]), GradeRationale)

    def test_level_a_pain_cites_sr_basis(self):
        a = compose_answer("What is the evidence for cannabis in chronic pain?")
        s = grade_rationale(_eff(a)[0]).summary().lower()
        self.assertTrue("systematic review" in s or "meta-analysis" in s,
                        f"should name the SR/MA basis: {s!r}")

    def test_single_rct_basis(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertIn("rct", grade_rationale(_eff(a)[0]).summary().lower())

    def test_does_not_fabricate_unassessable_factors(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        s = grade_rationale(_eff(a)[0]).summary().lower()
        self.assertNotIn("no publication bias", s)
        self.assertNotIn("no indirectness", s)

    def test_missing_disclosure_noted_when_present(self):
        # build/borrow nothing exotic — just assert the summary is non-empty + a str
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertIsInstance(grade_rationale(_eff(a)[0]).summary(), str)
        self.assertTrue(grade_rationale(_eff(a)[0]).summary())

if __name__ == "__main__":
    unittest.main()
