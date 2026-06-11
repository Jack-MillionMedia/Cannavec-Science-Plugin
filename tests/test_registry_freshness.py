"""Every curated registry must report a `last_verified` date — a research-
grounding tool that cannot say when its interaction / contraindication facts were
last checked is leaking provenance exactly where credibility matters most.

The eight oldest registries predate the per-row `last_verified` field; their
inventory freshness falls back to the registry's curation date (recovered from
git — the date the rows were authored and their citations checked). The date is
conservative (facts verified no later than then), never fabricated as "today".

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import re
import unittest

from cannavec_science.registries import build_inventory


class EveryRegistryReportsFreshness(unittest.TestCase):
    def test_no_registry_has_blank_last_verified(self):
        inv = build_inventory("all")
        blank = [g.name for g in inv.groups if not g.last_verified]
        self.assertEqual(
            blank, [],
            f"registries with no last_verified (provenance gap): {blank}",
        )

    def test_freshness_is_an_iso_date(self):
        inv = build_inventory("all")
        for g in inv.groups:
            with self.subTest(registry=g.name):
                self.assertRegex(
                    g.last_verified, r"^\d{4}-\d{2}-\d{2}$",
                    f"{g.name} last_verified is not an ISO date: "
                    f"{g.last_verified!r}",
                )


if __name__ == "__main__":
    unittest.main()
