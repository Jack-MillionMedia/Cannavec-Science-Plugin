"""Blended-brief tests — curated core + live breadth in one Answer.

The product promise: *one answer, not two endpoints.* ``compose_answer(live=...)``
merges the verified curated **core** (GRADE'd, retraction-checked) with the
citation-checked live **breadth** (provenance-tagged ``live_<source>``,
reranked) and the cross-source synthesis verdict (STRONG / MIXED / WEAK) into a
single brief that keeps the two tiers visibly distinct (Constitution §IX honesty
rule).

These tests pin the blend's invariants:

- the live tier never raises (or lowers) the curated GRADE (§IX no-promotion),
- curated-vs-live provenance is visibly distinct in the rendered brief,
- GRADE is inline at each curated citation (§XI),
- the synthesis verdict rides in the same brief,
- live findings are reranked (most relevant first) and retraction-checked (§VIII),
- the default (``live=None``) stays fully offline + deterministic (§X) — no
  network, no synthesis block, byte-stable curated JSON.

Fully offline: every test injects fake ``runners`` (Constitution §X).
"""

from __future__ import annotations

import unittest
from unittest import mock

from cannavec_science import live
from cannavec_science.answer import Answer, compose_answer, live_finding_from_row
from cannavec_science.evidence import EvidenceLevel
from cannavec_science.retraction import reset_to_seed


# A well-covered curated question (the endocrine registry anchors it with a
# Level-C NHANES citation), so the curated core is genuinely non-thin.
_CURATED_Q = (
    "How does chronic cannabis use alter insulin sensitivity in "
    "metabolic syndrome?"
)


class _FakeHit:
    """Stand-in for a searcher LiveHit — only needs ``.to_dict()``."""

    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _runner(rows):
    def _r(query, since, n):
        return list(rows)[:n]
    return _r


class BlendComposeTests(unittest.TestCase):
    def test_live_seam_off_by_default_stays_offline(self):
        # No ``live`` arg → no synthesis block, no live findings, and the
        # to_dict shape is unchanged (no ``live_synthesis`` key at all).
        a = compose_answer(_CURATED_Q)
        self.assertIsNone(a.live_synthesis)
        self.assertEqual(a.live_findings, [])
        self.assertNotIn("live_synthesis", a.to_dict())
        self.assertNotIn("## Live discovery", a.to_markdown())

    def test_empty_runner_mapping_is_a_noop(self):
        # Falsy ``live`` (an empty mapping) must not fan out.
        a = compose_answer(_CURATED_Q, live={})
        self.assertIsNone(a.live_synthesis)
        self.assertEqual(a.live_findings, [])

    def test_blend_weaves_curated_core_and_live_breadth(self):
        rows = [_FakeHit(pmid="40000001", title="A 2025 cohort", year=2025)]
        a = compose_answer(
            _CURATED_Q,
            live={"pubmed": _runner(rows)},
            live_sources=["pubmed"],
        )
        # Curated core intact.
        self.assertGreaterEqual(len(a.claims), 1)
        # Live breadth woven in, tagged + provisional.
        self.assertEqual(len(a.live_findings), 1)
        self.assertEqual(a.live_findings[0]["source_tag"], "live_pubmed")
        self.assertIn("provisional", a.live_findings[0]["provisional_grade"])
        # Synthesis verdict captured onto the same brief.
        self.assertIsNotNone(a.live_synthesis)
        self.assertIn("convergence", a.live_synthesis)

    def test_blend_never_changes_curated_grade(self):
        baseline = compose_answer(_CURATED_Q)
        # A live row making a huge claim must not move the curated grade.
        rows = [_FakeHit(pmid="40000002",
                         title="CBD cures everything, massive effect", year=2025)]
        blended = compose_answer(
            _CURATED_Q, live={"pubmed": _runner(rows)}, live_sources=["pubmed"],
        )
        self.assertEqual(
            blended.evidence_summary.highest_grade,
            baseline.evidence_summary.highest_grade,
        )
        # And the curated grade is a real curated level, not Unsupported.
        self.assertGreater(
            blended.evidence_summary.highest_grade.rank,
            EvidenceLevel.UNSUPPORTED.rank,
        )

    def test_refusal_short_circuits_the_blend(self):
        called = {"n": 0}

        def _spy(query, since, n):
            called["n"] += 1
            return []

        a = compose_answer(
            "Give me a step-by-step synthesis route for a K2/Spice "
            "synthetic cannabinoid at home.",
            live={"pubmed": _spy},
            live_sources=["pubmed"],
        )
        self.assertTrue(a.is_refusal)
        self.assertEqual(called["n"], 0, "no live fan-out on a refused prompt")
        self.assertIsNone(a.live_synthesis)
        self.assertEqual(a.live_findings, [])

    def test_blend_degrades_silently_when_lane_fails(self):
        def _boom(query, since, n):
            raise RuntimeError("offline")

        a = compose_answer(
            _CURATED_Q, live={"pubmed": _boom}, live_sources=["pubmed"],
        )
        # Curated brief still stands; the lane error never aborts composition.
        self.assertGreaterEqual(len(a.claims), 1)
        self.assertEqual(a.live_findings, [])


