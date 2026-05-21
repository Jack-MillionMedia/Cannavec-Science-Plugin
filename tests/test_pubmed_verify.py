"""Tests for `cannavec.pubmed_verify`.

All tests inject a canned fetcher so the suite runs offline. The
fixtures mirror the shape of real NCBI esummary and Crossref JSON
responses (verified against
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed
&retmode=json&id=28538134 at the time the fixture was authored).
"""

from __future__ import annotations

import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.pubmed_verify import (   # noqa: E402
    CrossrefRecord,
    PubMedRecord,
    VerificationVerdict,
    _decode_response_strict,
    fetch_crossref_doi,
    fetch_pubmed_record,
    scan_dois,
    scan_pmids,
    surname_normalise,
    verify_doi,
    verify_pmid,
    verify_text,
)


# ── Surname normalisation ─────────────────────────────────────────────


class TestSurnameNormalise(unittest.TestCase):
    def test_drops_diacritics(self) -> None:
        self.assertEqual(surname_normalise("Tóth"), "toth")
        self.assertEqual(surname_normalise("Oláh"), "olah")
        self.assertEqual(surname_normalise("Beránek"), "beranek")
        self.assertEqual(surname_normalise("Tóth"),
                         surname_normalise("Toth"))

    def test_drops_apostrophes_and_hyphens(self) -> None:
        self.assertEqual(surname_normalise("O'Brien"), "obrien")
        self.assertEqual(surname_normalise("Smith-Jones"), "smithjones")
        # Different ways of spelling a name compare equal once normalised.
        self.assertEqual(
            surname_normalise("d'Argent"),
            surname_normalise("dArgent"),
        )

    def test_empty_returns_empty(self) -> None:
        self.assertEqual(surname_normalise(""), "")
        self.assertEqual(surname_normalise(None or ""), "")


# ── Fixture builders ──────────────────────────────────────────────────


def _devinsky_2017_esummary_body() -> str:
    """Shape-accurate fixture for the Devinsky 2017 NEJM CBD/Dravet trial."""
    return json.dumps({
        "header": {"type": "esummary", "version": "0.3"},
        "result": {
            "uids": ["28538134"],
            "28538134": {
                "uid": "28538134",
                "pubdate": "2017 May 25",
                "epubdate": "2017 May 25",
                "source": "N Engl J Med",
                "authors": [
                    {"name": "Devinsky O", "authtype": "Author", "clusterid": ""},
                    {"name": "Cross JH", "authtype": "Author", "clusterid": ""},
                    {"name": "Laux L", "authtype": "Author", "clusterid": ""},
                ],
                "title": (
                    "Trial of Cannabidiol for Drug-Resistant Seizures in "
                    "the Dravet Syndrome."
                ),
                "pubtype": ["Journal Article", "Randomized Controlled Trial"],
            },
        },
    })


def _retracted_pmid_body(pmid: str) -> str:
    return json.dumps({
        "result": {
            "uids": [pmid],
            pmid: {
                "uid": pmid,
                "pubdate": "2018 Mar 15",
                "source": "J Retracted Studies",
                "authors": [{"name": "Bogus A", "authtype": "Author"}],
                "title": "A retracted manuscript",
                "pubtype": ["Journal Article", "Retracted Publication"],
            },
        },
    })


def _not_found_body(pmid: str) -> str:
    return json.dumps({
        "header": {"type": "esummary"},
        "result": {"uids": [pmid], pmid: {"uid": pmid, "error": "cannot get document summary"}},
    })


def _crossref_devinsky_body() -> str:
    return json.dumps({
        "status": "ok",
        "message-type": "work",
        "message": {
            "DOI": "10.1056/nejmoa1611618",
            "title": [
                "Trial of Cannabidiol for Drug-Resistant Seizures in "
                "the Dravet Syndrome"
            ],
            "container-title": ["New England Journal of Medicine"],
            "issued": {"date-parts": [[2017, 5, 25]]},
            "created": {"date-parts": [[2017, 5, 24]]},
            "author": [
                {"family": "Devinsky", "given": "Orrin"},
                {"family": "Cross", "given": "J. Helen"},
            ],
        },
    })


