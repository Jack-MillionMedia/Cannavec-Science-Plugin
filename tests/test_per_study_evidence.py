import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science.export import export_provenance, assert_citation_lossless

class PerStudyEvidence(unittest.TestCase):
    def test_every_graded_citation_shows_its_certainty_and_letter(self):
        a = compose_answer("What is the evidence for cannabis in chronic pain?")
        md = a.to_markdown()
        refs = md.split("## Citations", 1)[-1]
        self.assertIn("certainty", refs.lower())
        for atom in (x for x in export_provenance(a) if x.grade):
            self.assertIn(atom.raw_id, refs)
            self.assertIn(atom.grade, refs)  # canonical letter still present (gate floor)

    def test_floor_still_holds_on_canonical_markdown(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertTrue(assert_citation_lossless(a, a.to_markdown()).ok)

if __name__ == "__main__":
    unittest.main()