class ProvenanceDistinctionTests(unittest.TestCase):
    """Constitution honesty rule — curated and live tiers visibly distinct."""

    def test_markdown_keeps_curated_and_live_sections_separate(self):
        rows = [_FakeHit(pmid="40000003", title="Recent live hit", year=2025)]
        a = compose_answer(
            _CURATED_Q, live={"pubmed": _runner(rows)}, live_sources=["pubmed"],
        )
        md = a.to_markdown()
        # Curated claims under their own heading with inline GRADE.
        self.assertIn("## Claims", md)
        self.assertRegex(md, r"\*\*\[Level [A-E]\]\*\*")
        # Live tier under its own fenced, provisional heading.
        self.assertIn("## Live discovery — provisional, not curated", md)
        self.assertIn("§IX", md)
        self.assertIn("never auto-promote", md)
        self.assertIn("[live_pubmed]", md)
        # The curated section comes before the live section (core then breadth).
        self.assertLess(md.index("## Claims"), md.index("## Live discovery"))

    def test_grade_is_inline_at_each_curated_citation(self):
        # §XI — GRADE annotated at the citation site, not only in a summary.
        a = compose_answer("CBD evidence in Dravet syndrome")
        md = a.to_markdown()
        self.assertIn("## Citations", md)
        # At least one citation line carries an inline "— Level X" annotation.
        cite_lines = [
            ln for ln in md.splitlines()
            if ln.startswith("- ") and "Level" in ln and "—" in ln
        ]
        self.assertTrue(cite_lines, "no inline GRADE at any citation site")

    def test_synthesis_verdict_renders_in_the_brief(self):
        rows = [_FakeHit(pmid="40000004", title="hit", year=2024)]
        a = compose_answer(
            _CURATED_Q, live={"pubmed": _runner(rows)}, live_sources=["pubmed"],
        )
        md = a.to_markdown()
        self.assertIn("Cross-source synthesis:", md)
        # to_dict surfaces the verdict only when the live tier was woven in.
        self.assertIn("live_synthesis", a.to_dict())


class ConvergenceVerdictTests(unittest.TestCase):
    def test_three_sources_converge_to_strong(self):
        # Three distinct sources on the same (compound, condition) cluster,
        # each with a distinct citation key → STRONG convergence.
        common = {"_compound": "cbd", "_condition": "epilepsy"}
        a = compose_answer(
            "CBD epilepsy live convergence probe",
            live={
                "pubmed": _runner([_FakeHit(pmid="50000001", title="t1", **common)]),
                "ctgov": _runner([_FakeHit(nct_id="NCT05000001", title="t2", **common)]),
                "chembl": _runner([_FakeHit(chembl_id="CHEMBL50001", title="t3", **common)]),
            },
            live_sources=["pubmed", "ctgov", "chembl"],
        )
        self.assertEqual(a.live_synthesis["convergence"], "STRONG")
        self.assertIn("**Cross-source synthesis: STRONG**", a.to_markdown())

    def test_single_source_is_weak(self):
        rows = [_FakeHit(pmid="50000002", title="lonely", _compound="cbd",
                         _condition="sleep")]
        a = compose_answer(
            "CBD sleep live probe",
            live={"pubmed": _runner(rows)}, live_sources=["pubmed"],
        )
        self.assertEqual(a.live_synthesis["convergence"], "WEAK")


