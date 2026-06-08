"""Rigor / banned-pattern detectors must be condition-AGNOSTIC, not an
allowlist coverage lottery (§VI / §VII).

An adversarial stress test (2026-06-07) showed the cure / efficacy / safety
overclaim detectors only fire for a hand-listed set of condition names or regex
shapes, so the most NATURAL overclaims passed clean — a green ``rigor`` result
meant "avoided ~20 allowlisted condition names", not "no overclaim":

- ``cures ALS`` / ``cures everything`` / ``cure-all`` / ``cured Huntington's`` —
  all clean (cure_claim required a member of a fixed ~20-condition allowlist).
- ``CBD is 100% effective for seizures`` / ``never fails`` — clean
  (absolutist_efficacy matched "effective in 100%", not "100% effective for").
- ``CBD is a miracle drug`` / ``wonder drug`` / ``game-changer`` — clean
  (no miracle/wonder-drug detector; "miracle" only fired adjacent to an
  allowlisted condition).
- ``there are no risks`` / ``carries no risk of harm`` — clean
  (false_safety keyed on "safe"/"side-effects", never "risk").

A green ``rigor`` must mean the text avoided the overclaim CLASS, not a specific
vocabulary. The fix must not start flagging legitimate scientific language
(quantified effects, "cure rate", "Breakthrough Therapy designation", "low risk
of", past-tense trial safety reports) or negated rebuttals.

Stdlib only, offline, deterministic — positive + negative per Constitution §III.
"""

from __future__ import annotations

import unittest

from cannavec_science.banned_patterns import detect_banned_patterns


def _ids(text: str) -> set[str]:
    return {h.pattern.id for h in detect_banned_patterns(text)}


class CureClaimsAreConditionAgnostic(unittest.TestCase):
    MUST_FLAG = (
        "Cannabis cures ALS",
        "CBD cures everything",
        "CBD is a cure-all for chronic illness",
        "CBD cured her Huntington's disease",
        "cannabis cures any disease",
        "THC cures glaucoma completely",
    )

    def test_cure_claims_flag(self):
        for text in self.MUST_FLAG:
            with self.subTest(text=text):
                self.assertTrue(
                    detect_banned_patterns(text),
                    f"cure overclaim passed clean: {text!r}",
                )


class AbsolutistEfficacyCoversNaturalPhrasing(unittest.TestCase):
    MUST_FLAG = (
        "CBD is 100% effective for seizures",
        "this treatment never fails",
        "THC is completely effective for nausea",
    )

    def test_absolutist_efficacy_flags(self):
        for text in self.MUST_FLAG:
            with self.subTest(text=text):
                self.assertIn(
                    "absolutist_efficacy", _ids(text),
                    f"absolutist efficacy passed clean: {text!r}",
                )


class MiracleAndWonderDrugFraming(unittest.TestCase):
    MUST_FLAG = (
        "CBD is a miracle drug",
        "THC is a wonder drug for pain",
        "cannabis is a game-changer for medicine",
        "this is nature's perfect medicine",
    )

    def test_miracle_framing_flags(self):
        for text in self.MUST_FLAG:
            with self.subTest(text=text):
                self.assertTrue(
                    detect_banned_patterns(text),
                    f"miracle/wonder framing passed clean: {text!r}",
                )


class NoRiskSafetyOverclaims(unittest.TestCase):
    MUST_FLAG = (
        "there are no risks with CBD",
        "CBD carries no risk of harm",
        "THC has no risk whatsoever",
    )

    def test_no_risk_framing_flags(self):
        for text in self.MUST_FLAG:
            with self.subTest(text=text):
                self.assertIn(
                    "false_safety_claim", _ids(text),
                    f"no-risk safety overclaim passed clean: {text!r}",
                )


class LegitimateScientificLanguageIsNotFlagged(unittest.TestCase):
    """The broadening must not create false positives on rigorous prose."""

    MUST_BE_CLEAN = (
        "CBD reduced convulsive-seizure frequency by 39% vs placebo (Devinsky 2017)",
        "the cure rate for the condition was 40% at 12 months",
        "Epidiolex received FDA Breakthrough Therapy designation",
        "the trial reported a low risk of adverse events",
        "no serious adverse events were observed in n=120 over 14 weeks",
        "cannabis does not cure cancer",
    )

    def test_rigorous_prose_is_clean(self):
        for text in self.MUST_BE_CLEAN:
            with self.subTest(text=text):
                self.assertEqual(
                    _ids(text), set(),
                    f"false positive on legitimate prose: {text!r} "
                    f"-> {_ids(text)}",
                )


if __name__ == "__main__":
    unittest.main()
