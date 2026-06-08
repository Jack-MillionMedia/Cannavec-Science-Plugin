"""RED guardrails for the Phase-2 on-topic live gate (TDD — these FAIL now).

Phase 2 "live comprehensiveness" widens coverage by weaving live primary-source
rows onto a curated answer. Breadth without a relevance gate re-opens the exact
demo-killer this project exists to prevent: a confident, wrong-indication live
finding presented as if it answered the question (a Dravet efficacy row surfaced
for a Tourette query). These tests pin the contract the later tasks must satisfy:

- A live EFFICACY row about a DIFFERENT indication than the query is DROPPED
  (wrong-indication efficacy = drop, mirroring the curated off-KB gate).
- A live row that IS on-topic (names the query's compound + condition) SURVIVES.
- The Answer EXPOSES the gate's verdict — ``on_topic_filter_applied`` + a
  dropped-count — so the surface can be honest about what breadth was filtered.

Fully offline: every test injects a fake PubMed runner (the existing
``tests/test_live_discovery.py`` stub-fetcher pattern), so the network is never
touched. A runner takes ``(query, since, n)`` and returns rows exposing
``.to_dict()``; a PubMed row carries ``pmid`` / ``title`` / ``year`` and becomes a
``live_findings`` entry whose ``identifier`` is ``"PMID <pmid>"``.
"""

from __future__ import annotations

import unittest

from cannavec_science import live
from cannavec_science.answer import compose_answer


class _FakeHit:
    """Stand-in for a searcher's LiveHit (only needs ``.to_dict()``).

    Mirrors ``tests/test_live_discovery.py`` exactly so the offline harness is
    identical to the one Phase-2 implementers already know.
    """

    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _pubmed_runner(rows):
    """Inject a fixed list of stub PubMed rows offline (test_live_discovery
    pattern). The returned closure is the runner signature ``augment_answer``
    expects: ``(query, since, n) -> iterable_of_rows``."""

    def _runner(query, since, n):
        return rows[:n]

    return _runner


# A Tourette-syndrome query: an indication the curated KB does not carry graded
# efficacy for, so the answer is the "no curated efficacy" honest-BLUF state —
# precisely where a wrong-indication live row would be most damaging if surfaced.
_TOURETTE_Q = "What is the efficacy of CBD for Tourette syndrome tics?"

# A Dravet-seizure efficacy row — a DIFFERENT indication than the query. The
# 28538134-like PMID echoes the ground-truthed Devinsky 2017 Dravet trial; here
# it is a fake stub standing in for "an off-topic efficacy hit the fan-out found".
_DRAVET_ROW = _FakeHit(
    pmid="28538134",
    title="Trial of cannabidiol for drug-resistant seizures in Dravet syndrome",
    year=2017,
)
_DRAVET_PMID_IDENT = "PMID 28538134"

# An on-topic row: names BOTH the query's compound (cannabidiol/CBD) and the
# query's condition (Tourette tics). This is the breadth Phase 2 wants to keep.
_TOURETTE_ROW = _FakeHit(
    pmid="32000001",
    title="Cannabidiol reduces tic severity in adults with Tourette syndrome",
    year=2023,
)
_TOURETTE_PMID_IDENT = "PMID 32000001"


def _idents(answer) -> set:
    return {f.get("identifier") for f in answer.live_findings}


class WrongIndicationLiveRowIsDropped(unittest.TestCase):
    def test_wrong_indication_efficacy_live_row_is_dropped(self) -> None:
        # Compose for the UNCURATED indication, then augment with a stub fan-out
        # whose only live hit is a wrong-indication (Dravet) efficacy row.
        a = compose_answer(_TOURETTE_Q)
        live.augment_answer(
            a, sources=["pubmed"], runners={"pubmed": _pubmed_runner([_DRAVET_ROW])}
        )
        # The Dravet efficacy row is off-topic for a Tourette query: the on-topic
        # gate must DROP it (wrong-indication efficacy = drop). If a later design
        # chooses demote-not-drop, it must at minimum mark the row off_topic —
        # but it may NEVER appear as an unqualified, citable live finding.
        if _DRAVET_PMID_IDENT in _idents(a):
            dravet = next(
                f for f in a.live_findings
                if f.get("identifier") == _DRAVET_PMID_IDENT
            )
            self.assertTrue(
                dravet.get("off_topic") is True,
                "wrong-indication efficacy row was surfaced as an un-flagged "
                "live finding — it must be dropped (or at least off_topic-flagged) "
                "by the Phase-2 on-topic gate",
            )


