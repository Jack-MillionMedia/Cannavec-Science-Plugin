"""Regression tests for the P0 fixes from the 2026-06 adversarial audit.

Each test pins a defect that an expert reviewer hit on the live API and
that was confirmed by ground-truth verification (PubMed / Crossref / §VII):

- c04 — the TSC efficacy claim cited the Dravet trial (PMID 28538134) and
  rendered Dravet effect numbers; it must cite the real TSC trial
  (Thiele 2021, PMID 33346789, GWPCARE6).
- c08 — a "CBD mechanism …" query surfaced a Δ⁹-THC-only CB1-desensitization
  claim; a compound-named query must not surface a *different* cannabinoid's
  claim.
- D5 — a single non-Cochrane journal SR (Whiting 2015 JAMA) yielded Level A,
  above its source's own certainty; §VII reserves Level A for a
  Cochrane/AHRQ/NICE SR or ≥ 2 aligned RCTs.
- D1 — a retracted live finding rendered with no badge in the /api/discover
  Markdown (the JSON carried the status); §VIII requires it be badged.
- D2 — /api/rigor rated text containing a retracted PMID as "clean"; the
  retraction scanner must run on the rigor surface.

All offline / stdlib-only (no network, no socket bind).
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import EvidenceLevel, ClaimType

_API_DIR = Path(__file__).resolve().parent.parent / "api"


def _load_api(module_name: str):
    """Load an ``api/<name>.py`` handler module by path (mirrors
    test_api_handlers); lets us call its pure helpers without a socket."""
    path = _API_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"api_{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestC04TscCitation(unittest.TestCase):
    """c04 — the TSC claim must cite the TSC trial, not the Dravet trial."""

    def test_tsc_claim_cites_thiele_not_dravet(self):
        a = compose_answer("cannabidiol for tuberous sclerosis complex")
        tsc_claims = [
            c for c in a.claims
            if c.population and "tuberous sclerosis" in c.population.lower()
        ]
        self.assertTrue(tsc_claims, "expected a TSC efficacy claim")
        pmids = {s.pmid for c in tsc_claims for s in c.sources if s.pmid}
        self.assertIn(
            "33346789", pmids,
            "TSC claim must cite the Thiele 2021 TSC RCT (GWPCARE6)",
        )
        self.assertNotIn(
            "28538134", pmids,
            "TSC claim must NOT cite the Dravet trial (28538134)",
        )

    def test_tsc_effect_block_is_not_dravet_numbers(self):
        from cannavec_science.answer import _effect_estimates_for_claim
        a = compose_answer("cannabidiol for tuberous sclerosis complex")
        tsc_claims = [
            c for c in a.claims
            if c.population and "tuberous sclerosis" in c.population.lower()
        ]
        self.assertTrue(tsc_claims)
        for c in tsc_claims:
            for est in _effect_estimates_for_claim(c):
                self.assertNotEqual(
                    est.pmid, "28538134",
                    "TSC claim must not render the Dravet effect estimate",
                )
                if est.primary_outcome:
                    self.assertNotIn(
                        "convulsive seizure", est.primary_outcome.lower(),
                        "TSC effect block must not be the Dravet endpoint",
                    )


class TestC08CompoundScope(unittest.TestCase):
    """c08 (fixed in P1) — a CBD mechanism query surfaces CBD's own receptor
    activity as first-class typed claims and no longer recovers an off-target
    Δ⁹-THC CB1-desensitization claim via the thin-answer BM25 fallback."""

    def _cbd_mechanism_answer(self):
        return compose_answer("CBD mechanism at 5-HT1A and TRPV1 receptors")

    def test_excludes_offtarget_thc_desensitization_claim(self):
        a = self._cbd_mechanism_answer()
        for c in a.claims:
            self.assertNotIn(
                "homologous desensitization", c.text,
                "a CBD mechanism query must not surface the Δ⁹-THC CB1-"
                "desensitization claim (off-target / wrong compound)",
            )

    def test_surfaces_cbd_5ht1a_and_trpv1_mechanism_claims(self):
        a = self._cbd_mechanism_answer()
        texts = " ||| ".join(c.text for c in a.claims)
        self.assertIn(
            "5-HT1A", texts,
            "CBD's 5-HT1A receptor activity (Russo 2005) must surface as a "
            "typed mechanism claim",
        )
        self.assertIn(
            "TRPV1", texts,
            "CBD's TRPV1 receptor activity (Bisogno 2001) must surface as a "
            "typed mechanism claim",
        )
        # the on-target claims must carry their primary-source citations
        pmids = {s.pmid for c in a.claims for s in c.sources if s.pmid}
        self.assertIn("16258853", pmids, "Russo 2005 (CBD/5-HT1A) must be cited")
        self.assertIn("11606325", pmids, "Bisogno 2001 (CBD/TRPV1) must be cited")


class TestMinorCannabinoidMechanismClaims(unittest.TestCase):
    """c08 extension — MINOR cannabinoids (CBG/THCV/CBN/CBC/CBDV) also surface
    their curated receptor activity as first-class MECHANISM claims on a
    MECHANISM-intent query, anchored to their primary sources."""

    def test_cbg_mechanism_query_surfaces_receptor_claims(self):
        a = compose_answer("cannabigerol CBG mechanism and receptor targets")
        texts = " ||| ".join(c.text for c in a.claims)
        # CBG is a selective α2-adrenoceptor agonist + 5-HT1A antagonist
        # (Cascio 2010, PMID 20002104).
        self.assertIn(
            "adrenoceptor", texts,
            "CBG's α2-adrenoceptor activity (Cascio 2010) must surface as a "
            "typed mechanism claim",
        )
        pmids = {s.pmid for c in a.claims for s in c.sources if s.pmid}
        self.assertIn("20002104", pmids, "Cascio 2010 (CBG receptor) must be cited")
        # every emitted mechanism claim is graded (Level C, in-vitro tier)
        for c in a.claims:
            self.assertTrue(c.best_supportable_grade(), "claim must carry a grade")

    def test_thcv_mechanism_query_surfaces_cb1(self):
        a = compose_answer("THCV mechanism at the CB1 receptor")
        self.assertTrue(
            any("CB1" in c.text and "THCV" in c.text for c in a.claims),
            "THCV's CB1 receptor activity must surface as a typed claim",
        )

    def test_non_mechanism_minor_query_does_not_flood(self):
        # A non-MECHANISM minor-cannabinoid query (definition intent) must NOT
        # emit receptor-mechanism claims — the monograph alone answers it.
        a = compose_answer("what is cannabigerol")
        self.assertFalse(
            any("adrenoceptor" in c.text for c in a.claims),
            "a definition query must not emit receptor-mechanism claims",
        )


class TestD5GradeLevelACap(unittest.TestCase):
    """D5 — a lone non-Cochrane journal SR must not reach Level A (§VII)."""

    def test_cinv_single_journal_sr_not_level_a(self):
        a = compose_answer(
            "dronabinol nabilone for chemotherapy-induced nausea and "
            "vomiting CINV"
        )
        cinv = [
            c for c in a.claims
            if c.population and "CINV" in c.population
        ]
        self.assertTrue(cinv, "expected a CINV claim")
        for c in cinv:
            self.assertLessEqual(
                c.best_supportable_grade().rank, EvidenceLevel.B.rank,
                "a single non-Cochrane JAMA SR must not yield Level A (§VII)",
            )

    def test_cochrane_backed_body_retains_level_a(self):
        # Regression guard against over-correction: a Cochrane-anchored body
        # of evidence (Mücke 2018) must KEEP Level A.
        a = compose_answer("cannabis for chronic neuropathic pain")
        grades = [
            c.best_supportable_grade() for c in a.claims
            if c.claim_type == ClaimType.CLINICAL_EFFICACY
        ]
        self.assertIn(
            EvidenceLevel.A, grades,
            "a Cochrane-anchored body of evidence should retain Level A",
        )


class TestD1DiscoverRetractionBadge(unittest.TestCase):
    """D1 — the discover Markdown must badge a retracted finding (§VIII)."""

    def test_retracted_finding_is_badged_clean_is_not(self):
        disc = _load_api("discover")
        result = {
            "query": "WIN 55212-2 glioma cell growth",
            "sources": {
                "pubmed": [
                    {"pmid": "11111111", "title": "A clean cannabinoid paper",
                     "retraction_status": "clean"},
                    {"pmid": "33977107",
                     "title": "Cannabinoid WIN 55,212-2 Inhibits Human Glioma "
                              "Cell Growth",
                     "retraction_status": "retracted"},
                ],
            },
            "synthesis": {"convergence": "WEAK"},
        }
        md = disc._markdown(result)
        retracted_line = next(
            (ln for ln in md.splitlines() if "33977107" in ln), ""
        )
        self.assertTrue(retracted_line, "retracted finding must appear")
        self.assertIn("⚠", retracted_line)
        self.assertIn("RETRACT", retracted_line.upper())
        clean_line = next(
            (ln for ln in md.splitlines() if "11111111" in ln), ""
        )
        self.assertTrue(clean_line)
        self.assertNotIn("⚠", clean_line)

    def test_expression_of_concern_is_badged(self):
        disc = _load_api("discover")
        result = {
            "query": "x",
            "sources": {"pubmed": [
                {"pmid": "22222222", "title": "EoC paper",
                 "retraction_status": "expression_of_concern"},
            ]},
        }
        md = disc._markdown(result)
        line = next((ln for ln in md.splitlines() if "22222222" in ln), "")
        self.assertIn("⚠", line)


class TestD2RigorRetractionScan(unittest.TestCase):
    """D2 — /api/rigor must flag a retracted PMID in pasted text."""

    def test_rigor_flags_retracted_pmid(self):
        rig = _load_api("rigor")
        report = rig._rigor_report(
            "A great source is PMID 32060308 which shows cannabidiol kills "
            "glioma cells"
        )
        self.assertFalse(
            report["clean"],
            "text citing a retracted PMID must not be reported as clean",
        )
        self.assertIn("32060308", json.dumps(report, default=str))

    def test_rigor_clean_text_stays_clean(self):
        rig = _load_api("rigor")
        report = rig._rigor_report(
            "Δ⁹-THC (CB1, UniProt P21554) at 10 mg oral, ~6% bioavailability "
            "in plasma."
        )
        self.assertTrue(report["clean"], "clean text must stay clean")


class TestD2CliRigorRetractionScan(unittest.TestCase):
    """D2 (surface parity) — the CLI ``rigor`` command must also flag a
    retracted PMID, not only /api/rigor."""

    def _run_cli_rigor(self, text):
        import contextlib
        import io
        from types import SimpleNamespace
        from cannavec_science.__main__ import _cmd_rigor
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_rigor(SimpleNamespace(text=text))
        return rc, buf.getvalue()

    def test_cli_rigor_flags_retracted_pmid(self):
        rc, out = self._run_cli_rigor(
            "see PMID 32060308 for cannabidiol glioma cell death"
        )
        self.assertEqual(rc, 1, "a retracted citation must yield a nonzero exit")
        self.assertIn("32060308", out)
        self.assertIn("Retracted citations:", out)

    def test_cli_rigor_clean_text_exit_zero(self):
        rc, out = self._run_cli_rigor(
            "Δ⁹-THC (CB1, UniProt P21554) at 10 mg oral, ~6% bioavailability "
            "in plasma."
        )
        self.assertEqual(rc, 0)
        self.assertIn("Clean.", out)


if __name__ == "__main__":
    unittest.main()
