"""Centralised HTTP discipline: timeouts, polite headers, retry + backoff.

Stdlib only (``urllib`` + ``time``). Every discoverer and verifier routes
through this module so the project has a single tunable for HTTP
behaviour. Behaviour preserved by default — discoverers that previously
called ``urllib.request.urlopen(req, timeout=N)`` now call
:func:`retry_urlopen` with the same timeout; transient 429 / 500 / 502 /
503 / 504 / URLError responses trigger bounded exponential backoff before
re-raising. :func:`retry_fetch` extends this to the body read so a
``socket.timeout`` during ``resp.read()`` is retried too.

Public surface
--------------

- :data:`TIMEOUT_FAST` / :data:`TIMEOUT_SLOW` — single source of truth
  for the previously duplicated ``_DEFAULT_TIMEOUT`` constants.
- :func:`user_agent` — polite ``cannavec-<component>/<version>`` UA.
- :func:`crossref_contact` — read operator mailto from
  ``CANNAVEC_CROSSREF_MAILTO`` (returns ``None`` if unset; we send no
  mailto rather than a fake one).
- :func:`retry_urlopen` — drop-in replacement for
  ``urllib.request.urlopen`` that retries on transient failures.
- :class:`RetryableHTTPError` — marker subclass surfaced when retries
  are exhausted, so callers can distinguish "the upstream stayed broken
  through N attempts" from "the upstream returned a hard 4xx".
"""

from __future__ import annotations

import os
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cannavec_science import _creds

__all__ = [
    "TIMEOUT_FAST",
    "TIMEOUT_SLOW",
    "user_agent",
    "crossref_contact",
    "ncbi_api_key",
    "ncbi_email",
    "append_ncbi_auth",
    "retry_urlopen",
    "retry_fetch",
    "RetryableHTTPError",
    "NetworkError",
    "make_json_fetcher",
]


# Two tunable defaults. Discoverers pick :data:`TIMEOUT_SLOW` when the
# upstream is paginated or known to be flaky (CT.gov, OpenAlex, Europe
# PMC, GWAS Catalog, BindingDB). Everything else uses :data:`TIMEOUT_FAST`.
TIMEOUT_FAST = 10  # seconds
TIMEOUT_SLOW = 15  # seconds

# Retry on transient HTTP responses only. 4xx (other than 429) is a
# caller-side problem and must propagate immediately. 500 is a *server*
# error, not a caller-side fault — every upstream this tool talks to is a
# public, free research API (NCBI E-utilities especially) that emits
# transient 500s under load, so it belongs with the other retryable 5xx.
# (501/505 stay non-retryable: those are permanent "not implemented".)
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Hard ceiling on any single backoff sleep — protects against a hostile
# or buggy upstream sending Retry-After: 86400.
_MAX_BACKOFF_SECONDS = 8.0
_MAX_RETRY_AFTER_SECONDS = 30.0


def user_agent(component: str) -> str:
    """Polite ``User-Agent`` string for a given component.

    ``component`` is the short lane name (e.g. ``"chembl-discover"``,
    ``"pubmed-verify"``). The returned string follows the format
    ``cannavec-<component>/<version>``; if the version cannot be
    resolved (e.g. import cycle at build time) it falls back to
    ``"unknown"`` rather than raising.
    """
    try:
        import cannavec  # noqa: WPS433 — local import to dodge cycles
        version = getattr(cannavec, "__version__", "unknown")
    except Exception:  # noqa: BLE001 — never let a UA failure block IO
        version = "unknown"
    return f"cannavec-{component}/{version}"


def crossref_contact() -> str | None:
    """Operator mailto for Crossref's polite-pool calls.

    Returns the value of ``CANNAVEC_CROSSREF_MAILTO`` or ``None``.
    Better polite-anonymous than impolitely-fake — the previous
    placeholder (``noreply@example.invalid``) violated Crossref's
    etiquette guide.
    """
    mail = os.environ.get("CANNAVEC_CROSSREF_MAILTO", "").strip()
    return mail or None


