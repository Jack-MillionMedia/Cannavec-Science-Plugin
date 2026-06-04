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

    def test_synthetic_fixtures_are_labelled_example(self) -> None:
        # Expectation updated for defect #10: the seed no longer ships
        # synthetic-ONLY records — it carries real, ground-truthed
        # retractions too (see TestRealRetractionSeed). The remaining
        # invariant is narrower: any SYNTHETIC fixture (reserved
        # 99000000+ PMID / 10.99999 DOI ranges) must stay clearly
        # labelled as an example so it is never mistaken for a real
        # retraction.
        for r in all_records():
            is_synthetic = (
                (r.pmid or "").startswith("99000")
                or (r.doi or "").startswith("10.99999/")
            )
            if is_synthetic:
                self.assertIn(
                    "example", r.title.lower(),
                    "Synthetic fixtures must be labelled as examples.",
                )

    def test_real_records_are_not_labelled_example(self) -> None:
        # The flip side: a real retraction record must NOT carry the
        # synthetic "example" marker (it is a citable, ground-truthed
        # fact, not a placeholder).
        for r in all_records():
            is_synthetic = (
                (r.pmid or "").startswith("99000")
                or (r.doi or "").startswith("10.99999/")
            )
            if not is_synthetic:
                self.assertNotIn("example", r.title.lower())
                self.assertTrue(
                    r.notice_url,
                    "real records must carry a primary-source notice_url",
                )


class TestRealRetractionSeed(unittest.TestCase):
    """§VIII must ship armed with REAL retractions, not only placeholders.

    Each DOI below was ground-truthed against Crossref / Retraction Watch
    (cannabis-relevant retracted papers). The local registry exists
    precisely because Crossref's structured ``is_retracted`` is *false*
    on these originals — they carry only a title-prefix ``RETRACTED:``
    notice — so a researcher citing the original DOI would otherwise slip
    the §VIII net. The registry keys on the ORIGINAL paper DOI (what a
    citation actually contains).
    """

    # (original_doi, retraction_note_doi) — all verified retracted.
    REAL_RETRACTED = (
        ("10.1038/s41598-020-59468-4", "10.1038/s41598-024-51877-z"),
        ("10.1155/2021/6612592", "10.1155/2023/9803081"),
        ("10.3892/ol.2015.3525", "10.3892/ol.2023.14183"),
        ("10.1177/1934578x221098843", "10.1177/1934578x241309731"),
        ("10.1016/j.jpsychires.2024.05.029", "10.1016/j.jpsychires.2024.05.029"),
    )

    def setUp(self) -> None:
        reset_to_seed()

    def test_seed_contains_real_retractions_not_only_synthetic(self) -> None:
        real = [
            r for r in all_records()
            if not (r.pmid or "").startswith("99000")
            and not (r.doi or "").startswith("10.99999/")
        ]
        self.assertGreaterEqual(
            len(real), 4,
            "Seed registry must ship REAL retractions, not only the "
            "synthetic 99000001/99000002 placeholders (§VIII).",
        )

    def test_known_real_retracted_doi_flagged(self) -> None:
        # Spec exemplar: CBD-induced death in glioblastoma cultures.
        rec = is_retracted(doi="10.1038/s41598-020-59468-4")
        self.assertIsNotNone(
            rec, "A known real retracted cannabis DOI must be flagged."
        )
        assert rec is not None
        self.assertEqual(rec.status, RetractionStatus.RETRACTED)

    def test_all_curated_real_retracted_dois_flagged(self) -> None:
        for original_doi, _note in self.REAL_RETRACTED:
            rec = is_retracted(doi=original_doi)
            self.assertIsNotNone(
                rec, f"{original_doi} should be flagged retracted.",
            )
            assert rec is not None
            self.assertEqual(rec.status, RetractionStatus.RETRACTED)

    def test_real_records_are_citable_with_notice(self) -> None:
        # A real record must carry a primary-source notice URL and a real
        # journal — the retraction-status fact is as well-cited as the
        # paper it concerns (module docstring inclusion bar).
        rec = is_retracted(doi="10.1155/2021/6612592")
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertTrue(rec.notice_url, "real records must carry a notice_url")
        self.assertNotIn("example", rec.title.lower())

    def test_non_retracted_real_cannabis_doi_not_flagged(self) -> None:
        # Negative control: Devinsky 2017 Dravet RCT (NEJM) is a real,
        # NON-retracted, heavily-cited cannabis paper. It MUST NOT match.
        self.assertIsNone(is_retracted(doi="10.1056/NEJMoa1611618"))
        self.assertIsNone(is_retracted(pmid="28538134"))

    def test_real_retracted_doi_caught_in_prose_scan(self) -> None:
        text = (
            "The antitumor synergy was reported (doi:10.3892/ol.2015.3525), "
            "but the finding has not replicated."
        )
        hits = scan_text_for_retracted_pmids(text)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_kind, "doi")
        self.assertEqual(hits[0].record.status, RetractionStatus.RETRACTED)


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
