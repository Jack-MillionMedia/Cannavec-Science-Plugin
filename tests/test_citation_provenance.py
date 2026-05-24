"""Per-citation provenance-timestamp tests (Plan R4).

The Citation dataclass gained two optional fields — ``fetched_at`` and
``retraction_checked_at`` — so a researcher reading a saved Answer six
months later can tell when each citation's upstream metadata and
retraction status were last verified.

Both fields default to ``None``; renderers emit the bracketed suffix
ONLY when populated, so every existing pinned-markdown / pinned-JSON
test remains unchanged.
"""

from __future__ import annotations

import json
import unittest

from cannavec_science.answer import Answer, Citation
from cannavec_science.evidence import EvidenceLevel


def _basic_citation(**kwargs) -> Citation:
    base = dict(
        label="Devinsky et al. (2017) Cannabidiol in Dravet syndrome.",
        pmid="28538134",
        year=2017,
        grade=EvidenceLevel.A,
    )
    base.update(kwargs)
    return Citation(**base)


class CitationDefaultsTests(unittest.TestCase):
    def test_fields_default_to_none(self):
        c = _basic_citation()
        self.assertIsNone(c.fetched_at)
        self.assertIsNone(c.retraction_checked_at)

    def test_back_compat_constructor_unchanged(self):
        # The existing constructors that pass only the historical keyword
        # set must continue to succeed — frozen dataclass with new
        # defaulted fields.
        c = Citation(label="X", pmid="123")
        self.assertEqual(c.pmid, "123")
        self.assertIsNone(c.fetched_at)


class CitationMarkdownRenderTests(unittest.TestCase):
    def _answer_with(self, citation: Citation) -> Answer:
        a = Answer(prompt="x")
        a.add_citation(citation)
        return a

    def test_unpopulated_does_not_emit_suffixes(self):
        md = self._answer_with(_basic_citation()).to_markdown()
        self.assertNotIn("[fetched", md)
        self.assertNotIn("[retraction-checked", md)

    def test_fetched_at_renders_bracketed_suffix(self):
        c = _basic_citation(fetched_at="2026-05-24")
        md = self._answer_with(c).to_markdown()
        self.assertIn("[fetched 2026-05-24]", md)

    def test_retraction_checked_at_renders_bracketed_suffix(self):
        c = _basic_citation(retraction_checked_at="2026-05-24")
        md = self._answer_with(c).to_markdown()
        self.assertIn("[retraction-checked 2026-05-24]", md)

    def test_both_render_in_order(self):
        c = _basic_citation(
            fetched_at="2026-05-24",
            retraction_checked_at="2026-05-25",
        )
        md = self._answer_with(c).to_markdown()
        i_fetch = md.index("[fetched 2026-05-24]")
        i_retract = md.index("[retraction-checked 2026-05-25]")
        # fetched_at must render before retraction_checked_at — UI
        # consistency for human readers.
        self.assertLess(i_fetch, i_retract)


class CitationJSONRenderTests(unittest.TestCase):
    def _answer_with(self, citation: Citation) -> Answer:
        a = Answer(prompt="x")
        a.add_citation(citation)
        return a

    def test_unpopulated_fields_omitted_from_json(self):
        a = self._answer_with(_basic_citation())
        payload = a.to_dict()
        row = payload["citations"][0]
        # Back-compat: existing pinned-JSON consumers must not see new keys.
        self.assertNotIn("fetched_at", row)
        self.assertNotIn("retraction_checked_at", row)

    def test_populated_fields_appear_in_json(self):
        c = _basic_citation(
            fetched_at="2026-05-24T00:00:00Z",
            retraction_checked_at="2026-05-24T00:00:00Z",
        )
        a = self._answer_with(c)
        payload = a.to_dict()
        row = payload["citations"][0]
        self.assertEqual(row["fetched_at"], "2026-05-24T00:00:00Z")
        self.assertEqual(row["retraction_checked_at"], "2026-05-24T00:00:00Z")
        # And it must round-trip through json.dumps without TypeError.
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
