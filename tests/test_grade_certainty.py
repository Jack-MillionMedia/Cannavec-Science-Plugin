import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.evidence import EvidenceLevel as E

class CertaintyVocabulary(unittest.TestCase):
    def test_certainty_word_per_level(self):
        self.assertEqual(E.A.certainty, "High")
        self.assertEqual(E.B.certainty, "Moderate")
        self.assertEqual(E.C.certainty, "Low")
        self.assertEqual(E.D.certainty, "Very low")
        self.assertEqual(E.E.certainty, "Very low")
        self.assertEqual(E.UNSUPPORTED.certainty, "Insufficient")

    def test_display_leads_with_certainty_keeps_letter(self):
        self.assertEqual(E.A.display(), "High certainty (Level A)")
        self.assertEqual(E.B.display(), "Moderate certainty (Level B)")
        self.assertEqual(E.UNSUPPORTED.display(), "Insufficient evidence")

    def test_display_letter_optional(self):
        self.assertEqual(E.B.display(letter=False), "Moderate certainty")

    def test_value_and_rank_unchanged(self):
        self.assertEqual(E.A.value, "Level A")
        self.assertEqual(E.B.rank, 4)

if __name__ == "__main__":
    unittest.main()
