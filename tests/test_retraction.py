"""Tests for cannavec.retraction."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.retraction import (   # noqa: E402
    RetractionStatus,
    RetractionRecord,
    add_records,
    all_records,
    format_hits,
    is_retracted,
    load_registry_from_yaml,
    reset_to_seed,
    scan_text_for_retracted_pmids,
)


class TestSeedRegistry(unittest.TestCase):
    def setUp(self) -> None:
        reset_to_seed()

    def test_seed_has_at_least_one_record(self) -> None:
        self.assertGreaterEqual(len(all_records()), 1)

    def test_seed_records_are_labelled_synthetic(self) -> None:
        for r in all_records():
            self.assertIn("example", r.title.lower(),
                          "Seed records must be explicitly labelled as examples.")


class TestIsRetracted(unittest.TestCase):
    def setUp(self) -> None:
        reset_to_seed()

    def test_known_pmid_found(self) -> None:
        rec = is_retracted(pmid="99000001")
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertEqual(rec.status, RetractionStatus.RETRACTED)

    def test_known_doi_found(self) -> None:
        rec = is_retracted(doi="10.99999/example-eoc.2021")
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertEqual(rec.status, RetractionStatus.EXPRESSION_OF_CONCERN)

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(is_retracted(pmid="12345678"))
        self.assertIsNone(is_retracted(doi="10.0/not-real"))
        self.assertIsNone(is_retracted())


class TestScanTextForRetractedPmids(unittest.TestCase):
    def setUp(self) -> None:
        reset_to_seed()

    def test_finds_pmid_in_prose(self) -> None:
        text = "Per PMID 99000001 the effect is reported, but see note."
        hits = scan_text_for_retracted_pmids(text)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_identifier, "99000001")

    def test_finds_doi_in_prose(self) -> None:
        text = "The original study (doi:10.99999/example-eoc.2021) was flagged."
        hits = scan_text_for_retracted_pmids(text)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_kind, "doi")

    def test_clean_text_returns_empty(self) -> None:
        text = "No identifiers here."
        self.assertEqual(scan_text_for_retracted_pmids(text), ())

    def test_multiple_pmid_format_variants(self) -> None:
        text = "PMID:99000001 and 99000001 both appear."
        hits = scan_text_for_retracted_pmids(text)
        self.assertGreaterEqual(len(hits), 1)


class TestYamlLoader(unittest.TestCase):
    def test_loads_yaml_records(self) -> None:
        yaml_text = """
records:
  - pmid: "11111111"
    doi: null
    title: "Custom retraction"
    journal: "Test Journal"
    year: 2024
    status: "retracted"
    notice_url: "https://example.com/notice"
    reason_summary: "Fabricated data."
    flagged_at: "2026-05-16"
    notes: ""
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(yaml_text)
            path = f.name
        try:
            n = load_registry_from_yaml(path)
            self.assertEqual(n, 1)
            rec = is_retracted(pmid="11111111")
            self.assertIsNotNone(rec)
            assert rec is not None
            self.assertEqual(rec.journal, "Test Journal")
            self.assertEqual(rec.year, 2024)
        finally:
            Path(path).unlink(missing_ok=True)
            reset_to_seed()

    def test_unknown_status_raises(self) -> None:
        yaml_text = """
records:
  - pmid: "22222222"
    doi: null
    title: "Bad status"
    journal: "Test"
    year: 2024
    status: "made-up-status"
    notice_url: null
    reason_summary: ""
    flagged_at: "2026-05-16"
    notes: ""
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(yaml_text)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_registry_from_yaml(path)
        finally:
            Path(path).unlink(missing_ok=True)
            reset_to_seed()


class TestAddRecords(unittest.TestCase):
    def setUp(self) -> None:
        reset_to_seed()

    def tearDown(self) -> None:
        reset_to_seed()

    def test_add_records_appears_in_registry(self) -> None:
        before = len(all_records())
        add_records([
            RetractionRecord(
                pmid="55555555",
                doi=None,
                title="custom",
                journal="J",
                year=2024,
                status=RetractionStatus.RETRACTED,
                notice_url=None,
                reason_summary="x",
                flagged_at="2026-05-16",
            ),
        ])
        self.assertEqual(len(all_records()), before + 1)
        self.assertIsNotNone(is_retracted(pmid="55555555"))


class TestFormatHits(unittest.TestCase):
    def setUp(self) -> None:
        reset_to_seed()

    def test_empty_returns_clean_message(self) -> None:
        self.assertIn("Clean", format_hits([]))

    def test_renders_table_for_hits(self) -> None:
        hits = scan_text_for_retracted_pmids("PMID 99000001")
        out = format_hits(hits)
        self.assertIn("99000001", out)
        self.assertIn("retracted", out.lower())


if __name__ == "__main__":
    unittest.main()
