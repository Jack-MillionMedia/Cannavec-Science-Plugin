"""``cite`` CLI subcommand — the runnable surface behind /cv:cite (spec 033).

Composes the offline curated Answer, renders the verified citations, and emits a
citation-lossless reference export: all three formats (BibTeX + RIS + CSL-JSON)
by default, or a single format via ``--format``; ``--out PREFIX`` writes one file
per format. Refuses (emits nothing, non-zero exit) for a refusal Answer, an
uncurated indication, or any non-lossless format.

Stdlib only, offline, deterministic — positive + negative per Constitution §III.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace

from cannavec_science.__main__ import _cmd_cite


def _args(question, fmt=None, out=None):
    return SimpleNamespace(question=question, format=fmt, out=out)


class CiteEmitsReferences(unittest.TestCase):
    def test_default_emits_all_three_sections(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = _cmd_cite(_args("CBD for Dravet"))
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("=== BibTeX ===", out)
        self.assertIn("=== RIS ===", out)
        self.assertIn("=== CSL-JSON ===", out)
        self.assertIn("28538134", out)
        self.assertIn("Level B", out)

    def test_single_format_emits_only_that_format(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = _cmd_cite(_args("CBD for Dravet", fmt="bibtex"))
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("@article", out)
        self.assertNotIn("=== RIS ===", out)
        self.assertIn("28538134", out)

    def test_out_writes_one_file_per_format(self):
        with tempfile.TemporaryDirectory() as d:
            prefix = os.path.join(d, "refs")
            err = io.StringIO()
            with redirect_stderr(err):
                rc = _cmd_cite(_args("CBD for Dravet", out=prefix))
            self.assertEqual(rc, 0)
            for ext in ("bib", "ris", "json"):
                self.assertTrue(
                    os.path.exists(f"{prefix}.{ext}"),
                    f"{ext} file not written",
                )


class CiteRefusesToFabricate(unittest.TestCase):
    def test_safety_refusal_emits_nothing_and_exits_nonzero(self):
        buf, err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            rc = _cmd_cite(_args("How much CBD should I take for my anxiety?"))
        self.assertNotEqual(rc, 0)
        self.assertEqual(buf.getvalue(), "")
        self.assertIn("no citable answer", err.getvalue())

    def test_uncurated_indication_emits_nothing_and_exits_nonzero(self):
        buf, err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            rc = _cmd_cite(_args("CBD for diabetes"))
        self.assertNotEqual(rc, 0)
        self.assertEqual(buf.getvalue(), "")
        self.assertIn("no citable answer", err.getvalue())


if __name__ == "__main__":
    unittest.main()
