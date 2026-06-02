"""Offline tests for the optional LLM reranking backend.

A fake duck-typed client stands in for the Anthropic SDK so the suite runs
fully offline and never imports ``anthropic``. These tests pin the three
structural guarantees: the model only moves indices (never sourcing a
citation), the payload is identifier-free, and malformed output degrades to
the deterministic floor.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.ranker import Candidate, rank_candidates  # noqa: E402
from cannavec_science.ranker_llm import (  # noqa: E402
    RUBRIC,
    LLMReranker,
    build_payload,
)


# ── Fake Anthropic client ─────────────────────────────────────────────────


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeMessages:
    def __init__(self, payload_text, capture):
        self._payload_text = payload_text
        self._capture = capture

    def create(self, **kwargs):
        self._capture.update(kwargs)
        return _Resp(self._payload_text)


class _FakeClient:
    """Returns a fixed JSON body and records the kwargs it was called with."""

    def __init__(self, body):
        self.last_call = {}
        self.messages = _FakeMessages(body, self.last_call)


def _c(identifier, title="", abstract="", year=None, study_types=(),
       retraction_status="clean", topic=""):
    return Candidate(
        identifier=identifier, title=title, abstract=abstract, year=year,
        study_types=tuple(study_types), retraction_status=retraction_status,
        topic=topic, source="live_pubmed",
    )


def _cands():
    return [
        _c("PMID111", title="Cannabis for chronic pain", study_types=("RCT",), year=2020),
        _c("PMID222", title="Cannabis for neuropathic pain", study_types=("RCT",), year=2021),
        _c("PMID333", title="Cannabis for cancer pain", study_types=("RCT",), year=2019),
    ]


# ── Payload ───────────────────────────────────────────────────────────────


class PayloadTests(unittest.TestCase):
    def test_payload_is_identifier_free(self):
        cands = _cands()
        text = build_payload("cannabis pain", cands)
        for c in cands:
            self.assertNotIn(c.identifier, text)

    def test_payload_uses_indices_and_titles(self):
        text = build_payload("cannabis pain", _cands())
        self.assertIn("[0]", text)
        self.assertIn("[2]", text)
        self.assertIn("chronic pain", text)

    def test_payload_truncates_long_abstract(self):
        long = "word " * 500
        text = build_payload("q", [_c("X", title="t", abstract=long)])
        self.assertIn("…", text)

    def test_payload_flags_retracted(self):
        text = build_payload("q", [_c("X", title="t", retraction_status="retracted")])
        self.assertIn("RETRACTED", text)


# ── plan() parsing ────────────────────────────────────────────────────────


class PlanParsingTests(unittest.TestCase):
    def test_indices_map_back_to_identifiers(self):
        client = _FakeClient(json.dumps({"ranking": [
            {"index": 2, "reason": "most direct"},
            {"index": 0, "reason": "broad"},
            {"index": 1, "reason": "narrow"},
        ]}))
        plan = LLMReranker(client=client).plan("cannabis pain", _cands())
        self.assertEqual(list(plan.order), ["PMID333", "PMID111", "PMID222"])
        self.assertEqual(plan.rationales["PMID333"], "most direct")
        self.assertEqual(plan.backend, "llm")

    def test_out_of_range_index_dropped_then_appended(self):
        client = _FakeClient(json.dumps({"ranking": [
            {"index": 9},            # out of range → dropped
            {"index": 1},
        ]}))
        plan = LLMReranker(client=client).plan("cannabis pain", _cands())
        # Index 1 first; omitted 0 and 2 appended in original order.
        self.assertEqual(list(plan.order), ["PMID222", "PMID111", "PMID333"])

    def test_duplicate_index_ignored(self):
        client = _FakeClient(json.dumps({"ranking": [
            {"index": 0}, {"index": 0}, {"index": 1},
        ]}))
        plan = LLMReranker(client=client).plan("cannabis pain", _cands())
        self.assertEqual(list(plan.order), ["PMID111", "PMID222", "PMID333"])

    def test_garbage_response_yields_full_fallback_order(self):
        client = _FakeClient("not json at all")
        plan = LLMReranker(client=client).plan("cannabis pain", _cands())
        # No valid indices → every candidate appended in original order.
        self.assertEqual(list(plan.order), ["PMID111", "PMID222", "PMID333"])

    def test_prose_wrapped_json_is_recovered(self):
        client = _FakeClient('Sure!\n{"ranking": [{"index": 1}]}\nDone.')
        plan = LLMReranker(client=client).plan("cannabis pain", _cands())
        self.assertEqual(plan.order[0], "PMID222")

    def test_empty_candidates_no_call(self):
        client = _FakeClient(json.dumps({"ranking": []}))
        plan = LLMReranker(client=client).plan("q", [])
        self.assertEqual(plan.order, ())
        self.assertEqual(client.last_call, {})  # never called the model


# ── Request construction ──────────────────────────────────────────────────


class RequestConstructionTests(unittest.TestCase):
    def test_uses_opus_and_prompt_cached_rubric(self):
        client = _FakeClient(json.dumps({"ranking": [{"index": 0}]}))
        LLMReranker(client=client).plan("cannabis pain", _cands())
        call = client.last_call
        self.assertEqual(call["model"], "claude-opus-4-8")
        # Static rubric carried as a cache_control system block.
        self.assertEqual(call["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(call["system"][0]["text"], RUBRIC)
        # Adaptive thinking + effort under output_config (cost-quality lever).
        self.assertEqual(call["thinking"], {"type": "adaptive"})
        self.assertIn("effort", call["output_config"])
        self.assertEqual(
            call["output_config"]["format"]["type"], "json_schema"
        )

    def test_rubric_forbids_grading_and_inventing(self):
        # The contract lives in the rubric text — pin its load-bearing clauses.
        self.assertIn("NOT a source of citations", RUBRIC)
        self.assertIn("do not output any", RUBRIC.lower())
        self.assertIn("index", RUBRIC.lower())


# ── End-to-end through the pipeline ───────────────────────────────────────


class PipelineIntegrationTests(unittest.TestCase):
    def test_rank_candidates_with_llm_backend(self):
        client = _FakeClient(json.dumps({"ranking": [
            {"index": 2, "reason": "most direct"},
            {"index": 1},
            {"index": 0},
        ]}))
        result = rank_candidates(
            "cannabis pain", _cands(),
            backend=LLMReranker(client=client), escalate=True, now_year=2026,
        )
        self.assertEqual(result.backend_used, "llm")
        self.assertEqual(result.ranked[0].candidate.identifier, "PMID333")
        self.assertEqual(result.ranked[0].rationale, "most direct")

    def test_pipeline_output_ids_subset_of_inputs(self):
        # The model can never widen the citation set, whatever it returns.
        client = _FakeClient(json.dumps({"ranking": [{"index": i} for i in range(3)]}))
        cands = _cands()
        result = rank_candidates(
            "cannabis pain", cands, backend=LLMReranker(client=client),
            escalate=True, now_year=2026,
        )
        out = {r.candidate.identifier for r in result.ranked}
        self.assertTrue(out.issubset({c.identifier for c in cands}))


if __name__ == "__main__":
    unittest.main()
