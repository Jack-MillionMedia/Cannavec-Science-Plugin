"""Transparency: a brief-level notice when the live frontier is unavailable/empty.

``/cv:pdf`` augments the curated brief with live primary-source evidence by
default, degrading to curated-only when live retrieval is unavailable (offline /
firewall) or returns nothing on-topic. That degrade was only on stderr — the
rendered artifact gave no hint why the live section was absent. These tests pin a
small, factual render-only notice (``Answer.live_retrieval_note``) that surfaces
the reason IN the brief, in BOTH the Markdown and the PDF/HTML renders.

The note is render-only UX text, never a grade and never evidence:
- it must carry no "Level X" / certainty word (so the §XI gate never reads it),
- it must pass the no-system-language guard (no §/Constitution/internal framing),
- and it must not perturb the §XI faithfulness gate.

Default empty → renders nothing → non-augmented answers are unchanged.

Fully offline + deterministic (stub fetchers, network never touched).
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import live, pdf_export
from cannavec_science.__main__ import main
from cannavec_science.answer import compose_answer
from cannavec_science.pdf_export import assert_render_faithful, render_html
from tests.test_no_system_language import BANNED


# The three exact notes set by the CLI live-augment block.
_UNAVAILABLE = (
    "Live literature retrieval was unavailable — showing curated evidence "
    "only. Re-run on an open network to include the live primary-source "
    "frontier."
)
_GATE = (
    "Live evidence was retrieved but could not be safely rendered; showing "
    "curated evidence only."
)
_EMPTY = (
    "Live retrieval found no additional on-topic primary sources for this "
    "question."
)

_CURATED_Q = "CBD for chronic pain"


class _FakeHit:
    """Stand-in for a searcher's LiveHit (only needs ``.to_dict()``)."""

    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _boom_runner(query, since, n):
    """A runner that fails like an unreachable upstream."""
    raise OSError("simulated network down")


# A wrong-indication / off-topic efficacy row: a Dravet seizure trial for a
# chronic-pain query — the on-topic gate drops it, so the augment succeeds but
# leaves zero on-topic findings.
_OFFTOPIC_ROW = _FakeHit(
    pmid="28538134",
    title="Trial of cannabidiol for drug-resistant seizures in Dravet syndrome",
    year=2017,
)


def _brief_runners(pubmed_rows):
    runners = {src: (lambda q, s, n: []) for src in live.BRIEF_SOURCES}
    runners["pubmed"] = lambda q, s, n: pubmed_rows[:n]
    return runners


def _run_cli(argv: list) -> int:
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class NoteRendersInMarkdown(unittest.TestCase):
    def test_markdown_renders_note_when_set(self) -> None:
        a = compose_answer(_CURATED_Q)
        a.live_retrieval_note = _UNAVAILABLE
        md = a.to_markdown()
        self.assertIn(_UNAVAILABLE, md)

    def test_markdown_omits_note_when_empty(self) -> None:
        a = compose_answer(_CURATED_Q)
        # Default empty → nothing about a live-retrieval note in the brief.
        self.assertEqual(a.live_retrieval_note, "")
        md = a.to_markdown()
        self.assertNotIn("curated evidence only", md)
        self.assertNotIn("Live literature retrieval was unavailable", md)
        self.assertNotIn(
            "found no additional on-topic primary sources", md
        )


class NoteRendersInPdfHtml(unittest.TestCase):
    def test_html_renders_escaped_note_when_set(self) -> None:
        a = compose_answer(_CURATED_Q)
        a.live_retrieval_note = _UNAVAILABLE
        doc = render_html(a)
        # Rendered, escaped (the em dash survives; the text is present).
        self.assertIn("Live literature retrieval was unavailable", doc)

    def test_html_omits_note_when_empty(self) -> None:
        a = compose_answer(_CURATED_Q)
        doc = render_html(a)
        self.assertNotIn("curated evidence only", doc)

    def test_render_faithful_passes_with_note_present(self) -> None:
        # The note introduces no grade / inflation, so the §XI gate still passes.
        for note in (_UNAVAILABLE, _GATE, _EMPTY):
            a = compose_answer(_CURATED_Q)
            a.live_retrieval_note = note
            doc = render_html(a)
            assert_render_faithful(a, doc)  # must not raise


