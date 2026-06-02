"""Tests for the eCBome enzyme-inhibitor pharmacology registry
(spec 005 US4 / FR-004).
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.ecbome import detect_ecbome_mention
from cannavec_science.ecbome_inhibitors import (
    EcbomeInhibitorCitation,
    EcbomeInhibitorRow,
    EcbomeInhibitorTopic,
    all_ecbome_inhibitor_rows,
    detect_ecbome_inhibitor_mention,
    find_ecbome_inhibitor_rows,
    render_markdown,
)
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_five_rows(self):
        rows = all_ecbome_inhibitor_rows()
        self.assertGreaterEqual(len(rows), 5)

    def test_every_row_has_primary_citation(self):
        for r in all_ecbome_inhibitor_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(c.pmid or c.doi)

    def test_topic_coverage(self):
        topics = {r.topic for r in all_ecbome_inhibitor_rows()}
        for t in (
            EcbomeInhibitorTopic.FAAH_INHIBITOR_EFFICACY,
            EcbomeInhibitorTopic.FAAH_INHIBITOR_SAFETY_DISASTER,
            EcbomeInhibitorTopic.MAGL_INHIBITOR,
            EcbomeInhibitorTopic.DUAL_INHIBITOR,
        ):
            self.assertIn(t, topics)

    def test_every_row_has_target_protein(self):
        for r in all_ecbome_inhibitor_rows():
            self.assertTrue(r.target_protein)

    def test_every_row_has_compound_id(self):
        for r in all_ecbome_inhibitor_rows():
            self.assertTrue(r.compound_id)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            EcbomeInhibitorRow(
                name="bogus",
                topic=EcbomeInhibitorTopic.FAAH_INHIBITOR_EFFICACY,
                claim_text="x",
                claim_type=ClaimType.CLINICAL_EFFICACY,
                evidence_level=EvidenceLevel.B,
                source_tier=SourceTier.JOURNAL_RCT,
                citations=(),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_pf_04457845(self):
        rows = detect_ecbome_inhibitor_mention(
            "PF-04457845 FAAH inhibitor cannabis withdrawal"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(EcbomeInhibitorTopic.FAAH_INHIBITOR_EFFICACY, topics)

    def test_bia_10_2474_disaster(self):
        rows = detect_ecbome_inhibitor_mention(
            "BIA 10-2474 Rennes Phase 1 disaster Kerbrat 2016"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(
            EcbomeInhibitorTopic.FAAH_INHIBITOR_SAFETY_DISASTER, topics
        )

    def test_magl_inhibitor(self):
        rows = detect_ecbome_inhibitor_mention(
            "MAGL inhibitor ABX-1431 monoacylglycerol lipase"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(EcbomeInhibitorTopic.MAGL_INHIBITOR, topics)

    def test_dual_inhibitor(self):
        rows = detect_ecbome_inhibitor_mention(
            "dual FAAH MAGL inhibitor JZL195 Long 2009"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(EcbomeInhibitorTopic.DUAL_INHIBITOR, topics)


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated_prompt(self):
        self.assertEqual(
            detect_ecbome_inhibitor_mention("CBD in Dravet syndrome RCT"),
            (),
        )

    def test_static_ecbome_reference_alone_does_not_fire(self):
        # Querying for FAAH per se (without an inhibitor) should hit
        # the eCBome reference registry but NOT the inhibitor registry.
        rows = detect_ecbome_inhibitor_mention("FAAH endocannabinoid hydrolase")
        self.assertEqual(rows, ())


class BiaDisambiguationTests(unittest.TestCase):
    """The BIA 10-2474 row MUST explicitly distinguish off-target
    serine-hydrolase inhibition from on-target FAAH biology.
    """

    def test_bia_row_mentions_off_target(self):
        rows = [
            r for r in all_ecbome_inhibitor_rows()
            if r.topic == EcbomeInhibitorTopic.FAAH_INHIBITOR_SAFETY_DISASTER
        ]
        self.assertTrue(rows)
        for r in rows:
            text_lower = r.claim_text.lower()
            self.assertIn("off-target", text_lower)
            # van Esbroeck 2017 is the activity-based protein profiling
            # citation that proved the off-target mechanism.
            pmids = {c.pmid for c in r.citations}
            self.assertIn("28596366", pmids)

    def test_bia_row_carries_kerbrat_2016(self):
        rows = [
            r for r in all_ecbome_inhibitor_rows()
            if r.topic == EcbomeInhibitorTopic.FAAH_INHIBITOR_SAFETY_DISASTER
        ]
        for r in rows:
            pmids = {c.pmid for c in r.citations}
            self.assertIn("27806235", pmids)


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        for r in all_ecbome_inhibitor_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_pf_04457845_query_returns_dsouza_2019(self):
        a = compose_answer(
            "PF-04457845 FAAH inhibitor cannabis withdrawal NEJM"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("30528676", pmids)

    def test_bia_query_returns_disaster_row(self):
        a = compose_answer("BIA 10-2474 Rennes Phase 1 disaster")
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("27806235", pmids)
        self.assertIn("28596366", pmids)
        # The off-target disambiguation must appear in the rendered text.
        self.assertIn("off-target", a.to_markdown().lower())

    def test_ecbome_reference_and_inhibitor_coexist(self):
        # A query that names both should surface BOTH the eCBome
        # static reference AND the inhibitor registry rows.
        prompt = "PF-04457845 FAAH inhibitor endocannabinoid tone"
        a = compose_answer(prompt)
        self.assertTrue(detect_ecbome_inhibitor_mention(prompt))
        # And the existing eCBome reference (FAAH entry) also fires.
        self.assertTrue(detect_ecbome_mention(prompt))


class RendererTests(unittest.TestCase):
    def test_render_includes_section_header(self):
        rows = all_ecbome_inhibitor_rows()
        md = render_markdown(rows)
        self.assertIn("eCBome inhibitor pharmacology registry", md)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        rows = find_ecbome_inhibitor_rows("magl_inhibitor")
        self.assertTrue(rows)


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified(self):
        for r in all_ecbome_inhibitor_rows():
            self.assertTrue(r.last_verified)


if __name__ == "__main__":
    unittest.main()
