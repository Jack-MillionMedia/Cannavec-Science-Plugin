"""Tests for the cannabis-endocrinology registry (spec 026 US1 / FR-026).

Covers the ten canonical endocrine-axis questions: metabolic / insulin,
adipogenesis & leptin/ghrelin, diabetic ketoacidosis, HPT (thyroid),
growth-hormone & prolactin, HPG (gonadal), embryo implantation, HPA
(cortisol), CB1/CB2 desensitization, and bone remodeling / BMD.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import compose_answer
from cannavec_science.evidence import (
    ClaimType,
    EvidenceLevel,
    SourceTier,
)
from cannavec_science.uncertainty import grade_wording_consistency
from cannavec_science.banned_patterns import detect_banned_patterns
from cannavec_science.endocrine import (
    EndocrineCitation,
    EndocrineRow,
    EndocrineTopic,
    all_endocrine_rows,
    detect_endocrine_mention,
    find_endocrine_rows,
    render_markdown,
)


# The ten canonical endocrine questions, paired with the topic each must
# route to. These are the exact prompts from the system goal.
_CANONICAL = (
    (
        "How does chronic cannabis use alter peripheral insulin sensitivity "
        "and fasting glucose levels in patients with metabolic syndrome?",
        EndocrineTopic.METABOLIC_INSULIN,
    ),
    (
        "Does the activation of CB1 receptors by THC contribute to "
        "adipogenesis, and how does this affect leptin and ghrelin signaling?",
        EndocrineTopic.ADIPOGENESIS_LEPTIN,
    ),
    (
        "Is there a statistically significant correlation between heavy, "
        "daily cannabis use and the incidence of diabetic ketoacidosis in "
        "patients with Type 1 diabetes?",
        EndocrineTopic.DIABETIC_KETOACIDOSIS,
    ),
    (
        "How do phytocannabinoids impact the Hypothalamic-Pituitary-Thyroid "
        "axis, specifically altering levels of TSH, free T3, and free T4?",
        EndocrineTopic.THYROID_HPT,
    ),
    (
        "What is the acute impact of THC ingestion on growth hormone and "
        "prolactin secretion in adolescent subjects versus adults?",
        EndocrineTopic.GROWTH_HORMONE_PROLACTIN,
    ),
    (
        "Does chronic exposure to high-potency THC downregulate the "
        "Hypothalamic-Pituitary-Gonadal axis, thereby altering testosterone "
        "in males and the estrogen/progesterone balance in females?",
        EndocrineTopic.GONADAL_HPG,
    ),
    (
        "To what extent do endocannabinoids disrupt embryo implantation and "
        "early placental development?",
        EndocrineTopic.EMBRYO_IMPLANTATION,
    ),
    (
        "How does continuous cannabis use modify the "
        "Hypothalamic-Pituitary-Adrenal axis and cortisol awakening "
        "response in patients with chronic anxiety?",
        EndocrineTopic.ADRENAL_HPA,
    ),
    (
        "How do different ratios of THC to CBD affect the desensitization "
        "and internalization of CB1 and CB2 receptors in endocrine tissues?",
        EndocrineTopic.RECEPTOR_DESENSITIZATION,
    ),
    (
        "What are the downstream effects of cannabinoid receptor activation "
        "on osteoblast and osteoclast activity and overall bone mineral "
        "density?",
        EndocrineTopic.BONE_REMODELING,
    ),
)


class RegistryShapeTests(unittest.TestCase):
    def test_ten_rows_one_per_axis(self):
        rows = all_endocrine_rows()
        self.assertEqual(len(rows), 10)
        self.assertEqual(len({r.topic for r in rows}), 10)

    def test_every_row_has_primary_citation(self):
        for r in all_endocrine_rows():
            self.assertTrue(r.citations)
            for c in r.citations:
                self.assertTrue(
                    c.pmid or c.doi,
                    msg=f"{r.topic} citation {c.label!r} lacks identifier",
                )

    def test_evidence_levels_are_honest(self):
        # The cannabis-endocrinology literature is observational /
        # preclinical; the deterministic grader caps these at Level C.
        for r in all_endocrine_rows():
            self.assertIn(
                r.evidence_level,
                {EvidenceLevel.C, EvidenceLevel.D},
            )

    def test_topic_coverage(self):
        topics = {r.topic for r in all_endocrine_rows()}
        for t in (
            EndocrineTopic.METABOLIC_INSULIN,
            EndocrineTopic.ADIPOGENESIS_LEPTIN,
            EndocrineTopic.DIABETIC_KETOACIDOSIS,
            EndocrineTopic.THYROID_HPT,
            EndocrineTopic.GROWTH_HORMONE_PROLACTIN,
            EndocrineTopic.GONADAL_HPG,
            EndocrineTopic.EMBRYO_IMPLANTATION,
            EndocrineTopic.ADRENAL_HPA,
            EndocrineTopic.RECEPTOR_DESENSITIZATION,
            EndocrineTopic.BONE_REMODELING,
        ):
            self.assertIn(t, topics)

    def test_anchor_pmids_present(self):
        all_pmids = {
            c.pmid for r in all_endocrine_rows() for c in r.citations if c.pmid
        }
        for pmid in (
            "23684393",  # Penner 2013 NHANES insulin
            "19285260",  # Vettor 2009 adipocyte CB1
            "30398521",  # Akturk 2019 DKA
            "22821384",  # Bonnet 2013 thyroid (null)
            "12412841",  # Brown & Dobs 2002 endocrine review
            "30916627",  # Payne 2019 male fertility SR
            "16886060",  # Wang/Dey 2006 FAAH implantation
            "21631618",  # van Leeuwen 2011 TRAILS HPA
            "22940268",  # Lazenka 2012 CB1 desensitization
            "16407142",  # Ofek 2006 CB2 bone
        ):
            self.assertIn(pmid, all_pmids)


class EvidenceHonestyTests(unittest.TestCase):
    def test_no_row_overclaims_for_its_grade(self):
        # Every curated claim's wording must be consistent with Level C
        # (the wording-vs-grade checker would otherwise drop it).
        for r in all_endocrine_rows():
            violations = grade_wording_consistency(
                r.claim_text, EvidenceLevel.C
            )
            self.assertFalse(
                violations,
                msg=f"{r.topic} over-claims: "
                    f"{[v.matched_phrase for v in violations]}",
            )

    def test_claim_text_clean_of_banned_patterns(self):
        for r in all_endocrine_rows():
            hits = detect_banned_patterns(r.claim_text)
            self.assertFalse(hits, msg=f"{r.topic} trips: {hits}")

    def test_receptor_mentions_carry_identifiers(self):
        # Constitution §VI — receptors named in mechanism context must
        # carry a resolvable identifier. Any row that names CB1/CB2 must
        # also include its UniProt accession.
        for r in all_endocrine_rows():
            text = r.claim_text
            if "CB1" in text:
                self.assertIn("P21554", text, msg=f"{r.topic} CB1 no UniProt")
            if "CB2" in text:
                self.assertIn("P34972", text, msg=f"{r.topic} CB2 no UniProt")


class ValidationTests(unittest.TestCase):
    def test_row_without_citation_raises(self):
        with self.assertRaises(ValueError):
            EndocrineRow(
                name="bogus",
                topic=EndocrineTopic.METABOLIC_INSULIN,
                claim_text="x",
                claim_type=ClaimType.MECHANISM,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.JOURNAL_RCT,
                citations=(),
            )

    def test_citation_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            EndocrineRow(
                name="bogus",
                topic=EndocrineTopic.METABOLIC_INSULIN,
                claim_text="x",
                claim_type=ClaimType.MECHANISM,
                evidence_level=EvidenceLevel.C,
                source_tier=SourceTier.JOURNAL_RCT,
                citations=(EndocrineCitation(label="orphan"),),
            )


class DetectionPositiveTests(unittest.TestCase):
    def test_each_canonical_question_routes_to_its_topic(self):
        for prompt, expected_topic in _CANONICAL:
            rows = detect_endocrine_mention(prompt)
            self.assertTrue(rows, msg=f"no detection for: {prompt[:50]}")
            self.assertIn(
                expected_topic,
                {r.topic for r in rows},
                msg=f"{prompt[:50]} did not route to {expected_topic}",
            )

    def test_latex_receptor_notation_still_detects(self):
        # The goal prompts arrive with LaTeX \(CB_{1}\) markup.
        rows = detect_endocrine_mention(
            r"Do \(CB_{1}\) and \(CB_{2}\) receptors desensitize with "
            r"chronic THC and internalization?"
        )
        self.assertIn(
            EndocrineTopic.RECEPTOR_DESENSITIZATION,
            {r.topic for r in rows},
        )


class DetectionNegativeTests(unittest.TestCase):
    def test_endocrine_without_cannabis_is_quiet(self):
        # Insulin question with NO cannabinoid context must not fire.
        self.assertEqual(
            detect_endocrine_mention(
                "How does metformin alter fasting insulin and HOMA-IR in "
                "type 2 diabetes?"
            ),
            (),
        )

    def test_cannabis_without_endocrine_is_quiet(self):
        self.assertEqual(
            detect_endocrine_mention(
                "What is the CB1 binding affinity of Δ⁹-THC versus CBD?"
            ),
            (),
        )

    def test_unrelated_prompt(self):
        self.assertEqual(
            detect_endocrine_mention("CBD in Dravet syndrome RCT"),
            (),
        )

    def test_empty(self):
        self.assertEqual(detect_endocrine_mention(""), ())


class ClaimRoundTripTests(unittest.TestCase):
    def test_to_claim_returns_typed_claim_graded_c(self):
        for r in all_endocrine_rows():
            claim = r.to_claim()
            self.assertEqual(claim.text, r.claim_text)
            self.assertEqual(claim.claim_type, r.claim_type)
            self.assertTrue(claim.sources)
            # Honest grade: single observational / mechanistic study caps
            # at Level C.
            self.assertEqual(
                claim.best_supportable_grade(),
                EvidenceLevel.C,
                msg=f"{r.topic} graded "
                    f"{claim.best_supportable_grade().value}, expected C",
            )


class FreshnessTests(unittest.TestCase):
    def test_every_row_has_last_verified(self):
        for r in all_endocrine_rows():
            self.assertTrue(r.last_verified)
            self.assertEqual(len(r.last_verified), 10)

    def test_watch_pmids_populated_from_citations(self):
        for r in all_endocrine_rows():
            self.assertTrue(r.watch_pmids)


class FindRowsTests(unittest.TestCase):
    def test_find_by_topic(self):
        self.assertTrue(find_endocrine_rows("metabolic_insulin"))

    def test_find_by_name_substring(self):
        self.assertTrue(find_endocrine_rows("Penner"))


class RendererTests(unittest.TestCase):
    def test_render_includes_section_header(self):
        md = render_markdown(all_endocrine_rows())
        self.assertIn("Endocrinology registry", md)

    def test_render_includes_anchor_pmid(self):
        md = render_markdown(all_endocrine_rows())
        self.assertIn("23684393", md)


class IntegrationWithComposerTests(unittest.TestCase):
    def test_every_canonical_question_surfaces_a_cited_claim(self):
        for prompt, _topic in _CANONICAL:
            a = compose_answer(prompt)
            self.assertFalse(
                a.is_refusal, msg=f"unexpected refusal: {prompt[:50]}"
            )
            self.assertGreaterEqual(
                len(a.claims), 1,
                msg=f"0 claims for: {prompt[:60]}",
            )
            # Every surfaced claim must carry a primary-source citation (§I).
            self.assertTrue(
                {c.pmid for c in a.citations if c.pmid},
                msg=f"no PMID citation for: {prompt[:60]}",
            )

    def test_insulin_question_surfaces_penner(self):
        a = compose_answer(_CANONICAL[0][0])
        self.assertIn("23684393", {c.pmid for c in a.citations if c.pmid})

    def test_highest_grade_is_level_c(self):
        a = compose_answer(_CANONICAL[2][0])  # DKA
        self.assertIsNotNone(a.evidence_summary)
        self.assertEqual(a.evidence_summary.highest_grade, EvidenceLevel.C)


class InventoryTests(unittest.TestCase):
    def test_endocrine_group_in_inventory(self):
        from cannavec_science.registries import (
            all_registry_groups,
            build_inventory,
        )
        self.assertIn("endocrine", all_registry_groups())
        inv = build_inventory("endocrine")
        # 10 curated rows in the inventory group.
        self.assertTrue(inv.groups)


if __name__ == "__main__":
    unittest.main()