# Only NCBI E-utilities calls are authenticated; the key/email never leak to
# any other host.
_NCBI_EUTILS_HOST = "eutils.ncbi.nlm.nih.gov"


def ncbi_api_key() -> str | None:
    """Operator's NCBI E-utilities API key from ``NCBI_API_KEY``.

    A key raises the E-utilities rate limit from 3 → 10 requests/second and
    identifies the caller, so NCBI is far less likely to refuse a shared
    cloud-egress IP (the production fix for the ``403 Forbidden`` seen from a
    locked-down environment). Returns ``None`` when unset — in which case the
    request is sent unauthenticated, exactly as before, so offline tests and
    key-less deployments are unaffected.
    """
    return _creds.resolve("NCBI_API_KEY")


def ncbi_email() -> str | None:
    """Operator contact e-mail from ``NCBI_EMAIL`` (NCBI etiquette). Optional."""
    return _creds.resolve("NCBI_EMAIL")


def append_ncbi_auth(url: str) -> str:
    """Return ``url`` with NCBI ``api_key`` (and ``email``) query params added.

    No-ops unless (a) a key is configured AND (b) the URL targets the NCBI
    E-utilities host — so the credential is never appended to Crossref,
    ChEMBL, CT.gov, or any other source. Idempotent: an already-present
    ``api_key`` is left untouched.
    """
    key = ncbi_api_key()
    if not key:
        return url
    parts = urlsplit(url)
    if parts.netloc != _NCBI_EUTILS_HOST:
        return url
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.setdefault("api_key", key)
    email = ncbi_email()
    if email:
        q.setdefault("email", email)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment)
    )


class RetryableHTTPError(urllib.error.HTTPError):
    """Raised when bounded retry exhausts without success."""


class NetworkError(Exception):
    """Raised by a live-discovery lane when a fetch fails — HTTP error, timeout,
    or JSON parse error.

    Single shared class (previously copy-pasted as ~13 identical per-lane
    ``NetworkError`` definitions). Distinct from
    :class:`cannavec_science.discover_guard.DiscoverRefused`, which the safety
    preflight raises BEFORE any network call; a NetworkError is an operational
    transport/parse problem the caller may retry or report.
    """


def make_json_fetcher(component: str, *, timeout: float = TIMEOUT_FAST):
    """Build a lane ``Fetcher`` (``url -> decoded str``) for a JSON GET endpoint.

    Replaces the per-lane ``default_<lane>_fetcher`` boilerplate — polite
    ``User-Agent`` + ``Accept: application/json`` + bounded-retry ``urlopen`` +
    UTF-8 decode — that was copy-pasted across ~11 discovery lanes differing only
    by ``component`` (the UA suffix, e.g. ``"chembl-discover"``) and ``timeout``.
    The returned fetcher accepts the single ``url`` argument the injected-fetcher
    test seam expects. Lanes that POST a body (rcsb, opentargets), send a custom
    mailto-aware UA, or decode leniently (europepmc, openalex) keep their own
    fetcher.
    """
    ua = user_agent(component)

    def _fetch(url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": ua, "Accept": "application/json"},
        )
        with retry_urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")

    return _fetch


