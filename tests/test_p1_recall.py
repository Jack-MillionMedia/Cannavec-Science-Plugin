"""Regression tests for the P1 recall fixes from the 2026-06 adversarial audit.

P1 raises curated recall so an expert query surfaces the *right* primary
sources. Ground-truthed via PubMed.

- c02 — the "adult MS spasticity" row cited only a narrative review
  (MacCallum 2018) and missed the pivotal nabiximols MS-spasticity RCT.
  It must cite Novotna 2011 (PMID 21362108, Eur J Neurol, the Phase 3
  enriched-design Sativex RCT, ITT p=0.0002).

NOTE on Dravet/LGS: those rows remain Level B by *deliberate* design
(per-study grade on a single pivotal RCT; the body-of-evidence Level A lives
in the major-cannabinoid monograph). See test_grade_by_design /
test_grade_consistency — that is intentional and is NOT changed here.

Offline / stdlib-only.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import EvidenceLevel

_API_DIR = Path(__file__).resolve().parent.parent / "api"


def _load_api(module_name: str):
    path = _API_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"api_{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestC02NabiximolsMsSpasticity(unittest.TestCase):
    """c02 — MS spasticity must cite the pivotal Novotna 2011 RCT."""

    def _ms_claim(self):
        a = compose_answer("nabiximols for multiple sclerosis spasticity")
        ms = [
            c for c in a.claims
            if c.population and "ms spasticity" in c.population.lower()
        ]
        return ms

    def test_ms_spasticity_cites_novotna_pivotal_rct(self):
        ms = self._ms_claim()
        self.assertTrue(ms, "expected an 'adult MS spasticity' claim")
        pmids = {s.pmid for c in ms for s in c.sources if s.pmid}
        self.assertIn(
            "21362108", pmids,
            "MS-spasticity claim must cite Novotna 2011 (pivotal Sativex RCT)",
        )

    def test_ms_spasticity_grade_at_least_b_with_rct(self):
        ms = self._ms_claim()
        self.assertTrue(ms)
        best = max(c.best_supportable_grade().rank for c in ms)
        self.assertGreaterEqual(
            best, EvidenceLevel.B.rank,
            "with the pivotal RCT cited, the MS-spasticity row should reach "
            "its Level-B curator anchor (was Level C on a narrative review)",
        )


class TestD4MinorCannabinoidMonographSurfaces(unittest.TestCase):
    """D4 — a query for a minor cannabinoid (CBG/CBC/CBN) must surface its
    curated monograph instead of a bare "no evidence found", and the monograph
    must reach JSON consumers (not be Markdown-only)."""

    MINOR_QUERIES = (
        "cannabigerol CBG pharmacology and targets",
        "cannabichromene CBC therapeutic efficacy",
        "CBN cannabinol for sleep",
    )

    def test_monograph_sections_serialized_in_to_dict(self):
        a = compose_answer("cannabigerol CBG pharmacology and targets")
        d = a.to_dict()
        self.assertIn(
            "sections", d,
            "monograph sections must be in to_dict() so JSON / at-scale "
            "consumers receive the monograph, not just the Markdown brief",
        )
        self.assertTrue(d["sections"])
        blob = json.dumps(d["sections"]).lower()
        self.assertIn("cannabigerol", blob)

    def test_minor_cannabinoid_not_flagged_no_evidence(self):
        ans = _load_api("answer")
        for q in self.MINOR_QUERIES:
            a = compose_answer(q)
            self.assertFalse(
                ans._is_no_evidence(a),
                f"{q!r}: a populated curated monograph must not be flagged "
                f"no_evidence",
            )

    def test_true_nonsense_still_flagged_no_evidence(self):
        ans = _load_api("answer")
        a = compose_answer("asdfqwer zzz nonsense token salad")
        self.assertTrue(
            ans._is_no_evidence(a),
            "a query with no claims, no monograph and no live findings must "
            "still be flagged no_evidence",
        )


if __name__ == "__main__":
    unittest.main()
