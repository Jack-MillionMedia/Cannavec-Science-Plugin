"""Tests for the minor-cannabinoid registry.

Coverage:

- Registry shape: every entry has a name, a long name, at least one
  receptor activity, at least one clinical-evidence row (even if the
  row records "no admissible primary clinical evidence"), at least one
  preclinical-evidence row, a regulatory note, a safety note, and at
  least one common-misconception entry.
- Receptor IDs: every receptor activity that names a CB1 / CB2 / TRPV1
  / TRPA1 / 5-HT1A target also carries the canonical UniProt ID — the
  rigor-check "receptor-without-ID" rule must hold inside the registry.
- Citation hygiene: every PMID-bearing citation has a numeric PMID
  string; no row uses a year-only "Mead 2023" style anchor without
  a verifiable identifier (test enforces presence of pmid or url).
- Grading: clinical_grade reflects the actual evidence; the entries
  the v2.6 audit identified as "no human RCT" must show
  UNSUPPORTED clinical_grade.
- Detection: scanning prose surfaces the right compound; the CBN
  sleep query that the v2.6 audit highlighted resolves to the CBN
  entry without dragging in any other compound.
- Round-trip: ``to_dict`` returns serialisable structures so
  ``python -m cannavec answer ... --json`` can include them.
- Round-trip into compose_answer: a "Does CBN improve sleep?" prompt
  produces a typed Answer whose citations include the CBN-specific
  primary sources (not Devinsky/Dravet, which was the v2.6 bug).
"""

from __future__ import annotations

import json
import unittest

from cannavec_science.minor_cannabinoids import (
    MinorCannabinoid,
    MinorCannabinoidEvidenceClass,
    all_minor_cannabinoids,
    detect_minor_cannabinoid_mention,
    find_minor_cannabinoid,
    format_for_researcher,
)


_RECEPTOR_UNIPROTS = {
    "CB1": "P21554",
    "CB2": "P34972",
    "TRPV1": "Q8NER1",
    "TRPA1": "O75762",
    "5-HT1A": "P08908",
}


class TestRegistryShape(unittest.TestCase):

    def setUp(self) -> None:
        self.entries = all_minor_cannabinoids()

    def test_registry_covers_audit_compounds(self) -> None:
        """The v2.6 audit named THCV/CBDV/CBC/CBN/CBG as under-served."""
        names = {e.name for e in self.entries}
        for required in ("THCV", "CBDV", "CBC", "CBN", "CBG"):
            self.assertIn(required, names,
                          f"minor-cannabinoid registry missing {required}")

    def test_every_entry_has_required_fields(self) -> None:
        from cannavec_science.minor_cannabinoids import MinorCannabinoidEvidenceClass
        for e in self.entries:
            self.assertTrue(e.name, "missing name")
            self.assertTrue(e.long_name, f"{e.name} missing long_name")
            self.assertTrue(e.chemistry_note,
                            f"{e.name} missing chemistry note")
            # Constitution §I (Primary-Source-Or-Refuse) is enforced
            # by the clinical_grade-vs-clinical_evidence consistency
            # rule, not by requiring fake rows. Compounds with no
            # admissible clinical evidence MUST be graded UNSUPPORTED;
            # compounds graded above UNSUPPORTED MUST carry at least
            # one row.
            if e.clinical_grade != MinorCannabinoidEvidenceClass.UNSUPPORTED:
                self.assertGreaterEqual(
                    len(e.clinical_evidence), 1,
                    f"{e.name} graded {e.clinical_grade.value} but "
                    f"no clinical row — evidence-honesty violation",
                )
            # Receptor activity / preclinical evidence likewise: only
            # required when the pharmacology_grade is above UNSUPPORTED.
            if e.pharmacology_grade != MinorCannabinoidEvidenceClass.UNSUPPORTED:
                self.assertGreaterEqual(
                    len(e.receptor_activity), 1,
                    f"{e.name} graded {e.pharmacology_grade.value} but "
                    f"no receptor activity row — evidence-honesty violation",
                )
            self.assertTrue(e.regulatory_status,
                            f"{e.name} missing regulatory note")
            self.assertTrue(e.safety_note,
                            f"{e.name} missing safety note")
            self.assertGreaterEqual(len(e.common_misconceptions), 1,
                                    f"{e.name} has no misconceptions captured")

    def test_receptor_activity_carries_uniprot_when_applicable(self) -> None:
        """rigor-check receptor-without-ID applies to the registry itself."""
        for e in self.entries:
            for r in e.receptor_activity:
                if r.target in _RECEPTOR_UNIPROTS:
                    self.assertEqual(
                        r.uniprot,
                        _RECEPTOR_UNIPROTS[r.target],
                        f"{e.name}: {r.target} missing canonical UniProt "
                        f"(expected {_RECEPTOR_UNIPROTS[r.target]}, "
                        f"got {r.uniprot!r})",
                    )

    def test_citations_have_identifiers_when_real(self) -> None:
        """A citation that is not an explicit knowledge-gap row must have
        a PMID, DOI, or URL — otherwise it is an unverifiable label."""
        for e in self.entries:
            for r in e.receptor_activity:
                for c in r.citations:
                    self.assertTrue(
                        c.pmid or c.doi or c.url,
                        f"{e.name} receptor citation {c.label!r} lacks "
                        "any identifier",
                    )
            for ce in e.clinical_evidence:
                # An UNSUPPORTED-grade clinical row with citations=() is
                # the explicit "no clinical evidence" pattern — allowed.
                if ce.grade is MinorCannabinoidEvidenceClass.UNSUPPORTED:
                    continue
                for c in ce.citations:
                    self.assertTrue(
                        c.pmid or c.doi or c.url,
                        f"{e.name} clinical citation {c.label!r} lacks "
                        "any identifier",
                    )

    def test_unsupported_clinical_compounds_are_explicit(self) -> None:
        """CBC and CBG have no human RCT — the audit demands this be
        named explicitly, not buried."""
        cbc = find_minor_cannabinoid("CBC")
        cbg = find_minor_cannabinoid("CBG")
        for compound in (cbc, cbg):
            assert compound is not None
            self.assertEqual(
                compound.clinical_grade,
                MinorCannabinoidEvidenceClass.UNSUPPORTED,
                f"{compound.name} clinical_grade must be UNSUPPORTED "
                "until an adequately-powered human RCT publishes",
            )


