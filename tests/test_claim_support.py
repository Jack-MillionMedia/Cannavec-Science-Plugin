"""Offline tests for the deterministic claim-support verifier."""

from __future__ import annotations

import unittest

from cannavec_science.claim_support import (
    Verdict,
    assess_support,
    claimed_direction,
    extract_entities,
)

# A representative real abstract (Geffrey 2015, CBD-clobazam), paraphrased.
_GEFFREY = (
    "Cannabidiol (CBD) is studied as adjuvant treatment of refractory epilepsy. "
    "Because clobazam and CBD are both metabolized in the cytochrome P450 (CYP) "
    "pathway, we evaluated a drug-drug interaction. We report elevated clobazam "
    "and norclobazam levels with increasing CBD dose; monitoring of clobazam "
    "levels is necessary."
)


class ExtractEntities(unittest.TestCase):
    def test_cannabinoid_and_cyp(self) -> None:
        e = extract_entities("CBD inhibits CYP3A4 and CYP2C19")
        self.assertIn("cbd", e.cannabinoids)
        self.assertIn("cyp3a", e.cyps)
        self.assertIn("cyp2c", e.cyps)

    def test_synonym_words_count(self) -> None:
        e = extract_entities("cannabidiol elevated clobazam exposure")
        self.assertIn("cbd", e.cannabinoids)

    def test_direction_parsing(self) -> None:
        self.assertEqual(claimed_direction("CBD inhibits CYP3A4"), "inhibit")
        self.assertEqual(claimed_direction("CBD induces CYP3A4"), "induce")
        self.assertEqual(claimed_direction("no significant interaction"), "no_effect")
        self.assertEqual(claimed_direction("x", direction_hint="inhibits"), "inhibit")


class AssessSupport(unittest.TestCase):
    def test_supported(self) -> None:
        r = assess_support(
            "CBD inhibits CYP3A4, increasing midazolam exposure",
            "Cannabidiol inhibited CYP3A4 activity, increasing midazolam AUC 14.8-fold.",
            cannabinoid="CBD", cyp_isoform="CYP3A4", direction_hint="inhibits",
        )
        self.assertEqual(r.verdict, Verdict.SUPPORTED)
        self.assertFalse(r.needs_review)

    def test_missing_entity_is_unverified(self) -> None:
        # Claim is about CYP2C19 but the abstract only discusses CYP3A4.
        r = assess_support(
            "CBD inhibits CYP2C19",
            "Cannabidiol inhibited CYP3A4 in human liver microsomes.",
            cannabinoid="CBD", cyp_isoform="CYP2C19", direction_hint="inhibits",
        )
        self.assertEqual(r.verdict, Verdict.UNVERIFIED)
        self.assertIn("cyp2c", r.missing)
        self.assertTrue(r.needs_review)

    def test_direction_contradiction(self) -> None:
        # Claim says induction; abstract reports inhibition (and not induction).
        r = assess_support(
            "CBD induces CYP3A4",
            "Cannabidiol inhibited CYP3A4 activity in a time-dependent manner.",
            cannabinoid="CBD", cyp_isoform="CYP3A4", direction_hint="induces",
        )
        self.assertEqual(r.verdict, Verdict.CONTRADICTION)
        self.assertTrue(r.needs_review)

    def test_weak_when_direction_absent(self) -> None:
        r = assess_support(
            "CBD inhibits CYP3A4",
            "Cannabidiol and CYP3A4 were both present in the assay system.",
            cannabinoid="CBD", cyp_isoform="CYP3A4", direction_hint="inhibits",
        )
        self.assertEqual(r.verdict, Verdict.WEAK)

    def test_no_text(self) -> None:
        r = assess_support("CBD inhibits CYP3A4", "", cannabinoid="CBD")
        self.assertEqual(r.verdict, Verdict.NO_TEXT)

    def test_partner_drug_match(self) -> None:
        r = assess_support(
            "CBD raises clobazam levels via CYP pathway",
            _GEFFREY, cannabinoid="CBD", partner_drug="clobazam",
            direction_hint="increase",
        )
        self.assertEqual(r.verdict, Verdict.SUPPORTED)
        self.assertIn("clobazam", r.matched)

    def test_partner_drug_absent_flags(self) -> None:
        r = assess_support(
            "CBD raises warfarin INR",
            _GEFFREY, cannabinoid="CBD", partner_drug="warfarin",
            direction_hint="increase",
        )
        self.assertEqual(r.verdict, Verdict.UNVERIFIED)
        self.assertIn("warfarin", r.missing)

    def test_cyp_family_match_3a4_vs_3a(self) -> None:
        # Claim CYP3A4 should match an abstract that writes only "CYP3A".
        r = assess_support(
            "CBD inhibits CYP3A4",
            "cannabidiol inhibited CYP3A in microsomes",
            cannabinoid="CBD", cyp_isoform="CYP3A4", direction_hint="inhibits",
        )
        self.assertEqual(r.verdict, Verdict.SUPPORTED)


if __name__ == "__main__":
    unittest.main()
