"""Tests for cannavec.contraindications."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.contraindications import (   # noqa: E402
    ContraindicationSeverity,
    all_contraindications,
    detect_contraindication_mention,
    find_contraindications,
    format_for_clinician,
)


class TestRegistryShape(unittest.TestCase):
    def test_registry_is_substantial(self) -> None:
        self.assertGreaterEqual(len(all_contraindications()), 8)

    def test_every_entry_has_citation(self) -> None:
        for x in all_contraindications():
            self.assertGreater(len(x.citations), 0)

    def test_absolute_entries_have_no_override(self) -> None:
        for x in all_contraindications():
            if x.severity == ContraindicationSeverity.ABSOLUTE:
                self.assertIn("no", x.override_context.lower())


class TestFindContraindications(unittest.TestCase):
    def test_filter_by_compound(self) -> None:
        hits = find_contraindications(compound="THC")
        self.assertGreater(len(hits), 0)

    def test_min_severity_absolute(self) -> None:
        hits = find_contraindications(min_severity=ContraindicationSeverity.ABSOLUTE)
        self.assertTrue(all(x.severity == ContraindicationSeverity.ABSOLUTE
                            for x in hits))


class TestDetectContraindicationMention(unittest.TestCase):
    def test_detects_thc_pregnancy(self) -> None:
        text = "Pregnant patient considering THC for nausea."
        hits = detect_contraindication_mention(text)
        self.assertTrue(any("pregnan" in x.population.lower() for x in hits))

    def test_detects_smoked_cannabis_asthma(self) -> None:
        text = "Patient with asthma asking about smoking cannabis."
        hits = detect_contraindication_mention(text)
        self.assertTrue(any("asthma" in x.population.lower() or
                            "respiratory" in x.population.lower()
                            for x in hits))

    def test_returns_empty_without_population(self) -> None:
        self.assertEqual(detect_contraindication_mention("Just CBD."), ())

    def test_returns_empty_without_compound(self) -> None:
        self.assertEqual(detect_contraindication_mention("Pregnancy."), ())


class TestFormatForClinician(unittest.TestCase):
    def test_empty_returns_honest_message(self) -> None:
        self.assertIn("No high-confidence", format_for_clinician([]))

    def test_table_shows_severity(self) -> None:
        hits = find_contraindications(compound="THC")
        out = format_for_clinician(hits)
        self.assertIn("Severity", out)


if __name__ == "__main__":
    unittest.main()
