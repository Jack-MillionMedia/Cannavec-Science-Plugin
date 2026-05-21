"""Tests for cannavec.pharmacogenomics — CYP pharmacogenomics registry."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.pharmacogenomics import (   # noqa: E402
    PGxClinicalImpact,
    PGxActionability,
    PGxRecord,
    all_pgx_records,
    detect_pgx_mention,
    find_by_cannabinoid,
    find_by_enzyme,
    find_high_impact,
    format_for_clinician,
)


class TestRegistryShape(unittest.TestCase):
    def test_registry_is_nonempty(self) -> None:
        self.assertGreater(len(all_pgx_records()), 4)

    def test_every_entry_has_at_least_one_citation(self) -> None:
        for r in all_pgx_records():
            self.assertTrue(
                r.citations,
                f"PGx record '{r.enzyme} / {r.allele_or_variant}' has no citations",
            )
            for c in r.citations:
                has_id = bool(c.pmid or c.doi or c.url)
                self.assertTrue(
                    has_id,
                    f"Citation '{c.label}' has no resolvable identifier",
                )

    def test_every_entry_has_nonempty_magnitude(self) -> None:
        for r in all_pgx_records():
            self.assertTrue(
                r.magnitude,
                f"PGx record '{r.enzyme}' has empty magnitude",
            )

    def test_every_entry_has_clinical_notes(self) -> None:
        for r in all_pgx_records():
            self.assertTrue(
                r.clinical_notes,
                f"PGx record '{r.enzyme}' has empty clinical_notes",
            )


class TestFindByEnzyme(unittest.TestCase):
    def test_cyp2c9_returns_results(self) -> None:
        results = find_by_enzyme("CYP2C9")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("cyp2c9", r.enzyme.lower())

    def test_cyp2c19_returns_results(self) -> None:
        results = find_by_enzyme("CYP2C19")
        self.assertGreater(len(results), 0)

    def test_unknown_enzyme_returns_empty(self) -> None:
        results = find_by_enzyme("CYP99Z99")
        self.assertEqual(results, [])


class TestFindByCannabioid(unittest.TestCase):
    def test_thc_returns_results(self) -> None:
        results = find_by_cannabinoid("THC")
        self.assertGreater(len(results), 0)

    def test_cbd_returns_results(self) -> None:
        results = find_by_cannabinoid("CBD")
        self.assertGreater(len(results), 0)

    def test_unknown_returns_empty(self) -> None:
        results = find_by_cannabinoid("ZZZNONEXISTENT")
        self.assertEqual(results, [])


class TestFindHighImpact(unittest.TestCase):
    def test_high_impact_returns_nonempty(self) -> None:
        results = find_high_impact()
        self.assertGreater(len(results), 0)

    def test_all_are_high_impact(self) -> None:
        for r in find_high_impact():
            self.assertEqual(r.clinical_impact, PGxClinicalImpact.HIGH)

    def test_cyp2c9_polymorphism_is_high_impact(self) -> None:
        high = find_high_impact()
        names = [r.allele_or_variant for r in high]
        self.assertTrue(
            any("2c9" in n.lower() for n in names),
            "CYP2C9*3 must be classified as HIGH clinical impact",
        )


class TestCYP2C9PoorMetaboliser(unittest.TestCase):
    """The CYP2C9*3 / THC interaction is the most documented."""

    def test_cyp2c9_star3_thc_entry_exists(self) -> None:
        results = find_by_enzyme("CYP2C9")
        thc_entries = [
            r for r in results
            if "poor metaboliser" in r.allele_or_variant.lower()
            and "thc" in r.cannabinoid.lower()
        ]
        self.assertGreater(
            len(thc_entries), 0,
            "CYP2C9*3 poor metaboliser / THC entry must exist",
        )

    def test_sachse_seeboth_citation_present(self) -> None:
        results = find_by_enzyme("CYP2C9")
        all_dois = [c.doi for r in results for c in r.citations if c.doi]
        self.assertTrue(
            any("clpt.2008" in d.lower() for d in all_dois),
            "Sachse-Seeboth 2009 citation (doi containing 'clpt.2008') must be present",
        )


class TestCBDCYP2C19Inhibition(unittest.TestCase):
    """CBD inhibits CYP2C19 — the clobazam interaction is well-documented."""

    def test_cbd_cyp2c19_inhibition_entry_exists(self) -> None:
        results = find_by_enzyme("CYP2C19")
        cbd_inhibitor = [
            r for r in results
            if "cbd" in r.cannabinoid.lower()
            and "inhibit" in r.direction.lower()
        ]
        self.assertGreater(
            len(cbd_inhibitor), 0,
            "CBD CYP2C19 inhibitor entry must exist",
        )

    def test_clobazam_mentioned_in_clinical_notes(self) -> None:
        results = find_by_enzyme("CYP2C19")
        cbd_inhibitor = [
            r for r in results
            if "cbd" in r.cannabinoid.lower()
            and "inhibit" in r.direction.lower()
        ]
        self.assertTrue(cbd_inhibitor)
        combined_notes = " ".join(r.clinical_notes for r in cbd_inhibitor)
        self.assertIn(
            "clobazam",
            combined_notes.lower(),
            "CBD/CYP2C19 entry must mention clobazam interaction",
        )


class TestDetectPGxMention(unittest.TestCase):
    def test_cyp2c9_detected(self) -> None:
        result = detect_pgx_mention(
            "The patient's CYP2C9*3 genotype may affect THC clearance."
        )
        self.assertIn("cyp2c9", result)

    def test_polymorphism_detected(self) -> None:
        result = detect_pgx_mention(
            "Poor metaboliser status altered the patient's response."
        )
        self.assertIn("polymorphism", result)

    def test_unrelated_text_returns_empty(self) -> None:
        result = detect_pgx_mention(
            "The dispensary was open on weekends and accepted cash only."
        )
        self.assertEqual(result, [])


class TestFormatForClinician(unittest.TestCase):
    def test_returns_nonempty_markdown(self) -> None:
        out = format_for_clinician(all_pgx_records())
        self.assertTrue(out)
        self.assertIn("###", out)

    def test_empty_input_returns_helpful_message(self) -> None:
        out = format_for_clinician([])
        self.assertIn("No pharmacogenomic", out)

    def test_magnitude_appears_in_output(self) -> None:
        out = format_for_clinician(all_pgx_records())
        self.assertIn("Magnitude", out)


if __name__ == "__main__":
    unittest.main()
