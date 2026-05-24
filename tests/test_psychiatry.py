"""Tests for the psychiatry / cannabis-psychosis registry
(spec 006 US2 / FR-002)."""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)
from cannavec_science.psychiatry import (
    PsychiatryCitation,
    PsychiatryRow,
    PsychiatryTopic,
    all_psychiatry_rows,
    detect_psychiatry_mention,
    find_psychiatry_rows,
    render_markdown,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_six_rows(self):
        rows = all_psychiatry_rows()
        self.assertGreaterEqual(len(rows), 6)

    def test_every_row_has_primary_citation(self):
        for r in all_psychiatry_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(c.pmid or c.doi)

    def test_evidence_levels_make_sense(self):
        for r in all_psychiatry_rows():
            self.assertIn(
                r.evidence_level,
                {EvidenceLevel.A, EvidenceLevel.B, EvidenceLevel.C, EvidenceLevel.D},
            )

    def test_topic_coverage(self):
        topics = {r.topic for r in all_psychiatry_rows()}
        for t in (
            PsychiatryTopic.CASE_CONTROL_PSYCHOSIS,
            PsychiatryTopic.DOSE_RESPONSE_SR,
            PsychiatryTopic.MR_CAUSALITY,
            PsychiatryTopic.ACUTE_PHARMACOLOGY,
            PsychiatryTopic.NATIONAL_COHORT,
            PsychiatryTopic.REVIEW_LANCET,
        ):
            self.assertIn(t, topics)

    def test_anchor_pmids_present(self):
        all_pmids = {
            c.pmid for r in all_psychiatry_rows() for c in r.citations if c.pmid
        }
        for pmid in (
            "30902669",  # Di Forti 2019 EU-GEI
            "26884547",  # Marconi 2016 SR
            "29039420",  # Vaucher 2018 MR
        ):
            self.assertIn(pmid, all_pmids)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            PsychiatryRow(
                name="bogus",
                topic=PsychiatryTopic.CASE_CONTROL_PSYCHOSIS,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.JOURNAL_RCT,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            PsychiatryRow(
                name="bogus",
                topic=PsychiatryTopic.CASE_CONTROL_PSYCHOSIS,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.JOURNAL_RCT,
                citations=(PsychiatryCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_di_forti_eu_gei(self):
        rows = detect_psychiatry_mention(
            "high potency cannabis psychosis Di Forti EU-GEI Lancet Psychiatry"
        )
        self.assertTrue(rows)
        self.assertIn(
            PsychiatryTopic.CASE_CONTROL_PSYCHOSIS,
            {r.topic for r in rows},
        )

    def test_marconi_dose_response(self):
        rows = detect_psychiatry_mention(
            "Marconi 2016 cannabis psychosis dose response meta-analysis"
        )
        self.assertTrue(rows)
        self.assertIn(
            PsychiatryTopic.DOSE_RESPONSE_SR,
            {r.topic for r in rows},
        )

    def test_vaucher_mr(self):
        rows = detect_psychiatry_mention(
            "Vaucher 2018 Mendelian randomization cannabis schizophrenia"
        )
        self.assertTrue(rows)
        self.assertIn(
            PsychiatryTopic.MR_CAUSALITY,
            {r.topic for r in rows},
        )

    def test_bhattacharyya_fmri(self):
        rows = detect_psychiatry_mention(
            "acute THC fMRI prefrontal cortex Bhattacharyya 2009 healthy volunteer"
        )
        self.assertTrue(rows)
        self.assertIn(
            PsychiatryTopic.ACUTE_PHARMACOLOGY,
            {r.topic for r in rows},
        )

    def test_hjorthoj_register(self):
        rows = detect_psychiatry_mention(
            "Hjorthøj 2023 cannabis schizophrenia national register Denmark"
        )
        self.assertTrue(rows)
        self.assertIn(
            PsychiatryTopic.NATIONAL_COHORT,
            {r.topic for r in rows},
        )

    def test_murray_lancet_review(self):
        rows = detect_psychiatry_mention(
            "Murray 2017 Lancet Psychiatry cannabis psychosis review"
        )
        self.assertTrue(rows)
        self.assertIn(
            PsychiatryTopic.REVIEW_LANCET,
            {r.topic for r in rows},
        )


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated_prompt(self):
        self.assertEqual(
            detect_psychiatry_mention("CBD in Dravet syndrome RCT"),
            (),
        )

    def test_pharmacokinetics_prompt(self):
        self.assertEqual(
            detect_psychiatry_mention(
                "THC inhaled vs oral pharmacokinetics Tmax Cmax"
            ),
            (),
        )

    def test_empty(self):
        self.assertEqual(detect_psychiatry_mention(""), ())


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        for r in all_psychiatry_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)
            self.assertEqual(claim.claim_type, r.claim_type)
            self.assertTrue(claim.sources)


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified(self):
        for r in all_psychiatry_rows():
            self.assertTrue(r.last_verified)
            self.assertEqual(len(r.last_verified), 10)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        rows = find_psychiatry_rows("case_control_psychosis")
        self.assertTrue(rows)


class RendererTests(unittest.TestCase):
    def test_render_includes_section_header(self):
        rows = all_psychiatry_rows()
        md = render_markdown(rows)
        self.assertIn("Psychiatry registry", md)

    def test_render_includes_di_forti_pmid(self):
        rows = all_psychiatry_rows()
        md = render_markdown(rows)
        self.assertIn("30902669", md)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_di_forti_query_surfaces_pmid(self):
        a = compose_answer(
            "high potency cannabis psychosis Di Forti EU-GEI Lancet Psychiatry"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("30902669", pmids)


class BannedPatternPassTests(unittest.TestCase):
    def test_claim_text_does_not_trip_banned_patterns(self):
        from cannavec_science.banned_patterns import detect_banned_patterns
        for r in all_psychiatry_rows():
            hits = detect_banned_patterns(r.claim_text)
            self.assertFalse(hits, msg=f"row {r.name!r} trips: {hits}")


if __name__ == "__main__":
    unittest.main()
