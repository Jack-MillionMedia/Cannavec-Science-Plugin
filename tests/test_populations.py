"""Tests for cannavec.populations."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.evidence import EvidenceLevel   # noqa: E402
from cannavec_science.populations import (   # noqa: E402
    all_populations,
    detect_population_mention,
    find_populations,
    format_for_clinician,
)


class TestRegistryShape(unittest.TestCase):
    def test_registry_has_minimum_entries(self) -> None:
        self.assertGreaterEqual(len(all_populations()), 8)

    def test_every_entry_has_citation(self) -> None:
        for x in all_populations():
            self.assertGreater(len(x.citations), 0)

    def test_every_entry_has_required_cautions(self) -> None:
        for x in all_populations():
            self.assertGreater(
                len(x.required_cautions), 0,
                f"{x.label}: must declare at least one required caution",
            )

    def test_avoidance_populations_have_no_dose(self) -> None:
        # Pregnant / lactating + adolescents are avoidance / caution
        # populations with no trial-supported personal-dose range.
        for x in all_populations():
            if "avoidance" in x.label or "caution" in x.label.lower():
                self.assertIn("not applicable", x.dose_range_population.lower())


class TestFindPopulations(unittest.TestCase):
    def test_label_substring(self) -> None:
        hits = find_populations(label_substring="Dravet")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].highest_grade_anchor, EvidenceLevel.A)

    def test_cannabinoid_substring(self) -> None:
        hits = find_populations(cannabinoid_substring="nabiximols")
        self.assertGreaterEqual(len(hits), 1)

    def test_min_grade_filter(self) -> None:
        hits = find_populations(min_grade=EvidenceLevel.A)
        self.assertTrue(all(x.highest_grade_anchor == EvidenceLevel.A
                            for x in hits))


class TestDetectPopulationMention(unittest.TestCase):
    def test_detects_dravet(self) -> None:
        text = "Paediatric Dravet syndrome and CBD."
        hits = detect_population_mention(text)
        self.assertTrue(any("Dravet" in x.label for x in hits))

    def test_detects_cinv(self) -> None:
        text = "CINV in adults receiving chemotherapy."
        hits = detect_population_mention(text)
        self.assertTrue(any("CINV" in x.label for x in hits))

    def test_detects_ms_spasticity(self) -> None:
        text = "MS spasticity not responsive to baclofen."
        hits = detect_population_mention(text)
        self.assertTrue(any("MS spasticity" in x.label for x in hits))

    def test_returns_empty_without_anchor(self) -> None:
        self.assertEqual(detect_population_mention("Just a prompt."), ())


class TestFormatForClinician(unittest.TestCase):
    def test_empty_returns_honest_message(self) -> None:
        out = format_for_clinician([])
        self.assertIn("No trial-supported", out)

    def test_renders_dose_range_and_grade(self) -> None:
        hits = find_populations(label_substring="Dravet")
        out = format_for_clinician(hits)
        self.assertIn("Trial-supported dose range", out)
        self.assertIn("Highest evidence grade", out)
        self.assertIn("Level A", out)
        self.assertIn("Required cautions", out)


class TestIndicationKeywordFallback(unittest.TestCase):
    """Regression tests for the Oracle Auditor §T12 paraphrase finding.

    A user asking the indication ("seizure", "epilepsy", "pain", …)
    without naming a specific syndrome must still surface the
    registered Level-A / Level-B populations.
    """

    def test_seizures_returns_three_paediatric_epilepsy_rows(self) -> None:
        rows = detect_population_mention("What does CBD do for seizures?")
        labels = {r.label for r in rows}
        self.assertIn("paediatric Dravet syndrome", labels)
        self.assertIn("paediatric Lennox-Gastaut syndrome", labels)
        self.assertIn("paediatric tuberous sclerosis complex (TSC)", labels)

    def test_epilepsy_paraphrase_matches_seizure_keyword(self) -> None:
        rows = detect_population_mention(
            "How does cannabidiol affect epilepsy?",
        )
        self.assertGreaterEqual(len(rows), 3)

    def test_spasticity_alone_returns_ms_row(self) -> None:
        rows = detect_population_mention("Cannabis for spasticity")
        self.assertTrue(any(r.label == "adult MS spasticity" for r in rows))

    def test_neuropathy_paraphrase_matches_pain_row(self) -> None:
        rows = detect_population_mention(
            "Is cannabis effective for neuropathy?",
        )
        self.assertTrue(
            any(r.label == "adult chronic neuropathic pain" for r in rows)
        )

    def test_nausea_returns_cinv_row(self) -> None:
        rows = detect_population_mention("Cannabis for chemotherapy nausea")
        self.assertTrue(any("CINV" in r.label for r in rows))

    def test_appetite_returns_cachexia_row(self) -> None:
        rows = detect_population_mention(
            "Cannabis for cancer appetite loss",
        )
        self.assertTrue(any("cachexia" in r.label for r in rows))

    def test_unrelated_text_still_returns_empty(self) -> None:
        self.assertEqual(detect_population_mention("Just a prompt."), ())


if __name__ == "__main__":
    unittest.main()
