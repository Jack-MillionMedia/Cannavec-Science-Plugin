"""Lane-registry single-source invariants (critical-path #5b).

The advertised discover breadth lived in several independently-maintained lists
that drifted: the web-API ``live.default_runners()`` / ``SUPPORTED_SOURCES``, the
CLI ``_DISCOVERER_REGISTRY``, and the synthesizer's ``_SOURCE_KEYS``. The drift
that mattered: a lane the CLI can run whose rows the synthesizer does NOT iterate
is silently dropped from the cross-source convergence verdict (this caught
``openalex``). These guards make such drift fail loudly on every test run instead
of shipping as a silent breadth overclaim / silent data loss.

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cannavec_science.live as live
import cannavec_science.synthesis as synthesis
from cannavec_science.__main__ import _DISCOVERER_REGISTRY


class TestLaneRegistryInvariants(unittest.TestCase):
    def test_synthesis_covers_every_cli_lane(self) -> None:
        # Every lane the CLI can fan out to MUST be iterated by the synthesizer,
        # or that lane's rows are silently excluded from the convergence verdict.
        cli = set(_DISCOVERER_REGISTRY.keys())
        synth = set(synthesis._SOURCE_KEYS)
        missing = cli - synth
        self.assertEqual(
            missing, set(),
            f"CLI discover lanes the synthesizer silently ignores: {missing}. "
            f"Add them to synthesis._SOURCE_KEYS.",
        )

    def test_web_api_supported_sources_match_runners(self) -> None:
        # SUPPORTED_SOURCES is the advertised web-API lane set; it must equal the
        # lanes actually wired in default_runners() (single source of truth).
        self.assertEqual(
            set(live.SUPPORTED_SOURCES), set(live.default_runners().keys()),
            "live.SUPPORTED_SOURCES drifted from live.default_runners().",
        )

    def test_web_api_lanes_are_real_cli_lanes(self) -> None:
        # The web API must not advertise a lane the CLI registry doesn't know.
        dr = set(live.default_runners().keys())
        cli = set(_DISCOVERER_REGISTRY.keys())
        self.assertTrue(
            dr <= cli,
            f"web-API lanes not in the CLI registry: {dr - cli}",
        )

    def test_every_synthesis_source_has_a_display_label(self) -> None:
        # render_markdown does ``_SOURCE_DISPLAY[s]`` for every s in _SOURCE_KEYS;
        # a missing label is a hard KeyError at render time. Lock the alignment.
        keys = set(synthesis._SOURCE_KEYS)
        labelled = set(synthesis._SOURCE_DISPLAY.keys())
        missing = keys - labelled
        self.assertEqual(
            missing, set(),
            f"synthesis._SOURCE_KEYS lanes with no _SOURCE_DISPLAY label: "
            f"{missing}",
        )


if __name__ == "__main__":
    unittest.main()
