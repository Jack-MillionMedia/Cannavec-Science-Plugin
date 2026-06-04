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

import argparse
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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


# ── Defect #6 — structured authors / journal / volume / pages ─────────
#
# Regression for the verbatim eval finding:
#   author = {Pertwee RG and Br J Pharmacol and lig and -binding profile
#             of phytocannabinoids}
# The exporter used to tokenize the *human-readable label* on commas and
# emit the journal name and title fragments as bogus "authors", and never
# emitted journal / volume / issue / pages. A bibliography that drops
# garbage authors into Zotero is not citable. These tests pin the
# strength: author/journal/volume/issue/pages are derived from STRUCTURE,
# never from naive label tokenization.

_AUTHOR_RE = re.compile(r"author\s*=\s*\{([^}]*)\}")


def _bibtex_authors(out: str, cite_key: str) -> str:
    """Return the raw ``author = {...}`` body for one BibTeX entry."""
    block = out.split(f"@article{{{cite_key},", 1)[1].split("@article{", 1)[0]
    m = _AUTHOR_RE.search(block)
    return m.group(1) if m else ""


def _bibtex_field(out: str, cite_key: str, field: str) -> str:
    block = out.split(f"@article{{{cite_key},", 1)[1].split("@article{", 1)[0]
    m = re.search(rf"{field}\s*=\s*\{{([^}}]*)\}}", block)
    return m.group(1) if m else ""


class TestLabelTokenizationRegression(unittest.TestCase):
    """The exact #6 smoking gun: the comma-delimited Cannavec label
    ``"<Authors>, <Journal> <Year>, <description>"`` must yield a real
    surname author and the real journal — never the journal or title
    fragments as authors."""

    PERTWEE = "Pertwee RG, Br J Pharmacol 2008, ligand-binding profile of phytocannabinoids"

    def _pertwee_answer(self) -> Answer:
        ans = Answer(prompt="receptor binding", audience="researcher")
        ans.citations.append(Citation(label=self.PERTWEE, pmid="17828291", year=2008))
        return ans

    def test_author_is_real_surname_not_journal_or_title(self) -> None:
        entries = bibliography_from_answer(self._pertwee_answer())
        (e,) = entries
        joined = " | ".join(e.authors)
        # POSITIVE: the real first author is present.
        self.assertIn("Pertwee", joined)
        # NEGATIVE: the journal abbreviation must NOT be an author.
        self.assertNotIn("Br J Pharmacol", joined)
        self.assertNotIn("Pharmacol", joined)
        # NEGATIVE: title fragments must NOT be authors.
        self.assertNotIn("lig", joined)
        self.assertNotIn("binding", joined)
        self.assertNotIn("phytocannabinoids", joined)

    def test_journal_extracted_from_label(self) -> None:
        (e,) = bibliography_from_answer(self._pertwee_answer())
        self.assertEqual(e.journal, "Br J Pharmacol")

    def test_bibtex_author_field_has_no_journal_or_title(self) -> None:
        out = render_bibtex(bibliography_from_answer(self._pertwee_answer()))
        authors = _bibtex_authors(out, "cannavec_pmid_17828291")
        self.assertIn("Pertwee", authors)
        # The historical bug emitted: Pertwee RG and Br J Pharmacol and lig and ...
        self.assertNotIn("Br J Pharmacol", authors)
        self.assertNotIn("binding profile", authors)
        self.assertNotIn("phytocannabinoids", authors)
        # And the journal must land in the journal field, not authors.
        self.assertEqual(
            _bibtex_field(out, "cannavec_pmid_17828291", "journal"),
            "Br J Pharmacol",
        )

    def test_csljson_authors_are_real_surnames(self) -> None:
        parsed = json.loads(render_csljson(bibliography_from_answer(self._pertwee_answer())))
        (item,) = parsed
        families = [a.get("family", "") for a in item.get("author", [])]
        self.assertIn("Pertwee", " ".join(families))
        # No journal / title fragments masquerading as a family name.
        for bad in ("Pharmacol", "lig", "phytocannabinoids", "binding"):
            for fam in families:
                self.assertNotIn(bad, fam)
        self.assertEqual(item.get("container-title"), "Br J Pharmacol")

    def test_multi_author_comma_form_keeps_journal_out(self) -> None:
        # "Lazenka MF, Selley DE, Sim-Selley LJ, Life Sci 2012, ..." — three
        # comma-separated authors then the journal+year. The journal token
        # must not become a fourth "author".
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Lazenka MF, Selley DE, Sim-Selley LJ, Life Sci 2012, brain CB1 desensitization",
            pmid="22222222", year=2012,
        ))
        (e,) = bibliography_from_answer(ans)
        joined = " | ".join(e.authors)
        self.assertIn("Lazenka", joined)
        self.assertNotIn("Life Sci", joined)
        self.assertNotIn("desensitization", joined)
        self.assertEqual(e.journal, "Life Sci")

    def test_ampersand_author_join_keeps_journal_out(self) -> None:
        # "Gaoni Y & Mechoulam R, J Am Chem Soc 1964, ..." — the '&' joins
        # two authors; the journal must not be swept into the author list.
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Gaoni Y & Mechoulam R, J Am Chem Soc 1964, isolation and structure of THC",
            pmid="33333333", year=1964,
        ))
        (e,) = bibliography_from_answer(ans)
        joined = " | ".join(e.authors)
        self.assertIn("Gaoni", joined)
        self.assertNotIn("J Am Chem Soc", joined)
        self.assertEqual(e.journal, "J Am Chem Soc")


