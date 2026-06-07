"""Per-citation GRADE is derived from the SURVIVING claims at serialization and
survives the save->re-export round-trip (critical-path #6a, §XI / §I / §VII).

Two coupled requirements:
1. A curated answer's cited PMID serializes its real grade, so the save->
   re-export bibliography path stays GRADE-lossless (the original defect:
   ``citations[].grade == null`` because dedup dropped the graded copy).
2. A citation whose claim was DROPPED after attach (e.g. a wrong-indication
   efficacy claim removed by the off-KB gate, whose citation is retained for the
   bibliography under §I) must serialize ``grade=null`` — never an orphaned
   Level-A/B stamp. A "no curated evidence for X" answer must NOT export a
   Level-A-graded bibliography for X (the citation->claim binding lie this
   project exists to prevent).

The two grade-resolution paths (``Answer.to_dict`` and
``bibliography._evidence_level_for_citation``) must therefore AGREE.

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import Answer, Citation, compose_answer
from cannavec_science.evidence import (
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
)


class TestCuratedAnswerSerializesCitationGrade(unittest.TestCase):
    """A curated efficacy answer serializes the real grade on its cited PMID."""

    def test_dravet_citation_grade_in_json(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        cites = {c["pmid"]: c for c in a.to_dict()["citations"] if c.get("pmid")}
        self.assertIn("28538134", cites, "Devinsky 2017 citation missing")
        self.assertEqual(
            cites["28538134"]["grade"], "Level B",
            f"per-citation grade lost in serialization: {cites['28538134']}",
        )

    def test_roundtrip_bibliography_keeps_grade_note(self) -> None:
        from cannavec_science.bibliography import _entry_from_citation, render_bibtex
        a = compose_answer("CBD evidence in Dravet syndrome")
        payload = a.to_dict()
        rebuilt = [
            Citation(
                label=c["label"], pmid=c.get("pmid"), doi=c.get("doi"),
                url=c.get("url"), year=c.get("year"),
                grade=EvidenceLevel(c["grade"]) if c.get("grade") else None,
            )
            for c in payload["citations"]
        ]
        entries = []
        for c in rebuilt:
            e = _entry_from_citation(c, answer=None)
            if c.grade is not None:
                e = e.__class__(**{**e.__dict__, "evidence_level": c.grade.value})
            entries.append(e)
        bibtex = render_bibtex(entries)
        self.assertIn("Cannavec GRADE: Level B", bibtex,
                      "save->re-export dropped the GRADE note")


class TestDroppedClaimGradeNotOrphaned(unittest.TestCase):
    """A citation whose claim was dropped must NOT carry an orphaned grade."""

    def test_uncurated_indication_citations_have_no_orphaned_grade(self) -> None:
        # "CBD for Tourette" drops the wrong-indication efficacy claims but keeps
        # their citations (§I). Those citations must serialize grade=null — never
        # the Level A/B the dropped claim would have stamped.
        a = compose_answer("What is the evidence for CBD in Tourette syndrome?")
        d = a.to_dict()
        self.assertIn("no curated", d["short_answer"].lower(), d["short_answer"])
        cites = {c.get("pmid"): c["grade"] for c in d["citations"]}
        # The neuropathic-pain SRs were graded Level A ONLY by the dropped
        # wrong-indication efficacy claims — they must now serialize null
        # (the orphan the round-trip used to stamp onto a Tourette bibliography).
        for pmid in ("29513392", "29847469", "26103030", "29307505"):
            self.assertIsNone(
                cites.get(pmid),
                f"orphaned grade on dropped-efficacy citation {pmid}: "
                f"{cites.get(pmid)}",
            )
        # No citation may carry an efficacy-tier grade (A/B) on a no-curated-
        # evidence answer — any surviving grade is adjacent (e.g. a Level-C
        # safety claim), never the dropped efficacy claim's A/B.
        self.assertEqual(
            {g for g in cites.values() if g in ("Level A", "Level B")}, set(),
            f"efficacy-grade orphan on a no-curated-evidence answer: {cites}",
        )

    def test_dropping_a_claim_unsets_its_citation_grade(self) -> None:
        # Unit-level: a citation's serialized grade tracks the CURRENT claims.
        a = Answer(prompt="x")
        claim = Claim(
            text="cannabidiol has trial-supported evidence for convulsive seizures",
            claim_type=ClaimType.CLINICAL_EFFICACY,
            population="paediatric Dravet syndrome",
            sources=(Source(title="Devinsky 2017", tier=SourceTier.JOURNAL_RCT,
                            pmid="28538134", year=2017),),
        )
        a.add_claim(claim)
        before = {c["pmid"]: c["grade"] for c in a.to_dict()["citations"]
                  if c.get("pmid")}
        self.assertIsNotNone(before.get("28538134"),
                             "graded claim should grade its citation")
        # Drop the claim (as the off-KB gate does); citation stays (§I).
        a.claims = []
        after = {c["pmid"]: c["grade"] for c in a.to_dict()["citations"]
                 if c.get("pmid")}
        self.assertIn("28538134", after, "citation should be retained")
        self.assertIsNone(after["28538134"],
                          "grade must clear when its claim is gone")


class TestGradePathsAgree(unittest.TestCase):
    """to_dict's serialized grade must equal the bibliography claim-walk grade
    for every citation — the two resolution paths cannot disagree."""

    def _check(self, prompt: str) -> None:
        from cannavec_science.bibliography import _evidence_level_for_citation
        a = compose_answer(prompt)
        serialized = {
            c["pmid"]: c["grade"] for c in a.to_dict()["citations"] if c.get("pmid")
        }
        for c in a.citations:
            if not c.pmid:
                continue
            walk = _evidence_level_for_citation(a, c)
            self.assertEqual(
                serialized.get(c.pmid), walk,
                f"grade path disagreement for {c.pmid} in {prompt!r}: "
                f"serialized={serialized.get(c.pmid)} claim-walk={walk}",
            )

    def test_curated_query_paths_agree(self) -> None:
        self._check("CBD evidence in Dravet syndrome")

    def test_uncurated_query_paths_agree(self) -> None:
        self._check("What is the evidence for CBD in Tourette syndrome?")

    def test_autism_query_paths_agree(self) -> None:
        # A second off-KB indication that reaches a DIFFERENT bottom line (a
        # surviving Level-C curated claim, not the "no curated efficacy"
        # override) — the serialized grade must still equal the claim-walk
        # re-resolution for every citation, with no orphaned A/B grade.
        self._check("What is the evidence for CBD in autism spectrum disorder?")

    def test_markdown_citations_grade_matches_json(self) -> None:
        # The Markdown "## Citations" section and the JSON citations[] must show
        # the same per-citation grade (both recomputed from surviving claims).
        a = compose_answer("CBD evidence in Dravet syndrome")
        md = a.to_markdown()
        cites = {c["pmid"]: c["grade"] for c in a.to_dict()["citations"]
                 if c.get("pmid")}
        self.assertEqual(cites.get("28538134"), "Level B")
        # The Markdown Citations line for the Dravet trial must carry "Level B".
        cite_section = md.split("## Citations", 1)[-1]
        dravet_line = next(
            (ln for ln in cite_section.splitlines() if "28538134" in ln), ""
        )
        self.assertIn("Level B", dravet_line,
                      f"Markdown citation grade missing/mismatched: {dravet_line!r}")


if __name__ == "__main__":
    unittest.main()
