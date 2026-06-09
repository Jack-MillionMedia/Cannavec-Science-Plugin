"""RED guardrails for the Phase-2 §XI graded-live-finding contract (FAIL now).

Phase 2 graduates a live finding from a bare "provisional (live, unverified)"
label to one that can carry a real, conservative single-source GRADE / certainty
(e.g. a peer-reviewed live PubMed hit graded Level C). The moment a finding
carries a grade, that grade becomes part of the §XI evidence surface and MUST be
held to the same citation-lossless + no-inflation guarantee as a curated claim:

- A graded live finding's identifier AND grade SURVIVE a render losslessly
  (``assert_render_faithful`` does not raise).
- FORGING that grade upward in the rendered HTML is REFUSED
  (``assert_render_faithful`` raises ``FaithfulnessError``).

Both fail today: ``export_provenance`` / ``assert_citation_lossless`` only see
``answer.citations`` and ``answer.claims`` — live findings sit OUTSIDE the §XI
evidence surface, so a forged live grade sails through. The later tasks must pull
graded live findings into that surface. The tests use the future field names
(``grade`` / ``certainty`` on a finding) so the implementers make them pass.

Fully offline: a graded live finding is injected via the existing stub-fetcher
augment path (``tests/test_live_discovery.py`` pattern) and then graded in place,
so no network is touched.
"""

from __future__ import annotations

import unittest

from cannavec_science import live
from cannavec_science.answer import compose_answer
from cannavec_science.pdf_export import (
    FaithfulnessError,
    assert_render_faithful,
    render_html,
)


class _FakeHit:
    """Stand-in for a searcher's LiveHit (only needs ``.to_dict()``) — the
    ``tests/test_live_discovery.py`` offline stub pattern, verbatim."""

    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _pubmed_runner(rows):
    def _runner(query, since, n):
        return rows[:n]

    return _runner


# A query the curated KB DOES cover, so the rendered Answer is a full evidence
# brief (claims + citations present) — the state where a graded live finding is
# woven alongside curated evidence and must be held to the §XI surface contract.
# Its curated evidence renders at Level C (and ONLY Level C); we deliberately give
# the live finding a DIFFERENT grade below so each assertion binds to the live
# finding's grade, never the curated one — i.e. the test cannot pass vacuously off
# a curated label that is already in the HTML.
_COVERED_Q = (
    "How does chronic cannabis use alter insulin sensitivity in "
    "metabolic syndrome?"
)

# A peer-reviewed live PubMed hit that Phase-2 grading would assign a real,
# conservative single-source grade. Its identifier becomes ``PMID 39000001`` in
# ``answer.live_findings``. The true grade is Level D — a grade the curated render
# of ``_COVERED_Q`` does NOT contain, so:
#   * "survives" genuinely needs the LIVE grade rendered (it is absent today), and
#   * the forge below (Level D -> Level A) tampers ONLY the live finding's grade,
#     never a curated citation — so a pass requires the live finding to be inside
#     the §XI surface, not the pre-existing curated-surface check.
_GRADED_LIVE_ROW = _FakeHit(
    pmid="39000001",
    title="Cannabidiol and insulin sensitivity: a single-centre cohort",
    year=2024,
)
_GRADED_LIVE_IDENT = "PMID 39000001"
_TRUE_LIVE_GRADE = "Level D"
_FORGED_LIVE_GRADE = "Level A"


def _augment_with_graded_live(answer) -> dict:
    """Weave the stub graded live row, then attach the future grade fields the
    Phase-2 grader will set (``grade`` / ``certainty``). Returns the finding dict
    so a test can locate it. Offline — runs through the injected-runner seam."""
    live.augment_answer(
        answer,
        sources=["pubmed"],
        runners={"pubmed": _pubmed_runner([_GRADED_LIVE_ROW])},
    )
    finding = next(
        (f for f in answer.live_findings if f.get("identifier") == _GRADED_LIVE_IDENT),
        None,
    )
    assert finding is not None, "stub graded live row was not woven onto the answer"
    # The future Phase-2 grade fields. Today these are inert keys on the finding
    # dict; the later tasks make the §XI surface read + enforce them.
    finding["grade"] = _TRUE_LIVE_GRADE
    finding["certainty"] = "Very low certainty"
    return finding


class GradedLiveFindingSurvivesRender(unittest.TestCase):
    def test_graded_live_finding_survives_render(self) -> None:
        a = compose_answer(_COVERED_Q)
        _augment_with_graded_live(a)

        rendered = render_html(a)
        # The finding's identifier must survive (it does today, via the
        # whole-document identifier floor) …
        self.assertIn(_GRADED_LIVE_IDENT.split()[-1], rendered)
        # … AND its real grade must be rendered beside it, losslessly. This
        # fails until the render emits the live finding's grade into the
        # §XI-checked surface.
        self.assertIn(_TRUE_LIVE_GRADE, rendered)
        # The faithfulness gate must accept the honest render. This fails until
        # graded live findings are part of the §XI provenance the gate checks.
        assert_render_faithful(a, rendered)


