"""Tests for cannavec.source_health (spec 002 US7 — Wave C).

Per-source health probe + persistence to state/source_health.json +
green/yellow/red status mapping. Mirrors the established discoverer
test pattern: injected probe (replaces fetcher), no real network.

elite-expert-engine-002 US7
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.source_health import (  # noqa: E402
    HealthStatus,
    SourceHealth,
    load_health_state,
    ping,
    ping_all,
    save_health_state,
)


# ── Probe stub helpers ──────────────────────────────────────────────────


def _fast_probe(_url: str) -> float:
    """Simulates a fast network probe (< 5 s)."""
    return 0.3  # latency in seconds


def _slow_probe(_url: str) -> float:
    """Simulates a slow but successful probe (between 5 and 15 s)."""
    return 7.5


def _failing_probe(_url: str) -> float:
    raise OSError("connection refused")


# ── 1. Status mapping ───────────────────────────────────────────────────


class StatusMappingTests(unittest.TestCase):
    def test_green_when_fast_success(self) -> None:
        health = ping("pubmed", probe=_fast_probe)
        self.assertEqual(health.status, HealthStatus.GREEN)
        self.assertIsNotNone(health.latency_ms)
        self.assertLess(health.latency_ms, 5000)
        self.assertIsNotNone(health.last_success_iso)
        self.assertIsNone(health.error_excerpt)

    def test_yellow_when_slow_success(self) -> None:
        health = ping("ctgov", probe=_slow_probe)
        self.assertEqual(health.status, HealthStatus.YELLOW)
        self.assertGreaterEqual(health.latency_ms, 5000)
        self.assertLess(health.latency_ms, 15000)

    def test_red_when_probe_raises(self) -> None:
        health = ping("chembl", probe=_failing_probe)
        self.assertEqual(health.status, HealthStatus.RED)
        self.assertIsNotNone(health.error_excerpt)
        self.assertIn("connection refused", health.error_excerpt)


# ── 2. Source name validation ────────────────────────────────────────────


class SourceNameTests(unittest.TestCase):
    def test_known_source_succeeds(self) -> None:
        for name in ("pubmed", "chembl", "ctgov", "biorxiv", "medrxiv",
                     "courtlistener"):
            with self.subTest(source=name):
                health = ping(name, probe=_fast_probe)
                self.assertEqual(health.source, name)

    def test_unknown_source_raises(self) -> None:
        with self.assertRaises(ValueError):
            ping("unknown_source", probe=_fast_probe)


# ── 3. ping_all ─────────────────────────────────────────────────────────


class PingAllTests(unittest.TestCase):
    def test_returns_one_per_source(self) -> None:
        results = ping_all(probe=_fast_probe)
        names = {r.source for r in results}
        self.assertEqual(names, {
            # Original Spec-002 set.
            "pubmed", "chembl", "ctgov", "biorxiv", "medrxiv", "courtlistener",
            # Cannabis-primary-source widening (life-science skill layer).
            "pubchem", "pharmgkb", "rcsb", "opentargets", "gwas", "bindingdb",
            # Spec 005 US6 — Europe PMC twelfth primary-source live lane.
            "europepmc",
        })


# ── 4. Persistence ───────────────────────────────────────────────────────


class PersistenceTests(unittest.TestCase):
    def test_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source_health.json"
            results = ping_all(probe=_fast_probe)
            save_health_state(results, state_path=path)
            self.assertTrue(path.exists())
            loaded = load_health_state(state_path=path)
            self.assertEqual(len(loaded), len(results))
            for orig, after in zip(
                sorted(results, key=lambda r: r.source),
                sorted(loaded, key=lambda r: r.source),
            ):
                self.assertEqual(orig.source, after.source)
                self.assertEqual(orig.status, after.status)

    def test_load_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "does_not_exist.json"
            loaded = load_health_state(state_path=path)
            self.assertEqual(loaded, [])


# ── 5. Dataclass invariants ──────────────────────────────────────────────


class DataclassInvariantTests(unittest.TestCase):
    def test_error_excerpt_only_on_red(self) -> None:
        green = ping("pubmed", probe=_fast_probe)
        self.assertIsNone(green.error_excerpt)
        red = ping("pubmed", probe=_failing_probe)
        self.assertIsNotNone(red.error_excerpt)


# ── 6. Serialisation ─────────────────────────────────────────────────────


class SerialisationTests(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        health = ping("pubmed", probe=_fast_probe)
        d = health.to_dict()
        self.assertEqual(d["source"], "pubmed")
        self.assertEqual(d["status"], "green")
        # Re-serialise via json
        text = json.dumps(d)
        back = json.loads(text)
        self.assertEqual(back["source"], "pubmed")


# ── 7. Discover unreachable handling (integration smoke) ────────────────


class DiscoverIntegrationTests(unittest.TestCase):
    """Smoke test: `cannavec discover` should mark sources unreachable
    via the same per-source NetworkError → unreachable mapping the
    contract documents. The actual CLI test lives in test_cli.py;
    here we just verify the helper exists."""

    def test_helper_module_imports(self) -> None:
        from cannavec_science import source_health
        self.assertTrue(hasattr(source_health, "ping"))
        self.assertTrue(hasattr(source_health, "ping_all"))


if __name__ == "__main__":
    unittest.main()
