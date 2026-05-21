"""Tests for the modern-prescribing interaction rows added in spec 004 US3.

The 17-row registry until v2.12 covered the 2019-era priorities
(warfarin, clobazam, valproate, TCAs, statins). The 2024–2026
prescribing reality required adding:

- Direct oral anticoagulants (DOACs): apixaban, rivaroxaban,
  dabigatran, edoxaban.
- SSRI-specific entries: sertraline, fluoxetine, escitalopram.
- Lithium (narrow therapeutic index, pharmacodynamic interaction).
- Anesthesia agents: propofol + volatile.
- Chemotherapy specifics: taxanes, vinca alkaloids, irinotecan,
  platinum agents.

This module asserts every new row is matchable by its canonical drug
name AND its common brand-name aliases.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.interactions import (   # noqa: E402
    all_interactions,
    detect_interaction_mention,
)


def _interaction_for(text: str):
    """Return the set of partner_drug strings in detected interactions."""
    return {x.partner_drug for x in detect_interaction_mention(text)}


class TestDoacRows(unittest.TestCase):
    """Direct oral anticoagulants must surface as specific rows."""

    def test_apixaban_by_generic_name(self) -> None:
        partners = _interaction_for("Patient on CBD and apixaban.")
        self.assertIn("apixaban", partners)

    def test_apixaban_by_brand(self) -> None:
        partners = _interaction_for("Eliquis with CBD adjunct.")
        self.assertIn("apixaban", partners)

    def test_rivaroxaban_by_brand(self) -> None:
        partners = _interaction_for("Xarelto co-administered with CBD.")
        self.assertIn("rivaroxaban", partners)

    def test_dabigatran_specific(self) -> None:
        partners = _interaction_for("Pradaxa user adding CBD daily.")
        self.assertIn("dabigatran", partners)

    def test_edoxaban_specific(self) -> None:
        partners = _interaction_for("Savaysa daily plus 25 mg CBD.")
        self.assertIn("edoxaban", partners)

    def test_doac_class_keyword(self) -> None:
        partners = _interaction_for(
            "Patient on a DOAC (direct oral anticoagulant) considering CBD."
        )
        # The DOAC class keyword routes to apixaban as the default.
        self.assertIn("apixaban", partners)


class TestSsriRows(unittest.TestCase):
    """SSRI-specific entries must surface; generic TCA does not substitute."""

    def test_sertraline_by_generic_name(self) -> None:
        partners = _interaction_for("Patient on sertraline 100 mg adding CBD.")
        self.assertIn("sertraline", partners)

    def test_sertraline_by_brand(self) -> None:
        partners = _interaction_for("Zoloft co-administered with CBD.")
        self.assertIn("sertraline", partners)

    def test_fluoxetine_by_generic_name(self) -> None:
        partners = _interaction_for("CBD plus fluoxetine — safety review.")
        self.assertIn("fluoxetine", partners)

    def test_fluoxetine_by_brand(self) -> None:
        partners = _interaction_for("Prozac user starting CBD.")
        self.assertIn("fluoxetine", partners)

    def test_escitalopram_by_generic_name(self) -> None:
        partners = _interaction_for("Patient on escitalopram + CBD considerations.")
        self.assertIn("escitalopram", partners)

    def test_escitalopram_by_brand(self) -> None:
        partners = _interaction_for("Lexapro plus CBD: safety?")
        self.assertIn("escitalopram", partners)

    def test_ssri_class_keyword(self) -> None:
        partners = _interaction_for("Patient on an SSRI considering CBD.")
        self.assertIn("sertraline", partners)


class TestLithiumRow(unittest.TestCase):
    def test_lithium_specific(self) -> None:
        partners = _interaction_for("Patient on lithium plus CBD therapy.")
        self.assertIn("lithium", partners)


class TestAnesthesiaRows(unittest.TestCase):
    def test_propofol_specific(self) -> None:
        partners = _interaction_for("CBD daily user undergoing propofol induction.")
        self.assertIn("propofol", partners)

    def test_volatile_sevoflurane(self) -> None:
        partners = _interaction_for("Chronic THC user with sevoflurane maintenance.")
        self.assertIn(
            "volatile anaesthetics (sevoflurane, isoflurane, desflurane)",
            partners,
        )

    def test_perioperative_keyword(self) -> None:
        partners = _interaction_for("Perioperative cannabis screening with CBD.")
        self.assertIn("propofol", partners)


class TestChemotherapyRows(unittest.TestCase):
    def test_paclitaxel_specific(self) -> None:
        partners = _interaction_for("Patient on paclitaxel chemotherapy adding CBD.")
        self.assertIn("taxanes (paclitaxel, docetaxel)", partners)

    def test_paclitaxel_by_brand_taxol(self) -> None:
        partners = _interaction_for("Taxol therapy plus CBD.")
        self.assertIn("taxanes (paclitaxel, docetaxel)", partners)

    def test_vincristine_specific(self) -> None:
        partners = _interaction_for("Vincristine chemo regimen plus CBD.")
        self.assertIn("vinca alkaloids (vincristine, vinblastine)", partners)

    def test_irinotecan_specific(self) -> None:
        partners = _interaction_for("Irinotecan regimen plus CBD.")
        self.assertIn("irinotecan", partners)

    def test_cisplatin_specific(self) -> None:
        partners = _interaction_for("Cisplatin chemo plus CBD adjunct.")
        self.assertIn(
            "platinum agents (cisplatin, carboplatin, oxaliplatin)",
            partners,
        )


class TestPolypharmacyStack(unittest.TestCase):
    """A multi-drug prompt must surface all matching rows simultaneously."""

    def test_four_drug_stack(self) -> None:
        partners = _interaction_for(
            "Patient is on apixaban, sertraline, lithium, and atorvastatin. "
            "Considering CBD addition."
        )
        # Each named drug should surface its row (or its class row for statin).
        self.assertIn("apixaban", partners)
        self.assertIn("sertraline", partners)
        self.assertIn("lithium", partners)
        self.assertIn(
            "CYP3A4 substrates (statins, immunosuppressants, some antifungals)",
            partners,
        )

    def test_five_drug_stack(self) -> None:
        partners = _interaction_for(
            "Polypharmacy: rivaroxaban + fluoxetine + clobazam + propofol + "
            "tacrolimus with CBD planned."
        )
        self.assertIn("rivaroxaban", partners)
        self.assertIn("fluoxetine", partners)
        self.assertIn("clobazam", partners)
        self.assertIn("propofol", partners)
        self.assertIn("tacrolimus", partners)


class TestRegistryRowIntegrity(unittest.TestCase):
    """Every new row must carry the required structural fields."""

    REQUIRED_NEW_PARTNERS = (
        "apixaban", "rivaroxaban", "dabigatran", "edoxaban",
        "sertraline", "fluoxetine", "escitalopram",
        "lithium", "propofol",
        "taxanes (paclitaxel, docetaxel)",
        "vinca alkaloids (vincristine, vinblastine)",
        "irinotecan",
        "platinum agents (cisplatin, carboplatin, oxaliplatin)",
        "volatile anaesthetics (sevoflurane, isoflurane, desflurane)",
    )

    def test_every_new_row_has_a_citation(self) -> None:
        rows = all_interactions()
        for partner in self.REQUIRED_NEW_PARTNERS:
            matches = [x for x in rows if x.partner_drug == partner]
            with self.subTest(partner=partner):
                self.assertEqual(len(matches), 1,
                                 f"expected exactly one row for {partner!r}")
                self.assertGreaterEqual(
                    len(matches[0].citations), 1,
                    f"{partner} has zero citations",
                )

    def test_every_new_row_has_a_clinical_action(self) -> None:
        rows = all_interactions()
        for partner in self.REQUIRED_NEW_PARTNERS:
            matches = [x for x in rows if x.partner_drug == partner]
            with self.subTest(partner=partner):
                self.assertEqual(len(matches), 1)
                self.assertIsNotNone(matches[0].clinical_action)


if __name__ == "__main__":
    unittest.main()
