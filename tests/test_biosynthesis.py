"""Tests for the cannabinoid biosynthesis pathway registry
(spec 005 US5 / FR-005).
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.biosynthesis import (
    BiosynthesisCitation,
    BiosynthesisRow,
    BiosynthesisTopic,
    all_biosynthesis_rows,
    detect_biosynthesis_mention,
    find_biosynthesis_rows,
    render_markdown,
)
from cannavec_science.cultivation_science import detect_cultivation_science_mention
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_five_rows(self):
        rows = all_biosynthesis_rows()
        self.assertGreaterEqual(len(rows), 5)

    def test_every_row_has_primary_citation(self):
        for r in all_biosynthesis_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(c.pmid or c.doi)

    def test_topic_coverage(self):
        topics = {r.topic for r in all_biosynthesis_rows()}
        for t in (
            BiosynthesisTopic.POLYKETIDE_ORIGIN,
            BiosynthesisTopic.PRENYLTRANSFERASE,
            BiosynthesisTopic.ACID_SYNTHASE,
            BiosynthesisTopic.HETEROLOGOUS_EXPRESSION,
        ):
            self.assertIn(t, topics)

    def test_every_row_has_enzyme_name(self):
        for r in all_biosynthesis_rows():
            self.assertTrue(r.enzyme_name)


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            BiosynthesisRow(
                name="bogus",
                topic=BiosynthesisTopic.POLYKETIDE_ORIGIN,
                claim_text="x",
                claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.SINGLE_ARM_OR_MECH,
                citations=(),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_olivetolic_acid_synthase(self):
        rows = detect_biosynthesis_mention(
            "olivetolic acid synthase polyketide pathway biosynthesis"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(BiosynthesisTopic.POLYKETIDE_ORIGIN, topics)

    def test_prenyltransferase_cbgas(self):
        rows = detect_biosynthesis_mention(
            "CBGAS aromatic prenyltransferase cannabis"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(BiosynthesisTopic.PRENYLTRANSFERASE, topics)

    def test_thca_synthase_mechanism(self):
        rows = detect_biosynthesis_mention(
            "THCA synthase FAD-dependent oxidocyclase Sirikantaramas 2004"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(BiosynthesisTopic.ACID_SYNTHASE, topics)

    def test_yeast_heterologous_expression(self):
        rows = detect_biosynthesis_mention(
            "Luo 2019 yeast cannabinoid heterologous expression Nature"
        )
        self.assertTrue(rows)
        topics = {r.topic for r in rows}
        self.assertIn(BiosynthesisTopic.HETEROLOGOUS_EXPRESSION, topics)


class DetectionNegativeTests(unittest.TestCase):
    def test_unrelated_prompt(self):
        self.assertEqual(
            detect_biosynthesis_mention("CBD in Dravet syndrome RCT"),
            (),
        )

    def test_empty_prompt(self):
        self.assertEqual(detect_biosynthesis_mention(""), ())


class CultivationCoexistenceTests(unittest.TestCase):
    """The v0.4 cultivation-science synthase-genetics rows must coexist
    with the v0.5 biosynthesis-pathway rows. Different topics:
    cultivation_science covers chemotype-inheritance from a breeder
    angle; biosynthesis covers the enzymology / pathway mechanism.
    """

    def test_thca_synthase_query_fires_both_detectors(self):
        prompt = "THCA synthase FAD-dependent oxidocyclase cannabis"
        # Biosynthesis fires on the FAD-oxidocyclase mechanism.
        self.assertTrue(detect_biosynthesis_mention(prompt))
        # Cultivation-science fires on the THCA-synthase keyword too
        # (chemotype-inheritance row).
        self.assertTrue(detect_cultivation_science_mention(prompt))


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim(self):
        for r in all_biosynthesis_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_olivetol_query_returns_taura_2009(self):
        a = compose_answer(
            "olivetolic acid synthase polyketide pathway biosynthesis"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("19454282", pmids)

    def test_luo_2019_query_returns_heterologous_row(self):
        a = compose_answer(
            "Luo 2019 yeast cannabinoid heterologous expression Nature"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("30814733", pmids)

    def test_thca_synthase_query_returns_sirikantaramas(self):
        a = compose_answer(
            "THCA synthase enzymology FAD-dependent oxidocyclase"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("15190053", pmids)

    def test_cbdas_query_returns_taura_1996(self):
        a = compose_answer(
            "CBDA synthase Taura 1996 cannabidiolic acid biosynthesis"
        )
        pmids = {c.pmid for c in a.citations if c.pmid}
        self.assertIn("8663284", pmids)


class RendererTests(unittest.TestCase):
    def test_render_includes_section_header(self):
        rows = all_biosynthesis_rows()
        md = render_markdown(rows)
        self.assertIn("Cannabinoid biosynthesis pathway registry", md)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        rows = find_biosynthesis_rows("polyketide_origin")
        self.assertTrue(rows)


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified(self):
        for r in all_biosynthesis_rows():
            self.assertTrue(r.last_verified)


if __name__ == "__main__":
    unittest.main()
