import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science import pdf_export as P

class PdfCertainty(unittest.TestCase):
    def test_badges_show_certainty_and_letter(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        doc = P.render_html(a)
        # Pin the actual badge HTML: certainty word + canonical letter, colour
        # class keyed off the letter (gb). Locks the gate-floor letter too.
        self.assertIn('class="grade gb">Moderate certainty (Level B)</span>', doc)
        P.assert_render_faithful(a, doc)

    def test_claim_shows_grade_rationale(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        doc = P.render_html(a)
        # Pin the grade-why div specifically (not incidental "RCT" in prose).
        self.assertIn('grade-why">Why this grade:', doc)
        self.assertIn("single adequately-powered RCT", doc)

    def test_curated_set_all_faithful(self):
        for q in ("What is the evidence for cannabis in chronic pain?",
                  "cannabinoids for MS spasticity",
                  "cannabis for chemotherapy-induced nausea and vomiting"):
            a = compose_answer(q)
            P.assert_render_faithful(a, P.render_html(a))

if __name__ == "__main__":
    unittest.main()
