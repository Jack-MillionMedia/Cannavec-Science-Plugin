"""Spec 036 Step 4 — INFORMATIVE live findings (snippet + direction + provenance).

Each on-topic live finding should render, where the data allows:

- a verified ``abstract_snippet`` — a TRUE substring of the row's abstract,
  never a paraphrase (§I / M5). No abstract ⇒ no snippet (no fabrication).
- a ``direction`` (supports / refutes / neutral) sourced ONLY from the existing
  synthesis attributor (``synthesis._row_direction``) — no new sentiment model.
- a Live-section search-provenance line: "Searched N live sources · M found ·
  K on-topic", from counts already on the Answer (deterministic, offline).

These tests pin the substring guarantee (a paraphrase is rejected), the
degrade-cleanly path (a PubMed row carries no abstract in the offline harness),
the render of all three on both surfaces (Markdown + PDF HTML), serialization,
and that the snippet survives the §XI render gate (``assert_render_faithful``).
"""

from __future__ import annotations

import unittest

from cannavec_science import live
from cannavec_science.answer import (
    Answer,
    compose_answer,
    live_finding_from_row,
)
from cannavec_science.live_snippet import supporting_snippet
from cannavec_science.pdf_export import assert_render_faithful, render_html


# A real-shaped abstract sentence — direction-bearing, on-topic prose.
_ABSTRACT = (
    "Background: refractory epilepsy remains hard to treat. "
    "Cannabidiol significantly reduced seizure frequency in this cohort. "
    "We enrolled 120 patients across three sites."
)


class _FakeHit:
    """Stand-in for a searcher LiveHit (only needs ``.to_dict()``)."""

    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _runner(rows):
    def _r(query, since, n):
        return rows[:n]

    return _r


# ── the snippet helper itself ─────────────────────────────────────────


class TestSupportingSnippet(unittest.TestCase):

    def test_returns_a_literal_substring(self) -> None:
        snip = supporting_snippet("cannabidiol seizure frequency", _ABSTRACT)
        self.assertTrue(snip)
        # The chosen span MUST be a verbatim slice of the abstract.
        self.assertIn(snip, _ABSTRACT)

    def test_paraphrase_can_never_be_returned(self) -> None:
        # A query that shares words but whose best sentence is verified — the
        # helper may only ever return text that IS in the abstract. We assert the
        # invariant directly: whatever it returns is a true substring (or empty).
        for q in ("seizure", "patients enrolled", "cannabidiol", "unrelated xyz"):
            snip = supporting_snippet(q, _ABSTRACT)
            if snip:
                self.assertIn(snip, _ABSTRACT)

    def test_no_abstract_returns_empty(self) -> None:
        self.assertEqual(supporting_snippet("anything", ""), "")
        self.assertEqual(supporting_snippet("", _ABSTRACT), "")

    def test_a_fabricated_candidate_is_rejected(self) -> None:
        # A candidate sentence that is NOT in the abstract is never surfaced —
        # the substring gate (verify_quote) rejects it. Proven by an abstract
        # whose only overlapping content is a paraphrase of the query: the helper
        # must not echo the query, only a real abstract sentence.
        abstract = "Cannabidiol lowered seizures markedly in the treated arm."
        snip = supporting_snippet("CBD reduced seizure frequency", abstract)
        # If anything comes back it is a real slice of the abstract, never the
        # paraphrased query wording ("reduced seizure frequency").
        if snip:
            self.assertIn(snip, abstract)
            self.assertNotIn("reduced seizure frequency", snip.lower())

    def test_substring_gate_is_load_bearing(self) -> None:
        # Direct proof the substring gate (not just overlap scoring) is what
        # admits a snippet: monkeypatch verify_quote to always reject, and even a
        # perfect-overlap sentence yields NO snippet — never a fabrication.
        import cannavec_science.claim_support as cs

        original = cs.verify_quote
        try:
            cs.verify_quote = lambda *a, **k: False  # gate rejects everything
            self.assertEqual(
                supporting_snippet("cannabidiol seizure frequency", _ABSTRACT), ""
            )
        finally:
            cs.verify_quote = original


# ── snippet attachment in live_finding_from_row ───────────────────────


class TestSnippetOnFinding(unittest.TestCase):

    def test_row_with_abstract_gets_a_substring_snippet(self) -> None:
        f = live_finding_from_row(
            "biorxiv",
            {
                "doi": "10.1101/2024.05.05",
                "title": "Cannabidiol reduces seizure frequency in refractory epilepsy",
                "abstract": _ABSTRACT,
                "year": 2024,
            },
        )
        assert f is not None
        self.assertIn("abstract_snippet", f)
        self.assertIn(f["abstract_snippet"], _ABSTRACT)

    def test_row_without_abstract_gets_no_snippet(self) -> None:
        # The offline PubMed harness carries no abstract — the field is omitted
        # (no paraphrase, no fabrication), the finding still grades + renders.
        f = live_finding_from_row(
            "pubmed", {"pmid": "12345678", "title": "CBD epilepsy trial", "year": 2024}
        )
        assert f is not None
        self.assertNotIn("abstract_snippet", f)


