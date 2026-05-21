"""Tests for the citation-network + field-pushback module (spec 002 US4)."""

import json
import unittest

from cannavec_science.citation_network import (
    CitationNetworkBlock,
    FieldPushback,
    PushbackAggregate,
    ReplicationStatus,
    build_citation_network,
    classify_replication,
    fetch_forward_cites,
    render_markdown,
)


# ── Fixtures ─────────────────────────────────────────────────────


def _elink_payload(cite_pmids):
    return json.dumps({
        "linksets": [{
            "linksetdbs": [{
                "linkname": "pubmed_pubmed_citedin",
                "links": list(cite_pmids),
            }],
        }],
    })


def _esummary_payload(pmid_titles):
    """pmid_titles is a list of (pmid, title) pairs."""
    return json.dumps({
        "result": {
            **{p: {"title": t} for p, t in pmid_titles},
            "uids": [p for p, _ in pmid_titles],
        },
    })


def _empty_elink_payload():
    return json.dumps({"linksets": [{"linksetdbs": []}]})


# ── Replication classifier ───────────────────────────────────────


class ReplicationClassifierTests(unittest.TestCase):
    def test_replicated(self):
        abstracts = (
            "We replicated the prior finding of CBD efficacy.",
            "We reproduced the previous result of THC sedation.",
        )
        self.assertEqual(
            classify_replication(abstracts),
            ReplicationStatus.REPLICATED,
        )

    def test_replication_failed(self):
        abstracts = (
            "We failed to replicate the prior finding.",
            "We did not reproduce the previous result.",
        )
        self.assertEqual(
            classify_replication(abstracts),
            ReplicationStatus.REPLICATION_FAILED,
        )

    def test_mixed_replication(self):
        abstracts = (
            "We replicated the prior finding.",
            "We failed to replicate the same effect.",
        )
        self.assertEqual(
            classify_replication(abstracts),
            ReplicationStatus.MIXED,
        )

    def test_not_reported(self):
        self.assertEqual(
            classify_replication(("Plain abstract.", "Another one.")),
            ReplicationStatus.NOT_REPORTED,
        )

    def test_empty(self):
        self.assertEqual(
            classify_replication(()),
            ReplicationStatus.NOT_REPORTED,
        )


# ── Forward-cite fetch ──────────────────────────────────────────


class FetchForwardCitesTests(unittest.TestCase):
    def test_happy_path(self):
        def stub(url: str) -> str:
            return _elink_payload(["11111", "22222", "33333"])

        cites = fetch_forward_cites("28538134", fetcher=stub)
        self.assertEqual(cites, ("11111", "22222", "33333"))

    def test_empty_linksets(self):
        def stub(url: str) -> str:
            return _empty_elink_payload()

        cites = fetch_forward_cites("28538134", fetcher=stub)
        self.assertEqual(cites, ())

    def test_dedup(self):
        def stub(url: str) -> str:
            return _elink_payload(["11111", "11111", "22222"])

        cites = fetch_forward_cites("28538134", fetcher=stub)
        self.assertEqual(cites, ("11111", "22222"))

    def test_invalid_json(self):
        def stub(url: str) -> str:
            return "not json"

        cites = fetch_forward_cites("28538134", fetcher=stub)
        self.assertEqual(cites, ())


# ── Build citation network ──────────────────────────────────────