def _crossref_404_body() -> str:
    # Crossref returns 404 with empty body, but JSON-decodable error
    # responses also occur on some endpoints. Test both branches.
    return json.dumps({"status": "fail", "message": {}})


# ── PubMed fetcher ────────────────────────────────────────────────────


class TestFetchPubMedRecord(unittest.TestCase):

    def test_valid_pmid_returns_record(self) -> None:
        body = _devinsky_2017_esummary_body()
        rec = fetch_pubmed_record("28538134", fetcher=lambda url: body)
        assert rec is not None
        self.assertEqual(rec.pmid, "28538134")
        self.assertEqual(rec.first_author_surname, "Devinsky")
        self.assertEqual(rec.year, 2017)
        self.assertEqual(rec.journal, "N Engl J Med")
        self.assertIn("Cannabidiol", rec.title)
        self.assertEqual(rec.retraction_status, "clean")

    def test_malformed_pmid_returns_none(self) -> None:
        # Letters in PMID → reject pre-fetch.
        self.assertIsNone(
            fetch_pubmed_record("abc123", fetcher=lambda url: "ignored")
        )
        # Too short.
        self.assertIsNone(
            fetch_pubmed_record("12", fetcher=lambda url: "ignored")
        )

    def test_pmid_not_found_returns_none(self) -> None:
        body = _not_found_body("99999999")
        rec = fetch_pubmed_record("99999999", fetcher=lambda url: body)
        self.assertIsNone(rec)

    def test_retracted_pmid_reports_retraction_status(self) -> None:
        body = _retracted_pmid_body("12345678")
        rec = fetch_pubmed_record("12345678", fetcher=lambda url: body)
        assert rec is not None
        self.assertEqual(rec.retraction_status, "retracted")

    def test_malformed_json_returns_none(self) -> None:
        rec = fetch_pubmed_record(
            "28538134", fetcher=lambda url: "<html>not json</html>",
        )
        self.assertIsNone(rec)


# ── PubMed verification ───────────────────────────────────────────────


