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


class TestLgsEnrollmentGroundTruth(unittest.TestCase):
    """Defect #7: the LGS row's enrolment must match the cited trial.

    PMID 29768152 (Devinsky 2018, NEJM, GWPCARE3) enrolled a total of 225
    patients across the 10 mg/kg, 20 mg/kg, and placebo arms ("A total of 225
    patients were enrolled"). The population row previously claimed n=171,
    which traces to nothing — not the ITT (225), not the 76+73=149 active arms,
    not a GWPCARE4 figure. The major_cannabinoids monograph for the same PMID
    already records 225, so the two surfaces disagreed.
    """

    def _lgs_citation(self):
        row = find_populations(label_substring="Lennox-Gastaut")[0]
        for c in row.citations:
            if c.pmid == "29768152":
                return c
        self.fail("LGS row missing its PMID 29768152 citation")

    def test_lgs_enrollment_is_225(self) -> None:
        self.assertEqual(
            self._lgs_citation().n, 225,
            "LGS row must record the ground-truthed ITT enrolment of 225",
        )

    def test_lgs_enrollment_matches_major_cannabinoid_monograph(self) -> None:
        # Cross-surface consistency: the same PMID must carry the same n in
        # both the population registry and the cannabinoid monograph.
        from cannavec_science.major_cannabinoids import all_major_cannabinoids

        monograph_n = None
        for entry in all_major_cannabinoids():
            for crow in getattr(entry, "clinical_evidence", ()) or ():
                if any(getattr(cit, "pmid", None) == "29768152"
                       for cit in getattr(crow, "citations", ()) or ()):
                    monograph_n = crow.n
        self.assertEqual(
            self._lgs_citation().n, monograph_n,
            "the LGS enrolment must agree across the population and "
            "major-cannabinoid surfaces for PMID 29768152",
        )


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
