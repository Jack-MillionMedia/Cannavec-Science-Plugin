"""Tests for :mod:`cannavec_science._http` retry / backoff helper.

The retry helper sits underneath every live discoverer and verifier; a
silent regression here would surface to the user as confusing latency
spikes or "transient" errors becoming permanent. Pinned behaviour:

- Retries on 429 / 502 / 503 / 504.
- Does NOT retry on 404, 401, 403, 500 (hard errors propagate).
- Honours ``Retry-After`` (numeric seconds) on 429.
- Caps backoff at 8 s and Retry-After at 30 s (defeat hostile upstreams).
- Surfaces :class:`RetryableHTTPError` after ``max_attempts`` failures.
- Retries on :class:`urllib.error.URLError` (transient network).
"""

from __future__ import annotations

import io
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from cannavec_science._http import (
    RetryableHTTPError,
    TIMEOUT_FAST,
    TIMEOUT_SLOW,
    crossref_contact,
    retry_urlopen,
    user_agent,
)


def _http_error(code: int, *, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        url="https://example.test/x",
        code=code,
        msg=f"upstream {code}",
        hdrs=headers,
        fp=io.BytesIO(b""),
    )


class _FakeResponse:
    """Minimal stand-in for an HTTPResponse opened by urlopen()."""

    def __init__(self, body: bytes = b"{}"):
        self._body = body
        self.headers = Message()

    def read(self, n: int | None = None) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class RetryUrlopenRetryableStatusTests(unittest.TestCase):
    """The five retryable HTTP statuses should retry-and-recover."""

    def _request(self) -> urllib.request.Request:
        import urllib.request as r
        return r.Request("https://example.test/x")

    def test_429_retried_then_succeeds(self):
        sleeps: list[float] = []
        responses = [_http_error(429), _FakeResponse(b'{"ok": true}')]
        with patch("urllib.request.urlopen", side_effect=responses):
            resp = retry_urlopen(
                self._request(), timeout=TIMEOUT_FAST,
                sleep=sleeps.append,
            )
            self.assertEqual(resp.read(), b'{"ok": true}')
        self.assertEqual(len(sleeps), 1)  # one backoff between attempts

    def test_503_retried_then_succeeds(self):
        sleeps: list[float] = []
        responses = [_http_error(503), _http_error(503), _FakeResponse()]
        with patch("urllib.request.urlopen", side_effect=responses):
            retry_urlopen(
                self._request(), timeout=TIMEOUT_SLOW,
                sleep=sleeps.append,
            )
        self.assertEqual(len(sleeps), 2)

    def test_502_504_retried(self):
        for code in (502, 504):
            sleeps: list[float] = []
            with patch(
                "urllib.request.urlopen",
                side_effect=[_http_error(code), _FakeResponse()],
            ):
                retry_urlopen(
                    self._request(), timeout=TIMEOUT_FAST,
                    sleep=sleeps.append,
                )
            self.assertEqual(len(sleeps), 1, f"{code} should retry once")


class RetryUrlopenNonRetryableTests(unittest.TestCase):
    """Hard 4xx/5xx must propagate immediately without sleeping."""

    def _request(self) -> urllib.request.Request:
        import urllib.request as r
        return r.Request("https://example.test/x")

    def test_404_propagates_immediately(self):
        sleeps: list[float] = []
        with patch("urllib.request.urlopen", side_effect=_http_error(404)):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                retry_urlopen(
                    self._request(), timeout=TIMEOUT_FAST,
                    sleep=sleeps.append,
                )
            self.assertEqual(ctx.exception.code, 404)
        self.assertEqual(sleeps, [], "must not sleep on a hard error")

    def test_401_propagates_immediately(self):
        with patch("urllib.request.urlopen", side_effect=_http_error(401)):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                retry_urlopen(
                    self._request(), timeout=TIMEOUT_FAST,
                    sleep=lambda _s: None,
                )
            self.assertEqual(ctx.exception.code, 401)
            # A hard 401 is not the RetryableHTTPError marker — it's
            # the original exception, untouched.
            self.assertNotIsInstance(ctx.exception, RetryableHTTPError)


class RetryUrlopenExhaustionTests(unittest.TestCase):
    def _request(self) -> urllib.request.Request:
        import urllib.request as r
        return r.Request("https://example.test/x")

    def test_exhausted_retries_raise_retryable_marker(self):
        sleeps: list[float] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=[_http_error(503)] * 3,
        ):
            with self.assertRaises(RetryableHTTPError) as ctx:
                retry_urlopen(
                    self._request(), timeout=TIMEOUT_FAST,
                    max_attempts=3, sleep=sleeps.append,
                )
            self.assertEqual(ctx.exception.code, 503)
            self.assertIn("after 3 attempts", str(ctx.exception))
        # One fewer sleep than attempts: no sleep after the final failure.
        self.assertEqual(len(sleeps), 2)

    def test_url_error_retried_then_raised(self):
        sleeps: list[float] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with self.assertRaises(urllib.error.URLError):
                retry_urlopen(
                    self._request(), timeout=TIMEOUT_FAST,
                    max_attempts=3, sleep=sleeps.append,
                )
        self.assertEqual(len(sleeps), 2)


class RetryAfterHeaderTests(unittest.TestCase):
    def _request(self) -> urllib.request.Request:
        import urllib.request as r
        return r.Request("https://example.test/x")

    def test_retry_after_honoured(self):
        sleeps: list[float] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=[_http_error(429, retry_after="3"), _FakeResponse()],
        ):
            retry_urlopen(
                self._request(), timeout=TIMEOUT_FAST,
                sleep=sleeps.append,
            )
        self.assertEqual(sleeps, [3.0])

    def test_retry_after_capped_at_30s(self):
        sleeps: list[float] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _http_error(429, retry_after="99999"),
                _FakeResponse(),
            ],
        ):
            retry_urlopen(
                self._request(), timeout=TIMEOUT_FAST,
                sleep=sleeps.append,
            )
        # Capped at _MAX_RETRY_AFTER_SECONDS = 30.
        self.assertEqual(sleeps, [30.0])

    def test_backoff_capped_at_8s(self):
        # base_backoff * 2**attempt grows fast; the cap must kick in.
        sleeps: list[float] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=[_http_error(503)] * 4,
        ):
            with self.assertRaises(RetryableHTTPError):
                retry_urlopen(
                    self._request(), timeout=TIMEOUT_FAST,
                    max_attempts=4, base_backoff=10.0,
                    sleep=sleeps.append,
                )
        # Every backoff should be the cap (8.0), not 10/20/40.
        self.assertTrue(all(s == 8.0 for s in sleeps), sleeps)


class HttpHelperTests(unittest.TestCase):
    def test_user_agent_format(self):
        ua = user_agent("test-component")
        self.assertTrue(ua.startswith("cannavec-test-component/"))

    def test_crossref_contact_none_when_unset(self):
        # The default env (in CI) has no CANNAVEC_CROSSREF_MAILTO set.
        with patch.dict("os.environ", {}, clear=False):
            import os as _os
            _os.environ.pop("CANNAVEC_CROSSREF_MAILTO", None)
            self.assertIsNone(crossref_contact())

    def test_crossref_contact_returns_env_when_set(self):
        with patch.dict(
            "os.environ",
            {"CANNAVEC_CROSSREF_MAILTO": "ops@example.org"},
            clear=False,
        ):
            self.assertEqual(crossref_contact(), "ops@example.org")


if __name__ == "__main__":
    unittest.main()
