import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer

# The GRADE *value* (letter) per curated question must be EXACTLY these. Spec 035
# (GRADE-certainty wording + per-source rationale) is display-only; this audit
# fails loudly if any grade VALUE silently shifts.
EXPECTED = {
    "CBD evidence in Dravet syndrome": "Level B",
    "What is the evidence for cannabis in chronic pain?": "Level A",
    "cannabis for chemotherapy-induced nausea and vomiting": "Level B",
    "cannabinoids for MS spasticity": "Level B",
}

class GradeValueUnchanged(unittest.TestCase):
    def test_letters_unchanged(self):
        for q, want in EXPECTED.items():
            a = compose_answer(q)
            self.assertEqual(a.evidence_summary.highest_grade.value, want, q)

if __name__ == "__main__":
    unittest.main()
