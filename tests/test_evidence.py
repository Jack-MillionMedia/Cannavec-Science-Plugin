"""Tests for cannavec.evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.evidence import (   # noqa: E402
    Claim,
    ClaimType,
    EvidenceLevel,
    ProvenanceScore,
    Source,
    SourceTier,
    apply_grade_modifiers,
    grade_from_source,
    missing_disclosures,
    required_disclosures,
    source_authority_weight,
)


class TestEvidenceLevels(unittest.TestCase):
    def test_rank_ordering(self) -> None:
        self.assertGreater(EvidenceLevel.A.rank, EvidenceLevel.B.rank)
        self.assertGreater(EvidenceLevel.B.rank, EvidenceLevel.C.rank)
        self.assertGreater(EvidenceLevel.C.rank, EvidenceLevel.D.rank)
        self.assertGreater(EvidenceLevel.D.rank, EvidenceLevel.E.rank)
        self.assertGreater(EvidenceLevel.E.rank, EvidenceLevel.UNSUPPORTED.rank)

    def test_wording_per_level(self) -> None:
        # Level A is allowed to say "established"; Level C is not.
        self.assertIn("established", EvidenceLevel.A.acceptable_wording)
        self.assertNotIn("established", EvidenceLevel.C.acceptable_wording)
        self.assertIn("may reduce", EvidenceLevel.C.acceptable_wording)


class TestSourceConstruction(unittest.TestCase):
    def test_source_requires_identifier(self) -> None:
        with self.assertRaises(ValueError):
            Source(title="No ID source", tier=SourceTier.JOURNAL_RCT)

    def test_source_accepts_pmid(self) -> None:
        s = Source(title="ok", tier=SourceTier.JOURNAL_RCT, pmid="28538134")
        self.assertEqual(s.pmid, "28538134")


class TestSourceAuthorityWeight(unittest.TestCase):
    def test_flagship_sr_full_weight(self) -> None:
        s = Source(title="Cochrane SR", tier=SourceTier.SR_FLAGSHIP, doi="10.x/y")
        self.assertEqual(source_authority_weight(s), 1.00)

    def test_industry_with_undeclared_coi_penalised(self) -> None:
        s = Source(
            title="Industry whitepaper",
            tier=SourceTier.INDUSTRY_OR_CONFERENCE,
            doi="10.x/y",
            coi_undeclared_surfaced=True,
        )
        # 0.35 * 0.50 = 0.175
        self.assertAlmostEqual(source_authority_weight(s), 0.175, places=3)

    def test_prereg_boost_capped_at_one(self) -> None:
        s = Source(
            title="Pre-registered SR",
            tier=SourceTier.SR_FLAGSHIP,
            doi="10.x/y",
            pre_registered=True,
            adequately_powered=True,
        )
        # 1.00 * 1.10 * 1.05 would be 1.155 — must cap at 1.00
        self.assertEqual(source_authority_weight(s), 1.00)

    def test_small_n_penalty(self) -> None:
        s = Source(
            title="Small RCT", tier=SourceTier.JOURNAL_RCT,
            doi="10.x/y", sample_size=15,
        )
        # 0.85 * 0.60 = 0.51
        self.assertAlmostEqual(source_authority_weight(s), 0.51, places=3)


class TestGradeFromSource(unittest.TestCase):
    def test_flagship_sr_anchors_level_a(self) -> None:
        s = Source(title="Cochrane", tier=SourceTier.SR_FLAGSHIP, doi="10.x/y")
        self.assertEqual(grade_from_source(s), EvidenceLevel.A)

    def test_retracted_source_is_unsupported(self) -> None:
        s = Source(
            title="Retracted paper",
            tier=SourceTier.SR_FLAGSHIP,
            doi="10.x/y",
            retraction_status="retracted",
        )
        self.assertEqual(grade_from_source(s), EvidenceLevel.UNSUPPORTED)

    def test_rct_without_prereg_is_level_c_max(self) -> None:
        s = Source(title="RCT", tier=SourceTier.JOURNAL_RCT, doi="10.x/y")
        self.assertEqual(grade_from_source(s), EvidenceLevel.C)

    def test_prereg_powered_rct_is_level_b(self) -> None:
        s = Source(
            title="Pre-reg powered RCT",
            tier=SourceTier.JOURNAL_RCT,
            doi="10.x/y",
            pre_registered=True,
            adequately_powered=True,
        )
        self.assertEqual(grade_from_source(s), EvidenceLevel.B)


class TestGradeModifiers(unittest.TestCase):
    def test_one_downgrade_per_grade_domain(self) -> None:
        grade = apply_grade_modifiers(
            EvidenceLevel.A,
            risk_of_bias_serious=True,
        )
        self.assertEqual(grade, EvidenceLevel.B)

    def test_multiple_grade_domains_compound(self) -> None:
        grade = apply_grade_modifiers(
            EvidenceLevel.A,
            risk_of_bias_serious=True,
            inconsistency_serious=True,
            indirectness_serious=True,
        )
        # A -> B -> C -> D
        self.assertEqual(grade, EvidenceLevel.D)

    def test_methods_unverified_caps_at_c(self) -> None:
        grade = apply_grade_modifiers(
            EvidenceLevel.A,
            methods_unverified=True,
        )
        self.assertEqual(grade, EvidenceLevel.C)

    def test_single_primary_study_caps_at_c(self) -> None:
        grade = apply_grade_modifiers(
            EvidenceLevel.A,
            single_primary_study=True,
        )
        self.assertEqual(grade, EvidenceLevel.C)

    def test_single_primary_study_prereg_caps_at_b(self) -> None:
        grade = apply_grade_modifiers(
            EvidenceLevel.A,
            single_primary_study=True,
            pre_registered_major_journal=True,
        )
        self.assertEqual(grade, EvidenceLevel.B)

    def test_missing_disclosure_each_downgrades_one(self) -> None:
        grade = apply_grade_modifiers(
            EvidenceLevel.A,
            missing_disclosure_count=2,
        )
        self.assertEqual(grade, EvidenceLevel.C)


class TestProvenanceScore(unittest.TestCase):
    def test_score_capped_at_one(self) -> None:
        p = ProvenanceScore(
            link_liveness_factor=1.0,
            retraction_factor=1.0,
            source_authority_weight=1.5,
        )
        self.assertEqual(p.score, 1.0)

    def test_retracted_zeroes_score(self) -> None:
        p = ProvenanceScore(
            link_liveness_factor=1.0,
            retraction_factor=0.0,
            source_authority_weight=1.0,
        )
        self.assertEqual(p.score, 0.0)
        self.assertIn("Reject", p.acceptable_use)

    def test_acceptable_use_bins(self) -> None:
        self.assertIn(
            "Level A/B",
            ProvenanceScore(1.0, 1.0, 0.9).acceptable_use,
        )
        self.assertIn(
            "Level C",
            ProvenanceScore(1.0, 1.0, 0.65).acceptable_use,
        )
        self.assertIn(
            "Context only",
            ProvenanceScore(1.0, 1.0, 0.45).acceptable_use,
        )


class TestRequiredDisclosures(unittest.TestCase):
    def test_clinical_efficacy_requires_effect_size(self) -> None:
        self.assertIn("effect_size", required_disclosures(ClaimType.CLINICAL_EFFICACY))
        self.assertIn("ci_95", required_disclosures(ClaimType.CLINICAL_EFFICACY))

    def test_dosing_requires_route(self) -> None:
        self.assertIn("route", required_disclosures(ClaimType.DOSING))
        self.assertIn("dose_range", required_disclosures(ClaimType.DOSING))

    def test_legal_requires_jurisdiction(self) -> None:
        req = required_disclosures(ClaimType.LEGAL_REGULATORY)
        self.assertIn("jurisdiction", req)
        self.assertIn("effective_date", req)
        self.assertIn("statutory_citation", req)

    def test_missing_disclosures_returns_subset(self) -> None:
        missing = missing_disclosures(
            ClaimType.CLINICAL_EFFICACY,
            present=["effect_size", "n", "comparator"],
        )
        self.assertIn("ci_95", missing)
        self.assertIn("evidence_grade", missing)
        self.assertNotIn("effect_size", missing)


class TestClaim(unittest.TestCase):
    def test_unsupported_when_no_sources(self) -> None:
        c = Claim(text="CBD reduces seizures.", claim_type=ClaimType.CLINICAL_EFFICACY)
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.UNSUPPORTED)

    def test_two_independent_sr_supports_a(self) -> None:
        s1 = Source(
            title="Cochrane CBD pain",
            tier=SourceTier.SR_FLAGSHIP,
            doi="10.x/cochrane1",
            pre_registered=True,
            adequately_powered=True,
        )
        s2 = Source(
            title="AHRQ CBD pain",
            tier=SourceTier.SR_FLAGSHIP,
            doi="10.x/ahrq1",
            pre_registered=True,
            adequately_powered=True,
        )
        c = Claim(
            text="CBD reduces pain.",
            claim_type=ClaimType.CLINICAL_EFFICACY,
            sources=(s1, s2),
            disclosures_present=frozenset({
                "effect_size", "ci_95", "n", "comparator", "primary_outcome",
                "evidence_grade", "funding", "coi",
            }),
        )
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.A)

    def test_single_rct_caps_at_c_without_prereg(self) -> None:
        s = Source(
            title="Single RCT",
            tier=SourceTier.JOURNAL_RCT,
            pmid="12345678",
        )
        c = Claim(
            text="CBD reduces anxiety.",
            claim_type=ClaimType.CLINICAL_EFFICACY,
            sources=(s,),
            disclosures_present=frozenset({
                "effect_size", "ci_95", "n", "comparator", "primary_outcome",
                "evidence_grade", "funding", "coi",
            }),
        )
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.C)

    def test_retracted_only_source_returns_unsupported(self) -> None:
        s = Source(
            title="Retracted big SR",
            tier=SourceTier.SR_FLAGSHIP,
            doi="10.x/retracted",
            retraction_status="retracted",
        )
        c = Claim(
            text="Foo treats bar.",
            claim_type=ClaimType.CLINICAL_EFFICACY,
            sources=(s,),
            disclosures_present=frozenset({
                "effect_size", "ci_95", "n", "comparator", "primary_outcome",
                "evidence_grade", "funding", "coi",
            }),
        )
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.UNSUPPORTED)


if __name__ == "__main__":
    unittest.main()
