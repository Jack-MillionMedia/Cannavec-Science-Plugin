"""Tests for cannavec.discover_guard (spec 002 foundational layer).

`discover_guard` is the single auditable safety + banned-pattern
preflight that every per-source discoverer MUST call as the first
line of its `search()` method. Centralising it makes the FR-002
sequencing — "preflight BEFORE any network call" — impossible to
silently bypass on a future source.

Also exercises the Provenance enum (FR-017) which extends the
existing `live_search` provenance tag to per-source values.

elite-expert-engine-002 foundational
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.discover_guard import (  # noqa: E402
    DiscoverRefused,
    Provenance,
    preflight,
)


class ProvenanceEnumTests(unittest.TestCase):
    """The provenance enum extends, not replaces, the existing tag.

    Per FR-017: five live-source values, plus continuity with the
    pre-existing `live_search` tag (now aliased to `live_pubmed`).
    """

    # Spec 002 baseline (5 values) plus spec 003 US5+US6 additions
    # (12 values: 3 federal openFDA + 4 state ARS + USPTO + 4 standards
    # bodies). Total = 17. The dedicated parity guard for the extended
    # enum lives in tests/test_provenance_extended.py — this test just
    # pins the spec-002 floor.
    EXPECTED_SPEC_002_VALUES = {
        "live_pubmed",
        "live_chembl",
        "live_ctgov",
        "live_preprint",
        "live_courtlistener",
    }

    def test_enum_has_exactly_five_live_values(self) -> None:
        present = {p.value for p in Provenance}
        # All spec-002 values must remain present.
        self.assertTrue(self.EXPECTED_SPEC_002_VALUES.issubset(present))
        # All other values MUST be spec-003 additions starting with
        # live_ — see tests/test_provenance_extended.py for the
        # canonical enumeration.
        spec_003 = present - self.EXPECTED_SPEC_002_VALUES
        for v in spec_003:
            self.assertTrue(v.startswith("live_"), f"unexpected: {v!r}")

    def test_each_value_is_str_subclass(self) -> None:
        for p in Provenance:
            with self.subTest(p=p):
                self.assertIsInstance(p.value, str)
                self.assertIsInstance(p, str)

    def test_lookup_by_value(self) -> None:
        self.assertEqual(Provenance("live_chembl"), Provenance.LIVE_CHEMBL)
        self.assertEqual(Provenance("live_ctgov"), Provenance.LIVE_CTGOV)
        self.assertEqual(Provenance("live_pubmed"), Provenance.LIVE_PUBMED)

    def test_invalid_value_raises(self) -> None:
        with self.assertRaises(ValueError):
            Provenance("live_nonexistent")


class DiscoverRefusedTests(unittest.TestCase):
    def test_carries_reason_and_detail(self) -> None:
        exc = DiscoverRefused("safety:adolescent_thc", "user asked about their own dose")
        self.assertEqual(exc.reason, "safety:adolescent_thc")
        self.assertEqual(exc.detail, "user asked about their own dose")

    def test_str_includes_reason(self) -> None:
        exc = DiscoverRefused("banned:cultivar_as_effect")
        self.assertIn("cultivar_as_effect", str(exc))

    def test_detail_optional(self) -> None:
        exc = DiscoverRefused("safety:overdose_question")
        self.assertEqual(exc.detail, "")


class PreflightSafePromptsTests(unittest.TestCase):
    """Educational / population-level prompts MUST pass preflight."""

    PASSING_PROMPTS = (
        "CBD CB1 binding",
        "PTSD cannabinoid trials phase 3",
        "Cannabidiol pharmacokinetics review",
        "Section 280E cannabis dispensary federal opinions",
        "Optimal PPFD for cannabis flowering",
    )

    def test_each_safe_prompt_returns_none(self) -> None:
        for prompt in self.PASSING_PROMPTS:
            with self.subTest(prompt=prompt):
                self.assertIsNone(preflight(prompt))


class PreflightBannedPatternTests(unittest.TestCase):
    """A banned-pattern hit MUST raise DiscoverRefused.

    The standard banned-pattern surface is reused — we do not invent
    a per-source banned set.
    """

    BANNED_PROMPTS = (
        ("indica cures cancer", "banned"),
        ("OG Kush is good for pain relief", "banned"),
    )

    def test_each_banned_prompt_raises(self) -> None:
        for prompt, reason_prefix in self.BANNED_PROMPTS:
            with self.subTest(prompt=prompt):
                with self.assertRaises(DiscoverRefused) as ctx:
                    preflight(prompt)
                self.assertTrue(
                    ctx.exception.reason.startswith(reason_prefix),
                    f"Expected reason to start with '{reason_prefix}', "
                    f"got '{ctx.exception.reason}'.",
                )


class PreflightSafetyTests(unittest.TestCase):
    """A safety refuse verdict MUST raise DiscoverRefused.

    Cannabis-question safety flags that map to REFUSE (individualized
    medical or harmful) MUST short-circuit before any network call.
    """

    UNSAFE_PROMPTS = (
        "What dose of CBD should I take for my insomnia?",  # individualized dosing
        "How do I synthesize K2 / Spice?",                  # harmful
    )

    def test_each_unsafe_prompt_raises(self) -> None:
        for prompt in self.UNSAFE_PROMPTS:
            with self.subTest(prompt=prompt):
                with self.assertRaises(DiscoverRefused) as ctx:
                    preflight(prompt)
                self.assertTrue(
                    ctx.exception.reason.startswith("safety:")
                    or ctx.exception.reason.startswith("banned:"),
                    f"Expected reason to start with 'safety:' or 'banned:', "
                    f"got '{ctx.exception.reason}'.",
                )


class PreflightPrecedenceTests(unittest.TestCase):
    """When both safety and banned-pattern fire, banned-pattern wins.

    A `cultivar_as_effect` banned-pattern is a clearer signal than
    a `pain_relief` safety flag, and the refusal message is more
    actionable for the reader.
    """

    def test_banned_takes_precedence(self) -> None:
        # This prompt fires BOTH cultivar_as_effect (banned) AND
        # individualized_dosing + individualized_medical (safety).
        # The contract is: banned wins for actionable refusal text.
        prompt = "OG Kush is the best for insomnia, what dose should I take?"
        with self.assertRaises(DiscoverRefused) as ctx:
            preflight(prompt)
        self.assertTrue(
            ctx.exception.reason.startswith("banned:"),
            f"Expected banned: precedence, got '{ctx.exception.reason}'.",
        )


class PreflightDeterminismTests(unittest.TestCase):
    """Same prompt → same verdict, every time."""

    def test_safe_prompt_deterministic(self) -> None:
        for _ in range(3):
            self.assertIsNone(preflight("CBD CB1 binding"))

    def test_refused_prompt_deterministic(self) -> None:
        reasons: list[str] = []
        for _ in range(3):
            try:
                preflight("indica cures cancer")
            except DiscoverRefused as exc:
                reasons.append(exc.reason)
        self.assertEqual(len(set(reasons)), 1)


class PreflightEmptyInputTests(unittest.TestCase):
    """An empty prompt is a programming error, not a user input.

    We surface it via ValueError so the calling discoverer can
    distinguish an empty-string bug from a refused real prompt.
    """

    def test_empty_string_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            preflight("")

    def test_whitespace_only_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            preflight("   \n\t  ")


if __name__ == "__main__":
    unittest.main()
