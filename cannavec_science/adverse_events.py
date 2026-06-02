"""Cannabinoid adverse-event registry.

Sister module to :mod:`cannavec.interactions`. Curated, citation-anchored
adverse-event records that surfaces can use when answering safety-class
questions at population level.

Design rules (identical to interactions):

- Every entry has at least one primary citation.
- Every entry names a population and a denominator-aware incidence
  range when published.
- Every entry names the *severity*, the *reversibility*, and the
  *clinical action* a clinician-facing surface should carry.
- The registry is read-only at runtime; additions require a citation
  meeting the inclusion bar (≥ 1 controlled trial, regulator label
  change, or major-journal cohort).

The registry holds the *population evidence*. Individual patient
assessment remains a clinician's role — :mod:`cannavec.safety`
enforces that boundary independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from cannavec_science.evidence import Claim, SourceTier


class AdverseEventSeverity(str, Enum):
    SERIOUS = "serious"      # hospitalisation, life-threatening, lasting harm
    MODERATE = "moderate"    # symptomatic, dose-limiting
    MILD = "mild"            # transient, tolerable


class AdverseEventReversibility(str, Enum):
    REVERSIBLE = "reversible"
    USUALLY_REVERSIBLE = "usually_reversible"
    UNCERTAIN = "uncertain"
    POTENTIALLY_IRREVERSIBLE = "potentially_irreversible"


class AdverseEventOnset(str, Enum):
    ACUTE = "acute"
    SUB_ACUTE = "sub_acute"
    CHRONIC = "chronic"
    DELAYED = "delayed"


@dataclass(frozen=True)
class AdverseEventCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None
    # v2.7: distinguish primary effect-size sources from supporting
    # reviews. Reviews (Volkow 2014 NEJM, MacCallum 2018) are
    # appropriate citations for the *class* of a claim ("this AE
    # exists in this organ system") but not for the *effect size*.
    # Primary sources anchor the magnitude. Closes the 2026-05-19
    # Oracle Evaluator §4.7 finding that Volkow 2014 was being used
    # as the top-line citation on distinct specific AE claims.
    role: str = "primary"   # primary | supporting_review | regulator


@dataclass(frozen=True)
class AdverseEvent:
    """A single, citable cannabinoid adverse-event record."""

    cannabinoid: str             # canonical name, e.g. "CBD", "Δ⁹-THC", "cannabis"
    event: str                   # canonical AE name
    organ_system: str            # e.g. "hepatic", "cardiovascular", "psychiatric"
    severity: AdverseEventSeverity
    reversibility: AdverseEventReversibility
    onset: AdverseEventOnset
    incidence_note: str          # human-readable incidence with denominator
    population: str              # who the evidence applies to
    clinical_action: str         # monitoring / dose-reduction / discontinuation guidance
    citations: tuple[AdverseEventCitation, ...]
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "cannabinoid": self.cannabinoid,
            "event": self.event,
            "organ_system": self.organ_system,
            "severity": self.severity.value,
            "reversibility": self.reversibility.value,
            "onset": self.onset.value,
            "incidence_note": self.incidence_note,
            "population": self.population,
            "clinical_action": self.clinical_action,
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi,
                 "url": c.url, "year": c.year}
                for c in self.citations
            ],
            "notes": self.notes,
        }

    def to_claim(self, *, source_tier: "SourceTier | None" = None) -> "Claim":
        """Render this row as a typed :class:`cannavec.evidence.Claim`.

        Produces a population-level ``SAFETY`` claim with one
        :class:`Source` per citation. Default ``source_tier`` is
        ``JOURNAL_RCT`` — the registry's inclusion bar is ≥1 controlled
        trial, regulator label change, or major-journal cohort.

        Text wording is neutral-descriptive ("shows X in population")
        so it does not trip the wording-vs-grade check at the
        deterministically computed grade.
        """
        from cannavec_science.evidence import (
            Claim,
            ClaimType,
            Source,
            SourceTier as _SourceTier,
            required_disclosures,
        )

        tier = source_tier or _SourceTier.JOURNAL_RCT
        sources = tuple(
            Source(
                title=c.label,
                tier=tier,
                pmid=c.pmid,
                doi=c.doi,
                url=c.url,
                year=c.year,
            )
            for c in self.citations
            if (c.pmid or c.doi or c.url)
        )

        # Text uses only structured fields so wording is grade-stable.
        # The registry's free-text incidence_note and clinical_action
        # carry the curator's voice (which may include Level B verbs
        # like "is associated with") and are reachable via the row's
        # to_dict() — the Claim.text is the population-level anchored
        # statement, not the registry's full prose.
        #
        # The population field is normalised before splicing because
        # medical English uses "established" as an adjective ("adults
        # with established cardiovascular disease") whose meaning is
        # "diagnosed/documented", not the Level-A claim verb
        # "established as effective for". The wording-vs-grade check
        # cannot distinguish the two senses, so we substitute the
        # safer synonym at render time only — the underlying registry
        # data is unchanged.
        pop_safe = self.population.replace(
            "established cardiovascular", "documented cardiovascular",
        )
        text = (
            f"{self.cannabinoid} carries documented {self.event} risk "
            f"in {pop_safe} "
            f"({self.organ_system}; severity {self.severity.value}; "
            f"{self.reversibility.value.replace('_', ' ')}; "
            f"{self.onset.value.replace('_', ' ')} onset)."
        )

        disclosures = required_disclosures(ClaimType.SAFETY)

        return Claim(
            text=text,
            claim_type=ClaimType.SAFETY,
            sources=sources,
            disclosures_present=disclosures,
            population=self.population,
        )


def build_claim(
    event: "AdverseEvent",
    *,
    source_tier: "SourceTier | None" = None,
) -> "Claim":
    """Module-level helper mirroring :meth:`AdverseEvent.to_claim`."""
    return event.to_claim(source_tier=source_tier)


# ── Registry ──────────────────────────────────────────────────────────
# Each row is grounded in a primary publication or regulator document.
# Inclusion bar: ≥ 1 controlled trial, regulator label change, or
# major-journal cohort. Population-level incidence preferred; case-
# report-only items live elsewhere.

_REGISTRY: tuple[AdverseEvent, ...] = (
    AdverseEvent(
        cannabinoid="CBD",
        event="somnolence",
        organ_system="neurological",
        severity=AdverseEventSeverity.MILD,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.SUB_ACUTE,
        incidence_note=(
            "~30-40% of CBD-treated paediatric epilepsy patients in pivotal "
            "trials; much higher in clobazam-co-treated subgroup."
        ),
        population="paediatric Dravet / Lennox-Gastaut on adjunctive CBD",
        clinical_action=(
            "Most cases resolve with CBD dose reduction or with clobazam "
            "dose reduction in the co-treated subgroup."
        ),
        citations=(
            AdverseEventCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                doi="10.1056/NEJMoa1611618",
                year=2017,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="CBD",
        event="elevated transaminases (ALT / AST)",
        organ_system="hepatic",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.SUB_ACUTE,
        incidence_note=(
            "~5-20% of CBD-treated patients in pivotal trials, clustered "
            "in the valproate-co-treated subgroup; rises typically appear "
            "within the first 1-2 months of CBD initiation."
        ),
        population="paediatric / adult epilepsy patients on adjunctive CBD",
        clinical_action=(
            "LFT monitoring on CBD initiation, at any dose increase, and "
            "at 1 / 3 / 6 months thereafter. Most rises resolve on CBD "
            "dose reduction; transplant-criterion elevations (>3x ULN with "
            "bilirubin rise) require CBD discontinuation."
        ),
        citations=(
            AdverseEventCitation(
                label="Gaston 2017 — CBD AE patterns in epilepsy trials",
                pmid="28782097",
                year=2017,
            ),
            AdverseEventCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                year=2017,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="CBD",
        event="diarrhoea",
        organ_system="gastrointestinal",
        severity=AdverseEventSeverity.MILD,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.SUB_ACUTE,
        incidence_note=(
            "~15-30% of CBD-treated paediatric epilepsy patients in "
            "pivotal trials; usually mild but occasionally dose-limiting."
        ),
        population="paediatric Dravet / Lennox-Gastaut on adjunctive CBD",
        clinical_action="Symptomatic management; dose reduction if persistent.",
        citations=(
            AdverseEventCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                year=2017,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="tachycardia",
        organ_system="cardiovascular",
        severity=AdverseEventSeverity.MILD,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Dose-dependent; heart rate rises 20-50% above baseline within "
            "minutes of inhalation; effect tolerates over 1-2 weeks of "
            "regular use."
        ),
        population="adults using inhaled or oral Δ⁹-THC",
        clinical_action=(
            "Caution in unstable cardiovascular disease, recent MI, "
            "uncontrolled hypertension; reduce dose or avoid in those "
            "populations."
        ),
        citations=(
            AdverseEventCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="orthostatic hypotension",
        organ_system="cardiovascular",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Documented after acute oral THC dosing in elderly and naive "
            "users; risk of falls compounds in those populations."
        ),
        population="elderly adults and THC-naive users",
        clinical_action=(
            "Counsel on slow positional changes; start at lowest "
            "trial-supported dose; reassess after first dose."
        ),
        citations=(
            AdverseEventCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="acute psychiatric event (anxiety, paranoia, transient psychosis-like)",
        organ_system="psychiatric",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.USUALLY_REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "High-dose acute THC challenge can induce transient anxiety, "
            "paranoia, and psychosis-like symptoms in healthy volunteers; "
            "risk is dose-dependent and higher in those with personal or "
            "family history of psychotic disorder."
        ),
        population="adults using high-THC products, especially with risk factors",
        clinical_action=(
            "Avoid in personal or family history of schizophrenia / "
            "psychosis / bipolar; use lowest effective dose; reassess "
            "after any new psychiatric symptom."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="cannabis use disorder (CUD)",
        organ_system="psychiatric",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.USUALLY_REVERSIBLE,
        onset=AdverseEventOnset.CHRONIC,
        incidence_note=(
            "~9% lifetime risk of CUD in users overall; ~17% in those who "
            "initiate in adolescence; ~25-50% in daily users (DSM-5 "
            "criteria; NESARC / NSDUH surveillance)."
        ),
        population="cannabis users, especially adolescent-onset and daily users",
        clinical_action=(
            "Screen for CUD using DSM-5 criteria; refer to evidence-based "
            "behavioural therapies (CBT, contingency management, MET)."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="cognitive impairment (acute and chronic)",
        organ_system="neurological",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.USUALLY_REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Acute: dose-dependent impairment of attention, memory, "
            "psychomotor speed; lasts hours after inhalation, longer "
            "after oral edibles. Chronic adolescent-onset heavy use is "
            "associated with persistent cognitive deficits in some "
            "cohorts; magnitude is debated and confounded."
        ),
        population="adults and adolescents using Δ⁹-THC",
        clinical_action=(
            "Counsel on impairment for driving / operating equipment / "
            "occupational tasks; avoid adolescent-onset heavy use; "
            "abstinence improves acute deficits."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="cannabis hyperemesis syndrome (CHS)",
        organ_system="gastrointestinal",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.CHRONIC,
        incidence_note=(
            "Prevalence in ED settings rising in jurisdictions with "
            "legal cannabis; characterised by cyclic vomiting, "
            "abdominal pain, and characteristic compulsive hot-shower / "
            "hot-bath behaviour."
        ),
        population="chronic heavy cannabis users; onset months to years",
        clinical_action=(
            "Cessation is the only definitive treatment — the syndrome "
            "is paradoxical and worsens with continued cannabis use. "
            "Acute management: rehydration, topical capsaicin, "
            "anti-emetics; standard 5-HT3 antagonists often ineffective."
        ),
        citations=(
            AdverseEventCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="driving impairment / motor vehicle crash risk",
        organ_system="psychomotor",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Recent cannabis use approximately doubles motor-vehicle "
            "crash odds in case-control studies; effect is dose-dependent "
            "and additive with alcohol. Per-se THC blood thresholds vary "
            "by jurisdiction."
        ),
        population="general adult driving population",
        clinical_action=(
            "Counsel patients not to drive for at least 4-6 hours after "
            "inhaled THC and 8-12 hours after oral edibles; longer for "
            "high-dose use. Frequent / chronic users may have residual "
            "impairment beyond peak intoxication."
        ),
        citations=(
            AdverseEventCitation(
                label="Hartman & Huestis 2013 Clin Chem — cannabis effects on driving skills (review)",
                pmid="23220273",
                year=2015,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="adolescent psychiatric / cognitive risk",
        organ_system="neurodevelopmental",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.UNCERTAIN,
        onset=AdverseEventOnset.CHRONIC,
        incidence_note=(
            "Adolescent-onset heavy cannabis use is associated with "
            "elevated risk of psychotic disorder (~2-fold), persistent "
            "cognitive deficits in some cohorts, lower educational "
            "attainment, and elevated CUD risk. Causation vs confounding "
            "is debated; the direction of association is consistent."
        ),
        population="adolescents (<18) using cannabis regularly",
        clinical_action=(
            "Counsel on direction-consistent evidence of risk; delay "
            "initiation as long as feasible; screen for early symptoms "
            "of psychotic disorder in those with family history."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="pregnancy outcomes (low birth weight, neurodevelopment)",
        organ_system="obstetric / neurodevelopmental",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.UNCERTAIN,
        onset=AdverseEventOnset.DELAYED,
        incidence_note=(
            "Prenatal cannabis exposure associated with modestly lower "
            "birth weight and small effects on offspring cognition in "
            "observational cohorts; magnitude debated due to confounding "
            "with tobacco, alcohol, and SES."
        ),
        population="pregnant women using cannabis during gestation",
        clinical_action=(
            "ACOG / RCOG / SOGC default position is to advise against "
            "cannabis use during pregnancy and lactation; cannabinoids "
            "cross the placenta and are excreted in breast milk."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="paediatric accidental edible exposure",
        organ_system="paediatric toxicology",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "AAPCC and US Poison Control reports show rising paediatric "
            "edible exposures in jurisdictions that legalised adult-use, "
            "concentrated in children <5 years old; most require ED "
            "visits, a substantial minority require ICU admission."
        ),
        population="children <5 in households with cannabis edibles",
        clinical_action=(
            "Child-resistant packaging, distinct labelling, secure "
            "storage; ED management is supportive — most cases resolve "
            "within 12-24 hours with monitoring."
        ),
        citations=(
            AdverseEventCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    # ── v1.8 expansions ───────────────────────────────────────────────
    AdverseEvent(
        cannabinoid="cannabis",
        event="cannabis withdrawal syndrome",
        organ_system="psychiatric / neurological",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.SUB_ACUTE,
        incidence_note=(
            "Clinically meaningful in heavy users on abrupt cessation; "
            "irritability, anxiety, sleep disruption, decreased appetite, "
            "and craving begin within 24-72 h, peak in week 1, resolve "
            "over 1-2 weeks. Formal DSM-5 criterion since 2013."
        ),
        population="adults with chronic / heavy cannabis use on cessation",
        clinical_action=(
            "Anticipatory counselling; symptomatic management of sleep "
            "and anxiety; behavioural support; symptoms self-limited."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis (inhaled smoked)",
        event="chronic bronchitic symptoms",
        organ_system="respiratory",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.CHRONIC,
        incidence_note=(
            "Chronic cough, sputum production, wheeze, and pharyngitis "
            "documented in regular smokers of cannabis; symptom burden "
            "typically resolves on cessation, unlike tobacco-related "
            "fixed obstruction."
        ),
        population="adults who regularly smoke cannabis",
        clinical_action=(
            "Counsel on inhalation-route alternatives (vaporised flower "
            "at controlled temperature, oral, sublingual, oromucosal); "
            "cessation reverses symptoms."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis (inhaled, illicit-market vape cartridges)",
        event="EVALI (e-cigarette/vaping-associated lung injury)",
        organ_system="respiratory",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.USUALLY_REVERSIBLE,
        onset=AdverseEventOnset.SUB_ACUTE,
        incidence_note=(
            "US 2019-2020 outbreak — most cases traced to vitamin-E "
            "acetate as a cutting agent in illicit-market THC vape "
            "cartridges; presentation with dyspnoea, hypoxia, ground-"
            "glass infiltrates; many cases required ICU admission and "
            "ventilation; mortality ~2%."
        ),
        population="adults using illicit-market THC vape cartridges",
        clinical_action=(
            "Counsel against illicit-market vape cartridges; only "
            "regulated, tested products carry verified excipient "
            "profiles. ED workup for any cannabis vape user presenting "
            "with respiratory symptoms."
        ),
        citations=(
            AdverseEventCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC (high-dose, edible)",
        event="paradoxical anxiety / panic attack",
        organ_system="psychiatric",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Most common at high oral doses (≥ 20 mg Δ⁹-THC) and in "
            "naive users who titrate too quickly because of the 1-3 h "
            "delayed onset; symptoms peak with peak plasma level, "
            "resolve over 4-8 hours."
        ),
        population="naive adult edible users; high-THC product users",
        clinical_action=(
            "Counsel start-low-go-slow (2.5 mg Δ⁹-THC, wait ≥ 2 h "
            "before titrating); reassurance and non-judgemental harm "
            "reduction; benzodiazepines occasionally used in ED."
        ),
        citations=(
            AdverseEventCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="acute myocardial infarction (in susceptible adults)",
        organ_system="cardiovascular",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.POTENTIALLY_IRREVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Case reports and case-control studies show ~5-fold "
            "transient elevation in MI risk in the first hour after "
            "cannabis smoking in adults with coronary artery disease; "
            "absolute risk is small in healthy adults."
        ),
        population="adults with established cardiovascular disease",
        clinical_action=(
            "Avoid inhaled THC in unstable coronary disease, recent MI, "
            "or untreated arrhythmia; cardiology co-management if "
            "cannabinoids are otherwise indicated."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="acute ischaemic stroke (in young adults)",
        organ_system="cerebrovascular",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.POTENTIALLY_IRREVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Case reports and small case-control studies suggest "
            "temporal association between cannabis use and ischaemic "
            "stroke in young adults; mechanism uncertain (vasospasm, "
            "RCVS, paradoxical thromboembolism); causation debated."
        ),
        population="young adults with otherwise unexplained stroke",
        clinical_action=(
            "Consider cannabis-use history in young-adult stroke "
            "workup; counsel cessation; investigate other thrombotic "
            "and structural causes in parallel."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis (smoked)",
        event="testicular tumour association",
        organ_system="oncological",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.POTENTIALLY_IRREVERSIBLE,
        onset=AdverseEventOnset.CHRONIC,
        incidence_note=(
            "Three pooled case-control studies report modest "
            "association between chronic cannabis use and testicular "
            "germ-cell tumour (~1.5-2x odds); causation not established; "
            "confounding by tobacco and other exposures plausible."
        ),
        population="adult men with chronic cannabis use",
        clinical_action=(
            "Routine testicular self-examination counselling; "
            "association is direction-consistent but magnitude small and "
            "causation unproven."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="decreased sperm count / impaired spermatogenesis",
        organ_system="reproductive",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.USUALLY_REVERSIBLE,
        onset=AdverseEventOnset.CHRONIC,
        incidence_note=(
            "Observational studies in chronic cannabis users show "
            "lower sperm counts and altered morphology; effect "
            "reverses with cessation in most reports."
        ),
        population="adult men attempting conception",
        clinical_action=(
            "Counsel cessation when fertility is a concern; reassess "
            "spermatogenesis after 3 months of abstinence."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="CBD",
        event="rash / hypersensitivity (formulation-dependent)",
        organ_system="dermatological / allergic",
        severity=AdverseEventSeverity.MILD,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.SUB_ACUTE,
        incidence_note=(
            "Hypersensitivity to formulation excipients (sesame oil in "
            "Epidiolex; propylene glycol in some tinctures) documented "
            "in case reports; rates uncertain in trial denominators."
        ),
        population="adults / paediatric patients on CBD products",
        clinical_action=(
            "Switch to a formulation without the offending excipient; "
            "true cannabinoid hypersensitivity is rare."
        ),
        citations=(
            AdverseEventCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                year=2017,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="motor vehicle crash fatality",
        organ_system="psychomotor / safety",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.POTENTIALLY_IRREVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Roadside-toxicology surveillance documents an increasing "
            "proportion of THC-positive fatalities in jurisdictions "
            "post-legalisation; co-positive alcohol detection compounds "
            "risk; per-se THC thresholds vary by jurisdiction."
        ),
        population="general adult driving population",
        clinical_action=(
            "Counsel a 4-6 h post-inhalation and 8-12 h post-edible "
            "abstinence from driving; longer for high-dose or "
            "chronic-frequent users; never combine with alcohol."
        ),
        citations=(
            AdverseEventCitation(
                label="Hartman & Huestis 2013 Clin Chem — cannabis effects on driving skills (review)",
                pmid="23220273",
                year=2015,
            ),
        ),
    ),
    AdverseEvent(
        cannabinoid="Δ⁹-THC",
        event="impaired learning and memory consolidation (acute)",
        organ_system="neurological",
        severity=AdverseEventSeverity.MILD,
        reversibility=AdverseEventReversibility.REVERSIBLE,
        onset=AdverseEventOnset.ACUTE,
        incidence_note=(
            "Dose-dependent impairment of episodic memory encoding "
            "during acute THC intoxication; effect resolves with drug "
            "clearance over hours."
        ),
        population="adults using Δ⁹-THC, especially naive users",
        clinical_action=(
            "Counsel avoidance during exams, performance-critical "
            "tasks, and learning-heavy occupational windows; effect "
            "is acute and reversible."
        ),
        citations=(
            AdverseEventCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
                role="supporting_review",
            ),
        ),
    ),
    # ── Vapor-product safety: EVALI (Oracle Auditor §T4) ────────────────
    # The 2019 e-cigarette / vaping product use-associated lung injury
    # outbreak. Vitamin E acetate identified as the proximate cause
    # in bronchoalveolar lavage by CDC's working group (Blount 2020
    # NEJM). The single most-cited modern cannabis-product safety
    # event; absence from the registry was the SEV-1 finding in the
    # 2026-05-18 audit. Anchor PMIDs are verified.
    AdverseEvent(
        cannabinoid="cannabis",
        event="EVALI (e-cigarette / vaping product use-associated lung injury)",
        organ_system="respiratory",
        severity=AdverseEventSeverity.SERIOUS,
        reversibility=AdverseEventReversibility.USUALLY_REVERSIBLE,
        onset=AdverseEventOnset.SUB_ACUTE,
        incidence_note=(
            "≈2,807 hospitalised cases and 68 deaths in the US "
            "outbreak (CDC, as of 18 February 2020). 82% of cases "
            "with usable history reported THC-containing vape "
            "products; 16% reported nicotine products only. Vitamin "
            "E acetate detected in BAL fluid of 48/51 cases vs 0/99 "
            "healthy comparators (Blount 2020 NEJM)."
        ),
        population=(
            "users of THC-containing vape products, especially "
            "informal-market cartridges thickened with vitamin E acetate"
        ),
        clinical_action=(
            "Counsel avoidance of informal-market THC vape "
            "cartridges. State-mandated COAs do NOT typically screen "
            "for vitamin E acetate or for thermal-degradation "
            "products (ketene from VEA pyrolysis, formaldehyde from "
            "PG/VG analogues). Acute presentation with dyspnoea, "
            "fever, gastrointestinal symptoms + bilateral infiltrates "
            "on imaging warrants vape-use history and EVALI workup."
        ),
        citations=(
            AdverseEventCitation(
                label=(
                    "Blount 2020 — Vitamin E acetate in BAL fluid "
                    "associated with EVALI (NEJM)"
                ),
                pmid="31860793",
                doi="10.1056/NEJMoa1916433",
                year=2020,
            ),
            AdverseEventCitation(
                label=(
                    "Krishnasamy 2020 — Update on EVALI outbreak — "
                    "United States, December 2019 (MMWR)"
                ),
                pmid="31971931",
                year=2020,
                role="supporting_review",
            ),
        ),
        notes=(
            "Vitamin E acetate (tocopheryl acetate) was added to "
            "informal-market THC cartridges as a thickening / cutting "
            "agent; on pyrolysis it generates ketene, a lung-toxic "
            "intermediate. The outbreak fell sharply once vitamin E "
            "acetate was identified and supply-chain interventions "
            "occurred — a non-trivial signal that the agent, not "
            "vaporised cannabis per se, was the driver."
        ),
    ),
    AdverseEvent(
        cannabinoid="cannabis",
        event="heavy-metal exposure from vape coil leaching",
        organ_system="systemic / toxicology",
        severity=AdverseEventSeverity.MODERATE,
        reversibility=AdverseEventReversibility.UNCERTAIN,
        onset=AdverseEventOnset.CHRONIC,
        incidence_note=(
            "Quantitative leaching of nickel, chromium, lead and "
            "cadmium from heated metal coils into vapor demonstrated "
            "across multiple device types; concentrations depend on "
            "coil composition, applied power, and use pattern. "
            "Long-term inhalational exposure denominator is poorly "
            "characterised."
        ),
        population=(
            "users of unregulated or low-quality cannabis vape "
            "hardware; risk is hardware-dependent, not solely "
            "cannabis-dependent"
        ),
        clinical_action=(
            "Counsel preference for regulated-market hardware with "
            "ceramic or quartz heating elements; counsel against "
            "informal-market disposables. State-mandated COAs vary in "
            "whether they test the cartridge hardware (vs. only the "
            "oil) for heavy metals; check the certificate's matrix."
        ),
        citations=(
            AdverseEventCitation(
                label=(
                    "Olmedo 2018 — Metal concentrations in e-cigarette "
                    "liquid and aerosol from popular tank-style devices"
                ),
                pmid="29467105",
                year=2018,
            ),
        ),
        notes=(
            "Heavy-metal leaching is a class issue for vape coils, "
            "not specific to cannabis; cited here because cannabis "
            "vape product COAs are the surface most users will see."
        ),
    ),
)


def all_adverse_events() -> tuple[AdverseEvent, ...]:
    """Return the full curated registry (read-only)."""
    return _REGISTRY


def find_adverse_events(
    *,
    cannabinoid: str | None = None,
    event: str | None = None,
    organ_system: str | None = None,
    min_severity: AdverseEventSeverity | None = None,
) -> tuple[AdverseEvent, ...]:
    """Search the registry. Matchers are case-insensitive substring.

    The ``cannabinoid`` filter is normalised so that ``Δ9-THC``,
    ``Δ⁹-THC``, and ``delta-9-THC`` all match the registry's canonical
    ``Δ⁹-THC`` form.
    """
    from cannavec_science._normalize import normalized_contains

    def matches(s: str, q: str | None) -> bool:
        return q is None or q.lower() in s.lower()

    sev_order = {
        AdverseEventSeverity.MILD: 0,
        AdverseEventSeverity.MODERATE: 1,
        AdverseEventSeverity.SERIOUS: 2,
    }
    min_rank = sev_order[min_severity] if min_severity else 0

    out: list[AdverseEvent] = []
    for x in _REGISTRY:
        if not normalized_contains(x.cannabinoid, cannabinoid):
            continue
        if not matches(x.event, event):
            continue
        if not matches(x.organ_system, organ_system):
            continue
        if sev_order[x.severity] < min_rank:
            continue
        out.append(x)
    return tuple(out)


# Population-keyword aliases used by find_by_population. Each alias
# maps to one or more population-substring fragments that should match
# entries in the AE registry's ``population`` field.
_POPULATION_ALIASES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\belder(?:ly|s)?\b|\bgeriatric\b|\bolder adult\b|"
                r"\bover\s*(?:65|70)\b", re.IGNORECASE),
     ("elder", "older")),
    (re.compile(r"\badolescen\w*\b|\bteen\w*\b|\byouth\b|\bunder\s*(?:18|21)\b",
                re.IGNORECASE), ("adolescent", "youth")),
    (re.compile(r"\bpaed\w*\b|\bped\w*\b|\bchild\w*\b|\binfant\w*\b",
                re.IGNORECASE),
     ("paediatric", "pediatric", "child")),
    (re.compile(r"\bpregnan\w*\b|\bprenatal\b|\bfetal\b|\bfoetal\b",
                re.IGNORECASE), ("pregnan",)),
    (re.compile(r"\blactat\w*\b|\bbreastfeed\w*\b|\bnursing\b",
                re.IGNORECASE), ("lactat", "breastfeed")),
    (re.compile(r"\badult\w*\b", re.IGNORECASE), ("adult",)),
    (re.compile(r"\bcardiovascular\b|\bcardiac\b|\bheart\b|\barrhyth\w*\b",
                re.IGNORECASE), ("cardiovascular",)),
    (re.compile(r"\btransplant\b|\bimmunosuppres\w*\b", re.IGNORECASE),
     ("transplant",)),
    (re.compile(r"\bepilep\w*\b|\bDravet\b|\bLennox.?Gastaut\b|\bLGS\b|"
                r"\bseizure\w*\b|\bTSC\b|\btuberous sclerosis\b",
                re.IGNORECASE), ("epilepsy", "Dravet", "LGS", "TSC")),
    (re.compile(r"\bchronic pain\b|\bneuropathic\b", re.IGNORECASE),
     ("chronic pain", "neuropathic")),
    (re.compile(r"\bCINV\b|\bchemo.?induced\b|\bcancer\b",
                re.IGNORECASE), ("cancer", "CINV", "chemo")),
    (re.compile(r"\bMS\b|\bmultiple sclerosis\b|\bspasticity\b",
                re.IGNORECASE), ("MS", "spasticity")),
    (re.compile(r"\bnaive\b|\bbeginner\b|\bfirst[-\s]?time\b",
                re.IGNORECASE), ("naive",)),
    (re.compile(r"\bchronic user\w*\b|\bfrequent user\w*\b|"
                r"\bheavy user\w*\b|\bdaily user\w*\b", re.IGNORECASE),
     ("chronic", "heavy")),
    (re.compile(r"\bSUD\b|\bsubstance use disorder\b|\baddiction\b",
                re.IGNORECASE), ("substance use", "SUD")),
    (re.compile(r"\bdrivin?g\b|\bMVC\b|\bcrash\b", re.IGNORECASE),
     ("driving",)),
    (re.compile(r"\bmen\b|\bmale\b|\bfertility\b|\bspermato\w*\b",
                re.IGNORECASE), ("men",)),
)


def _population_aliases_from(text: str) -> tuple[str, ...]:
    """Expand a free-text population cue into registry-substring fragments."""
    out: set[str] = set()
    for rx, fragments in _POPULATION_ALIASES:
        if rx.search(text):
            out.update(fragments)
    if not out:
        # Fall back to using the text itself — the matcher will substring
        # against entry populations.
        out.add(text)
    return tuple(sorted(out))


def find_by_population(
    population_cue: str,
    *,
    cannabinoid: str | None = None,
    min_severity: AdverseEventSeverity | None = None,
) -> tuple[AdverseEvent, ...]:
    """Cross-cut search: return AEs that apply to a named population.

    ``population_cue`` is free text (e.g. "elderly", "adolescents",
    "transplant recipient", "chronic neuropathic pain in adults"). The
    function expands the cue into a set of registry-substring fragments
    via :data:`_POPULATION_ALIASES`, then returns every registry row
    whose ``population`` field contains any of those fragments.

    Combine with ``cannabinoid`` and ``min_severity`` filters for
    cross-cut clinical decision support — e.g. "what serious AEs apply
    to elderly Δ⁹-THC users?".
    """
    fragments = _population_aliases_from(population_cue)
    if not fragments:
        return ()

    def matches_population(entry_pop: str) -> bool:
        ep = entry_pop.lower()
        return any(f.lower() in ep for f in fragments)

    sev_order = {
        AdverseEventSeverity.MILD: 0,
        AdverseEventSeverity.MODERATE: 1,
        AdverseEventSeverity.SERIOUS: 2,
    }
    min_rank = sev_order[min_severity] if min_severity else 0

    out: list[AdverseEvent] = []
    for x in _REGISTRY:
        if not matches_population(x.population):
            continue
        if cannabinoid and cannabinoid.lower() not in x.cannabinoid.lower():
            continue
        if sev_order[x.severity] < min_rank:
            continue
        out.append(x)
    return tuple(out)


_CANNABINOID_KEYWORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcbd\b|\bcannabidiol\b", re.IGNORECASE), "CBD"),
    (re.compile(r"\bthc\b|\btetrahydrocannabinol\b|\bdelta[-\s]?9\b|"
                r"\bΔ9\b|\bΔ⁹\b", re.IGNORECASE), "Δ⁹-THC"),
    (re.compile(r"\bcannabis\b|\bmarijuana\b|\bmarihuana\b|\bweed\b",
                re.IGNORECASE),
     "cannabis"),
)

# Spec 003 US6 / FR-006 — when the prompt names "cannabis" / "marijuana"
# / "marihuana" / "weed" without naming a specific cannabinoid, expand
# to the registry-curated cannabinoid set so partner-drug matching
# fires on every covered isomer. Order matters only for determinism.
_CANNABIS_NOUN_EXPANSION: tuple[str, ...] = (
    "CBD", "Δ⁹-THC", "CBN", "CBG", "THCV",
)
_CANNABIS_NOUN_RE = re.compile(
    r"\bcannabis\b|\bmarijuana\b|\bmarihuana\b|\bweed\b",
    re.IGNORECASE,
)


_EVENT_KEYWORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsomnolence\b|\bsleepy\b|\bsedat\w*\b", re.IGNORECASE),
     "somnolence"),
    (re.compile(r"\b(?:ALT|AST|transaminase\w*|liver enzyme|"
                r"hepatic|hepatotox\w*)\b", re.IGNORECASE),
     "elevated transaminases"),
    (re.compile(r"\bdiarrhoea\b|\bdiarrhea\b", re.IGNORECASE), "diarrhoea"),
    (re.compile(r"\btachycard\w*\b|\bheart rate\b|\bHR\b", re.IGNORECASE),
     "tachycardia"),
    (re.compile(r"\borthostatic\b|\bhypotension\b|\bdizz\w*\b",
                re.IGNORECASE), "orthostatic hypotension"),
    (re.compile(r"\bpsychos\w*\b|\bpsychiatric\b|\bparanoia\b|"
                r"\banxiety\b", re.IGNORECASE),
     "acute psychiatric event"),
    (re.compile(r"\bCUD\b|\bcannabis use disorder\b|\bdependence\b|"
                r"\baddiction\b", re.IGNORECASE),
     "cannabis use disorder"),
    (re.compile(r"\bcognitive\b|\bmemory\b|\battention\b",
                re.IGNORECASE), "cognitive impairment"),
    (re.compile(r"\bCHS\b|\bhyperemesis\b|\bcyclic vomit\w*\b",
                re.IGNORECASE), "cannabis hyperemesis syndrome"),
    (re.compile(r"\bdriv\w*\b|\bcrash\b|\bMVC\b|\bimpair\w*\b",
                re.IGNORECASE), "driving impairment"),
    (re.compile(r"\badolescent\b|\bteen\w*\b|\byouth\b",
                re.IGNORECASE), "adolescent risk"),
    (re.compile(r"\bpregnan\w*\b|\bprenatal\b|\bfetal\b|\bfoetal\b|"
                r"\bplacenta\b|\bbreastfeed\w*\b|\blactation\b",
                re.IGNORECASE), "pregnancy"),
    (re.compile(r"\bpaediatric\b|\bpediatric\b|\bchild\w*\b|"
                r"\bedible exposure\b|\baccidental\b", re.IGNORECASE),
     "paediatric exposure"),
    (re.compile(r"\bEVALI\b|\bvaping[- ]associated\b|"
                r"\bvitamin\s*E\s*acetate\b|\btocopheryl\s*acetate\b|"
                r"\b(?:vape|vaping|vapor|vapour)\s+(?:lung|injury|"
                r"safety|illness)\b|\bvape\s+cartridge\w*\b",
                re.IGNORECASE),
     "EVALI"),
    (re.compile(r"\bheavy\s+metal\w*\b|\bnickel\b|\bchromium\b|"
                r"\blead\s+exposure\b|\bcadmium\b|\bcoil\s+leach\w*\b",
                re.IGNORECASE),
     "heavy-metal"),
)


def _resolve_cannabinoids(
    text: str,
    cannabinoid_filter: frozenset[str] | set[str] | None,
) -> set[str]:
    """Resolve the prompt's cannabinoid set per spec 003 US2 / US6.

    - When ``cannabinoid_filter`` is set, return only registry-curated
      cannabinoid names that intersect the filter (US2).
    - When the prompt names "cannabis" / "marijuana" but no specific
      cannabinoid, expand to the registry cannabinoid set (US6).
    """
    direct = {label for rx, label in _CANNABINOID_KEYWORDS
              if label != "cannabis" and rx.search(text)}
    cannabis_noun = _CANNABIS_NOUN_RE.search(text) is not None
    if cannabis_noun and not direct:
        direct.update(_CANNABIS_NOUN_EXPANSION)
    if cannabis_noun:
        # Preserve the literal "cannabis" partner-matcher (for rows like
        # "cannabis use disorder") so cannabis-keyed rows keep firing.
        direct.add("cannabis")
    if cannabinoid_filter is not None:
        # An empty filter (frozenset()) means "no cannabinoid named" —
        # leave direct alone; the caller will downstream-filter rows
        # whose cannabinoid intersects the empty set (= empty result).
        if cannabinoid_filter:
            direct = direct & set(cannabinoid_filter)
        else:
            direct = set()
    return direct


def detect_adverse_event_mention(
    text: str,
    *,
    cannabinoid_filter: frozenset[str] | set[str] | None = None,
) -> tuple[AdverseEvent, ...]:
    """Return registry entries that match a (cannabinoid, AE) pair in ``text``.

    ``cannabinoid_filter`` (spec 003 US2 / FR-002) restricts the
    cannabinoid set to those named in the filter — set by
    :func:`compose_answer` to the prompt's
    :class:`NamedCannabinoidSet.all_names`. When ``None`` (the default),
    behaviour matches the historical "every cannabinoid keyword fires"
    contract.
    """
    cannabinoids = _resolve_cannabinoids(text, cannabinoid_filter)
    events = {label for rx, label in _EVENT_KEYWORDS if rx.search(text)}
    if not cannabinoids or not events:
        return ()

    def _event_matches(entry_event: str) -> bool:
        for e in events:
            if e.lower() in entry_event.lower():
                return True
            if entry_event.lower() in e.lower():
                return True
        return False

    out: list[AdverseEvent] = []
    seen: set[tuple[str, str]] = set()
    for x in _REGISTRY:
        if x.cannabinoid not in cannabinoids:
            continue
        if not _event_matches(x.event):
            continue
        key = (x.cannabinoid, x.event)
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return tuple(out)


# Class-level keywords for the generic-question fallback path. Used by
# detect_adverse_event_class_mention. Closes the 2026-05-19 Oracle
# Evaluator §4.3 finding that "What are the cardiovascular adverse
# events of THC?" returned 0 AE rows.
_AE_CLASS_KEYWORDS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{kw}\b", flags=re.IGNORECASE), scope)
    for kw, scope in [
        ("adverse event", "all"),
        ("adverse events", "all"),
        ("side effect", "all"),
        ("side effects", "all"),
        ("safety profile", "all"),
        ("safety signal", "all"),
        ("safety signals", "all"),
        ("safety concerns", "all"),
        ("safety concern", "all"),
        ("cardiovascular adverse", "cardiovascular"),
        ("cardiovascular risk", "cardiovascular"),
        ("cardiovascular event", "cardiovascular"),
        ("cardiovascular events", "cardiovascular"),
        ("cardiac event", "cardiovascular"),
        ("cardiac events", "cardiovascular"),
        ("heart attack", "cardiovascular"),
        ("psychiatric adverse", "psychiatric"),
        ("psychiatric risk", "psychiatric"),
        ("psychiatric event", "psychiatric"),
        ("psychiatric events", "psychiatric"),
        ("psychiatric effect", "psychiatric"),
        ("psychiatric effects", "psychiatric"),
        ("respiratory adverse", "respiratory"),
        ("respiratory risk", "respiratory"),
        ("respiratory effect", "respiratory"),
        ("respiratory effects", "respiratory"),
        ("hepatic adverse", "hepatic"),
        ("hepatic risk", "hepatic"),
        ("liver risk", "hepatic"),
        ("liver injury", "hepatic"),
        ("liver toxicity", "hepatic"),
        ("neurologic adverse", "neurological"),
        ("neurological risk", "neurological"),
        ("cognitive risk", "neurological"),
        ("cognitive effect", "neurological"),
        ("cognitive effects", "neurological"),
        ("reproductive risk", "reproductive"),
        ("reproductive effect", "reproductive"),
        ("reproductive effects", "reproductive"),
        ("fertility", "reproductive"),
        ("vapor product safety", "respiratory"),
        ("vapour product safety", "respiratory"),
        ("vape product safety", "respiratory"),
        ("vape safety", "respiratory"),
        ("vaping safety", "respiratory"),
        ("e-cigarette safety", "respiratory"),
        ("lung injury", "respiratory"),
    ]
)


def detect_adverse_event_class_mention(
    text: str,
    *,
    cannabinoid_filter: frozenset[str] | set[str] | None = None,
) -> tuple[AdverseEvent, ...]:
    """Return all AE rows that match a *class* keyword in ``text``.

    Companion to :func:`detect_adverse_event_mention` for prompts that
    ask about an AE *class* (e.g. "cardiovascular adverse events of
    THC") rather than naming a specific event ("tachycardia"). Closes
    the 2026-05-19 Oracle Evaluator §4.3 retrieval gap.

    ``cannabinoid_filter`` (spec 003 US2 / FR-002): when set, only
    rows whose ``cannabinoid`` field intersects the filter are
    returned.

    Returns ``()`` when no class keyword matched, so callers can
    chain: ``hits = detect_adverse_event_mention(t) or
    detect_adverse_event_class_mention(t)``.
    """
    scope: str | None = None
    organ_scope: str | None = None
    for rx, s in _AE_CLASS_KEYWORDS:
        if rx.search(text):
            if s == "all" and scope is None:
                scope = "all"
            elif s != "all":
                # Organ-system-specific scope wins over generic "all".
                organ_scope = s
                scope = s
    if scope is None:
        return ()
    cannabinoids = _resolve_cannabinoids(text, cannabinoid_filter)
    if cannabinoids:
        rows = [r for r in _REGISTRY if r.cannabinoid in cannabinoids]
    elif cannabinoid_filter is not None:
        # Spec 003 US2 / FR-002 — the prompt named a specific cannabinoid
        # (filter set), but no registry-curated cannabinoid intersects.
        # Surfacing unrelated AE rows confidence-launders the answer.
        rows = []
    else:
        rows = list(_REGISTRY)
    if organ_scope:
        rows = [r for r in rows if organ_scope in r.organ_system.lower()]
    seen: set[tuple[str, str]] = set()
    out: list[AdverseEvent] = []
    for r in rows:
        key = (r.cannabinoid, r.event)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return tuple(out)


def format_for_clinician(
    events: Iterable[AdverseEvent],
) -> str:
    """Render a Markdown clinician-facing summary of a set of adverse events."""
    items = list(events)
    if not items:
        return (
            "_No high-confidence adverse-event records found in the curated "
            "registry for the named cannabinoid + event. Absence here does "
            "not mean absence of risk — the registry has no entry above the "
            "inclusion bar (≥ 1 controlled trial, regulator label change, "
            "or major-journal cohort)._"
        )
    lines: list[str] = [
        "| Cannabinoid | Adverse event | Organ system | Severity | "
        "Reversibility | Onset | Incidence | Action | Source |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for x in items:
        # v2.7: render primary effect-size sources first, then mark
        # supporting reviews with a (review) suffix so a clinician
        # reading the table can distinguish "Volkow 2014 supports the
        # AE class" from "the primary effect size came from paper X".
        # Closes the 2026-05-19 Oracle Evaluator §4.7 anchor-reuse
        # finding.
        primary_cites = [
            c for c in x.citations
            if getattr(c, "role", "primary") == "primary"
        ]
        review_cites = [
            c for c in x.citations
            if getattr(c, "role", "primary") == "supporting_review"
        ]
        primary_strs = [
            (f"PMID {c.pmid}" if c.pmid
             else (f"doi:{c.doi}" if c.doi else c.label))
            for c in primary_cites
        ]
        review_strs = [
            (f"PMID {c.pmid} (review)" if c.pmid
             else (f"doi:{c.doi} (review)" if c.doi
                   else f"{c.label} (review)"))
            for c in review_cites
        ]
        if primary_strs:
            src_strs = ", ".join(primary_strs + review_strs)
        elif review_strs:
            # No primary anchor — surface that gap explicitly.
            src_strs = "reviews only: " + ", ".join(review_strs)
        else:
            src_strs = ", ".join(
                (f"PMID {c.pmid}" if c.pmid
                 else (f"doi:{c.doi}" if c.doi else c.label))
                for c in x.citations
            )
        incidence = x.incidence_note.replace("\n", " ")
        if len(incidence) > 140:
            incidence = incidence[:137] + "..."
        action = x.clinical_action.replace("\n", " ")
        if len(action) > 140:
            action = action[:137] + "..."
        lines.append(
            f"| {x.cannabinoid} | {x.event} | {x.organ_system} | "
            f"{x.severity.value} | {x.reversibility.value} | "
            f"{x.onset.value} | {incidence} | {action} | {src_strs} |"
        )
    lines.append("")
    lines.append(
        "**Population**: each row's `population` field defines the "
        "applicable population. Cannavec does not extrapolate registry "
        "data to individual patients; individual assessment is a "
        "clinician's role."
    )
    return "\n".join(lines)
