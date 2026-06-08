import sys, re, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science import pdf_export

# Internal framing that must never appear in expert-facing output. Targets the
# specific markers (not a bare "§", which could legitimately appear in a statute
# citation) — adjust ONLY if you hit a genuine false-positive from real content.
BANNED = re.compile(
    r"Constitution|§\s?[IVXLC]+\b|\bM[0-9]\b|scaffolding to reason|"
    r"not the intelligence itself|the intelligence itself|"
    r"Verify each identifier before citing", re.IGNORECASE)

QUESTIONS = [
    "CBD evidence in Dravet syndrome",
    "What is the evidence for cannabis in chronic pain?",
    "cannabis for chemotherapy-induced nausea and vomiting",
    "cannabinoids for MS spasticity",
    "cannabis for breast cancer",
    "How much CBD should I take for my anxiety every day?",
    "CBG cannabigerol monograph",
]

class NoSystemLanguageInOutput(unittest.TestCase):
    def test_markdown_and_pdf_have_no_internal_framing(self):
        for q in QUESTIONS:
            a = compose_answer(q)
            for surface, text in (("markdown", a.to_markdown()),
                                  ("pdf-html", pdf_export.render_html(a))):
                m = BANNED.search(text)
                self.assertIsNone(m, f"internal/system language in {surface} for {q!r}: {m.group(0) if m else ''} … context: {text[max(0,(m.start()-40)):m.start()+40] if m else ''!r}")

if __name__ == "__main__":
    unittest.main()
