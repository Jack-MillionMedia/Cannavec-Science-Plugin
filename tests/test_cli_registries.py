"""CLI ``registries`` integration tests (Plan R7).

The registries subcommand lists every curated registry with row counts
and freshness. These tests pin the CLI-level contract:

- JSON ``--format json`` returns 20 groups (the 20 curated registries
  shipped at v0.6).
- Markdown render mentions every registry name.
- A bogus ``--registry`` exits non-zero with a helpful error.
"""

from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr

from cannavec_science.__main__ import _cmd_registries


_EXPECTED_REGISTRIES = {
    "major_cannabinoids",
    "minor_cannabinoids",
    "terpenes",
    "interactions",
    "adverse_events",
    "populations",
    "contraindications",
    "pharmacogenomics",
    "ecbome",
    "analytical_chemistry",
    "cultivation_science",
    "pharmacokinetics",
    "use_disorder",
    "hyperemesis_syndrome",
    "ecbome_inhibitors",
    "biosynthesis",
    "pain_medicine",
    "psychiatry",
    "driving_impairment",
    "ptsd_anxiety_sleep",
}


class RegistriesJSONTests(unittest.TestCase):
    def test_all_returns_twenty_groups_in_json(self):
        args = argparse.Namespace(registry="all", format="json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = _cmd_registries(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        # Tolerate either ``groups`` or top-level dict keyed by registry.
        groups = payload.get("groups") or payload.get("registries") or payload
        if isinstance(groups, list):
            names = {g.get("name") or g.get("registry") for g in groups}
        else:
            names = set(groups.keys())
        # All 20 expected registries must be present (extras are fine
        # — the v0.7+ amendment cycle could add more).
        self.assertTrue(
            _EXPECTED_REGISTRIES.issubset(names),
            f"missing registries: {_EXPECTED_REGISTRIES - names}",
        )
        self.assertEqual(
            len(names & _EXPECTED_REGISTRIES), 20,
            "all 20 curated v0.6 registries must surface",
        )

    def test_specific_registry_returns_only_that_one(self):
        args = argparse.Namespace(
            registry="major_cannabinoids", format="json",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = _cmd_registries(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        body = json.dumps(payload).lower()
        self.assertIn("major_cannabinoids", body)


class RegistriesMarkdownTests(unittest.TestCase):
    def test_markdown_reports_the_full_registry_count(self):
        # The markdown renderer uses prose display names (e.g. "Cannabinoid
        # hyperemesis syndrome") rather than snake_case keys, so the
        # comprehensive name-check belongs on the JSON output. Here we
        # pin the headline row that proves all 20 registries rendered.
        args = argparse.Namespace(registry="all", format="markdown")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = _cmd_registries(args)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        # The header is rendered with markdown bold around the count.
        self.assertIn("**20** curated registries", out)
        # And a representative subset of display names should appear.
        for fragment in (
            "Major cannabinoids",
            "Minor cannabinoids",
            "Terpenes",
            "Pharmacogenomics",
            "Pain medicine",
            "PTSD",
        ):
            self.assertIn(fragment, out)


class RegistriesUnknownTests(unittest.TestCase):
    def test_unknown_registry_nonzero_with_actionable_error(self):
        args = argparse.Namespace(
            registry="nonexistent_xyz", format="markdown",
        )
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            rc = _cmd_registries(args)
        self.assertNotEqual(rc, 0)
        err = err_buf.getvalue()
        # The error must list the accepted names so the user can fix it.
        self.assertIn("nonexistent_xyz", err)
        self.assertIn("major_cannabinoids", err)


if __name__ == "__main__":
    unittest.main()
