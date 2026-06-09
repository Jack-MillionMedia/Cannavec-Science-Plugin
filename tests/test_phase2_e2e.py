"""Phase-2 "live comprehensiveness" end-to-end smoke (spec 036, Task 7).

This is the one test that exercises the whole Phase-2 spine through a single
augment → render path, offline with stub fetchers, on a CURATED indication
("CBD for chronic pain"). It pins, in one flow, that breadth is delivered WITHOUT
lowering the evidence floor:

- the on-topic CBD/pain live row survives, graded conservatively (≤ Level C),
  marked ``· live · provisional`` with a non-empty grade rationale and a synthesis
  direction;
- a wrong-indication efficacy row (a Dravet seizure trial) is DROPPED by the
  on-topic gate (``on_topic_filter_applied`` True, dropped count ≥ 1) and never
  reaches the brief or the convergence verdict;
- the honest live-synthesis prose (verdict-matched, no efficacy claim) and the
  search-provenance line both render end-to-end;
- the curated ``evidence_summary`` is unchanged by the live data (a live row can
  never raise the curated grade);
- the §XI render gate (``assert_render_faithful``) accepts the honest render and
  REFUSES a forged upward inflation of the live finding's grade;
- and the ``pdf`` CLI surface (the surface ``/cv:pdf`` drives) renders a curated-
  only brief without crashing when a live lane raises a network-style error.

Fully offline + deterministic: every live lane is an injected stub fetcher
(``tests/test_live_discovery.py`` pattern); the network is never touched.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import live
from cannavec_science.__main__ import main
from cannavec_science.answer import compose_answer
from cannavec_science.evidence import EvidenceLevel
from cannavec_science.pdf_export import (
    FaithfulnessError,
    assert_render_faithful,
    render_html,
)


# ── offline stub harness (verbatim from tests/test_live_discovery.py) ─────


class _FakeHit:
    """Stand-in for a searcher's LiveHit (only needs ``.to_dict()``)."""

    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _runner(rows):
    def _r(query, since, n):
        return rows[:n]

    return _r


def _boom_runner(query, since, n):
    """A runner that fails like an unreachable upstream — the degrade probe."""
    raise OSError("simulated network down")


# A curated indication: "CBD for chronic pain" carries graded curated efficacy,
# so the brief is a full evidence brief — the state where live breadth is woven
# alongside curated evidence and held to the §XI surface contract.
_CURATED_Q = "CBD for chronic pain"

# An ON-TOPIC live row: names the query's compound (cannabidiol) AND condition
# (chronic pain). Phase-2 grading assigns it a conservative single-source grade.
_ONTOPIC_ROW = _FakeHit(
    pmid="40000001",
    title="Cannabidiol reduces chronic pain severity: a randomized controlled trial",
    journal="Pain",
    pubtypes=["Randomized Controlled Trial"],
    year=2024,
    abstract=(
        "Cannabidiol significantly reduced chronic pain scores in this trial. "
        "We enrolled 90 patients across two sites."
    ),
)
_ONTOPIC_IDENT = "PMID 40000001"

# A WRONG-INDICATION efficacy row: a Dravet seizure trial — a DIFFERENT
# indication than chronic pain. The on-topic gate must DROP it.
_DRAVET_ROW = _FakeHit(
    pmid="28538134",
    title="Trial of cannabidiol for drug-resistant seizures in Dravet syndrome",
    year=2017,
)
_DRAVET_IDENT = "PMID 28538134"


def _idents(answer) -> set:
    return {f.get("identifier") for f in answer.live_findings}


def _brief_sources_runners(pubmed_rows):
    """Inject stub runners for the ``BRIEF_SOURCES`` breadth set offline: the
    pubmed lane returns ``pubmed_rows`` (so the surviving finding's identifier is
    the deterministic ``PMID <pmid>``); every other brief lane returns nothing.
    This exercises the real BRIEF_SOURCES fan-out path the PDF uses by default,
    without the network and without cross-lane identifier ambiguity."""
    runners = {src: _runner([]) for src in live.BRIEF_SOURCES}
    runners["pubmed"] = _runner(pubmed_rows)
    return runners


