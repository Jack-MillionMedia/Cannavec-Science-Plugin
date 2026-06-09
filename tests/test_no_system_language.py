import sys, re, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science import pdf_export, live

# Internal framing that must never appear in expert-facing output. Targets the
# specific markers (not a bare "§", which could legitimately appear in a statute
# citation) — adjust ONLY if you hit a genuine false-positive from real content.
# ``\bConstitution\b`` is word-bounded so it catches "Constitution §IX" but NOT
# legitimate chemistry like "constitutional isomer" in a compound monograph.
BANNED = re.compile(
    r"\bConstitution\b|§\s?[IVXLC]+\b|\bM[0-9]\b|scaffolding to reason|"
    r"not the intelligence itself|the intelligence itself|"
    r"Verify each identifier before citing", re.IGNORECASE)


class _FakeHit:
    def __init__(self, **d): self.__dict__.update(d)
    def to_dict(self): return dict(self.__dict__)

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

    def test_live_augmented_output_has_no_internal_framing(self):
        # The Phase-2 live tier (findings, snippet, synthesis prose, provenance
        # line) must also be free of internal/system framing.
        def _runner(query, since, n):
            return [_FakeHit(
                pmid="39000099",
                title="Cannabidiol for chronic pain: a randomized controlled trial",
                year="2023", retraction_status="clean", journal="PAIN",
                pubtypes=("Randomized Controlled Trial",),
                abstract="Cannabidiol reduced pain scores versus placebo in this trial.",
            )][:n]
        a = compose_answer("What is the evidence for cannabis in chronic pain?")
        live.augment_answer(a, sources=["pubmed"], runners={"pubmed": _runner})
        self.assertTrue(a.live_findings, "test setup: expected a live finding")
        for surface, text in (("markdown", a.to_markdown()),
                              ("pdf-html", pdf_export.render_html(a))):
            m = BANNED.search(text)
            self.assertIsNone(
                m, f"internal/system language in live-augmented {surface}: "
                   f"{m.group(0) if m else ''} … "
                   f"{text[max(0,(m.start()-40)):m.start()+40] if m else ''!r}")

if __name__ == "__main__":
    unittest.main()
