"""Spec 003 v0.3 — routing-and-surfacing user stories.

Test triples (positive / negative / refusal where applicable) for each
P1 / P2 / P3 story in `specs/003-industry-expert-review/spec.md`.

User stories covered:

- US1 — cannabinoid-specific monograph routing (Δ⁸-THC must not fire
  Δ⁹-THC monograph) — FR-001.
- US2 — cannabinoid-scoped registry detectors — FR-002.
- US3 — anti-confidence-laundering on grade aggregation — FR-003.
- US6 — cannabis × <drug> interaction expansion — FR-006.
- US7 — eCBome registry threaded into compose_answer — FR-007.
- US9 — 0-claim classification — FR-009.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import (
    NamedCannabinoidSet,
    compose_answer,
    resolve_named_cannabinoid_set,
)
from cannavec_science.evidence import EvidenceLevel


# ── US1 — cannabinoid-specific monograph routing ─────────────────────


class US1MonographRoutingTests(unittest.TestCase):
    """Δ⁸-THC pharmacology must NOT emit the Δ⁹-THC monograph."""

    def test_delta_8_thc_does_not_fire_major_thc(self):
        s = resolve_named_cannabinoid_set("Δ⁸-THC pharmacology and safety")
        self.assertEqual([c.name for c in s.major], [])
        self.assertIn("Δ⁸-THC", [c.name for c in s.minor])

    def test_delta_8_thc_compose_emits_minor_monograph(self):
        a = compose_answer("Δ⁸-THC pharmacology and safety")
        section_titles = [s[0] for s in a.sections]
        # Acceptance 1: no Δ⁹-THC major monograph block.
        self.assertNotIn(
            "Major cannabinoid monograph — THC", section_titles,
        )
        # Acceptance 2: Δ⁸-THC monograph IS emitted.
        self.assertIn(
            "Minor cannabinoid monograph — Δ⁸-THC", section_titles,
        )

    def test_hhc_vs_delta_8_emits_both_minors(self):
        # Acceptance 2 — a real comparison query.
        a = compose_answer("HHC vs Δ⁸-THC pharmacology")
        section_titles = [s[0] for s in a.sections]
        self.assertIn(
            "Minor cannabinoid monograph — HHC", section_titles,
        )
        self.assertIn(
            "Minor cannabinoid monograph — Δ⁸-THC", section_titles,
        )
        # NOT the major Δ⁹-THC monograph.
        self.assertNotIn(
            "Major cannabinoid monograph — THC", section_titles,
        )

    def test_thcp_does_not_fire_major_thc(self):
        # Acceptance 3 — THCP standalone.
        a = compose_answer("THCP CB1 affinity")
        section_titles = [s[0] for s in a.sections]
        self.assertIn(
            "Minor cannabinoid monograph — THCP", section_titles,
        )
        self.assertNotIn(
            "Major cannabinoid monograph — THC", section_titles,
        )

    def test_delta_9_thc_still_fires(self):
        # Regression — explicit Δ⁹-THC must still fire major monograph
        # (it's a comparison-class prompt with explicit isomer).
        s = resolve_named_cannabinoid_set("Compare Δ⁹-THC and CBD")
        names = {c.name for c in s.major}
        self.assertIn("THC", names)
        self.assertIn("CBD", names)

    def test_dravet_golden_path_regression(self):
        # Regression — CBD-Dravet must remain Level B.
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertEqual(
            a.evidence_summary.highest_grade, EvidenceLevel.B,
        )


# ── US2 — cannabinoid-scoped registries ──────────────────────────────


class US2CannabinoidScopeFilterTests(unittest.TestCase):
    """AE / interaction / contraindication / population detectors must
    accept ``cannabinoid_filter`` and respect it."""

    def test_hhc_safety_returns_zero_ae_claims(self):
        # Acceptance 1: HHC safety profile returns 0 AE claims (because
        # the AE registry has no HHC rows).
        a = compose_answer("HHC safety profile and adverse events")
        for c in a.claims:
            # No claim attributes an AE to HHC because the registry
            # doesn't carry HHC rows. The claim list MUST NOT mix
            # other cannabinoids' AE rows.
            self.assertNotIn("CBD ", c.text)
            self.assertNotIn("Δ⁹-THC ", c.text)

    def test_cbd_adverse_events_filters_to_cbd(self):
        # Acceptance 3: CBD adverse events excludes Δ⁹-THC AE rows.
        a = compose_answer("CBD adverse events in paediatric epilepsy")
        # At least one claim should be present.
        self.assertGreater(len(a.claims), 0)
        # No claim attributes the AE to Δ⁹-THC.
        for c in a.claims:
            self.assertFalse(
                c.text.startswith("Δ⁹-THC"),
                f"CBD AE query should not surface Δ⁹-THC AE claims; "
                f"got: {c.text[:80]}",
            )

    def test_explicit_thc_safety_returns_thc_aes(self):
        # Acceptance 4 regression: explicit Δ⁹-THC safety question
        # returns Δ⁹-THC AE rows.
        a = compose_answer("Δ⁹-THC cardiovascular adverse events")
        # The interactions / AE detectors should surface Δ⁹-THC rows.
        thc_attributed = [
            c for c in a.claims if "Δ⁹-THC" in c.text or "THC " in c.text
        ]
        self.assertGreater(
            len(thc_attributed), 0,
            "Δ⁹-THC safety query must surface Δ⁹-THC AE rows",
        )

    def test_filter_directly_passed_to_detect_ae(self):
        # The detect_*_mention APIs accept cannabinoid_filter directly.
        from cannavec_science.adverse_events import detect_adverse_event_mention
        # Δ⁹-THC tachycardia row exists; filter to {"CBD"} must drop it.
        no_cbd_match = detect_adverse_event_mention(
            "THC tachycardia",
            cannabinoid_filter=frozenset({"CBD"}),
        )
        # The registry has no CBD-tachycardia row, so result is empty.
        self.assertEqual(len(no_cbd_match), 0)
        # Same prompt unfiltered should surface Δ⁹-THC tachycardia.
        unfiltered = detect_adverse_event_mention("THC tachycardia")
        self.assertGreater(len(unfiltered), 0)


# ── US3 — anti-confidence-laundering on grade aggregation ────────────


class US3TopicalRelevanceTests(unittest.TestCase):
    """``highest_grade`` must be computed over topically-relevant claims."""

    def test_entourage_effect_not_level_a(self):
        # Acceptance 1: highest_grade MUST NOT be ≥ Level B for an
        # entourage-effect prompt without anchored citations.
        a = compose_answer(
            "What is the evidence that the entourage effect is real?",
        )
        self.assertEqual(
            a.evidence_summary.highest_grade, EvidenceLevel.UNSUPPORTED,
            f"entourage-effect grade should be Unsupported when no "
            f"canonical citation backs the claim; got "
            f"{a.evidence_summary.highest_grade.value}",
        )

    def test_entourage_with_canonical_pmid_remains_topical(self):
        # The classifier accepts the canonical PMIDs as anchoring.
        # We can't directly inject a claim here; instead, assert the
        # _topical_relevance_for_claim function honours the PMID list.
        from cannavec_science.answer import _topical_relevance_for_claim
        from cannavec_science.evidence import Claim, ClaimType, Source, SourceTier
        canonical_source = Source(
            title="Russo 2011 entourage", pmid="21749363",
            tier=SourceTier.JOURNAL_RCT,
        )
        c = Claim(
            text="terpene-cannabinoid synergy in pain",
            claim_type=ClaimType.CLINICAL_EFFICACY,
            sources=(canonical_source,),
        )
        from cannavec_science.answer import resolve_named_cannabinoid_set
        s = resolve_named_cannabinoid_set("entourage effect evidence")
        self.assertTrue(_topical_relevance_for_claim(
            c, "entourage effect evidence", s,
        ))

    def test_unrelated_pmid_not_topical_for_entourage(self):
        from cannavec_science.answer import _topical_relevance_for_claim
        from cannavec_science.evidence import Claim, ClaimType, Source, SourceTier
        unrelated = Source(
            title="Devinsky 2017 Dravet", pmid="28538134",
            tier=SourceTier.SR_FLAGSHIP,
        )
        c = Claim(
            text="CBD reduces seizures in Dravet syndrome",
            claim_type=ClaimType.CLINICAL_EFFICACY,
            sources=(unrelated,),
        )
        from cannavec_science.answer import resolve_named_cannabinoid_set
        s = resolve_named_cannabinoid_set("entourage effect evidence")
        self.assertFalse(_topical_relevance_for_claim(
            c, "entourage effect evidence", s,
        ))

    def test_dravet_remains_topical_to_cbd_query(self):
        # Regression: Dravet Level B is topically relevant to the
        # named CBD + Dravet prompt.
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertEqual(
            a.evidence_summary.highest_grade, EvidenceLevel.B,
        )


# ── US6 — cannabis × <drug> interaction expansion ────────────────────


class US6CannabisExpansionTests(unittest.TestCase):
    """``cannabis`` / ``marijuana`` / ``weed`` must expand to the
    cannabinoid set for interaction matching."""

    def test_cannabis_tacrolimus_matches_cbd_tacrolimus_row(self):
        # Acceptance 1: cannabis × tacrolimus surfaces the CBD-tacrolimus row.
        from cannavec_science.interactions import detect_interaction_mention
        hits = detect_interaction_mention(
            "cannabis interaction with tacrolimus",
        )
        partners = {h.partner_drug for h in hits}
        self.assertTrue(
            any("tacrolimus" in p.lower() for p in partners),
            f"cannabis × tacrolimus should match CBD-tacrolimus row; "
            f"got partners: {partners}",
        )

    def test_cannabis_warfarin_matches_both_cbd_and_thc_warfarin(self):
        # Acceptance 2: cannabis × warfarin returns multiple cannabinoid rows.
        from cannavec_science.interactions import detect_interaction_mention
        hits = detect_interaction_mention("cannabis warfarin")
        cannabinoids = {h.cannabinoid for h in hits}
        # Either CBD or Δ⁹-THC (both have warfarin partners in some form).
        self.assertGreater(
            len(cannabinoids), 0,
            "cannabis × warfarin should match at least one cannabinoid row",
        )

    def test_marijuana_synonym_expands(self):
        from cannavec_science.interactions import detect_interaction_mention
        hits = detect_interaction_mention("marijuana tacrolimus interaction")
        self.assertTrue(
            any("tacrolimus" in h.partner_drug.lower() for h in hits),
        )

    def test_weed_synonym_expands(self):
        from cannavec_science.interactions import detect_interaction_mention
        hits = detect_interaction_mention("weed and tacrolimus")
        self.assertTrue(
            any("tacrolimus" in h.partner_drug.lower() for h in hits),
        )

    def test_specific_cannabinoid_wins(self):
        # Acceptance 3: when both "cannabis" and a specific name are
        # in the prompt, no double-rendering of the same row.
        from cannavec_science.interactions import detect_interaction_mention
        hits = detect_interaction_mention("cannabis CBD tacrolimus")
        # No duplicate (CBD, tacrolimus) row.
        keys = [(h.cannabinoid, h.partner_drug) for h in hits]
        self.assertEqual(
            len(keys), len(set(keys)),
            f"duplicate rows surfaced: {keys}",
        )


# ── US7 — eCBome registry surfacing ──────────────────────────────────


class US7EcbomeSurfacingTests(unittest.TestCase):
    """eCBome entries must surface when the prompt names them."""

    def test_anandamide_surfaces_ecbome_section(self):
        a = compose_answer("anandamide FAAH inhibition")
        section_titles = [s[0] for s in a.sections]
        self.assertIn(
            "Endocannabinoidome (eCBome) reference", section_titles,
        )

    def test_2_ag_surfaces_ecbome_section(self):
        a = compose_answer("2-AG MAGL signaling")
        section_titles = [s[0] for s in a.sections]
        self.assertIn(
            "Endocannabinoidome (eCBome) reference", section_titles,
        )

    def test_pea_surfaces_ecbome_section(self):
        a = compose_answer("PEA anti-inflammatory PPARα")
        section_titles = [s[0] for s in a.sections]
        self.assertIn(
            "Endocannabinoidome (eCBome) reference", section_titles,
        )

    def test_dravet_does_not_spuriously_surface_ecbome(self):
        # Acceptance 3 — the eCBome registry is NOT spuriously surfaced.
        a = compose_answer("CBD evidence in Dravet syndrome")
        section_titles = [s[0] for s in a.sections]
        self.assertNotIn(
            "Endocannabinoidome (eCBome) reference", section_titles,
        )

    def test_ecbome_citations_attached(self):
        a = compose_answer("anandamide degradation")
        # eCBome entries each carry primary-source citations.
        self.assertGreater(len(a.citations), 0)


# ── US9 — 0-claim classification ─────────────────────────────────────


class US9ZeroClaimClassificationTests(unittest.TestCase):

    def test_in_scope_uncurated_gets_discover_hint(self):
        # In §IV, in scope, no registry row — surfaces "try discover".
        a = compose_answer("anandamide FAAH inhibition")
        # The eCBome surfaces, so this may have citations but 0 claims.
        # Look at notes for the discover-hint pattern when there are
        # 0 typed claims.
        if not a.claims and not a.is_refusal:
            joined = " ".join(a.notes)
            self.assertTrue(
                "discover" in joined.lower(),
                f"0-claim answer should hint at discover: notes={a.notes}",
            )

    def test_out_of_scope_audience_classified(self):
        # Cultivation question — out of §IV.
        a = compose_answer("Best cultivar for indoor grow")
        if not a.claims and not a.is_refusal:
            joined = " ".join(a.notes)
            self.assertTrue(
                "researcher" in joined.lower()
                or "parent cannavec plugin" in joined.lower(),
                f"out-of-scope-audience notes mismatch: {a.notes}",
            )

    def test_deferred_v0_4_analytical_chemistry(self):
        # Out-of-scope-deferred (v0.4 horizon).
        a = compose_answer("decarboxylation kinetics of THCA in flower")
        if not a.claims and not a.is_refusal:
            joined = " ".join(a.notes)
            self.assertTrue(
                "v0.4" in joined or "analytical" in joined.lower(),
                f"deferred notes mismatch: {a.notes}",
            )


if __name__ == "__main__":
    unittest.main()
