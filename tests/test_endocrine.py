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
    # ── Spec 027 — second endocrine question wave ──────────────────────
    (
        "How does cannabis use influence the onset age and clinical "
        "progression of autoimmune thyroiditis (Hashimoto's disease)?",
        EndocrineTopic.AUTOIMMUNE_THYROIDITIS,
    ),
    (
        "What role do exogenous cannabinoids play in modulating pancreatic "
        "beta-cell apoptosis and survival in response to inflammatory "
        "cytokines?",
        EndocrineTopic.BETA_CELL_SURVIVAL,
    ),
    (
        "How does maternal cannabis use alter the fetal endocannabinoid tone "
        "and subsequent neuroendocrine development of the offspring?",
        EndocrineTopic.PRENATAL_NEUROENDOCRINE,
    ),
    (
        "Does long-term cannabis consumption affect the circadian rhythm of "
        "melatonin secretion and associated metabolic homeostasis?",
        EndocrineTopic.MELATONIN_CIRCADIAN,
    ),
    (
        "What are the distinct impacts of isolated CBD versus full-spectrum "
        "hemp extract on cortisol levels during acute stress testing?",
        EndocrineTopic.CBD_FULLSPECTRUM_CORTISOL,
    ),
    (
        "Does cannabis hyperemesis syndrome (CHS) trigger significant, acute "
        "fluctuations in antidiuretic hormone (ADH) and electrolyte balance?",
        EndocrineTopic.CHS_ADH_ELECTROLYTE,
    ),
    (
        "How does the administration of CB1 receptor antagonists or inverse "
        "agonists affect energy expenditure and uncoupling protein 1 (UCP1) "
        "expression in brown adipose tissue?",
        EndocrineTopic.CB1_ANTAGONIST_BAT,
    ),
    (
        "To what degree does daily cannabis use alter the lipid profile, "
        "specifically HDL, LDL, and very-low-density lipoprotein (VLDL) "
        "synthesis in the liver?",
        EndocrineTopic.LIPID_PROFILE,
    ),
    (
        "Does localized cannabinoid receptor signaling within the "
        "gastrointestinal tract modify the secretion of incretin hormones "
        "like GLP-1 and GIP?",
        EndocrineTopic.GI_INCRETIN,
    ),
    (
        "How do different delivery methods (inhalation, ingestion, topical) "
        "vary in their peak pharmacokinetic impact on serum testosterone and "
        "luteinizing hormone (LH) levels?",
        EndocrineTopic.DELIVERY_ROUTE_HPG,
    ),
)


class RegistryShapeTests(unittest.TestCase):
    def test_twenty_rows_one_per_axis(self):
        # Spec 026 shipped 10 endocrine axes; spec 027 added 10 more.
        rows = all_endocrine_rows()
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({r.topic for r in rows}), 20)

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
            # Spec 027 — second wave anchors.
            "20191092",  # Nagarkatti 2009 CB2 immunomodulation (Hashimoto gap)
            "34872800",  # González-Mariscal 2021 Abn-CBD β-cell
            "36810840",  # Frau & Melis 2023 prenatal THC dopamine
            "36539991",  # Ried 2022 RCT cannabis melatonin
            "31915861",  # Appiah-Kusi 2020 CBD cortisol RCT
            "27567272",  # Sorensen 2017 CHS review
            "19057531",  # Verty 2008 rimonabant BAT/UCP1
            "27186350",  # Reimann & Gribble 2016 incretin
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
        self.assertTrue(inv.groups)


class FalseConfidenceRegressionTests(unittest.TestCase):
    """Spec 027 — a research tool must not answer a DIFFERENT question with
    false confidence. These pin the specific off-target failures found when
    the spec-027 questions were first run against the system."""

    def test_melatonin_secretion_does_not_surface_drug_interaction(self):
        # "How does cannabis affect melatonin SECRETION" is endocrine
        # physiology — it must NOT match the CBN×melatonin-supplement
        # drug-interaction row.
        from cannavec_science.interactions import detect_interaction_mention
        rows = detect_interaction_mention(
            "how does long-term cannabis use affect melatonin secretion and "
            "circadian rhythm"
        )
        self.assertEqual(
            rows, (),
            msg="endogenous-melatonin question wrongly matched a drug "
                "interaction",
        )

    def test_genuine_melatonin_supplement_interaction_still_fires(self):
        # The guard must NOT break a real co-administration query.
        from cannavec_science.interactions import detect_interaction_mention
        rows = detect_interaction_mention(
            "does CBN interact with melatonin supplement taken together at "
            "bedtime"
        )
        self.assertTrue(
            rows,
            msg="legitimate CBN×melatonin interaction query stopped firing",
        )

    def test_melatonin_question_leads_with_secretion_evidence(self):
        # End-to-end: the composed answer must lead with the melatonin
        # secretion RCT, not an interaction claim.
        a = compose_answer(
            "Does long-term cannabis consumption affect the circadian rhythm "
            "of melatonin secretion and associated metabolic homeostasis?"
        )
        self.assertIn("36539991", {c.pmid for c in a.citations if c.pmid})
        self.assertIn("melatonin", (a.short_answer or "").lower())
        # The off-target interaction PMID must not be the lead citation.
        self.assertNotIn("interacts with", (a.short_answer or "").lower())

    def test_hashimoto_leads_with_autoimmune_not_generic_thyroid(self):
        # The Hashimoto's question must surface the autoimmune-specific
        # (honest-gap) row, not only the generic HPT-function answer.
        a = compose_answer(
            "How does cannabis use influence the onset age and clinical "
            "progression of autoimmune thyroiditis (Hashimoto's disease)?"
        )
        self.assertIn("autoimmun", (a.short_answer or "").lower())

    def test_ucp1_question_leads_with_bat_thermogenesis(self):
        # The UCP1/BAT question must lead with the rimonabant-BAT row, not a
        # generic adipogenesis claim.
        a = compose_answer(
            "How does the administration of CB1 receptor antagonists or "
            "inverse agonists affect energy expenditure and uncoupling "
            "protein 1 (UCP1) expression in brown adipose tissue?"
        )
        sa = (a.short_answer or "").lower()
        self.assertTrue("ucp1" in sa or "brown adipose" in sa)


class HonestGapTests(unittest.TestCase):
    """The honest-gap rows must say 'not directly studied' rather than
    manufacture a confident off-target answer."""

    def test_honest_gap_rows_signal_the_gap(self):
        from cannavec_science.endocrine import find_endocrine_rows
        for topic in ("autoimmune_thyroiditis", "chs_adh_electrolyte",
                      "delivery_route_hpg"):
            rows = find_endocrine_rows(topic)
            self.assertTrue(rows, msg=f"{topic} missing")
            text = rows[0].claim_text.lower()
            # Each explicitly flags the absence of direct evidence.
            self.assertTrue(
                any(p in text for p in (
                    "no direct", "no study", "not been", "unstudied",
                    "evidence gap", "not directly", "secondary",
                    "has not", "not a primary", "inference",
                )),
                msg=f"{topic} does not flag its evidence gap",
            )


if __name__ == "__main__":
    unittest.main()
