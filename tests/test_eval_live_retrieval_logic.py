"""Offline tests for the hardened live-retrieval eval's pure logic — best-of-N,
inconclusive handling, and the reliability/relevance gate. The eval module is
loaded by path (``evals/`` is not a package); no network is touched (the discover
runner is injected)."""

from __future__ import annotations

import importlib.util
import os
import unittest

_EVAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "evals", "eval_live_retrieval.py",
)
_spec = importlib.util.spec_from_file_location("_elr", _EVAL_PATH)
elr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(elr)


def _payload(*titles):
    rows = [{"title": t} for t in titles]
    return {"sources": {"pubmed": rows}, "ranking": {"ranked": rows}}


_EMPTY = ({"sources": {}, "ranking": {"ranked": []}, "_err": "boom"}, True)


def _runner_from(script):
    """Return a runner that yields each (payload, inconclusive) in order, then
    repeats the last."""
    state = {"i": 0}

    def runner(_q, _sources, _max):
        i = min(state["i"], len(script) - 1)
        state["i"] += 1
        return script[i]

    return runner


class BestOfN(unittest.TestCase):
    def test_best_attempt_wins(self):
        # First attempt off-topic, second on-topic → best relevance = 1.0.
        runner = _runner_from([
            (_payload("totally unrelated paper"), False),
            (_payload("CB1 and working memory in the hippocampus"), False),
        ])
        sc = elr._best_of(runner, "q", "pubmed", 5, ("memory", "cb1"), 3, best_of=2)
        self.assertFalse(sc["inconclusive"])
        self.assertEqual(sc["relevance"], 1.0)

    def test_inconclusive_only_when_all_attempts_fail_transport(self):
        self.assertTrue(elr._best_of(_runner_from([_EMPTY]), "q", "s", 5, ("x",), 3,
                                     best_of=3)["inconclusive"])
        # One reachable attempt (even with no rows) → conclusive.
        mixed = _runner_from([_EMPTY, (_payload("memory paper"), False)])
        self.assertFalse(elr._best_of(mixed, "q", "s", 5, ("memory",), 3,
                                      best_of=2)["inconclusive"])


class Gate(unittest.TestCase):
    def _result(self, *, coverage=1, relevance=1.0, top1=True, inconclusive=False):
        return {"coverage": coverage, "relevance": relevance,
                "top1_on_topic": top1, "inconclusive": inconclusive}

    def test_pass_when_grounded_and_relevant(self):
        results = [self._result(relevance=0.6, top1=True) for _ in range(8)]
        g = elr.gate(results, min_relevance=0.25, min_top1=0.375)
        self.assertEqual(g["status"], "pass")

    def test_fail_on_real_relevance_collapse(self):
        results = [self._result(relevance=0.0, top1=False) for _ in range(8)]
        g = elr.gate(results, min_relevance=0.25, min_top1=0.375)
        self.assertEqual(g["status"], "fail")

    def test_fail_when_a_reachable_question_is_not_grounded(self):
        results = [self._result(relevance=0.9, top1=True) for _ in range(7)]
        results.append(self._result(coverage=0, relevance=0.0, top1=False))  # reachable, 0 rows
        g = elr.gate(results, min_relevance=0.25, min_top1=0.375)
        self.assertEqual(g["status"], "fail")
        self.assertFalse(g["grounded"])

    def test_inconclusive_when_too_few_reachable(self):
        results = [self._result(inconclusive=True) for _ in range(6)]
        results += [self._result() for _ in range(2)]  # only 2/8 reachable < 60%
        g = elr.gate(results, min_relevance=0.25, min_top1=0.375)
        self.assertEqual(g["status"], "inconclusive")

    def test_variance_dip_does_not_fail(self):
        # The historical flake: one query dips, the rest fine → mean ~0.37, PASS.
        results = ([self._result(relevance=0.0, top1=False)]
                   + [self._result(relevance=0.5, top1=True) for _ in range(7)])
        g = elr.gate(results, min_relevance=0.25, min_top1=0.375)
        self.assertEqual(g["status"], "pass")  # 0.4375 mean clears the 0.25 floor


if __name__ == "__main__":
    unittest.main()
