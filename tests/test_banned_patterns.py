"""Tests for cannavec.banned_patterns."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.banned_patterns import (   # noqa: E402
    BANNED_PATTERN_REGISTRY,
    detect_banned_patterns,
    format_hits,
)


class TestBannedPatternRegistry(unittest.TestCase):
    def test_registry_has_minimum_patterns(self) -> None:
        # Minimum 13 patterns: 10 original + 3 added in v1.10
        # (endocannabinoid_deficiency_causal, full_spectrum_superiority,
        # non_psychoactive_cbd_misuse). Use >= so future additions don't break this.
        self.assertGreaterEqual(len(BANNED_PATTERN_REGISTRY), 13)

    def test_each_pattern_has_required_fields(self) -> None:
        for p in BANNED_PATTERN_REGISTRY:
            self.assertTrue(p.id)
            self.assertTrue(p.title)
            self.assertTrue(p.replacement)
            self.assertTrue(p.why)
            self.assertTrue(p.regex.pattern)

    def test_ids_unique(self) -> None:
        ids = [p.id for p in BANNED_PATTERN_REGISTRY]
        self.assertEqual(len(ids), len(set(ids)))


class TestIndicaSativaDetection(unittest.TestCase):
    def test_sativa_for_energy(self) -> None:
        hits = detect_banned_patterns("Sativa for daytime energy.")
        self.assertTrue(any(h.pattern.id == "indica_sativa_as_pharmacology" for h in hits))

    def test_indica_for_sleep(self) -> None:
        hits = detect_banned_patterns("Indica strains are great for sleep.")
        self.assertTrue(any(h.pattern.id == "indica_sativa_as_pharmacology" for h in hits))

    def test_indica_botanical_no_effect_claim_does_not_fire(self) -> None:
        # Mentioning indica botanically without an effect claim should not fire.
        hits = detect_banned_patterns(
            "C. sativa subsp. indica is one of the traditional botanical names."
        )
        # No effect-keyword nearby — should be clean.
        self.assertFalse(any(h.pattern.id == "indica_sativa_as_pharmacology" for h in hits))


class TestCureClaimDetection(unittest.TestCase):
    def test_cures_cancer_detected(self) -> None:
        hits = detect_banned_patterns("Cannabis cures cancer.")
        self.assertTrue(any(h.pattern.id == "cure_claim" for h in hits))

    def test_cures_epilepsy_detected(self) -> None:
        hits = detect_banned_patterns("CBD cures epilepsy in children.")
        self.assertTrue(any(h.pattern.id == "cure_claim" for h in hits))

    def test_reverses_alzheimers(self) -> None:
        hits = detect_banned_patterns("Cannabinoids reverse Alzheimer's disease.")
        self.assertTrue(any(h.pattern.id == "cure_claim" for h in hits))

    def test_quantified_effect_does_not_fire(self) -> None:
        # A quantified claim about seizure reduction is allowed.
        hits = detect_banned_patterns(
            "CBD reduces convulsive-seizure frequency by 39% versus placebo "
            "in Dravet syndrome (Devinsky 2017, NEJM)."
        )
        self.assertFalse(any(h.pattern.id == "cure_claim" for h in hits))

    def test_negated_cure_claim_does_not_fire(self) -> None:
        """Negation regression — correct rebuttal statements must not flag.

        A Cannavec answer to 'Can cannabis cure cancer?' must be able to
        say 'Cannabis does NOT cure cancer' without the banned-pattern
        detector flagging its own correct answer.

        Note: only patterns where the negation PRECEDES the cure verb within
        the 30-character look-back window are filtered.  Sentences where the
        negation follows the verb — e.g. "the claim that cannabis cures X is
        not supported" — still fire because they embed an unchecked cure
        assertion.  Cannavec should phrase refusals as "Cannabis does not
        cure X" (negation first), not "cannabis cures X is untrue" (cure
        embedded, negation later).
        """
        negated_statements = [
            # Negation immediately before the cure verb.
            "Cannabis does NOT cure cancer.",
            "Cannabis is not a cure for cancer.",
            "Cannabinoids do not cure or reverse Alzheimer's disease.",
            "No, cannabis cannot cure cancer.",
            "CBD does not cure epilepsy; it reduces seizure frequency.",
            "Cannabis has not cured any condition in controlled trials.",
            "Cannabis will not cure PTSD.",
        ]
        for text in negated_statements:
            hits = detect_banned_patterns(text)
            cure_hits = [h for h in hits if h.pattern.id == "cure_claim"]
            self.assertEqual(
                cure_hits, [],
                f"cure_claim fired on a negated statement: {text!r} "
                f"→ {[(h.match) for h in cure_hits]}",
            )

    def test_unnegated_cure_still_fires_after_negation_fix(self) -> None:
        """The negation fix must not suppress positive-case detection."""
        positive_claims = [
            "Cannabis cures cancer.",
            "CBD cures epilepsy.",
            "THC reverses Alzheimer's disease.",
            "Hemp heals diabetes.",
        ]
        for text in positive_claims:
            hits = detect_banned_patterns(text)
            self.assertTrue(
                any(h.pattern.id == "cure_claim" for h in hits),
                f"cure_claim did NOT fire on positive claim: {text!r}",
            )


class TestNaturalSafeDetection(unittest.TestCase):
    def test_natural_therefore_safer(self) -> None:
        hits = detect_banned_patterns(
            "Cannabis is natural and therefore safer than synthetic drugs."
        )
        self.assertTrue(any(h.pattern.id == "natural_therefore_safe" for h in hits))

    def test_plant_medicine_gentler(self) -> None:
        hits = detect_banned_patterns("Plant medicine is gentler than synthetics.")
        self.assertTrue(any(h.pattern.id == "natural_therefore_safe" for h in hits))


class TestUntestableWellnessDetection(unittest.TestCase):
    def test_boosts_immune_system(self) -> None:
        hits = detect_banned_patterns("CBD boosts the immune system.")
        self.assertTrue(any(h.pattern.id == "untestable_wellness" for h in hits))

    def test_balances_endocannabinoid_system(self) -> None:
        hits = detect_banned_patterns("Cannabis balances the endocannabinoid system.")
        self.assertTrue(any(h.pattern.id == "untestable_wellness" for h in hits))

    def test_promotes_wellness(self) -> None:
        hits = detect_banned_patterns("CBD promotes wellness.")
        self.assertTrue(any(h.pattern.id == "untestable_wellness" for h in hits))


class TestMarketingRatio(unittest.TestCase):
    def test_one_to_one_for_balance(self) -> None:
        hits = detect_banned_patterns(
            "Try a 1:1 CBD:THC product for balance and calm."
        )
        self.assertTrue(any(h.pattern.id == "marketing_ratio" for h in hits))


class TestAnecdoteAsEvidence(unittest.TestCase):
    def test_patients_report_relief(self) -> None:
        hits = detect_banned_patterns(
            "Patients report relief from chronic pain after using cannabis."
        )
        self.assertTrue(any(h.pattern.id == "anecdote_as_evidence" for h in hits))


class TestMechanismLeap(unittest.TestCase):
    def test_cb2_immune_leap(self) -> None:
        hits = detect_banned_patterns(
            "CB2 receptors are on immune cells, therefore cannabis treats "
            "autoimmune disease."
        )
        self.assertTrue(any(h.pattern.id == "mechanism_to_clinic" for h in hits))


class TestBrandEndorsement(unittest.TestCase):
    def test_we_recommend_brand(self) -> None:
        hits = detect_banned_patterns(
            "We recommend Brand X's product for the best results."
        )
        self.assertTrue(any(h.pattern.id == "brand_endorsement" for h in hits))


class TestNewPatternsV110(unittest.TestCase):
    """Tests for the three patterns added in v1.10."""

    def test_endocannabinoid_deficiency_causal_fires(self) -> None:
        hits = detect_banned_patterns(
            "Endocannabinoid deficiency causes fibromyalgia in most patients."
        )
        self.assertTrue(
            any(h.pattern.id == "endocannabinoid_deficiency_causal" for h in hits),
            "endocannabinoid_deficiency_causal should fire on causal claim",
        )

    def test_endocannabinoid_deficiency_hypothesis_clean(self) -> None:
        hits = detect_banned_patterns(
            "The clinical endocannabinoid deficiency hypothesis (Russo 2004) "
            "proposes that reduced endocannabinoid tone may contribute to "
            "migraine, IBS, and fibromyalgia — the evidence is classified Level D."
        )
        ids = [h.pattern.id for h in hits]
        self.assertNotIn(
            "endocannabinoid_deficiency_causal",
            ids,
            "endocannabinoid_deficiency_causal must not fire on hedged hypothesis",
        )

    def test_full_spectrum_superiority_fires(self) -> None:
        hits = detect_banned_patterns(
            "Full-spectrum CBD is superior to isolate and more effective "
            "for anxiety."
        )
        self.assertTrue(
            any(h.pattern.id == "full_spectrum_superiority" for h in hits),
            "full_spectrum_superiority should fire on unsupported superiority claim",
        )

    def test_full_spectrum_with_evidence_context_may_pass(self) -> None:
        hits = detect_banned_patterns(
            "Some observational data (Pamplona 2018) suggest lower doses of "
            "full-spectrum CBD may achieve similar seizure control compared "
            "to isolate, but no powered RCT has confirmed this."
        )
        ids = [h.pattern.id for h in hits]
        self.assertNotIn(
            "full_spectrum_superiority",
            ids,
        )

    def test_non_psychoactive_cbd_safety_fires(self) -> None:
        hits = detect_banned_patterns(
            "CBD is non-psychoactive and has no adverse effects."
        )
        self.assertTrue(
            any(h.pattern.id == "non_psychoactive_cbd_misuse" for h in hits),
            "non_psychoactive_cbd_misuse should fire when non-psychoactive implies safety",
        )


class TestCleanContent(unittest.TestCase):
    def test_well_formed_claim_is_clean(self) -> None:
        text = (
            "Δ⁹-tetrahydrocannabinol (PubChem CID 16078) is a partial agonist "
            "at the human cannabinoid receptor CB1 (UniProt P21554) with "
            "reported Ki values of 5–80 nM depending on assay (BindingDB)."
        )
        hits = detect_banned_patterns(text)
        self.assertEqual(hits, [])


class TestFormatHits(unittest.TestCase):
    def test_format_clean(self) -> None:
        self.assertIn("Clean", format_hits([]))

    def test_format_includes_replacement(self) -> None:
        hits = detect_banned_patterns("Cannabis cures cancer.")
        out = format_hits(hits)
        self.assertIn("cure", out.lower())
        self.assertIn("Suggested replacement", out)


class TestInlineCodeSkip(unittest.TestCase):
    """Meta-language guard: pattern names inside inline code or fenced
    code blocks must not trigger banned-pattern detection.

    Regression: an audit / discussion section that documents the banned
    patterns by name (e.g. "we avoid `cure` claims" or
    "`natural-therefore-safe` is a banned inference") must not fail its
    own audit just for naming the pattern in code formatting.
    """

    def test_cure_claim_in_inline_code_skipped(self) -> None:
        text = (
            "## Banned-Pattern Audit\n"
            "The brief avoids `cure` claims for cancer and other indications."
        )
        hits = detect_banned_patterns(text)
        cure_hits = [h for h in hits if h.pattern.id == "cure_claim"]
        self.assertEqual(
            cure_hits, [],
            "cure_claim must not fire on `cure` quoted inside inline code",
        )

    def test_natural_therefore_safe_in_inline_code_skipped(self) -> None:
        text = (
            "## Banned-Pattern Audit\n"
            "We avoid the `natural-therefore-safe` inference by reporting "
            "explicit adverse-event data with citations."
        )
        hits = detect_banned_patterns(text)
        nts_hits = [h for h in hits if h.pattern.id == "natural_therefore_safe"]
        self.assertEqual(
            nts_hits, [],
            "natural_therefore_safe must not fire on the pattern name "
            "quoted inside inline code",
        )

    def test_fenced_code_block_skipped(self) -> None:
        # Pattern naming inside a fenced code block (e.g. CLI output
        # documentation) must also be skipped.
        text = (
            "Example output from the audit CLI:\n\n"
            "```\n"
            "- banned-pattern: cure_claim (cures cancer)\n"
            "- banned-pattern: natural_therefore_safe (cannabis is natural and safer)\n"
            "```\n"
        )
        hits = detect_banned_patterns(text)
        # Neither pattern should fire on the documentation example.
        cure_hits = [h for h in hits if h.pattern.id == "cure_claim"]
        nts_hits = [h for h in hits if h.pattern.id == "natural_therefore_safe"]
        self.assertEqual(cure_hits, [], "cure_claim must not fire inside ```fenced``` code")
        self.assertEqual(nts_hits, [], "natural_therefore_safe must not fire inside fenced code")

    def test_unquoted_pattern_outside_code_still_fires(self) -> None:
        # The skip is positional, not lexical — text outside code spans
        # in the same document must still be checked.
        text = (
            "We avoid `cure` claims in audit sections.\n"
            "But this sentence does claim that CBD cures epilepsy in children — that's the violation."
        )
        hits = detect_banned_patterns(text)
        self.assertTrue(
            any(h.pattern.id == "cure_claim" for h in hits),
            "cure_claim must still fire on the unquoted prose assertion",
        )


class TestFullSpectrumSuperiorityPlural(unittest.TestCase):
    """Regression: full_spectrum_superiority pattern previously failed
    to match the plural form 'isolates' because of an over-tight word
    boundary."""

    def test_full_spectrum_better_than_isolates_plural(self) -> None:
        text = "Full-spectrum oil is superior to isolates for chronic pain."
        hits = detect_banned_patterns(text)
        self.assertTrue(
            any(h.pattern.id == "full_spectrum_superiority" for h in hits),
            "full_spectrum_superiority must fire on plural 'isolates'",
        )

    def test_full_spectrum_better_than_isolate_singular(self) -> None:
        text = "Full-spectrum oil is more effective than isolate for pain."
        hits = detect_banned_patterns(text)
        self.assertTrue(
            any(h.pattern.id == "full_spectrum_superiority" for h in hits),
            "full_spectrum_superiority must still fire on singular 'isolate'",
        )


class TestTerpeneAsClinicalEffect(unittest.TestCase):
    """The terpene-as-clinical-effect pattern catches single-terpene
    causal claims that overclaim what cannabis inhalation actually
    delivers at receptor concentrations."""

    def test_myrcene_causes_couch_lock(self) -> None:
        hits = detect_banned_patterns("Myrcene causes couch lock and sedation.")
        self.assertTrue(
            any(h.pattern.id == "terpene_as_clinical_effect" for h in hits)
        )

    def test_high_myrcene_cultivars_produce_sedation(self) -> None:
        hits = detect_banned_patterns("High-myrcene cultivars produce sedation.")
        self.assertTrue(
            any(h.pattern.id == "terpene_as_clinical_effect" for h in hits)
        )

    def test_linalool_responsible_for_calming(self) -> None:
        hits = detect_banned_patterns(
            "Linalool is responsible for the calming effect of cannabis."
        )
        self.assertTrue(
            any(h.pattern.id == "terpene_as_clinical_effect" for h in hits)
        )

    def test_caryophyllene_delivers_anti_inflammatory(self) -> None:
        hits = detect_banned_patterns(
            "Caryophyllene-rich strains deliver anti-inflammatory benefits."
        )
        self.assertTrue(
            any(h.pattern.id == "terpene_as_clinical_effect" for h in hits)
        )


class TestEcsMasterRegulator(unittest.TestCase):
    """The ECS-as-master-regulator pattern catches the over-broad
    framing of the endocannabinoid system as governing all human
    physiology — the conceptual gateway to over-broad cannabinoid
    claims."""

    def test_ecs_regulates_all_human_physiology(self) -> None:
        hits = detect_banned_patterns(
            "The endocannabinoid system regulates all human physiology."
        )
        self.assertTrue(
            any(h.pattern.id == "ecs_master_regulator" for h in hits)
        )

    def test_ecs_abbreviation_master_regulator(self) -> None:
        hits = detect_banned_patterns(
            "The ECS is the master regulator of every body system."
        )
        self.assertTrue(
            any(h.pattern.id == "ecs_master_regulator" for h in hits)
        )

    def test_endocannabinoid_system_master_regulator_phrase(self) -> None:
        hits = detect_banned_patterns(
            "The endocannabinoid system is the master regulator of homeostasis."
        )
        self.assertTrue(
            any(h.pattern.id == "ecs_master_regulator" for h in hits)
        )

    def test_constrained_ecs_role_does_not_fire(self) -> None:
        # A properly-scoped ECS statement should not trigger the
        # master-regulator detector.
        hits = detect_banned_patterns(
            "The ECS modulates pain signalling in some patient populations."
        )
        self.assertFalse(
            any(h.pattern.id == "ecs_master_regulator" for h in hits),
            "constrained ECS-role statements must not fire the master-"
            "regulator detector",
        )


if __name__ == "__main__":
    unittest.main()