class TestVerifyPmid(unittest.TestCase):

    def test_match_when_surname_and_year_align(self) -> None:
        body = _devinsky_2017_esummary_body()
        result = verify_pmid(
            "28538134",
            expected_first_author="Devinsky",
            expected_year=2017,
            fetcher=lambda url: body,
        )
        self.assertEqual(result.verdict, VerificationVerdict.MATCH)
        self.assertTrue(result.passed)
        self.assertEqual(result.actual_first_author, "Devinsky")
        self.assertEqual(result.actual_year, 2017)

    def test_diacritic_difference_is_accepted(self) -> None:
        body = json.dumps({
            "result": {
                "uids": ["11111111"],
                "11111111": {
                    "uid": "11111111",
                    "pubdate": "2018",
                    "source": "Eur J Pain",
                    "authors": [{"name": "Tóth A", "authtype": "Author"}],
                    "title": "x",
                    "pubtype": ["Journal Article"],
                },
            },
        })
        result = verify_pmid(
            "11111111",
            expected_first_author="Toth",
            expected_year=2018,
            fetcher=lambda url: body,
        )
        # surname normaliser strips the accent → match.
        self.assertEqual(result.verdict, VerificationVerdict.MATCH)

    def test_surname_mismatch_yields_mismatch(self) -> None:
        body = _devinsky_2017_esummary_body()
        result = verify_pmid(
            "28538134",
            expected_first_author="Smith",   # wrong author
            expected_year=2017,
            fetcher=lambda url: body,
        )
        self.assertEqual(result.verdict, VerificationVerdict.MISMATCH)
        self.assertFalse(result.passed)

    def test_year_mismatch_yields_mismatch(self) -> None:
        body = _devinsky_2017_esummary_body()
        result = verify_pmid(
            "28538134",
            expected_first_author="Devinsky",
            expected_year=2019,   # wrong year
            fetcher=lambda url: body,
        )
        self.assertEqual(result.verdict, VerificationVerdict.MISMATCH)

    def test_bare_cite_ok_when_no_claim_provided(self) -> None:
        body = _devinsky_2017_esummary_body()
        result = verify_pmid("28538134", fetcher=lambda url: body)
        self.assertEqual(result.verdict, VerificationVerdict.BARE_CITE_OK)
        self.assertTrue(result.passed)

    def test_not_found_yields_not_found(self) -> None:
        body = _not_found_body("99999999")
        result = verify_pmid("99999999", fetcher=lambda url: body)
        self.assertEqual(result.verdict, VerificationVerdict.NOT_FOUND)
        self.assertFalse(result.passed)

    def test_retracted_overrides_match(self) -> None:
        body = _retracted_pmid_body("12345678")
        result = verify_pmid(
            "12345678",
            expected_first_author="Bogus",
            expected_year=2018,
            fetcher=lambda url: body,
        )
        # Even though surname + year match, retraction precludes acceptance.
        self.assertEqual(result.verdict, VerificationVerdict.RETRACTED)
        self.assertFalse(result.passed)

    def test_network_error_yields_network_error_verdict(self) -> None:
        def angry_fetcher(_url: str) -> str:
            raise urllib.error.URLError("connection refused")
        result = verify_pmid("28538134", fetcher=angry_fetcher)
        self.assertEqual(result.verdict, VerificationVerdict.NETWORK_ERROR)
        self.assertFalse(result.passed)


# ── Crossref ──────────────────────────────────────────────────────────


class TestFetchCrossrefDoi(unittest.TestCase):

    def test_valid_doi_returns_record(self) -> None:
        body = _crossref_devinsky_body()
        rec = fetch_crossref_doi(
            "10.1056/nejmoa1611618", fetcher=lambda url: body,
        )
        assert rec is not None
        self.assertEqual(rec.year, 2017)
        self.assertEqual(rec.first_author_surname, "Devinsky")
        self.assertEqual(rec.container_title, "New England Journal of Medicine")

    def test_malformed_doi_returns_none(self) -> None:
        self.assertIsNone(
            fetch_crossref_doi("not-a-doi", fetcher=lambda url: "ignored")
        )

    def test_fail_response_returns_none(self) -> None:
        body = _crossref_404_body()
        rec = fetch_crossref_doi("10.9999/notexists", fetcher=lambda url: body)
        self.assertIsNone(rec)


class TestVerifyDoi(unittest.TestCase):

    def test_match(self) -> None:
        body = _crossref_devinsky_body()
        result = verify_doi(
            "10.1056/nejmoa1611618",
            expected_first_author="Devinsky",
            expected_year=2017,
            fetcher=lambda url: body,
        )
        self.assertEqual(result.verdict, VerificationVerdict.MATCH)

    def test_year_mismatch(self) -> None:
        body = _crossref_devinsky_body()
        result = verify_doi(
            "10.1056/nejmoa1611618",
            expected_first_author="Devinsky",
            expected_year=2020,
            fetcher=lambda url: body,
        )
        self.assertEqual(result.verdict, VerificationVerdict.MISMATCH)

    def test_bare_cite(self) -> None:
        body = _crossref_devinsky_body()
        result = verify_doi("10.1056/nejmoa1611618", fetcher=lambda url: body)
        self.assertEqual(result.verdict, VerificationVerdict.BARE_CITE_OK)


# ── Scanners ──────────────────────────────────────────────────────────


