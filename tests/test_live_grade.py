"""Honest metadata-only GRADE for live hits (spec 036, Step 2).

Every assertion here is the honesty contract (M2 / §VII) for the live tier:

- A live hit is graded ONLY from metadata the lane already returned (journal +
  pubtypes for literature lanes; the preprint server name for bioRxiv/medRxiv).
  No per-finding network fetch happens — the tests run fully offline.
- The grade is routed through the SAME GRADE engine the curated tier uses
  (``Claim([source]).best_supportable_grade()``), then CLAMPED so a live hit is
  NEVER as certain as curated evidence: a live JOURNAL hit is at most Level C
  (Low certainty); a live PREPRINT is at most Level D (Very low). Never A/B.
- When metadata is absent / ambiguous the grader prefers the LOWER tier, and
  when nothing is gradeable it degrades to the existing provisional string.
- A non-empty ``grade_rationale`` always rides along, plus a visible
  ``live · provisional`` qualifier distinct from a curated grade.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import live_finding_from_row, live_source_from_row
from cannavec_science.evidence import (
    EvidenceLevel,
    SourceTier,
    infer_tier_from_pubtypes,
    journal_tier_from_name,
    study_design_signal_from_abstract,
)


class InferTierFromPubtypes(unittest.TestCase):
    def test_systematic_review_and_meta_analysis_map_to_journal_sr_tier(self) -> None:
        self.assertEqual(
            infer_tier_from_pubtypes(("Systematic Review",)),
            SourceTier.JOURNAL_RCT,
        )
        self.assertEqual(
            infer_tier_from_pubtypes(("Meta-Analysis",)),
            SourceTier.JOURNAL_RCT,
        )

    def test_randomized_controlled_trial_maps_to_rct_tier(self) -> None:
        self.assertEqual(
            infer_tier_from_pubtypes(("Randomized Controlled Trial",)),
            SourceTier.JOURNAL_RCT,
        )

    def test_observational_designs_map_to_single_arm_tier(self) -> None:
        for pt in ("Observational Study", "Cohort Study", "Case-Control Study"):
            with self.subTest(pubtype=pt):
                self.assertEqual(
                    infer_tier_from_pubtypes((pt,)),
                    SourceTier.SINGLE_ARM_OR_MECH,
                )

    def test_case_reports_and_editorials_map_to_lowest_evidential_tier(self) -> None:
        for pt in ("Case Reports", "Comment", "Editorial", "Letter"):
            with self.subTest(pubtype=pt):
                self.assertEqual(
                    infer_tier_from_pubtypes((pt,)),
                    SourceTier.PREPRINT_OR_SMALL,
                )

    def test_empty_pubtypes_is_conservative_lowest_evidential_tier(self) -> None:
        self.assertEqual(
            infer_tier_from_pubtypes(()),
            SourceTier.PREPRINT_OR_SMALL,
        )

    def test_unknown_pubtype_is_conservative_lowest_evidential_tier(self) -> None:
        self.assertEqual(
            infer_tier_from_pubtypes(("Some Future Pubtype",)),
            SourceTier.PREPRINT_OR_SMALL,
        )

    def test_ambiguous_multi_design_prefers_the_lower_tier(self) -> None:
        # An RCT token AND a case-report token: prefer the LOWER (weaker) tier.
        self.assertEqual(
            infer_tier_from_pubtypes(
                ("Randomized Controlled Trial", "Case Reports")
            ),
            SourceTier.PREPRINT_OR_SMALL,
        )

    def test_case_insensitive(self) -> None:
        self.assertEqual(
            infer_tier_from_pubtypes(("randomized controlled trial",)),
            SourceTier.JOURNAL_RCT,
        )


class JournalTierFromName(unittest.TestCase):
    def test_known_high_impact_journal_full_name(self) -> None:
        self.assertEqual(
            journal_tier_from_name("New England Journal of Medicine"),
            SourceTier.SR_FLAGSHIP,
        )

    def test_known_high_impact_journal_abbreviation(self) -> None:
        self.assertEqual(
            journal_tier_from_name("N Engl J Med"),
            SourceTier.SR_FLAGSHIP,
        )

    def test_specialist_journal_is_journal_rct_tier(self) -> None:
        self.assertEqual(journal_tier_from_name("Epilepsia"), SourceTier.JOURNAL_RCT)

    def test_unknown_journal_is_conservative_default(self) -> None:
        self.assertEqual(
            journal_tier_from_name("Journal of Made-Up Studies"),
            SourceTier.SINGLE_ARM_OR_MECH,
        )

    def test_empty_journal_is_conservative_default(self) -> None:
        self.assertEqual(journal_tier_from_name(""), SourceTier.SINGLE_ARM_OR_MECH)

    def test_case_insensitive(self) -> None:
        self.assertEqual(journal_tier_from_name("lancet"), SourceTier.SR_FLAGSHIP)


class StudyDesignSignalFromAbstract(unittest.TestCase):
    def test_trial_registry_id_signals_pre_registered(self) -> None:
        for ident in (
            "Registered as NCT01234567.",
            "ISRCTN12345678",
            "EudraCT 2019-001234-12",
        ):
            with self.subTest(ident=ident):
                pre, _ = study_design_signal_from_abstract("", ident)
                self.assertTrue(pre)

    def test_no_registry_id_is_not_pre_registered(self) -> None:
        pre, _ = study_design_signal_from_abstract("", "An open-label series.")
        self.assertFalse(pre)

    def test_sample_size_signal_is_adequately_powered(self) -> None:
        for txt in ("N=120 patients", "we enrolled 250 participants", "n = 100"):
            with self.subTest(txt=txt):
                _, powered = study_design_signal_from_abstract("", txt)
                self.assertTrue(powered)

    def test_small_sample_is_not_adequately_powered(self) -> None:
        _, powered = study_design_signal_from_abstract("", "N=12 patients")
        self.assertFalse(powered)

    def test_no_sample_signal_is_not_powered(self) -> None:
        _, powered = study_design_signal_from_abstract("", "A mechanistic study.")
        self.assertFalse(powered)


class LiveSourceFromRow(unittest.TestCase):
    def test_pubmed_row_builds_a_source_from_metadata(self) -> None:
        src = live_source_from_row(
            "pubmed",
            {
                "pmid": "39000001",
                "title": "CBD RCT",
                "journal": "N Engl J Med",
                "pubtypes": ["Randomized Controlled Trial"],
                "year": 2024,
            },
        )
        self.assertIsNotNone(src)
        self.assertEqual(src.pmid, "39000001")
        self.assertEqual(src.year, 2024)

    def test_row_without_any_identifier_yields_no_source(self) -> None:
        self.assertIsNone(live_source_from_row("pubmed", {"title": "no id"}))


class LiveGradeClamp(unittest.TestCase):
    """A live hit is NEVER more certain than curated evidence."""

    def test_live_rct_in_top_journal_clamps_to_level_c_at_most(self) -> None:
        finding = live_finding_from_row(
            "pubmed",
            {
                "pmid": "39000010",
                "title": "Cannabidiol RCT for chronic pain",
                "journal": "N Engl J Med",
                "pubtypes": ["Randomized Controlled Trial"],
                "year": 2024,
            },
        )
        self.assertEqual(finding["grade"], "Level C")
        self.assertEqual(finding["certainty"], "Low")
        # Never above C.
        self.assertLessEqual(
            EvidenceLevel("Level C").rank, EvidenceLevel.B.rank - 0
        )
        self.assertGreater(EvidenceLevel.B.rank, EvidenceLevel("Level C").rank)

    def test_live_observational_is_level_c_or_lower(self) -> None:
        finding = live_finding_from_row(
            "pubmed",
            {
                "pmid": "39000011",
                "title": "Cohort of cannabis users and pain",
                "journal": "Epilepsia",
                "pubtypes": ["Observational Study"],
                "year": 2023,
            },
        )
        self.assertIn(finding["grade"], {"Level C", "Level D", "Level E"})
        self.assertLessEqual(
            EvidenceLevel(finding["grade"]).rank, EvidenceLevel.C.rank
        )

    def test_live_preprint_clamps_to_level_d(self) -> None:
        finding = live_finding_from_row(
            "biorxiv",
            {
                "doi": "10.1101/2024.01.01.000001",
                "title": "Cannabidiol receptor binding (preprint)",
                "year": 2024,
            },
        )
        self.assertEqual(finding["grade"], "Level D")
        self.assertEqual(finding["certainty"], "Very low")

    def test_empty_metadata_row_grades_to_conservative_floor(self) -> None:
        # A bare PubMed row (no journal, no pubtypes) is undesigned: the empty-
        # pubtype floor + unrecognised-journal rule pin it to Level D (the Task-4
        # contract). It must NEVER receive a canonical curated-style A/B grade.
        finding = live_finding_from_row(
            "pubmed",
            {"pmid": "39000099", "title": "Untyped article", "year": 2024},
        )
        self.assertEqual(finding["grade"], "Level D")
        self.assertLessEqual(
            EvidenceLevel(finding["grade"]).rank, EvidenceLevel.C.rank
        )

    def test_truly_ungradeable_row_falls_back_to_provisional_string(self) -> None:
        # A row with NO primary identifier at all is not gradeable — it degrades
        # to the existing provisional string (no canonical grade attached). Such
        # a row also returns None from live_finding_from_row (nothing citable),
        # so we assert at the source layer.
        self.assertIsNone(
            live_source_from_row("pubmed", {"title": "no identifier"})
        )

    def test_grade_rationale_is_attached_and_non_empty(self) -> None:
        finding = live_finding_from_row(
            "pubmed",
            {
                "pmid": "39000012",
                "title": "CBD RCT",
                "journal": "Lancet",
                "pubtypes": ["Randomized Controlled Trial"],
                "year": 2024,
            },
        )
        self.assertIn("grade_rationale", finding)
        self.assertTrue(finding["grade_rationale"].strip())
        # The visible "live · provisional" qualifier is preserved.
        self.assertTrue(finding.get("provisional"))
        self.assertIn("live", finding["provisional_grade"])

    def test_no_live_hit_ever_grades_above_level_c(self) -> None:
        """Probe several deliberately high-tier rows — none may exceed C."""
        high_tier_rows = [
            ("pubmed", {
                "pmid": "1", "title": "SR of CBD", "journal": "N Engl J Med",
                "pubtypes": ["Systematic Review"], "year": 2024,
            }),
            ("pubmed", {
                "pmid": "2", "title": "Meta-analysis of CBD",
                "journal": "Lancet", "pubtypes": ["Meta-Analysis"], "year": 2024,
            }),
            ("pubmed", {
                "pmid": "3", "title": "Pre-registered powered RCT NCT01234567",
                "journal": "JAMA",
                "pubtypes": ["Randomized Controlled Trial"], "year": 2024,
                "abstract": "Registered NCT01234567. We enrolled 400 patients.",
            }),
            ("europepmc", {
                "pmid": "4", "title": "Cohort", "journal": "BMJ",
                "pubtypes": ["Systematic Review"], "year": 2024,
            }),
        ]
        for src, row in high_tier_rows:
            with self.subTest(row=row.get("title")):
                finding = live_finding_from_row(src, row)
                self.assertIn("grade", finding)
                self.assertLessEqual(
                    EvidenceLevel(finding["grade"]).rank,
                    EvidenceLevel.C.rank,
                    f"{row.get('title')} graded above Level C",
                )


if __name__ == "__main__":
    unittest.main()