# ── direction + provenance line via the weave ─────────────────────────


class TestLiveRenderWeave(unittest.TestCase):

    def _augmented(self):
        """A curated answer augmented with two on-topic preprint rows (abstracts
        present so direction + snippet are computable), fully offline."""
        a = compose_answer("CBD for refractory epilepsy seizure frequency")
        rows = [
            _FakeHit(
                doi="10.1101/2024.01.01",
                title="Cannabidiol reduces seizure frequency in refractory epilepsy",
                abstract=_ABSTRACT,
                year=2024,
            ),
            _FakeHit(
                doi="10.1101/2024.02.02",
                title="Cannabidiol and refractory epilepsy seizure outcomes",
                abstract=(
                    "Cannabidiol did not improve seizure frequency in this "
                    "randomized cohort of refractory epilepsy patients."
                ),
                year=2024,
            ),
        ]
        n = live.augment_answer(a, sources=["biorxiv"], runners={"biorxiv": _runner(rows)})
        self.assertGreater(n, 0)
        return a

    def test_provenance_line_renders_with_counts(self) -> None:
        a = self._augmented()
        md = a.to_markdown()
        self.assertIn("Searched", md)
        # N live sources / M found / K on-topic — the counts must be real.
        self.assertIn("on-topic", md)
        self.assertRegex(md, r"Searched \d+ live source")

    def test_snippet_renders_under_the_finding(self) -> None:
        a = self._augmented()
        md = a.to_markdown()
        # At least one finding carries a verified snippet, rendered verbatim.
        snippets = [f.get("abstract_snippet") for f in a.live_findings if f.get("abstract_snippet")]
        self.assertTrue(snippets)
        for s in snippets:
            self.assertIn(s, md)

    def test_direction_renders_where_synthesis_provides_it(self) -> None:
        a = self._augmented()
        # One row "reduced ... significantly" → supports; one "did not improve"
        # → refutes. Both are synthesis-attributed directions, not invented.
        dirs = {f.get("direction") for f in a.live_findings if f.get("direction")}
        self.assertTrue(dirs)
        self.assertTrue(dirs.issubset({"supports", "refutes", "neutral"}))
        md = a.to_markdown()
        self.assertIn("→", md)

    def test_direction_and_snippet_serialize(self) -> None:
        a = self._augmented()
        d = a.to_dict()
        lf = d["live_findings"]
        self.assertTrue(any("abstract_snippet" in f for f in lf))
        self.assertTrue(any("direction" in f for f in lf))

    def test_render_gate_passes_with_snippet_and_direction(self) -> None:
        # §XI faithfulness: the snippet is prose context near a live id; it must
        # not introduce a stray "Level X" the gate reads as a grade, and every id
        # + grade must survive losslessly.
        a = self._augmented()
        html = render_html(a)
        assert_render_faithful(a, html)  # raises FaithfulnessError on any drift

    def test_degrades_cleanly_when_no_abstract(self) -> None:
        # The offline PubMed harness carries no abstract: the provenance line and
        # grade still render, but NO snippet is fabricated and the §XI render gate
        # still passes (degrade, never block — §I / M5).
        a = compose_answer("CBD for refractory epilepsy seizure frequency")
        rows = [
            _FakeHit(
                pmid="30000001",
                title="Cannabidiol in refractory epilepsy: a clinical trial",
                year=2024,
            )
        ]
        live.augment_answer(a, sources=["pubmed"], runners={"pubmed": _runner(rows)})
        self.assertFalse(any(f.get("abstract_snippet") for f in a.live_findings))
        self.assertFalse(any(f.get("direction") for f in a.live_findings))
        md = a.to_markdown()
        self.assertIn("Searched 1 live source", md)
        assert_render_faithful(a, render_html(a))

    def test_pdf_renders_snippet_and_provenance(self) -> None:
        a = self._augmented()
        html = render_html(a)
        self.assertIn("Searched", html)
        snippets = [f.get("abstract_snippet") for f in a.live_findings if f.get("abstract_snippet")]
        self.assertTrue(snippets)
        # The snippet text appears in the rendered HTML (escaped, but the words
        # survive).
        self.assertIn("seizure frequency", html)


if __name__ == "__main__":
    unittest.main()