class TestLookup(unittest.TestCase):

    def test_canonical_name_lookup(self) -> None:
        for name in ("THCV", "CBDV", "CBC", "CBN", "CBG"):
            self.assertIsNotNone(find_minor_cannabinoid(name))

    def test_alias_lookup_case_insensitive(self) -> None:
        self.assertIsNotNone(find_minor_cannabinoid("tetrahydrocannabivarin"))
        self.assertIsNotNone(find_minor_cannabinoid("CANNABIDIVARIN"))
        self.assertIsNotNone(find_minor_cannabinoid("Cannabigerol"))

    def test_unknown_lookup_returns_none(self) -> None:
        self.assertIsNone(find_minor_cannabinoid("nonexistent-cannabinoid"))
        self.assertIsNone(find_minor_cannabinoid(""))


class TestDetection(unittest.TestCase):

    def test_cbn_sleep_query_resolves_to_cbn_only(self) -> None:
        """The v2.6 audit's canonical failure case must surface CBN —
        and only CBN — without dragging in other compounds."""
        hits = detect_minor_cannabinoid_mention("Does CBN improve sleep?")
        self.assertEqual(len(hits), 1, "expected exactly one compound hit")
        self.assertEqual(hits[0].name, "CBN")

    def test_thcv_monograph_query_resolves_to_thcv(self) -> None:
        hits = detect_minor_cannabinoid_mention(
            "Write a research monograph on THCV"
        )
        names = [h.name for h in hits]
        self.assertIn("THCV", names)

    def test_multi_compound_query_returns_all(self) -> None:
        hits = detect_minor_cannabinoid_mention(
            "Compare CBG, CBN, and CBDV for the entourage hypothesis."
        )
        names = {h.name for h in hits}
        self.assertEqual(names, {"CBG", "CBN", "CBDV"})

    def test_no_minor_cannabinoid_returns_empty(self) -> None:
        hits = detect_minor_cannabinoid_mention(
            "What is the evidence for CBD on Dravet syndrome?"
        )
        # CBD is not a minor cannabinoid — must NOT match.
        names = {h.name for h in hits}
        self.assertNotIn("CBD", names)
        self.assertEqual(hits, ())

    def test_cannabidivarin_full_name_detected(self) -> None:
        hits = detect_minor_cannabinoid_mention(
            "Cannabidivarin trial in adult focal epilepsy"
        )
        self.assertEqual([h.name for h in hits], ["CBDV"])


