"""Tests for cannavec_science.registries (spec 003 US8 / FR-008)."""

from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout

from cannavec_science.registries import (
    RegistryGroup,
    RegistryInventory,
    all_registry_groups,
    build_inventory,
    render_json,
    render_markdown,
)


class AllRegistryGroupsTests(unittest.TestCase):
    def test_canonical_order(self):
        names = all_registry_groups()
        # Spec 003 US8 acceptance: nine registries grouped in canonical order.
        self.assertEqual(names, (
            "major_cannabinoids",
            "minor_cannabinoids",
            "terpenes",
            "interactions",
            "adverse_events",
            "populations",
            "contraindications",
            "pharmacogenomics",
            "ecbome",
        ))


class BuildInventoryTests(unittest.TestCase):
    def test_all_registries_returns_nine_groups(self):
        inv = build_inventory("all")
        self.assertEqual(len(inv.groups), 9)
        self.assertGreater(inv.total_rows, 100)

    def test_single_registry_filter(self):
        inv = build_inventory("minor_cannabinoids")
        self.assertEqual(len(inv.groups), 1)
        self.assertEqual(inv.groups[0].name, "minor_cannabinoids")

    def test_unknown_registry_raises(self):
        with self.assertRaises(ValueError):
            build_inventory("nonexistent_xyz")

    def test_major_cannabinoid_inventory_has_thc_and_cbd(self):
        inv = build_inventory("major_cannabinoids")
        self.assertEqual(set(inv.groups[0].entries), {"THC", "CBD"})

    def test_minor_cannabinoid_inventory_includes_v02_additions(self):
        inv = build_inventory("minor_cannabinoids")
        entries = set(inv.groups[0].entries)
        # v0.2 added Δ⁸-THC, HHC, THCO, THCP plus the v0.1 set.
        for required in ("Δ⁸-THC", "HHC", "THCO", "THCP",
                         "THCV", "CBDV", "CBC", "CBN", "CBG"):
            self.assertIn(required, entries)

    def test_ecbome_inventory_present(self):
        inv = build_inventory("ecbome")
        self.assertGreater(inv.groups[0].row_count, 20)
        # Anandamide must be in the entries.
        entry_names = {e.split(" (")[0] for e in inv.groups[0].entries}
        self.assertIn("anandamide", entry_names)


class RenderMarkdownTests(unittest.TestCase):
    def test_markdown_has_headers_for_each_group(self):
        inv = build_inventory("all")
        md = render_markdown(inv)
        self.assertIn("## Cannavec Science — registry inventory", md)
        # Every group title appears.
        for label in (
            "Major cannabinoids", "Minor cannabinoids", "Terpenes",
            "Drug interactions", "Adverse events",
            "Trial-supported populations", "Contraindications",
            "Pharmacogenomics", "Endocannabinoidome",
        ):
            self.assertIn(label, md)


class RenderJsonTests(unittest.TestCase):
    def test_json_round_trip(self):
        inv = build_inventory("minor_cannabinoids")
        s = render_json(inv)
        payload = json.loads(s)
        self.assertIn("groups", payload)
        self.assertEqual(len(payload["groups"]), 1)
        self.assertEqual(payload["groups"][0]["name"], "minor_cannabinoids")


class CLIRegistriesTests(unittest.TestCase):
    def _run(self, *args) -> tuple[int, str]:
        from cannavec_science.__main__ import _cmd_registries
        ns = argparse.Namespace(
            registry=args[0] if len(args) > 0 else "all",
            format=args[1] if len(args) > 1 else "markdown",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = _cmd_registries(ns)
        return rc, buf.getvalue()

    def test_default_emits_inventory(self):
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("registry inventory", out)
        self.assertIn("Major cannabinoids", out)

    def test_json_format(self):
        rc, out = self._run("all", "json")
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertIn("groups", payload)

    def test_unknown_registry_exits_2(self):
        rc, _ = self._run("nonexistent_xyz")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