class OnTopicLiveRowSurvives(unittest.TestCase):
    def test_on_topic_live_row_survives(self) -> None:
        # Same harness, a row that IS on-topic for the query (mentions the
        # query's compound + condition). The gate must keep it.
        a = compose_answer(_TOURETTE_Q)
        live.augment_answer(
            a, sources=["pubmed"], runners={"pubmed": _pubmed_runner([_TOURETTE_ROW])}
        )
        # The on-topic row survives …
        self.assertIn(
            _TOURETTE_PMID_IDENT,
            _idents(a),
            "an on-topic live row (query compound + condition) must survive the "
            "Phase-2 on-topic gate",
        )
        # … and survives precisely BECAUSE the gate ran and kept it (not merely
        # because no gate exists). This binds the test to the unbuilt contract:
        # the filter must report it ran and that it dropped this on-topic row 0×.
        # FAILS today — ``on_topic_filter_applied`` does not exist; it becomes a
        # real "gate kept on-topic breadth" regression guard once Phase-2 lands.
        self.assertTrue(
            getattr(a, "on_topic_filter_applied", False),
            "the on-topic gate must report it ran when a live row was woven",
        )
        self.assertEqual(
            getattr(a, "live_findings_dropped_off_topic", None),
            0,
            "an on-topic-only fan-out must drop zero findings as off-topic",
        )


class OnTopicFilterMetadataExposed(unittest.TestCase):
    def test_on_topic_filter_metadata_exposed(self) -> None:
        # After an augment that drops a wrong-indication row, the Answer must
        # EXPOSE the gate's verdict so the brief can be honest about what breadth
        # was filtered: a boolean ``on_topic_filter_applied`` and a dropped-count.
        a = compose_answer(_TOURETTE_Q)
        live.augment_answer(
            a,
            sources=["pubmed"],
            runners={"pubmed": _pubmed_runner([_DRAVET_ROW, _TOURETTE_ROW])},
        )

        # Exposed as an attribute on the Answer …
        self.assertTrue(
            getattr(a, "on_topic_filter_applied", False),
            "Answer must expose ``on_topic_filter_applied`` after a live augment",
        )
        dropped = getattr(a, "live_findings_dropped_off_topic", None)
        self.assertIsNotNone(
            dropped,
            "Answer must expose a count of live findings dropped as off-topic",
        )
        self.assertGreaterEqual(
            dropped,
            1,
            "the wrong-indication Dravet row should be counted as dropped",
        )

        # … and mirrored into the serialized dict so a JSON consumer sees it too.
        d = a.to_dict()
        self.assertIn("on_topic_filter_applied", d)
        self.assertTrue(d["on_topic_filter_applied"])
        self.assertGreaterEqual(d.get("live_findings_dropped_off_topic", 0), 1)


class SiblingIndicationLiveRowIsDropped(unittest.TestCase):
    def test_sibling_indication_efficacy_live_row_is_dropped(self) -> None:
        # c04 on the LIVE tier: Dravet / Lennox-Gastaut / TSC all share the
        # ``epilepsy`` FAMILY tag, so a plain family-tag intersection keeps a
        # Dravet efficacy row for a tuberous-sclerosis query — the exact
        # sibling-indication leak the curated predicate already closes. The live
        # gate must mirror that sub-tag precision: a Dravet efficacy row is the
        # WRONG indication for a TSC query and must be dropped (or off_topic).
        q = "What is the efficacy of CBD for tuberous sclerosis complex seizures?"
        a = compose_answer(q)
        live.augment_answer(
            a, sources=["pubmed"], runners={"pubmed": _pubmed_runner([_DRAVET_ROW])}
        )
        if _DRAVET_PMID_IDENT in _idents(a):
            dravet = next(
                f for f in a.live_findings
                if f.get("identifier") == _DRAVET_PMID_IDENT
            )
            self.assertTrue(
                dravet.get("off_topic") is True,
                "a Dravet efficacy row was surfaced UNFLAGGED for a tuberous-"
                "sclerosis query — the live gate omitted the sibling sub-tag "
                "precision the curated predicate has (Dravet vs TSC share the "
                "'epilepsy' family tag); it must be dropped or off_topic-flagged",
            )


class ConditionlessQueryDropsConditionSpecificLiveRow(unittest.TestCase):
    def test_condition_specific_efficacy_dropped_for_conditionless_query(self) -> None:
        # Mirrors the curated predicate's condition-less rule: a condition-
        # SPECIFIC efficacy row (Dravet) surfaced for a query that names NO
        # condition (a pure pharmacokinetics question) is the retrieval/live
        # layer overreaching — it answers a question the user did not ask, so it
        # must be dropped (or off_topic), not led with as a citable finding.
        q = "What is the plasma half-life and oral bioavailability of cannabidiol?"
        a = compose_answer(q)
        live.augment_answer(
            a, sources=["pubmed"], runners={"pubmed": _pubmed_runner([_DRAVET_ROW])}
        )
        if _DRAVET_PMID_IDENT in _idents(a):
            dravet = next(
                f for f in a.live_findings
                if f.get("identifier") == _DRAVET_PMID_IDENT
            )
            self.assertTrue(
                dravet.get("off_topic") is True,
                "a condition-specific Dravet efficacy row was surfaced UNFLAGGED "
                "for a condition-less PK query — the live gate must drop a "
                "condition-specific efficacy row when the prompt names no "
                "condition, mirroring the curated predicate",
            )


if __name__ == "__main__":
    unittest.main()
