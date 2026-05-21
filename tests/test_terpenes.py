"""Tests for cannavec.terpenes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.terpenes import (   # noqa: E402
    Terpene,
    TerpeneName,
    all_terpenes,
    detect_terpene_mention,
    entourage_effect_note,
    find_terpenes,
    format_for_clinician,
)
from cannavec_science.evidence import EvidenceLevel


class TestTerpeneRegistry(unittest.TestCase):
    def test_registry_not_empty(self) -> None:
        self.assertGreater(len(all_terpenes()), 0)

    def test_beta_caryophyllene_present(self) -> None:
        names = {t.name for t in all_terpenes()}
        self.assertIn(TerpeneName.BETA_CARYOPHYLLENE, names)

    def test_every_entry_has_citation(self) -> None:
        for t in all_terpenes():
            self.assertTrue(
                t.citations,
                f"{t.name.value} has no citations",
            )

    def test_every_citation_has_identifier(self) -> None:
        for t in all_terpenes():
            for c in t.citations:
                self.assertTrue(
                    c.pmid or c.doi or c.url,
                    f"{t.name.value} citation '{c.label}' has no identifier",
                )

    def test_every_entry_has_concentration_info(self) -> None:
        for t in all_terpenes():
            self.assertTrue(
                t.typical_concentration_pct_ww,
                f"{t.name.value} missing typical_concentration_pct_ww",
            )
            self.assertTrue(
                t.in_vitro_active_concentration,
                f"{t.name.value} missing in_vitro_active_concentration",
            )

    def test_beta_caryophyllene_is_highest_grade(self) -> None:
        bcp = next(
            t for t in all_terpenes()
            if t.name == TerpeneName.BETA_CARYOPHYLLENE
        )
        # β-caryophyllene has the best-evidenced pharmacology
        self.assertGreaterEqual(
            bcp.pharmacology_evidence_grade.rank,
            EvidenceLevel.B.rank,
        )

    def test_clinical_grade_conservative(self) -> None:
        # No terpene has Level A or B clinical evidence — that would
        # require a powered human RCT isolating terpene effects.
        for t in all_terpenes():
            self.assertLessEqual(
                t.clinical_evidence_grade.rank,
                EvidenceLevel.C.rank,
                f"{t.name.value} has implausibly high clinical grade",
            )

    def test_entourage_role_valid_values(self) -> None:
        valid = {"proposed", "limited", "not studied"}
        for t in all_terpenes():
            self.assertIn(
                t.entourage_role,
                valid,
                f"{t.name.value} has invalid entourage_role: {t.entourage_role}",
            )

    def test_to_dict_serializable(self) -> None:
        import json
        for t in all_terpenes():
            d = t.to_dict()
            # Should not raise
            json.dumps(d)
            self.assertIn("name", d)
            self.assertIn("pharmacology_evidence_grade", d)
            self.assertIn("clinical_evidence_grade", d)
            self.assertIn("citations", d)


class TestTerpeneDetection(unittest.TestCase):
    def test_detect_caryophyllene_by_name(self) -> None:
        hits = detect_terpene_mention("Beta-caryophyllene is a sesquiterpene.")
        names = {h.name for h in hits}
        self.assertIn(TerpeneName.BETA_CARYOPHYLLENE, names)

    def test_detect_caryophyllene_abbreviation(self) -> None:
        hits = detect_terpene_mention("BCP is a CB2 partial agonist.")
        names = {h.name for h in hits}
        self.assertIn(TerpeneName.BETA_CARYOPHYLLENE, names)

    def test_detect_myrcene(self) -> None:
        hits = detect_terpene_mention("The cultivar has high myrcene content.")
        names = {h.name for h in hits}
        self.assertIn(TerpeneName.MYRCENE, names)

    def test_detect_multiple_terpenes(self) -> None:
        hits = detect_terpene_mention(
            "This profile shows myrcene, linalool, and limonene."
        )
        names = {h.name for h in hits}
        self.assertIn(TerpeneName.MYRCENE, names)
        self.assertIn(TerpeneName.LINALOOL, names)
        self.assertIn(TerpeneName.LIMONENE, names)

    def test_detect_case_insensitive(self) -> None:
        hits = detect_terpene_mention("MYRCENE is abundant in cannabis.")
        names = {h.name for h in hits}
        self.assertIn(TerpeneName.MYRCENE, names)

    def test_no_match_on_unrelated_text(self) -> None:
        hits = detect_terpene_mention(
            "CBD binds CB1 and CB2 receptors in vitro."
        )
        self.assertEqual(len(hits), 0)

    def test_deduplication(self) -> None:
        # myrcene mentioned twice — should only appear once
        hits = detect_terpene_mention("Myrcene is common. Myrcene also causes...")
        myrcene_hits = [h for h in hits if h.name == TerpeneName.MYRCENE]
        self.assertEqual(len(myrcene_hits), 1)


class TestFindTerpenes(unittest.TestCase):
    def test_find_all_when_no_filter(self) -> None:
        results = find_terpenes()
        self.assertEqual(len(results), len(all_terpenes()))

    def test_find_by_name_substring(self) -> None:
        results = find_terpenes(name_substring="caryophyllene")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, TerpeneName.BETA_CARYOPHYLLENE)

    def test_find_by_type_sesquiterpene(self) -> None:
        results = find_terpenes(terpene_type="sesquiterpene")
        for t in results:
            self.assertIn("sesquiterpene", t.type)

    def test_find_by_min_grade_filters_low(self) -> None:
        # Only β-caryophyllene reaches Level B pharmacology
        high_grade = find_terpenes(min_pharmacology_grade=EvidenceLevel.B)
        names = {t.name for t in high_grade}
        self.assertIn(TerpeneName.BETA_CARYOPHYLLENE, names)

    def test_find_by_min_grade_excludes_lowest(self) -> None:
        # Level A filter should return nothing (no terpene has Level A pharmacology)
        level_a_only = find_terpenes(min_pharmacology_grade=EvidenceLevel.A)
        self.assertEqual(len(level_a_only), 0)


class TestEntourageNote(unittest.TestCase):
    def test_note_not_empty(self) -> None:
        note = entourage_effect_note()
        self.assertGreater(len(note), 50)

    def test_note_includes_pmid(self) -> None:
        note = entourage_effect_note()
        # Russo 2011 is the canonical entourage-effect citation
        self.assertIn("20925516", note)

    def test_note_hedges(self) -> None:
        note = entourage_effect_note()
        # Must express that clinical evidence is weak
        self.assertRegex(note, r"(?i)hypothesis|not established|level c|weak|limited")

    def test_note_names_concentration_gap(self) -> None:
        note = entourage_effect_note()
        # Must surface the concentration gap between assay and in-vivo
        self.assertRegex(note, r"(?i)nanomolar|micromolar|concentration")


class TestFormatForClinician(unittest.TestCase):
    def test_format_empty_returns_placeholder(self) -> None:
        out = format_for_clinician([])
        self.assertIn("No terpene registry entries matched", out)

    def test_format_single_entry_contains_name(self) -> None:
        bcp = next(
            t for t in all_terpenes()
            if t.name == TerpeneName.BETA_CARYOPHYLLENE
        )
        out = format_for_clinician([bcp])
        self.assertIn("caryophyllene", out)
        self.assertIn("entourage", out.lower())

    def test_format_always_appends_entourage_note(self) -> None:
        myrcene = next(
            t for t in all_terpenes() if t.name == TerpeneName.MYRCENE
        )
        out = format_for_clinician([myrcene])
        self.assertIn("20925516", out)  # Russo 2011 citation in entourage note


class TestSafetyIntegration(unittest.TestCase):
    """Verify terpene questions proceed through the safety layer correctly."""

    def test_terpene_question_proceeds(self) -> None:
        from cannavec_science.safety import SafetyAction, check_safety
        v = check_safety("How do terpenes affect cannabis effects?")
        self.assertEqual(v.recommended_action, SafetyAction.PROCEED)

    def test_myrcene_couch_lock_question_proceeds(self) -> None:
        from cannavec_science.safety import SafetyAction, check_safety
        # A question about myrcene and sedation should proceed (not refused)
        v = check_safety("What is the evidence for myrcene causing sedation?")
        self.assertEqual(v.recommended_action, SafetyAction.PROCEED)

    @unittest.skip("domains module is out-of-scope for the MVP "
                   "(researcher audience only; no domain-routing surface)")
    def test_terpene_domain_classifies_correctly(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
