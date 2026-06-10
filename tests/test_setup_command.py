"""The `setup` operator command — store the user's OWN NCBI key, this machine
only. Offline: the live NCBI validation is monkeypatched so the test never hits
the network (and so save still works when offline / the key is unverifiable).
"""

from __future__ import annotations

import argparse
import io
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import cannavec_science.__main__ as cli
from cannavec_science import _creds


class _Sandbox:
    """Isolated CANNAVEC_HOME + clean NCBI env + patched validation."""

    def __enter__(self):
        self._tmp = tempfile.mkdtemp(prefix="cv_setup_test_")
        self._saved = {k: os.environ.get(k) for k in
                       ("CANNAVEC_HOME", "NCBI_API_KEY", "NCBI_EMAIL")}
        os.environ["CANNAVEC_HOME"] = self._tmp
        os.environ.pop("NCBI_API_KEY", None)
        os.environ.pop("NCBI_EMAIL", None)
        self._orig_validate = cli._validate_ncbi_key
        cli._validate_ncbi_key = lambda key: (True, "validation stubbed (offline test)")
        return self

    def __exit__(self, *_a):
        cli._validate_ncbi_key = self._orig_validate
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class SetupCommand(unittest.TestCase):
    def test_show_reports_not_set_then_set(self):
        with _Sandbox():
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_setup(argparse.Namespace(show=True))
            self.assertEqual(rc, 1)                       # missing key → non-zero
            self.assertIn("NOT set", out.getvalue())

            cli._cmd_setup(argparse.Namespace(
                show=False, ncbi_key="MYKEYabcdef1234", ncbi_email="me@x.org",
                force=False))
            out2 = io.StringIO()
            with redirect_stdout(out2):
                rc2 = cli._cmd_setup(argparse.Namespace(show=True))
            self.assertEqual(rc2, 0)                      # key present → zero
            self.assertIn("set (", out2.getvalue())
            self.assertNotIn("MYKEYabcdef1234", out2.getvalue())  # key is masked

    def test_save_writes_owner_only_file_and_resolves(self):
        with _Sandbox():
            with redirect_stdout(io.StringIO()):
                rc = cli._cmd_setup(argparse.Namespace(
                    show=False, ncbi_key="MYKEYabcdef1234", ncbi_email="me@x.org",
                    force=False))
            self.assertEqual(rc, 0)
            p = _creds.credentials_path()
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            self.assertEqual(_creds.resolve("NCBI_API_KEY"), "MYKEYabcdef1234")
            self.assertEqual(_creds.resolve("NCBI_EMAIL"), "me@x.org")

    def test_rejected_key_is_not_saved_without_force(self):
        with _Sandbox():
            cli._validate_ncbi_key = lambda key: (False, "NCBI rejected the key")
            with redirect_stdout(io.StringIO()):
                rc = cli._cmd_setup(argparse.Namespace(
                    show=False, ncbi_key="badkey123456", ncbi_email="",
                    cannavec_key=None, force=False))
            self.assertEqual(rc, 1)
            self.assertIsNone(_creds.resolve("NCBI_API_KEY"))  # not saved

    def test_cannavec_key_is_stored_masked_and_merges_with_ncbi(self):
        with _Sandbox():
            # Save NCBI first.
            with redirect_stdout(io.StringIO()):
                cli._cmd_setup(argparse.Namespace(
                    show=False, ncbi_key="NCBIkey123456", ncbi_email="me@x.org",
                    cannavec_key=None, force=False))
            # Then add the Cannavec key — must NOT wipe the NCBI key.
            with redirect_stdout(io.StringIO()):
                rc = cli._cmd_setup(argparse.Namespace(
                    show=False, ncbi_key=None, ncbi_email=None,
                    cannavec_key="ck_live_abcdef123456", force=False))
            self.assertEqual(rc, 0)
            self.assertEqual(_creds.resolve("NCBI_API_KEY"), "NCBIkey123456")  # preserved
            self.assertEqual(_creds.resolve("CANNAVEC_API_KEY"), "ck_live_abcdef123456")
            out = io.StringIO()
            with redirect_stdout(out):
                cli._cmd_setup(argparse.Namespace(show=True))
            text = out.getvalue()
            self.assertIn("CANNAVEC_API_KEY: set (", text)
            self.assertNotIn("ck_live_abcdef123456", text)  # masked, not leaked


if __name__ == "__main__":
    unittest.main()
