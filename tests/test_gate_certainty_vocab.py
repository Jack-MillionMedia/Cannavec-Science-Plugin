import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science.export import grade_inflation_failures, export_provenance

class CertaintyGateVocab(unittest.TestCase):
    def test_inflated_certainty_word_is_flagged(self):
        a = compose_answer("CBD evidence in Dravet syndrome")  # 28538134 -> Level B (Moderate)
        fails = grade_inflation_failures(a, "PMID 28538134, High certainty")
        self.assertIn("PMID:28538134", {f.identifier for f in fails})

    def test_correct_certainty_word_not_flagged(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertEqual(grade_inflation_failures(a, "PMID 28538134, Moderate certainty (Level B)"), ())

    def test_lower_certainty_word_not_flagged(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        # 'Low'/'Very low' are weaker than Moderate -> not inflation
        self.assertEqual(grade_inflation_failures(a, "PMID 28538134, Low certainty"), ())

    def test_very_low_not_misread_as_low_rank(self):
        # 'Very low certainty' must NOT produce a rank-3 'Low' hit that flags a
        # citation; bind it to the graded Dravet cite and confirm no inflation.
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertEqual(grade_inflation_failures(a, "PMID 28538134, Very low certainty"), ())

if __name__ == "__main__":
    unittest.main()
