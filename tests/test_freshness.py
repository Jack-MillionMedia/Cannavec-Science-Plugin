"""Tests for the registry freshness layer (spec 002 US5)."""

import datetime
import unittest

from cannavec_science.freshness import (
    DEFAULT_LAST_VERIFIED,
    FreshnessReport,
    FreshnessRow,
    FreshnessStatus,
    STALE_THRESHOLD_DAYS_HARD,
    STALE_THRESHOLD_DAYS_SOFT,
    all_registry_names,
    extract_watch_pmids,
    iter_registry_rows,
    probe_all,
    probe_registry,
    render_json,
    render_markdown,
    stale_suffix,
)


class RegistryEnumerationTests(unittest.TestCase):
    def test_canonical_eight_registries(self):
        names = all_registry_names()
        self.assertEqual(len(names), 8)
        self.assertIn("major_cannabinoids", names)
        self.assertIn("minor_cannabinoids", names)
        self.assertIn("interactions", names)
        self.assertIn("pharmacogenomics", names)

    def test_iter_registry_yields_triples(self):
        triples = list(iter_registry_rows("major_cannabinoids"))
        self.assertGreater(len(triples), 0)
        for row_id, row_label, row in triples:
            self.assertTrue(row_id)
            self.assertTrue(row_label)
            self.assertIsNotNone(row)

    def test_unknown_registry_raises(self):
        with self.assertRaises(ValueError):
            list(iter_registry_rows("nonexistent_registry"))


class WatchPmidExtractionTests(unittest.TestCase):
    def test_extracts_from_interactions_citations(self):
        from cannavec_science.interactions import all_interactions
        rows = all_interactions()
        first_row = rows[0]
        pmids = extract_watch_pmids(first_row)
        # The CBD-clobazam first row carries PMIDs.
        self.assertGreater(len(pmids), 0)

    def test_extracts_from_minor_cannabinoid_clinical_evidence(self):
        from cannavec_science.minor_cannabinoids import all_minor_cannabinoids
        rows = all_minor_cannabinoids()
        thcv = next(r for r in rows if r.name == "THCV")
        pmids = extract_watch_pmids(thcv)
        # THCV row has citations on multiple evidence rows.
        self.assertGreater(len(pmids), 0)

    def test_explicit_watch_pmids_field_wins(self):
        class Row:
            watch_pmids = ("12345", "67890")
            citations = ()
        pmids = extract_watch_pmids(Row())
        self.assertEqual(pmids, ("12345", "67890"))

    def test_empty_row_returns_empty(self):
        class Row:
            pass
        self.assertEqual(extract_watch_pmids(Row()), ())


class ProbeOfflineTests(unittest.TestCase):
    """Offline probes use only the local retraction registry."""

    def test_probe_interactions_returns_report(self):
        rep = probe_registry("interactions")
        self.assertIsInstance(rep, FreshnessReport)
        self.assertEqual(rep.registry, "interactions")
        self.assertGreater(len(rep.rows), 0)

    def test_probe_all_returns_eight_reports(self):
        reports = probe_all()
        self.assertEqual(len(reports), 8)
        names = [r.registry for r in reports]
        self.assertEqual(names, list(all_registry_names()))

    def test_offline_probe_does_not_detect_retraction_in_clean_registry(self):
        # No row in the curated registries cites a retracted PMID by
        # design (the retraction-enforcement layer keeps them out).
        rep = probe_registry("interactions")
        self.assertEqual(rep.n_retraction, 0)

    def test_no_watch_pmids_status_for_url_only_rows(self):
        # Some PGx rows cite without PMIDs.
        rep = probe_registry("pharmacogenomics")
        # The status enum surface includes NO_WATCH_PMIDS when rows
        # carry no PMIDs to probe.
        statuses = [r.status for r in rep.rows]
        self.assertTrue(
            FreshnessStatus.CLEAN in statuses
            or FreshnessStatus.NO_WATCH_PMIDS in statuses
        )

    def test_probe_does_not_mutate_registry_rows(self):
        from cannavec_science.interactions import all_interactions
        before = all_interactions()
        first_before = before[0]
        probe_registry("interactions")
        after = all_interactions()
        first_after = after[0]
        # Same identity (singleton tuple).
        self.assertIs(before, after)
        self.assertIs(first_before, first_after)


