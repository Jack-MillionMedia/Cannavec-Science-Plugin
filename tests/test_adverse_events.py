"""Tests for cannavec.adverse_events."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.adverse_events import (   # noqa: E402
    AdverseEventOnset,
    AdverseEventReversibility,
    AdverseEventSeverity,
    all_adverse_events,
    detect_adverse_event_mention,
    find_adverse_events,
    format_for_clinician,
)


class TestRegistryShape(unittest.TestCase):
    def test_registry_is_substantial(self) -> None:
        self.assertGreater(len(all_adverse_events()), 10)

    def test_every_entry_has_at_least_one_citation(self) -> None:
        for x in all_adverse_events():
            self.assertGreater(len(x.citations), 0)
            for c in x.citations:
                self.assertTrue(c.pmid or c.doi or c.url,
                                f"{x.event}: citation missing identifier")

    def test_serious_events_have_actionable_guidance(self) -> None:
        for x in all_adverse_events():
            if x.severity == AdverseEventSeverity.SERIOUS:
                self.assertGreater(len(x.clinical_action), 20,
                                   f"{x.event}: clinical_action too brief")


class TestFindAdverseEvents(unittest.TestCase):
    def test_find_cbd_hepatic(self) -> None:
        hits = find_adverse_events(cannabinoid="CBD", organ_system="hepatic")
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].severity, AdverseEventSeverity.MODERATE)
        self.assertEqual(hits[0].reversibility, AdverseEventReversibility.REVERSIBLE)

    def test_min_severity_filter(self) -> None:
        hits = find_adverse_events(min_severity=AdverseEventSeverity.SERIOUS)
        self.assertTrue(all(x.severity == AdverseEventSeverity.SERIOUS for x in hits))

    def test_event_substring(self) -> None:
        hits = find_adverse_events(event="hyperemesis")
        self.assertGreaterEqual(len(hits), 1)

    def test_unknown_returns_empty(self) -> None:
        hits = find_adverse_events(cannabinoid="unobtainium")
        self.assertEqual(hits, ())


class TestDetectAdverseEventMention(unittest.TestCase):
    def test_detects_cbd_transaminase(self) -> None:
        text = "Patient on CBD with elevated transaminases."
        hits = detect_adverse_event_mention(text)
        self.assertTrue(any("transaminase" in x.event for x in hits))

    def test_detects_thc_tachycardia(self) -> None:
        text = "THC and tachycardia in CV-disease adults."
        hits = detect_adverse_event_mention(text)
        self.assertTrue(any(x.event == "tachycardia" for x in hits))

    def test_detects_cannabis_chs(self) -> None:
        text = "Cannabis hyperemesis syndrome management."
        hits = detect_adverse_event_mention(text)
        self.assertTrue(any("hyperemesis" in x.event for x in hits))

    def test_returns_empty_without_both_cues(self) -> None:
        self.assertEqual(detect_adverse_event_mention("Just CBD."), ())
        self.assertEqual(detect_adverse_event_mention("Just tachycardia."), ())


class TestOnsetEnum(unittest.TestCase):
    def test_onset_values(self) -> None:
        for o in (AdverseEventOnset.ACUTE, AdverseEventOnset.SUB_ACUTE,
                  AdverseEventOnset.CHRONIC, AdverseEventOnset.DELAYED):
            self.assertIsNotNone(o)


class TestFormatForClinician(unittest.TestCase):
    def test_empty_returns_honest_message(self) -> None:
        out = format_for_clinician([])
        self.assertIn("No high-confidence", out)

    def test_table_includes_organ_system(self) -> None:
        hits = find_adverse_events(cannabinoid="CBD", organ_system="hepatic")
        out = format_for_clinician(hits)
        self.assertIn("hepatic", out)
        self.assertIn("PMID", out)


class TestEvaliCoverage(unittest.TestCase):
    """Regression tests for the Oracle Auditor §T4 EVALI gap finding."""

    def test_evali_keyword_returns_blount_2020(self) -> None:
        rows = detect_adverse_event_mention(
            "Analyze cannabis vapor product safety including EVALI",
        )
        events = [r.event for r in rows]
        self.assertTrue(any("EVALI" in e for e in events),
                        f"expected EVALI row, got events={events}")
        pmids = {c.pmid for r in rows for c in r.citations}
        self.assertIn("31995731", pmids)  # Blount 2020 NEJM

    def test_vitamin_e_acetate_keyword_returns_evali(self) -> None:
        rows = detect_adverse_event_mention(
            "cannabis cartridge vitamin E acetate contamination",
        )
        self.assertTrue(any("EVALI" in r.event for r in rows))

    def test_heavy_metal_vape_keyword_returns_coil_row(self) -> None:
        rows = detect_adverse_event_mention(
            "cannabis vape heavy metal coil leaching",
        )
        events = [r.event for r in rows]
        self.assertTrue(any("heavy-metal" in e for e in events),
                        f"expected heavy-metal row, got events={events}")


if __name__ == "__main__":
    unittest.main()
