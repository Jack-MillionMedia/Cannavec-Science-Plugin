"""The /cv:pdf renderer — a citation-lossless, non-inflating transform of the
verified Answer into a polished evidence brief.

Pins the §XI/§VII guarantees the flagship output skill rests on:
  * every primary-source identifier and GRADE label survives into the HTML,
  * no graded citation is rendered above its assigned grade, and an ungraded
    reference-context citation shows NO grade,
  * a tampered render (dropped id / softened or inflated GRADE) is REFUSED,
  * refusal and uncurated-indication answers render an honest artifact that
    fabricates no evidence,
  * the HTML is self-contained (no external scripts/stylesheets), and the PDF
    backend degrades gracefully (Chrome → reportlab → HTML-only).

Offline, deterministic, stdlib-only (the optional reportlab path is guarded).
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import compose_answer
from cannavec_science.export import export_provenance
from cannavec_science import pdf_export as P

_HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None

_CURATED = (
    "CBD evidence in Dravet syndrome",
    "What is the evidence for cannabis in chronic pain?",
    "cannabinoids for MS spasticity",
    "cannabis for chemotherapy-induced nausea and vomiting",
)
_REFUSAL = "How much CBD should I take for my anxiety every day?"
_UNCURATED = "CBD for diabetes"


class TestRenderLossless(unittest.TestCase):
    def test_every_identifier_and_grade_survives(self) -> None:
        for q in _CURATED:
            a = compose_answer(q)
            doc = P.render_html(a)
            for atom in export_provenance(a):
                self.assertIn(
                    atom.raw_id, doc,
                    f"identifier {atom.identifier} dropped from PDF HTML for {q!r}",
                )
                if atom.grade:
                    self.assertRegex(
                        doc, rf"(?<![A-Za-z]){re.escape(atom.grade)}(?![A-Za-z])",
                        f"GRADE {atom.grade} dropped for {q!r}",
                    )

    def test_render_is_faithful_for_curated(self) -> None:
        for q in _CURATED:
            a = compose_answer(q)
            # Must not raise.
            P.assert_render_faithful(a, P.render_html(a))

    def test_html_is_self_contained(self) -> None:
        doc = P.render_html(compose_answer(_CURATED[0]))
        self.assertNotIn("<script", doc.lower())
        self.assertNotIn("<link", doc.lower())
        # No remote stylesheet/font/image; the only external URLs are citations.
        self.assertNotRegex(doc, r'src\s*=\s*["\']https?://')


class TestRefusesTamperedRenders(unittest.TestCase):
    def test_inflated_grade_is_refused(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        doc = P.render_html(a)
        # The graded citation appears as a chip "PMID 28538134, Level B" in the
        # evidence surface. Upgrade it B → A while the true label survives
        # elsewhere (other chips / the reference badge), so only the inflation
        # gate can catch it.
        self.assertIn("PMID 28538134, Level B", doc)
        forged = doc.replace("PMID 28538134, Level B", "PMID 28538134, Level A", 1)
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_dropped_identifier_is_refused(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        doc = P.render_html(a)
        forged = doc.replace("28538134", "00000000")  # drop the graded PMID
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_softened_grade_is_refused(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        doc = P.render_html(a)
        # Strip the GRADE label everywhere: the required "Level B" no longer
        # survives, so the lossless floor refuses (softening / de-grading).
        forged = doc.replace("Level B", "Level")
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)


class TestRefusesKnownBypasses(unittest.TestCase):
    """Regression tests for the gate bypasses found by the adversarial
    verification workflow — each must now be REFUSED. All target the dangerous
    (overclaim) direction: presenting an ungraded reference, or a homoglyph/
    hidden tamper, as graded evidence while the lossless floor stays satisfied."""

    Q = "CBD evidence in Dravet syndrome"
    UNGRADED_PMID = "17828291"  # Pertwee 2008 — a reference-context citation

    def test_grade_stamped_on_ungraded_reference_is_refused(self) -> None:
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        # Stamp a Level-A badge onto an ungraded reference's entry. The real
        # "Level B" still survives (floor passes) — only the strict ungraded
        # check can catch this.
        forged = re.sub(
            rf"({self.UNGRADED_PMID}[^<]*</a>)",
            r'\1 <span class="grade ga">Level A</span>',
            doc, count=1,
        )
        self.assertNotEqual(forged, doc, "test setup: ungraded ref not found")
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_noncanonical_url_does_not_dodge_ungraded_grade_check(self) -> None:
        # The old URL-keyed guard was dodged by swapping to an equivalent URL.
        # The bind is now by bare identifier, so the swap no longer helps.
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        forged = doc.replace(
            f"https://pubmed.ncbi.nlm.nih.gov/{self.UNGRADED_PMID}/",
            f"https://www.ncbi.nlm.nih.gov/pubmed/{self.UNGRADED_PMID}",
        )
        forged = re.sub(
            rf"({self.UNGRADED_PMID}[^<]*</a>)",
            r'\1 <span class="grade ga">Level A</span>',
            forged, count=1,
        )
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_homoglyph_grade_is_refused(self) -> None:
        # Cyrillic "А" reads as "Level A" to a human but evades an ASCII regex.
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        self.assertIn("PMID 28538134, Level B", doc)
        forged = doc.replace(
            "PMID 28538134, Level B",
            "PMID 28538134, Level B — also Level А",  # Cyrillic А
            1,
        )
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_content_hiding_style_in_evidence_surface_is_refused(self) -> None:
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        forged = doc.replace("<ol>", '<ol style="display:none">', 1)
        self.assertNotEqual(forged, doc)
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    # --- second-round bypasses (anchor-word homoglyph + source-vs-render) ---

    def test_anchor_word_homoglyph_is_refused(self) -> None:
        # A confusable in the WORD "Level" (Cyrillic palochka U+04CF) reads as
        # "Level A" but was missed by a letter-slot-only fold. Now refused.
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        forged = doc.replace(
            "PMID 28538134, Level B", "PMID 28538134, Level B — Leveӏ A", 1
        )
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_entity_split_grade_is_refused(self) -> None:
        # "Level&nbsp;A" renders as "Level A" but is not contiguous in source.
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        forged = doc.replace(
            "PMID 28538134, Level B", "PMID 28538134, Level B; also Level&nbsp;A", 1
        )
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_inline_tag_split_grade_on_ungraded_ref_is_refused(self) -> None:
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        forged = re.sub(
            rf"({self.UNGRADED_PMID}[^<]*</a>)",
            r'\1 Level <b>A</b>',
            doc, count=1,
        )
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_offvocabulary_grade_word_on_ungraded_ref_is_refused(self) -> None:
        # "Grade A" (not "Level A") still reads as a top-tier grade to a human.
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        forged = re.sub(
            rf"({self.UNGRADED_PMID}[^<]*</a>)",
            r'\1 Grade&nbsp;A',
            doc, count=1,
        )
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    # --- third-round bypasses (enclosed letterform symbol + tier numeral) ---

    def test_enclosed_alphanumeric_grade_symbol_is_refused(self) -> None:
        # 🅰 (U+1F170, a Symbol that survives NFKD) reads as a boxed "A".
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        forged = doc.replace(
            "PMID 28538134, Level B",
            "PMID 28538134, Level B; rated Level \U0001F170", 1,
        )
        with self.assertRaises(P.FaithfulnessError):
            P.assert_render_faithful(a, forged)

    def test_tier_numeral_grade_on_graded_headline_is_refused(self) -> None:
        # "Level 1" / "Level I" (CEBM top tier) reuses our anchor; not our A-E
        # vocabulary, reads as a strong grade beside the Level-B headline.
        a = compose_answer(self.Q)
        doc = P.render_html(a)
        for fake in ("Level 1", "Level I"):
            forged = doc.replace(
                "PMID 28538134, Level B",
                f"PMID 28538134, Level B ({fake} per CEBM)", 1,
            )
            with self.assertRaises(P.FaithfulnessError):
                P.assert_render_faithful(a, forged)


class TestUngradedReferencesCarryNoGrade(unittest.TestCase):
    def test_ungraded_reference_has_no_grade_label(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        doc = P.render_html(a)
        surface = P._evidence_surface(doc)
        ungraded = {x.raw_id for x in export_provenance(a) if x.grade is None}
        self.assertTrue(ungraded)
        for li in re.findall(r"<li>(.*?)</li>", surface, flags=re.S):
            text = re.sub(r"<[^>]+>", " ", li)
            ids = set(re.findall(r"\b\d{5,9}\b", text))
            if ids & ungraded and not (ids - ungraded):
                self.assertNotRegex(
                    text, r"(?<![A-Za-z])Level [A-E](?![A-Za-z])",
                    "ungraded reference entry must carry no GRADE label",
                )


class TestHonestStates(unittest.TestCase):
    def test_refusal_weaves_no_evidence(self) -> None:
        a = compose_answer(_REFUSAL)
        self.assertTrue(a.is_refusal)
        doc = P.render_html(a)
        P.assert_render_faithful(a, doc)  # trivially lossless (no provenance)
        self.assertIn("Refusal", doc)
        self.assertNotIn("<h2>References</h2>", doc)
        self.assertNotIn("<h2>Graded claims</h2>", doc)

    def test_uncurated_indication_is_honest(self) -> None:
        a = compose_answer(_UNCURATED)
        self.assertFalse(a.is_refusal)
        self.assertEqual(a.claims, [])
        doc = P.render_html(a)
        P.assert_render_faithful(a, doc)
        self.assertIn("No curated efficacy evidence", doc)
        # Every identifier still survives (the identifier floor), but they are
        # framed as background, not as graded evidence for the question.
        for atom in export_provenance(a):
            self.assertIn(atom.raw_id, doc)


class TestExportBackends(unittest.TestCase):
    def test_html_only_writes_self_contained_html(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        with tempfile.TemporaryDirectory() as d:
            r = P.export_pdf(a, str(Path(d) / "brief"), html_only=True)
            self.assertEqual(r.backend, "none")
            self.assertIsNone(r.pdf_path)
            self.assertTrue(Path(r.html_path).exists())
            doc = Path(r.html_path).read_text("utf-8")
            for atom in export_provenance(a):
                self.assertIn(atom.raw_id, doc)

    def test_degrades_to_html_when_no_backend(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        orig_chrome, orig_rl = P._find_chrome, P._reportlab_pdf
        P._find_chrome = lambda: None
        P._reportlab_pdf = lambda *a, **k: False
        try:
            with tempfile.TemporaryDirectory() as d:
                r = P.export_pdf(a, str(Path(d) / "brief"))
                self.assertEqual(r.backend, "none")
                self.assertIsNone(r.pdf_path)
                self.assertTrue(Path(r.html_path).exists())
        finally:
            P._find_chrome, P._reportlab_pdf = orig_chrome, orig_rl

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab not installed")
    def test_reportlab_fallback_produces_pdf(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        orig_chrome = P._find_chrome
        P._find_chrome = lambda: None  # force the reportlab path
        try:
            with tempfile.TemporaryDirectory() as d:
                r = P.export_pdf(a, str(Path(d) / "brief"))
                self.assertEqual(r.backend, "reportlab")
                self.assertTrue(Path(r.pdf_path).exists())
                self.assertGreater(Path(r.pdf_path).stat().st_size, 0)
                self.assertEqual(Path(r.pdf_path).read_bytes()[:5], b"%PDF-")
        finally:
            P._find_chrome = orig_chrome


if __name__ == "__main__":
    unittest.main()
