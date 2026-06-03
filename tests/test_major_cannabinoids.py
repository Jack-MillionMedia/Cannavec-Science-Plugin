"""Tests for cannavec.major_cannabinoids."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.major_cannabinoids import (   # noqa: E402
    all_major_cannabinoids,
    detect_major_cannabinoid_mention,
    find_major_cannabinoid,
)
from cannavec_science.minor_cannabinoids import (   # noqa: E402
    MinorCannabinoidEvidenceClass,
)


class TestRegistryShape(unittest.TestCase):
    def test_registry_has_thc_and_cbd(self) -> None:
        names = {c.name for c in all_major_cannabinoids()}
        self.assertIn("THC", names)
        self.assertIn("CBD", names)

    def test_every_entry_has_at_least_one_citation(self) -> None:
        for c in all_major_cannabinoids():
            self.assertGreater(
                len(c.citations), 0,
                f"{c.name}: registry entry must have cross-cutting citations",
            )

    def test_every_entry_has_receptor_activity(self) -> None:
        for c in all_major_cannabinoids():
            self.assertGreater(
                len(c.receptor_activity), 0,
                f"{c.name}: must declare at least one receptor activity",
            )

    def test_every_receptor_row_has_uniprot(self) -> None:
        for c in all_major_cannabinoids():
            for r in c.receptor_activity:
                self.assertTrue(
                    r.uniprot,
                    f"{c.name} / {r.target}: missing UniProt ID",
                )

    def test_clinical_evidence_grade_anchored(self) -> None:
        # THC should be Level B (modest SR/MA evidence); CBD should
        # be Level A (Dravet / LGS pivotal RCTs).
        names = {c.name: c for c in all_major_cannabinoids()}
        self.assertEqual(
            names["THC"].clinical_grade,
            MinorCannabinoidEvidenceClass.B,
        )
        self.assertEqual(
            names["CBD"].clinical_grade,
            MinorCannabinoidEvidenceClass.A,
        )


class TestGradeConsistencyAndSources(unittest.TestCase):
    """Issue-1 (grade consistency) + Issue-3b (primary source) regressions."""

    def setUp(self) -> None:
        self.cbd = find_major_cannabinoid("CBD")

    def test_single_rct_indication_rows_capped_at_b(self) -> None:
        # Each single-pivotal-RCT indication caps at Level B (§VII single-study
        # rule), matching the deterministic headline grade. The aggregate
        # clinical_grade stays A (the replicated Dravet + LGS + TSC body).
        for row in self.cbd.clinical_evidence:
            self.assertEqual(
                row.grade, MinorCannabinoidEvidenceClass.B,
                f"{row.indication}: single-RCT row must grade to B, not A",
            )
        self.assertEqual(self.cbd.clinical_grade, MinorCannabinoidEvidenceClass.A)

    def test_rodent_seizure_row_cites_primary_study_not_binding_review(self) -> None:
        seizure_rows = [
            r for r in self.cbd.preclinical_evidence
            if "seizure" in r.indication_or_model.lower()
        ]
        self.assertTrue(seizure_rows)
        pmids = {c.pmid for r in seizure_rows for c in r.citations}
        self.assertIn("19906779", pmids)      # Jones 2010 — primary CBD-seizure study
        self.assertNotIn("17828291", pmids)   # Pertwee — a binding review, not seizure data

    def test_pertwee_review_still_anchors_receptor_binding(self) -> None:
        # The binding review stays where it IS the right source: CB1 / TRPV1.
        pmids = {c.pmid for r in self.cbd.receptor_activity for c in r.citations}
        self.assertIn("17828291", pmids)

    def test_dravet_brief_is_internally_grade_consistent(self) -> None:
        from cannavec_science.answer import compose_answer
        md = compose_answer(
            "What is the evidence for cannabidiol in Dravet syndrome?"
        ).to_markdown()
        # The Dravet indication row must agree with the headline (Level B), and
        # the only Level A is the explicitly-labelled aggregate ("overall grade").
        idx = md.find("convulsive seizures in Dravet syndrome")
        self.assertGreater(idx, -1)
        window = md[idx:idx + 500]
        self.assertIn("**Grade:** Level B", window)
        self.assertNotIn("**Grade:** Level A", window)
        self.assertIn("overall grade:", md)


class TestFindMajorCannabinoid(unittest.TestCase):
    def test_exact_canonical_name(self) -> None:
        c = find_major_cannabinoid("THC")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "THC")

    def test_long_name(self) -> None:
        c = find_major_cannabinoid("cannabidiol")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "CBD")

    def test_alias_dronabinol_resolves_to_thc(self) -> None:
        c = find_major_cannabinoid("dronabinol")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "THC")

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(find_major_cannabinoid("nonexistent"))


class TestDetectMajorCannabinoidMention(unittest.TestCase):
    def test_thc_mention_returns_thc(self) -> None:
        hits = detect_major_cannabinoid_mention("THC binds CB1.")
        names = {c.name for c in hits}
        self.assertIn("THC", names)

    def test_cbd_mention_returns_cbd(self) -> None:
        hits = detect_major_cannabinoid_mention("Epidiolex is CBD.")
        names = {c.name for c in hits}
        self.assertIn("CBD", names)

    def test_both_returned_when_both_named(self) -> None:
        hits = detect_major_cannabinoid_mention(
            "Compare THC and CBD pharmacology.",
        )
        names = {c.name for c in hits}
        self.assertEqual(names, {"THC", "CBD"})

    def test_unrelated_text_returns_empty(self) -> None:
        self.assertEqual(
            detect_major_cannabinoid_mention("hempcrete and pesticides"),
            (),
        )


if __name__ == "__main__":
    unittest.main()
