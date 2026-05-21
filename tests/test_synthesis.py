"""Tests for cannavec.synthesis (spec 002 US5 — Wave C).

The cross-source synthesizer is the elite-tier deliverable. Its
correctness is the highest-impact failure mode in this spec, so this
suite is the largest of any single Wave-C module.

Deterministic rules only — NO LLM, NO randomness. Same input → same
output, every time.

elite-expert-engine-002 US5
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.synthesis import (  # noqa: E402
    Convergence,
    SynthesisBlock,
    build_claim_clusters,
    pubmed_sentiment,
    render_json,
    render_markdown,
    synthesize,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _pubmed_hit(
    pmid: str = "12345",
    title: str = "CBD for epilepsy: a randomised trial",
    abstract: str = "Cannabidiol significantly improved seizure frequency.",
    compound: str = "cbd",
    condition: str = "epilepsy",
) -> dict:
    """Synthesizer-compatible PubMed row shape."""
    return {
        "source": "live_pubmed",
        "pmid": pmid,
        "native_id": pmid,
        "title": title,
        "abstract": abstract,
        "_compound": compound,        # synthesizer reads these (test seam)
        "_condition": condition,
    }


def _chembl_hit(
    chembl_id: str = "CHEMBL190",
    compound: str = "cbd",
    target: str = "CB1",
) -> dict:
    return {
        "source": "live_chembl",
        "chembl_id": chembl_id,
        "native_id": chembl_id,
        "title": f"{compound} @ {target}",
        "_compound": compound,
        "_target": target,
        "_condition": "",
    }


def _ctgov_hit(
    nct: str = "NCT01234567",
    compound: str = "cbd",
    condition: str = "epilepsy",
    status: str = "RECRUITING",
) -> dict:
    return {
        "source": "live_ctgov",
        "nct_id": nct,
        "native_id": nct,
        "title": f"{compound} for {condition}",
        "status": status,
        "_compound": compound,
        "_condition": condition,
    }


def _preprint_hit(
    doi: str = "10.1101/2026.04.12.123456",
    compound: str = "cbd",
    condition: str = "epilepsy",
    abstract: str = "Cannabidiol significantly improved seizure frequency.",
) -> dict:
    return {
        "source": "live_preprint",
        "doi": doi,
        "native_id": doi,
        "title": "CBD for epilepsy preprint",
        "abstract": abstract,
        "_compound": compound,
        "_condition": condition,
    }


def _cl_hit(
    opinion_id: str = "1000001",
    compound: str = "cbd",
    condition: str = "regulatory",
) -> dict:
    return {
        "source": "live_courtlistener",
        "opinion_id": opinion_id,
        "native_id": opinion_id,
        "title": f"State v. {compound} dispensary",
        "_compound": compound,
        "_condition": condition,
    }


# ── 1. Empty / no-rows scenarios ─────────────────────────────────────────


class EmptyInputTests(unittest.TestCase):
    def test_all_none_returns_none_convergence(self) -> None:
        result = synthesize(
            "CBD epilepsy",
            {"pubmed": None, "chembl": None, "ctgov": None,
             "preprint": None, "courtlistener": None},
        )
        self.assertEqual(result.convergence, Convergence.NONE)
        self.assertTrue(result.incomplete)
        self.assertEqual(set(result.unreachable_sources), {
            "pubmed", "chembl", "ctgov", "preprint", "courtlistener"
        })

    def test_all_empty_lists_returns_none_convergence(self) -> None:
        result = synthesize(
            "CBD epilepsy",
            {"pubmed": [], "chembl": [], "ctgov": [],
             "preprint": [], "courtlistener": []},
        )
        self.assertEqual(result.convergence, Convergence.NONE)
        self.assertFalse(result.incomplete)
        # No unreachable sources
        self.assertEqual(result.unreachable_sources, ())


# ── 2. Single source ─────────────────────────────────────────────────────


class SingleSourceTests(unittest.TestCase):
    def test_single_source_weak_convergence(self) -> None:
        result = synthesize(
            "CBD epilepsy",
            {"pubmed": [_pubmed_hit()], "chembl": [], "ctgov": [],
             "preprint": [], "courtlistener": []},
        )
        self.assertEqual(result.convergence, Convergence.WEAK)


# ── 3. Two-source cluster ────────────────────────────────────────────────


class TwoSourceClusterTests(unittest.TestCase):
    def test_two_sources_mixed_convergence(self) -> None:
        result = synthesize(
            "CBD epilepsy",
            {
                "pubmed": [_pubmed_hit(compound="cbd", condition="epilepsy")],
                "ctgov": [_ctgov_hit(compound="cbd", condition="epilepsy")],
                "chembl": [],
                "preprint": [],
                "courtlistener": [],
            },
        )
        # Two sources, same cluster → MIXED
        self.assertEqual(result.convergence, Convergence.MIXED)


# ── 4. Three-source cluster ──────────────────────────────────────────────


class ThreeSourceClusterTests(unittest.TestCase):
    def test_three_sources_strong_convergence(self) -> None:
        result = synthesize(
            "CBD epilepsy",
            {
                "pubmed": [_pubmed_hit(compound="cbd", condition="epilepsy")],
                "ctgov": [_ctgov_hit(compound="cbd", condition="epilepsy")],
                "preprint": [_preprint_hit(compound="cbd", condition="epilepsy")],
                "chembl": [],
                "courtlistener": [],
            },
        )
        self.assertEqual(result.convergence, Convergence.STRONG)


class FourSourceClusterTests(unittest.TestCase):
    def test_four_sources_strong_convergence(self) -> None:
        result = synthesize(
            "CBD epilepsy",
            {
                "pubmed": [_pubmed_hit(compound="cbd", condition="epilepsy")],
                "ctgov": [_ctgov_hit(compound="cbd", condition="epilepsy")],
                "preprint": [_preprint_hit(compound="cbd", condition="epilepsy")],
                "chembl": [_chembl_hit(compound="cbd")],  # neutral but same cluster
                "courtlistener": [],
            },
        )
        # 4 sources but chembl is neutral; still cluster gets 3 distinct
        # source-supporters → STRONG
        self.assertEqual(result.convergence, Convergence.STRONG)


# ── 5. Disagreement ──────────────────────────────────────────────────────


class DisagreementTests(unittest.TestCase):
    def test_disagreement_detected_when_two_supporters_one_refuter(self) -> None:
        result = synthesize(
            "CBD anxiety",
            {
                "pubmed": [
                    _pubmed_hit(
                        compound="cbd", condition="anxiety",
                        abstract="Cannabidiol significantly improved anxiety scores."
                    ),
                ],
                "preprint": [
                    _preprint_hit(
                        compound="cbd", condition="anxiety",
                        abstract="Cannabidiol did not improve anxiety compared to placebo."
                    ),
                ],
                "chembl": [], "ctgov": [], "courtlistener": [],
            },
        )
        self.assertIsNotNone(result.disagreement)
        self.assertIn("supports", result.disagreement or "")
        self.assertIn("refute", result.disagreement or "")


# ── 6. De-duplication by citation key ────────────────────────────────────


class DeduplicationTests(unittest.TestCase):
    def test_same_pmid_in_two_sources_counts_as_one(self) -> None:
        """A CT.gov trial whose results-paper is in PubMed should NOT
        look like cross-source convergence."""
        # We model: same PMID appears in both pubmed and ctgov rows
        pmid = "99999"
        pm = _pubmed_hit(pmid=pmid, compound="cbd", condition="epilepsy")
        ct = _ctgov_hit(compound="cbd", condition="epilepsy")
        ct["pmid"] = pmid  # CT.gov row references the same PMID

        result = synthesize(
            "CBD epilepsy",
            {
                "pubmed": [pm],
                "ctgov": [ct],
                "chembl": [], "preprint": [], "courtlistener": [],
            },
        )
        # Without dedup: 2 distinct sources → MIXED.
        # With dedup: 1 distinct underlying publication → WEAK.
        self.assertEqual(result.convergence, Convergence.WEAK)


# ── 7. Determinism ───────────────────────────────────────────────────────


class DeterminismTests(unittest.TestCase):
    def test_same_input_same_output(self) -> None:
        per_source = {
            "pubmed": [_pubmed_hit(compound="cbd", condition="epilepsy")],
            "ctgov": [_ctgov_hit(compound="cbd", condition="epilepsy")],
            "preprint": [], "chembl": [], "courtlistener": [],
        }
        r1 = synthesize("CBD epilepsy", per_source)
        r2 = synthesize("CBD epilepsy", per_source)
        self.assertEqual(r1.convergence, r2.convergence)
        self.assertEqual(r1.per_source_counts, r2.per_source_counts)
        self.assertEqual(r1.disagreement, r2.disagreement)


# ── 8. PubMed sentiment parser ───────────────────────────────────────────


class PubmedSentimentTests(unittest.TestCase):
    def test_no_significant_difference_refutes(self) -> None:
        self.assertEqual(
            pubmed_sentiment("There was no significant difference between groups"),
            "refutes",
        )

    def test_did_not_improve_refutes(self) -> None:
        self.assertEqual(
            pubmed_sentiment("Cannabidiol did not improve outcomes"),
            "refutes",
        )

    def test_significantly_improved_supports(self) -> None:
        self.assertEqual(
            pubmed_sentiment("Cannabidiol significantly improved scores"),
            "supports",
        )

    def test_efficacious_supports(self) -> None:
        self.assertEqual(
            pubmed_sentiment("The intervention was efficacious"),
            "supports",
        )

    def test_neutral_abstract_is_neutral(self) -> None:
        self.assertEqual(
            pubmed_sentiment("We described pharmacokinetics in healthy adults"),
            "neutral",
        )

    def test_empty_input_is_neutral(self) -> None:
        self.assertEqual(pubmed_sentiment(""), "neutral")


# ── 9. Per-source direction rules ────────────────────────────────────────


class PerSourceDirectionTests(unittest.TestCase):
    def test_chembl_always_neutral(self) -> None:
        """ChEMBL rows are bioactivity, not clinical claims → neutral."""
        clusters = build_claim_clusters({
            "pubmed": [],
            "chembl": [_chembl_hit(compound="cbd")],
            "ctgov": [], "preprint": [], "courtlistener": [],
        })
        for cluster in clusters:
            for src, row in cluster.members:
                if src == "chembl":
                    self.assertEqual(row["direction"], "neutral")

    def test_courtlistener_always_neutral(self) -> None:
        """A court ruling is not clinical evidence → neutral."""
        clusters = build_claim_clusters({
            "pubmed": [],
            "chembl": [], "ctgov": [], "preprint": [],
            "courtlistener": [_cl_hit(compound="cbd", condition="regulatory")],
        })
        for cluster in clusters:
            for src, row in cluster.members:
                if src == "courtlistener":
                    self.assertEqual(row["direction"], "neutral")


# ── 10. Multi-cluster scenarios ──────────────────────────────────────────


class MultiClusterTests(unittest.TestCase):
    def test_two_clusters_at_2_distinct_each_max_is_mixed(self) -> None:
        """Two compound clusters at 2-distinct-sources each → MIXED."""
        result = synthesize(
            "CBD and CBN for sleep",
            {
                "pubmed": [
                    _pubmed_hit(compound="cbd", condition="sleep"),
                    _pubmed_hit(pmid="22222", compound="cbn", condition="sleep"),
                ],
                "preprint": [
                    _preprint_hit(compound="cbd", condition="sleep"),
                    _preprint_hit(
                        doi="10.1101/cbn", compound="cbn", condition="sleep",
                    ),
                ],
                "chembl": [], "ctgov": [], "courtlistener": [],
            },
        )
        self.assertEqual(result.convergence, Convergence.MIXED)


# ── 11. Renderers ────────────────────────────────────────────────────────


class RendererTests(unittest.TestCase):
    def test_markdown_includes_required_lines(self) -> None:
        block = synthesize(
            "CBD epilepsy",
            {
                "pubmed": [_pubmed_hit()],
                "ctgov": [_ctgov_hit()],
                "preprint": [], "chembl": [], "courtlistener": [],
            },
        )
        md = render_markdown(block)
        self.assertIn("SYNTHESIS", md)
        self.assertIn("Convergence:", md)
        self.assertIn("Disagreement:", md)
        self.assertIn("Unreachable:", md)
        self.assertIn("Deterministic", md)

    def test_json_shape(self) -> None:
        block = synthesize(
            "CBD epilepsy",
            {
                "pubmed": [_pubmed_hit()],
                "ctgov": [], "preprint": [], "chembl": [], "courtlistener": [],
            },
        )
        payload = json.loads(render_json(block))
        self.assertIn("convergence", payload)
        self.assertIn("per_source_counts", payload)
        self.assertIn("disagreement", payload)


# ── 12. Per-source counts in block ──────────────────────────────────────


class PerSourceCountsTests(unittest.TestCase):
    def test_counts_reflect_inputs(self) -> None:
        block = synthesize(
            "CBD",
            {
                "pubmed": [_pubmed_hit(), _pubmed_hit(pmid="2"), _pubmed_hit(pmid="3")],
                "chembl": [_chembl_hit()],
                "ctgov": [], "preprint": [], "courtlistener": [],
            },
        )
        self.assertEqual(block.per_source_counts["pubmed"], 3)
        self.assertEqual(block.per_source_counts["chembl"], 1)
        self.assertEqual(block.per_source_counts["ctgov"], 0)


# ── 13. Unreachable handling ─────────────────────────────────────────────


class UnreachableTests(unittest.TestCase):
    def test_partial_unreachable_marks_incomplete(self) -> None:
        block = synthesize(
            "CBD",
            {
                "pubmed": [_pubmed_hit()],
                "chembl": None,  # unreachable
                "ctgov": [], "preprint": [], "courtlistener": [],
            },
        )
        self.assertTrue(block.incomplete)
        self.assertIn("chembl", block.unreachable_sources)


if __name__ == "__main__":
    unittest.main()
