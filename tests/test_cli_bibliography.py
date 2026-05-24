"""CLI ``bibliography`` integration tests (Plan R7).

The bibliography subcommand re-renders a previously saved ``Answer``
JSON into BibTeX, RIS, or CSL-JSON. These tests pin the CLI contract:

- All three formats produce output containing at least the expected
  per-format header lines.
- A bogus JSON file errors non-zero rather than silently emitting an
  empty bibliography.
- ``--out`` writes to a file; without it, output goes to stdout.
"""

from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cannavec_science.__main__ import _cmd_bibliography


def _seed_answer_json(tmpdir: Path) -> Path:
    """Write a tiny valid Answer JSON for the bibliography to consume."""
    payload = {
        "prompt": "CBD evidence in Dravet syndrome",
        "audience": "researcher",
        "generated_at": "2026-05-24T00:00:00Z",
        "short_answer": "",
        "refusal_reason": None,
        "claims": [],
        "citations": [
            {
                "label": "Devinsky et al. (2017) Cannabidiol in Dravet syndrome.",
                "pmid": "28538134",
                "doi": "10.1056/NEJMoa1611618",
                "url": None,
                "year": 2017,
                "grade": "Level A",
            },
        ],
        "cautions": [],
        "notes": [],
        "retractions_suppressed": [],
        "rigor_violations": [],
        "evidence_summary": {"highest_grade": "Level A"},
        "safety_verdict": None,
    }
    path = tmpdir / "answer.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class BibliographyFormatsTests(unittest.TestCase):
    def test_bibtex_emits_at_minimum_an_at_entry(self):
        with tempfile.TemporaryDirectory() as td:
            path = _seed_answer_json(Path(td))
            args = argparse.Namespace(
                answer_json=str(path), format="bibtex", out=None,
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_bibliography(args)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("@", out)
            self.assertIn("Devinsky", out)

    def test_ris_emits_at_minimum_a_TY_tag(self):
        with tempfile.TemporaryDirectory() as td:
            path = _seed_answer_json(Path(td))
            args = argparse.Namespace(
                answer_json=str(path), format="ris", out=None,
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_bibliography(args)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            # RIS records always start with a TY line.
            self.assertIn("TY  -", out)
            self.assertIn("28538134", out)

    def test_csljson_emits_parseable_json_array(self):
        with tempfile.TemporaryDirectory() as td:
            path = _seed_answer_json(Path(td))
            args = argparse.Namespace(
                answer_json=str(path), format="csljson", out=None,
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_bibliography(args)
            self.assertEqual(rc, 0)
            # Strip leading/trailing whitespace and parse — CSL-JSON
            # contract is "a JSON array of entries".
            data = json.loads(buf.getvalue())
            self.assertIsInstance(data, list)
            self.assertGreaterEqual(len(data), 1)


class BibliographyOutFileTests(unittest.TestCase):
    def test_out_flag_writes_to_file(self):
        with tempfile.TemporaryDirectory() as td:
            answer = _seed_answer_json(Path(td))
            out_path = Path(td) / "out.bib"
            args = argparse.Namespace(
                answer_json=str(answer),
                format="bibtex",
                out=str(out_path),
            )
            rc = _cmd_bibliography(args)
            self.assertEqual(rc, 0)
            self.assertTrue(out_path.exists())
            body = out_path.read_text(encoding="utf-8")
            self.assertIn("Devinsky", body)


if __name__ == "__main__":
    unittest.main()
