"""The citation-lossless export gate — the §XI guarantee made mechanical.

This is the foundation primitive every ``/cv`` output skill (cite / pdf /
evidence-table / presentation) calls to PROVE its rendered transform preserved
the verification: every primary-source identifier and every GRADE label present
in the verified Answer must survive into the rendered output, or the skill
refuses to emit. Without this gate an output skill could silently drop or soften
a citation/GRADE — exactly the "noise" (un-anchored, de-graded output) the
project exists to prevent (§XI / §I / §VII / M2).

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import compose_answer
from cannavec_science.export import (
    CitationAtom,
    assert_citation_lossless,
    export_provenance,
    grade_adjacency_failures,
)


class TestExportProvenance(unittest.TestCase):
    def test_curated_answer_provenance_has_graded_identifier(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        atoms = export_provenance(a)
        self.assertTrue(atoms, "curated answer should expose provenance atoms")
        dravet = [x for x in atoms if x.identifier == "PMID:28538134"]
        self.assertEqual(len(dravet), 1)
        self.assertEqual(dravet[0].grade, "Level B")

    def test_one_atom_per_citation_identifier(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        ids = [x.identifier for x in export_provenance(a)]
        self.assertEqual(len(ids), len(set(ids)), "duplicate provenance atoms")


class TestLosslessGate(unittest.TestCase):
    def test_canonical_markdown_is_lossless_against_itself(self) -> None:
        # The canonical brief MUST be citation-lossless — it is the source a
        # /cv skill transforms, so it sets the bar.
        a = compose_answer("CBD evidence in Dravet syndrome")
        report = assert_citation_lossless(a, a.to_markdown())
        self.assertTrue(
            report.ok,
            f"canonical Markdown brief is not citation-lossless: "
            f"missing ids={report.missing_identifiers} "
            f"missing grades={report.missing_grades}",
        )

    def test_bibliography_render_is_lossless(self) -> None:
        from cannavec_science.bibliography import (
            bibliography_from_answer, render_bibtex,
        )
        a = compose_answer("CBD evidence in Dravet syndrome")
        bibtex = render_bibtex(bibliography_from_answer(a))
        report = assert_citation_lossless(a, bibtex)
        self.assertTrue(report.ok, f"bibtex dropped: {report.missing_identifiers} "
                                   f"{report.missing_grades}")

    def test_dropped_identifier_is_caught(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        rendered = a.to_markdown().replace("28538134", "XXXXXXXX")  # drop a PMID
        report = assert_citation_lossless(a, rendered)
        self.assertFalse(report.ok)
        self.assertIn("PMID:28538134", report.missing_identifiers)

    def test_stripped_grade_is_caught(self) -> None:
        # Identifiers present but every GRADE label removed — a softening drop.
        a = compose_answer("CBD evidence in Dravet syndrome")
        ids_only = " ".join(
            x.identifier.split(":", 1)[1] for x in export_provenance(a)
        )
        report = assert_citation_lossless(a, ids_only)
        self.assertFalse(report.ok)
        self.assertTrue(report.missing_grades, "a dropped GRADE went uncaught")

    def test_refused_answer_is_flagged_and_has_empty_provenance(self) -> None:
        # The foundation contract: a /cv skill checks ``is_refusal`` FIRST and
        # surfaces the refusal — it never renders a brief for a refused query.
        # Provenance is empty so a skill can't be misled into "preserving"
        # reference-context citations a refusal never renders.
        a = compose_answer("You should take 50mg of THC for your insomnia tonight.")
        self.assertTrue(a.is_refusal, "safety-refused prompt must flag is_refusal")
        self.assertEqual(export_provenance(a), ())

    def test_dropped_pmid_not_masked_by_doi_embedding_those_digits(self) -> None:
        # Cross-citation digit masking: a dropped PMID must not pass merely
        # because a SURVIVING DOI embeds those digits ("...pone.28538134").
        a = compose_answer("CBD evidence in Dravet syndrome")
        rendered = a.to_markdown().replace(
            "28538134", "10.1371/journal.pone.28538134"
        )
        report = assert_citation_lossless(a, rendered)
        self.assertFalse(report.ok)
        self.assertIn("PMID:28538134", report.missing_identifiers)

    def test_empty_answer_is_trivially_lossless(self) -> None:
        from cannavec_science.answer import Answer
        a = Answer(prompt="x")  # no claims, no citations
        self.assertEqual(export_provenance(a), ())
        self.assertTrue(assert_citation_lossless(a, "").ok)

    def test_dropped_pmid_is_not_falsely_present_as_substring(self) -> None:
        # A dropped PMID must NOT pass merely because its digits appear inside a
        # longer number — the gate matches numeric ids on digit boundaries.
        a = compose_answer("CBD evidence in Dravet syndrome")
        rendered = a.to_markdown().replace("28538134", "1285381340")  # embed as substring
        report = assert_citation_lossless(a, rendered)
        self.assertFalse(report.ok)
        self.assertIn("PMID:28538134", report.missing_identifiers)

    def test_report_is_falsy_when_not_ok(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        bad = assert_citation_lossless(a, "")  # nothing survived
        self.assertFalse(bad)            # __bool__ == ok
        self.assertFalse(bad.ok)


class TestGradeAdjacency(unittest.TestCase):
    """Per-citation GRADE adjacency — the strict check inline multi-citation
    renders must pass (beyond the per-label floor)."""

    def test_canonical_markdown_grades_are_anchored(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertEqual(
            grade_adjacency_failures(a, a.to_markdown()), (),
            "canonical Markdown brief has a GRADE not anchored to its citation",
        )

    def test_grade_far_from_identifier_is_flagged(self) -> None:
        # Identifier present and the label exists somewhere, but not near the id
        # — the floor would pass; adjacency must catch it.
        a = compose_answer("CBD evidence in Dravet syndrome")
        rendered = "28538134" + (" filler" * 200) + " Level B"
        self.assertTrue(
            grade_adjacency_failures(a, rendered),
            "a GRADE far from its identifier was not flagged",
        )


if __name__ == "__main__":
    unittest.main()
