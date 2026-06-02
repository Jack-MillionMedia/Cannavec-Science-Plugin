"""Tests for the PTSD / anxiety / sleep registry (spec 006 US4 / FR-004)."""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)
from cannavec_science.ptsd_anxiety_sleep import (
    PtsdAnxietySleepCitation,
    PtsdAnxietySleepRow,
    PtsdAnxietySleepTopic,
    all_ptsd_anxiety_sleep_rows,
    detect_ptsd_anxiety_sleep_mention,
    find_ptsd_anxiety_sleep_rows,
    render_markdown,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_five_rows(self):
        self.assertGreaterEqual(len(all_ptsd_anxiety_sleep_rows()), 5)

    def test_every_row_has_primary_identifier(self):
        for r in all_ptsd_anxiety_sleep_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(c.pmid or c.doi)

    def test_topic_coverage(self):
        topics = {r.topic for r in all_ptsd_anxiety_sleep_rows()}
        for t in (
            PtsdAnxietySleepTopic.PTSD_RCT,
            PtsdAnxietySleepTopic.SAD_ACUTE_CHALLENGE,
            PtsdAnxietySleepTopic.SLEEP_SR,
            PtsdAnxietySleepTopic.ACUTE_ANXIETY_DOSE_RESPONSE,
        ):
            self.assertIn(t, topics)

    def test_anchor_pmids_present(self):
        pmids = {
            c.pmid for r in all_ptsd_anxiety_sleep_rows()
            for c in r.citations if c.pmid
        }
        for p in (
            "33730032",  # Bonn-Miller 2021 PTSD
            "20829306",  # Crippa 2011 CBD-SAD
            "21307846",  # Bergamaschi 2011 CBD-SAD
            "19897322",  # Bedi 2010 acute anxiety
            "28392485",  # Walsh 2017 sleep
        ):
            self.assertIn(p, pmids)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            PtsdAnxietySleepRow(
                name="bogus",
                topic=PtsdAnxietySleepTopic.PTSD_RCT,
                claim_text="x",
                claim_type=ClaimType.CLINICAL_EFFICACY,
                evidence_level=EvidenceLevel.B,
                source_tier=SourceTier.JOURNAL_RCT,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            PtsdAnxietySleepRow(
                name="bogus",
                topic=PtsdAnxietySleepTopic.PTSD_RCT,
                claim_text="x",
                claim_type=ClaimType.CLINICAL_EFFICACY,
                evidence_level=EvidenceLevel.B,
                source_tier=SourceTier.JOURNAL_RCT,
                citations=(PtsdAnxietySleepCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_bonn_miller_ptsd(self):
        rows = detect_ptsd_anxiety_sleep_mention(
            "Bonn-Miller 2021 PTSD cannabis randomized controlled trial PLOS"
        )
        self.assertTrue(rows)
        self.assertIn(
            PtsdAnxietySleepTopic.PTSD_RCT,
            {r.topic for r in rows},
        )

    def test_crippa_sad(self):
        rows = detect_ptsd_anxiety_sleep_mention(
            "CBD social anxiety disorder Crippa 2011 J Psychopharmacol"
        )
        self.assertTrue(rows)
        self.assertIn(
            PtsdAnxietySleepTopic.SAD_ACUTE_CHALLENGE,
            {r.topic for r in rows},
        )

    def test_walsh_sleep(self):
        rows = detect_ptsd_anxiety_sleep_mention(
            "cannabis sleep Walsh 2017 sleep medicine reviews systematic review"
        )
        self.assertTrue(rows)
        self.assertIn(
            PtsdAnxietySleepTopic.SLEEP_SR,
            {r.topic for r in rows},
        )

    def test_bedi_acute_anxiety(self):
        rows = detect_ptsd_anxiety_sleep_mention(
            "acute THC anxiety dose response Bedi 2010 drug alcohol depend"
        )
        self.assertTrue(rows)
        self.assertIn(
            PtsdAnxietySleepTopic.ACUTE_ANXIETY_DOSE_RESPONSE,
            {r.topic for r in rows},
        )


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated(self):
        self.assertEqual(
            detect_ptsd_anxiety_sleep_mention("CBD Dravet RCT"),
            (),
        )

    def test_empty(self):
        self.assertEqual(detect_ptsd_anxiety_sleep_mention(""), ())


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim(self):
        for r in all_ptsd_anxiety_sleep_rows():
            c = r.to_claim()
            self.assertEqual(c.text, r.claim_text)
            self.assertTrue(c.sources)


class FreshnessTests(unittest.TestCase):
    def test_last_verified(self):
        for r in all_ptsd_anxiety_sleep_rows():
            self.assertTrue(r.last_verified)
            self.assertEqual(len(r.last_verified), 10)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        self.assertTrue(find_ptsd_anxiety_sleep_rows("ptsd_rct"))


class RendererTests(unittest.TestCase):
    def test_render_includes_section(self):
        md = render_markdown(all_ptsd_anxiety_sleep_rows())
        self.assertIn("PTSD / anxiety / sleep registry", md)

    def test_render_includes_bonn_miller_pmid(self):
        md = render_markdown(all_ptsd_anxiety_sleep_rows())
        self.assertIn("33730032", md)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_bonn_miller_query_surfaces(self):
        a = compose_answer(
            "Bonn-Miller 2021 PTSD cannabis randomized controlled trial PLOS One"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("33730032", pmids)


class BannedPatternPassTests(unittest.TestCase):
    def test_claim_text_does_not_trip(self):
        from cannavec_science.banned_patterns import detect_banned_patterns
        for r in all_ptsd_anxiety_sleep_rows():
            hits = detect_banned_patterns(r.claim_text)
            self.assertFalse(hits, msg=f"{r.name!r}: {hits}")


if __name__ == "__main__":
    unittest.main()
