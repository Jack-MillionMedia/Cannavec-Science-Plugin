"""Tests for the three new cannabis-rigor detectors shipped in spec 004 US2.

The three traps are:

- ``detect_thca_vs_thc_conflation`` — bare ``THC`` / ``CBD`` in a flower /
  cultivar / assay / pre-decarb context without ``THCA`` / ``CBDA``
  disambiguation.
- ``detect_matrix_unit_confusion`` — a concentration unit (``ng/mL``,
  ``%w/w``, ``mg/g`` …) cited near a cannabinoid name without an
  explicit matrix tag (``plasma``, ``flower``, ``in vitro`` …).
- ``detect_decarb_context_missing`` — a neutral-cannabinoid pharmacology
  claim sourced from a raw-extract / undecarbed / acid-form context.

Each detector follows the existing rigor-check convention: deterministic
regex, narrow positive fire, generous negation window, sentence-window
context disambiguation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.rigor_checks import (   # noqa: E402
    detect_decarb_context_missing,
    detect_matrix_unit_confusion,
    detect_thca_vs_thc_conflation,
    run_rigor_checks,
)


class TestThcaVsThcConflation(unittest.TestCase):
    """Bare ``THC`` / ``CBD`` paired with a flower/cultivar/assay context
    without THCA/CBDA disambiguation must fire."""

    def test_pct_thc_in_hplc_context_fires(self) -> None:
        text = "This cultivar tests at 22% THC by HPLC."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].cannabinoid, "THC")

    def test_cultivar_thc_label_fires(self) -> None:
        text = "Cultivar 'Skywalker OG' is labelled at 20% THC."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(len(hits), 1)

    def test_flower_pct_cbd_fires(self) -> None:
        text = "The flower contains 18% CBD by potency test."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].cannabinoid, "CBD")

    def test_lcms_cbd_pct_fires(self) -> None:
        text = "Raw plant sample measures 18.4% CBD by LC-MS."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_coa_thc_pct_fires(self) -> None:
        text = (
            "The COA reports a value of 22.4% THC for this batch — "
            "review attached."
        )
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(len(hits), 1)

    def test_thca_disambiguated_does_not_fire(self) -> None:
        text = (
            "This cultivar tests at 22% THCA by HPLC, equivalent to "
            "approximately 19.3% Δ⁹-THC after full decarboxylation."
        )
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(hits, ())

    def test_decarboxylation_disclaimer_blocks(self) -> None:
        text = (
            "Total THC = THCA + THC × 0.877 — the COA shows 22% THC "
            "equivalent post-decarboxylation."
        )
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(hits, ())

    def test_delta9_prefix_blocks(self) -> None:
        text = "This cultivar tests at 22% Δ⁹-THC by HPLC after full decarb."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(hits, ())

    def test_delta9_prefix_long_form_blocks(self) -> None:
        text = "This cultivar tests at 22% delta-9 THC by HPLC."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(hits, ())

    def test_thc_in_pharmacology_context_does_not_fire_here(self) -> None:
        """``"THC binds CB1"`` is an isomer-collapse hit, not a THCA-vs-THC
        hit. The two detectors carve out separate context buckets."""
        text = "THC binds CB1 with partial-agonist affinity."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(hits, ())

    def test_legal_status_thc_does_not_fire(self) -> None:
        text = "THC is Schedule I under the federal Controlled Substances Act."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(hits, ())

    def test_high_thc_class_label_alone_does_not_fire(self) -> None:
        """High-THC as a class label without an explicit %-claim is
        ambiguous but does not on its own conflate THCA with THC.

        Note: a pure ``high-THC cultivar`` phrasing without a percentage
        is colloquial; the detector does not fire on it. A future
        tightening could add this as a soft warning."""
        text = "Patients often select high-THC cultivars for symptom relief."
        hits = detect_thca_vs_thc_conflation(text)
        self.assertEqual(hits, ())


class TestMatrixUnitConfusion(unittest.TestCase):
    """A concentration value cited near a cannabinoid name without an
    explicit matrix tag must fire."""

    def test_ng_per_ml_no_matrix_fires(self) -> None:
        text = "CBD level was 150 ng/mL after the dose."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(len(hits), 1)

    def test_pct_ww_no_matrix_fires_when_cannabinoid_near(self) -> None:
        text = "The 22% w/w cannabinoid value is reported in the batch summary."
        hits = detect_matrix_unit_confusion(text)
        # The unit pairs with the cannabinoid term `cannabinoid` and
        # there is no matrix tag like "flower" / "extract" present.
        self.assertGreaterEqual(len(hits), 1)

    def test_mg_per_g_no_matrix_fires(self) -> None:
        text = "THCA content reported as 220 mg/g in the sample."
        # Note: 'sample' is not a matrix tag — we need 'flower', 'extract',
        # 'edible' explicitly.
        hits = detect_matrix_unit_confusion(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_plasma_tag_blocks(self) -> None:
        text = "Plasma CBD was 150 ng/mL one hour post-dose."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_cmax_implicit_plasma_blocks(self) -> None:
        text = "CBD C-max was 150 ng/mL after 750 mg oral dose."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_tmax_implicit_plasma_blocks(self) -> None:
        text = "Δ⁹-THC T-max of 8 ng/mL was reached at 60 minutes."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_in_vitro_buffer_tag_blocks(self) -> None:
        text = "Assay buffer THC concentration of 10 nM gave 50% inhibition."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_flower_tag_blocks(self) -> None:
        text = "Flower THCA value of 22% w/w by HPLC."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_extract_tag_blocks(self) -> None:
        text = "Extract CBD concentration of 800 mg/g was achieved."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_no_cannabinoid_nearby_does_not_fire(self) -> None:
        """A concentration unit without a cannabinoid name nearby is
        not the matrix-unit detector's concern."""
        text = "Blood glucose was 90 mg/dL fasting."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_topical_matrix_blocks(self) -> None:
        text = "Topical CBD cream contained 30 mg/g."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())

    def test_microsome_in_vitro_blocks(self) -> None:
        text = "Liver microsome incubation with CBD at 10 µM."
        hits = detect_matrix_unit_confusion(text)
        self.assertEqual(hits, ())


