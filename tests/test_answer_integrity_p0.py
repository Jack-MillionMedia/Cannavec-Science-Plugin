"""P0 integrity contracts for ``answer.py`` — fail-loud, no silent corruption.

Synthesised from the three-persona review (Developer C reliability/security +
Developer B's ``dataclasses.replace`` cleanup). Each test pins a failure path
that the composer previously swallowed in silence:

* a registry row whose ``to_claim()`` raises must be DROPPED AUDIBLY (trace),
  never invisibly;
* a retraction-registry fault must neither crash the whole composition nor
  silently promote an unverifiable source as "clean";
* a strict-wording rejection must be recorded (the old comment promised this
  but the body just ``pass``ed);
* a transient populations-registry fault must NOT poison the effect-index cache
  into permanently-empty for the process lifetime;
* the two citation-dedup paths (``add_citation`` / ``merge_citations``) must
  share one identity rule so they cannot drift.

All offline. None of these paths fire on a well-formed fixture, so the pinned
Markdown/JSON snapshots elsewhere are unaffected.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from cannavec_science.answer import (
    Answer,
    Citation,
    ClaimWordingError,
    _attach_claim_safely,
    _build_population_effect_index,
    _is_same_citation,
    _population_effect_index,
    merge_citations,
)
from cannavec_science.evidence import (
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
)


def _trace_count(a: Answer, detector: str) -> int:
    return sum(h for d, h in a.trace if d == detector)


class _RaisingRow:
    id = "ROW_BAD"

    def to_claim(self):
        raise ValueError("malformed registry row")


class _GoodRow:
    id = "ROW_OK"

    def __init__(self, claim: Claim):
        self._claim = claim

    def to_claim(self) -> Claim:
        return self._claim


def _simple_claim() -> Claim:
    src = Source(title="t", tier=SourceTier.JOURNAL_RCT, pmid="111", year=2020)
    return Claim(
        text="CBD may reduce X.",
        claim_type=ClaimType.CLINICAL_EFFICACY,
        sources=(src,),
    )


class AttachClaimSafelyIntegrity(unittest.TestCase):
    def test_to_claim_failure_is_traced_not_silent(self):
        a = Answer(prompt="q")
        _attach_claim_safely(a, _RaisingRow(), "strict")
        self.assertEqual(a.claims, [], "malformed row must not add a claim")
        self.assertEqual(
            _trace_count(a, "claim_build_error"), 1,
            "a dropped row must leave an auditable trace, not vanish",
        )

    def test_retraction_fault_neither_crashes_nor_promotes_as_clean(self):
        a = Answer(prompt="q", strict_wording=False)
        row = _GoodRow(_simple_claim())
        with mock.patch(
            "cannavec_science.retraction.is_retracted",
            side_effect=RuntimeError("retraction registry down"),
        ):
            _attach_claim_safely(a, row, "strict")  # must NOT raise
        self.assertEqual(len(a.claims), 1, "registry fault must not lose the row")
        self.assertEqual(_trace_count(a, "retraction_check_error"), 1)
        self.assertTrue(
            any("retraction" in c.lower() for c in a.cautions),
            "unverifiable retraction status must surface to the researcher",
        )

    def test_wording_rejection_is_recorded(self):
        a = Answer(prompt="q")
        row = _GoodRow(_simple_claim())
        err = ClaimWordingError(_simple_claim(), EvidenceLevel.C, ())
        with mock.patch.object(Answer, "add_claim", side_effect=err):
            _attach_claim_safely(a, row, "badge")
        self.assertEqual(
            _trace_count(a, "wording_rejected"), 1,
            "a strict-wording rejection must be traced, not silently dropped",
        )


class PopulationEffectIndexCache(unittest.TestCase):
    def setUp(self):
        _build_population_effect_index.cache_clear()
        self.addCleanup(_build_population_effect_index.cache_clear)

    def test_registry_fault_returns_empty_without_poisoning_cache(self):
        with mock.patch(
            "cannavec_science.populations.all_populations",
            side_effect=RuntimeError("registry down"),
        ):
            self.assertEqual(
                _population_effect_index(), {},
                "a registry fault degrades to empty",
            )

        # The bug being pinned: the old lru_cache memoised that empty dict for
        # the whole process. A working registry on the next call must rebuild.
        cit = SimpleNamespace(
            pmid="222", n=100, comparator="placebo", primary_outcome="pain",
            effect_size="-1.2", confidence_interval="-2.0 to -0.4", nnt="5",
        )
        rows = [SimpleNamespace(citations=[cit])]
        with mock.patch(
            "cannavec_science.populations.all_populations", return_value=rows
        ):
            rebuilt = _population_effect_index()
        self.assertGreater(
            len(rebuilt), 0,
            "failure must not be cached — a later good call has to rebuild",
        )


class CitationDedupConsistency(unittest.TestCase):
    def test_url_only_matches_when_no_pmid_or_doi(self):
        self.assertTrue(
            _is_same_citation(
                Citation(label="a", url="u"), Citation(label="b", url="u")
            )
        )
        self.assertFalse(
            _is_same_citation(
                Citation(label="a", pmid="9", url="u"),
                Citation(label="b", url="u"),
            ),
            "a pmid-bearing citation is not a dup by URL alone",
        )

    def test_add_citation_and_merge_agree_on_identity(self):
        a1 = Answer(prompt="q")
        a1.add_citation(Citation(label="x", pmid="1", url="u"))
        a1.add_citation(Citation(label="x2", pmid="1", url="other"))
        self.assertEqual(len(a1.citations), 1, "same PMID is one citation")

        a2 = Answer(prompt="q")
        a2.add_citation(Citation(label="y", pmid="1", url="u"))
        self.assertEqual(
            len(merge_citations([a1, a2])), 1,
            "merge must use the same identity rule as add_citation",
        )


if __name__ == "__main__":
    unittest.main()
