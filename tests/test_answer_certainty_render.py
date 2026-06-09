import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer

class CertaintyRender(unittest.TestCase):
    def test_markdown_leads_with_certainty_keeps_letter(self):
        md = compose_answer("CBD evidence in Dravet syndrome").to_markdown()
        self.assertIn("Moderate certainty", md)
        self.assertIn("(Level B)", md)   # secondary letter still present

    def test_json_exposes_certainty_and_rationale_keeps_grade(self):
        d = compose_answer("CBD evidence in Dravet syndrome").to_dict()
        c = d["claims"][0]
        self.assertEqual(c["certainty"], "Moderate")
        self.assertEqual(c["grade"], "Level B")
        self.assertIn("rct", c["grade_rationale"].lower())

    def test_inline_cite_uses_certainty(self):
        md = compose_answer("CBD evidence in Dravet syndrome").to_markdown()
        self.assertIn("PMID 28538134, Moderate certainty", md)

if __name__ == "__main__":
    unittest.main()
