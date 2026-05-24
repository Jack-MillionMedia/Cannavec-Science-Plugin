"""Tests enforcing eval-suite coverage (spec 002 US3).

A future contributor cannot silently reduce the eval-suite below the
spec's per-bucket minimums — this test gates them.
"""

import json
import unittest
from pathlib import Path


_EVAL_FILE = (
    Path(__file__).parent.parent / "evals" / "canonical_research_questions.json"
)


def _load_evals():
    return json.loads(_EVAL_FILE.read_text())


class EvalFileShapeTests(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(_EVAL_FILE.exists())

    def test_has_category_minimums_block(self):
        data = _load_evals()
        self.assertIn("category_minimums", data)
        self.assertIsInstance(data["category_minimums"], dict)

    def test_has_at_least_100_prompts(self):
        data = _load_evals()
        self.assertGreaterEqual(len(data["prompts"]), 100)

    def test_has_at_least_142_prompts_v04(self):
        # Spec 004 SC-007 — v0.4 lifts the eval total to ≥ 142.
        data = _load_evals()
        self.assertGreaterEqual(len(data["prompts"]), 142)

    def test_has_at_least_162_prompts_v05(self):
        # Spec 005 SC-009 — v0.5 lifts the eval total to ≥ 162.
        data = _load_evals()
        self.assertGreaterEqual(len(data["prompts"]), 162)


class CategoryMinimumTests(unittest.TestCase):
    """Per-bucket minimums per spec 002 FR-207 / FR-208."""

    def setUp(self):
        self.data = _load_evals()
        self.prompts = self.data["prompts"]
        self.minimums = self.data["category_minimums"]
        self.counts: dict[str, int] = {}
        for p in self.prompts:
            self.counts[p["category"]] = self.counts.get(p["category"], 0) + 1

    def _assert_bucket(self, category: str, minimum: int) -> None:
        actual = self.counts.get(category, 0)
        self.assertGreaterEqual(
            actual, minimum,
            f"category {category!r}: have {actual}, need ≥ {minimum}",
        )

    def test_curated_minimum_25(self):
        self._assert_bucket("curated", 25)

    def test_rigor_positive_minimum_30(self):
        self._assert_bucket("rigor_positive", 30)

    def test_rigor_negative_minimum_20(self):
        self._assert_bucket("rigor_negative", 20)

    def test_refusal_minimum_15(self):
        self._assert_bucket("refusal", 15)

    def test_live_minimum_10(self):
        self._assert_bucket("live", 10)

    def test_cross_cutting_minimum_5(self):
        self._assert_bucket("cross_cutting", 5)

    def test_routing_surfacing_minimum_15(self):
        # Spec 003 US8 / SC-006 — v0.3 routing-and-surfacing bucket.
        self._assert_bucket("routing_surfacing", 15)

    def test_analytical_cultivation_minimum_10(self):
        # Spec 004 US6 / FR-007 — v0.4 analytical-chemistry +
        # cultivation-science bucket.
        self._assert_bucket("analytical_cultivation", 10)

    def test_clinical_pharmacology_depth_minimum_14(self):
        # Spec 005 US8 / FR-009 — v0.5 clinical-pharmacology-depth bucket.
        self._assert_bucket("clinical_pharmacology_depth", 14)

    def test_minimums_in_metadata_match_spec(self):
        expected = {
            "curated": 25,
            "rigor_positive": 30,
            "rigor_negative": 20,
            "refusal": 15,
            "live": 10,
            "cross_cutting": 5,
            "routing_surfacing": 15,
            "analytical_cultivation": 10,
            "clinical_pharmacology_depth": 14,
        }
        for cat, m in expected.items():
            self.assertEqual(
                self.minimums.get(cat), m,
                f"category_minimums[{cat!r}] = {self.minimums.get(cat)}, expected {m}",
            )


class PromptIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.prompts = _load_evals()["prompts"]

    def test_every_prompt_has_id(self):
        for p in self.prompts:
            self.assertIn("id", p)
            self.assertTrue(p["id"])

    def test_every_prompt_has_category(self):
        for p in self.prompts:
            self.assertIn("category", p)

    def test_every_prompt_has_prompt_text(self):
        for p in self.prompts:
            self.assertIn("prompt", p)
            self.assertTrue(p["prompt"])

    def test_ids_unique(self):
        ids = [p["id"] for p in self.prompts]
        self.assertEqual(
            len(ids), len(set(ids)),
            "prompt ids must be unique",
        )

    def test_live_prompts_carry_live_flag(self):
        for p in self.prompts:
            if p["category"] == "live":
                self.assertTrue(
                    p.get("live"),
                    f"live-category prompt {p['id']} must declare live: true "
                    "so the offline runner can skip it",
                )

    def test_non_live_prompts_dont_carry_live_flag(self):
        for p in self.prompts:
            if p["category"] != "live":
                self.assertFalse(
                    p.get("live"),
                    f"non-live prompt {p['id']} should not have live: true",
                )


class EntourageBucketCoverageTests(unittest.TestCase):
    """The new entourage detector ships with eval coverage (spec 002 US6)."""

    def test_entourage_positive_prompts_exist(self):
        prompts = _load_evals()["prompts"]
        entourage_positives = [
            p for p in prompts
            if "entourage_overclaim" in (p.get("expect", {}).get("rigor_detectors_fire") or [])
        ]
        self.assertGreaterEqual(
            len(entourage_positives), 5,
            "entourage detector requires ≥ 5 positive eval prompts",
        )


if __name__ == "__main__":
    unittest.main()