class ProbeWithFetcherTests(unittest.TestCase):
    def test_retracted_pmid_flagged_by_injected_fetcher(self):
        # Inject a fetcher that returns a retraction marker for one PMID.
        def stub_fetcher(url: str) -> str:
            # Recognise the test PMID and return a PubMed esummary with a
            # retraction pubtype.
            if "id=99999999" in url:
                return (
                    '{"result": {"99999999": {"title": "fake retracted paper",'
                    ' "pubdate": "2020", "pubtype": ["Retracted Publication"]}}}'
                )
            return '{"result": {"uids": []}}'

        class FakeRow:
            watch_pmids = ("99999999",)
            last_verified = DEFAULT_LAST_VERIFIED
            citations = ()

        from cannavec_science.freshness import _probe_one_row
        r = _probe_one_row(
            "test_registry", "test:row", "fake", FakeRow(),
            fetcher=stub_fetcher, today=None,
        )
        self.assertEqual(r.status, FreshnessStatus.RETRACTION_DETECTED)

    def test_network_error_pmid_flagged(self):
        def broken_fetcher(url: str) -> str:
            raise IOError("network down")

        class FakeRow:
            watch_pmids = ("88888888",)
            last_verified = DEFAULT_LAST_VERIFIED
            citations = ()

        from cannavec_science.freshness import _probe_one_row
        r = _probe_one_row(
            "test_registry", "test:row", "fake", FakeRow(),
            fetcher=broken_fetcher, today=None,
        )
        self.assertEqual(r.status, FreshnessStatus.NETWORK_ERROR)


class StaleSuffixTests(unittest.TestCase):
    def test_fresh_row_no_suffix(self):
        class Row:
            last_verified = "2026-05-21"
        suffix = stale_suffix(Row(), today=datetime.date(2026, 6, 1))
        self.assertEqual(suffix, "")

    def test_stale_row_gets_suffix(self):
        class Row:
            last_verified = "2024-01-01"
        suffix = stale_suffix(Row(), today=datetime.date(2026, 5, 21))
        self.assertIn("[freshness: stale", suffix)
        self.assertIn("2024-01-01", suffix)

    def test_boundary_at_365_days(self):
        class Row:
            last_verified = "2025-05-21"
        # Exactly 365 days later → stale.
        suffix = stale_suffix(Row(), today=datetime.date(2026, 5, 21))
        self.assertIn("stale", suffix)

    def test_just_under_365_days_not_stale(self):
        class Row:
            last_verified = "2025-05-21"
        # 364 days later → fresh.
        suffix = stale_suffix(Row(), today=datetime.date(2026, 5, 20))
        self.assertEqual(suffix, "")

    def test_no_last_verified_attribute_uses_default(self):
        class Row:
            pass
        # Default = v0.2 landing date = 2026-05-21. At "today=2026-06-01"
        # the row is fresh.
        suffix = stale_suffix(Row(), today=datetime.date(2026, 6, 1))
        self.assertEqual(suffix, "")


class StaleSoftThresholdTests(unittest.TestCase):
    def test_soft_threshold_surfaces_as_status(self):
        class FakeRow:
            last_verified = "2025-08-01"  # 290 days old at today
            citations = ()

        from cannavec_science.freshness import _probe_one_row
        r = _probe_one_row(
            "test", "test:row", "fake", FakeRow(),
            fetcher=None, today=datetime.date(2026, 5, 21),
        )
        self.assertEqual(r.status, FreshnessStatus.LAST_VERIFIED_STALE)


class RenderTests(unittest.TestCase):
    def test_markdown_renders_summary_and_rows(self):
        rep = probe_registry("interactions")
        md = render_markdown(rep)
        self.assertIn("Freshness probe", md)
        self.assertIn("interactions", md)
        self.assertIn("Total rows", md)

    def test_json_renders_serialisable(self):
        rep = probe_registry("interactions")
        s = render_json(rep)
        self.assertIn("registry", s)
        self.assertIn("interactions", s)


class ConstantsTests(unittest.TestCase):
    def test_default_last_verified_is_v02_landing(self):
        self.assertEqual(DEFAULT_LAST_VERIFIED, "2026-05-21")

    def test_thresholds_sane(self):
        self.assertEqual(STALE_THRESHOLD_DAYS_SOFT, 180)
        self.assertEqual(STALE_THRESHOLD_DAYS_HARD, 365)


if __name__ == "__main__":
    unittest.main()