class BuildNetworkTests(unittest.TestCase):
    def test_support_heavy_signal(self):
        def stub(url: str) -> str:
            if "elink" in url:
                return _elink_payload(["1", "2", "3", "4", "5"])
            return _esummary_payload([
                ("1", "Significantly improved seizure frequency."),
                ("2", "Efficacy was demonstrated for adjunctive use."),
                ("3", "Significantly reduced convulsive episodes."),
                ("4", "Routine clinical observation."),
                ("5", "Mechanism unclear."),
            ])

        block = build_citation_network("28538134", fetcher=stub)
        self.assertEqual(block.count, 5)
        self.assertEqual(
            block.field_pushback_signal.aggregate,
            PushbackAggregate.SUPPORT_HEAVY,
        )
        self.assertFalse(block.grade_downgrade_recommended)

    def test_refute_heavy_signal_recommends_downgrade(self):
        def stub(url: str) -> str:
            if "elink" in url:
                return _elink_payload(["1", "2", "3", "4", "5"])
            return _esummary_payload([
                ("1", "No significant difference was observed."),
                ("2", "Did not improve outcomes."),
                ("3", "Failed to show benefit."),
                ("4", "Clinically significant improvement."),
                ("5", "Mechanism unclear."),
            ])

        block = build_citation_network("28538134", fetcher=stub)
        self.assertEqual(
            block.field_pushback_signal.aggregate,
            PushbackAggregate.REFUTE_HEAVY,
        )
        self.assertTrue(block.grade_downgrade_recommended)

    def test_mixed_signal(self):
        def stub(url: str) -> str:
            if "elink" in url:
                return _elink_payload(["1", "2", "3", "4"])
            return _esummary_payload([
                ("1", "Significantly improved outcomes."),
                ("2", "Did not improve outcomes."),
                ("3", "Significantly improved compared to baseline."),
                ("4", "Did not differ from placebo."),
            ])

        block = build_citation_network("28538134", fetcher=stub)
        self.assertEqual(
            block.field_pushback_signal.aggregate,
            PushbackAggregate.MIXED,
        )

    def test_neutral_signal(self):
        def stub(url: str) -> str:
            if "elink" in url:
                return _elink_payload(["1", "2", "3"])
            return _esummary_payload([
                ("1", "Pharmacokinetic study."),
                ("2", "Mechanism of action study."),
                ("3", "Receptor binding assay."),
            ])

        block = build_citation_network("28538134", fetcher=stub)
        self.assertEqual(
            block.field_pushback_signal.aggregate,
            PushbackAggregate.NEUTRAL,
        )

    def test_insufficient_with_few_cites(self):
        def stub(url: str) -> str:
            if "elink" in url:
                return _elink_payload(["1"])
            return _esummary_payload([("1", "Some title.")])

        block = build_citation_network("28538134", fetcher=stub)
        self.assertEqual(
            block.field_pushback_signal.aggregate,
            PushbackAggregate.INSUFFICIENT,
        )

    def test_zero_cites(self):
        def stub(url: str) -> str:
            return _empty_elink_payload()

        block = build_citation_network("28538134", fetcher=stub)
        self.assertEqual(block.count, 0)
        self.assertEqual(
            block.field_pushback_signal.aggregate,
            PushbackAggregate.INSUFFICIENT,
        )

    def test_network_error_graceful(self):
        def stub(url: str) -> str:
            raise IOError("network down")

        block = build_citation_network("28538134", fetcher=stub)
        self.assertEqual(block.count, 0)
        self.assertIsNotNone(block.error)


# ── Integration with apply_grade_modifiers ─────────────────────


class GradeIntegrationTests(unittest.TestCase):
    def test_refute_heavy_triggers_one_level_downgrade(self):
        from cannavec_science.evidence import (
            EvidenceLevel, apply_grade_modifiers,
        )
        # Without the signal, Level B stays B.
        base = apply_grade_modifiers(EvidenceLevel.B)
        self.assertEqual(base, EvidenceLevel.B)
        # With inconsistency_serious (the bit citation_network flips),
        # B → C.
        downgraded = apply_grade_modifiers(
            EvidenceLevel.B, inconsistency_serious=True,
        )
        self.assertEqual(downgraded, EvidenceLevel.C)


# ── Renderer ─────────────────────────────────────────────────────


class RendererTests(unittest.TestCase):
    def test_render_includes_pmid_and_count(self):
        def stub(url: str) -> str:
            if "elink" in url:
                return _elink_payload(["1", "2", "3"])
            return _esummary_payload([
                ("1", "Significantly improved outcomes."),
                ("2", "Significantly reduced symptoms."),
                ("3", "Efficacy was demonstrated."),
            ])

        block = build_citation_network("28538134", fetcher=stub)
        md = render_markdown(block)
        self.assertIn("28538134", md)
        self.assertIn("Forward citations", md)
        self.assertIn("support_heavy", md)

    def test_render_error_state(self):
        block = CitationNetworkBlock(
            pmid="28538134", count=0, error="rate limited",
        )
        md = render_markdown(block)
        self.assertIn("unavailable", md)
        self.assertIn("rate limited", md)


# ── Serialisation ────────────────────────────────────────────────


class SerialisationTests(unittest.TestCase):
    def test_to_dict_round_trip(self):
        block = CitationNetworkBlock(
            pmid="28538134", count=3,
            field_pushback_signal=FieldPushback(
                supports=2, refutes=0, neutral=1,
                aggregate=PushbackAggregate.SUPPORT_HEAVY,
            ),
            replication_status=ReplicationStatus.NOT_REPORTED,
            forward_pmids=("1", "2", "3"),
        )
        d = block.to_dict()
        self.assertEqual(d["pmid"], "28538134")
        self.assertEqual(d["count"], 3)
        self.assertEqual(d["field_pushback_signal"]["aggregate"], "support_heavy")


if __name__ == "__main__":
    unittest.main()
