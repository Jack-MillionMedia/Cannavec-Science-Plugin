"""Tests for cannavec.evidence_synthesis."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import Answer   # noqa: E402
from cannavec_science.evidence import (   # noqa: E402
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
)
from cannavec_science.evidence_synthesis import (   # noqa: E402
    synthesise,
    synthesise_answer,
    to_markdown,
)


_FULL_DISCLOSURES = frozenset({
    "effect_size", "ci_95", "n", "comparator", "primary_outcome",
    "evidence_grade", "funding", "coi",
})


def _strong_claim() -> Claim:
    s1 = Source(title="cochrane", tier=SourceTier.SR_FLAGSHIP,
                pmid="111111", pre_registered=True, adequately_powered=True)
    s2 = Source(title="NICE", tier=SourceTier.SR_FLAGSHIP,
                pmid="111112", pre_registered=True, adequately_powered=True)
    return Claim(
        text="Cannabidiol is effective for paediatric Dravet seizures.",
        claim_type=ClaimType.CLINICAL_EFFICACY,
        sources=(s1, s2),
        disclosures_present=_FULL_DISCLOSURES,
    )


def _weak_claim() -> Claim:
    s = Source(title="single small trial",
               tier=SourceTier.SINGLE_ARM_OR_MECH, pmid="222222")
    return Claim(
        text="Cannabis may reduce pain in some adults.",
        claim_type=ClaimType.CLINICAL_EFFICACY,
        sources=(s,),
        disclosures_present=_FULL_DISCLOSURES,
    )


class TestSynthesise(unittest.TestCase):
    def test_empty_claims_returns_unsupported(self) -> None:
        s = synthesise([])
        self.assertEqual(s.n_claims, 0)
        self.assertEqual(s.highest_grade, EvidenceLevel.UNSUPPORTED)
        self.assertEqual(s.weakest_grade, EvidenceLevel.UNSUPPORTED)

    def test_one_strong_claim_picks_level_a(self) -> None:
        s = synthesise([_strong_claim()])
        self.assertEqual(s.highest_grade, EvidenceLevel.A)
        self.assertEqual(s.n_with_primary_source, 1)
        self.assertEqual(s.n_with_pre_registration, 1)

    def test_mixed_claims_track_highest_and_weakest(self) -> None:
        s = synthesise([_strong_claim(), _weak_claim()])
        self.assertEqual(s.highest_grade, EvidenceLevel.A)
        # Weak claim should land lower than Level A.
        self.assertNotEqual(s.weakest_grade, EvidenceLevel.A)

    def test_distinct_sources_counted_once(self) -> None:
        c1 = _strong_claim()   # two sources
        c2 = _weak_claim()     # one source
        s = synthesise([c1, c2])
        # Two SR_FLAGSHIP + one SINGLE_ARM = three distinct sources.
        self.assertEqual(s.distinct_sources, 3)

    def test_cited_pmids_listed(self) -> None:
        s = synthesise([_strong_claim()])
        self.assertIn("111111", s.cited_pmids)
        self.assertIn("111112", s.cited_pmids)

    def test_provenance_scores_bounded(self) -> None:
        s = synthesise([_strong_claim(), _weak_claim()])
        self.assertGreaterEqual(s.mean_provenance_score, 0.0)
        self.assertLessEqual(s.mean_provenance_score, 1.0)


class TestSynthesiseAnswer(unittest.TestCase):
    def test_wraps_answer_claims(self) -> None:
        a = Answer(prompt="x")
        a.add_claim(_strong_claim())
        a.add_claim(_weak_claim())
        s = synthesise_answer(a)
        self.assertEqual(s.n_claims, 2)
        self.assertEqual(s.highest_grade, EvidenceLevel.A)


class TestMarkdown(unittest.TestCase):
    def test_empty_message(self) -> None:
        s = synthesise([])
        self.assertIn("No claims", to_markdown(s))

    def test_renders_grade_buckets(self) -> None:
        s = synthesise([_strong_claim(), _weak_claim()])
        out = to_markdown(s)
        self.assertIn("Evidence synthesis", out)
        self.assertIn("Level A", out)
        self.assertIn("Citations", out)


class TestContradictionsInSynthesis(unittest.TestCase):
    def test_synthesis_surfaces_contradictions(self) -> None:
        s_a = Source(title="cochrane", tier=SourceTier.SR_FLAGSHIP,
                     pmid="111111", pre_registered=True,
                     adequately_powered=True)
        c1 = Claim(text="CBD reduces seizures in Dravet.",
                   claim_type=ClaimType.CLINICAL_EFFICACY,
                   sources=(s_a,),
                   disclosures_present=_FULL_DISCLOSURES)
        c2 = Claim(text="CBD increases seizures in Dravet.",
                   claim_type=ClaimType.CLINICAL_EFFICACY,
                   sources=(s_a,),
                   disclosures_present=_FULL_DISCLOSURES)
        s = synthesise([c1, c2])
        self.assertGreaterEqual(len(s.contradictions), 1)


if __name__ == "__main__":
    unittest.main()
