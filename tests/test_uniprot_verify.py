"""Tests for cannavec_science.uniprot_verify (spec 003 US5 / FR-005).

Mirrors the offline-injected-fetcher pattern used by every other
Tier-3 verifier (PubMed / Crossref / ChEMBL / CT.gov): a fixture
fetcher returns canned JSON so the tests run with zero network calls.
"""

from __future__ import annotations

import json
import unittest
import urllib.error

from cannavec_science.uniprot_verify import (
    UniProtRecord,
    fetch_uniprot_record,
    is_uniprot_accession,
    verify_uniprot,
)


# ── Accession shape checks ─────────────────────────────────────────────


class AccessionShapeTests(unittest.TestCase):
    """Constitution §I — the verify surface gates accept/reject on the
    canonical UniProt regex."""

    def test_cb1_p21554_passes(self):
        self.assertTrue(is_uniprot_accession("P21554"))

    def test_cb2_p34972_passes(self):
        self.assertTrue(is_uniprot_accession("P34972"))

    def test_trpv1_q8ner1_passes(self):
        self.assertTrue(is_uniprot_accession("Q8NER1"))

    def test_ppar_gamma_p37231_passes(self):
        self.assertTrue(is_uniprot_accession("P37231"))

    def test_trembl_a1b2c34567_passes(self):
        # TrEMBL pattern: [A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}
        self.assertTrue(is_uniprot_accession("A1ABC1"))

    def test_lowercase_normalises(self):
        # The verifier uppercases before regex, so lower-case should work.
        self.assertTrue(is_uniprot_accession("p21554"))

    def test_pmid_does_not_match(self):
        self.assertFalse(is_uniprot_accession("28538134"))

    def test_doi_does_not_match(self):
        self.assertFalse(is_uniprot_accession("10.1056/NEJMoa1611618"))

    def test_chembl_does_not_match(self):
        self.assertFalse(is_uniprot_accession("CHEMBL5803"))

    def test_nct_does_not_match(self):
        self.assertFalse(is_uniprot_accession("NCT02224560"))

    def test_empty_does_not_match(self):
        self.assertFalse(is_uniprot_accession(""))


# ── Fetcher fixtures ──────────────────────────────────────────────────


_CB1_PAYLOAD = {
    "primaryAccession": "P21554",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "Cannabinoid receptor 1"},
        },
    },
    "genes": [{"geneName": {"value": "CNR1"}}],
    "organism": {
        "scientificName": "Homo sapiens",
        "taxonId": 9606,
    },
    "sequence": {"length": 472, "molWeight": 52864},
}


def _green_fetcher(url: str) -> str:
    return json.dumps(_CB1_PAYLOAD)


def _not_found_fetcher(url: str) -> str:
    # Simulate a 404 from UniProt — fetcher raises HTTPError.
    raise urllib.error.HTTPError(
        url=url, code=404, msg="Not Found", hdrs=None, fp=None,
    )


def _network_error_fetcher(url: str) -> str:
    raise urllib.error.URLError("connection refused")


# ── Positive: record parses correctly ─────────────────────────────────


class PositiveResolutionTests(unittest.TestCase):
    """Per Constitution §III, each Tier-3 resolver ships a positive case."""

    def test_cb1_p21554_parses(self):
        rec = fetch_uniprot_record("P21554", fetcher=_green_fetcher)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.accession, "P21554")
        self.assertEqual(rec.protein_name, "Cannabinoid receptor 1")
        self.assertEqual(rec.gene_symbol, "CNR1")
        self.assertEqual(rec.organism, "Homo sapiens")
        self.assertEqual(rec.organism_taxon_id, 9606)
        self.assertEqual(rec.sequence_length, 472)
        self.assertTrue(rec.reviewed)

    def test_verify_uniprot_public_entry(self):
        # verify_uniprot is the public surface; same shape as
        # verify_pmid / verify_doi.
        rec = verify_uniprot("P21554", fetcher=_green_fetcher)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.accession, "P21554")

    def test_to_dict_round_trip(self):
        rec = fetch_uniprot_record("P21554", fetcher=_green_fetcher)
        d = rec.to_dict()
        self.assertEqual(d["accession"], "P21554")
        self.assertEqual(d["gene_symbol"], "CNR1")
        # JSON-serialisable.
        json.dumps(d)


# ── Negative: malformed / unknown identifiers ─────────────────────────


class NegativeShapeTests(unittest.TestCase):
    """Per Constitution §III, each resolver ships a negative case."""

    def test_non_accession_returns_none(self):
        # PubMed-style identifier — not a UniProt accession.
        rec = fetch_uniprot_record("12345678", fetcher=_green_fetcher)
        self.assertIsNone(rec)

    def test_doi_shape_returns_none(self):
        rec = fetch_uniprot_record(
            "10.1056/NEJMoa1611618", fetcher=_green_fetcher,
        )
        self.assertIsNone(rec)

    def test_empty_returns_none(self):
        self.assertIsNone(fetch_uniprot_record("", fetcher=_green_fetcher))


class NotFoundResolutionTests(unittest.TestCase):
    """A 404 from upstream returns None rather than raising."""

    def test_404_returns_none(self):
        rec = fetch_uniprot_record("P00000", fetcher=_not_found_fetcher)
        self.assertIsNone(rec)


# ── Network error: surfaces, not silently swallowed ──────────────────


class NetworkErrorTests(unittest.TestCase):
    """Per Constitution §III, each resolver ships a network-error case.

    Unlike a 404 (which is "the accession is not real"), a transport
    error is a real exception the caller may want to retry. The verifier
    propagates the exception so callers can handle it.
    """

    def test_network_error_propagates(self):
        with self.assertRaises(urllib.error.URLError):
            fetch_uniprot_record("P21554", fetcher=_network_error_fetcher)


if __name__ == "__main__":
    unittest.main()
