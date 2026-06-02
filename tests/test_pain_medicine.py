"""Tests for the pain-medicine registry (spec 006 US1 / FR-001)."""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)
from cannavec_science.pain_medicine import (
    PainMedicineCitation,
    PainMedicineRow,
    PainMedicineTopic,
    all_pain_medicine_rows,
    detect_pain_medicine_mention,
    find_pain_medicine_rows,
    render_markdown,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_seven_rows(self):
        rows = all_pain_medicine_rows()
        self.assertGreaterEqual(len(rows), 7)

    def test_every_row_has_primary_citation(self):
        for r in all_pain_medicine_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(c.pmid or c.doi)

    def test_evidence_levels_make_sense(self):
        # SRs and Cochrane → Level A or B; cohort → C; experimental → C.
        for r in all_pain_medicine_rows():
            self.assertIn(
                r.evidence_level,
                {
                    EvidenceLevel.A,
                    EvidenceLevel.B,
                    EvidenceLevel.C,
                },
            )

    def test_topic_coverage(self):
        topics = {r.topic for r in all_pain_medicine_rows()}
        for t in (
            PainMedicineTopic.NASEM_FINDING,
            PainMedicineTopic.SR_CHRONIC_PAIN,
            PainMedicineTopic.SR_NEUROPATHIC,
            PainMedicineTopic.COCHRANE_REVIEW,
            PainMedicineTopic.COHORT_OBSERVATIONAL,
            PainMedicineTopic.IPD_META_ANALYSIS,
            PainMedicineTopic.EXPERIMENTAL_PAIN,
        ):
            self.assertIn(t, topics)

    def test_anchor_pmids_present(self):
        all_pmids = {
            c.pmid
            for r in all_pain_medicine_rows()
            for c in r.citations
            if c.pmid
        }
        for pmid in (
            "26103030",  # Whiting 2015 JAMA SR
            "29847469",  # Stockings 2018 PAIN SR
            "29513392",  # Mücke 2018 Cochrane neuropathic
            "31237829",  # Boehnke 2019 J Pain cohort
            "26362106",  # Andreae 2015 IPD-MA
        ):
            self.assertIn(pmid, all_pmids)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            PainMedicineRow(
                name="bogus",
                topic=PainMedicineTopic.NASEM_FINDING,
                claim_text="x",
                claim_type=ClaimType.CLINICAL_EFFICACY,
                evidence_level=EvidenceLevel.A,
                source_tier=SourceTier.SR_FLAGSHIP,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            PainMedicineRow(
                name="bogus",
                topic=PainMedicineTopic.NASEM_FINDING,
                claim_text="x",
                claim_type=ClaimType.CLINICAL_EFFICACY,
                evidence_level=EvidenceLevel.A,
                source_tier=SourceTier.SR_FLAGSHIP,
                citations=(PainMedicineCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_nasem_2017_chronic_pain(self):
        rows = detect_pain_medicine_mention(
            "NASEM 2017 cannabis chronic pain conclusive evidence"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PainMedicineTopic.NASEM_FINDING, topics)

    def test_whiting_jama_sr(self):
        rows = detect_pain_medicine_mention(
            "Whiting 2015 JAMA cannabis chronic pain systematic review"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PainMedicineTopic.SR_CHRONIC_PAIN, topics)

    def test_stockings_neuropathic(self):
        rows = detect_pain_medicine_mention(
            "Stockings 2018 cannabinoid neuropathic pain systematic review"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PainMedicineTopic.SR_NEUROPATHIC, topics)

    def test_mucke_cochrane(self):
        rows = detect_pain_medicine_mention(
            "nabiximols neuropathic pain Mücke Cochrane 2018"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PainMedicineTopic.COCHRANE_REVIEW, topics)

    def test_boehnke_cohort(self):
        rows = detect_pain_medicine_mention(
            "medical cannabis chronic pain prospective cohort Boehnke 2019"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PainMedicineTopic.COHORT_OBSERVATIONAL, topics)

    def test_andreae_ipd_ma(self):
        rows = detect_pain_medicine_mention(
            "Andreae 2015 IPD meta-analysis inhaled cannabis neuropathic pain"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PainMedicineTopic.IPD_META_ANALYSIS, topics)

    def test_experimental_pain_de_vita(self):
        rows = detect_pain_medicine_mention(
            "experimental pain laboratory cannabinoid de Vita 2018 systematic review"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PainMedicineTopic.EXPERIMENTAL_PAIN, topics)


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated_prompt(self):
        # Make sure CBD-Dravet prompt does NOT pull in pain rows.
        self.assertEqual(
            detect_pain_medicine_mention("CBD in Dravet syndrome RCT"),
            (),
        )

    def test_empty_prompt(self):
        self.assertEqual(detect_pain_medicine_mention(""), ())

    def test_pharmacokinetics_prompt_does_not_pull_pain(self):
        self.assertEqual(
            detect_pain_medicine_mention(
                "THC inhaled vs oral pharmacokinetics Tmax Cmax"
            ),
            (),
        )


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        for r in all_pain_medicine_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)
            self.assertEqual(claim.claim_type, r.claim_type)
            self.assertTrue(claim.sources)


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified(self):
        for r in all_pain_medicine_rows():
            self.assertTrue(r.last_verified)
            self.assertEqual(len(r.last_verified), 10)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        rows = find_pain_medicine_rows("sr_chronic_pain")
        self.assertTrue(rows)


class RendererTests(unittest.TestCase):
    def test_render_includes_section_header(self):
        rows = all_pain_medicine_rows()
        md = render_markdown(rows)
        self.assertIn("Pain medicine registry", md)

    def test_render_includes_whiting_pmid(self):
        rows = all_pain_medicine_rows()
        md = render_markdown(rows)
        self.assertIn("26103030", md)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_nasem_2017_query_surfaces_whiting(self):
        a = compose_answer(
            "NASEM 2017 cannabis chronic pain conclusive evidence finding"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("26103030", pmids)

    def test_mucke_cochrane_query_surfaces_pmid(self):
        a = compose_answer(
            "nabiximols neuropathic pain Mücke 2018 Cochrane review"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("29513392", pmids)

    def test_andreae_query_emits_at_least_one_claim(self):
        a = compose_answer(
            "Andreae 2015 IPD meta-analysis cannabis neuropathic pain"
        )
        self.assertGreaterEqual(len(a.claims), 1)


class BannedPatternPassTests(unittest.TestCase):
    def test_claim_text_does_not_trip_banned_patterns(self):
        # The pain-medicine claim_text MUST NOT trip any
        # banned-pattern detector — no entourage overclaim, no
        # marketing copy, no indica/sativa pharmacology framing.
        from cannavec_science.banned_patterns import detect_banned_patterns
        for r in all_pain_medicine_rows():
            hits = detect_banned_patterns(r.claim_text)
            self.assertFalse(
                hits,
                msg=f"row {r.name!r} claim_text trips banned-pattern: {hits}",
            )


if __name__ == "__main__":
    unittest.main()
