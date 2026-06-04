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
    detect_isomer_equivalence,
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


class TestDoseRoutePrecisionBattery(unittest.TestCase):
    """Precision battery (defect #8).

    The dose-route detector FALSE-POSITIVED on standard route
    abbreviations: ``CBD 20 mg/kg/day PO`` flagged ``dose_route_violation``
    even though ``PO`` (*per os*, orally) **is** the route. Three root
    causes (all reproduced before the fix):

    1. ``_ROUTE_TOKEN`` lacked the bare two-letter abbreviations
       (PO / IV / IM / SC / SL / IN / IP / PR / SQ / IT).
    2. The dotted forms were DEAD CODE — ``_ROUTE_TOKEN.search('p.o.')``
       returned ``None`` because a trailing ``\\b`` after a literal period
       can never match.
    3. ``_sentence_window`` truncated at the first ``.``, chopping
       ``p.o.`` before the route check could see it.

    The plugin's OWN dosing tables tripped it
    (``populations.py``: "nabilone 1-2 mg PO twice daily";
    ``ecbome_inhibitors.py``: "4 mg PO daily").

    This battery pins: every textbook-correct route notation reads
    CLEAN, the product's own dosing strings read CLEAN, and a genuine
    route-less dose still FLAGS (recall preserved).
    """

    # --- Negatives: route present, must NOT fire. ---

    def test_bare_po_does_not_fire(self) -> None:
        # The exact smoking-gun reproduction from the fix brief.
        hits = detect_missing_dose_route("CBD 20 mg/kg/day PO")
        self.assertEqual(hits, (), f"bare PO is a route: {hits}")

    def test_dotted_po_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("Nabilone 1-2 mg p.o. twice daily.")
        self.assertEqual(hits, (), f"dotted p.o. is a route: {hits}")

    def test_bare_iv_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("THC 5 mg IV bolus over 2 minutes.")
        self.assertEqual(hits, (), f"bare IV is a route: {hits}")

    def test_dotted_iv_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("Midazolam 2 mg i.v. for sedation.")
        self.assertEqual(hits, (), f"dotted i.v. is a route: {hits}")

    def test_bare_im_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("Nabilone 1 mg IM every 8 hours.")
        self.assertEqual(hits, (), f"bare IM is a route: {hits}")

    def test_bare_sc_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("Drug X 0.5 mg SC twice daily.")
        self.assertEqual(hits, (), f"bare SC is a route: {hits}")

    def test_bare_sl_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("CBD 10 mg SL under the tongue.")
        self.assertEqual(hits, (), f"bare SL is a route: {hits}")

    def test_bare_in_intranasal_abbrev_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("Drug X 4 mg IN once daily.")
        self.assertEqual(hits, (), f"bare IN (intranasal) is a route: {hits}")

    def test_spelled_intranasal_does_not_fire(self) -> None:
        hits = detect_missing_dose_route("Drug X 4 mg intranasal once daily.")
        self.assertEqual(hits, (), f"spelled intranasal is a route: {hits}")

    def test_epidiolex_dosing_string_does_not_fire(self) -> None:
        hits = detect_missing_dose_route(
            "Epidiolex 10 mg/kg/day PO twice daily."
        )
        self.assertEqual(hits, (), f"Epidiolex PO string must be clean: {hits}")

    def test_in_repo_nabilone_dosing_string_does_not_fire(self) -> None:
        # Verbatim from populations.py:472 (the plugin's own dosing table).
        hits = detect_missing_dose_route(
            "nabilone 1-2 mg PO twice daily; dronabinol 2.5-10 mg PO "
            "in divided doses."
        )
        self.assertEqual(
            hits, (), f"the plugin's own dosing table must be clean: {hits}"
        )

    def test_in_repo_ecbome_dosing_string_does_not_fire(self) -> None:
        # Verbatim shape from ecbome_inhibitors.py:211.
        hits = detect_missing_dose_route(
            "PF-04457845 (n=70, 4 mg PO daily for 28 days)."
        )
        self.assertEqual(
            hits, (), f"the plugin's own dosing table must be clean: {hits}"
        )

    def test_in_repo_dronabinol_dose_range_string_does_not_fire(self) -> None:
        # Verbatim from populations.py:497.
        hits = detect_missing_dose_route("2.5-10 mg PO twice daily")
        self.assertEqual(hits, (), f"dose range with PO must be clean: {hits}")

    # --- Positives: no route, MUST still fire (recall preserved). ---

    def test_dose_without_any_route_still_fires(self) -> None:
        hits = detect_missing_dose_route(
            "A 10 mg dose helped most patients in the cohort."
        )
        self.assertGreaterEqual(
            len(hits), 1,
            "a genuinely route-less clinical dose must still flag",
        )

    def test_mg_per_kg_without_route_still_fires(self) -> None:
        # Re-pin the canonical positive after broadening the lexicon.
        hits = detect_missing_dose_route(
            "Cannabidiol was dosed at 20 mg/kg/day in the Dravet trial."
        )
        self.assertGreaterEqual(len(hits), 1)

    def test_io_substring_in_word_is_not_a_route(self) -> None:
        # Guard against the bare-abbreviation lexicon over-matching:
        # ordinary prose words containing 'in'/'im'/'po'/'sc' as
        # substrings must NOT count as a route, so a route-less dose
        # in such a sentence still fires.
        hits = detect_missing_dose_route(
            "The important impact of a 50 mg amount became apparent."
        )
        self.assertGreaterEqual(
            len(hits), 1,
            "substrings inside 'important'/'impact'/'amount' are not routes",
        )