class TestEmDashAndParenLabels(unittest.TestCase):
    """The other dominant Cannavec label shapes must also parse cleanly."""

    def test_em_dash_journal_in_parens(self) -> None:
        # "Devinsky 2017 — CBD in Dravet syndrome (NEJM)"
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
            pmid="28538134", year=2017,
        ))
        (e,) = bibliography_from_answer(ans)
        self.assertEqual(e.authors, ("Devinsky",))
        self.assertEqual(e.journal, "NEJM")

    def test_em_dash_journal_before_dash(self) -> None:
        # "Bansal et al. 2022 Drug Metab Dispos — cannabinoid CYP ..."
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Bansal et al. 2022 Drug Metab Dispos — cannabinoid CYP drug-interaction predictions",
            pmid="44444444", year=2022,
        ))
        (e,) = bibliography_from_answer(ans)
        self.assertEqual(e.authors, ("Bansal",))
        self.assertNotIn("interaction", " ".join(e.authors))
        self.assertEqual(e.journal, "Drug Metab Dispos")

    def test_paren_year_form_keeps_title_out(self) -> None:
        # Mirrors tests/test_cli_bibliography.py's fixture label.
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Devinsky et al. (2017) Cannabidiol in Dravet syndrome.",
            pmid="28538134", year=2017,
        ))
        (e,) = bibliography_from_answer(ans)
        self.assertEqual(e.authors, ("Devinsky",))
        self.assertNotIn("Cannabidiol", " ".join(e.authors))


class TestNonCitationLabels(unittest.TestCase):
    """Section/monograph titles are not author-bearing — they must not be
    tokenized into a person."""

    def test_topic_label_yields_no_bogus_author(self) -> None:
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Adverse events", url="https://example.org/ae", year=None,
        ))
        (e,) = bibliography_from_answer(ans)
        # A two-word topic phrase must not be split so that "events"
        # becomes a surname author. Either no authors, or a single token
        # that is not the trailing common word.
        self.assertNotIn("events", " ".join(e.authors))


