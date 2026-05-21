"""Tests for the bibliography exporter (spec 004 US4).

The exporter turns a Cannavec :class:`Answer`'s citation list into a
BibTeX / RIS / CSL-JSON bibliography that imports cleanly into Zotero
/ Mendeley / EndNote. Tests cover:

- Happy-path round-trip for each format.
- Deterministic byte-identical output for identical input.
- Cite-key stability (PMID-bearing citations produce
  ``cannavec_pmid_<pmid>``; DOI-only produce a stable hash key).
- Empty-input behaviour (zero entries, valid file header).
- GRADE annotation surfaces in each format's note field.
- Sanitization (no profile data).
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import Answer, Citation       # noqa: E402
from cannavec_science.bibliography import (                # noqa: E402
    BibliographyEntry,
    bibliography_from_answer,
    render,
    render_bibtex,
    render_csljson,
    render_ris,
)


def _make_answer_with_pmids() -> Answer:
    """Build a fixture Answer with three citations covering the three
    identifier modes (PMID, DOI, URL)."""
    ans = Answer(prompt="What is the evidence for CBD in Dravet syndrome?",
                 audience="researcher")
    ans.citations.append(Citation(
        label="Devinsky 2017 — Trial of cannabidiol for drug-resistant seizures in Dravet — NEJM",
        pmid="28538134",
        year=2017,
    ))
    ans.citations.append(Citation(
        label="Thiele 2018 — Cannabidiol in patients with seizures associated with LGS — Lancet",
        pmid="29395273",
        doi="10.1016/S0140-6736(18)30136-3",
        year=2018,
    ))
    ans.citations.append(Citation(
        label="FDA briefing memo — Epidiolex approval 2018",
        url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2018/210365lbl.pdf",
        year=2018,
    ))
    return ans


class TestBibliographyFromAnswer(unittest.TestCase):
    def test_builds_one_entry_per_citation(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        self.assertEqual(len(entries), 3)

    def test_entries_sorted_deterministically(self) -> None:
        ans = _make_answer_with_pmids()
        a = bibliography_from_answer(ans)
        b = bibliography_from_answer(ans)
        # Byte-identical
        self.assertEqual(
            [e.cite_key for e in a], [e.cite_key for e in b],
        )

    def test_pmid_citekey_is_stable(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        keys = {e.cite_key for e in entries}
        self.assertIn("cannavec_pmid_28538134", keys)
        self.assertIn("cannavec_pmid_29395273", keys)

    def test_doi_only_citekey_is_a_hash(self) -> None:
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Doe 2021 — Cannabis methods review",
            doi="10.1234/example.2021.0001",
            year=2021,
        ))
        entries = bibliography_from_answer(ans)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].cite_key.startswith("cannavec_doi_"))

    def test_url_only_citekey_is_a_hash(self) -> None:
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="FDA Epidiolex label",
            url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2018/210365lbl.pdf",
            year=2018,
        ))
        entries = bibliography_from_answer(ans)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].cite_key.startswith("cannavec_url_"))


class TestBibtexRender(unittest.TestCase):
    def test_emits_one_article_per_citation(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        out = render_bibtex(entries)
        self.assertEqual(out.count("@article{"), 3)

    def test_contains_required_fields(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        out = render_bibtex(entries)
        # PMID 28538134 entry should carry title, year, pmid
        self.assertIn("cannavec_pmid_28538134", out)
        self.assertIn("title", out)
        self.assertIn("year    = {2017}", out)
        self.assertIn("pmid    = {28538134}", out)

    def test_empty_input_emits_valid_header(self) -> None:
        out = render_bibtex(())
        self.assertIn("Cannavec Science bibliography", out)
        self.assertNotIn("@article", out)

    def test_byte_deterministic(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        self.assertEqual(render_bibtex(entries), render_bibtex(entries))

    def test_escapes_bibtex_metacharacters(self) -> None:
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Smith 2020 — Δ⁹-THC & CBD: 100% efficacy claim",
            pmid="99999999",
            year=2020,
        ))
        entries = bibliography_from_answer(ans)
        out = render_bibtex(entries)
        # `&` and `%` must be escaped to prevent BibTeX parser errors
        self.assertIn(r"\&", out)
        self.assertIn(r"\%", out)


class TestRisRender(unittest.TestCase):
    def test_emits_one_record_per_citation(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        out = render_ris(entries)
        self.assertEqual(out.count("TY  - JOUR"), 3)
        self.assertEqual(out.count("ER  -"), 3)

    def test_pmid_uses_m2_line(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        out = render_ris(entries)
        self.assertIn("M2  - PMID:28538134", out)
        self.assertIn("M2  - PMID:29395273", out)

    def test_doi_uses_do_line(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        out = render_ris(entries)
        self.assertIn("DO  - 10.1016/S0140-6736(18)30136-3", out)

    def test_empty_input_emits_empty_string(self) -> None:
        out = render_ris(())
        # No records → essentially empty (a trailing newline is fine).
        self.assertNotIn("TY  - JOUR", out)
        self.assertNotIn("ER  - ", out)


class TestCsljsonRender(unittest.TestCase):
    def test_parses_as_valid_json(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        out = render_csljson(entries)
        parsed = json.loads(out)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 3)

    def test_required_csl_fields_present(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        parsed = json.loads(render_csljson(entries))
        for item in parsed:
            self.assertEqual(item["type"], "article-journal")
            self.assertIn("title", item)
            self.assertIn("id", item)

    def test_pmid_surfaces_in_csl(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        parsed = json.loads(render_csljson(entries))
        pmids = {item.get("PMID") for item in parsed if "PMID" in item}
        self.assertIn("28538134", pmids)
        self.assertIn("29395273", pmids)

    def test_empty_input_emits_empty_array(self) -> None:
        out = render_csljson(())
        parsed = json.loads(out)
        self.assertEqual(parsed, [])


class TestRenderDispatch(unittest.TestCase):
    def test_format_dispatch_bibtex(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        self.assertIn("@article{", render(entries, "bibtex"))

    def test_format_dispatch_ris(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        self.assertIn("TY  - JOUR", render(entries, "ris"))

    def test_format_dispatch_csljson(self) -> None:
        ans = _make_answer_with_pmids()
        entries = bibliography_from_answer(ans)
        out = render(entries, "csljson")
        # Should parse as JSON
        json.loads(out)

    def test_format_dispatch_csl_alias(self) -> None:
        entries = ()
        self.assertEqual(render(entries, "csl"), "[]\n")

    def test_format_dispatch_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            render((), "wikitext")


class TestEvidenceLevelAnnotation(unittest.TestCase):
    """When the source Answer provides typed Claims with evidence grades,
    each bibliography entry should surface the matching GRADE."""

    def _make_answer_with_grade(self) -> Answer:
        from cannavec_science.evidence import (
            Claim, ClaimType, Source, SourceTier, required_disclosures,
        )
        ans = Answer(prompt="x", audience="researcher")
        source = Source(
            title="Devinsky 2017 NEJM Dravet RCT",
            tier=SourceTier.JOURNAL_RCT,
            pmid="28538134",
            year=2017,
            pre_registered=True,
            adequately_powered=True,
        )
        # A two-source claim makes the deterministic single-primary-cap not apply.
        source2 = Source(
            title="Thiele 2018 Lancet LGS RCT",
            tier=SourceTier.JOURNAL_RCT,
            pmid="29395273",
            year=2018,
            pre_registered=True,
            adequately_powered=True,
        )
        claim = Claim(
            text="CBD reduces convulsive seizures in Dravet syndrome at 20 mg/kg/day (oral).",
            claim_type=ClaimType.CLINICAL_EFFICACY,
            sources=(source, source2),
            disclosures_present=required_disclosures(ClaimType.CLINICAL_EFFICACY),
        )
        ans.add_claim(claim)
        return ans

    def test_grade_appears_in_entry(self) -> None:
        ans = self._make_answer_with_grade()
        entries = bibliography_from_answer(ans)
        self.assertGreaterEqual(len(entries), 1)
        levels = {e.evidence_level for e in entries
                  if e.pmid == "28538134"}
        # Two pre-registered adequately-powered RCTs = at least Level B
        self.assertTrue(
            any(lvl in {"Level A", "Level B"} for lvl in levels),
            f"expected GRADE A or B, got {levels}",
        )

    def test_grade_appears_in_bibtex_note(self) -> None:
        ans = self._make_answer_with_grade()
        entries = bibliography_from_answer(ans)
        out = render_bibtex(entries)
        self.assertIn("Cannavec GRADE: Level", out)

    def test_grade_appears_in_ris_note(self) -> None:
        ans = self._make_answer_with_grade()
        entries = bibliography_from_answer(ans)
        out = render_ris(entries)
        self.assertIn("Cannavec GRADE: Level", out)

    def test_grade_appears_in_csljson_note(self) -> None:
        ans = self._make_answer_with_grade()
        entries = bibliography_from_answer(ans)
        out = render_csljson(entries)
        parsed = json.loads(out)
        notes = [item.get("note", "") for item in parsed]
        self.assertTrue(any("Cannavec GRADE" in n for n in notes))


class TestSanitization(unittest.TestCase):
    """The exporter must never include profile data or filesystem paths."""

    def test_profile_notes_do_not_leak(self) -> None:
        """The bibliography operates on Answer.citations only — there is
        no Answer.profile field, so by construction the exporter cannot
        leak profile data. This test guards against future regressions
        by asserting the exporter signature."""
        from inspect import signature
        sig = signature(bibliography_from_answer)
        params = set(sig.parameters)
        self.assertEqual(params, {"answer"})


if __name__ == "__main__":
    unittest.main()
