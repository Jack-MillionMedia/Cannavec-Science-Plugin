"""Tests for cannavec.terpene_reference."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.evidence import EvidenceLevel  # noqa: E402
from cannavec_science.terpene_reference import (  # noqa: E402
    ENTOURAGE_HYPOTHESIS_STATEMENT,
    TerpeneClass,
    all_terpenes,
    find_by_class,
    find_by_receptor,
    find_terpene,
    format_terpene_summary,
)


class TestTerpeneRegistry(unittest.TestCase):
    def test_registry_not_empty(self) -> None:
        self.assertGreater(len(all_terpenes()), 0)

    def test_all_terpenes_have_cas(self) -> None:
        for t in all_terpenes():
            self.assertTrue(t.cas, f"{t.name} missing CAS")

    def test_all_terpenes_have_formula(self) -> None:
        for t in all_terpenes():
            self.assertTrue(t.molecular_formula, f"{t.name} missing formula")

    def test_all_terpenes_have_concentration_range(self) -> None:
        for t in all_terpenes():
            lo, hi = t.typical_concentration_pct_ww
            self.assertGreaterEqual(lo, 0.0, f"{t.name} min conc negative")
            self.assertGreater(hi, 0.0, f"{t.name} max conc zero or negative")
            self.assertLessEqual(lo, hi, f"{t.name} min > max")

    def test_all_interactions_have_evidence_level(self) -> None:
        for t in all_terpenes():
            for i in t.receptor_interactions:
                self.assertIsInstance(i.evidence_level, EvidenceLevel)

    def test_all_interactions_have_primary_source_or_are_unsupported(self) -> None:
        for t in all_terpenes():
            for i in t.receptor_interactions:
                if i.evidence_level != EvidenceLevel.UNSUPPORTED:
                    self.assertTrue(
                        i.primary_db,
                        f"{t.name} → {i.receptor}: non-UNSUPPORTED interaction has no source",
                    )

    def test_no_level_a_terpene_pharmacology(self) -> None:
        # No terpene-receptor interaction in cannabis should be Level A.
        # Level A requires Cochrane-level systematic review; none exist for
        # cannabis terpene pharmacology in humans.
        for t in all_terpenes():
            for i in t.receptor_interactions:
                self.assertNotEqual(
                    i.evidence_level,
                    EvidenceLevel.A,
                    f"{t.name} → {i.receptor} incorrectly graded Level A",
                )

    def test_beta_caryophyllene_has_cb2_interaction(self) -> None:
        t = find_terpene("(−)-β-caryophyllene")
        self.assertIsNotNone(t)
        assert t is not None
        receptors = [i.receptor for i in t.receptor_interactions]
        self.assertTrue(
            any("CB2" in r for r in receptors),
            "β-caryophyllene should have CB2 interaction",
        )

    def test_beta_caryophyllene_cb2_evidence_level(self) -> None:
        t = find_terpene("(−)-β-caryophyllene")
        assert t is not None
        cb2_interactions = [
            i for i in t.receptor_interactions if "CB2" in i.receptor
        ]
        self.assertTrue(cb2_interactions)
        level = cb2_interactions[0].evidence_level
        # CB2 binding has the strongest evidence of any terpene interaction —
        # Level C at most (single primary study, no Cochrane SR).
        self.assertLessEqual(level.rank, EvidenceLevel.C.rank)
        self.assertGreaterEqual(level.rank, EvidenceLevel.D.rank)


class TestFindFunctions(unittest.TestCase):
    def test_find_by_common_name(self) -> None:
        t = find_terpene("myrcene")
        self.assertIsNotNone(t)
        assert t is not None
        self.assertEqual(t.name, "myrcene")

    def test_find_by_alias(self) -> None:
        t = find_terpene("BCP")
        self.assertIsNotNone(t)
        assert t is not None
        self.assertIn("caryophyllene", t.name.lower())

    def test_find_nonexistent_returns_none(self) -> None:
        self.assertIsNone(find_terpene("nonexistent_terpene_xyz"))

    def test_find_by_class_monoterpenes(self) -> None:
        monoterpenes = find_by_class(TerpeneClass.MONOTERPENE)
        self.assertGreater(len(monoterpenes), 0)
        for t in monoterpenes:
            self.assertEqual(t.terpene_class, TerpeneClass.MONOTERPENE)

    def test_find_by_class_sesquiterpenes(self) -> None:
        sesqui = find_by_class(TerpeneClass.SESQUITERPENE)
        self.assertGreater(len(sesqui), 0)
        for t in sesqui:
            self.assertEqual(t.terpene_class, TerpeneClass.SESQUITERPENE)

    def test_find_by_receptor_cb2(self) -> None:
        cb2_terpenes = find_by_receptor("CB2")
        self.assertGreater(len(cb2_terpenes), 0)
        names = [t.name for t in cb2_terpenes]
        self.assertTrue(any("caryophyllene" in n.lower() for n in names))

    def test_find_by_receptor_5ht1a(self) -> None:
        ht1a = find_by_receptor("5-HT1A")
        self.assertGreater(len(ht1a), 0)

    def test_find_by_receptor_nonexistent(self) -> None:
        result = find_by_receptor("nonexistent_receptor_xyz")
        self.assertEqual(len(result), 0)


class TestFormatSummary(unittest.TestCase):
    def test_format_includes_name(self) -> None:
        t = find_terpene("myrcene")
        assert t is not None
        summary = format_terpene_summary(t)
        self.assertIn("myrcene", summary)

    def test_format_includes_concentration_range(self) -> None:
        t = find_terpene("myrcene")
        assert t is not None
        summary = format_terpene_summary(t)
        self.assertIn("% w/w", summary)

    def test_format_includes_evidence_grade(self) -> None:
        t = find_terpene("(−)-β-caryophyllene")
        assert t is not None
        summary = format_terpene_summary(t)
        # Should include a GRADE label
        self.assertTrue(
            any(f"Level {g}" in summary for g in ["A", "B", "C", "D", "E"]),
            "Summary should include an evidence grade",
        )

    def test_format_caryophyllene_includes_ki(self) -> None:
        t = find_terpene("(−)-β-caryophyllene")
        assert t is not None
        summary = format_terpene_summary(t)
        self.assertIn("Ki/IC", summary)
        self.assertIn("μM", summary)


class TestEntourageHypothesisStatement(unittest.TestCase):
    def test_statement_not_empty(self) -> None:
        self.assertTrue(len(ENTOURAGE_HYPOTHESIS_STATEMENT) > 100)

    def test_statement_names_entourage(self) -> None:
        self.assertIn("Entourage", ENTOURAGE_HYPOTHESIS_STATEMENT)

    def test_statement_names_hypothesis_not_fact(self) -> None:
        # Must explicitly call it a hypothesis, not an established fact.
        self.assertIn("hypothesis", ENTOURAGE_HYPOTHESIS_STATEMENT.lower())

    def test_statement_does_not_claim_established(self) -> None:
        # Must NOT say "is established" — entourage is not Level A.
        lower = ENTOURAGE_HYPOTHESIS_STATEMENT.lower()
        self.assertNotIn("is established", lower)

    def test_statement_includes_evidence_gap_language(self) -> None:
        lower = ENTOURAGE_HYPOTHESIS_STATEMENT.lower()
        self.assertTrue(
            any(
                phrase in lower
                for phrase in [
                    "insufficient", "limited", "unclear", "preliminary",
                    "no human", "open", "not confirmed",
                ]
            ),
            "Statement should include evidence-gap language",
        )

    def test_statement_cites_a_pmid(self) -> None:
        self.assertIn("PMID", ENTOURAGE_HYPOTHESIS_STATEMENT)
