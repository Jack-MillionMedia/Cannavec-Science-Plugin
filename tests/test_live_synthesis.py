"""Spec 036 Step 5 (Task 6) — on-topic convergence + honest synthesis prose +
condition canonicalization + the ``BRIEF_SOURCES`` literature-breadth set.

These pin the four sub-contracts of "make the brief's cross-source synthesis
genuinely useful + the live tier genuinely broad" WITHOUT lowering the evidence
floor:

1. Sibling epilepsy subtypes (Dravet / Lennox-Gastaut / TSC) cluster under ONE
   ``epilepsy`` family tag, not three singletons (condition canonicalization via
   ``intent.indication_terms``).
2. A live row DROPPED by the on-topic gate never reaches a cluster or the
   convergence verdict (convergence is computed over post-gate rows only).
3. ``synthesize`` emits a human-readable ``prose`` string whose wording matches
   the ``Convergence`` enum verdict (STRONG -> "converge", MIXED -> "mixed",
   NONE/WEAK -> "insufficient"/"limited"); it names the contributing sources and
   never asserts efficacy.
4. ``live.BRIEF_SOURCES`` is a subset of ``default_runners().keys()`` (every lane
   exists) and a superset of ``DEFAULT_SOURCES`` (genuinely broader breadth).

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import live  # noqa: E402
from cannavec_science.answer import compose_answer  # noqa: E402
from cannavec_science.synthesis import Convergence, synthesize  # noqa: E402


# ── shared offline harness (mirrors tests/test_live_ontopic_gate.py) ──────


class _FakeHit:
    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _pubmed_runner(rows):
    def _runner(query, since, n):
        return rows[:n]

    return _runner


# ── 1. Condition canonicalization — siblings → ONE epilepsy cluster ───────


class SiblingEpilepsyConditionsClusterToOne(unittest.TestCase):
    def test_dravet_lgs_tsc_cluster_under_one_family_tag(self) -> None:
        # Three production-shaped rows (no _compound/_condition seam) naming three
        # DIFFERENT epilepsy subtypes but the SAME compound (CBD). The epilepsy
        # family canonicalizes them to one ``epilepsy`` condition, so they form a
        # single 3-source cluster -> STRONG, not three WEAK singletons.
        rows = {
            "pubmed": [{
                "pmid": "1",
                "title": "Cannabidiol in the Dravet syndrome",
            }],
            "ctgov": [{
                "nct_id": "NCT2",
                "title": "CBD for Lennox-Gastaut syndrome seizures",
            }],
            "europepmc": [{
                "pmid": "3",
                "title": "Cannabidiol for tuberous sclerosis complex seizures",
            }],
        }
        block = synthesize("CBD for epilepsy", rows)
        self.assertEqual(
            block.convergence, Convergence.STRONG,
            "Dravet + Lennox-Gastaut + TSC are sibling epilepsy subtypes; they "
            "must cluster under one family tag, not three singletons",
        )


# ── 2. On-topic convergence — a dropped row never reaches the verdict ─────


_TOURETTE_Q = "What is the efficacy of CBD for Tourette syndrome tics?"
_DRAVET_ROW = _FakeHit(
    pmid="28538134",
    title="Trial of cannabidiol for drug-resistant seizures in Dravet syndrome",
    year=2017,
)
_TOURETTE_ROW = _FakeHit(
    pmid="32000001",
    title="Cannabidiol reduces tic severity in adults with Tourette syndrome",
    year=2023,
)


class DroppedRowNeverReachesVerdict(unittest.TestCase):
    def test_dropped_wrong_indication_row_not_in_synthesis_counts(self) -> None:
        # Fan out a Tourette query with ONE wrong-indication (Dravet) + ONE
        # on-topic (Tourette) live row. The Dravet row is DROPPED by the on-topic
        # gate, so the recomputed live synthesis must reflect only the kept row:
        # its per-source counts must not double-count the dropped row, and its
        # verdict must be WEAK (one on-topic source), never MIXED/STRONG.
        a = compose_answer(_TOURETTE_Q)
        live.augment_answer(
            a,
            sources=["pubmed"],
            runners={"pubmed": _pubmed_runner([_DRAVET_ROW, _TOURETTE_ROW])},
        )
        self.assertGreaterEqual(a.live_findings_dropped_off_topic, 1)
        synth = a.live_synthesis
        self.assertIsNotNone(synth)
        # Only the on-topic Tourette row survives into the verdict.
        self.assertEqual(synth["per_source_counts"].get("pubmed", 0), 1)
        # One on-topic source -> WEAK. A dropped row must NOT manufacture MIXED.
        self.assertEqual(synth["convergence"], Convergence.WEAK.value)


# ── 3. Honest prose — wording matches the verdict, never asserts efficacy ─


class SynthesisProseIsHonest(unittest.TestCase):
    def _block(self, rows, q="CBD for epilepsy"):
        return synthesize(q, rows)

    def test_strong_prose_says_converge_and_names_sources(self) -> None:
        rows = {
            "pubmed": [{"pmid": "1", "title": "Cannabidiol in the Dravet syndrome"}],
            "ctgov": [{"nct_id": "NCT2", "title": "CBD for Lennox-Gastaut seizures"}],
            "europepmc": [{"pmid": "3", "title": "Cannabidiol for tuberous sclerosis seizures"}],
        }
        block = self._block(rows)
        self.assertEqual(block.convergence, Convergence.STRONG)
        self.assertIsInstance(block.prose, str)
        self.assertIn("converge", block.prose.lower())
        # Names the contributing sources (display labels).
        self.assertIn("PubMed", block.prose)
        self.assertIn("CT.gov", block.prose)
        self.assertIn("Europe PMC", block.prose)

    def test_mixed_prose_says_mixed(self) -> None:
        rows = {
            "pubmed": [{"pmid": "1", "title": "Cannabidiol for Lennox-Gastaut seizures"}],
            "ctgov": [{"nct_id": "NCT2", "title": "CBD in Lennox-Gastaut syndrome"}],
        }
        block = self._block(rows, q="CBD Lennox-Gastaut")
        self.assertEqual(block.convergence, Convergence.MIXED)
        self.assertIn("mixed", block.prose.lower())

    def test_weak_prose_says_limited_or_insufficient(self) -> None:
        rows = {"pubmed": [{"pmid": "1", "title": "Cannabidiol for Dravet seizures"}]}
        block = self._block(rows)
        self.assertEqual(block.convergence, Convergence.WEAK)
        low = block.prose.lower()
        self.assertTrue(
            "limited" in low or "insufficient" in low or "single" in low,
            f"WEAK prose must read as limited/insufficient, got: {block.prose!r}",
        )

    def test_none_prose_says_insufficient(self) -> None:
        block = self._block({"pubmed": [], "ctgov": []}, q="CBD epilepsy")
        self.assertEqual(block.convergence, Convergence.NONE)
        self.assertIn("insufficient", block.prose.lower())

    def test_prose_never_asserts_efficacy(self) -> None:
        # No matter the verdict, the prose must never claim the compound WORKS.
        for rows, q in (
            ({"pubmed": [{"pmid": "1", "title": "Cannabidiol in the Dravet syndrome"}],
              "ctgov": [{"nct_id": "2", "title": "CBD for Lennox-Gastaut seizures"}],
              "europepmc": [{"pmid": "3", "title": "Cannabidiol for tuberous sclerosis"}]},
             "CBD epilepsy"),
            ({"pubmed": [{"pmid": "1", "title": "Cannabidiol for Dravet seizures"}]},
             "CBD epilepsy"),
            ({"pubmed": [], "ctgov": []}, "CBD epilepsy"),
        ):
            block = synthesize(q, rows)
            low = block.prose.lower()
            for banned in (
                "effective", "efficacious", "works", "proven", "cures",
                "improves seizure", "reduces seizure", "treats",
            ):
                self.assertNotIn(
                    banned, low,
                    f"synthesis prose asserted efficacy ({banned!r}): "
                    f"{block.prose!r}",
                )

    def test_prose_in_to_dict_and_markdown(self) -> None:
        from cannavec_science.synthesis import render_markdown

        rows = {"pubmed": [{"pmid": "1", "title": "Cannabidiol for Dravet seizures"}]}
        block = synthesize("CBD epilepsy", rows)
        self.assertIn("prose", block.to_dict())
        self.assertEqual(block.to_dict()["prose"], block.prose)
        self.assertIn(block.prose, render_markdown(block))


# ── 4. BRIEF_SOURCES — broader literature-breadth lane subset ─────────────


class BriefSourcesBreadthSet(unittest.TestCase):
    def test_brief_sources_is_subset_of_runners(self) -> None:
        self.assertTrue(
            set(live.BRIEF_SOURCES) <= set(live.default_runners().keys()),
            f"BRIEF_SOURCES names a lane with no runner: "
            f"{set(live.BRIEF_SOURCES) - set(live.default_runners().keys())}",
        )

    def test_brief_sources_is_superset_of_default_sources(self) -> None:
        self.assertTrue(
            set(live.DEFAULT_SOURCES) <= set(live.BRIEF_SOURCES),
            "BRIEF_SOURCES must be at least as broad as the lean DEFAULT_SOURCES",
        )

    def test_brief_sources_is_strictly_broader_than_default(self) -> None:
        self.assertGreater(
            len(set(live.BRIEF_SOURCES)), len(set(live.DEFAULT_SOURCES)),
            "BRIEF_SOURCES is meant to be MORE comprehensive than DEFAULT_SOURCES",
        )

    def test_default_sources_unchanged(self) -> None:
        # Registry-invariant guard: the lean serverless default stays the lean
        # serverless default (the web API depends on it).
        self.assertEqual(live.DEFAULT_SOURCES, ("pubmed", "ctgov"))


if __name__ == "__main__":
    unittest.main()
