"""Major-cannabinoid monograph registry.

Sister module to :mod:`cannavec.minor_cannabinoids`. The minor-
cannabinoid registry covers THCV / CBDV / CBC / CBN / CBG — compounds
that lack rich coverage in the AE / interactions / contraindications
/ populations registries and therefore need their own monograph
view. The major cannabinoids (Δ⁹-THC, CBD) are covered comprehensively
across those four registries, so they were intentionally left out of
the minor-cannabinoid registry.

But: when a user asks a comparison-style prompt ("Compare THC, CBD,
CBG, CBN, THCV"), :func:`cannavec.answer.compose_answer` emits a
monograph block per matched compound. Without major-cannabinoid
entries, the comparison block silently omits THC and CBD — exactly
the two compounds the user named first. Closes the Oracle Auditor
2026-05-18 "major-cannabinoid monograph view" finding (the
replacement issue for the originally mis-diagnosed ISSUE-005).

Design rules (identical to minor-cannabinoids):

- Every entry has at least one primary citation.
- Receptor activity rows carry a UniProt ID where applicable.
- Clinical-evidence rows declare an explicit GRADE level.
- Common misconceptions are listed so audience-surface prompts can
  refuse them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cannavec_science.minor_cannabinoids import (
    ClinicalEvidenceRow,
    MinorCannabinoid,
    MinorCannabinoidCitation,
    MinorCannabinoidEvidenceClass,
    PreclinicalEvidenceRow,
    ReceptorActivity,
)


@dataclass(frozen=True)
class MajorCannabinoid(MinorCannabinoid):
    """A major-cannabinoid record. Schema is identical to
    :class:`MinorCannabinoid` so the existing renderer can emit it
    unchanged; the dataclass exists for type-clarity in callers."""


# ─── Citations re-used across the THC and CBD entries ──────────────────

_PERTWEE_2008 = MinorCannabinoidCitation(
    label="Pertwee 2008 — CB1/CB2 receptor pharmacology of Δ⁹-THC, CBD & THCV (Br J Pharmacol)",
    pmid="17828291", doi="10.1038/sj.bjp.0707442", year=2008,
)
# Primary preclinical CBD-seizure study (replaces the binding review formerly
# mis-cited for rodent seizure efficacy): in-vivo PTZ + in-vitro hippocampal-
# slice models, CB1-independent anticonvulsant effect.
_JONES_2010 = MinorCannabinoidCitation(
    label=("Jones 2010 — CBD antiepileptiform & antiseizure properties "
           "in vitro and in vivo (J Pharmacol Exp Ther)"),
    pmid="19906779", doi="10.1124/jpet.109.159145", year=2010,
)
_DEVINSKY_2017 = MinorCannabinoidCitation(
    label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
    pmid="28538134", doi="10.1056/NEJMoa1611618", year=2017,
)
_DEVINSKY_2018_LGS = MinorCannabinoidCitation(
    label="Devinsky 2018 — CBD in Lennox-Gastaut syndrome (NEJM)",
    pmid="29768152", year=2018,
)
_WHITING_2015 = MinorCannabinoidCitation(
    label="Whiting 2015 — Cannabinoids for medical use SR/MA (JAMA)",
    pmid="26103030", year=2015,
)
_MUCKE_2018 = MinorCannabinoidCitation(
    label="Mücke 2018 — Cannabis-based medicines for chronic neuropathic pain (Cochrane SR)",
    pmid="29513392", doi="10.1002/14651858.CD012182.pub2", year=2018,
)
_VOLKOW_2014 = MinorCannabinoidCitation(
    label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
    pmid="24897085", year=2014,
)
_HUESTIS_2007 = MinorCannabinoidCitation(
    label=(
        "Huestis MA, Chem Biodivers 2007 — Δ⁹-THC pharmacokinetics "
        "across inhaled / oral / oromucosal routes"
    ),
    pmid="17712819", year=2007,
)
_GROTENHERMEN_2003 = MinorCannabinoidCitation(
    label=(
        "Grotenhermen F, Clin Pharmacokinet 2003 — clinical pharmacokinetics "
        "of cannabinoids"
    ),
    pmid="12648025", year=2003,
)
_TAYLOR_2018 = MinorCannabinoidCitation(
    label="Taylor 2018 — Phase 1 PK of CBD oral solution in healthy adults",
    pmid="30374683", year=2018,
)


_REGISTRY: tuple[MajorCannabinoid, ...] = (
    MajorCannabinoid(
        name="THC",
        long_name="Δ⁹-tetrahydrocannabinol",
        aliases=(
            "Δ9-THC", "Δ⁹-THC", "delta-9-THC", "delta-9-tetrahydrocannabinol",
            "dronabinol", "tetrahydrocannabinol",
        ),
        chemistry_note=(
            "The principal psychoactive phytocannabinoid in Cannabis "
            "sativa. C21H30O2, MW 314.5 g/mol. Decarboxylates from "
            "THCA (acidic precursor) on heating. Highly lipophilic "
            "(logP ≈ 6.97). Exists primarily as the (-)-trans "
            "stereoisomer; Δ⁸-THC is a positional isomer with lower "
            "CB1 potency. Dronabinol is the synthetic Δ⁹-THC "
            "formulation FDA-approved as Marinol / Syndros."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="partial agonist",
                affinity_note="Ki ≈ 5–40 nM depending on assay",
                assay="competitive binding + functional GTPγS",
                citations=(_PERTWEE_2008,),
            ),
            ReceptorActivity(
                target="CB2",
                uniprot="P34972",
                gene_symbol="CNR2",
                activity="partial agonist",
                affinity_note="Ki similar order to CB1 (low nM)",
                assay="competitive binding in CB2-transfected cells",
                citations=(_PERTWEE_2008,),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.B,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="chronic neuropathic pain (adjunctive)",
                design="systematic review / meta-analysis (Cochrane)",
                n=0,
                dose_route=(
                    "inhaled 10-25% Δ⁹-THC flower, nabiximols 1-12 "
                    "sprays/day, oral 2.5-20 mg Δ⁹-THC + 5-40 mg CBD"
                ),
                outcome=(
                    "Modest reduction in pain scores; NNT ≈ 20 for "
                    "≥30% reduction; substantial heterogeneity; "
                    "evidence quality low to moderate (Mücke 2018)"
                ),
                grade=MinorCannabinoidEvidenceClass.B,
                citations=(_MUCKE_2018, _WHITING_2015),
                caveats=(
                    "Effect sizes are clinically modest.",
                    "Honest synthesis includes null trials.",
                ),
            ),
            ClinicalEvidenceRow(
                indication=(
                    "chemotherapy-induced nausea and vomiting (CINV) "
                    "refractory to first-line antiemetics"
                ),
                design="systematic review",
                n=0,
                dose_route="nabilone 1-2 mg oral BID; dronabinol 5-10 mg oral",
                outcome=(
                    "Nabilone and dronabinol demonstrate antiemetic "
                    "efficacy in CINV; second-line indication."
                ),
                grade=MinorCannabinoidEvidenceClass.B,
                citations=(_WHITING_2015,),
                caveats=(
                    "Better-tolerated alternatives (5-HT3 antagonists, "
                    "NK1 antagonists) are first-line for most regimens.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.B,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="rodent / primate CB1-knockout phenotypes",
                species_or_assay="C57BL/6 mice; CB1-KO line",
                dose_or_concentration="varies (analgesia / hypothermia / hypolocomotion assays)",
                outcome=(
                    "CB1 knockout abolishes Δ⁹-THC analgesia, "
                    "hypothermia, hypolocomotion, and the "
                    "psychotomimetic-equivalent phenotypes — anchors "
                    "CB1 as the load-bearing target."
                ),
                bridging_to_clinic=(
                    "Mechanistic anchor for human pharmacology. "
                    "Quantitative translation to human dose-response "
                    "remains via clinical PK/PD studies."
                ),
                grade=MinorCannabinoidEvidenceClass.B,
                citations=(_VOLKOW_2014, _PERTWEE_2008),
            ),
        ),
        regulatory_status=(
            "**US-federal:** Schedule I (CSA, 1970). 2024 DEA NPRM "
            "proposes Schedule III; comment period closed 2024-07-22; "
            "final-rule decision pending. Dronabinol (synthetic Δ⁹-"
            "THC) is Schedule III as Marinol and Schedule II as "
            "Syndros oral solution.\n\n"
            "**US-state:** patchwork — 25+ adult-use, 15+ medical-"
            "only, remainder limited / none.\n\n"
            "**EU:** product-by-product approvals; nabiximols (Sativex) "
            "registered for MS spasticity in multiple member states.\n\n"
            "**UK:** Schedule 2 of the Misuse of Drugs Regulations "
            "2018 (CBPM rescheduling); prescription-only by specialist "
            "clinicians.\n\n"
            "**Canada / Australia / Israel:** legal medical and (in "
            "Canada) adult-use programs."
        ),
        commercial_reality=(
            "Dronabinol (synthetic Δ⁹-THC) is the FDA-approved "
            "single-molecule preparation. Botanical preparations "
            "(flower, concentrate, edibles) vary widely in potency "
            "and consistency; the same labelled %Δ⁹-THC delivers "
            "substantially different effects depending on cultivar, "
            "terpene profile, route, and individual PK. State-"
            "mandated COAs cover potency and contaminants but vary "
            "in rigor; the supply chain remains uneven."
        ),
        safety_note=(
            "Dose-dependent psychotomimetic effects, anxiety, "
            "tachycardia, motor and cognitive impairment, driving "
            "impairment, and dependence with chronic exposure. CHS "
            "(cannabis hyperemesis syndrome) is a recognised syndrome "
            "of chronic heavy use. Adolescent exposure carries "
            "cognitive-development concerns; pregnancy is an "
            "avoidance population. Drug interactions concentrate at "
            "CYP2C9 substrates and CNS depressants."
        ),
        pharmacokinetics_note=(
            "Inhalation: peak plasma 5–10 min, Cmax dose-dependent, "
            "elimination half-life 25–36 h (chronic users longer due "
            "to lipophilic redistribution). Oral: bioavailability "
            "6–20% with substantial first-pass; onset 60–180 min; "
            "Tmax 1–3 h. Oromucosal (nabiximols): bioavailability "
            "intermediate; onset 30–60 min. Highly lipophilic — "
            "distributes into adipose tissue with slow redistribution."
        ),
        key_uncertainties=(
            "Magnitude of cognitive-impairment effects from chronic "
            "moderate use in adults remains contested.",
            "Pharmacogenomics of CYP2C9 polymorphisms on Δ⁹-THC "
            "metabolism is documented but rarely clinically applied.",
            "The drug-drug interaction profile with novel agents "
            "(monoclonal antibodies, immune-modulators) is "
            "incompletely characterised.",
        ),
        common_misconceptions=(
            "Δ⁹-THC and Δ⁸-THC are not pharmacologically equivalent "
            "— Δ⁸-THC is approximately half as potent at CB1 in vitro; "
            "clinical data are sparse.",
            "Indica vs sativa labelling does NOT predict THC content "
            "or pharmacological effect — chemovar genotype is the "
            "load-bearing variable.",
            "Δ⁹-THC is not a 'natural pain reliever' for everyone — "
            "effect size is modest in pooled SR data, and adverse-"
            "event profile favours alternatives where available.",
            "Dronabinol (Marinol) is NOT the same drug experience as "
            "smoked or vaporised cannabis — route, formulation, and "
            "terpene profile substantially alter the effect.",
        ),
        citations=(
            _PERTWEE_2008, _VOLKOW_2014, _WHITING_2015, _MUCKE_2018,
            _HUESTIS_2007, _GROTENHERMEN_2003,
        ),
    ),
    MajorCannabinoid(
        name="CBD",
        long_name="cannabidiol",
        aliases=("cannabidiol", "Epidiolex", "Epidyolex"),
        chemistry_note=(
            "Non-intoxicating phytocannabinoid. C21H30O2, MW "
            "314.5 g/mol (constitutional isomer of Δ⁹-THC). "
            "Decarboxylates from CBDA on heating. Highly lipophilic "
            "(logP ≈ 6.3). Epidiolex (CBD oral solution) is the "
            "FDA-approved single-molecule preparation for paediatric "
            "Dravet syndrome, Lennox-Gastaut syndrome, and tuberous "
            "sclerosis complex."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="negative allosteric modulator",
                affinity_note=(
                    "Very low orthosteric CB1 affinity; functional "
                    "effects best understood as negative allosteric "
                    "modulation of CB1 signalling."
                ),
                assay="functional GTPγS in CB1-transfected cells",
                citations=(_PERTWEE_2008,),
            ),
            ReceptorActivity(
                target="5-HT1A",
                uniprot="P08908",
                gene_symbol="HTR1A",
                activity="agonist (in vitro)",
                affinity_note=(
                    "Proposed mechanism for some of CBD's anxiolytic "
                    "and antinociceptive preclinical effects."
                ),
                assay="functional cAMP / receptor binding",
                citations=(_PERTWEE_2008,),
            ),
            ReceptorActivity(
                target="TRPV1",
                uniprot="Q8NER1",
                gene_symbol="TRPV1",
                activity="agonist",
                affinity_note=(
                    "One of the proposed anticonvulsant mechanisms. "
                    "Mechanism is multi-factorial; no single receptor "
                    "explains the Dravet / LGS efficacy."
                ),
                assay="Ca²⁺ flux in TRPV1-transfected cells",
                citations=(_PERTWEE_2008,),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.B,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="convulsive seizures in Dravet syndrome",
                design="RCT (NEJM)",
                n=120,
                dose_route="CBD 20 mg/kg/day oral",
                outcome=(
                    "Median monthly convulsive seizure frequency "
                    "reduced 38.9% on CBD 20 mg/kg/day vs 13.3% on "
                    "placebo (n=120, 14-week double-blind). NNT ≈ 7 "
                    "for ≥50% responder rate."
                ),
                # Per-indication grade: a single pivotal RCT caps at Level B
                # (§VII single-study rule) — matching the deterministic grade the
                # composed answer surfaces. The aggregate `clinical_grade` (A)
                # below reflects the replicated body (Dravet + LGS + TSC RCTs).
                grade=MinorCannabinoidEvidenceClass.B,
                citations=(_DEVINSKY_2017,),
                caveats=(
                    "Pivotal trial; effect replicated in Lennox-"
                    "Gastaut and TSC trials.",
                    "Hepatic transaminase elevation and somnolence "
                    "are common AEs.",
                ),
            ),
            ClinicalEvidenceRow(
                indication="drop seizures in Lennox-Gastaut syndrome",
                design="RCT (NEJM)",
                n=171,
                dose_route="CBD 20 mg/kg/day oral",
                outcome=(
                    "Median monthly drop-seizure frequency reduced "
                    "41.9% on CBD 20 mg/kg/day vs 17.2% on placebo."
                ),
                # Single pivotal RCT → Level B per the §VII single-study cap
                # (see the Dravet row above); the aggregate grade is A.
                grade=MinorCannabinoidEvidenceClass.B,
                citations=(_DEVINSKY_2018_LGS,),
                caveats=(
                    "Same hepatic and CNS-depressant interaction "
                    "monitoring as Dravet.",
                    "Clobazam co-treated subgroup drives effect "
                    "magnitude in some analyses.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.A,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="rodent + in-vitro seizure models",
                species_or_assay=(
                    "pentylenetetrazole (in vivo, rat); Mg²⁺-free & 4-AP "
                    "hippocampal slices (in vitro)"
                ),
                dose_or_concentration="1–100 mg/kg (in vivo); 0.01–100 µM (in vitro)",
                outcome=(
                    "CBD reduced the incidence of severe seizures and "
                    "mortality in the pentylenetetrazole model (significant "
                    "at 100 mg/kg) and suppressed epileptiform burst activity "
                    "in hippocampal slices — an anticonvulsant effect that "
                    "appears largely CB1-independent."
                ),
                bridging_to_clinic=(
                    "Rodent mg/kg doses do not translate directly to human "
                    "dosing; the Dravet / LGS RCT data anchor the clinical "
                    "dose range."
                ),
                grade=MinorCannabinoidEvidenceClass.B,
                citations=(_JONES_2010,),
            ),
        ),
        regulatory_status=(
            "**US-federal:** Epidiolex (cannabidiol oral solution) is "
            "Schedule V; non-Epidiolex CBD has no FDA-approved over-"
            "the-counter pathway. Hemp-derived CBD (≤0.3% Δ⁹-THC by "
            "dry weight) is federally legal under the 2018 Farm Bill "
            "but lacks an FDA-approved dietary-supplement framework.\n\n"
            "**EU:** EMA-approved as Epidyolex for the same paediatric "
            "epilepsy indications. EFSA novel-food assessment applies "
            "to ingestible non-medical CBD products.\n\n"
            "**UK:** MHRA-approved Epidyolex; novel-food regime for "
            "consumer CBD via the FSA.\n\n"
            "**Canada / Australia:** legal under prescription pathways "
            "with controlled-substance scheduling."
        ),
        commercial_reality=(
            "The consumer CBD market is regulated unevenly. "
            "Independent COA analyses have repeatedly found "
            "mislabelled potency (under and over) and Δ⁹-THC "
            "contamination in non-medical preparations. Epidiolex / "
            "Epidyolex is the only preparation with FDA-grade "
            "consistency. Hemp-derived 'CBD' products may also contain "
            "detectable Δ⁹-THC and / or hemp-derived intoxicants "
            "(Δ⁸-THC, HHC) — check the COA."
        ),
        safety_note=(
            "Generally well-tolerated. Most common AEs: somnolence, "
            "diarrhoea, decreased appetite, elevated transaminases. "
            "Hepatic transaminase elevations are dose-dependent and "
            "concentrate in the valproate-co-treated subgroup. "
            "Significant CYP-mediated drug interactions: CBD inhibits "
            "CYP3A4, CYP2C9, CYP2C19; clinically relevant for "
            "clobazam, tacrolimus, warfarin, and many CYP substrates."
        ),
        pharmacokinetics_note=(
            "Oral (Epidiolex / Epidyolex): bioavailability 6–19% "
            "fasted; high-fat meal increases AUC 4–5×. Tmax 2.5–5 h. "
            "Elimination half-life 56–61 h after chronic dosing. "
            "Extensive hepatic metabolism via CYP2C19 / CYP3A4 to "
            "active 7-OH-CBD metabolite and inactive 7-COOH-CBD. "
            "Sublingual / oromucosal preparations show faster onset "
            "but lower total bioavailability."
        ),
        key_uncertainties=(
            "Optimal dose-response for CBD in adult anxiety and PTSD "
            "remains underspecified — most clinical data come from "
            "small SAD / public-speaking models.",
            "CBD's pharmacokinetic interactions with antiseizure "
            "drugs in the non-Dravet population are incompletely "
            "characterised.",
            "Long-term safety of consumer-grade CBD products at doses "
            "far below the Epidiolex range (e.g. 25 mg/day) rests on "
            "inference, not adequately-powered RCTs.",
        ),
        common_misconceptions=(
            "'Non-psychoactive' is shorthand and incomplete. CBD has "
            "central nervous system activity (it would not anchor "
            "anti-seizure efficacy otherwise); it is non-intoxicating, "
            "which is the more precise term.",
            "Consumer-grade CBD at typical 25–50 mg doses is NOT "
            "evidence-based for any indication — the Epidiolex "
            "20 mg/kg/day dose anchors the only Level-A indications.",
            "Full-spectrum 'entourage effect' is a marketing claim "
            "that exceeds the current clinical evidence base.",
            "CBD does NOT show on most workplace drug screens — but "
            "Δ⁹-THC contamination in some CBD products can produce "
            "positive screens; check the COA.",
        ),
        citations=(
            _PERTWEE_2008, _DEVINSKY_2017, _DEVINSKY_2018_LGS,
            _TAYLOR_2018, _WHITING_2015,
        ),
    ),
)


def all_major_cannabinoids() -> tuple[MajorCannabinoid, ...]:
    """Return the curated registry (read-only)."""
    return _REGISTRY


def find_major_cannabinoid(name: str) -> MajorCannabinoid | None:
    """Look up a single entry by canonical name (case-insensitive)."""
    needle = name.strip().lower()
    for c in _REGISTRY:
        if c.name.lower() == needle:
            return c
        if c.long_name.lower() == needle:
            return c
        for alias in c.aliases:
            if alias.lower() == needle:
                return c
    return None


_DETECT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(
        r"\bTHC\b|\btetrahydrocannabinol\b|\bΔ\s*9?[- ]*THC\b|"
        r"\bdelta[- ]?9[- ]?THC\b|\bdronabinol\b|\bmarinol\b",
        re.IGNORECASE,
    ), "THC"),
    (re.compile(
        r"\bCBD\b|\bcannabidiol\b|\bEpidiolex\b|\bEpidyolex\b",
        re.IGNORECASE,
    ), "CBD"),
)


def detect_major_cannabinoid_mention(text: str) -> tuple[MajorCannabinoid, ...]:
    """Return registry entries for every major cannabinoid named in
    ``text``. Deduplicated; preserves registry order.

    Used by :func:`cannavec.answer.compose_answer` to emit a monograph
    section per major cannabinoid named in a comparison-style prompt
    ("Compare THC, CBD, CBG, CBN, THCV"). Without this, THC and CBD
    are silently absent from the comparison even though they are the
    two most-named cannabinoids — the Oracle Auditor 2026-05-18 T2
    coverage gap.
    """
    seen: set[str] = set()
    out: list[MajorCannabinoid] = []
    for entry, _span in detect_major_cannabinoid_mention_with_spans(text):
        if entry.name not in seen:
            seen.add(entry.name)
            out.append(entry)
    return tuple(out)


def detect_major_cannabinoid_mention_with_spans(
    text: str,
) -> tuple[tuple[MajorCannabinoid, tuple[int, int]], ...]:
    """Return ``(entry, span)`` pairs for every major-cannabinoid hit.

    Spec 003 US1 / FR-001 — exposes match spans so the compose layer
    can suppress Δ⁹-THC / CBD hits that overlap a more specific minor-
    cannabinoid mention (Δ⁸-THC, THCV, CBDV, etc.). The first-fire
    span per match is returned; downstream consumers deduplicate by
    entry name.
    """
    out: list[tuple[MajorCannabinoid, tuple[int, int]]] = []
    for pat, name in _DETECT_PATTERNS:
        for m in pat.finditer(text):
            entry = find_major_cannabinoid(name)
            if entry is None:
                continue
            out.append((entry, m.span()))
    return tuple(out)
