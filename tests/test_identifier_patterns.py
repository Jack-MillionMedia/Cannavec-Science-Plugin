"""Characterization tests for the scientific-identifier scanners (§I / §VIII).

These pin the EXACT current behavior of the PMID / DOI / NCT pattern surfaces so
the "single source of truth" refactor (centralizing the duplicated pattern cores
into ``cannavec_science._identifiers``) cannot silently change matching. They
must pass before AND after that refactor.

The load-bearing invariant they protect: the verifier scans only PREFIXED PMIDs
("PMID 12345678") while the §VIII retraction sweep scans BARE numbers — and the
bare sweep is bounded to >= 6 digits so a 4-digit year ("2017") is never mistaken
for a PMID. Unifying those two ranges would reintroduce that false-positive.

Stdlib only, fully offline, deterministic.
"""

from __future__ import annotations

import unittest

from cannavec_science.pubmed_verify import scan_pmids, scan_dois
from cannavec_science.retraction import scan_text_for_retracted_pmids
from cannavec_science.__main__ import _classify_identifier

# Real retracted seed records (pmid + doi) — used to prove the bare retraction
# sweep still catches an unprefixed identifier.
_RETRACTED_PMID = "32060308"
_RETRACTED_DOI = "10.1038/s41598-020-59468-4"


class PmidScanRequiresPrefix(unittest.TestCase):
    """The bulk verifier scans only explicitly-labelled PMIDs (never bare
    numbers), so it cannot waste a verify API call on a year or a count."""

    def test_prefixed_pmid_is_found(self):
        self.assertEqual(scan_pmids("See PMID: 12345678 for details."), ("12345678",))
        self.assertEqual(scan_pmids("pmid 32060308 and PMID:26622862"),
                         ("32060308", "26622862"))

    def test_bare_number_is_not_a_pmid_for_the_verifier(self):
        self.assertEqual(scan_pmids("the number 32060308 alone"), ())
        self.assertEqual(scan_pmids("published in 2017 with n=2048"), ())

    def test_four_digit_prefixed_pmid_is_allowed(self):
        self.assertEqual(scan_pmids("PMID 1234"), ("1234",))

    def test_dedup_preserves_order(self):
        self.assertEqual(scan_pmids("PMID 1111 PMID 2222 PMID 1111"),
                         ("1111", "2222"))


class DoiScanBehavior(unittest.TestCase):
    """DOI scan: optional prefix, broad trailing class, trailing-punct strip, and
    the fabricated 10.0000 namespace is skipped."""

    def test_doi_with_and_without_prefix(self):
        self.assertEqual(scan_dois("doi: 10.1038/s41598-020-59468-4."),
                         ("10.1038/s41598-020-59468-4",))
        self.assertEqual(scan_dois("(10.1155/2021/6612592)"),
                         ("10.1155/2021/6612592",))

    def test_fabricated_namespace_is_skipped(self):
        self.assertEqual(scan_dois("10.0000/fabricated-x"), ())

    def test_dedup_preserves_order(self):
        self.assertEqual(
            scan_dois("10.1234/a and 10.5678/b and 10.1234/a"),
            ("10.1234/a", "10.5678/b"),
        )


class RetractionSweepCatchesBareIdentifiers(unittest.TestCase):
    """§VIII — the retraction sweep must flag a retracted PMID/DOI even when it
    appears as a BARE token, and must not mistake a 4-digit year for a PMID."""

    def test_bare_retracted_pmid_is_flagged(self):
        hits = scan_text_for_retracted_pmids(f"see {_RETRACTED_PMID} for the study")
        self.assertTrue(any(h.matched_identifier == _RETRACTED_PMID
                            and h.matched_kind == "pmid" for h in hits),
                        f"bare retracted PMID not caught: {hits}")

    def test_retracted_doi_is_flagged(self):
        hits = scan_text_for_retracted_pmids(f"reported in {_RETRACTED_DOI}.")
        self.assertTrue(any(h.matched_identifier == _RETRACTED_DOI
                            and h.matched_kind == "doi" for h in hits),
                        f"retracted DOI not caught: {hits}")

    def test_four_digit_year_is_not_swept_as_a_pmid(self):
        # 2017 is 4 digits; the bare sweep requires >= 6, so no spurious lookup.
        hits = scan_text_for_retracted_pmids("a 2017 review of 1999 data")
        self.assertEqual([h for h in hits if h.matched_kind == "pmid"], [])


class ClassifyIdentifierShapes(unittest.TestCase):
    """The CLI verify classifier maps a single token to one of the five §I
    shapes."""

    def test_nct_classification_is_case_insensitive(self):
        self.assertEqual(_classify_identifier("NCT12345678"), "NCT")
        self.assertEqual(_classify_identifier("nct12345678"), "NCT")

    def test_pmid_doi_chembl_shapes(self):
        self.assertEqual(_classify_identifier("32060308"), "PMID")
        self.assertEqual(_classify_identifier("10.1038/s41598-020-59468-4"), "DOI")
        self.assertEqual(_classify_identifier("CHEMBL25"), "ChEMBL")

    def test_malformed_nct_is_not_classified_as_nct(self):
        self.assertNotEqual(_classify_identifier("NCT123"), "NCT")  # too short


if __name__ == "__main__":
    unittest.main()
