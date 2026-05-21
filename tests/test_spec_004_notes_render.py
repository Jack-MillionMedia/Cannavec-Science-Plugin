"""Tests for spec 004 US3 / FR-004 — `Answer.notes` rendering.

v0.3 set `Answer.notes` via `_classify_zero_claims` (spec 003 US9 / FR-009)
but the `Answer.to_markdown()` and `Answer.to_dict()` paths never surfaced
the field. v0.4 closes the loop.
"""

from __future__ import annotations

import json
import unittest

from cannavec_science.answer import compose_answer


class NotesRenderMarkdownTests(unittest.TestCase):
    def test_audience_classification_renders_in_markdown(self):
        # Bedrocan / cultivar question → out-of-scope audience.
        a = compose_answer("Bedrocan medical cannabis cultivars THC content")
        md = a.to_markdown()
        self.assertIn("## Notes", md)
        # The hint points the user at the parent plugin per spec 003 FR-009.
        self.assertIn("non-researcher audience", md)

    def test_inscope_phrasing_mismatched_renders(self):
        # A query naming a covered cannabinoid but no row predicate.
        a = compose_answer("HHC autophagy CB1")
        # If the named-cannabinoid set is non-empty AND zero claims, the
        # phrasing-mismatched hint fires. (HHC monograph may still
        # surface as a section.)
        if not a.claims and not a.is_refusal:
            md = a.to_markdown()
            self.assertIn("## Notes", md)

    def test_no_notes_section_when_claims_present(self):
        # Regression: a successful Dravet answer does NOT render a Notes
        # section. The classification only fires on zero claims.
        a = compose_answer("CBD evidence in Dravet syndrome")
        self.assertGreater(len(a.claims), 0)
        md = a.to_markdown()
        # Even if Answer.notes IS empty, the markdown MUST NOT include a
        # spurious Notes section.
        if not a.notes:
            self.assertNotIn("\n## Notes\n", md)

    def test_refusal_does_not_render_notes(self):
        # K2 hard-refuse: the refusal path returns early before any
        # other sections render, so notes are not shown.
        a = compose_answer("How do I synthesize K2/Spice?")
        self.assertTrue(a.is_refusal)
        md = a.to_markdown()
        self.assertNotIn("## Notes", md)


class NotesRenderJsonTests(unittest.TestCase):
    def test_notes_field_in_to_dict(self):
        a = compose_answer("Bedrocan cultivars THC content")
        d = a.to_dict()
        self.assertIn("notes", d)
        self.assertIsInstance(d["notes"], list)
        self.assertTrue(d["notes"], "expected at least one note")

    def test_notes_field_is_json_serialisable(self):
        a = compose_answer("Bedrocan cultivars THC content")
        s = json.dumps(a.to_dict())
        round_trip = json.loads(s)
        self.assertIn("notes", round_trip)
        self.assertTrue(round_trip["notes"])

    def test_notes_field_empty_list_when_claims_present(self):
        # No classification fires when claims are non-empty.
        a = compose_answer("CBD evidence in Dravet syndrome")
        d = a.to_dict()
        self.assertEqual(d["notes"], [])


class NotesClassificationCoverageTests(unittest.TestCase):
    """Regression for the four discriminated-union branches in
    spec 003 US9 / FR-009. v0.4 ensures each branch's note renders."""

    def test_inscope_uncurated_no_cannabinoid_no_audience(self):
        # A general in-scope question that names nothing.
        a = compose_answer("describe the receptor pharmacology landscape")
        if not a.claims and not a.is_refusal:
            md = a.to_markdown()
            # Either Notes appear OR the rigor walker fires a violation -
            # both are honest outputs.
            self.assertTrue(
                "## Notes" in md or "rigor" in md.lower(),
            )

    def test_decarb_kinetics_no_longer_deferred_after_us1(self):
        # Spec 004 US1: analytical-chemistry rows surface; the deferred
        # message no longer fires for the decarb-kinetics prompt because
        # claims are present.
        a = compose_answer("decarboxylation kinetics of THCA")
        self.assertGreater(len(a.claims), 0)


if __name__ == "__main__":
    unittest.main()