class TestStructuredVolumeIssuePages(unittest.TestCase):
    """When an entry carries structured journal/volume/issue/pages, every
    format must round-trip them (we never *invent* them, but if present
    they must reach Zotero)."""

    def _entry(self) -> BibliographyEntry:
        return BibliographyEntry(
            cite_key="cannavec_pmid_28538134",
            title="Trial of cannabidiol for drug-resistant seizures in the Dravet syndrome",
            authors=("Devinsky",),
            year=2017,
            journal="N Engl J Med",
            volume="376",
            issue="21",
            pages="2011-2020",
            pmid="28538134",
            doi="10.1056/NEJMoa1611618",
        )

    def test_bibtex_emits_journal_volume_number_pages(self) -> None:
        out = render_bibtex([self._entry()])
        self.assertIn("journal = {N Engl J Med}", out)
        self.assertIn("volume  = {376}", out)
        self.assertIn("number  = {21}", out)
        self.assertIn("pages   = {2011-2020}", out)

    def test_ris_emits_jo_vl_is_sp_ep(self) -> None:
        out = render_ris([self._entry()])
        self.assertIn("JO  - N Engl J Med", out)
        self.assertIn("VL  - 376", out)
        self.assertIn("IS  - 21", out)
        self.assertIn("SP  - 2011", out)
        self.assertIn("EP  - 2020", out)

    def test_csljson_emits_container_volume_issue_page(self) -> None:
        (item,) = json.loads(render_csljson([self._entry()]))
        self.assertEqual(item["container-title"], "N Engl J Med")
        self.assertEqual(item["volume"], "376")
        self.assertEqual(item["issue"], "21")
        self.assertEqual(item["page"], "2011-2020")

    def test_absent_volume_pages_are_omitted(self) -> None:
        # An entry without volume/pages must not emit empty fields.
        ans = Answer(prompt="x", audience="researcher")
        ans.citations.append(Citation(
            label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
            pmid="28538134", year=2017,
        ))
        out_bib = render_bibtex(bibliography_from_answer(ans))
        self.assertNotIn("volume  = {}", out_bib)
        self.assertNotIn("pages   = {}", out_bib)
        out_ris = render_ris(bibliography_from_answer(ans))
        self.assertNotIn("VL  - \n", out_ris)
        self.assertNotIn("SP  - \n", out_ris)


class TestCliErrorGuard(unittest.TestCase):
    """Defect #11 — the CLI must fail gracefully (clean ``[error]`` line +
    non-zero exit), never dump a raw stdlib traceback, on a missing or
    malformed input file — matching every sibling ``_cmd_*`` handler."""

    def _run(self, path: str, fmt: str = "bibtex") -> tuple[int, str, str]:
        from cannavec_science.__main__ import _cmd_bibliography
        args = argparse.Namespace(answer_json=path, format=fmt, out=None)
        out_buf, err_buf = io.StringIO(), io.StringIO()
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            rc = _cmd_bibliography(args)
        return rc, out_buf.getvalue(), err_buf.getvalue()

    def test_missing_file_clean_error_nonzero(self) -> None:
        rc, out, err = self._run("/does/not/exist.json")
        self.assertNotEqual(rc, 0)
        self.assertIn("[error]", err)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("Traceback", out)

    def test_non_json_file_clean_error_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "garbage.json"
            p.write_text("this is not json {{{", encoding="utf-8")
            rc, out, err = self._run(str(p))
        self.assertNotEqual(rc, 0)
        self.assertIn("[error]", err)
        self.assertNotIn("Traceback", err)

    def test_valid_file_still_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "answer.json"
            p.write_text(json.dumps({
                "citations": [{
                    "label": "Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                    "pmid": "28538134", "doi": None, "url": None,
                    "year": 2017, "grade": "Level B",
                }],
            }), encoding="utf-8")
            rc, out, err = self._run(str(p))
        self.assertEqual(rc, 0)
        self.assertIn("@article{cannavec_pmid_28538134", out)


class TestNoSyntaxWarning(unittest.TestCase):
    """The module must compile clean under ``-W error::SyntaxWarning`` —
    the line-288 docstring carried an invalid escape sequence ('\\`')."""

    def test_module_compiles_without_syntaxwarning(self) -> None:
        import py_compile
        import warnings

        src = Path(__file__).resolve().parents[1] / "cannavec_science" / "bibliography.py"
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            # doraise surfaces a SyntaxWarning-turned-error as PyCompileError.
            py_compile.compile(str(src), doraise=True)


if __name__ == "__main__":
    unittest.main()
