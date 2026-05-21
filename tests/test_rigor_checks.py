"""Tests for `cannavec.rigor_checks`.

These verify that the three cannabis-specific traps documented in
`docs/EVIDENCE_PHILOSOPHY.md § 7` ("Cannabis-specific traps") fire
mechanically on real-shaped over-claims and *do not* fire on the
shapes the documentation explicitly carves out (cultivation ppm, lab
LOD/LOQ, in-vitro nM, legal-status mentions of THC).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.rigor_checks import (   # noqa: E402
    detect_isomer_collapse,
    detect_missing_dose_route,
    detect_missing_receptor_ids,
    run_rigor_checks,
)


class TestIsomerCollapse(unittest.TestCase):
    """Bare 'THC'/'CBD' in pharmacology context should fire."""

    def test_bare_thc_in_binding_context_fires(self) -> None:
        text = (
            "THC binds CB1 with a partial agonist affinity, "
            "producing cannabinoid-like behavioural effects."
        )
        hits = detect_isomer_collapse(text)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].cannabinoid, "THC")

    def test_bare_thc_in_metabolism_context_fires(self) -> None:
        text = (
            "THC is metabolised by CYP2C9 and CYP3A4 to "
            "11-OH-THC and then to 11-COOH-THC."
        )
        hits = detect_isomer_collapse(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_delta_9_disambiguation_blocks_violation(self) -> None:
        text = (
            "Δ⁹-THC binds CB1 with a Ki of ~40 nM in human "
            "membrane preparations."
        )
        hits = detect_isomer_collapse(text)
        self.assertEqual(hits, ())

    def test_thca_disambiguation_blocks_violation(self) -> None:
        text = "THCA is the carboxylated precursor; THCA does not bind CB1."
        hits = detect_isomer_collapse(text)
        self.assertEqual(hits, ())

    def test_11oh_thc_disambiguation_blocks_violation(self) -> None:
        text = "11-OH-THC is the active metabolite of THC and binds CB1."
        hits = detect_isomer_collapse(text)
        # 11-OH-THC disambiguates the "THC" within its own token via the
        # 20-char window; bare "THC" later in the same sentence is also
        # in scope of "11-OH-THC" disambiguation.
        # We are intentionally permissive here when the 11-OH form is named.
        self.assertEqual(hits, ())

    def test_bare_thc_in_legal_context_does_not_fire(self) -> None:
        text = "THC is a Schedule I drug under the US Controlled Substances Act."
        hits = detect_isomer_collapse(text)
        self.assertEqual(hits, ())

    def test_bare_thc_in_lay_description_does_not_fire(self) -> None:
        text = "THC is the cannabis compound that makes you feel high."
        hits = detect_isomer_collapse(text)
        self.assertEqual(hits, ())

    def test_thcv_is_not_a_bare_thc_violation(self) -> None:
        text = "THCV binds CB1 with low affinity but acts as an antagonist."
        hits = detect_isomer_collapse(text)
        # THCV is its own analyte; the bare-THC detector must not fire
        # on substring matches inside other cannabinoid names.
        self.assertEqual(hits, ())

    def test_bare_cbd_in_pharmacokinetics_does_not_fire(self) -> None:
        # CBD is intentionally NOT in the isomer-collapse family.
        # The philosophy doc names THC isomer-collapse explicitly;
        # CBD's analogues (CBDA, CBDV, 7-OH-CBD) are not commonly
        # conflated in research writing the way THC isomers are.
        text = (
            "CBD has poor oral bioavailability — 6 to 20 percent in fasted "
            "adults due to extensive first-pass metabolism."
        )
        hits = detect_isomer_collapse(text)
        self.assertEqual(hits, ())


class TestReceptorMissingId(unittest.TestCase):
    """Receptor mentions in mechanism context without an identifier."""

    def test_cb1_without_uniprot_fires(self) -> None:
        text = "Δ⁹-THC acts as a partial agonist at CB1, mediating euphoria."
        hits = detect_missing_receptor_ids(text)
        self.assertGreaterEqual(len(hits), 1)
        ids = {h.receptor for h in hits}
        self.assertIn("CB1", ids)

    def test_cb1_with_uniprot_does_not_fire(self) -> None:
        text = (
            "Δ⁹-THC acts as a partial agonist at CB1 (CNR1; UniProt P21554), "
            "mediating its psychoactive effects."
        )
        hits = detect_missing_receptor_ids(text)
        # The CNR1 gene symbol AND the UniProt accession both satisfy the
        # identifier requirement.
        self.assertEqual(hits, ())

    def test_trpv1_without_id_fires(self) -> None:
        text = "Cannabidiol activates TRPV1, modulating calcium influx."
        hits = detect_missing_receptor_ids(text)
        self.assertGreaterEqual(len(hits), 1)
        ids = {h.receptor for h in hits}
        # canonicalised name strips punctuation, so TRPV1 should appear
        self.assertIn("TRPV1", ids)

    def test_trpv1_with_chembl_id_does_not_fire(self) -> None:
        text = "Cannabidiol activates TRPV1 (CHEMBL4794), modulating calcium."
        hits = detect_missing_receptor_ids(text)
        self.assertEqual(hits, ())

    def test_receptor_mentioned_outside_mechanism_context_does_not_fire(self) -> None:
        text = (
            "The CB1 receptor was discovered by Devane in 1988 at the "
            "St. Louis University School of Medicine."
        )
        hits = detect_missing_receptor_ids(text)
        # No agonist/antagonist/binding/etc. context → not a mechanism claim.
        self.assertEqual(hits, ())

    def test_cb2_with_gene_symbol_in_sentence_does_not_fire(self) -> None:
        text = (
            "β-caryophyllene is a selective CB2 (CNR2) partial agonist, "
            "demonstrated by Gertsch and colleagues."
        )
        hits = detect_missing_receptor_ids(text)
        self.assertEqual(hits, ())


class TestDoseRouteMissing(unittest.TestCase):
    """Dose expressions missing a route in clinical/dosing context."""

    def test_mg_per_kg_without_route_fires(self) -> None:
        text = (
            "Cannabidiol was dosed at 20 mg/kg/day in the Devinsky 2017 "
            "Dravet trial."
        )
        hits = detect_missing_dose_route(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_mg_per_kg_with_oral_route_does_not_fire(self) -> None:
        text = (
            "Cannabidiol was dosed at 20 mg/kg/day orally in the Devinsky "
            "2017 Dravet trial."
        )
        hits = detect_missing_dose_route(text)
        self.assertEqual(hits, ())

    def test_milligrams_with_inhaled_route_does_not_fire(self) -> None:
        text = "Inhaled THC at 10 mg produces peak plasma levels at 5-10 minutes."
        hits = detect_missing_dose_route(text)
        self.assertEqual(hits, ())

    def test_dose_with_sublingual_route_does_not_fire(self) -> None:
        text = "Sativex is dosed at 1-12 sprays per day sublingually."
        hits = detect_missing_dose_route(text)
        self.assertEqual(hits, ())

    def test_lod_value_does_not_fire(self) -> None:
        text = "The HPLC method achieved an LOD of 0.05 mg per gram of flower."
        hits = detect_missing_dose_route(text)
        # LOD context is a lab-method statement, not a clinical dose.
        self.assertEqual(hits, ())

    def test_cultivation_ppm_does_not_fire(self) -> None:
        text = "Apply 150 mg per litre of calcium nitrate to the nutrient mix."
        hits = detect_missing_dose_route(text)
        self.assertEqual(hits, ())

    def test_in_vitro_micromolar_does_not_fire(self) -> None:
        text = (
            "β-caryophyllene at 10 μM in vitro reduces inflammatory "
            "cytokine release."
        )
        hits = detect_missing_dose_route(text)
        # Cell-culture dose, not a clinical dose.
        self.assertEqual(hits, ())


class TestRunRigorChecks(unittest.TestCase):
    """The combined runner returns the expected aggregated report."""

    def test_clean_pharmacology_answer_passes(self) -> None:
        text = (
            "Δ⁹-THC binds CB1 (CNR1; UniProt P21554) with a Ki of ~40 nM "
            "in human membrane prep, and is dosed at 5-10 mg orally for "
            "adult Sativex-naive titration."
        )
        report = run_rigor_checks(text)
        self.assertTrue(
            report.clean,
            msg=(report.isomer_violations,
                 report.receptor_violations,
                 report.dose_route_violations),
        )

    def test_overclaiming_pharmacology_answer_fails_all_three(self) -> None:
        text = (
            "THC binds CB1 with high potency, with a typical dose of "
            "20 mg/kg/day producing CNS effects."
        )
        report = run_rigor_checks(text)
        self.assertFalse(report.clean)
        self.assertGreaterEqual(len(report.isomer_violations), 1)
        self.assertGreaterEqual(len(report.receptor_violations), 1)
        self.assertGreaterEqual(len(report.dose_route_violations), 1)


@unittest.skip("self_audit module is out-of-scope for the MVP "
               "(researcher audience only; no multi-audience template surface)")
class TestAuditWiring(unittest.TestCase):
    pass


class TestMechanismContextCoverage(unittest.TestCase):
    """``acts at`` / ``acts on`` / ``active at`` weaker verbs must also
    place a receptor mention in mechanism context.

    Regression: before this patch, ``Δ⁹-THC acts at CB1`` did NOT fire
    the receptor-without-ID check because ``acts at`` was missing from
    _MECHANISM_CONTEXT. ``binds`` / ``agonist`` / ``affinity`` already
    fired. ``acts at`` is now covered, plus ``acts on``, ``acting at``,
    ``action at``, ``active at``, ``active on``.
    """

    def test_acts_at_triggers_receptor_check(self) -> None:
        from cannavec_science.rigor_checks import detect_missing_receptor_ids
        text = "Δ⁹-THC acts at CB1 to produce analgesia."
        violations = detect_missing_receptor_ids(text)
        self.assertGreaterEqual(
            len(violations), 1,
            "'acts at CB1' without UniProt/HGNC ID must fire receptor-without-ID",
        )

    def test_acts_on_triggers_receptor_check(self) -> None:
        from cannavec_science.rigor_checks import detect_missing_receptor_ids
        text = "Δ⁹-THC acts on CB2 to modulate cytokine release."
        violations = detect_missing_receptor_ids(text)
        self.assertGreaterEqual(len(violations), 1)

    def test_active_at_triggers_receptor_check(self) -> None:
        from cannavec_science.rigor_checks import detect_missing_receptor_ids
        text = "CBD is active at TRPV1 at sub-micromolar concentrations."
        violations = detect_missing_receptor_ids(text)
        self.assertGreaterEqual(len(violations), 1)

    def test_action_at_triggers_receptor_check(self) -> None:
        from cannavec_science.rigor_checks import detect_missing_receptor_ids
        text = "The action at CB1 of the lead candidate was attenuated."
        violations = detect_missing_receptor_ids(text)
        self.assertGreaterEqual(len(violations), 1)

    def test_acts_at_with_uniprot_id_does_not_fire(self) -> None:
        # When the UniProt accession is present in the same window,
        # the check passes — exactly the same false-positive guard as
        # the canonical 'binds' / 'agonist' phrasings.
        from cannavec_science.rigor_checks import detect_missing_receptor_ids
        text = "Δ⁹-THC acts at CB1 (CNR1 / UniProt P21554) to produce analgesia."
        violations = detect_missing_receptor_ids(text)
        cb_violations = [v for v in violations if v.receptor in ("CB1", "CB2")]
        self.assertEqual(
            cb_violations, [],
            "'acts at CB1' with a UniProt/HGNC ID in the same sentence must NOT fire",
        )

    def test_non_mechanism_act_does_not_fire(self) -> None:
        # 'Acts of Congress', 'a legal act', etc. must not be misread
        # as mechanism context for any nearby receptor name.
        from cannavec_science.rigor_checks import detect_missing_receptor_ids
        text = (
            "Under the federal CSA, possession of any product containing CB1 "
            "(as a registered trademark) requires special licensure; recent "
            "acts of Congress have not amended this."
        )
        violations = detect_missing_receptor_ids(text)
        # 'acts of Congress' should not be parsed as 'acts at/on' mechanism context.
        self.assertEqual(
            violations, (),
            f"Non-mechanism 'acts of' must not fire: {violations}",
        )

    def test_sentence_window_does_not_leak_across_periods(self) -> None:
        """Regression — the sentence-window walk previously did not
        narrow to sentence boundaries, so a CB1 mention in sentence 1
        could be 'satisfied' by a TRPV1 mention in sentence 2 (because
        TRPV1 is in the identifier-token vocabulary). With the window
        walk fixed, both mentions fire independently.
        """
        from cannavec_science.rigor_checks import detect_missing_receptor_ids
        text = "Δ⁹-THC acts at CB1 to produce analgesia. CBD is active at TRPV1."
        violations = detect_missing_receptor_ids(text)
        receptors = {v.receptor for v in violations}
        self.assertIn(
            "CB1", receptors,
            "CB1 in sentence 1 must fire — sentence-window must not leak across periods",
        )
        self.assertIn(
            "TRPV1", receptors,
            "TRPV1 in sentence 2 must fire — sentence-window must not leak across periods",
        )


class TestExtendedPharmacologyContext(unittest.TestCase):
    """Regression: the original `_PHARM_CONTEXT` only matched a narrow
    set of pharmacology terms (`bind`, `agonist`, `receptor`, ...).
    Bare `THC activates CB1 to produce analgesia at 20 mg/kg/day` did
    not fire isomer-collapse because none of `activates`, `analgesia`,
    `dose` were in the context. This test pins the extended coverage."""

    def test_activates_in_pharmacology_context(self) -> None:
        from cannavec_science.rigor_checks import detect_isomer_collapse
        text = "THC activates CB1 to produce analgesia in chronic pain."
        violations = detect_isomer_collapse(text)
        self.assertTrue(
            violations,
            "Bare 'THC' adjacent to 'activates' (pharmacology verb) must "
            "trigger isomer-collapse",
        )

    def test_inhibits_in_pharmacology_context(self) -> None:
        from cannavec_science.rigor_checks import detect_isomer_collapse
        text = "THC inhibits CYP2C9 in vitro at micromolar concentrations."
        violations = detect_isomer_collapse(text)
        self.assertTrue(violations)

    def test_dose_in_pharmacology_context(self) -> None:
        from cannavec_science.rigor_checks import detect_isomer_collapse
        text = "The recommended THC dose is 5 mg orally."
        violations = detect_isomer_collapse(text)
        self.assertTrue(
            violations,
            "Bare 'THC' adjacent to 'dose' must trigger isomer-collapse",
        )

    def test_analgesia_in_pharmacology_context(self) -> None:
        from cannavec_science.rigor_checks import detect_isomer_collapse
        text = "THC produces analgesia in animal models of inflammatory pain."
        violations = detect_isomer_collapse(text)
        self.assertTrue(violations)

    def test_legal_status_still_does_not_fire(self) -> None:
        # The extended context list must not over-fire on plain
        # legal/regulatory mentions.
        from cannavec_science.rigor_checks import detect_isomer_collapse
        text = "THC is Schedule I under the US Controlled Substances Act."
        violations = detect_isomer_collapse(text)
        self.assertEqual(
            violations, (),
            "Legal-status context must not trigger isomer-collapse "
            "even with extended pharmacology vocabulary",
        )

    def test_lay_summary_still_does_not_fire(self) -> None:
        from cannavec_science.rigor_checks import detect_isomer_collapse
        text = "THC is the intoxicating component of cannabis."
        violations = detect_isomer_collapse(text)
        self.assertEqual(violations, ())

    def test_disambiguated_isomer_still_does_not_fire(self) -> None:
        # Δ⁹-THC + extended-context word: the isomer prefix disambig
        # window must still suppress the violation.
        from cannavec_science.rigor_checks import detect_isomer_collapse
        text = "Δ⁹-THC activates CB1 to produce analgesia."
        violations = detect_isomer_collapse(text)
        self.assertEqual(
            violations, (),
            "Already-disambiguated Δ⁹-THC must not trigger isomer-collapse",
        )


if __name__ == "__main__":
    unittest.main()
