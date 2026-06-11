"""The shared lane-fetcher factory (_http.make_json_fetcher) replaces ~11
copy-pasted ``default_<lane>_fetcher`` functions that differed only by the UA
component string and the timeout. This pins the factory's contract: a polite
JSON GET through the bounded-retry transport, decoded UTF-8.

Stdlib only, offline (urlopen is monkeypatched), deterministic.
"""

from __future__ import annotations

import unittest

import cannavec_science._http as _http
from cannavec_science._http import make_json_fetcher, NetworkError, TIMEOUT_FAST, TIMEOUT_SLOW


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class MakeJsonFetcherContract(unittest.TestCase):
    def setUp(self):
        self._captured: dict = {}
        self._orig = _http.urllib.request.urlopen

        def fake_urlopen(req, timeout=None):
            self._captured["url"] = req.full_url
            self._captured["ua"] = req.get_header("User-agent")
            self._captured["accept"] = req.get_header("Accept")
            self._captured["timeout"] = timeout
            return _FakeResp(b'{"ok": true}')

        _http.urllib.request.urlopen = fake_urlopen

    def tearDown(self):
        _http.urllib.request.urlopen = self._orig

    def test_builds_polite_json_get_and_decodes(self):
        fetch = make_json_fetcher("widget-discover")
        out = fetch("https://example.org/x.json")
        self.assertEqual(out, '{"ok": true}')
        self.assertEqual(self._captured["url"], "https://example.org/x.json")
        self.assertEqual(self._captured["accept"], "application/json")
        self.assertIn("cannavec-widget-discover/", self._captured["ua"])
        self.assertEqual(self._captured["timeout"], TIMEOUT_FAST)

    def test_timeout_is_configurable(self):
        fetch = make_json_fetcher("slow-discover", timeout=TIMEOUT_SLOW)
        fetch("https://example.org/y.json")
        self.assertEqual(self._captured["timeout"], TIMEOUT_SLOW)


class NetworkErrorIsShared(unittest.TestCase):
    def test_network_error_is_an_exception(self):
        self.assertTrue(issubclass(NetworkError, Exception))

    def test_lanes_re_export_the_same_class(self):
        from cannavec_science.chembl_discover import NetworkError as ChemblNE
        from cannavec_science.gwas_discover import NetworkError as GwasNE
        self.assertIs(ChemblNE, NetworkError)
        self.assertIs(GwasNE, NetworkError)


if __name__ == "__main__":
    unittest.main()
