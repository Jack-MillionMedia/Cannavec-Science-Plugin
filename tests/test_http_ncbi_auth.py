"""Tests for NCBI E-utilities authentication wiring (spec 028 / Phase 2).

The production fix for the sandbox/cloud ``403 Forbidden``: append an
``api_key`` (and optional ``email``) to NCBI E-utilities URLs when the
operator sets ``NCBI_API_KEY``. Must be a strict no-op otherwise, and must
never leak the credential to a non-NCBI host.
"""

from __future__ import annotations

import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from cannavec_science import _http

_EUTILS = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&retmode=json&tool=cannavec&term=cannabis"
)
_CROSSREF = "https://api.crossref.org/works/10.1056/NEJMoa1611618"


class NcbiKeyTests(unittest.TestCase):
    def test_key_none_when_unset(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(_http.ncbi_api_key())
            self.assertIsNone(_http.ncbi_email())

    def test_key_read_from_env(self):
        with mock.patch.dict("os.environ", {"NCBI_API_KEY": "  abc123 "}):
            self.assertEqual(_http.ncbi_api_key(), "abc123")

    def test_email_read_from_env(self):
        with mock.patch.dict("os.environ", {"NCBI_EMAIL": "ops@example.org"}):
            self.assertEqual(_http.ncbi_email(), "ops@example.org")


class AppendNcbiAuthTests(unittest.TestCase):
    def test_noop_when_key_unset(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_http.append_ncbi_auth(_EUTILS), _EUTILS)

    def test_appends_api_key_for_eutils(self):
        with mock.patch.dict("os.environ", {"NCBI_API_KEY": "KEY"}, clear=True):
            out = _http.append_ncbi_auth(_EUTILS)
        q = parse_qs(urlsplit(out).query)
        self.assertEqual(q["api_key"], ["KEY"])
        # Existing params are preserved.
        self.assertEqual(q["db"], ["pubmed"])
        self.assertEqual(q["tool"], ["cannavec"])

    def test_appends_email_when_set(self):
        with mock.patch.dict("os.environ",
                             {"NCBI_API_KEY": "KEY", "NCBI_EMAIL": "a@b.org"},
                             clear=True):
            out = _http.append_ncbi_auth(_EUTILS)
        q = parse_qs(urlsplit(out).query)
        self.assertEqual(q["api_key"], ["KEY"])
        self.assertEqual(q["email"], ["a@b.org"])

    def test_never_touches_non_ncbi_host(self):
        with mock.patch.dict("os.environ", {"NCBI_API_KEY": "KEY"}, clear=True):
            self.assertEqual(_http.append_ncbi_auth(_CROSSREF), _CROSSREF)
            self.assertNotIn("api_key", _http.append_ncbi_auth(_CROSSREF))

    def test_does_not_double_append(self):
        with mock.patch.dict("os.environ", {"NCBI_API_KEY": "KEY"}, clear=True):
            once = _http.append_ncbi_auth(_EUTILS)
            twice = _http.append_ncbi_auth(once)
        self.assertEqual(parse_qs(urlsplit(twice).query)["api_key"], ["KEY"])

    def test_preexisting_key_is_respected(self):
        url = _EUTILS + "&api_key=ORIGINAL"
        with mock.patch.dict("os.environ", {"NCBI_API_KEY": "NEW"}, clear=True):
            out = _http.append_ncbi_auth(url)
        self.assertEqual(parse_qs(urlsplit(out).query)["api_key"], ["ORIGINAL"])


if __name__ == "__main__":
    unittest.main()
