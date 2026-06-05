"""Tests for `cannavec_science.flywheel` — the §IX expert-gated flywheel.

Fully offline and hermetic: identifier audits use injected esummary fixtures,
discovery is never called (candidates are passed directly), and every test
writes to a fresh tmp store dir so the shipped ``data/`` is untouched.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import flywheel as fw  # noqa: E402
from cannavec_science.flywheel import Lane  # noqa: E402
from cannavec_science.ranker import Candidate  # noqa: E402


# ── fixtures ──────────────────────────────────────────────────────────────

def esummary(pmid: str, *, retracted: bool = False,
             design: str = "Randomized Controlled Trial") -> str:
    pubtype = ["Journal Article", design]
    if retracted:
        pubtype = ["Journal Article", "Retracted Publication"]
    return json.dumps({
        "header": {"type": "esummary"},
        "result": {"uids": [pmid], pmid: {
            "uid": pmid, "pubdate": "2019 Jan 1", "source": "N Engl J Med",
            "authors": [{"name": "Devinsky O", "authtype": "Author"}],
            "title": "Trial of Cannabidiol for Seizures",
            "pubtype": pubtype,
        }},
    })


def not_found(pmid: str) -> str:
    return json.dumps({"result": {"uids": [pmid],
                                  pmid: {"uid": pmid, "error": "cannot get document summary"}}})


ABSTRACT = ("In this randomized controlled trial, cannabidiol reduced the frequency "
            "of convulsive seizures compared with placebo in patients with Dravet "
            "syndrome.")
CLAIM = ("Cannabidiol reduced convulsive seizure frequency versus placebo in a "
         "randomized controlled trial.")


def good_fetcher(pmid="30000001"):
    return lambda url: esummary(pmid)


def url_fetcher(url: str) -> str:
    """Return an esummary keyed to whichever PMID the request URL carries."""
    import re
    m = re.search(r"\d{6,9}", url)
    return esummary(m.group(0)) if m else not_found("0")


def candidate(identifier="30000001", design="Randomized Controlled Trial"):
    return Candidate(identifier=identifier, title="Cannabidiol for seizures",
                     abstract=ABSTRACT, study_types=(design,), topic="epilepsy")


class _StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ── the gate, lane by lane ─────────────────────────────────────────────────

class TestGate(_StoreCase):
    def test_basic_approvable(self) -> None:
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=good_fetcher())
        self.assertEqual(g.lane, Lane.BASIC_APPROVABLE)
        self.assertEqual(g.grade, "Level C")
        self.assertTrue(g.support_quote)
        self.assertEqual(g.checks["identifier"], "verified")
        self.assertEqual(g.checks["claim_support"], "supported")
        self.assertEqual(g.checks["rigor"], "clean")
        self.assertEqual(g.fatal, ())
        self.assertEqual(g.flags, ())

    def test_reject_not_found(self) -> None:
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=lambda u: not_found("30000001"))
        self.assertEqual(g.lane, Lane.REJECT)
        self.assertTrue(any("does not resolve" in r for r in g.fatal))

    def test_reject_retracted(self) -> None:
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=lambda u: esummary("30000001", retracted=True))
        self.assertEqual(g.lane, Lane.REJECT)
        self.assertTrue(any("RETRACTED" in r for r in g.fatal))

    def test_reject_claim_contradicted(self) -> None:
        contradicting = ("cannabidiol increased the frequency of convulsive seizures "
                         "compared with placebo.")
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=contradicting,
                    verify_fetcher=good_fetcher())
        self.assertEqual(g.lane, Lane.REJECT)
        self.assertEqual(g.checks["claim_support"], "contradiction")

    def test_reject_claim_unverified(self) -> None:
        # Title *and* abstract lack the claimed entity → the source is not about
        # the claim → UNVERIFIED → reject.
        off_topic = Candidate(identifier="30000001", title="Ibuprofen for headache",
                              abstract="Ibuprofen reduced headache severity in adults.",
                              study_types=("Randomized Controlled Trial",))
        g = fw.gate(off_topic, claim_text=CLAIM,
                    abstract="Ibuprofen reduced headache severity in adults.",
                    verify_fetcher=good_fetcher())
        self.assertEqual(g.lane, Lane.REJECT)
        self.assertEqual(g.checks["claim_support"], "unverified")

    def test_reject_no_identifier(self) -> None:
        g = fw.gate(Candidate(identifier="", title="x"), claim_text="Cannabidiol helps")
        self.assertEqual(g.lane, Lane.REJECT)

    def test_needs_expert_when_identifier_not_verified(self) -> None:
        # No verify_fetcher and no --network → identifier unverified → held.
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT)
        self.assertEqual(g.lane, Lane.NEEDS_EXPERT)
        self.assertEqual(g.checks["identifier"], "unverified")

    def test_needs_expert_when_no_abstract(self) -> None:
        g = fw.gate(Candidate(identifier="30000001", title="Cannabidiol for seizures"),
                    claim_text=CLAIM, abstract="", verify_fetcher=good_fetcher())
        self.assertEqual(g.lane, Lane.NEEDS_EXPERT)
        self.assertEqual(g.checks["claim_support"], "no_text")

    def test_needs_expert_for_synthesis_grade(self) -> None:
        g = fw.gate(candidate(design="Systematic Review"), claim_text=CLAIM,
                    abstract=ABSTRACT, verify_fetcher=good_fetcher())
        self.assertEqual(g.lane, Lane.NEEDS_EXPERT)
        self.assertEqual(g.grade, "Level B")  # never auto-A
        self.assertTrue(any("clinical-depth" in f for f in g.flags))

    def test_grade_never_level_a(self) -> None:
        for design in ("Systematic Review", "Meta-Analysis", "Randomized Controlled Trial",
                       "Cohort Study", "Case Report", "in vitro"):
            g = fw.gate(candidate(design=design), claim_text=CLAIM, abstract=ABSTRACT,
                        verify_fetcher=good_fetcher())
            self.assertNotEqual(g.grade, "Level A", design)


# ── stage / route ──────────────────────────────────────────────────────────

class TestStage(_StoreCase):
    def test_stage_writes_pending(self) -> None:
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=good_fetcher())
        sc = fw.stage(candidate(), g, store_dir=self.dir)
        self.assertIsNotNone(sc)
        self.assertEqual(sc.status, "pending")
        self.assertEqual(sc.lane, Lane.BASIC_APPROVABLE.value)
        pending = fw.queue(store_dir=self.dir)
        self.assertEqual(len(pending), 1)

    def test_stage_is_idempotent(self) -> None:
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=good_fetcher())
        self.assertIsNotNone(fw.stage(candidate(), g, store_dir=self.dir))
        self.assertIsNone(fw.stage(candidate(), g, store_dir=self.dir))
        self.assertEqual(len(fw.queue(store_dir=self.dir)), 1)

    def test_rejected_is_recorded_not_dropped(self) -> None:
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=lambda u: not_found("30000001"))
        sc = fw.stage(candidate(), g, store_dir=self.dir)
        self.assertEqual(sc.status, "rejected")
        rejected = fw.queue(status="rejected", store_dir=self.dir)
        self.assertEqual(len(rejected), 1)


# ── orchestrator ───────────────────────────────────────────────────────────

class TestRunFlywheel(_StoreCase):
    def test_offline_turn_counts_lanes(self) -> None:
        cands = [candidate("30000001"), candidate("30000002", design="Systematic Review"),
                 candidate("30000003")]
        claims = {c.identifier: CLAIM for c in cands}
        abstracts = {c.identifier: ABSTRACT for c in cands}
        report = fw.run_flywheel(
            "cannabidiol for drug-resistant seizures",
            extra_candidates=cands, claims=claims, abstracts=abstracts,
            verify_fetcher=url_fetcher, store_dir=self.dir,
        )
        self.assertEqual(report.candidates, 3)
        # two RCTs → basic; one SR → needs expert.
        self.assertEqual(report.basic_approvable, 2)
        self.assertEqual(report.needs_expert, 1)
        self.assertEqual(report.rejected, 0)
        self.assertEqual(report.topic, "epilepsy")

    def test_verify_fetcher_keyed_per_identifier(self) -> None:
        # A fetcher that 404s one PMID rejects exactly that candidate.
        def fetcher(url):
            return not_found("30000002") if "30000002" in url else esummary("30000001")
        cands = [candidate("30000001"), candidate("30000002")]
        report = fw.run_flywheel(
            "cannabidiol seizures",
            extra_candidates=cands,
            claims={c.identifier: CLAIM for c in cands},
            abstracts={c.identifier: ABSTRACT for c in cands},
            verify_fetcher=fetcher, store_dir=self.dir,
        )
        self.assertEqual(report.basic_approvable, 1)
        self.assertEqual(report.rejected, 1)


# ── demand-driven sweep (§IX) ──────────────────────────────────────────────

class _Hit:
    def __init__(self, pmid, title, abstract):
        self.pmid, self.title, self.abstract = pmid, title, abstract

    def to_dict(self):
        return {"pmid": self.pmid, "title": self.title, "abstract": self.abstract,
                "year": 2021, "pubtypes": ["Randomized Controlled Trial"],
                "provenance": "live_pubmed",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"}


class TestSweep(_StoreCase):
    def test_topic_query_known_and_fallback(self) -> None:
        from cannavec_science.demand import topic_query
        self.assertIn("Crohn", topic_query("ibd"))
        self.assertIn("fibromyalgia", topic_query("fibromyalgia"))
        # unknown-but-classified topic → generic cannabis query over the name
        self.assertIn("cannabis", topic_query("some_new_topic").lower())

    def test_sweep_reads_holes_and_stages(self) -> None:
        from cannavec_science import demand
        dd = tempfile.mkdtemp()
        try:
            for _ in range(3):
                demand.record_demand("cannabis for Crohn's", n_curated_claims=0,
                                     store_dir=dd)

            def runner(query, since, n):
                return [_Hit("40000001", "Cannabidiol in Crohn's RCT",
                             "In Crohn's disease, cannabidiol reduced disease activity "
                             "versus placebo.")]

            reports = fw.sweep_holes(
                n=3, runners={"pubmed": runner}, sources=["pubmed"],
                verify_fetcher=lambda u: esummary("40000001"),
                store_dir=self.dir, demand_store_dir=dd,
            )
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].topic, "ibd")
            self.assertEqual(reports[0].basic_approvable, 1)
            self.assertEqual([q["identifier"] for q in fw.queue(store_dir=self.dir)],
                             ["40000001"])
        finally:
            import shutil
            shutil.rmtree(dd, ignore_errors=True)

    def test_sweep_explicit_topics(self) -> None:
        reports = fw.sweep_holes(topics=["ibd", "fibromyalgia"], live=False,
                                 store_dir=self.dir)
        self.assertEqual([r.topic for r in reports], ["ibd", "fibromyalgia"])


# ── human-gated apply / reject / revoke (§IX) ──────────────────────────────

class TestApply(_StoreCase):
    def _stage_basic(self, ident="30000001"):
        g = fw.gate(candidate(ident), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=good_fetcher(ident))
        return fw.stage(candidate(ident), g, store_dir=self.dir)

    def test_apply_requires_named_approver(self) -> None:
        self._stage_basic()
        res = fw.apply_promotion("30000001", approver="  ", store_dir=self.dir)
        self.assertFalse(res.ok)
        self.assertIn("approver", res.reason)
        self.assertEqual(fw.verified_sources(store_dir=self.dir), [])

    def test_apply_promotes_basic_lane(self) -> None:
        self._stage_basic()
        res = fw.apply_promotion("30000001", approver="curator@cannavec",
                                 store_dir=self.dir)
        self.assertTrue(res.ok, res.reason)
        verified = fw.verified_sources(store_dir=self.dir)
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified[0]["approver"], "curator@cannavec")
        self.assertEqual(verified[0]["status"], "verified")
        # the staging row is now approved, not pending.
        self.assertEqual(fw.queue(store_dir=self.dir), [])
        self.assertEqual(len(fw.queue(status="approved", store_dir=self.dir)), 1)

    def test_apply_refuses_needs_expert_without_override(self) -> None:
        g = fw.gate(candidate(design="Systematic Review"), claim_text=CLAIM,
                    abstract=ABSTRACT, verify_fetcher=good_fetcher())
        fw.stage(candidate(design="Systematic Review"), g, store_dir=self.dir)
        res = fw.apply_promotion("30000001", approver="curator", store_dir=self.dir)
        self.assertFalse(res.ok)
        self.assertIn("NEEDS_EXPERT", res.reason)
        # ...but an expert override promotes it.
        res2 = fw.apply_promotion("30000001", approver="prof@uni",
                                  allow_expert_lane=True, store_dir=self.dir)
        self.assertTrue(res2.ok, res2.reason)

    def test_apply_refuses_rejected(self) -> None:
        g = fw.gate(candidate(), claim_text=CLAIM, abstract=ABSTRACT,
                    verify_fetcher=lambda u: not_found("30000001"))
        fw.stage(candidate(), g, store_dir=self.dir)
        res = fw.apply_promotion("30000001", approver="curator", store_dir=self.dir)
        self.assertFalse(res.ok)

    def test_apply_unknown_identifier(self) -> None:
        res = fw.apply_promotion("99999999", approver="curator", store_dir=self.dir)
        self.assertFalse(res.ok)
        self.assertIn("not in the staging queue", res.reason)

    def test_apply_rechecks_retraction_at_promotion_time(self) -> None:
        self._stage_basic()
        # A row that became retracted *after* staging must not promote (§IX).
        fake = mock.Mock()
        fake.status.value = "retracted"
        with mock.patch("cannavec_science.retraction.is_retracted", return_value=fake):
            res = fw.apply_promotion("30000001", approver="curator", store_dir=self.dir)
        self.assertFalse(res.ok)
        self.assertIn("retracted", res.reason.lower())
        self.assertEqual(fw.verified_sources(store_dir=self.dir), [])

    def test_revoke_is_reversible(self) -> None:
        self._stage_basic()
        fw.apply_promotion("30000001", approver="curator", store_dir=self.dir)
        res = fw.revoke_promotion("30000001", approver="curator", reason="bad read",
                                  store_dir=self.dir)
        self.assertTrue(res.ok)
        self.assertEqual(fw.verified_sources(store_dir=self.dir), [])
        # the staging row is returned to pending so it can be re-decided.
        self.assertEqual(len(fw.queue(store_dir=self.dir)), 1)

    def test_reject_candidate(self) -> None:
        self._stage_basic()
        res = fw.reject_candidate("30000001", approver="curator", reason="off-topic",
                                  store_dir=self.dir)
        self.assertTrue(res.ok)
        self.assertEqual(fw.queue(store_dir=self.dir), [])
        self.assertEqual(len(fw.queue(status="rejected", store_dir=self.dir)), 1)


# ── stats / exclusion ──────────────────────────────────────────────────────

class TestStatsAndExclusion(_StoreCase):
    def test_defect_rate_is_measured(self) -> None:
        # one basic, one reject → defect_rate 0.5
        fw.stage(candidate("30000001"),
                 fw.gate(candidate("30000001"), claim_text=CLAIM, abstract=ABSTRACT,
                         verify_fetcher=good_fetcher("30000001")),
                 store_dir=self.dir)
        fw.stage(candidate("30000002"),
                 fw.gate(candidate("30000002"), claim_text=CLAIM, abstract=ABSTRACT,
                         verify_fetcher=lambda u: not_found("30000002")),
                 store_dir=self.dir)
        s = fw.stats(self.dir)
        self.assertEqual(s["scanned"], 2)
        self.assertEqual(s["rejected"], 1)
        self.assertAlmostEqual(s["defect_rate"], 0.5)
        self.assertEqual(s["queue_pending_basic_approvable"], 1)
        self.assertEqual(s["target"], 1500)

    def test_curated_identifiers_nonempty_and_excluded(self) -> None:
        ids = fw.curated_identifiers()
        # ~155 curated PMIDs across the registries; Devinsky 2017 is one of them.
        self.assertGreater(len(ids), 50)
        self.assertIn("28538134", ids)
        # fanout must not re-surface an already-curated identifier.
        c = Candidate(identifier="28538134", title="Cannabidiol for Dravet",
                      abstract=ABSTRACT, study_types=("Randomized Controlled Trial",))
        out = fw.fanout("cannabidiol dravet", extra_candidates=[c], store_dir=self.dir)
        self.assertEqual([x.identifier for x in out], [])

    def test_stats_progress_to_target(self) -> None:
        s = fw.stats(self.dir)
        self.assertEqual(s["verified_tier"], 0)
        self.assertGreater(s["curated_registry_identifiers"], 50)
        self.assertEqual(
            s["remaining_to_target"],
            max(0, 1500 - s["verified_plus_curated"]),
        )


if __name__ == "__main__":
    unittest.main()
