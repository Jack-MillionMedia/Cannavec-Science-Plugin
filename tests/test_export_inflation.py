"""Grade-INFLATION gate — the missing half of the §XI/§VII citation guarantee.

The lossless gate (``assert_citation_lossless`` + ``grade_adjacency_failures``)
proves a rendered transform never *drops* or *softens* a GRADE. It did NOT prove
the mirror: that a transform never *inflates* one — rendering "Level A" beside a
Level-B citation passed every check as long as a "Level B" token survived
somewhere. Presenting evidence as more certain than the backbone graded it is the
exact M5/§VII overclaim this project exists to prevent, so it must be a code-
computed refusal, not a hope.

These tests pin:
  * ``grade_inflation_failures`` flags a citation rendered above its assigned grade
    (and ANY grade rendered beside an ungraded reference-context citation),
  * a faithful render of the canonical Answer has NO inflation,
  * the GRADE floor is token-boundary scoped ("Level Below" no longer masks a
    dropped "Level B"),
  * a GRADE label far from every identifier (a legend) is not mistaken for
    inflation.

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import compose_answer
from cannavec_science.export import (
    assert_citation_lossless,
    export_provenance,
    grade_inflation_failures,
)

_CURATED = (
    "CBD evidence in Dravet syndrome",
    "What is the evidence for cannabis in chronic pain?",
    "cannabinoids for MS spasticity",
    "cannabis for chemotherapy-induced nausea and vomiting",
)


class TestNoInflationOnFaithfulRender(unittest.TestCase):
    """The canonical Markdown brief is the bar — a faithful transform of the
    verified Answer must never trip the inflation gate."""

    def test_canonical_markdown_has_no_inflation(self) -> None:
        for q in _CURATED:
            a = compose_answer(q)
            fails = grade_inflation_failures(a, a.to_markdown())
            self.assertEqual(
                fails, (),
                f"faithful canonical brief flagged as inflated for {q!r}: "
                f"{[f.identifier for f in fails]}",
            )


class TestInflationIsCaught(unittest.TestCase):
    def test_upgraded_grade_beside_citation_is_flagged(self) -> None:
        # Dravet's single graded citation is Level B. Upgrade ONE inline tag to
        # Level A while leaving every real "Level B" token in place, so the floor
        # still passes — only the inflation gate can catch this.
        a = compose_answer("CBD evidence in Dravet syndrome")
        md = a.to_markdown()
        self.assertIn("(PMID 28538134, Level B)", md)
        forged = md.replace("(PMID 28538134, Level B)", "(PMID 28538134, Level A)", 1)
        # Floor is satisfied (Level B survives in the citations list / BLUF).
        self.assertTrue(assert_citation_lossless(a, forged).ok)
        # Inflation gate flags the upgraded citation.
        fails = grade_inflation_failures(a, forged)
        self.assertIn("PMID:28538134", {f.identifier for f in fails})

    def test_curated_section_row_grade_near_ungraded_citation_is_not_inflation(
        self,
    ) -> None:
        # An ungraded reference-context citation legitimately appears inside a
        # curated-background section that prints that source's OWN row grade
        # (e.g. "**Grade:** Level B"). That is honest background, not the citation
        # being presented above its grade — the proximity gate must NOT flag it,
        # or it would flag the canonical Markdown brief itself. (The renderer owns
        # the separate guarantee that an ungraded citation shows no grade — see
        # the /cv:pdf reference-list tests.)
        a = compose_answer("CBD evidence in Dravet syndrome")
        ungraded = [x for x in export_provenance(a) if x.grade is None]
        self.assertTrue(ungraded, "expected reference-context citations")
        atom = ungraded[0]
        rendered = (
            f"## Curated reference\n- Row for PMID {atom.raw_id}\n"
            f"  - **Grade:** Level A (the row's own curated grade)\n"
        )
        self.assertEqual(grade_inflation_failures(a, rendered), ())

    def test_nearest_binding_does_not_blame_the_wrong_citation(self) -> None:
        # A legitimate Level-A citation sitting next to an unrelated ungraded id
        # must blame neither: the strong label binds to its own (Level-A) id.
        a = compose_answer("What is the evidence for cannabis in chronic pain?")
        fails = grade_inflation_failures(a, a.to_markdown())
        self.assertEqual(fails, ())


class TestStrictUngradedMode(unittest.TestCase):
    """``flag_ungraded=True`` makes a grade beside an UNGRADED citation a failure
    — for a region that holds only the answer's evidence (e.g. a PDF evidence
    surface). The default stays lenient so curated-background row grades near an
    ungraded citation are not mis-flagged (and the canonical brief stays clean)."""

    def test_grade_on_ungraded_flagged_only_in_strict_mode(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        atom = next(x for x in export_provenance(a) if x.grade is None)
        rendered = f"Source PMID {atom.raw_id} Level A is decisive."
        self.assertEqual(grade_inflation_failures(a, rendered), ())  # lenient
        strict = grade_inflation_failures(a, rendered, flag_ungraded=True)
        self.assertIn(atom.identifier, {f.identifier for f in strict})

    def test_lenient_default_still_clean_on_canonical_markdown(self) -> None:
        for q in _CURATED:
            a = compose_answer(q)
            self.assertEqual(grade_inflation_failures(a, a.to_markdown()), ())


class TestHomoglyphGradeIsCaught(unittest.TestCase):
    def test_cyrillic_level_a_beside_graded_citation_is_inflation(self) -> None:
        # Cyrillic "А" (U+0410) reads as "Level A" but is not ASCII; folded to A,
        # it must be caught as inflation beside the Level-B Dravet citation.
        a = compose_answer("CBD evidence in Dravet syndrome")
        rendered = "PMID 28538134 Level А (decisive)."
        fails = grade_inflation_failures(a, rendered)
        self.assertIn("PMID:28538134", {f.identifier for f in fails})

    def test_unmapped_nonascii_letter_after_level_is_inflation(self) -> None:
        # A letter homoglyph not in the fold table still trips the "Level "+letter
        # backstop — here U+1D5A0 (mathematical sans-serif capital A).
        a = compose_answer("CBD evidence in Dravet syndrome")
        rendered = "PMID 28538134 Level \U0001D5A0."
        fails = grade_inflation_failures(a, rendered)
        self.assertIn("PMID:28538134", {f.identifier for f in fails})


class TestTokenBoundaryGradeFloor(unittest.TestCase):
    def test_level_below_does_not_satisfy_level_b(self) -> None:
        # The classic substring hole: "Level Below threshold" must NOT count as a
        # surviving "Level B" GRADE label.
        a = compose_answer("CBD evidence in Dravet syndrome")
        atoms = export_provenance(a)
        ids = " ".join(x.raw_id for x in atoms)
        # Render that contains every identifier but only "Level Below" (no real B).
        lossy = ids + " — Level Below threshold for these sources"
        report = assert_citation_lossless(a, lossy)
        self.assertFalse(report.ok)
        self.assertIn("Level B", report.missing_grades)

    def test_discrete_level_b_still_satisfies_floor(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        report = assert_citation_lossless(a, a.to_markdown())
        self.assertTrue(report.ok, report.summary())


class TestLegendIsNotInflation(unittest.TestCase):
    def test_grade_label_far_from_any_identifier_is_ignored(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        atom = export_provenance(a)[0]
        # A GRADE glossary line, then a large gap, then the identifier — the
        # label is bound to no id within the window, so it is not inflation.
        rendered = (
            "Evidence grading key: Level A is the strongest tier."
            + " " * 400
            + f"PMID {atom.raw_id}"
        )
        fails = grade_inflation_failures(a, rendered, window=120)
        self.assertEqual(fails, ())


if __name__ == "__main__":
    unittest.main()