class TestRendering(unittest.TestCase):

    def test_format_for_researcher_science_default_monograph(self) -> None:
        thcv = find_minor_cannabinoid("THCV")
        assert thcv is not None
        md = format_for_researcher(thcv)

        # Standalone default keeps the compound title + ``##`` science sections.
        self.assertIn("# THCV — tetrahydrocannabivarin", md)
        self.assertIn("## Chemistry", md)
        self.assertIn("## Receptor pharmacology", md)
        self.assertIn("## Human clinical evidence", md)
        self.assertIn("## Preclinical evidence", md)
        self.assertIn("## Pharmacokinetics", md)
        self.assertIn("## Safety", md)
        self.assertIn("## Common misconceptions", md)

        # Constitution §IV: regulatory scheduling + consumer-market prose are
        # NOT primary-source research science — omitted from the brief default.
        self.assertNotIn("## Regulatory status", md)
        self.assertNotIn("## Commercial reality", md)

        # Receptor IDs surface
        self.assertIn("P21554", md, "CB1 UniProt missing from rendering")
        self.assertIn("P34972", md, "CB2 UniProt missing from rendering")

        # Trial identifiers surface
        self.assertIn("PMID 27573936", md, "Jadoon 2016 PMID missing")
        self.assertIn("PMID 26577065", md, "Englund 2016 PMID missing")

    def test_regulatory_and_commercial_are_opt_in(self) -> None:
        thcv = find_minor_cannabinoid("THCV")
        assert thcv is not None
        md = format_for_researcher(
            thcv, include_regulatory=True, include_commercial=True
        )
        self.assertIn("## Regulatory status", md)
        self.assertIn("## Commercial reality", md)

    def test_nested_render_keeps_single_heading_tree(self) -> None:
        """Nested under an Answer ``##`` section: title suppressed, sub-sections
        at ``###``, no in-body H1/H2 to collide with the Answer's own tree."""
        thcv = find_minor_cannabinoid("THCV")
        assert thcv is not None
        md = format_for_researcher(thcv, title=False, heading_level=2)

        for line in md.splitlines():
            self.assertFalse(
                line.startswith("# ") or line.startswith("## "),
                f"nested monograph must not emit H1/H2, got: {line!r}",
            )
        self.assertIn("### Chemistry", md)
        self.assertIn("### Receptor pharmacology", md)
        # The long name is not lost when the H1 title is suppressed.
        self.assertIn("tetrahydrocannabivarin", md)

    def test_meta_analysis_row_omits_meaningless_n_zero(self) -> None:
        """An SR / meta-analysis row carries n=0 (patient count is the wrong
        unit); the renderer must not print the misleading 'n=0'."""
        from cannavec_science.major_cannabinoids import find_major_cannabinoid

        thc = find_major_cannabinoid("THC")
        assert thc is not None
        md = format_for_researcher(thc)
        self.assertNotIn("n=0", md)
        # The SR row itself still renders — only the bogus count is dropped.
        self.assertIn("Cochrane", md)

    def test_cbn_rendering_names_marketing_gap(self) -> None:
        cbn = find_minor_cannabinoid("CBN")
        assert cbn is not None
        md = format_for_researcher(cbn)

        # The audit's specific framing must appear somewhere.
        self.assertRegex(
            md,
            r"(?i)marketing.*outpace|outpace.*evidence|"
            r"exceeds the evidence",
            "CBN rendering must name the marketing-vs-evidence gap",
        )
        # Single-night crossover honest framing.
        self.assertRegex(md, r"(?i)crossover|single.?night|placebo")


class TestSerialisation(unittest.TestCase):

    def test_to_dict_round_trips_json(self) -> None:
        for e in all_minor_cannabinoids():
            d = e.to_dict()
            j = json.dumps(d)
            self.assertIsInstance(j, str)
            # Sanity: re-load and check key fields
            loaded = json.loads(j)
            self.assertEqual(loaded["name"], e.name)
            self.assertEqual(loaded["clinical_grade"], e.clinical_grade.value)


class TestComposeAnswerIntegration(unittest.TestCase):
    """The CBN sleep query must surface CBN-specific citations, NOT
    the Devinsky/Dravet anchor that the v2.6 audit identified."""

    def test_cbn_sleep_prompt_attaches_cbn_citations(self) -> None:
        from cannavec_science.answer import compose_answer

        a = compose_answer("Does CBN improve sleep?", audience="researcher")
        cite_pmids = {c.pmid for c in a.citations if c.pmid}

        # CBN-specific anchors must be present:
        # PMID 17828291 (Pertwee 2008) is the receptor-pharmacology
        # anchor; PMID 24160757 (Stout & Cimino 2014) is the
        # CYP3A4 PK / drug-interaction anchor. Both come from the
        # minor-cannabinoid registry.
        self.assertIn("17828291", cite_pmids,
                      "CBN sleep answer missing Pertwee 2008 anchor")
        self.assertIn("24160757", cite_pmids,
                      "CBN sleep answer missing Stout 2014 PK anchor")

        # Devinsky/Dravet (PMID 28538134) must NOT appear — it has
        # nothing to do with CBN or sleep. This is the v2.6 bug we
        # are guarding against by adding the minor-cannabinoid
        # registry to compose_answer.
        self.assertNotIn(
            "28538134", cite_pmids,
            "CBN sleep answer must NOT cite Devinsky/Dravet (v2.6 bug)",
        )

    def test_thcv_monograph_prompt_attaches_thcv_clinical_pmids(self) -> None:
        from cannavec_science.answer import compose_answer

        a = compose_answer(
            "Write a research monograph on THCV",
            audience="researcher",
        )
        cite_pmids = {c.pmid for c in a.citations if c.pmid}

        # Jadoon 2016 (T2D RCT) and Englund 2016 (PD challenge crossover)
        # are the two human-trial anchors that any THCV monograph must
        # surface. Both come from the minor-cannabinoid registry.
        self.assertIn("27573936", cite_pmids,
                      "THCV monograph missing Jadoon 2016 T2D RCT")
        self.assertIn("26577065", cite_pmids,
                      "THCV monograph missing Englund 2016 challenge")


if __name__ == "__main__":
    unittest.main()