class NoteIsRenderOnlyUxText(unittest.TestCase):
    def test_no_note_contains_a_grade_label(self) -> None:
        # The §XI gate keys on "Level X"/certainty words. None of the notes may.
        for note in (_UNAVAILABLE, _GATE, _EMPTY):
            self.assertNotRegex(note, r"Level\s[A-E]")
            for word in ("certainty", "Level A", "Level B", "Level C",
                         "Level D", "Level E"):
                self.assertNotIn(word, note)

    def test_notes_pass_no_system_language_guard(self) -> None:
        for note in (_UNAVAILABLE, _GATE, _EMPTY):
            self.assertIsNone(BANNED.search(note))

    def test_no_system_language_in_rendered_surfaces_with_note(self) -> None:
        for note in (_UNAVAILABLE, _GATE, _EMPTY):
            a = compose_answer(_CURATED_Q)
            a.live_retrieval_note = note
            for text in (a.to_markdown(), render_html(a)):
                self.assertIsNone(BANNED.search(text))


class EvidenceSummaryUnchangedByNote(unittest.TestCase):
    def test_evidence_summary_identical_with_and_without_note(self) -> None:
        a = compose_answer(_CURATED_Q)
        before = a.to_dict()["evidence_summary"]
        a.live_retrieval_note = _UNAVAILABLE
        after = a.to_dict()["evidence_summary"]
        self.assertEqual(before, after)


class CliBranchWiring(unittest.TestCase):
    """The three live-augment branches of ``_cmd_pdf`` set the right note (or
    none), and the note (or its absence) lands in the rendered artifact."""

    def test_network_error_branch_sets_unavailable_note(self) -> None:
        import cannavec_science.live as live_mod

        original = live_mod.ALL_LANE_RUNNERS.copy()
        try:
            for src in live_mod.BRIEF_SOURCES:
                live_mod.ALL_LANE_RUNNERS[src] = _boom_runner
            with tempfile.TemporaryDirectory() as d:
                prefix = str(Path(d) / "pain")
                rc = _run_cli(["pdf", _CURATED_Q, "--out", prefix,
                               "--html-only"])
                self.assertEqual(rc, 0)
                doc = Path(prefix + ".html").read_text("utf-8")
                self.assertIn(
                    "Live literature retrieval was unavailable", doc
                )
        finally:
            live_mod.ALL_LANE_RUNNERS.clear()
            live_mod.ALL_LANE_RUNNERS.update(original)

    def test_zero_on_topic_branch_sets_empty_note(self) -> None:
        # A successful augment that returns only an OFF-topic row → the on-topic
        # gate drops it → augmented.live_findings is empty → the "no additional
        # on-topic" note is set.
        import cannavec_science.live as live_mod

        runners = _brief_runners([_OFFTOPIC_ROW])
        original = live_mod.ALL_LANE_RUNNERS.copy()
        try:
            for src in live_mod.BRIEF_SOURCES:
                live_mod.ALL_LANE_RUNNERS[src] = runners[src]
            with tempfile.TemporaryDirectory() as d:
                prefix = str(Path(d) / "pain")
                rc = _run_cli(["pdf", _CURATED_Q, "--out", prefix,
                               "--html-only"])
                self.assertEqual(rc, 0)
                doc = Path(prefix + ".html").read_text("utf-8")
                self.assertIn(
                    "found no additional on-topic primary sources", doc
                )
                # And no live section was woven (the off-topic row was dropped).
                self.assertNotIn("Live discovery", doc)
        finally:
            live_mod.ALL_LANE_RUNNERS.clear()
            live_mod.ALL_LANE_RUNNERS.update(original)

    def test_no_live_flag_sets_no_note(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            prefix = str(Path(d) / "pain")
            rc = _run_cli(["pdf", _CURATED_Q, "--out", prefix,
                           "--html-only", "--no-live"])
            self.assertEqual(rc, 0)
            doc = Path(prefix + ".html").read_text("utf-8")
            self.assertNotIn("curated evidence only", doc)
            self.assertNotIn(
                "found no additional on-topic primary sources", doc
            )


if __name__ == "__main__":
    unittest.main()