def retry_urlopen(
    req: urllib.request.Request,
    *,
    timeout: float,
    max_attempts: int = 3,
    base_backoff: float = 0.5,
    sleep=None,
):
    """Open ``req`` with bounded retry+backoff on transient failures.

    Returns the open ``HTTPResponse``. The caller is responsible for the
    response lifecycle — use it inside a ``with`` block or call
    ``.close()`` explicitly.

    Retries on HTTP 429 / 502 / 503 / 504 and on
    :class:`urllib.error.URLError` (DNS failure, connection refused,
    TCP reset, read timeout). Non-transient HTTP errors (404, 401, 403,
    500, ...) propagate unchanged. The ``Retry-After`` header is
    honoured on 429 responses, capped at
    :data:`_MAX_RETRY_AFTER_SECONDS` to defeat a misbehaving upstream.
    Between retries the function sleeps
    ``min(base_backoff * 2**attempt, 8.0)`` seconds.

    Tests inject ``sleep`` to skip the real ``time.sleep`` call. The
    function never sleeps before the first attempt.
    """
    _sleep = sleep or time.sleep
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in _RETRYABLE_STATUSES:
                raise
            if attempt == max_attempts - 1:
                raise RetryableHTTPError(
                    url=getattr(exc, "url", req.full_url),
                    code=exc.code,
                    msg=f"transient HTTP {exc.code} after {max_attempts} attempts",
                    hdrs=exc.headers,
                    fp=None,
                ) from exc
            delay = (
                _retry_after_delay(exc)
                or min(base_backoff * (2 ** attempt), _MAX_BACKOFF_SECONDS)
            )
            _sleep(delay)
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                raise
            _sleep(min(base_backoff * (2 ** attempt), _MAX_BACKOFF_SECONDS))
    # The loop above always returns or raises before this point.
    assert last_exc is not None  # pragma: no cover — defensive
    raise last_exc  # pragma: no cover


def retry_fetch(
    req: urllib.request.Request,
    *,
    timeout: float,
    max_attempts: int = 3,
    base_backoff: float = 0.5,
    sleep=None,
) -> tuple[bytes, str | None]:
    """Open ``req``, read the whole body, and return ``(body, charset)``.

    The crucial difference from :func:`retry_urlopen`: the body ``read()``
    happens **inside** the retry loop, so a body-read timeout
    (``socket.timeout`` — "The read operation timed out", which NCBI
    E-utilities throws routinely when its shared-IP rate limit is hit) is
    retried instead of escaping as a permanent failure. ``retry_urlopen``
    only wraps the ``urlopen`` handshake; the caller's later ``resp.read()``
    is outside its protection.

    Retries on the same transient HTTP statuses as :func:`retry_urlopen`
    (429 / 500 / 502 / 503 / 504), on :class:`urllib.error.URLError`, and on
    ``socket.timeout`` raised during the read. Non-transient HTTP errors
    (404, 401, 403, …) propagate immediately. Backoff and ``Retry-After``
    handling are identical to :func:`retry_urlopen`. ``charset`` is the
    response's declared content charset (``None`` if absent), so the caller
    can decode exactly as before.

    Tests inject ``sleep`` to skip the real ``time.sleep``.
    """
    _sleep = sleep or time.sleep
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                charset = resp.headers.get_content_charset()
            return body, charset
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE_STATUSES:
                raise
            if attempt == max_attempts - 1:
                raise RetryableHTTPError(
                    url=getattr(exc, "url", req.full_url),
                    code=exc.code,
                    msg=f"transient HTTP {exc.code} after {max_attempts} attempts",
                    hdrs=exc.headers,
                    fp=None,
                ) from exc
            delay = (
                _retry_after_delay(exc)
                or min(base_backoff * (2 ** attempt), _MAX_BACKOFF_SECONDS)
            )
            _sleep(delay)
        except (urllib.error.URLError, socket.timeout) as exc:
            # socket.timeout is an alias of TimeoutError on 3.10+; on 3.9 it
            # is a distinct OSError subclass — naming it covers both. A read
            # timeout is the body-read failure retry_urlopen cannot see.
            if attempt == max_attempts - 1:
                raise
            _sleep(min(base_backoff * (2 ** attempt), _MAX_BACKOFF_SECONDS))
    raise AssertionError("unreachable")  # pragma: no cover — defensive


def _retry_after_delay(exc: urllib.error.HTTPError) -> float | None:
    """Best-effort ``Retry-After`` parser; ``None`` if header is absent/odd."""
    header = exc.headers.get("Retry-After") if exc.headers else None
    if not header:
        return None
    raw = header.strip()
    if raw.isdigit():
        return min(float(raw), _MAX_RETRY_AFTER_SECONDS)
    return None