class TestDecarbContextMissing(unittest.TestCase):
    """A neutral-cannabinoid pharmacology claim sourced from a raw-extract
    / undecarbed / acid-form context must fire."""

    def test_raw_extract_cbd_inhibit_fires(self) -> None:
        text = (
            "CBD inhibited cytokine release at 10 µM in raw extract "
            "preparations from cannabis biomass."
        )
        hits = detect_decarb_context_missing(text)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].cannabinoid, "CBD")

    def test_unheated_thc_activate_fires(self) -> None:
        text = (
            "Unheated cannabis extract: THC activated TRPV1 channels at "
            "5 µM."
        )
        hits = detect_decarb_context_missing(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_acid_form_cbd_action_fires(self) -> None:
        text = (
            "From the acid-form preparation, CBD reduced inflammation "
            "in a dose-dependent manner."
        )
        hits = detect_decarb_context_missing(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_decarb_applied_blocks(self) -> None:
        text = (
            "CBD inhibited cytokine release at 10 µM; raw extract was "
            "decarboxylated to completion (heated to 110 °C for 30 min) "
            "prior to assay."
        )
        hits = detect_decarb_context_missing(text)
        self.assertEqual(hits, ())

    def test_thca_named_blocks(self) -> None:
        text = (
            "In raw extract, THCA inhibited COX-2 with an IC50 of "
            "200 nM (CBD itself was not measured)."
        )
        hits = detect_decarb_context_missing(text)
        self.assertEqual(hits, ())

    def test_delta9_thc_explicit_blocks(self) -> None:
        text = (
            "In raw extract heated to 130 °C, Δ⁹-THC inhibited adenylyl "
            "cyclase at 10 µM."
        )
        hits = detect_decarb_context_missing(text)
        # The decarb-applied phrase or the delta-9 prefix or both block this.
        self.assertEqual(hits, ())

    def test_no_raw_extract_context_does_not_fire(self) -> None:
        text = (
            "CBD inhibited cytokine release at 10 µM in plasma-spiked "
            "preparations."
        )
        hits = detect_decarb_context_missing(text)
        self.assertEqual(hits, ())

    def test_purified_isolate_does_not_fire(self) -> None:
        text = (
            "Purified CBD isolate (≥ 98% by HPLC) inhibited TRPV1 at "
            "5 µM."
        )
        hits = detect_decarb_context_missing(text)
        self.assertEqual(hits, ())


class TestRunRigorChecksAggregator(unittest.TestCase):
    """The aggregator must include all six checks."""

    def test_clean_text_passes_all_six(self) -> None:
        text = (
            "Δ⁹-THC binds CB1 (UniProt P21554) with a partial-agonist "
            "affinity (Ki ≈ 40 nM in cell-membrane assays). After oral "
            "administration of 5 mg in adults, plasma C-max is "
            "1–10 ng/mL within 1–2 h. THCA dominates raw extract; "
            "decarboxylation applied prior to pharmacology assay."
        )
        report = run_rigor_checks(text)
        self.assertTrue(report.clean, msg=report.summary())

    def test_summary_lists_all_violation_classes(self) -> None:
        # Each violation lives in its own paragraph with enough separator
        # text to push surrounding-matrix-tag windows out of reach.
        separator = "\n\n" + ("." * 200) + "\n\n"
        text = (
            "THC binds CB1."  # isomer collapse (pharmacology context)
            + separator +
            "This cultivar tests at 22% THC by HPLC."  # THCA-vs-THC
            + separator +
            "CBD was reported at 150 ng/mL post-dose, no other context."  # matrix-unit
            + separator +
            "Within the raw extract, CBD inhibited cytokine release."  # decarb
        )
        report = run_rigor_checks(text)
        self.assertFalse(report.clean)
        s = report.summary()
        # The aggregator should at minimum surface the new violation classes.
        self.assertIn("THCA-vs-THC", s)
        self.assertIn("Matrix-unit", s)
        self.assertIn("Decarb-context", s)


if __name__ == "__main__":
    unittest.main()
