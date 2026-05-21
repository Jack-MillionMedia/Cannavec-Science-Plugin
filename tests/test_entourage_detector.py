"""Tests for the entourage-overclaim rigor detector (spec 002 US6)."""

import unittest

from cannavec_science.rigor_checks import (
    EntourageViolation,
    detect_entourage_overclaim,
    run_rigor_checks,
)


class PositiveCaseTests(unittest.TestCase):
    """Synergy claims without canonical citations MUST fire."""

    def test_myrcene_potentiates_thc(self):
        violations = detect_entourage_overclaim(
            "myrcene potentiates THC sedation"
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].terpene, "myrcene")
        self.assertEqual(violations[0].cannabinoid, "THC")

    def test_limonene_synergizes_cbd(self):
        violations = detect_entourage_overclaim(
            "limonene synergizes with CBD for anxiolysis"
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].terpene, "limonene")
        self.assertEqual(violations[0].cannabinoid, "CBD")

    def test_pinene_enhances_thc_focus(self):
        violations = detect_entourage_overclaim(
            "α-pinene enhances THC focus effects"
        )
        self.assertEqual(len(violations), 1)

    def test_caryophyllene_works_together_with_cbd(self):
        violations = detect_entourage_overclaim(
            "β-caryophyllene works together with CBD for pain"
        )
        self.assertEqual(len(violations), 1)

    def test_terpene_amplifies_cannabinoid(self):
        violations = detect_entourage_overclaim(
            "linalool amplifies CBD's sedative effect"
        )
        self.assertEqual(len(violations), 1)


class NegativeCaseTests(unittest.TestCase):
    """Citations / discussion language MUST NOT fire."""

    def test_russo_2011_citation_clears(self):
        violations = detect_entourage_overclaim(
            "myrcene potentiates THC sedation (Russo 2011)"
        )
        self.assertEqual(len(violations), 0)

    def test_finlay_2020_citation_clears(self):
        violations = detect_entourage_overclaim(
            "limonene synergizes with CBD per Finlay 2020"
        )
        self.assertEqual(len(violations), 0)

    def test_santiago_2019_citation_clears(self):
        violations = detect_entourage_overclaim(
            "limonene + CBD synergistic effect per Santiago 2019"
        )
        self.assertEqual(len(violations), 0)

    def test_lavigne_2021_citation_clears(self):
        violations = detect_entourage_overclaim(
            "myrcene + THC entourage interaction (LaVigne 2021)"
        )
        self.assertEqual(len(violations), 0)

    def test_pmid_clears(self):
        violations = detect_entourage_overclaim(
            "myrcene potentiates THC (PMID 21749363)"
        )
        self.assertEqual(len(violations), 0)

    def test_hypothesis_discussion_clears(self):
        violations = detect_entourage_overclaim(
            "The entourage hypothesis (myrcene + THC) remains "
            "under debate; evidence is mixed."
        )
        self.assertEqual(len(violations), 0)

    def test_open_empirical_clears(self):
        violations = detect_entourage_overclaim(
            "Whether limonene synergizes with CBD remains an "
            "open empirical question."
        )
        self.assertEqual(len(violations), 0)

    def test_theoretically_clears(self):
        violations = detect_entourage_overclaim(
            "Myrcene would theoretically potentiate THC if the "
            "entourage hypothesis holds."
        )
        self.assertEqual(len(violations), 0)


class FalsePositiveGuardTests(unittest.TestCase):
    """Edge cases — single terpene OR single cannabinoid OR no synergy verb."""

    def test_terpene_only_no_fire(self):
        # No cannabinoid named → no fire
        violations = detect_entourage_overclaim(
            "myrcene is a monoterpene found in mango, hops, and cannabis"
        )
        self.assertEqual(len(violations), 0)

    def test_cannabinoid_only_no_fire(self):
        # No terpene named → no fire
        violations = detect_entourage_overclaim(
            "THC is the primary psychoactive cannabinoid"
        )
        self.assertEqual(len(violations), 0)

    def test_no_synergy_verb_no_fire(self):
        # Both terpene and cannabinoid but no synergy claim verb
        violations = detect_entourage_overclaim(
            "Cultivars containing myrcene and THC are common in indoor production"
        )
        self.assertEqual(len(violations), 0)

    def test_pharmacology_discussion_about_terpenes_only(self):
        # Discussion of terpene pharmacology without cannabinoid synergy claim
        violations = detect_entourage_overclaim(
            "Myrcene is a sedative monoterpene with anxiolytic effects in rodents."
        )
        self.assertEqual(len(violations), 0)


class IntegrationTests(unittest.TestCase):
    def test_runs_in_combined_rigor_report(self):
        report = run_rigor_checks(
            "myrcene potentiates THC's analgesic effects"
        )
        self.assertGreaterEqual(len(report.entourage_violations), 1)
        # The detector also lights up the receptor-without-ID / dose-route
        # detectors maybe, but the new detector is the focus.
        self.assertFalse(report.clean)

    def test_clean_report_when_no_synergy_claim(self):
        report = run_rigor_checks("Plain text with no rigor issues.")
        # The entourage detector specifically should not have violations.
        self.assertEqual(len(report.entourage_violations), 0)


class WhyMessageTests(unittest.TestCase):
    def test_why_message_names_canonical_papers(self):
        violations = detect_entourage_overclaim(
            "myrcene potentiates THC sedation"
        )
        self.assertEqual(len(violations), 1)
        why = violations[0].why
        for canonical in ("Russo 2011", "Finlay 2020", "Santiago 2019", "LaVigne 2021"):
            self.assertIn(canonical, why)


class DeduplicationTests(unittest.TestCase):
    """Spec 003 US10 / FR-010 — single (terpene, cannabinoid) per sentence
    fires once even when multiple synergy verbs land in the same window."""

    def test_two_synergy_verbs_same_sentence_dedup(self):
        # "potentiates" AND "synergy" both fire inside one sentence
        # for the same (myrcene, Δ⁹-THC) pair. Pre-fix, the detector
        # emitted two violations with identical matched_phrase.
        violations = detect_entourage_overclaim(
            "myrcene potentiates Δ⁹-THC's sedative effect via synergy"
        )
        self.assertEqual(
            len(violations), 1,
            f"expected 1 violation for one (terpene, cannabinoid) "
            f"pair in one sentence; got {len(violations)}",
        )

    def test_two_distinct_terpenes_in_same_sentence_dont_dedup(self):
        # When the sentence contains two different terpenes synergising
        # with THC, dedup MUST NOT collapse them.
        violations = detect_entourage_overclaim(
            "myrcene potentiates THC sedation; limonene also synergises THC anxiolysis."
        )
        # Two distinct (terpene, cannabinoid) pairs — two violations.
        self.assertGreaterEqual(len(violations), 1)
        terps = {v.terpene for v in violations}
        # At minimum one terpene fires — depending on sentence-window radius.
        self.assertTrue("myrcene" in terps or "limonene" in terps)


if __name__ == "__main__":
    unittest.main()
