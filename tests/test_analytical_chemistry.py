"""Tests for the analytical-chemistry registry (spec 004 US1 / FR-001)."""

from __future__ import annotations

import unittest

from cannavec_science.analytical_chemistry import (
    AnalyticalChemistryCitation,
    AnalyticalChemistryRow,
    AnalyticalTopic,
    all_analytical_chemistry_rows,
    detect_analytical_chemistry_mention,
    find_analytical_chemistry_rows,
    render_markdown,
)
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_eight_rows(self):
        # Constitution §III + spec 004 US1 / FR-001: ≥ 8 rows.
        rows = all_analytical_chemistry_rows()
        self.assertGreaterEqual(len(rows), 8)

    def test_every_row_has_a_primary_citation(self):
        # Constitution §I — every row anchors to a primary source.
        for r in all_analytical_chemistry_rows():
            self.assertTrue(r.citations, f"{r.name}: empty citations")
            for c in r.citations:
                self.assertTrue(
                    c.pmid or c.doi,
                    f"{r.name}: citation {c.label!r} lacks PMID and DOI",
                )

    def test_every_row_has_an_evidence_level(self):
        for r in all_analytical_chemistry_rows():
            self.assertIsInstance(r.evidence_level, EvidenceLevel)
            # No row laundering — analytical chemistry primary literature
            # caps at Level C without a Cochrane / AHRQ / NICE review.
            self.assertIn(r.evidence_level, {EvidenceLevel.C, EvidenceLevel.D})

    def test_every_row_has_watch_pmids_or_doi(self):
        for r in all_analytical_chemistry_rows():
            ids = list(r.watch_pmids) + [c.doi for c in r.citations if c.doi]
            self.assertTrue(ids, f"{r.name}: no PMID/DOI to watch")

    def test_topic_distribution_covers_all_five(self):
        # Every advertised topic ships in v0.4.
        topics = {r.topic for r in all_analytical_chemistry_rows()}
        for t in (
            AnalyticalTopic.DECARB_KINETICS,
            AnalyticalTopic.HPLC_VALIDATION,
            AnalyticalTopic.GC_MS_ARTEFACT,
            AnalyticalTopic.CHEMOVAR,
            AnalyticalTopic.PYROLYSIS,
        ):
            self.assertIn(t, topics, f"missing topic {t}")


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            AnalyticalChemistryRow(
                name="bogus",
                topic=AnalyticalTopic.CHEMOVAR,
                claim_text="x",
                claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            AnalyticalChemistryRow(
                name="bogus",
                topic=AnalyticalTopic.CHEMOVAR,
                claim_text="x",
                claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(
                    AnalyticalChemistryCitation(label="orphan"),
                ),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_decarb_kinetics_at_110(self):
        rows = detect_analytical_chemistry_mention(
            "Decarboxylation kinetics of THCA at 110 degrees C in flower"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(AnalyticalTopic.DECARB_KINETICS, topics)

    def test_thca_to_thc_inline_arrow(self):
        rows = detect_analytical_chemistry_mention("THCA → Δ⁹-THC conversion")
        self.assertTrue(rows)
        self.assertIn(
            AnalyticalTopic.DECARB_KINETICS,
            {r.topic for r in rows},
        )

    def test_hplc_validation(self):
        rows = detect_analytical_chemistry_mention(
            "HPLC method validation for cannabinoid potency analysis"
        )
        topics = {r.topic for r in rows}
        self.assertIn(AnalyticalTopic.HPLC_VALIDATION, topics)

    def test_gc_ms_vs_hplc(self):
        rows = detect_analytical_chemistry_mention(
            "HPLC vs GC-MS cannabinoid quantitation"
        )
        topics = {r.topic for r in rows}
        # HPLC fires; GC-MS-vs-HPLC also fires.
        self.assertIn(AnalyticalTopic.HPLC_VALIDATION, topics)
        self.assertIn(AnalyticalTopic.GC_MS_ARTEFACT, topics)

    def test_chemovar_classification(self):
        rows = detect_analytical_chemistry_mention(
            "Type II chemovar genetic basis"
        )
        topics = {r.topic for r in rows}
        self.assertIn(AnalyticalTopic.CHEMOVAR, topics)

    def test_hazekamp_fischedick_citation_keyword(self):
        rows = detect_analytical_chemistry_mention(
            "Hazekamp & Fischedick 2012 chemovar framework"
        )
        topics = {r.topic for r in rows}
        self.assertIn(AnalyticalTopic.CHEMOVAR, topics)

    def test_pyrolysis_byproducts(self):
        rows = detect_analytical_chemistry_mention(
            "Cannabis vapor pyrolysis byproducts at combustion vs "
            "vaporisation temperatures"
        )
        topics = {r.topic for r in rows}
        self.assertIn(AnalyticalTopic.PYROLYSIS, topics)

    def test_edible_decarb(self):
        rows = detect_analytical_chemistry_mention(
            "edibles decarb autoclave temperature"
        )
        topics = {r.topic for r in rows}
        self.assertIn(AnalyticalTopic.DECARB_KINETICS, topics)


class DetectionNegativeTests(unittest.TestCase):
    def test_cbd_dravet_does_not_fire_analytical(self):
        # The flagship clinical-efficacy prompt MUST NOT surface analytical
        # rows — that would be confidence-laundering by category drift.
        rows = detect_analytical_chemistry_mention(
            "CBD evidence in Dravet syndrome"
        )
        self.assertEqual(rows, ())

    def test_empty_string(self):
        self.assertEqual(detect_analytical_chemistry_mention(""), ())

    def test_unrelated_terpene_prompt(self):
        rows = detect_analytical_chemistry_mention(
            "myrcene CB1 binding affinity"
        )
        self.assertEqual(rows, ())

    def test_botany_taxonomy_does_not_fire_analytical(self):
        # Botany prompts route to cultivation_science, not analytical.
        rows = detect_analytical_chemistry_mention(
            "Cannabis sativa L. botanical taxonomy"
        )
        self.assertEqual(rows, ())


class FindRowsTests(unittest.TestCase):
    def test_by_topic(self):
        rows = find_analytical_chemistry_rows("chemovar")
        self.assertGreaterEqual(len(rows), 1)

    def test_by_partial_name(self):
        rows = find_analytical_chemistry_rows("hplc potency")
        self.assertGreaterEqual(len(rows), 1)


class ToClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        from cannavec_science.evidence import Claim
        row = all_analytical_chemistry_rows()[0]
        claim = row.to_claim()
        self.assertIsInstance(claim, Claim)
        self.assertEqual(claim.text, row.claim_text)
        self.assertEqual(claim.claim_type, row.claim_type)
        self.assertGreaterEqual(len(claim.sources), 1)

    def test_to_claim_sources_carry_pmid_or_doi(self):
        for row in all_analytical_chemistry_rows():
            claim = row.to_claim()
            for s in claim.sources:
                self.assertTrue(s.pmid or s.doi)


class RigorClaimCleanlinessTests(unittest.TestCase):
    """Spec 004 plan §Risks — every claim_text uses isomer-disambiguated
    THC naming so the curated row doesn't itself trigger an isomer-
    collapse violation.

    This is a sanity check; the rigor detector treats a Δ-prefixed THC
    reference as disambiguated, so curated rows that say Δ⁹-THC (with
    the Δ glyph) escape the detector. The test asserts the registry
    actually does use the Δ-prefix in its claim texts.
    """

    def test_claim_texts_use_disambiguated_thc_naming(self):
        # Every row that mentions THC must either prefix it with Δ⁹ or
        # write THCA explicitly. Bare "THC" without a Δ-prefix would
        # imply isomer collapse.
        for row in all_analytical_chemistry_rows():
            text = row.claim_text
            # The decarb-kinetics + GC-MS + chemovar rows discuss
            # THCA → Δ⁹-THC conversion explicitly with Δ-prefix.
            if "THC" in text:
                self.assertTrue(
                    "Δ⁹-THC" in text
                    or "Δ8-THC" in text or "Δ⁸-THC" in text
                    or "THCA" in text
                    or "Δ9-THC" in text,
                    f"{row.name}: bare 'THC' without Δ-prefix in text",
                )


class RendererTests(unittest.TestCase):
    def test_render_full_registry(self):
        md = render_markdown(all_analytical_chemistry_rows())
        self.assertIn("## Analytical-chemistry registry", md)
        # Every topic display name appears.
        for label in (
            "Decarboxylation kinetics",
            "HPLC method validation",
            "GC-MS in-injector artefact",
            "Chemovar classification",
            "Vapor / smoke pyrolysis byproducts",
        ):
            self.assertIn(label, md)

    def test_render_empty_returns_empty(self):
        self.assertEqual(render_markdown(()), "")

    def test_pmid_and_doi_surface_in_render(self):
        md = render_markdown(all_analytical_chemistry_rows())
        self.assertIn("10.1089/can.2016.0020", md)  # Wang 2016 (DOI render)
        self.assertIn("PMID 22362625", md)        # Hazekamp & Fischedick 2012


class FreshnessFieldTests(unittest.TestCase):
    def test_rows_carry_last_verified(self):
        for r in all_analytical_chemistry_rows():
            self.assertTrue(r.last_verified)

    def test_rows_extract_watch_pmids_from_citations(self):
        for r in all_analytical_chemistry_rows():
            cited_pmids = [c.pmid for c in r.citations if c.pmid]
            if cited_pmids:
                # Every row that has PMID citations carries them in watch_pmids.
                for pmid in cited_pmids:
                    self.assertIn(pmid, r.watch_pmids)


if __name__ == "__main__":
    unittest.main()
