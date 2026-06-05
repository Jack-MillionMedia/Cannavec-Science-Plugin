"""Integration tests for v0.2 answer.py extensions (spec 002 US1 + US5).

Covers:
- Preprint badge rendering (`[preprint, not peer-reviewed]`) when a
  Citation carries `preprint_provenance`.
- Freshness staleness suffix (`[freshness: stale (verified YYYY-MM-DD)]`)
  when a Citation carries `freshness_stale_since`.
- Scaffolder threading via the CLI flags.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from cannavec_science.answer import Answer, Citation, compose_answer
from cannavec_science.evidence import EvidenceLevel


class CitationFieldsTests(unittest.TestCase):
    def test_citation_accepts_preprint_provenance(self):
        c = Citation(
            label="bioRxiv test", doi="10.1101/2026.04.12.589123",
            preprint_provenance="live_biorxiv",
        )
        self.assertEqual(c.preprint_provenance, "live_biorxiv")

    def test_citation_accepts_freshness_stale_since(self):
        c = Citation(
            label="Old paper", pmid="12345",
            freshness_stale_since="2024-01-01",
        )
        self.assertEqual(c.freshness_stale_since, "2024-01-01")

    def test_citation_defaults_none(self):
        c = Citation(label="Standard", pmid="28538134")
        self.assertIsNone(c.preprint_provenance)
        self.assertIsNone(c.freshness_stale_since)


class PreprintBadgeRenderTests(unittest.TestCase):
    def test_preprint_badge_in_markdown(self):
        a = Answer(prompt="test")
        a.citations.append(Citation(
            label="A preprint",
            doi="10.1101/2026.04.12.589123",
            grade=EvidenceLevel.D,
            preprint_provenance="live_biorxiv",
        ))
        md = a.to_markdown()
        self.assertIn("[preprint, not peer-reviewed]", md)

    def test_no_badge_when_no_provenance(self):
        a = Answer(prompt="test")
        a.citations.append(Citation(
            label="Regular paper",
            pmid="28538134",
            grade=EvidenceLevel.A,
        ))
        md = a.to_markdown()
        self.assertNotIn("[preprint", md)


class FreshnessSuffixRenderTests(unittest.TestCase):
    def test_stale_suffix_in_markdown(self):
        a = Answer(prompt="test")
        a.citations.append(Citation(
            label="Old paper",
            pmid="12345",
            year=2010,
            grade=EvidenceLevel.B,
            freshness_stale_since="2024-01-01",
        ))
        md = a.to_markdown()
        self.assertIn("[freshness: stale (verified 2024-01-01)]", md)

    def test_no_suffix_when_no_freshness_field(self):
        a = Answer(prompt="test")
        a.citations.append(Citation(
            label="Recent paper",
            pmid="28538134",
            grade=EvidenceLevel.A,
        ))
        md = a.to_markdown()
        self.assertNotIn("[freshness:", md)


class CLIScaffolderIntegrationTests(unittest.TestCase):
    """End-to-end test of the answer CLI with v0.2 scaffolder flags.

    Validates that the assembled output includes the scaffolder blocks.
    """

    def _run(self, *args) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, "-m", "cannavec_science", "answer", *args],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        return result.returncode, result.stdout + result.stderr

    def test_pico_flag_emits_pico_block(self):
        rc, out = self._run(
            "CBD evidence in Dravet syndrome",
            "--pico",
        )
        self.assertEqual(rc, 0)
        self.assertIn("PICO frame", out)

    def test_power_calc_flag_emits_power_block(self):
        rc, out = self._run(
            "CBD evidence in Dravet syndrome",
            "--power-calc",
        )
        self.assertEqual(rc, 0)
        self.assertIn("Power calculation", out)

    def test_grade_profile_flag_emits_table(self):
        rc, out = self._run(
            "CBD evidence in Dravet syndrome",
            "--grade-profile",
        )
        self.assertEqual(rc, 0)
        self.assertIn("GRADE evidence-profile table", out)

    def test_grade_profile_csv_format(self):
        rc, out = self._run(
            "CBD evidence in Dravet syndrome",
            "--grade-profile", "--grade-profile-format", "csv",
        )
        self.assertEqual(rc, 0)
        # CSV output has the column header line.
        self.assertIn("outcome", out)
        self.assertIn("n_studies", out)

    def test_protocol_skeleton_flag_emits_watermark(self):
        rc, out = self._run(
            "CBD evidence in Dravet syndrome",
            "--protocol-skeleton",
        )
        self.assertEqual(rc, 0)
        self.assertIn("Auto-generated skeleton", out)

    def test_regulatory_feasibility_flag_emits_watermark(self):
        rc, out = self._run(
            "Can I study Δ⁹-THC in rats?",
            "--regulatory-feasibility", "us",
        )
        self.assertEqual(rc, 0)
        self.assertIn("not legal advice", out)

    def test_all_scaffolders_combine(self):
        rc, out = self._run(
            "CBD evidence in Dravet syndrome",
            "--pico", "--power-calc",
            "--grade-profile", "--protocol-skeleton",
        )
        self.assertEqual(rc, 0)
        for block in (
            "PICO frame",
            "Power calculation",
            "GRADE evidence-profile table",
            "Auto-generated skeleton",
        ):
            self.assertIn(block, out)

    def test_json_includes_scaffolders(self):
        rc, out = self._run(
            "CBD evidence in Dravet syndrome",
            "--json", "--pico", "--power-calc",
        )
        self.assertEqual(rc, 0)
        # Strip warning lines, parse JSON.
        payload = json.loads(out)
        self.assertIn("scaffolders", payload)
        self.assertIn("pico", payload["scaffolders"])
        self.assertIn("power_calc", payload["scaffolders"])


class CLIFreshnessIntegrationTests(unittest.TestCase):
    def _run(self, *args) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, "-m", "cannavec_science", "freshness", *args],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        return result.returncode, result.stdout + result.stderr

    def test_freshness_all_registries(self):
        rc, out = self._run()
        # Some registries may have no_watch_pmids rows; that's OK.
        self.assertIn("Freshness probe", out)
        # All 8 registry names should appear.
        for name in (
            "major_cannabinoids", "minor_cannabinoids", "terpenes",
            "interactions", "adverse_events", "populations",
            "contraindications", "pharmacogenomics",
        ):
            self.assertIn(name, out)

    def test_freshness_single_registry(self):
        rc, out = self._run("--registry", "interactions")
        self.assertEqual(rc, 0)
        self.assertIn("interactions", out)

    def test_freshness_unknown_registry_errors(self):
        rc, out = self._run("--registry", "nonexistent_registry_XYZ")
        self.assertEqual(rc, 2)

    def test_freshness_json_output(self):
        rc, out = self._run("--registry", "interactions", "--json")
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertIn("registries", payload)


if __name__ == "__main__":
    unittest.main()
