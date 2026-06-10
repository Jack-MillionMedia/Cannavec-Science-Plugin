"""§I / M2 / §VII — the off-KB efficacy refusal must hold for the NATURAL
phrasings a researcher actually types, not only "<cannabinoid> for <disease>".

Two confident-wrong-answer leaks were reproduced (2026-06-09 first-principles
audit) where the structural efficacy backstop silently let an off-knowledge-base
disease through to a graded BLUF stitched onto a BM25-recovered off-topic row —
the citation->claim binding lie this project exists to prevent:

1. **Cannabinoid-first "to treat" frame.** ``What is the evidence for CBD to
   treat breast cancer?`` rendered a confident "**High certainty (Level A …)**"
   brief citing chronic-pain Cochrane/JAMA reviews as breast-cancer evidence.
   ``_EFFICACY_FRAME_RX.search`` matched the FIRST preposition (``for`` in
   "evidence FOR CBD"), captured indication "CBD to treat breast cancer", saw a
   cannabinoid head, and returned ``None`` — so the honest override never fired.
   A non-greedy preposition scan must skip the cannabinoid head and find the
   later ``to treat <indication>`` frame.

2. **Efficacy verbs the frame did not list.** ``Does cannabis help with
   diabetes?`` / ``Is THC useful in endometriosis?`` / ``Does CBD work for Graves
   disease?`` used efficacy phrasings ("help with", "useful in", "work for") the
   preposition set never enumerated, so neither the vocabulary path nor the
   structural backstop fired and the off-topic recovery led the BLUF.

The fix widens the structural frame to efficacy-SPECIFIC verbs only (never bare
"and", which would over-refuse mechanism / PK / interaction questions) and makes
the scan iterate past a cannabinoid head. The safe failure direction is honest
over-refusal, NEVER a confident wrong answer — but it must not regress curated
indications (the cannabinoid-first "to treat Dravet" form stays covered) or
condition-agnostic pharmacology questions (which carry no efficacy frame and must
keep their claims).

Stdlib only, fully offline, deterministic — positive + negative per Constitution
§III.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import ClaimType


def _has_efficacy_certainty_frame(short_answer: str) -> bool:
    """Does the BLUF lead with a graded clinical-evidence certainty frame
    ("High certainty (Level A …)", "Low-certainty evidence (Level C …)")? Stitched
    onto an off-topic recovered row for an uncurated indication, that assertion is
    the confident-wrong-answer this suite forbids."""
    sa = (short_answer or "").lower()
    return "certainty evidence (level" in sa or "certainty (level" in sa


def _was_uncovered_cleared(answer) -> bool:
    return any(key == "binding.uncovered_indication_cleared" for key, _ in answer.trace)


class NaturalPhrasingOffKbEfficacyRefusesHonestly(unittest.TestCase):
    """The reproduced leak phrasings must refuse honestly — no graded efficacy
    frame and no clinical-efficacy claim bound to the uncurated indication."""

    # (prompt, indication-substring the honest BLUF must name)
    MUST_REFUSE = (
        ("What is the evidence for CBD to treat breast cancer?", "cancer"),
        ("What is the evidence for THC to treat lupus?", "lupus"),
        ("Does cannabis help with diabetes?", "diabetes"),
        ("Is THC useful in endometriosis?", "endometriosis"),
        ("Does CBD work for Graves disease?", "graves"),
        # Bare "treat" — the most natural efficacy verb — must be a frame too;
        # "Can CBD treat breast cancer" leaked a "Level C" BLUF (2026-06-09 review).
        ("Can CBD treat breast cancer", "cancer"),
        ("Does CBD treat psoriasis", "psoriasis"),
    )

    def test_no_graded_efficacy_frame_or_claim(self):
        for prompt, _ in self.MUST_REFUSE:
            with self.subTest(prompt=prompt):
                a = compose_answer(prompt)
                self.assertFalse(
                    _has_efficacy_certainty_frame(a.short_answer),
                    f"BLUF asserts graded evidence for an uncurated indication: "
                    f"{a.short_answer!r}",
                )
                self.assertEqual(
                    [c for c in a.claims
                     if c.claim_type == ClaimType.CLINICAL_EFFICACY],
                    [],
                    "no clinical-efficacy claim may be bound to an uncurated "
                    "indication",
                )

    def test_bluf_refuses_and_names_the_indication(self):
        for prompt, needle in self.MUST_REFUSE:
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


class CuratedIndicationStaysCoveredAcrossPhrasings(unittest.TestCase):
    """The fix must NOT start refusing curated indications — especially the
    cannabinoid-first 'to treat <curated-disease>' form the leak fix newly
    parses."""

    MUST_STAY_COVERED = (
        "What is the evidence for CBD to treat Dravet syndrome?",
        "What is the evidence for THC to treat neuropathic pain?",
        "CBD for Dravet syndrome",
    )

    def test_curated_indication_keeps_efficacy_claim(self):
        for prompt in self.MUST_STAY_COVERED:
            with self.subTest(prompt=prompt):
                a = compose_answer(prompt)
                self.assertFalse(
                    _was_uncovered_cleared(a),
                    f"curated indication was wrongly cleared as uncovered: "
                    f"{prompt!r}",
                )
                self.assertNotIn(
                    "no curated", (a.short_answer or "").lower(),
                    f"curated indication wrongly refused: {a.short_answer!r}",
                )
                self.assertTrue(
                    any(c.claim_type == ClaimType.CLINICAL_EFFICACY
                        for c in a.claims),
                    f"curated indication lost its efficacy claim: {prompt!r}",
                )


class ConditionAgnosticQuestionsAreNotOverRefused(unittest.TestCase):
    """Mechanism / pharmacokinetics / interaction questions carry no efficacy
    frame and must keep their claims — the widened frame must not sweep them into
    a 'no curated efficacy' refusal."""

    MUST_NOT_CLEAR = (
        "How does CBD interact with CYP3A4?",
        "What is the pharmacokinetics of THC?",
        "What is the mechanism of action of CBD at CB1 and CB2 receptors?",
    )

    def test_non_efficacy_questions_are_not_cleared(self):
        for prompt in self.MUST_NOT_CLEAR:
            with self.subTest(prompt=prompt):
                a = compose_answer(prompt)
                self.assertFalse(
                    _was_uncovered_cleared(a),
                    f"condition-agnostic question wrongly cleared as an "
                    f"uncovered efficacy indication: {prompt!r}",
                )


if __name__ == "__main__":
    unittest.main()
