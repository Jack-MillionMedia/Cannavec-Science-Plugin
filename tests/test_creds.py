"""Per-user credential resolution (NCBI keys etc.).

NCBI requires every user to use their OWN personal key — pooling traffic through
a shared key is prohibited — so a key must never live in shipped source. Keys are
resolved per machine/user, in precedence order: process environment → the user's
``~/.cannavec/credentials`` file (written by ``cannavec_science setup``). A local
``.env`` is bootstrapped into the environment by the CLI for developer
convenience. Stdlib only, offline, fail-safe.
"""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from cannavec_science import _creds


class _EnvSandbox:
    """Save/restore specific env vars around a test."""

    def __init__(self, *names):
        self._names = names
        self._saved = {}

    def __enter__(self):
        for n in self._names:
            self._saved[n] = os.environ.get(n)
            os.environ.pop(n, None)
        return self

    def __exit__(self, *_a):
        for n, v in self._saved.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v


class Resolve(unittest.TestCase):
    def test_env_takes_precedence_over_file(self):
        with _EnvSandbox("NCBI_API_KEY"), tempfile.TemporaryDirectory() as d:
            p = Path(d) / "credentials"
            _creds.save_credentials({"NCBI_API_KEY": "from-file"}, path=p)
            os.environ["NCBI_API_KEY"] = "from-env"
            self.assertEqual(_creds.resolve("NCBI_API_KEY", path=p), "from-env")

    def test_file_fallback_when_env_unset(self):
        with _EnvSandbox("NCBI_API_KEY"), tempfile.TemporaryDirectory() as d:
            p = Path(d) / "credentials"
            _creds.save_credentials({"NCBI_API_KEY": "from-file"}, path=p)
            self.assertEqual(_creds.resolve("NCBI_API_KEY", path=p), "from-file")

    def test_none_when_neither(self):
        with _EnvSandbox("NCBI_API_KEY"), tempfile.TemporaryDirectory() as d:
            p = Path(d) / "credentials"  # does not exist
            self.assertIsNone(_creds.resolve("NCBI_API_KEY", path=p))


class DotenvParsing(unittest.TestCase):
    def test_parses_keys_quotes_comments_and_export(self):
        text = (
            "# a comment\n"
            "\n"
            "NCBI_API_KEY=abc123\n"
            'NCBI_EMAIL="me@example.org"\n'
            "export OTHER='spaces ok'\n"
            "MALFORMED_LINE_NO_EQUALS\n"
        )
        got = _creds.parse_env_text(text)
        self.assertEqual(got["NCBI_API_KEY"], "abc123")
        self.assertEqual(got["NCBI_EMAIL"], "me@example.org")
        self.assertEqual(got["OTHER"], "spaces ok")
        self.assertNotIn("MALFORMED_LINE_NO_EQUALS", got)

    def test_load_dotenv_sets_unset_only_and_is_failsafe(self):
        with _EnvSandbox("NCBI_API_KEY", "NCBI_EMAIL"), tempfile.TemporaryDirectory() as d:
            os.environ["NCBI_API_KEY"] = "already-set"
            p = Path(d) / ".env"
            p.write_text("NCBI_API_KEY=should-not-override\nNCBI_EMAIL=set-me@x.org\n")
            n = _creds.load_dotenv(p)
            self.assertEqual(os.environ["NCBI_API_KEY"], "already-set")  # not overridden
            self.assertEqual(os.environ["NCBI_EMAIL"], "set-me@x.org")   # newly set
            self.assertGreaterEqual(n, 1)
            # Missing file is a clean no-op.
            self.assertEqual(_creds.load_dotenv(Path(d) / "nope.env"), 0)


class SaveCredentials(unittest.TestCase):
    def test_round_trip_and_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "credentials"
            _creds.save_credentials({"NCBI_API_KEY": "k", "NCBI_EMAIL": "e@x.org"}, path=p)
            self.assertTrue(p.exists())
            mode = stat.S_IMODE(p.stat().st_mode)
            self.assertEqual(mode, 0o600, f"credentials file must be owner-only, got {oct(mode)}")
            self.assertEqual(_creds.parse_env_text(p.read_text())["NCBI_API_KEY"], "k")


if __name__ == "__main__":
    unittest.main()
