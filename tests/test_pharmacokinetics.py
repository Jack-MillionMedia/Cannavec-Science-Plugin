"""Tests for the pharmacokinetics registry (spec 005 US1 / FR-001)."""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)
from cannavec_science.pharmacokinetics import (
    PharmacokineticsCitation,
    PharmacokineticsRow,
    PharmacokineticsTopic,
    all_pharmacokinetics_rows,
    detect_pharmacokinetics_mention,
    find_pharmacokinetics_rows,
    render_markdown,
)
from cannavec_science.rigor_checks import detect_thca_vs_thc_conflation


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_eight_rows(self):
        rows = all_pharmacokinetics_rows()
        self.assertGreaterEqual(len(rows), 8)

    def test_every_row_has_primary_citation(self):
        for r in all_pharmacokinetics_rows():
            self.assertTrue(r.citations, f"{r.name}: empty citations")
            for c in r.citations:
                self.assertTrue(
                    c.pmid or c.doi,
                    f"{r.name}: citation {c.label!r} lacks PMID/DOI",
                )

    def test_every_row_has_evidence_level(self):
        for r in all_pharmacokinetics_rows():
            self.assertIsInstance(r.evidence_level, EvidenceLevel)
            # PK rows from controlled-dose human studies cap at C / B.
            self.assertIn(
                r.evidence_level,
                {EvidenceLevel.B, EvidenceLevel.C, EvidenceLevel.D},
            )

    def test_watch_pmids_populated(self):
        for r in all_pharmacokinetics_rows():
            ids = list(r.watch_pmids) + [c.doi for c in r.citations if c.doi]
            self.assertTrue(ids, f"{r.name}: no PMID/DOI to watch")

    def test_topic_coverage(self):
        topics = {r.topic for r in all_pharmacokinetics_rows()}
        for t in (
            PharmacokineticsTopic.INHALED_PK,
            PharmacokineticsTopic.ORAL_PK,
            PharmacokineticsTopic.FOOD_EFFECT,
            PharmacokineticsTopic.ACTIVE_METABOLITE,
            PharmacokineticsTopic.OROMUCOSAL_PK,
            PharmacokineticsTopic.DISTRIBUTION,
            PharmacokineticsTopic.DETECTION_WINDOW,
        ):
            self.assertIn(t, topics, f"missing topic {t}")


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            PharmacokineticsRow(
                name="bogus",
                topic=PharmacokineticsTopic.INHALED_PK,
                claim_text="x",
                claim_type=ClaimType.PHARMACOKINETIC,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            PharmacokineticsRow(
                name="bogus",
                topic=PharmacokineticsTopic.INHALED_PK,
                claim_text="x",
                claim_type=ClaimType.PHARMACOKINETIC,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(PharmacokineticsCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_inhaled_route_mentioned(self):
        rows = detect_pharmacokinetics_mention(
            "smoked THC pharmacokinetics Tmax Cmax"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PharmacokineticsTopic.INHALED_PK, topics)

    def test_oral_route_mentioned(self):
        rows = detect_pharmacokinetics_mention(
            "oral dronabinol pharmacokinetics first-pass effect"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PharmacokineticsTopic.ORAL_PK, topics)

    def test_food_effect_mentioned(self):
        rows = detect_pharmacokinetics_mention(
            "CBD epidiolex food effect AUC fivefold high fat meal"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PharmacokineticsTopic.FOOD_EFFECT, topics)

    def test_active_metabolite_mentioned(self):
        rows = detect_pharmacokinetics_mention(
            "11-hydroxy-THC active metabolite oral dronabinol"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PharmacokineticsTopic.ACTIVE_METABOLITE, topics)

    def test_oromucosal_mentioned(self):
        rows = detect_pharmacokinetics_mention(
            "Sativex nabiximols oromucosal pharmacokinetics"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PharmacokineticsTopic.OROMUCOSAL_PK, topics)

    def test_distribution_mentioned(self):
        rows = detect_pharmacokinetics_mention(
            "THC plasma protein binding lipophilic adipose distribution"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PharmacokineticsTopic.DISTRIBUTION, topics)

    def test_detection_window_mentioned(self):
        rows = detect_pharmacokinetics_mention(
            "urine cannabinoid detection window THC-COOH SAMHSA 50 ng"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(PharmacokineticsTopic.DETECTION_WINDOW, topics)


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated_prompt(self):
        rows = detect_pharmacokinetics_mention(
            "What is the boiling point of water?"
        )
        self.assertEqual(rows, ())

    def test_empty_prompt(self):
        self.assertEqual(detect_pharmacokinetics_mention(""), ())

    def test_botanical_taxonomy_does_not_fire(self):
        rows = detect_pharmacokinetics_mention(
            "Is Cannabis sativa one species or three?"
        )
        self.assertEqual(rows, ())


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        for r in all_pharmacokinetics_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)
            self.assertEqual(claim.claim_type, r.claim_type)
            self.assertTrue(claim.sources)

    def test_no_thca_vs_thc_conflation_in_curated_claim_text(self):
        # Constitution §VI — every row uses Δ⁹-THC or 11-OH-Δ⁹-THC
        # isomer naming. The THCA-vs-THC rigor detector must NOT fire
        # on curated PK text (metabolite stories are NOT acid/neutral
        # conflations).
        for r in all_pharmacokinetics_rows():
            violations = detect_thca_vs_thc_conflation(r.claim_text)
            self.assertEqual(
                violations, (),
                f"{r.name}: THCA-vs-THC rigor detector fired on "
                f"curated PK text",
            )


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified_date(self):
        for r in all_pharmacokinetics_rows():
            self.assertTrue(r.last_verified)
            self.assertEqual(len(r.last_verified), 10)
            self.assertTrue(
                r.last_verified[:4].isdigit(),
                f"{r.name}: malformed last_verified={r.last_verified!r}",
            )


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        rows = find_pharmacokinetics_rows("inhaled_pk")
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r.topic, "inhaled_pk")

    def test_find_returns_empty_on_unknown(self):
        rows = find_pharmacokinetics_rows("nonexistent_topic_xyz")
        self.assertEqual(rows, ())


class RendererTests(unittest.TestCase):
    def test_render_empty_returns_empty(self):
        self.assertEqual(render_markdown(()), "")

    def test_render_includes_section_header(self):
        rows = all_pharmacokinetics_rows()
        md = render_markdown(rows)
        self.assertIn("Pharmacokinetics registry", md)

    def test_render_includes_primary_pmid(self):
        rows = all_pharmacokinetics_rows()
        md = render_markdown(rows)
        # Huestis 2005 PMID is the canonical reference.
        self.assertIn("16142973", md)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_thc_pk_query_returns_pk_claims(self):
        a = compose_answer("THC inhaled vs oral pharmacokinetics Tmax Cmax")
        self.assertFalse(a.is_refusal)
        # ≥ 2 PK claims from inhaled + oral rows.
        self.assertGreaterEqual(len(a.claims), 2)
        # Highest grade is no longer Unsupported.
        self.assertNotEqual(a.evidence_summary.highest_grade.value, "Unsupported")

    def test_cbd_food_effect_returns_birnbaum(self):
        a = compose_answer(
            "CBD epidiolex food effect AUC fivefold high fat meal"
        )
        text = a.to_markdown()
        self.assertIn("31247132", text)

    def test_11_oh_thc_returns_active_metabolite_row(self):
        a = compose_answer("11-hydroxy-THC active metabolite oral dronabinol")
        self.assertFalse(a.is_refusal)
        # The Wall 1983 PMID should appear in the citation set.
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("6309462", pmids)


if __name__ == "__main__":
    unittest.main()