class ForgedInflatedLiveGradeIsRefused(unittest.TestCase):
    def test_forged_inflated_live_grade_is_refused(self) -> None:
        a = compose_answer(_COVERED_Q)
        _augment_with_graded_live(a)

        rendered = render_html(a)
        # An honest render must first contain the TRUE live grade, so the forge
        # below is a genuine upward tamper (Level C -> Level A), not a no-op.
        self.assertIn(
            _TRUE_LIVE_GRADE,
            rendered,
            "render must emit the live finding's true grade for the forge to bite",
        )

        # Forge the live finding's grade upward in the rendered HTML.
        forged = rendered.replace(_TRUE_LIVE_GRADE, _FORGED_LIVE_GRADE)
        self.assertNotEqual(
            forged, rendered, "forge did not change the HTML — true grade absent"
        )

        # The §XI gate MUST refuse the inflated render. Fails today because live
        # findings are outside the evidence surface the gate inspects.
        with self.assertRaises(FaithfulnessError):
            assert_render_faithful(a, forged)


# --------------------------------------------------------------------------- #
# A "packed" brief: TWO on-topic graded live findings with DIFFERENT grades.   #
# The inflation gate binds each GRADE label to the NEAREST identifier; when a   #
# finding's own grade renders FAR from its own id (past the title) and a        #
# sibling's id sits NEARER, the stronger finding's grade cross-binds to the     #
# weaker finding's id and the whole render is FALSELY refused. Both findings    #
# are legitimately graded (C and D) — this is a false inflation, not a real     #
# one, and the live tier must render packed, not degrade to curated-only.       #
# --------------------------------------------------------------------------- #

_PACKED_Q = "What is the evidence for cannabis in chronic pain?"


def _pubmed_graded_runner(query, since, n):
    return [
        _FakeHit(
            pmid="39000011",
            title="Cannabidiol for chronic pain: a randomized controlled trial",
            year="2023",
            retraction_status="clean",
            journal="PAIN",
            pubtypes=("Randomized Controlled Trial",),
            abstract="",
        )
    ][:n]


def _biorxiv_graded_runner(query, since, n):
    return [
        _FakeHit(
            doi="10.1101/2024.01.01.000001",
            title="Cannabidiol for chronic pain: a preprint",
            first_author="Doe",
            year="2024",
            server="biorxiv",
            retraction_status="clean",
            abstract="",
        )
    ][:n]


def _augment_two_graded_live(answer):
    """Weave two on-topic live findings (a graded PMID + a graded preprint DOI)
    through the offline injected-runner seam, returning the two finding dicts."""
    live.augment_answer(
        answer,
        sources=["pubmed", "biorxiv"],
        runners={
            "pubmed": _pubmed_graded_runner,
            "biorxiv": _biorxiv_graded_runner,
        },
    )
    pmid = next(
        (f for f in answer.live_findings if f.get("identifier") == "PMID 39000011"),
        None,
    )
    doi = next(
        (
            f
            for f in answer.live_findings
            if "10.1101/2024.01.01.000001" in (f.get("identifier") or "")
        ),
        None,
    )
    assert pmid is not None, "graded PMID live row was not woven"
    assert doi is not None, "graded preprint DOI live row was not woven"
    return pmid, doi


class TwoGradedLiveFindingsRenderPacked(unittest.TestCase):
    """Regression for the false-inflation refusal of a packed multi-finding brief.

    Two on-topic graded live findings with DIFFERENT clamped grades (C and D)
    must render with BOTH identifiers AND BOTH grades present, and the §XI gate
    must NOT raise — the live tier renders packed, it does not degrade to
    curated-only because one grade's nearest id is a sibling's."""

    def test_two_graded_live_findings_render_packed_without_false_inflation(
        self,
    ) -> None:
        a = compose_answer(_PACKED_Q)
        pmid, doi = _augment_two_graded_live(a)

        # Each finding carries its OWN clamped grade; they differ (the precondition
        # that triggers the cross-binding bug).
        self.assertEqual(pmid.get("grade"), "Level C")
        self.assertEqual(doi.get("grade"), "Level D")

        rendered = render_html(a)

        # Both identifiers survive the render (the §I floor).
        self.assertIn("39000011", rendered)
        self.assertIn("10.1101/2024.01.01.000001", rendered)
        # Both grades survive — the live tier is packed, not degraded.
        self.assertIn("Level C", rendered)
        self.assertIn("Level D", rendered)
        # The honest qualifier is still visible on the live tier.
        self.assertIn("live", rendered)
        self.assertIn("provisional", rendered)

        # The §XI gate must NOT raise: both findings are legitimately graded; the
        # cross-bound "Level C" was a FALSE inflation, not a real one.
        assert_render_faithful(a, rendered)


class ForgedInflationOnOneOfTwoLiveFindingsIsRefused(unittest.TestCase):
    """The fix must not blind the gate: forging ONE of the two findings' grades
    upward (the Level-D preprint -> Level A) must still be REFUSED — a real live
    inflation is still caught."""

    def test_forged_inflation_on_live_preprint_is_refused(self) -> None:
        a = compose_answer(_PACKED_Q)
        _augment_two_graded_live(a)

        rendered = render_html(a)
        # The honest render must contain the preprint's TRUE grade so the forge is
        # a genuine upward tamper (Level D -> Level A), not a no-op.
        self.assertIn("Level D", rendered)

        forged = rendered.replace("Level D", "Level A")
        self.assertNotEqual(forged, rendered, "forge did not change the HTML")

        with self.assertRaises(FaithfulnessError):
            assert_render_faithful(a, forged)


if __name__ == "__main__":
    unittest.main()