def _run_cli(argv: list) -> int:
    """Invoke the CLI, swallowing stdout/stderr so the suite stays quiet."""
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class Phase2AugmentedBriefIsHonestAndComprehensive(unittest.TestCase):
    def setUp(self) -> None:
        self.a = compose_answer(_CURATED_Q)
        # The curated grade BEFORE any live augment — must be unchanged after.
        self.curated_grade = self.a.evidence_summary.highest_grade
        # Augment across the BRIEF_SOURCES breadth set with a mix of one on-topic
        # row and one wrong-indication row, fully offline.
        self.attached = live.augment_answer(
            self.a,
            sources=live.BRIEF_SOURCES,
            runners=_brief_sources_runners([_ONTOPIC_ROW, _DRAVET_ROW]),
        )

    def test_on_topic_live_finding_survives_graded_conservatively(self) -> None:
        self.assertIn(_ONTOPIC_IDENT, _idents(self.a))
        finding = next(
            f for f in self.a.live_findings if f.get("identifier") == _ONTOPIC_IDENT
        )
        # Conservative grade — never above Level C (the live clamp).
        self.assertIn("grade", finding)
        self.assertLessEqual(
            EvidenceLevel(finding["grade"]).rank, EvidenceLevel.C.rank,
            "a live finding must never be graded above Level C",
        )
        # ``· live · provisional`` qualifier + a non-empty rationale ride along.
        self.assertTrue(finding.get("provisional"))
        self.assertIn("live", finding["provisional_grade"])
        self.assertTrue(finding.get("grade_rationale", "").strip())
        # A synthesis direction was attributed (the on-topic row "reduced ...
        # significantly" → supports), sourced only from the existing attributor.
        self.assertIn(finding.get("direction"), {"supports", "refutes", "neutral"})

    def test_wrong_indication_row_is_dropped(self) -> None:
        self.assertNotIn(_DRAVET_IDENT, _idents(self.a))
        self.assertTrue(self.a.on_topic_filter_applied)
        self.assertGreaterEqual(self.a.live_findings_dropped_off_topic, 1)

    def test_live_synthesis_prose_and_provenance_render(self) -> None:
        md = self.a.to_markdown()
        # The honest synthesis prose renders end-to-end and matches the verdict
        # without asserting efficacy.
        prose = (self.a.live_synthesis or {}).get("prose")
        self.assertTrue(prose, "live synthesis must produce a prose block")
        self.assertIn(prose, md)
        for banned in ("effective", "efficacious", "proven", "cures", "works"):
            self.assertNotIn(banned, prose.lower())
        # The search-provenance line renders with real counts.
        self.assertIn("Searched", md)
        self.assertIn("on-topic", md)
        self.assertRegex(md, r"Searched \d+ live source")

    def test_curated_evidence_summary_unchanged_by_live(self) -> None:
        # A live row must NEVER raise (or lower) the curated grade.
        self.assertEqual(
            self.a.evidence_summary.highest_grade, self.curated_grade,
            "live augmentation must not touch the curated evidence_summary",
        )

    def test_render_is_faithful_and_forged_inflation_refused(self) -> None:
        html = render_html(self.a)
        # The honest render survives the §XI gate.
        assert_render_faithful(self.a, html)
        # The live finding's true grade is present, so a forge upward bites.
        true_grade = next(
            f["grade"] for f in self.a.live_findings
            if f.get("identifier") == _ONTOPIC_IDENT
        )
        self.assertIn(true_grade, html)
        forged = html.replace(true_grade, "Level A")
        self.assertTrue(forged != html, "forge did not change the HTML")
        with self.assertRaises(FaithfulnessError):
            assert_render_faithful(self.a, forged)


class Phase2PdfDegradesGracefullyOnNetworkFailure(unittest.TestCase):
    def test_pdf_renders_curated_only_when_a_live_lane_raises(self) -> None:
        # Monkeypatch the production BRIEF_SOURCES runners so the default
        # (live-by-default) ``pdf`` path hits a lane that raises a network-style
        # error. The PDF must still render the curated-only brief — never crash.
        import cannavec_science.live as live_mod

        original = live_mod.ALL_LANE_RUNNERS.copy()
        try:
            for src in live_mod.BRIEF_SOURCES:
                live_mod.ALL_LANE_RUNNERS[src] = _boom_runner
            with tempfile.TemporaryDirectory() as d:
                prefix = str(Path(d) / "pain")
                rc = _run_cli(
                    ["pdf", _CURATED_Q, "--out", prefix, "--html-only"]
                )
                self.assertEqual(rc, 0, "pdf must not crash on a live lane error")
                doc = Path(prefix + ".html").read_text("utf-8")
                # The curated brief still rendered (References present for a
                # curated indication); no live findings were woven.
                self.assertIn("<h2>References</h2>", doc)
        finally:
            live_mod.ALL_LANE_RUNNERS.clear()
            live_mod.ALL_LANE_RUNNERS.update(original)


class Phase2VerifiedImportIsCleanNoOp(unittest.TestCase):
    """The verified-tier weaver must be a CLEAN no-op when the curation flywheel
    is archived (``cannavec_science.flywheel`` is intentionally not importable in
    the shipped engine) — not a raised-and-swallowed ImportError that masks real
    errors. The verified tier stays empty and nothing is raised."""

    def test_weave_verified_findings_is_clean_no_op_when_flywheel_archived(
        self,
    ) -> None:
        from cannavec_science.answer import weave_verified_findings

        a = compose_answer(_CURATED_Q)
        # The flywheel is archived → a clean no-op: returns 0, raises nothing,
        # and leaves the verified tier empty.
        woven = weave_verified_findings(a, prompt=_CURATED_Q)
        self.assertEqual(woven, 0)
        self.assertEqual(a.verified_findings, [])

    def test_compose_with_verified_true_does_not_raise(self) -> None:
        # The ``verified=True`` compose path must not blow up with the flywheel
        # archived — it simply leaves the verified tier empty.
        a = compose_answer(_CURATED_Q, verified=True)
        self.assertEqual(a.verified_findings, [])


class Phase2NoLiveFlagYieldsCuratedOnlyBrief(unittest.TestCase):
    def test_no_live_flag_skips_augmentation(self) -> None:
        # ``--no-live`` renders the deterministic curated-only brief: identical
        # to a default render with the network unreachable, but explicit + offline.
        with tempfile.TemporaryDirectory() as d:
            prefix = str(Path(d) / "pain-nolive")
            rc = _run_cli(
                ["pdf", _CURATED_Q, "--out", prefix, "--html-only", "--no-live"]
            )
            self.assertEqual(rc, 0)
            doc = Path(prefix + ".html").read_text("utf-8")
            self.assertIn("<h2>References</h2>", doc)
            # No live-discovery section when augmentation is skipped.
            self.assertNotIn("Live discovery", doc)


if __name__ == "__main__":
    unittest.main()