class TestScanners(unittest.TestCase):

    def test_pmid_scanner_finds_inline_forms(self) -> None:
        text = (
            "Devinsky 2017 NEJM (PMID 28538134) and Cross 2018 NEJM "
            "(PMID: 30009 ). Also see PMID#12345678 cited elsewhere."
        )
        self.assertEqual(scan_pmids(text), ("28538134", "30009", "12345678"))

    def test_pmid_scanner_deduplicates(self) -> None:
        text = "PMID 28538134 and PMID 28538134 again."
        self.assertEqual(scan_pmids(text), ("28538134",))

    def test_doi_scanner_finds_inline_forms(self) -> None:
        text = (
            "doi:10.1056/NEJMoa1611618 alongside 10.1016/j.cell.2020.01.001."
        )
        result = scan_dois(text)
        self.assertIn("10.1056/NEJMoa1611618", result)
        self.assertIn("10.1016/j.cell.2020.01.001", result)

    def test_doi_scanner_skips_reserved_namespace(self) -> None:
        # 10.0000/ is reserved/unassigned in CrossRef — used in
        # illustrative examples and historically by Cannavec's stub
        # generator. The scanner must skip these.
        text = "Bogus citation: doi:10.0000/example.28538134"
        self.assertEqual(scan_dois(text), ())

    def test_doi_scanner_strips_trailing_punctuation(self) -> None:
        text = "See (doi:10.1056/NEJMoa1611618)."
        self.assertEqual(scan_dois(text), ("10.1056/NEJMoa1611618",))


class TestCharsetWhitelist(unittest.TestCase):
    """Regression tests for Oracle Auditor §SEC-003: the network
    fetchers must whitelist response charsets so a misbehaving
    upstream cannot smuggle silently-corrupted JSON through
    ``errors='replace'``.
    """

    def test_default_utf8_decode_succeeds(self) -> None:
        body = '{"k": "value"}'.encode("utf-8")
        self.assertEqual(
            _decode_response_strict(body, "utf-8"),
            '{"k": "value"}',
        )

    def test_missing_charset_falls_back_to_utf8(self) -> None:
        body = "Tóth".encode("utf-8")
        self.assertEqual(
            _decode_response_strict(body, None), "Tóth",
        )

    def test_exotic_charset_coerced_to_utf8(self) -> None:
        # Declared charset is exotic (iso-2022-jp); whitelist coerces
        # the decoder to utf-8 so the bytes are read as the safe
        # charset and any inconsistency raises rather than silently
        # mangling.
        body = '{"name": "ascii"}'.encode("utf-8")
        self.assertEqual(
            _decode_response_strict(body, "iso-2022-jp"),
            '{"name": "ascii"}',
        )

    def test_malformed_utf8_raises_unicode_decode_error(self) -> None:
        # Raw non-UTF-8 bytes with charset claiming utf-8 should
        # raise rather than fall through with errors="replace".
        bad = b"\xff\xfe\xfd"
        with self.assertRaises(UnicodeDecodeError):
            _decode_response_strict(bad, "utf-8")

    def test_ascii_charset_is_safe(self) -> None:
        body = b'{"x": 1}'
        self.assertEqual(
            _decode_response_strict(body, "ascii"), '{"x": 1}',
        )


class TestVerifyText(unittest.TestCase):

    def test_verifies_each_pmid_and_doi(self) -> None:
        text = (
            "Devinsky 2017 (PMID 28538134); see also doi:10.1056/nejmoa1611618."
        )

        def pmid_fetcher(url: str) -> str:
            return _devinsky_2017_esummary_body()

        def doi_fetcher(url: str) -> str:
            return _crossref_devinsky_body()

        results = verify_text(
            text, pmid_fetcher=pmid_fetcher, doi_fetcher=doi_fetcher,
        )
        self.assertEqual(len(results), 2)
        verdicts = {r.verdict for r in results}
        self.assertEqual(verdicts, {VerificationVerdict.BARE_CITE_OK})


if __name__ == "__main__":
    unittest.main()
