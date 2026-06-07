"""Locked contract for the canonical Answer JSON that `/cv` output skills
transform.

Every `/cv` skill (cite / pdf / evidence-table / presentation) consumes
``python3 -m cannavec_science answer <q> --json``. If the engine silently
renames or drops a key those skills depend on, the skills break. This test
pins the stable shape so the contract changes only deliberately (with a test
update), never by accident — the foundation guarantee that lets skills be built
against a fixed surface.

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.answer import compose_answer

_GRADES = {"Level A", "Level B", "Level C", "Level D", "Level E", "Unsupported"}


class TestAnswerJsonContract(unittest.TestCase):
    def setUp(self) -> None:
        # A curated efficacy answer exercises every field a /cv skill reads.
        self.d = compose_answer("CBD evidence in Dravet syndrome").to_dict()

    def test_top_level_keys(self) -> None:
        for k in (
            "prompt", "audience", "generated_at", "short_answer",
            "refusal_reason", "claims", "citations", "evidence_summary",
            "cautions", "notes",
        ):
            self.assertIn(k, self.d, f"Answer JSON missing top-level key {k!r}")

    def test_claim_shape_and_grade_vocab(self) -> None:
        self.assertTrue(self.d["claims"], "expected at least one claim")
        for c in self.d["claims"]:
            for k in ("text", "claim_type", "grade", "sources", "population"):
                self.assertIn(k, c, f"claim missing key {k!r}")
            self.assertIn(c["grade"], _GRADES, f"invalid grade {c['grade']!r}")
            for s in c["sources"]:
                for k in ("title", "pmid", "doi", "url", "year", "tier"):
                    self.assertIn(k, s, f"source missing key {k!r}")

    def test_effect_estimate_shape_when_present(self) -> None:
        # The evidence-table skill reads these; pin every documented key when
        # emitted (a rename like confidence_interval->ci_95 must fail HERE, not
        # silently break the SoF skill). The Dravet fixture is known to carry a
        # full effect estimate, so this assertion is non-vacuous.
        seen_full = False
        for c in self.d["claims"]:
            for e in c.get("effect_estimates", []):
                for k in (
                    "pmid", "n", "comparator", "primary_outcome", "effect_size",
                    "confidence_interval", "nnt", "nnt_caveat",
                ):
                    self.assertIn(k, e, f"effect_estimate missing key {k!r}")
                seen_full = True
        self.assertTrue(
            seen_full,
            "the curated Dravet fixture should expose at least one full "
            "effect_estimate — the contract assertion must not be vacuous",
        )

    def test_evidence_summary_shape(self) -> None:
        es = self.d["evidence_summary"]
        for k in (
            "highest_grade", "n_claims", "n_with_primary_source",
            "n_missing_required_disclosures", "n_retracted_citations",
        ):
            self.assertIn(k, es, f"evidence_summary missing key {k!r}")
        self.assertIn(es["highest_grade"], _GRADES)

    def test_citation_shape_and_grade_vocab(self) -> None:
        self.assertTrue(self.d["citations"], "expected at least one citation")
        for c in self.d["citations"]:
            for k in ("label", "pmid", "doi", "url", "year", "grade"):
                self.assertIn(k, c, f"citation missing key {k!r}")
            self.assertTrue(
                c["grade"] is None or c["grade"] in _GRADES,
                f"invalid citation grade {c['grade']!r}",
            )
            # §I: every citation carries at least one resolvable identifier.
            self.assertTrue(
                c["pmid"] or c["doi"] or c["url"],
                f"citation with no primary-source identifier: {c}",
            )

    def test_refusal_is_detectable_from_json(self) -> None:
        # A /cv skill must be able to detect a refusal from the JSON alone and
        # skip rendering. A refused answer carries a non-null refusal_reason
        # OR an empty short_answer with no claims.
        d = compose_answer(
            "You should take 50mg of THC for your insomnia tonight."
        ).to_dict()
        self.assertIn("refusal_reason", d)
        self.assertTrue(
            d["refusal_reason"] or not d["claims"],
            "refusal not detectable from JSON contract",
        )


if __name__ == "__main__":
    unittest.main()
