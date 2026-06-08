"""Citation-lossless reference export — the deterministic core of /cv:cite
(spec 033).

``render_citation_export(answer, fmt)`` is the §XI guarantee made mechanical for
an output skill: it serializes the verified citations behind a composed Answer
into BibTeX / RIS / CSL-JSON, but ONLY if every primary-source identifier and
every GRADE label survives (``assert_citation_lossless``) — otherwise it refuses
(returns ``None``). It exports nothing for a refusal or for an Answer with no
graded claims (an uncurated-indication "no curated efficacy" brief carries the
compound monograph's cross-cutting citations, which are reference context, not
evidence for the asked question — exporting them would be the citation->claim
leak this project exists to prevent).

Stdlib only, offline, deterministic — positive + negative per Constitution §III.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from cannavec_science.answer import compose_answer
from cannavec_science.export import render_citation_export

_FORMATS = ("bibtex", "ris", "csljson")


class CuratedAnswerExportsLossless(unittest.TestCase):
    """A curated efficacy brief exports a citation-lossless reference set in
    every format — every PMID and the GRADE label survive."""

    def test_dravet_exports_with_pmid_and_grade_in_every_format(self):
        a = compose_answer("CBD for Dravet")
        for fmt in _FORMATS:
            with self.subTest(fmt=fmt):
                out = render_citation_export(a, fmt)
                self.assertIsNotNone(out, f"{fmt} export was refused")
                self.assertIn(
                    "28538134", out,
                    f"Devinsky 2017 PMID dropped from {fmt} export",
                )
                self.assertIn(
                    "Level B", out,
                    f"GRADE label dropped from {fmt} export",
                )

    def test_csljson_export_is_valid_json(self):
        a = compose_answer("CBD for Dravet")
        out = render_citation_export(a, "csljson")
        parsed = json.loads(out)
        self.assertIsInstance(parsed, list)
        self.assertTrue(any(e.get("PMID") == "28538134" for e in parsed))


class RefusalAndEmptyExportNothing(unittest.TestCase):
    """Refusals and no-graded-evidence briefs export nothing (§I / §V) — never
    a misleading reference set."""

    def test_safety_refusal_exports_nothing(self):
        a = compose_answer("How much CBD should I take for my anxiety?")
        self.assertTrue(a.is_refusal)
        for fmt in _FORMATS:
            with self.subTest(fmt=fmt):
                self.assertIsNone(render_citation_export(a, fmt))

    def test_uncurated_indication_exports_nothing(self):
        # 0 graded claims, but the CBD monograph leaves cross-cutting citations
        # attached — those must NOT be exported as evidence for diabetes.
        a = compose_answer("CBD for diabetes")
        self.assertEqual(len(a.claims), 0)
        self.assertGreater(len(a.citations), 0)
        for fmt in _FORMATS:
            with self.subTest(fmt=fmt):
                self.assertIsNone(
                    render_citation_export(a, fmt),
                    "exported a reference set for an uncurated indication",
                )


class LossyRenderIsRefused(unittest.TestCase):
    """The lossless gate is wired: a render that drops an identifier is refused
    even though the Answer itself is exportable."""

    def test_render_dropping_a_pmid_is_refused(self):
        a = compose_answer("CBD for Dravet")
        # A render that preserves no identifiers cannot be citation-lossless.
        lossy = "@article{x,\n  title = {redacted},\n}\n"
        with patch("cannavec_science.bibliography.render", return_value=lossy):
            self.assertIsNone(render_citation_export(a, "bibtex"))


if __name__ == "__main__":
    unittest.main()
