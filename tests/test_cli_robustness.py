"""A user must NEVER see a raw Python traceback from the CLI — adversarial or
empty input degrades to a clean ``[error] …`` message and a non-zero exit. The
top-level handler in ``main`` is the backstop for any unexpected error; the
per-command guards give friendlier messages. Offline + deterministic."""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

import cannavec_science.__main__ as cli


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(argv)
    return rc, out.getvalue() + err.getvalue()


class CliNeverTracebacks(unittest.TestCase):
    def test_discover_empty_query_is_clean_error(self):
        rc, text = _run(["discover", ""])
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Traceback", text)

    def test_discover_whitespace_query_is_clean_error(self):
        rc, text = _run(["discover", "   "])
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Traceback", text)

    def test_unexpected_command_error_is_caught_at_the_boundary(self):
        # An unexpected failure in any command must surface as a clean message,
        # not a traceback — the CLI boundary is the backstop.
        orig = cli._cmd_rigor

        def _boom(_args):
            raise RuntimeError("boom-sentinel-xyz")

        cli._cmd_rigor = _boom
        os.environ.pop("CANNAVEC_DEBUG", None)
        try:
            rc, text = _run(["rigor", "anything"])
        finally:
            cli._cmd_rigor = orig
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Traceback", text)
        self.assertIn("boom-sentinel-xyz", text)  # the message IS surfaced

    def test_debug_env_re_raises_for_developers(self):
        orig = cli._cmd_rigor

        def _boom(_args):
            raise RuntimeError("dev-trace")

        cli._cmd_rigor = _boom
        os.environ["CANNAVEC_DEBUG"] = "1"
        try:
            with self.assertRaises(RuntimeError):
                cli.main(["rigor", "anything"])
        finally:
            cli._cmd_rigor = orig
            os.environ.pop("CANNAVEC_DEBUG", None)


if __name__ == "__main__":
    unittest.main()
