"""Tests for cannavec.interactions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.interactions import (   # noqa: E402
    ClinicalAction,
    InteractionDirection,
    InteractionSeverity,
    all_interactions,
    detect_interaction_mention,
    find_interactions,
    format_for_clinician,
)


class TestRegistryShape(unittest.TestCase):
    def test_registry_is_nonempty(self) -> None:
        self.assertGreater(len(all_interactions()), 5)

    def test_every_entry_has_at_least_one_citation(self) -> None:
        for x in all_interactions():
            self.assertGreater(len(x.citations), 0)
            # Each citation must have at least one resolvable id.
            for c in x.citations:
                self.assertTrue(c.pmid or c.doi or c.url,
                                f"{x.partner_drug}: citation missing identifier")

    def test_high_severity_entries_have_clinical_action(self) -> None:
        for x in all_interactions():
            if x.severity == InteractionSeverity.HIGH:
                self.assertNotEqual(
                    x.clinical_action, ClinicalAction.NO_ACTION_REQUIRED,
                    f"high-severity entry has no-action: {x.partner_drug}",
                )


class TestFindInteractions(unittest.TestCase):
    def test_find_cbd_clobazam(self) -> None:
        hits = find_interactions(cannabinoid="CBD", partner_drug="clobazam")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].cyp_isoform, "CYP2C19")
        self.assertEqual(hits[0].severity, InteractionSeverity.HIGH)

    def test_min_severity_filter(self) -> None:
        hits = find_interactions(min_severity=InteractionSeverity.HIGH)
        self.assertTrue(all(x.severity == InteractionSeverity.HIGH for x in hits))

    def test_unknown_partner_returns_empty(self) -> None:
        hits = find_interactions(partner_drug="this drug does not exist")
        self.assertEqual(hits, ())


class TestDetectInteractionMention(unittest.TestCase):
    def test_detects_cbd_warfarin_in_prose(self) -> None:
        text = "I'm taking warfarin and have started CBD oil."
        hits = detect_interaction_mention(text)
        self.assertTrue(any("warfarin" in x.partner_drug for x in hits))

    def test_detects_thc_alcohol(self) -> None:
        text = "Mixing THC with alcohol — what does the evidence say?"
        hits = detect_interaction_mention(text)
        self.assertTrue(any("alcohol" in x.partner_drug for x in hits))

    def test_returns_empty_without_both_cues(self) -> None:
        self.assertEqual(detect_interaction_mention("I take CBD."), ())
        self.assertEqual(detect_interaction_mention("I take warfarin."), ())

    def test_clobazam_alias(self) -> None:
        text = "Paediatric Dravet patient on clobazam — adding CBD?"
        hits = detect_interaction_mention(text)
        self.assertTrue(any(x.partner_drug == "clobazam" for x in hits))


class TestFormatForClinician(unittest.TestCase):
    def test_empty_returns_honest_message(self) -> None:
        out = format_for_clinician([])
        self.assertIn("No high-confidence", out)

    def test_table_includes_pmid_when_present(self) -> None:
        hits = find_interactions(cannabinoid="CBD", partner_drug="clobazam")
        out = format_for_clinician(hits)
        self.assertIn("PMID 26114620", out)
        self.assertIn("CYP2C19", out)


class TestDirectionEnum(unittest.TestCase):
    def test_known_directions_exist(self) -> None:
        for d in (
            InteractionDirection.INHIBITS,
            InteractionDirection.INDUCES,
            InteractionDirection.IS_SUBSTRATE_OF,
            InteractionDirection.PHARMACODYNAMIC,
        ):
            self.assertIsNotNone(d)


if __name__ == "__main__":
    unittest.main()
