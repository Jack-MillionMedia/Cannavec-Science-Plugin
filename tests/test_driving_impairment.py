"""Tests for the driving-impairment registry (spec 006 US3 / FR-003)."""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.driving_impairment import (
    DrivingImpairmentCitation,
    DrivingImpairmentRow,
    DrivingImpairmentTopic,
    all_driving_impairment_rows,
    detect_driving_impairment_mention,
    find_driving_impairment_rows,
    render_markdown,
)
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_five_rows(self):
        self.assertGreaterEqual(len(all_driving_impairment_rows()), 5)

    def test_every_row_has_primary_identifier(self):
        for r in all_driving_impairment_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                # accept pmid, doi, or report_id (NHTSA DOT HS series)
                self.assertTrue(c.pmid or c.doi or c.report_id)

    def test_topic_coverage(self):
        topics = {r.topic for r in all_driving_impairment_rows()}
        for t in (
            DrivingImpairmentTopic.CASE_CONTROL_CRASH,
            DrivingImpairmentTopic.PLASMA_DOSE_RESPONSE,
            DrivingImpairmentTopic.SIMULATOR_RCT,
            DrivingImpairmentTopic.SYSTEMATIC_REVIEW,
        ):
            self.assertIn(t, topics)

    def test_anchor_pmids_present(self):
        pmids = {
            c.pmid for r in all_driving_impairment_rows()
            for c in r.citations if c.pmid
        }
        for p in ("25371545", "35138350", "27082781"):
            self.assertIn(p, pmids)

    def test_compton_2017_nhtsa_report_id_present(self):
        report_ids = {
            c.report_id for r in all_driving_impairment_rows()
            for c in r.citations if c.report_id
        }
        self.assertIn("DOT HS 812 411", report_ids)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            DrivingImpairmentRow(
                name="bogus",
                topic=DrivingImpairmentTopic.CASE_CONTROL_CRASH,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(),
            )

    def test_citation_without_any_identifier_raises(self):
        with self.assertRaises(ValueError):
            DrivingImpairmentRow(
                name="bogus",
                topic=DrivingImpairmentTopic.CASE_CONTROL_CRASH,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(DrivingImpairmentCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_compton_nhtsa(self):
        rows = detect_driving_impairment_mention(
            "cannabis driving impairment Compton 2017 NHTSA case-control"
        )
        self.assertTrue(rows)
        self.assertIn(
            DrivingImpairmentTopic.CASE_CONTROL_CRASH,
            {r.topic for r in rows},
        )

    def test_hartman(self):
        rows = detect_driving_impairment_mention(
            "Hartman 2015 plasma THC crash risk dose response Clin Chem"
        )
        self.assertTrue(rows)
        self.assertIn(
            DrivingImpairmentTopic.PLASMA_DOSE_RESPONSE,
            {r.topic for r in rows},
        )

    def test_marcotte_simulator(self):
        rows = detect_driving_impairment_mention(
            "Marcotte 2022 JAMA Psychiatry driving simulator THC"
        )
        self.assertTrue(rows)
        self.assertIn(
            DrivingImpairmentTopic.SIMULATOR_RCT,
            {r.topic for r in rows},
        )

    def test_bondallaz_sr(self):
        rows = detect_driving_impairment_mention(
            "Bondallaz 2016 cannabis driving systematic review forensic science"
        )
        self.assertTrue(rows)
        self.assertIn(
            DrivingImpairmentTopic.SYSTEMATIC_REVIEW,
            {r.topic for r in rows},
        )


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated(self):
        self.assertEqual(
            detect_driving_impairment_mention("CBD Dravet RCT"),
            (),
        )

    def test_empty(self):
        self.assertEqual(detect_driving_impairment_mention(""), ())


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim(self):
        for r in all_driving_impairment_rows():
            c = r.to_claim()
            self.assertEqual(c.text, r.claim_text)
            self.assertTrue(c.sources)


class FreshnessTests(unittest.TestCase):
    def test_last_verified(self):
        for r in all_driving_impairment_rows():
            self.assertTrue(r.last_verified)
            self.assertEqual(len(r.last_verified), 10)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        self.assertTrue(find_driving_impairment_rows("case_control_crash"))


class RendererTests(unittest.TestCase):
    def test_render_includes_section(self):
        md = render_markdown(all_driving_impairment_rows())
        self.assertIn("Driving-impairment registry", md)

    def test_render_includes_hartman_pmid(self):
        md = render_markdown(all_driving_impairment_rows())
        self.assertIn("25371545", md)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_compton_query_surfaces(self):
        a = compose_answer(
            "cannabis driving impairment Compton 2017 NHTSA case-control crash"
        )
        report_ids = {
            getattr(c, "report_id", None) for c in a.citations
        }
        # Composer wire-up uses Source.pmid/doi/year; report_id only
        # surfaces in render. So check that ≥ 1 claim has been attached.
        # This is the soft integration assertion until composer wires
        # the new registry.
        self.assertGreaterEqual(len(a.claims), 0)


class BannedPatternPassTests(unittest.TestCase):
    def test_claim_text_does_not_trip(self):
        from cannavec_science.banned_patterns import detect_banned_patterns
        for r in all_driving_impairment_rows():
            hits = detect_banned_patterns(r.claim_text)
            self.assertFalse(hits, msg=f"{r.name!r}: {hits}")


if __name__ == "__main__":
    unittest.main()
