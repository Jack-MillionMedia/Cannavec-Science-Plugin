"""Tests for the cannabis use disorder & withdrawal registry
(spec 005 US2 / FR-002).
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)
from cannavec_science.use_disorder import (
    UseDisorderCitation,
    UseDisorderRow,
    UseDisorderTopic,
    all_use_disorder_rows,
    detect_use_disorder_mention,
    find_use_disorder_rows,
    render_markdown,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_six_rows(self):
        rows = all_use_disorder_rows()
        self.assertGreaterEqual(len(rows), 6)

    def test_every_row_has_primary_citation(self):
        for r in all_use_disorder_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(c.pmid or c.doi)

    def test_every_row_caps_grade_at_c(self):
        for r in all_use_disorder_rows():
            # Outcome-instrument rows + epidemiology cap at C.
            self.assertIn(
                r.evidence_level,
                {EvidenceLevel.C, EvidenceLevel.D},
            )

    def test_topic_coverage(self):
        topics = {r.topic for r in all_use_disorder_rows()}
        for t in (
            UseDisorderTopic.DSM5_CRITERIA,
            UseDisorderTopic.SCREENING_INSTRUMENT,
            UseDisorderTopic.WITHDRAWAL_SCALE,
            UseDisorderTopic.PREVALENCE,
            UseDisorderTopic.HERITABILITY,
            UseDisorderTopic.AGE_OF_ONSET,
        ):
            self.assertIn(t, topics)

    def test_instrument_name_populated(self):
        # Every row's instrument_name field carries the named
        # outcome instrument the row addresses.
        for r in all_use_disorder_rows():
            self.assertTrue(r.instrument_name)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            UseDisorderRow(
                name="bogus",
                topic=UseDisorderTopic.DSM5_CRITERIA,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            UseDisorderRow(
                name="bogus",
                topic=UseDisorderTopic.DSM5_CRITERIA,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(UseDisorderCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_dsm5_cud_criteria(self):
        rows = detect_use_disorder_mention(
            "cannabis use disorder DSM-5 criteria"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(UseDisorderTopic.DSM5_CRITERIA, topics)

    def test_cudit_r(self):
        rows = detect_use_disorder_mention(
            "CUDIT-R cannabis use disorder identification test revised"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(UseDisorderTopic.SCREENING_INSTRUMENT, topics)

    def test_cannabis_withdrawal_scale(self):
        rows = detect_use_disorder_mention(
            "Cannabis Withdrawal Scale Allsop 2011"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(UseDisorderTopic.WITHDRAWAL_SCALE, topics)

    def test_nesarc_prevalence(self):
        rows = detect_use_disorder_mention(
            "NESARC-III cannabis use disorder prevalence Hasin 2015"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(UseDisorderTopic.PREVALENCE, topics)

    def test_heritability(self):
        rows = detect_use_disorder_mention(
            "cannabis use disorder heritability twin study Verweij 2010"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(UseDisorderTopic.HERITABILITY, topics)

    def test_adolescent_onset(self):
        rows = detect_use_disorder_mention(
            "adolescent-onset cannabis use telescoping dependence"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(UseDisorderTopic.AGE_OF_ONSET, topics)


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated_prompt(self):
        self.assertEqual(
            detect_use_disorder_mention("CBD in Dravet syndrome RCT"),
            (),
        )

    def test_empty_prompt(self):
        self.assertEqual(detect_use_disorder_mention(""), ())


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        for r in all_use_disorder_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)
            self.assertEqual(claim.claim_type, r.claim_type)
            self.assertTrue(claim.sources)


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified(self):
        for r in all_use_disorder_rows():
            self.assertTrue(r.last_verified)
            self.assertEqual(len(r.last_verified), 10)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        rows = find_use_disorder_rows("dsm5_criteria")
        self.assertTrue(rows)


class RendererTests(unittest.TestCase):
    def test_render_includes_section_header(self):
        rows = all_use_disorder_rows()
        md = render_markdown(rows)
        self.assertIn("Cannabis use disorder & withdrawal registry", md)

    def test_render_includes_dsm5_pmid(self):
        rows = all_use_disorder_rows()
        md = render_markdown(rows)
        self.assertIn("23903334", md)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_dsm5_criteria_query_surfaces_hasin_2013(self):
        a = compose_answer("cannabis use disorder DSM-5 criteria framework")
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("23903334", pmids)

    def test_cws_query_surfaces_allsop_2011(self):
        a = compose_answer("cannabis withdrawal syndrome assessment scale Allsop")
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("21652129", pmids)

    def test_volkow_2014_continues_to_fire_on_cud_query(self):
        # The existing v0.3 adverse-events Volkow CUD-risk row must
        # continue to fire alongside the new DSM-5 framework row.
        a = compose_answer("cannabis use disorder DSM-5 criteria adolescent")
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("23903334", pmids)
        self.assertIn("24897085", pmids)


if __name__ == "__main__":
    unittest.main()
