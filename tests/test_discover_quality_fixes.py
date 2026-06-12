"""Regressions for two real discover-quality flaws found in a live run:
 - a PubMed BookDocument (book chapter) rendered with a BLANK title;
 - CT.gov returning 0 trials for a verbose multi-concept query whose tokens AND to
   nothing, even though relevant trials exist (the GWPCARE Lennox-Gastaut trials).
Both fixes are offline-testable (no network)."""

from __future__ import annotations

import unittest

import cannavec_science.ctgov_discover as ctgov_mod
import cannavec_science.live as live
from cannavec_science.pubmed_search import PubMedSearcher


# ── book / non-English title fallback (never show a blank candidate) ──────────

class PubMedTitleFallback(unittest.TestCase):
    def test_book_record_falls_back_to_booktitle(self):
        hit = PubMedSearcher._record_to_hit(
            "31909928", {"title": "", "booktitle": "Cannabis-based medicinal products"})
        self.assertEqual(hit.title, "Cannabis-based medicinal products")

    def test_non_english_falls_back_to_vernacular_title(self):
        hit = PubMedSearcher._record_to_hit(
            "1", {"title": "", "vernaculartitle": "Titre français"})
        self.assertEqual(hit.title, "Titre français")

    def test_normal_article_title_is_unchanged(self):
        hit = PubMedSearcher._record_to_hit(
            "1", {"title": "Cannabidiol in Dravet syndrome", "booktitle": "ignored"})
        self.assertEqual(hit.title, "Cannabidiol in Dravet syndrome")

    def test_no_title_anywhere_is_empty_not_a_crash(self):
        hit = PubMedSearcher._record_to_hit("1", {})
        self.assertEqual(hit.title, "")


# ── CT.gov verbose-query 0-result fallback ───────────────────────────────────

class _FakeCTGov:
    """Returns rows only for an exact query string; records every query it saw."""
    def __init__(self, results):
        self.results = results
        self.calls: list = []

    def search(self, query, **kw):
        self.calls.append(query)
        return list(self.results.get(query, []))


class CTGovIndicationFallback(unittest.TestCase):
    def test_fallback_picks_specific_indication_over_family(self):
        fb = live._ctgov_indication_fallback(
            "delta-9-tetrahydrocannabinol Lennox-Gastaut syndrome tonic-clonic seizures")
        self.assertEqual(fb, "lennox-gastaut")              # specific, not "epilepsy"

    def test_no_indication_no_fallback(self):
        self.assertIsNone(live._ctgov_indication_fallback("CBD pharmacokinetics CYP3A4"))

    def test_run_ctgov_retries_with_indication_when_verbose_query_is_empty(self):
        verbose = "delta-9-tetrahydrocannabinol Lennox-Gastaut syndrome tonic-clonic seizures"
        fake = _FakeCTGov({"lennox-gastaut": ["NCT02815540"]})   # verbose → [], indication → hit
        orig = ctgov_mod.CTGovSearcher
        ctgov_mod.CTGovSearcher = lambda: fake
        try:
            rows = live._run_ctgov(verbose, None, 5)
        finally:
            ctgov_mod.CTGovSearcher = orig
        self.assertEqual(rows, ["NCT02815540"])             # recovered, not 0
        self.assertEqual(fake.calls, [verbose, "lennox-gastaut"])  # primary then fallback

    def test_run_ctgov_does_not_retry_when_primary_has_results(self):
        q = "CBD epilepsy"
        fake = _FakeCTGov({q: ["NCT1"]})                    # primary already matches
        orig = ctgov_mod.CTGovSearcher
        ctgov_mod.CTGovSearcher = lambda: fake
        try:
            rows = live._run_ctgov(q, None, 5)
        finally:
            ctgov_mod.CTGovSearcher = orig
        self.assertEqual(rows, ["NCT1"])
        self.assertEqual(fake.calls, [q])                   # no fallback — purely additive


if __name__ == "__main__":
    unittest.main()
