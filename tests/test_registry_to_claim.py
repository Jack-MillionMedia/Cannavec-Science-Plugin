"""Tests for ``to_claim()`` helpers on the four curated registries.

Each registry's record type now produces a typed :class:`Claim` for
end-to-end evidence threading through ``compose_answer``. These tests
cover:

- The four ``to_claim()`` methods (interactions, AEs, contraindications,
  populations).
- Grade-aware tier mapping on populations (Level A → SR_FLAGSHIP,
  Level B → JOURNAL_RCT with pre-reg + powered, Level C →
  SINGLE_ARM_OR_MECH).
- The module-level ``build_claim()`` mirrors.
- The ``compose_answer(include_claims=True)`` wired path.
- Refusal short-circuit: refused prompts produce zero Claims even
  when ``include_claims=True``.
- ``Answer.evidence_summary`` becomes meaningful after the threading.
- Wording-vs-grade safety: every emitted text passes the wording
  consistency check at its computed grade.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import (  # noqa: E402
    Claim,
    ClaimType,
    EvidenceLevel,
    SourceTier,
    build_claim_for_adverse_event,
    build_claim_for_contraindication,
    build_claim_for_interaction,
    build_claim_for_population,
    compose_answer,
    grade_wording_consistency,
)
from cannavec_science.adverse_events import all_adverse_events  # noqa: E402
from cannavec_science.contraindications import all_contraindications  # noqa: E402
from cannavec_science.interactions import all_interactions  # noqa: E402
from cannavec_science.populations import all_populations  # noqa: E402


# ── Per-registry shape tests ─────────────────────────────────────────


class TestInteractionToClaim(unittest.TestCase):
    def test_every_interaction_produces_a_claim(self) -> None:
        for row in all_interactions():
            claim = row.to_claim()
            self.assertIsInstance(claim, Claim)
            self.assertEqual(claim.claim_type, ClaimType.DRUG_INTERACTION)
            self.assertGreater(
                len(claim.sources), 0,
                f"row for {row.partner_drug} produced zero sources",
            )

    def test_default_tier_is_journal_rct(self) -> None:
        row = all_interactions()[0]
        claim = row.to_claim()
        for src in claim.sources:
            self.assertEqual(src.tier, SourceTier.JOURNAL_RCT)

    def test_module_level_helper_matches_method(self) -> None:
        row = all_interactions()[0]
        a = row.to_claim()
        b = build_claim_for_interaction(row)
        self.assertEqual(a.text, b.text)
        self.assertEqual(a.claim_type, b.claim_type)

    def test_source_tier_override(self) -> None:
        row = all_interactions()[0]
        claim = row.to_claim(source_tier=SourceTier.SR_FLAGSHIP)
        for src in claim.sources:
            self.assertEqual(src.tier, SourceTier.SR_FLAGSHIP)

    def test_claim_text_mentions_cannabinoid_and_partner(self) -> None:
        # CBD ↔ clobazam is the canonical Epidiolex interaction; the
        # claim text must mention both.
        for row in all_interactions():
            if row.partner_drug == "clobazam" and row.cannabinoid == "CBD":
                claim = row.to_claim()
                self.assertIn("CBD", claim.text)
                self.assertIn("clobazam", claim.text)
                self.assertIn("CYP2C19", claim.text)
                return
        self.fail("CBD-clobazam row missing from registry")

    def test_text_wording_consistent_with_grade(self) -> None:
        # The deterministic grader assigns a grade to each Claim.
        # The text must not exceed that grade's wording bound.
        for row in all_interactions():
            claim = row.to_claim()
            grade = claim.best_supportable_grade()
            violations = grade_wording_consistency(claim.text, grade)
            self.assertEqual(
                violations, (),
                f"interaction row '{row.partner_drug}' wording exceeds "
                f"its grade {grade.value}: {violations}",
            )


class TestAdverseEventToClaim(unittest.TestCase):
    def test_every_ae_produces_a_claim(self) -> None:
        for row in all_adverse_events():
            claim = row.to_claim()
            self.assertIsInstance(claim, Claim)
            self.assertEqual(claim.claim_type, ClaimType.SAFETY)
            self.assertGreater(len(claim.sources), 0)

    def test_module_level_helper_matches_method(self) -> None:
        row = all_adverse_events()[0]
        self.assertEqual(
            row.to_claim().text,
            build_claim_for_adverse_event(row).text,
        )

    def test_population_is_propagated(self) -> None:
        row = all_adverse_events()[0]
        claim = row.to_claim()
        self.assertEqual(claim.population, row.population)

    def test_text_wording_consistent_with_grade(self) -> None:
        for row in all_adverse_events():
            claim = row.to_claim()
            grade = claim.best_supportable_grade()
            violations = grade_wording_consistency(claim.text, grade)
            self.assertEqual(
                violations, (),
                f"AE row '{row.event}' wording exceeds grade "
                f"{grade.value}: {violations}",
            )

    def test_text_does_not_contain_banned_verbs(self) -> None:
        # Always-banned verbs (cure / miracle / heals) must never appear.
        for row in all_adverse_events():
            t = row.to_claim().text.lower()
            for bad in ("cure", "miracle", "heals", "100% safe",
                        "100% effective", "eradicat"):
                self.assertNotIn(
                    bad, t,
                    f"AE row '{row.event}' text contains banned: {bad}",
                )


class TestContraindicationToClaim(unittest.TestCase):
    def test_every_contraindication_produces_a_claim(self) -> None:
        for row in all_contraindications():
            claim = row.to_claim()
            self.assertEqual(claim.claim_type, ClaimType.SAFETY)
            self.assertGreater(len(claim.sources), 0)

    def test_severity_encoded_in_text(self) -> None:
        # Look for one absolute and one relative entry — both must
        # surface their severity grade in the rendered text.
        seen_absolute = False
        seen_relative = False
        for row in all_contraindications():
            t = row.to_claim().text
            if "contraindicated" not in t:
                self.fail(f"text missing 'contraindicated': {t}")
            if row.severity.value == "absolute":
                seen_absolute = True
            elif row.severity.value == "relative":
                seen_relative = True
                self.assertIn("relative", t)
        self.assertTrue(seen_absolute and seen_relative,
                        "registry should have at least one absolute and "
                        "one relative entry")

    def test_module_level_helper_matches_method(self) -> None:
        row = all_contraindications()[0]
        self.assertEqual(
            row.to_claim().text,
            build_claim_for_contraindication(row).text,
        )

    def test_text_wording_consistent_with_grade(self) -> None:
        for row in all_contraindications():
            claim = row.to_claim()
            grade = claim.best_supportable_grade()
            violations = grade_wording_consistency(claim.text, grade)
            self.assertEqual(
                violations, (),
                f"contraindication row '{row.population}' wording "
                f"exceeds {grade.value}: {violations}",
            )


class TestPopulationToClaim(unittest.TestCase):
    def test_every_population_produces_a_claim(self) -> None:
        for row in all_populations():
            claim = row.to_claim()
            self.assertEqual(claim.claim_type, ClaimType.CLINICAL_EFFICACY)

    def test_level_a_population_anchors_to_sr_flagship(self) -> None:
        # The Dravet population is curator-anchored at Level A. The
        # registry carries one pivotal NEJM citation; the deterministic
        # grader applies the ``single_primary_study`` cap, which lowers
        # the grade by one level when ``pre_registered_major_journal``
        # is True. So the deterministic grade is Level B — one level
        # below the curator anchor, which is honest given that only one
        # supporting source is independently cited in this row.
        for row in all_populations():
            if row.label == "paediatric Dravet syndrome":
                claim = row.to_claim()
                # Source tier is SR_FLAGSHIP per anchor mapping.
                self.assertEqual(
                    claim.sources[0].tier, SourceTier.SR_FLAGSHIP,
                )
                self.assertTrue(claim.sources[0].pre_registered)
                self.assertTrue(claim.sources[0].adequately_powered)
                # Deterministic grade is Level B (single-source cap).
                self.assertEqual(
                    claim.best_supportable_grade(), EvidenceLevel.B,
                    f"Dravet single-source row should grade to B; "
                    f"got {claim.best_supportable_grade().value}",
                )
                # v2.7: claim text contains NO embedded grade string —
                # the typed Claim.grade field is the single source of
                # truth. Closes 2026-05-19 Oracle Evaluator §4.5.
                self.assertNotRegex(
                    claim.text,
                    r"\bLevel\s+[A-E]\b|\bCurator[- ]anchor",
                    "claim prose must not embed a grade string",
                )
                # The curator-anchored grade remains available on the
                # source row itself.
                self.assertEqual(
                    row.highest_grade_anchor, EvidenceLevel.A,
                )
                return
        self.fail("Dravet population not found in registry")

    def test_level_b_population_anchors_to_journal_rct(self) -> None:
        # Curator anchor B + single JOURNAL_RCT source → deterministic C
        # (single_primary_study cap without SR_FLAGSHIP). This is the
        # honest output given the cited evidence base.
        for row in all_populations():
            if row.highest_grade_anchor == EvidenceLevel.B:
                claim = row.to_claim()
                self.assertEqual(
                    claim.best_supportable_grade(),
                    EvidenceLevel.C,
                    f"row '{row.label}': expected deterministic C, "
                    f"got {claim.best_supportable_grade().value}",
                )
                self.assertEqual(
                    claim.sources[0].tier, SourceTier.JOURNAL_RCT,
                )
                self.assertTrue(claim.sources[0].pre_registered)
                self.assertTrue(claim.sources[0].adequately_powered)
                # v2.7: claim text contains NO embedded grade string —
                # the typed Claim.grade field is the single source of
                # truth. Closes 2026-05-19 Oracle Evaluator §4.5.
                self.assertNotRegex(
                    claim.text,
                    r"\bLevel\s+[A-E]\b|\bCurator[- ]anchor",
                    "claim prose must not embed a grade string",
                )
                self.assertEqual(
                    row.highest_grade_anchor, EvidenceLevel.B,
                )
                return
        self.fail("no Level-B population in registry")

    def test_module_level_helper_matches_method(self) -> None:
        row = all_populations()[0]
        self.assertEqual(
            row.to_claim().text,
            build_claim_for_population(row).text,
        )

    def test_route_and_dose_propagated(self) -> None:
        row = all_populations()[0]
        claim = row.to_claim()
        self.assertEqual(claim.route, row.route)
        self.assertEqual(claim.dose_range, row.dose_range_population)

    def test_text_wording_consistent_with_grade(self) -> None:
        for row in all_populations():
            claim = row.to_claim()
            grade = claim.best_supportable_grade()
            violations = grade_wording_consistency(claim.text, grade)
            self.assertEqual(
                violations, (),
                f"population row '{row.label}' wording exceeds "
                f"{grade.value}: {violations}",
            )


# ── compose_answer integration tests ─────────────────────────────────


class TestComposeAnswerWithClaims(unittest.TestCase):
    def test_default_attaches_claims_v27(self) -> None:
        # v2.7 default: include_claims=True so the default invocation
        # surfaces the typed Claim objects the registries already hold.
        # Closes the 2026-05-19 Oracle Evaluator finding that the
        # canonical CBD/Dravet prompt surfaced "Unsupported" to
        # first-time users.
        a = compose_answer(
            "What does the population evidence say about CBD and clobazam?",
            audience="clinician",
        )
        self.assertGreater(
            len(a.claims), 0,
            "v2.7 default must populate Answer.claims when a registry "
            "row matches — the prior 'empty by default' behaviour "
            "regressed the user-facing surface.",
        )
        self.assertIsNotNone(a.evidence_summary)
        self.assertGreater(a.evidence_summary.n_claims, 0)

    def test_opt_out_no_claims(self) -> None:
        # v2.3-era opt-out path: include_claims=False yields the empty-
        # claims shape some downstream consumers may still depend on.
        a = compose_answer(
            "What does the population evidence say about CBD and clobazam?",
            audience="clinician",
            include_claims=False,
        )
        self.assertEqual(a.claims, [])
        self.assertEqual(a.evidence_summary.n_claims, 0)

    def test_opt_in_attaches_typed_claims(self) -> None:
        a = compose_answer(
            "What does the population evidence say about CBD and clobazam?",
            audience="clinician",
            include_claims=True,
        )
        self.assertFalse(a.is_refusal)
        self.assertGreater(
            len(a.claims), 0,
            "include_claims=True must populate Answer.claims when a "
            "registry row matches",
        )
        for c in a.claims:
            self.assertIsInstance(c, Claim)
            self.assertGreater(len(c.sources), 0)

    def test_evidence_summary_reflects_claims(self) -> None:
        # Dravet population is curator-anchored at Level A; the single-
        # source deterministic grade is Level B. The evidence summary
        # surfaces the deterministic grade — that's the honest "what
        # the cited rows independently support" answer.
        a = compose_answer(
            "What is the evidence for cannabidiol in Dravet syndrome?",
            audience="researcher",
            include_claims=True,
        )
        self.assertFalse(a.is_refusal)
        self.assertIsNotNone(a.evidence_summary)
        self.assertEqual(
            a.evidence_summary.highest_grade, EvidenceLevel.B,
            "Dravet single-source row grades deterministically to B",
        )
        self.assertGreaterEqual(a.evidence_summary.n_claims, 1)
        self.assertGreaterEqual(
            a.evidence_summary.n_with_primary_source, 1,
        )

    def test_refused_prompt_attaches_no_claims_even_when_opted_in(self) -> None:
        # Refusal short-circuit must hold even with include_claims=True.
        # Citations still attach (the population evidence base exists
        # whether or not Cannavec personally answers); Claims do not
        # because a refusal is not an answer.
        a = compose_answer(
            "I take warfarin every day. Can I add CBD to my regimen?",
            audience="patient",
            include_claims=True,
        )
        self.assertTrue(a.is_refusal)
        self.assertEqual(
            a.claims, [],
            "refused prompts must produce zero Claims even with "
            "include_claims=True",
        )
        # ... but citations still attach.
        self.assertGreater(len(a.citations), 0)

    def test_no_registry_hit_means_no_claims(self) -> None:
        # A prompt that doesn't hit any registry produces no Claims.
        # NOTE — original prompt was "boiling point of caryophyllene
        # oxide" but as of v2.8 the terpene registry is threaded into
        # compose_answer so a named terpene now produces claims. The
        # prompt is replaced with a question about a topic with no
        # registry coverage (sociology of cannabis consumption).
        a = compose_answer(
            "What is the sociology of cannabis subculture in 1970s San Francisco?",
            audience="researcher",
            include_claims=True,
        )
        self.assertEqual(a.claims, [])

    def test_include_registries_false_overrides_include_claims_true(self) -> None:
        # If the caller wants no registry citations, they also get no
        # registry claims. (Claim production requires registry hits.)
        a = compose_answer(
            "What does the population evidence say about CBD and clobazam?",
            audience="clinician",
            include_registries=False,
            include_claims=True,
        )
        self.assertEqual(a.claims, [])
        self.assertEqual(a.citations, [])

    def test_claims_markdown_renders_grade(self) -> None:
        a = compose_answer(
            "What is the evidence for cannabidiol in Dravet syndrome?",
            audience="researcher",
            include_claims=True,
        )
        md = a.to_markdown()
        self.assertIn("## Claims", md)
        # A grade marker for the deterministic grade should appear in
        # the claims section. The Dravet row deterministically grades
        # to Level B per the single-source cap.
        self.assertIn("Level B", md)


# ── Citation–source round-trip ───────────────────────────────────────


class TestRegistryClaimsAreCitation(unittest.TestCase):
    def test_each_claim_source_yields_a_citation(self) -> None:
        # Build a claim, walk its sources, confirm each produces a
        # resolvable Citation.
        row = all_interactions()[0]
        claim = row.to_claim()
        self.assertGreater(len(claim.sources), 0)
        for src in claim.sources:
            self.assertTrue(
                src.pmid or src.doi or src.url,
                f"source missing identifier: {src.title}",
            )


if __name__ == "__main__":
    unittest.main()