class TestDoseRoutePeriodTruncation(unittest.TestCase):
    """Regression for the sentence-window truncation bug (defect #8).

    ``_sentence_window`` walked to the first ``.`` and stopped, which
    chopped a route abbreviation written as ``p.o.`` / ``i.v.`` before
    the route check ran. The dose-route window must now tolerate the
    intra-token periods of route abbreviations while STILL isolating
    genuine sentence boundaries (so a route in a wholly unrelated next
    sentence does not silently satisfy a route-less dose).
    """

    def test_dotted_route_survives_window(self) -> None:
        # p.o. sits immediately after the dose; the window must keep it.
        hits = detect_missing_dose_route("Nabilone 1-2 mg p.o. twice daily.")
        self.assertEqual(hits, ())

    def test_dotted_iv_route_survives_window(self) -> None:
        hits = detect_missing_dose_route("Ketamine 0.5 mg/kg i.v. over 40 min.")
        self.assertEqual(hits, ())

    def test_route_in_unrelated_next_sentence_does_not_satisfy(self) -> None:
        # The dose is route-less; the *next* sentence mentions an oral
        # route for a different statement. The route-less dose must still
        # fire — abbreviation tolerance must not turn into cross-sentence
        # leakage.
        text = (
            "A 10 mg dose was administered. "
            "Separately, the oral bioavailability of CBD is low."
        )
        hits = detect_missing_dose_route(text)
        self.assertGreaterEqual(
            len(hits), 1,
            "a route in an unrelated next sentence must not satisfy a "
            "route-less dose",
        )


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


class TestIsomerEquivalence(unittest.TestCase):
    """Explicit isomer / decarb *equivalence* errors (defect #14).

    Before this detector, "THC and THCA are the same" passed 100% clean
    — no existing check catches an author asserting that two
    pharmacologically distinct cannabinoids are identical. The detector
    is intentionally conservative: it fires ONLY on an explicit
    ``X and Y are the same / identical / interchangeable`` (or the
    transposed ``X is the same as Y``) for a curated set of known
    distinct cannabinoid pairs (THC/THCA decarb pairs, Δ⁸/Δ⁹ isomers,
    CBD/CBDA, THC/CBD). It must NOT fire on correct precursor/conversion
    language or on "different" statements.
    """

    def test_thc_thca_same_fires(self) -> None:
        text = "THC and THCA are the same compound."
        hits = detect_isomer_equivalence(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_delta8_delta9_identical_fires(self) -> None:
        text = "Delta-8-THC and delta-9-THC are identical in their effects."
        hits = detect_isomer_equivalence(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_thc_cbd_interchangeable_fires(self) -> None:
        text = "For dosing purposes THC and CBD are interchangeable."
        hits = detect_isomer_equivalence(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_transposed_same_as_fires(self) -> None:
        text = "THCA is the same as THC once you account for the carboxyl."
        hits = detect_isomer_equivalence(text)
        self.assertGreaterEqual(len(hits), 1)

    def test_correct_precursor_language_does_not_fire(self) -> None:
        text = (
            "THCA is the carboxylated precursor of THC and converts to it "
            "via decarboxylation on heating."
        )
        hits = detect_isomer_equivalence(text)
        self.assertEqual(hits, ())

    def test_different_statement_does_not_fire(self) -> None:
        text = "THC and CBD are different compounds with distinct pharmacology."
        hits = detect_isomer_equivalence(text)
        self.assertEqual(hits, ())

    def test_unrelated_same_does_not_fire(self) -> None:
        # 'the same' about something other than a cannabinoid pair.
        text = "The dose was the same across both study arms."
        hits = detect_isomer_equivalence(text)
        self.assertEqual(hits, ())

    def test_equivalence_routed_through_combined_runner(self) -> None:
        report = run_rigor_checks("THC and THCA are the same molecule.")
        self.assertFalse(report.clean)
        self.assertGreaterEqual(len(report.isomer_equivalence_violations), 1)


if __name__ == "__main__":
    unittest.main()
