"""Tests for spec 004 US4 / FR-005 — indica/sativa-as-pharmacology
abstract-framing banned pattern.

v0.3 caught the prose form (\"indica strains are sedating\") but the
abstract meta-framing (\"indica vs sativa pharmacological differences\")
slipped through. v0.4 adds a sibling banned pattern that catches the
abstract framing without ensnaring legitimate botanical-taxonomy framings
of the genus.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.banned_patterns import detect_banned_patterns


class AbstractFramingFires(unittest.TestCase):
    def test_indica_vs_sativa_pharmacological_differences(self):
        hits = detect_banned_patterns(
            "indica vs sativa pharmacological differences"
        )
        ids = [h.pattern.id for h in hits]
        self.assertIn("indica_sativa_as_pharmacology_abstract", ids)

    def test_indica_vs_sativa_effects(self):
        hits = detect_banned_patterns("indica vs sativa effects")
        ids = [h.pattern.id for h in hits]
        self.assertIn("indica_sativa_as_pharmacology_abstract", ids)

    def test_hybrid_pharmacology(self):
        hits = detect_banned_patterns("hybrid pharmacology")
        ids = [h.pattern.id for h in hits]
        self.assertIn("indica_sativa_as_pharmacology_abstract", ids)

    def test_indica_pharmacodynamics(self):
        hits = detect_banned_patterns("indica pharmacodynamics")
        ids = [h.pattern.id for h in hits]
        self.assertIn("indica_sativa_as_pharmacology_abstract", ids)

    def test_sativa_receptor_activity(self):
        hits = detect_banned_patterns("sativa receptor activity")
        ids = [h.pattern.id for h in hits]
        self.assertIn("indica_sativa_as_pharmacology_abstract", ids)


class BotanicalFramingEscapes(unittest.TestCase):
    """Spec 004 US4 / FR-005 — botany / taxonomy framings escape."""

    def test_cannabis_sativa_l_botanical_taxonomy(self):
        hits = detect_banned_patterns(
            "Cannabis sativa L. botanical taxonomy"
        )
        self.assertEqual(hits, [])

    def test_one_species_or_three(self):
        hits = detect_banned_patterns(
            "Is Cannabis sativa one species or three?"
        )
        self.assertEqual(hits, [])

    def test_species_debate(self):
        hits = detect_banned_patterns(
            "Cannabis sativa L. species debate"
        )
        self.assertEqual(hits, [])

    def test_indica_sativa_taxonomy_phrasing(self):
        # When "taxonomy" appears in the sentence, the negative lookahead
        # in the new pattern lets the prompt through.
        hits = detect_banned_patterns("indica vs sativa taxonomy")
        self.assertEqual(hits, [])

    def test_indica_sativa_systematics_phrasing(self):
        hits = detect_banned_patterns("indica vs sativa systematics")
        self.assertEqual(hits, [])

    def test_taxonomically_question(self):
        hits = detect_banned_patterns(
            "What does indica mean taxonomically?"
        )
        self.assertEqual(hits, [])


class V03ProseFormRegression(unittest.TestCase):
    """The original v0.3 pattern (indica_sativa_as_pharmacology, prose
    form) MUST still fire — regression-protected."""

    def test_indica_strains_are_sedating(self):
        hits = detect_banned_patterns(
            "Indica strains are sedating because they have more myrcene; "
            "sativa strains are energetic"
        )
        ids = [h.pattern.id for h in hits]
        self.assertIn("indica_sativa_as_pharmacology", ids)


class ComposeAnswerRefusalIntegration(unittest.TestCase):
    """End-to-end: the abstract-framing prompt now produces a refusal,
    not a silent zero-claim output."""

    def test_abstract_pharmacology_query_refused(self):
        a = compose_answer(
            "indica vs sativa pharmacological differences"
        )
        self.assertTrue(a.is_refusal)
        md = a.to_markdown()
        self.assertIn("Refusal", md)

    def test_botany_query_NOT_refused(self):
        # The botanical-taxonomy framing is research-grade botany.
        a = compose_answer("Is Cannabis sativa one species or three?")
        self.assertFalse(a.is_refusal)


class CrossWiringWithCultivationScience(unittest.TestCase):
    """The new abstract-framing pattern must not block legitimate
    cultivation-science prompts that name indica / sativa for taxonomic
    reasons. The cultivation_science.botanical_taxonomy row must surface."""

    def test_one_species_or_three_returns_claim(self):
        a = compose_answer("Is Cannabis sativa one species or three?")
        self.assertFalse(a.is_refusal)
        self.assertGreater(len(a.claims), 0)
        # Citation set includes Small & Cronquist OR Hillig OR McPartland.
        all_labels = " ".join(c.label for c in a.citations)
        self.assertTrue(
            "Small E & Cronquist" in all_labels
            or "Hillig" in all_labels
            or "McPartland" in all_labels,
            f"expected a taxonomy citation; got {all_labels[:200]}…",
        )


if __name__ == "__main__":
    unittest.main()
