"""Tests for the reporting-rigor module (spec 006 US5 / FR-005)."""

from __future__ import annotations

import unittest

from cannavec_science.reporting_rigor import (
    ReportingGuideline,
    ReportingGuidelineViolation,
    detect_missing_consort,
    detect_missing_prisma,
    detect_missing_strobe,
    detect_missing_rob2,
    detect_missing_robins_i,
    detect_missing_amstar2,
    run_reporting_rigor_checks,
    REPORTING_GUIDELINE_PMIDS,
)
from cannavec_science.rigor_checks import run_rigor_checks


class GuidelinePmidTableTests(unittest.TestCase):
    def test_all_pmids_present(self):
        # Schulz 2010 BMJ, Page 2021 BMJ, von Elm 2007, Sterne 2019,
        # Sterne 2016, Shea 2017.
        for k, pmid in (
            (ReportingGuideline.CONSORT, "20335313"),
            (ReportingGuideline.PRISMA, "33781993"),
            (ReportingGuideline.STROBE, "17938396"),
            (ReportingGuideline.ROB_2, "31462531"),
            (ReportingGuideline.ROBINS_I, "27733354"),
            (ReportingGuideline.AMSTAR_2, "28935701"),
        ):
            self.assertEqual(REPORTING_GUIDELINE_PMIDS[k], pmid)


class ConsortTests(unittest.TestCase):
    def test_rct_without_consort_fires(self):
        v = detect_missing_consort(
            "we conducted a randomized controlled trial of CBD in chronic pain"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.CONSORT)
        self.assertEqual(v[0].recommendation_pmid, "20335313")

    def test_rct_double_blind_fires(self):
        v = detect_missing_consort(
            "this double-blind placebo-controlled randomized trial of nabilone"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.CONSORT)

    def test_rct_with_consort_silent(self):
        v = detect_missing_consort(
            "we conducted a CONSORT-2010 compliant randomized controlled trial of CBD"
        )
        self.assertEqual(v, ())

    def test_observational_does_not_fire_consort(self):
        v = detect_missing_consort(
            "this observational cohort of medical-cannabis users at the VA"
        )
        self.assertEqual(v, ())


class PrismaTests(unittest.TestCase):
    def test_sr_without_prisma_fires(self):
        v = detect_missing_prisma(
            "this systematic review of cannabinoid trials in neuropathic pain"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.PRISMA)
        self.assertEqual(v[0].recommendation_pmid, "33781993")

    def test_meta_analysis_fires(self):
        v = detect_missing_prisma(
            "we performed a meta-analysis of 14 cannabinoid RCTs in chronic pain"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.PRISMA)

    def test_sr_with_prisma_silent(self):
        v = detect_missing_prisma(
            "this PRISMA-2020 compliant systematic review of cannabinoid trials"
        )
        self.assertEqual(v, ())


class StrobeTests(unittest.TestCase):
    def test_observational_without_strobe_fires(self):
        v = detect_missing_strobe(
            "we ran a prospective observational cohort of MMJ-card holders"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.STROBE)
        self.assertEqual(v[0].recommendation_pmid, "17938396")

    def test_case_control_without_strobe_fires(self):
        v = detect_missing_strobe(
            "we performed a case-control study comparing cannabis users to controls"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.STROBE)

    def test_observational_with_strobe_silent(self):
        v = detect_missing_strobe(
            "STROBE-compliant observational cohort of medical cannabis patients"
        )
        self.assertEqual(v, ())


class Rob2Tests(unittest.TestCase):
    def test_rct_bias_appraisal_without_rob2_fires(self):
        v = detect_missing_rob2(
            "we appraised risk of bias in the included randomized trials"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.ROB_2)
        self.assertEqual(v[0].recommendation_pmid, "31462531")

    def test_rct_with_rob2_silent(self):
        v = detect_missing_rob2(
            "we used the Cochrane RoB 2 tool to appraise risk of bias in the RCTs"
        )
        self.assertEqual(v, ())

    def test_rob2_lowercase_acknowledgment_silent(self):
        v = detect_missing_rob2(
            "we used Cochrane risk of bias 2 to appraise the included RCTs"
        )
        self.assertEqual(v, ())


class RobinsITests(unittest.TestCase):
    def test_nrsi_bias_without_robins_i_fires(self):
        v = detect_missing_robins_i(
            "we appraised risk of bias in the non-randomized intervention studies"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.ROBINS_I)
        self.assertEqual(v[0].recommendation_pmid, "27733354")

    def test_robins_i_acknowledgment_silent(self):
        v = detect_missing_robins_i(
            "we used ROBINS-I to appraise risk of bias in non-randomized studies"
        )
        self.assertEqual(v, ())


class Amstar2Tests(unittest.TestCase):
    def test_sr_quality_without_amstar2_fires(self):
        v = detect_missing_amstar2(
            "we evaluated methodological quality of the included systematic reviews"
        )
        self.assertTrue(v)
        self.assertEqual(v[0].kind, ReportingGuideline.AMSTAR_2)
        self.assertEqual(v[0].recommendation_pmid, "28935701")

    def test_amstar2_acknowledgment_silent(self):
        v = detect_missing_amstar2(
            "we used AMSTAR-2 to evaluate the quality of the included reviews"
        )
        self.assertEqual(v, ())


class RunReportingRigorTests(unittest.TestCase):
    def test_run_returns_tuple(self):
        out = run_reporting_rigor_checks(
            "we conducted a randomized trial of CBD in chronic pain"
        )
        self.assertTrue(isinstance(out, tuple))
        self.assertTrue(out)
        kinds = {v.kind for v in out}
        self.assertIn(ReportingGuideline.CONSORT, kinds)

    def test_empty_text_clean(self):
        self.assertEqual(run_reporting_rigor_checks(""), ())

    def test_neutral_prose_clean(self):
        self.assertEqual(
            run_reporting_rigor_checks(
                "Cannabis is a flowering plant in the family Cannabaceae."
            ),
            (),
        )


class RigorCheckReportIntegrationTests(unittest.TestCase):
    def test_run_rigor_checks_includes_reporting_rigor(self):
        rep = run_rigor_checks(
            "we ran a systematic review and meta-analysis of cannabinoid trials"
        )
        # The rigor report now has a reporting_rigor_violations field.
        self.assertTrue(hasattr(rep, "reporting_rigor_violations"))
        self.assertTrue(rep.reporting_rigor_violations)
        kinds = {v.kind for v in rep.reporting_rigor_violations}
        self.assertIn(ReportingGuideline.PRISMA, kinds)

    def test_clean_property_includes_reporting_rigor(self):
        rep = run_rigor_checks(
            "this prospective observational cohort of medical-cannabis users"
        )
        self.assertFalse(rep.clean)

    def test_summary_renders_reporting_rigor_section(self):
        rep = run_rigor_checks(
            "we performed a randomized controlled trial of nabilone in chronic pain"
        )
        md = rep.summary()
        self.assertIn("Reporting-rigor", md)


class ViolationShapeTests(unittest.TestCase):
    def test_violation_has_anchor(self):
        v = detect_missing_consort(
            "we conducted a randomized controlled trial of CBD in chronic pain"
        )
        self.assertTrue(v[0].why)
        self.assertTrue(v[0].anchor_text)
        # Span valid
        start, end = v[0].span
        self.assertGreaterEqual(start, 0)
        self.assertGreater(end, start)


if __name__ == "__main__":
    unittest.main()
