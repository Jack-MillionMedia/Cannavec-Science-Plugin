"""Indication-aware claim selection + effect-precision at the citation site.

Covers two WP-RETRIEVAL defects (FIX_BRIEF §WP-RETRIEVAL):

- **#2 — Indication/topic mismatch.** ``compose_answer`` recovered curated
  *clinical-efficacy* rows for the WRONG indication via the BM25 retrieval
  fallback: "cannabidiol for Tourette syndrome tics" surfaced confident
  Level-B epilepsy (Dravet / LGS / TSC) claims because "cannabidiol" +
  "syndrome" co-occur, even though Tourette is absent from every matched row.
  The fix makes the recovery path indication-aware: a recovered
  ``clinical_efficacy`` claim that is *about a different condition* than the
  one the prompt names is dropped (mirroring the cannabinoid-scope filter), so
  the answer is an honest "no curated evidence for <indication>" rather than a
  confident answer to a different question. Condition-agnostic recoveries
  (driving / CYP / CHS / PK) are untouched.

- **#5 — Effect-estimate precision + non-significant NNT.** The ``## Claims``
  citation site rendered bare ``(PMID …, Level B)`` with no effect size / 95%
  CI / P, and quoted "NNT ~7 for ≥50% … responder" although that ≥50%
  responder endpoint in Devinsky 2017 (PMID 28538134) was OR 2.00 (95% CI
  0.93–4.30, P=0.08) — NOT significant (the PRIMARY convulsive-seizure-
  frequency endpoint WAS, P=0.01). The fix renders effect + CI + P inline at
  each curated citation site when the registry holds them, and guards the
  Dravet ≥50%-responder NNT with an explicit non-significance caveat anchored
  to the significant primary endpoint.

Stdlib only, fully offline, deterministic.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer


def _recovered(a) -> int:
    return sum(h for d, h in a.trace if d == "retrieval.recovered")


def _efficacy_populations(a) -> list:
    return [
        c.population
        for c in a.claims
        if c.claim_type.value == "clinical_efficacy" and c.population
    ]


# ── #2 Indication-aware retrieval recovery ──────────────────────────────────


class WrongIndicationIsNotAnswered(unittest.TestCase):
    """An off-KB indication must NOT receive a confident clinical-efficacy
    brief about a *different* curated condition."""

    def test_tourette_does_not_get_epilepsy_claims(self):
        # The reproduced defect: CBD-for-Tourette surfaced Dravet/LGS/TSC.
        a = compose_answer("cannabidiol for Tourette syndrome tics")
        epilepsy_pops = {
            "paediatric Dravet syndrome",
            "paediatric Lennox-Gastaut syndrome",
            "paediatric tuberous sclerosis complex (TSC)",
        }
        surfaced = set(_efficacy_populations(a))
        self.assertEqual(
            surfaced & epilepsy_pops,
            set(),
            f"Tourette query surfaced wrong-indication efficacy claims: "
            f"{surfaced & epilepsy_pops}",
        )

    def test_tourette_recovers_no_wrong_indication_claims(self):
        a = compose_answer("cannabidiol for Tourette syndrome tics")
        # No confident clinical-efficacy claim at all for an uncurated
        # indication — the recovery must not manufacture one.
        self.assertEqual(_efficacy_populations(a), [])

    def test_tourette_short_answer_is_not_a_confident_epilepsy_brief(self):
        a = compose_answer("cannabidiol for Tourette syndrome tics")
        sa = a.short_answer.lower()
        for token in ("dravet", "lennox", "tuberous", "drop seizure",
                      "convulsive seizure"):
            self.assertNotIn(
                token, sa,
                f"short answer leaks wrong-indication content {token!r}: "
                f"{a.short_answer!r}",
            )

    def test_tourette_emits_honest_not_curated_note(self):
        a = compose_answer("cannabidiol for Tourette syndrome tics")
        joined = " ".join(a.notes).lower()
        self.assertIn("tourette", joined,
                      f"note does not name the uncurated indication: {a.notes}")
        self.assertIn("no curated", joined, a.notes)

    def test_parkinson_tremor_no_epilepsy_claims(self):
        a = compose_answer("THC for Parkinson tremor")
        self.assertEqual(_efficacy_populations(a), [])
        joined = " ".join(a.notes).lower()
        self.assertIn("parkinson", joined, a.notes)

    def test_glaucoma_no_wrong_indication_claims(self):
        a = compose_answer("CBD for glaucoma")
        self.assertEqual(_efficacy_populations(a), [])
        joined = " ".join(a.notes).lower()
        self.assertIn("glaucoma", joined, a.notes)


class OnTopicQueriesAreUnchanged(unittest.TestCase):
    """The three control queries the brief pins MUST keep their correct
    briefs — the indication gate only blocks wrong-indication recoveries."""

    def test_cbd_for_dravet_unchanged(self):
        a = compose_answer("CBD for Dravet")
        self.assertIn("paediatric Dravet syndrome", _efficacy_populations(a))
        self.assertEqual(a.evidence_summary.highest_grade.value, "Level B")

    def test_cbd_evidence_in_dravet_unchanged(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertIn("paediatric Dravet syndrome", _efficacy_populations(a))

    def test_thc_for_neuropathic_pain_unchanged(self):
        a = compose_answer("THC for chronic neuropathic pain")
        self.assertIn(
            "adult chronic neuropathic pain", _efficacy_populations(a)
        )
        self.assertEqual(a.evidence_summary.highest_grade.value, "Level A")

    def test_cannabis_for_cinv_unchanged(self):
        a = compose_answer("cannabis for chemotherapy nausea")
        pops = _efficacy_populations(a)
        self.assertIn(
            "adult chemotherapy-induced nausea and vomiting (CINV)", pops
        )
        # §VII (D5 fix): the CINV row rests on a single non-canonical journal
        # SR (Whiting 2015, JAMA), which caps at Level B on its own — Level A
        # would require a canonical Cochrane/AHRQ/NICE SR or ≥ 2 aligned RCTs.
        self.assertEqual(a.evidence_summary.highest_grade.value, "Level B")


class ConditionAgnosticRecoveryStillWorks(unittest.TestCase):
    """The indication gate must not break the recoveries the retrieval layer
    exists for — those are condition-agnostic (safety / interaction / PK),
    not clinical-efficacy-for-a-condition."""

    def test_driving_miss_still_recovers(self):
        a = compose_answer("how does THC impair driving")
        self.assertGreaterEqual(len(a.claims), 1)
        self.assertGreaterEqual(_recovered(a), 1)

    def test_cyp_miss_still_recovers(self):
        a = compose_answer("what CYP enzymes does CBD inhibit")
        self.assertGreaterEqual(len(a.claims), 1)
        self.assertGreaterEqual(_recovered(a), 1)


# ── #5 Effect precision + non-significant NNT caveat ────────────────────────


class EffectEstimatePrecisionAtCitationSite(unittest.TestCase):
    def test_dravet_claim_renders_effect_ci_and_p(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        md = a.to_markdown()
        # Effect size, 95% CI, and the P-value of the significant primary
        # endpoint must render inline at the claim's citation site.
        self.assertIn("38.9%", md)
        self.assertIn("13.3%", md)
        self.assertIn("95% CI", md)
        self.assertIn("p=0.01", md)

    def test_dravet_json_exposes_effect_fields(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        payload = a.to_dict()
        dravet = [
            c for c in payload["claims"]
            if c.get("population") == "paediatric Dravet syndrome"
        ]
        self.assertTrue(dravet, "Dravet claim missing from JSON")
        effects = dravet[0].get("effect_estimates")
        self.assertTrue(effects, "no effect_estimates exposed in JSON")
        joined = " ".join(
            f"{e.get('effect_size', '')} {e.get('confidence_interval', '')}"
            for e in effects
        )
        self.assertIn("38.9%", joined)
        self.assertIn("95% CI", joined)

    def test_dravet_nnt_carries_non_significance_caveat(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        md = a.to_markdown().lower()
        # The NNT itself still surfaces …
        self.assertIn("nnt", md)
        # … but the ≥50%-responder NNT must be guarded: the responder endpoint
        # was NOT significant (OR 2.00, 95% CI 0.93-4.30, P=0.08).
        self.assertIn("0.93", md)
        has_caveat = (
            "not statistically significant" in md or "not significant" in md
        )
        self.assertTrue(
            has_caveat,
            "Dravet ≥50%-responder NNT lacks a non-significance caveat",
        )
        self.assertIn("p=0.08", md)

    def test_lgs_claim_has_no_spurious_nnt_caveat(self):
        # LGS (PMID 29768152) carries no ≥50%-responder NNT, so the caveat
        # must NOT attach to it — the guard is precise, not blanket.
        a = compose_answer("CBD evidence in Lennox-Gastaut syndrome")
        md = a.to_markdown()
        # The LGS effect renders (41.9% vs 17.2%) …
        self.assertIn("41.9%", md)
        # … and the Dravet-specific responder caveat numbers do NOT appear.
        self.assertNotIn("0.93", md)
        self.assertNotIn("p=0.08", md)

    def test_non_efficacy_claim_gets_no_effect_block(self):
        # An interaction brief carries no populations effect estimates, so the
        # effect-precision renderer must add nothing spurious.
        a = compose_answer("Does CBD interact with warfarin?")
        payload = a.to_dict()
        for c in payload["claims"]:
            self.assertNotIn(
                "effect_estimates", c,
                "effect block attached to a non-populations claim",
            )


if __name__ == "__main__":
    unittest.main()
