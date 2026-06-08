"""Off-knowledge-base efficacy refusal is driven by claim coverage, not a
hardcoded indication vocabulary (§I / M2 / §VII).

The honest "No curated efficacy evidence for X" override used to be gated on a
hand-curated ~14-disease allowlist (``intent._INDICATION_PATTERNS``). Any disease
*outside* that list (diabetes, breast cancer, lupus, endometriosis, Graves …)
fell through to a confident grade-led BLUF — "**Low-certainty evidence (Level C —
observational / single small trial).**" — stitched onto a BM25-recovered
*off-topic* mechanism / drug-interaction row. A clinician skimming the bold lead
reads "there is low-certainty efficacy evidence for this compound in this
disease," which is false: the exact citation→claim binding lie this project
exists to prevent, displaced from efficacy claims onto mechanism/interaction
claims.

The fix decouples the refusal from vocabulary membership: when the prompt asks an
efficacy question about an indication and NO surviving curated clinical-efficacy
claim covers it, the answer is an honest refusal with an empty graded-claim set —
regardless of whether the disease was hand-listed. Curated indications (Dravet,
chronic pain) and condition-agnostic pharmacology questions are untouched.

Stdlib only, fully offline, deterministic — positive + negative per Constitution
§III.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import ClaimType


def _has_efficacy_certainty_frame(short_answer: str) -> bool:
    """Does the BLUF lead with a clinical-evidence *certainty* frame?

    These frame strings ("Moderate-certainty evidence (Level B …)", "Low-certainty
    evidence (Level C …)") assert graded clinical evidence. Stitched onto an
    off-topic recovered row for an uncurated indication, that assertion is the
    confident-wrong-answer this suite forbids.
    """
    sa = (short_answer or "").lower()
    return "certainty evidence (level" in sa


class OffKbEfficacyQuestionRefusesHonestly(unittest.TestCase):
    """A cannabinoid-for-<uncurated-disease> efficacy question must refuse
    honestly even when the disease is NOT in the indication vocabulary."""

    UNCURATED = (
        ("CBD for diabetes", "diabetes"),
        ("CBD for breast cancer", "cancer"),
        ("CBD for lupus", "lupus"),
    )

    def test_bluf_is_honest_no_curated_efficacy(self):
        for prompt, needle in self.UNCURATED:
            with self.subTest(prompt=prompt):
                a = compose_answer(prompt)
                sa = (a.short_answer or "").lower()
                self.assertIn(
                    "no curated", sa,
                    f"BLUF should refuse honestly, got: {a.short_answer!r}",
                )
                self.assertIn(
                    needle, sa,
                    f"BLUF should name the indication, got: {a.short_answer!r}",
                )

    def test_bluf_does_not_assert_a_graded_evidence_frame(self):
        for prompt, _ in self.UNCURATED:
            with self.subTest(prompt=prompt):
                a = compose_answer(prompt)
                self.assertFalse(
                    _has_efficacy_certainty_frame(a.short_answer),
                    f"BLUF asserts graded evidence for an uncurated "
                    f"indication: {a.short_answer!r}",
                )

    def test_no_graded_claim_is_surfaced(self):
        for prompt, _ in self.UNCURATED:
            with self.subTest(prompt=prompt):
                a = compose_answer(prompt)
                self.assertEqual(
                    a.evidence_summary.highest_grade.value, "Unsupported",
                    f"an uncurated indication must surface no graded claim; "
                    f"claims={[c.text[:50] for c in a.claims]}",
                )
                self.assertEqual(
                    [c for c in a.claims
                     if c.claim_type == ClaimType.CLINICAL_EFFICACY],
                    [],
                    "no clinical-efficacy claim may be bound to an uncurated "
                    "indication",
                )


class OffTopicMechanismClaimDoesNotLeak(unittest.TestCase):
    """The Hashimoto's-thyroiditis review (PMID 20191092) is a universal
    immunomodulation magnet; it must not bind to unrelated questions."""

    LEAK_PMID = "20191092"
    PROMPTS = (
        "THC for Alzheimer disease agitation",
        "CBD for Parkinson disease tremor",
        "THC for Crohn disease",
    )

    def test_hashimoto_claim_does_not_bind_to_unrelated_indication(self):
        for prompt in self.PROMPTS:
            with self.subTest(prompt=prompt):
                a = compose_answer(prompt)
                leaked = [
                    c.text[:60]
                    for c in a.claims
                    for s in c.sources
                    if s.pmid == self.LEAK_PMID
                ]
                self.assertEqual(
                    leaked, [],
                    f"off-topic Hashimoto's claim leaked into {prompt!r}: "
                    f"{leaked}",
                )


class CuratedAndPharmacologyQueriesAreUntouched(unittest.TestCase):
    """The refusal must NOT over-fire: curated indications keep their graded
    answer and condition-agnostic pharmacology questions are not refused."""

    def test_dravet_still_grades_level_b(self):
        a = compose_answer("CBD for Dravet")
        self.assertEqual(a.evidence_summary.highest_grade.value, "Level B")
        self.assertNotIn("no curated", (a.short_answer or "").lower())

    def test_chronic_pain_still_grades_level_a(self):
        a = compose_answer("CBD for chronic pain")
        self.assertEqual(a.evidence_summary.highest_grade.value, "Level A")
        self.assertNotIn("no curated", (a.short_answer or "").lower())

    def test_pharmacology_question_is_not_refused_as_uncurated(self):
        # A mechanism / receptor-pharmacology question names no indication —
        # it must not be swept into the efficacy refusal.
        a = compose_answer("CB1 partial agonism of THC")
        self.assertNotIn(
            "no curated", (a.short_answer or "").lower(),
            f"pharmacology question wrongly refused: {a.short_answer!r}",
        )


if __name__ == "__main__":
    unittest.main()
