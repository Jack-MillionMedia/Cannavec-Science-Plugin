"""Tests for the cultivation-science registry (spec 004 US2 / FR-002)."""

from __future__ import annotations

import unittest

from cannavec_science.cultivation_science import (
    CultivationCitation,
    CultivationScienceRow,
    CultivationTopic,
    all_cultivation_science_rows,
    detect_cultivation_science_mention,
    find_cultivation_science_rows,
    render_markdown,
)
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_six_rows(self):
        # Constitution §III + spec 004 US2 / FR-002: ≥ 6 rows.
        rows = all_cultivation_science_rows()
        self.assertGreaterEqual(len(rows), 6)

    def test_every_row_has_a_primary_citation(self):
        for r in all_cultivation_science_rows():
            self.assertTrue(r.citations, f"{r.name}: empty citations")
            for c in r.citations:
                self.assertTrue(
                    c.pmid or c.doi,
                    f"{r.name}: citation {c.label!r} lacks PMID and DOI",
                )

    def test_every_row_has_an_evidence_level(self):
        for r in all_cultivation_science_rows():
            self.assertIsInstance(r.evidence_level, EvidenceLevel)
            # Cultivation primary literature caps at Level C (no Cochrane-
            # equivalent meta-analysis for botanical-taxonomy or synthase
            # genetics).
            self.assertIn(r.evidence_level, {EvidenceLevel.C, EvidenceLevel.D})

    def test_topic_distribution_covers_all_four(self):
        topics = {r.topic for r in all_cultivation_science_rows()}
        for t in (
            CultivationTopic.LIGHT_SPECTRUM,
            CultivationTopic.TRICHOME_BIOLOGY,
            CultivationTopic.SYNTHASE_GENETICS,
            CultivationTopic.BOTANICAL_TAXONOMY,
        ):
            self.assertIn(t, topics, f"missing topic {t}")


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            CultivationScienceRow(
                name="bogus",
                topic=CultivationTopic.LIGHT_SPECTRUM,
                claim_text="x",
                claim_type=ClaimType.CULTIVATION_PARAMETER,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            CultivationScienceRow(
                name="bogus",
                topic=CultivationTopic.LIGHT_SPECTRUM,
                claim_text="x",
                claim_type=ClaimType.CULTIVATION_PARAMETER,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(CultivationCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_uvb(self):
        rows = detect_cultivation_science_mention(
            "UV-B effect on cannabinoid biosynthesis"
        )
        topics = {r.topic for r in rows}
        self.assertIn(CultivationTopic.LIGHT_SPECTRUM, topics)

    def test_light_spectrum(self):
        rows = detect_cultivation_science_mention(
            "light spectrum cannabinoid yield"
        )
        topics = {r.topic for r in rows}
        self.assertIn(CultivationTopic.LIGHT_SPECTRUM, topics)

    def test_trichome_density(self):
        rows = detect_cultivation_science_mention(
            "trichome density cannabinoid yield"
        )
        topics = {r.topic for r in rows}
        self.assertIn(CultivationTopic.TRICHOME_BIOLOGY, topics)

    def test_thca_synthase(self):
        rows = detect_cultivation_science_mention(
            "THCA synthase CBDA synthase chemotype inheritance"
        )
        topics = {r.topic for r in rows}
        self.assertIn(CultivationTopic.SYNTHASE_GENETICS, topics)

    def test_botanical_taxonomy_one_species_three(self):
        rows = detect_cultivation_science_mention(
            "Is Cannabis sativa one species or three?"
        )
        topics = {r.topic for r in rows}
        self.assertIn(CultivationTopic.BOTANICAL_TAXONOMY, topics)

    def test_botanical_taxonomy_explicit_phrase(self):
        rows = detect_cultivation_science_mention(
            "Cannabis sativa L. botanical taxonomy"
        )
        topics = {r.topic for r in rows}
        self.assertIn(CultivationTopic.BOTANICAL_TAXONOMY, topics)


class DetectionNegativeTests(unittest.TestCase):
    def test_cbd_dravet_does_not_fire(self):
        rows = detect_cultivation_science_mention(
            "CBD evidence in Dravet syndrome"
        )
        self.assertEqual(rows, ())

    def test_indica_sativa_pharmacology_does_not_fire(self):
        # The indica/sativa-as-pharmacology framing routes to the banned-
        # pattern detector, NOT to cultivation_science.
        rows = detect_cultivation_science_mention(
            "indica vs sativa pharmacological differences"
        )
        self.assertEqual(rows, ())

    def test_decarb_kinetics_does_not_fire(self):
        # Decarb kinetics is analytical chemistry, not cultivation.
        rows = detect_cultivation_science_mention(
            "decarboxylation kinetics of THCA at 110 degrees C"
        )
        self.assertEqual(rows, ())

    def test_empty_string(self):
        self.assertEqual(detect_cultivation_science_mention(""), ())


class CoexistenceWithBannedPatternTests(unittest.TestCase):
    """Spec 004 US4 + US2 — botanical-taxonomy framing must escape the
    strengthened indica/sativa-as-pharmacology banned pattern."""

    def test_botany_taxonomy_does_not_fire_banned_pattern(self):
        from cannavec_science.banned_patterns import detect_banned_patterns
        hits = detect_banned_patterns("Cannabis sativa L. botanical taxonomy")
        self.assertEqual(hits, [])

    def test_one_species_or_three_does_not_fire_banned_pattern(self):
        from cannavec_science.banned_patterns import detect_banned_patterns
        hits = detect_banned_patterns(
            "Is Cannabis sativa one species or three?"
        )
        self.assertEqual(hits, [])

    def test_taxonomy_framing_does_not_fire_banned_pattern(self):
        from cannavec_science.banned_patterns import detect_banned_patterns
        hits = detect_banned_patterns("indica vs sativa taxonomy")
        self.assertEqual(hits, [])

    def test_pharmacology_framing_fires_banned_pattern(self):
        # Regression for US4 — the abstract pharmacology framing fires.
        from cannavec_science.banned_patterns import detect_banned_patterns
        hits = detect_banned_patterns(
            "indica vs sativa pharmacological differences"
        )
        self.assertTrue(hits)


class FindRowsTests(unittest.TestCase):
    def test_by_topic(self):
        rows = find_cultivation_science_rows("synthase_genetics")
        self.assertGreaterEqual(len(rows), 2)

    def test_by_partial_name(self):
        rows = find_cultivation_science_rows("trichome")
        self.assertGreaterEqual(len(rows), 1)


class ToClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        from cannavec_science.evidence import Claim
        row = all_cultivation_science_rows()[0]
        claim = row.to_claim()
        self.assertIsInstance(claim, Claim)
        self.assertEqual(claim.text, row.claim_text)
        self.assertEqual(claim.claim_type, row.claim_type)
        self.assertGreaterEqual(len(claim.sources), 1)

    def test_to_claim_sources_carry_pmid_or_doi(self):
        for row in all_cultivation_science_rows():
            claim = row.to_claim()
            for s in claim.sources:
                self.assertTrue(s.pmid or s.doi)


class HonestDebateBotanicalTaxonomyTest(unittest.TestCase):
    """The botanical-taxonomy row must surface BOTH single-species and
    multi-species citations honestly, not pick a winner."""

    def test_taxonomy_row_cites_both_camps(self):
        rows = find_cultivation_science_rows("botanical_taxonomy")
        self.assertEqual(len(rows), 1)
        labels = [c.label for c in rows[0].citations]
        # Small & Cronquist (single species) AND Hillig (three species)
        # AND McPartland (review). The honest-debate signal.
        joined = " | ".join(labels)
        self.assertIn("Small E & Cronquist", joined)
        self.assertIn("Hillig", joined)
        self.assertIn("McPartland", joined)


class RendererTests(unittest.TestCase):
    def test_render_full_registry(self):
        md = render_markdown(all_cultivation_science_rows())
        self.assertIn("## Cultivation-science registry", md)
        for label in (
            "Light spectrum",
            "Trichome biology",
            "Cannabinoid-synthase genetics",
            "Botanical taxonomy",
        ):
            self.assertIn(label, md)

    def test_render_empty_returns_empty(self):
        self.assertEqual(render_markdown(()), "")

    def test_pmid_surfaces_in_render(self):
        md = render_markdown(all_cultivation_science_rows())
        self.assertIn("PMID 3628508", md)         # Lydon 1987
        self.assertIn("PMID 12586720", md)        # de Meijer 2003


class FreshnessFieldTests(unittest.TestCase):
    def test_rows_carry_last_verified(self):
        for r in all_cultivation_science_rows():
            self.assertTrue(r.last_verified)

    def test_rows_extract_watch_pmids_from_citations(self):
        for r in all_cultivation_science_rows():
            cited_pmids = [c.pmid for c in r.citations if c.pmid]
            for pmid in cited_pmids:
                self.assertIn(pmid, r.watch_pmids)


if __name__ == "__main__":
    unittest.main()