class RerankAndRetractionTests(unittest.TestCase):
    def setUp(self):
        reset_to_seed()  # known retraction registry state

    def tearDown(self):
        reset_to_seed()

    def test_more_relevant_live_row_is_ranked_first(self):
        query = "cannabidiol seizure frequency epilepsy"
        relevant = _FakeHit(
            pmid="60000001",
            title="Cannabidiol reduces seizure frequency in epilepsy", year=2024,
        )
        irrelevant = _FakeHit(
            pmid="60000002", title="Cannabis and tensile bone density", year=2024,
        )
        a = compose_answer(
            query,
            # Deliberately attach the irrelevant row first in fan-out order.
            live={"pubmed": _runner([irrelevant, relevant])},
            live_sources=["pubmed"],
        )
        self.assertEqual(len(a.live_findings), 2)
        # Rerank puts the on-topic row first despite the raw fan-out order.
        self.assertEqual(a.live_findings[0]["identifier"], "PMID 60000001")

    def test_retracted_live_finding_is_badged_not_silently_cited(self):
        # Seed registry pmid 99000001 is RETRACTED.
        f = live_finding_from_row("pubmed", {"pmid": "99000001", "title": "x"})
        assert f is not None
        self.assertEqual(f["retraction_status"], "retracted")
        self.assertIn("RETRACTED", f["provisional_grade"])

        a = compose_answer(
            "CBD retraction probe",
            live={"pubmed": _runner([_FakeHit(pmid="99000001", title="x")])},
            live_sources=["pubmed"],
        )
        self.assertEqual(a.live_findings[0]["retraction_status"], "retracted")
        self.assertIn("⚠ RETRACTED", a.to_markdown())

    def test_clean_live_finding_carries_no_badge(self):
        f = live_finding_from_row("pubmed", {"pmid": "12345678", "title": "ok"})
        assert f is not None
        self.assertEqual(f["retraction_status"], "clean")
        a = compose_answer(
            "CBD clean probe",
            live={"pubmed": _runner([_FakeHit(pmid="12345678", title="ok")])},
            live_sources=["pubmed"],
        )
        self.assertNotIn("⚠", a.to_markdown())

    def test_retracted_row_sinks_even_when_most_relevant(self):
        # Adversarial: the retracted row is the MOST query-relevant and the
        # clean row is off-topic. §VIII must still pin the retracted row last —
        # the relevance ranker must not be able to float it to the top.
        reset_to_seed()
        retracted = _FakeHit(
            pmid="99000001",
            title="CBD epilepsy seizure frequency reduction RCT", year=2025,
        )
        clean = _FakeHit(pmid="60000003", title="cannabis bone density", year=2019)
        a = compose_answer(
            "cbd epilepsy seizure frequency reduction",
            live={"pubmed": _runner([retracted, clean])},
            live_sources=["pubmed"],
        )
        ids = [f["identifier"] for f in a.live_findings]
        self.assertEqual(ids[0], "PMID 60000003",
                         "the clean row must lead despite lower relevance")
        self.assertEqual(ids[-1], "PMID 99000001",
                         "a retracted live row must be pinned last")


class WeaveIsPureTests(unittest.TestCase):
    """``weave_live_findings`` does no I/O — it operates on a result dict."""

    def test_weave_sets_synthesis_and_attaches_in_rank_order(self):
        a = Answer(prompt="cbd epilepsy seizure frequency")
        result = {
            "query": a.prompt,
            "sources": {
                "pubmed": [
                    {"pmid": "70000002", "title": "off topic bone density"},
                    {"pmid": "70000001",
                     "title": "cbd reduces seizure frequency in epilepsy"},
                ],
            },
            "synthesis": {"convergence": "WEAK", "per_source_counts": {"pubmed": 2}},
        }
        n = live.weave_live_findings(a, result, query=a.prompt)
        self.assertEqual(n, 2)
        self.assertEqual(a.live_synthesis["convergence"], "WEAK")
        self.assertEqual(a.live_findings[0]["identifier"], "PMID 70000001")

    def test_weave_empty_sources_returns_zero(self):
        a = Answer(prompt="x")
        n = live.weave_live_findings(
            a, {"sources": {}, "synthesis": {"convergence": "NONE"}}, query="x"
        )
        self.assertEqual(n, 0)
        self.assertEqual(a.live_synthesis["convergence"], "NONE")


if __name__ == "__main__":
    unittest.main()
