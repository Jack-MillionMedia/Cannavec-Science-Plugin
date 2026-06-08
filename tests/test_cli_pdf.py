"""The ``pdf`` CLI subcommand (the surface /cv:pdf drives).

Exercises the command end-to-end with ``--html-only`` so the suite stays fast and
fully offline (no Chrome subprocess): a curated question writes a citation-lossless
HTML brief and exits 0; a refusal and an uncurated indication each render an honest
artifact (exit 0, no fabricated evidence); the documented subcommand surface stays
in lockstep with argparse.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.__main__ import main, _build_parser
from cannavec_science.answer import compose_answer
from cannavec_science.export import assert_citation_lossless, export_provenance


def _run(argv: list) -> int:
    """Invoke the CLI, swallowing its stdout/stderr so the suite stays quiet."""
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class TestPdfCli(unittest.TestCase):
    def test_curated_question_writes_lossless_html(self) -> None:
        a = compose_answer("CBD evidence in Dravet syndrome")
        with tempfile.TemporaryDirectory() as d:
            prefix = str(Path(d) / "brief")
            rc = _run(["pdf", "CBD evidence in Dravet syndrome",
                       "--out", prefix, "--html-only"])
            self.assertEqual(rc, 0)
            html_path = Path(prefix + ".html")
            self.assertTrue(html_path.exists())
            doc = html_path.read_text("utf-8")
            self.assertTrue(assert_citation_lossless(a, doc).ok)
            for atom in export_provenance(a):
                self.assertIn(atom.raw_id, doc)

    def test_refusal_renders_honest_artifact_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            prefix = str(Path(d) / "refusal")
            rc = _run(["pdf", "How much CBD should I take for my anxiety every day?",
                       "--out", prefix, "--html-only"])
            self.assertEqual(rc, 0)
            doc = Path(prefix + ".html").read_text("utf-8")
            self.assertIn("Refusal", doc)
            self.assertNotIn("<h2>References</h2>", doc)

    def test_uncurated_indication_is_honest_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            prefix = str(Path(d) / "diabetes")
            rc = _run(["pdf", "CBD for diabetes", "--out", prefix, "--html-only"])
            self.assertEqual(rc, 0)
            doc = Path(prefix + ".html").read_text("utf-8")
            self.assertIn("No curated efficacy evidence", doc)

    def test_default_out_prefix_is_derived_from_question(self) -> None:
        from cannavec_science.__main__ import _pdf_slug
        slug = _pdf_slug("CBD evidence in Dravet syndrome?")
        self.assertTrue(slug.startswith("cannavec-"))
        self.assertNotRegex(slug, r"[^a-z0-9-]")

    def test_pdf_is_a_registered_subcommand(self) -> None:
        parser = _build_parser()
        choices: set[str] = set()
        for action in parser._actions:
            if isinstance(action, argparse_subparsers_type()):
                choices.update(action.choices.keys())
        self.assertIn("pdf", choices)


def argparse_subparsers_type():
    import argparse
    return argparse._SubParsersAction


if __name__ == "__main__":
    unittest.main()
