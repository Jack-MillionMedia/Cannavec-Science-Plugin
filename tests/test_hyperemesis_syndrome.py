"""Tests for the cannabinoid hyperemesis syndrome registry
(spec 005 US3 / FR-003).
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)
from cannavec_science.hyperemesis_syndrome import (
    HyperemesisSyndromeCitation,
    HyperemesisSyndromeRow,
    HyperemesisSyndromeTopic,
    all_hyperemesis_syndrome_rows,
    detect_hyperemesis_syndrome_mention,
    find_hyperemesis_syndrome_rows,
    render_markdown,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_four_rows(self):
        rows = all_hyperemesis_syndrome_rows()
        self.assertGreaterEqual(len(rows), 4)

    def test_every_row_has_primary_citation(self):
        for r in all_hyperemesis_syndrome_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(c.pmid or c.doi)

    def test_every_row_caps_at_c_or_d(self):
        # CHS literature is case-series / consensus only; no Cochrane SR.
        for r in all_hyperemesis_syndrome_rows():
            self.assertIn(
                r.evidence_level,
                {EvidenceLevel.C, EvidenceLevel.D},
            )

    def test_topic_coverage(self):
        topics = {r.topic for r in all_hyperemesis_syndrome_rows()}
        for t in (
            HyperemesisSyndromeTopic.DIAGNOSTIC_CRITERIA,
            HyperemesisSyndromeTopic.ROME_IV,
            HyperemesisSyndromeTopic.CAPSAICIN_TREATMENT,
            HyperemesisSyndromeTopic.CYCLIC_VOMITING_DX,
        ):
            self.assertIn(t, topics)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            HyperemesisSyndromeRow(
                name="bogus",
                topic=HyperemesisSyndromeTopic.DIAGNOSTIC_CRITERIA,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            HyperemesisSyndromeRow(
                name="bogus",
                topic=HyperemesisSyndromeTopic.DIAGNOSTIC_CRITERIA,
                claim_text="x",
                claim_type=ClaimType.SAFETY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(HyperemesisSyndromeCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_chs_diagnostic_criteria(self):
        rows = detect_hyperemesis_syndrome_mention(
            "cannabinoid hyperemesis syndrome diagnostic criteria"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(HyperemesisSyndromeTopic.DIAGNOSTIC_CRITERIA, topics)

    def test_rome_iv(self):
        rows = detect_hyperemesis_syndrome_mention(
            "Rome IV functional GI cannabis hyperemesis cyclic vomiting"
        )
        self.assertTrue(rows)

    def test_capsaicin_treatment(self):
        rows = detect_hyperemesis_syndrome_mention(
            "capsaicin cream cannabis hyperemesis treatment"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(HyperemesisSyndromeTopic.CAPSAICIN_TREATMENT, topics)

    def test_cyclic_vomiting_differential(self):
        rows = detect_hyperemesis_syndrome_mention(
            "cyclic vomiting syndrome differential cannabis post-legalization"
        )
        self.assertTrue(rows)

    def test_hot_water_bathing(self):
        # Pathognomonic feature.
        rows = detect_hyperemesis_syndrome_mention(
            "compulsive hot water bathing cannabis hyperemesis"
        )
        self.assertTrue(rows)


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated_prompt(self):
        self.assertEqual(
            detect_hyperemesis_syndrome_mention(
                "Δ⁹-THC pharmacokinetics in healthy volunteers"
            ),
            (),
        )

    def test_empty_prompt(self):
        self.assertEqual(detect_hyperemesis_syndrome_mention(""), ())

    def test_general_nausea_does_not_fire(self):
        # Nausea / vomiting in CINV is a different topic — antiemetic
        # indication, not CHS — so the detector must not fire.
        rows = detect_hyperemesis_syndrome_mention(
            "dronabinol antiemetic chemotherapy nausea CINV"
        )
        self.assertEqual(rows, ())


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        for r in all_hyperemesis_syndrome_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_chs_query_returns_sorensen_2017(self):
        a = compose_answer(
            "cannabinoid hyperemesis syndrome diagnostic criteria"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("27567272", pmids)

    def test_chs_query_returns_allen_2004(self):
        a = compose_answer(
            "cannabinoid hyperemesis syndrome compulsive hot bathing"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("15082584", pmids)

    def test_capsaicin_query_returns_dezieck_2017(self):
        a = compose_answer(
            "capsaicin cream cannabinoid hyperemesis treatment"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("28215116", pmids)

    def test_static_caution_remains(self):
        # The existing v0.x static caution must continue to render
        # alongside the new registry row (no double-render collision).
        a = compose_answer(
            "cannabinoid hyperemesis syndrome diagnostic criteria"
        )
        md = a.to_markdown()
        self.assertIn("paradoxical", md.lower())


class RendererTests(unittest.TestCase):
    def test_render_includes_section_header(self):
        rows = all_hyperemesis_syndrome_rows()
        md = render_markdown(rows)
        self.assertIn("Cannabinoid hyperemesis syndrome registry", md)


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified(self):
        for r in all_hyperemesis_syndrome_rows():
            self.assertTrue(r.last_verified)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        rows = find_hyperemesis_syndrome_rows("diagnostic_criteria")
        self.assertTrue(rows)


if __name__ == "__main__":
    unittest.main()
