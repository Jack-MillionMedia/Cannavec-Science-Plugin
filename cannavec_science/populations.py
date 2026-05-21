"""Trial-supported population reference.

Curated, citation-anchored summary of the populations Cannavec is
willing to talk about at a clinical-magnitude level. Each entry
defines:

- the *named population* (e.g. paediatric Dravet, adult MS spasticity)
- the *indication* the population was studied for
- the *cannabinoid intervention* (compound + route + trial-supported
  dose range)
- the *evidence-anchor citation* (the pivotal trial or SR)
- the *highest evidence grade* Cannavec is willing to anchor
- the *required cautions* the safety layer should always attach

The primitive exists so audience surfaces (clinician, researcher,
patient) compose from a shared population schema rather than each
re-inventing the trial-supported framing. Individual prescribing
remains a clinician's call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, TYPE_CHECKING

from cannavec_science.evidence import EvidenceLevel

if TYPE_CHECKING:
    from cannavec_science.evidence import Claim, SourceTier


@dataclass(frozen=True)
class PopulationCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None
    # v2.7 quantitative anchor fields (P1.8). When populated, the
    # regimen template renders a "Quantitative effect" sub-block under
    # the population summary so a clinician reads the actual number,
    # not a generic "trial-supported evidence" line. Optional —
    # legacy citations without these fields render as before.
    n: int | None = None
    primary_outcome: str | None = None
    effect_size: str | None = None
    confidence_interval: str | None = None
    nnt: str | None = None
    comparator: str | None = None
    funding: str | None = None
    role: str = "primary"  # primary | systematic_review | replication | null_trial | regulator_approval


@dataclass(frozen=True)
class TrialSupportedPopulation:
    """A population for which a cannabinoid intervention has trial evidence."""

    label: str                          # e.g. "paediatric Dravet syndrome"
    indication: str                     # e.g. "convulsive seizures"
    cannabinoid: str                    # e.g. "cannabidiol (CBD)"
    route: str                          # e.g. "oral"
    dose_range_population: str          # trial-supported population range
    highest_grade_anchor: EvidenceLevel
    required_cautions: tuple[str, ...]
    age_band: str                       # e.g. "≥ 2 years", "adults", "any"
    geographies_approved: tuple[str, ...]  # regulator approvals
    citations: tuple[PopulationCitation, ...]
    notes: str = ""
    # v2.7: negative-evidence balancing (P2.14). When a non-trivial
    # null or negative trial exists for this population, list it here.
    # The regimen template surfaces null_trials under a distinct
    # heading so the user sees the evidence on both sides rather than
    # only the positive anchor.
    null_trials: tuple[PopulationCitation, ...] = ()

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "indication": self.indication,
            "cannabinoid": self.cannabinoid,
            "route": self.route,
            "dose_range_population": self.dose_range_population,
            "highest_grade_anchor": self.highest_grade_anchor.value,
            "age_band": self.age_band,
            "geographies_approved": list(self.geographies_approved),
            "required_cautions": list(self.required_cautions),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi,
                 "url": c.url, "year": c.year}
                for c in self.citations
            ],
            "notes": self.notes,
        }

    def to_claim(self, *, source_tier: "SourceTier | None" = None) -> "Claim":
        """Render this population row as a typed :class:`Claim`.

        Unlike the other registries, populations carry the curator's
        GRADE assessment in :attr:`highest_grade_anchor`. The default
        source tier maps that anchor:

        - ``Level A`` → :class:`SourceTier.SR_FLAGSHIP`
          (Cochrane / NEJM-tier pivotal trial — grades to A)
        - ``Level B`` → :class:`SourceTier.JOURNAL_RCT` with
          ``pre_registered=True``, ``adequately_powered=True``
          (grades to B)
        - ``Level C`` → :class:`SourceTier.SINGLE_ARM_OR_MECH`
          (grades to C)
        - ``Level D / E`` → :class:`SourceTier.PREPRINT_OR_SMALL`
          (grades to D)

        Wording is grade-aware:

        - Level A claims use "is established adjunctive therapy for…"
        - Level B claims use "is likely effective for…"
        - Level C claims use "may help…"
        - Lower grades use "preliminary evidence supports…"
        """
        from cannavec_science.evidence import (
            Claim,
            ClaimType,
            Source,
            SourceTier as _SourceTier,
            required_disclosures,
        )

        # Tier defaults from the curator-assessed anchor grade.
        default_tier_map = {
            EvidenceLevel.A: _SourceTier.SR_FLAGSHIP,
            EvidenceLevel.B: _SourceTier.JOURNAL_RCT,
            EvidenceLevel.C: _SourceTier.SINGLE_ARM_OR_MECH,
            EvidenceLevel.D: _SourceTier.PREPRINT_OR_SMALL,
            EvidenceLevel.E: _SourceTier.PREPRINT_OR_SMALL,
            EvidenceLevel.UNSUPPORTED: _SourceTier.PREPRINT_OR_SMALL,
        }
        tier = source_tier or default_tier_map[self.highest_grade_anchor]

        # Set ``pre_registered`` + ``adequately_powered`` for sources
        # whose curator-anchored grade reflects a pre-registered trial:
        #
        # - Level A + SR_FLAGSHIP (Cochrane / NEJM / Lancet / JAMA) —
        #   pre-reg + powered are characteristic; setting them lets the
        #   ``single_primary_study`` cap drop one level to B (not C).
        # - Level B + JOURNAL_RCT — Source grades to B (not C) when
        #   pre-reg + powered are set; ``single_primary_study`` cap then
        #   reaches C.
        #
        # Single-citation rows still typically grade one level below
        # the curator anchor because of the deterministic
        # single-primary-study rule; that's the honest output for
        # what's independently supportable from the cited rows alone.
        pre_reg = (
            (self.highest_grade_anchor == EvidenceLevel.B
             and tier == _SourceTier.JOURNAL_RCT)
            or (self.highest_grade_anchor == EvidenceLevel.A
                and tier == _SourceTier.SR_FLAGSHIP)
        )
        powered = pre_reg

        sources = tuple(
            Source(
                title=c.label,
                tier=tier,
                pmid=c.pmid,
                doi=c.doi,
                url=c.url,
                year=c.year,
                pre_registered=pre_reg,
                adequately_powered=powered,
            )
            for c in self.citations
            if (c.pmid or c.doi or c.url)
        )

        # Wording is intentionally neutral so the Claim text passes the
        # wording-vs-grade check at every deterministic grade. The
        # curator's anchor grade is reported as a structured field for
        # downstream consumers; the *deterministic* Claim grade
        # (computed from Source tier + count) governs strict-wording
        # enforcement. Single-source population rows typically grade
        # one level below the curator anchor because of the
        # ``single_primary_study`` cap in
        # :func:`cannavec.evidence.apply_grade_modifiers` — this is the
        # honest output for what we can independently support from the
        # cited rows.
        # Claim prose contains NO grade string. The typed Claim.grade
        # field (computed by best_supportable_grade) is the single
        # source of truth for the grade Cannavec can independently
        # defend from the cited evidence. Embedding "Level A" or
        # "Curator-anchored at Level A" in the prose creates a
        # wording-vs-grade conflict when the deterministic grade
        # demotes (e.g., single-primary-study cap on Dravet drops
        # the curator's Level A anchor to Level B). Closes the
        # 2026-05-19 Oracle Evaluator §4.5 / §3.9 finding.
        text = (
            f"{self.cannabinoid} ({self.route}, "
            f"dose range {self.dose_range_population}) "
            f"has trial-supported evidence for {self.indication} "
            f"in {self.label} ({self.age_band}). "
            f"Approved geographies: "
            f"{', '.join(self.geographies_approved) or 'none stated'}."
        )

        disclosures = required_disclosures(ClaimType.CLINICAL_EFFICACY)

        return Claim(
            text=text,
            claim_type=ClaimType.CLINICAL_EFFICACY,
            sources=sources,
            disclosures_present=disclosures,
            population=self.label,
            route=self.route,
            dose_range=self.dose_range_population,
        )

    def supportable_claim_grade(self) -> EvidenceLevel:
        """The deterministic grade Cannavec can independently support.

        Returns the result of :meth:`Claim.best_supportable_grade` for
        the Claim this row produces. This is the grade Cannavec
        defends from the cited rows alone; it may differ from
        :attr:`highest_grade_anchor` (the curator's assessment) when
        the ``single_primary_study`` cap decays the grade by one level.

        Used by the renderer to detect grade decay and emit a one-line
        rationale (specs/001-cannabis-insight-engine US7,
        constitution principle VI).
        """
        return self.to_claim().best_supportable_grade()


def build_claim(
    population: "TrialSupportedPopulation",
    *,
    source_tier: "SourceTier | None" = None,
) -> "Claim":
    """Module-level helper mirroring :meth:`TrialSupportedPopulation.to_claim`."""
    return population.to_claim(source_tier=source_tier)


_REGISTRY: tuple[TrialSupportedPopulation, ...] = (
    TrialSupportedPopulation(
        label="paediatric Dravet syndrome",
        indication="convulsive seizures (adjunctive therapy)",
        cannabinoid="cannabidiol (CBD; Epidiolex)",
        route="oral",
        dose_range_population="10-20 mg/kg/day in two divided doses",
        highest_grade_anchor=EvidenceLevel.A,
        age_band="≥ 2 years",
        geographies_approved=("US (FDA)", "EU (EMA)", "UK (MHRA)"),
        required_cautions=(
            "LFT monitoring on initiation and dose increases",
            "Clobazam interaction common — N-desmethylclobazam AUC rises ~3x",
            "Reduce clobazam dose proactively if somnolence emerges",
        ),
        citations=(
            PopulationCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                doi="10.1056/NEJMoa1611618",
                year=2017,
                role="primary",
                n=120,
                primary_outcome=(
                    "monthly convulsive seizure frequency over 14-week "
                    "treatment period"
                ),
                effect_size=(
                    "median seizure reduction 38.9% on CBD vs 13.3% on "
                    "placebo"
                ),
                confidence_interval=(
                    "adjusted median difference −22.8% "
                    "(95% CI −41.1 to −5.4, p=0.01)"
                ),
                nnt=(
                    "NNT ~7 for ≥50% reduction in convulsive seizure "
                    "frequency"
                ),
                comparator="placebo",
                funding="GW Pharmaceuticals (industry-funded; pre-registered)",
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="paediatric Lennox-Gastaut syndrome",
        indication="drop seizures (adjunctive therapy)",
        cannabinoid="cannabidiol (CBD; Epidiolex)",
        route="oral",
        dose_range_population="10-20 mg/kg/day in two divided doses",
        highest_grade_anchor=EvidenceLevel.A,
        age_band="≥ 2 years",
        geographies_approved=("US (FDA)", "EU (EMA)", "UK (MHRA)"),
        required_cautions=(
            "LFT monitoring on initiation and dose increases",
            "AED interaction surveillance — clobazam, valproate especially",
        ),
        citations=(
            PopulationCitation(
                label="Devinsky 2018 — CBD in Lennox-Gastaut syndrome (NEJM)",
                pmid="29768152",
                year=2018,
                role="primary",
                n=171,
                primary_outcome=(
                    "monthly drop-seizure frequency over 14-week "
                    "treatment period"
                ),
                effect_size=(
                    "drop-seizure reduction 41.9% on CBD 20 mg/kg/day "
                    "vs 17.2% on placebo"
                ),
                confidence_interval=(
                    "estimated median difference −21.6% "
                    "(95% CI −34.8 to −6.7, p=0.005)"
                ),
                comparator="placebo",
                funding="GW Pharmaceuticals (industry-funded; pre-registered)",
            ),
            PopulationCitation(
                label="Gaston 2017 — CBD AE patterns in epilepsy trials",
                pmid="28815401",
                year=2017,
                role="primary",
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="adult MS spasticity",
        indication="moderate-to-severe spasticity unresponsive to first-line therapy",
        cannabinoid="nabiximols (Δ⁹-THC + CBD, Sativex / Mevatyl)",
        route="oromucosal spray",
        dose_range_population="1-12 sprays/day (each spray = 2.7 mg THC + 2.5 mg CBD)",
        highest_grade_anchor=EvidenceLevel.B,
        age_band="adults",
        geographies_approved=("UK (MHRA)", "EU (multiple)", "Canada", "Israel"),
        required_cautions=(
            "Driving impairment for hours after dosing",
            "Titrate slowly to limit dizziness and oral mucosa irritation",
            "Caution in personal / family history of psychotic disorder",
        ),
        citations=(
            PopulationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="adult chronic neuropathic pain",
        indication="treatment-refractory chronic neuropathic pain (adjunctive)",
        cannabinoid="various (THC-predominant, CBD-predominant, balanced; nabiximols)",
        route="inhaled or oromucosal or oral",
        dose_range_population=(
            "small-to-moderate effects in pooled Cochrane / SR data; "
            "trial-supported ranges differ by product (e.g. inhaled "
            "10-25% Δ⁹-THC flower, nabiximols 1-12 sprays/day, oral "
            "2.5-20 mg Δ⁹-THC + 5-40 mg CBD)"
        ),
        highest_grade_anchor=EvidenceLevel.B,
        age_band="adults",
        geographies_approved=(
            "UK (CBPM unlicensed special)", "Germany (BfArM)",
            "Israel", "Canada", "Australia (TGA)",
        ),
        required_cautions=(
            "Modest effect sizes; honest synthesis includes null trials",
            "Caution with concurrent opioids — additive sedation",
            "Driving impairment counselling required",
        ),
        citations=(
            PopulationCitation(
                label="Mücke 2018 — Cannabis-based medicines for chronic neuropathic pain (Cochrane SR)",
                pmid="29513392",
                doi="10.1002/14651858.CD012182.pub2",
                year=2018,
                role="systematic_review",
            ),
            PopulationCitation(
                label="Stockings 2018 — Cannabis and cannabinoids for chronic non-cancer pain SR/MA (Pain)",
                pmid="29796855",
                year=2018,
                role="systematic_review",
            ),
            PopulationCitation(
                label="Whiting 2015 — Cannabinoids for medical use SR/MA (JAMA)",
                pmid="26408728",
                year=2015,
                role="systematic_review",
            ),
            PopulationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
                role="primary",
            ),
        ),
        null_trials=(
            PopulationCitation(
                label=(
                    "Mücke 2018 — Cochrane null/inconclusive finding: "
                    "modest reduction in pain scores with high NNT (≈20 "
                    "for 30% pain reduction); evidence quality low to "
                    "moderate; substantial heterogeneity across "
                    "individual trials"
                ),
                pmid="29513392",
                year=2018,
                role="null_trial",
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="adult chemotherapy-induced nausea and vomiting (CINV)",
        indication="CINV not adequately controlled by first-line antiemetics",
        cannabinoid="nabilone, dronabinol",
        route="oral",
        dose_range_population=(
            "nabilone 1-2 mg PO twice daily; dronabinol 2.5-10 mg PO "
            "before and after chemotherapy"
        ),
        highest_grade_anchor=EvidenceLevel.B,
        age_band="adults",
        geographies_approved=("US (FDA)", "Canada (Health Canada)", "UK"),
        required_cautions=(
            "Not a first-line antiemetic when 5-HT3 antagonists are available",
            "Sedation and orthostatic effects common — especially in older adults",
            "Caution in unstable cardiovascular disease",
        ),
        citations=(
            PopulationCitation(
                label="Whiting 2015 — Cannabinoids for medical use SR/MA (JAMA)",
                pmid="26408728",
                year=2015,
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="adult HIV / cancer cachexia and appetite stimulation",
        indication="weight loss / appetite stimulation in HIV-AIDS and cancer cachexia",
        cannabinoid="dronabinol",
        route="oral",
        dose_range_population="2.5-10 mg PO twice daily",
        highest_grade_anchor=EvidenceLevel.B,
        age_band="adults",
        geographies_approved=("US (FDA)",),
        required_cautions=(
            "Modest evidence; not first-line in modern combination ART era",
            "Sedation and orthostatic hypotension limit dose escalation",
        ),
        citations=(
            PopulationCitation(
                label="Whiting 2015 — Cannabinoids for medical use SR/MA (JAMA)",
                pmid="26408728",
                year=2015,
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="paediatric tuberous sclerosis complex (TSC)",
        indication="seizures associated with TSC (adjunctive therapy)",
        cannabinoid="cannabidiol (CBD; Epidiolex)",
        route="oral",
        dose_range_population="25 mg/kg/day in two divided doses",
        highest_grade_anchor=EvidenceLevel.A,
        age_band="≥ 1 year",
        geographies_approved=("US (FDA)", "EU (EMA)", "UK (MHRA)"),
        required_cautions=(
            "Same hepatic and interaction monitoring as Dravet / LGS",
        ),
        citations=(
            PopulationCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM, pivotal trial framework)",
                pmid="28538134",
                year=2017,
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="adolescents (caution population, not trial-indicated)",
        indication=(
            "CAUTION population — cannabis is not first-line for any "
            "adolescent indication outside narrow paediatric epilepsy "
            "protocols"
        ),
        cannabinoid="Δ⁹-THC and high-THC cannabis (CAUTION)",
        route="any",
        dose_range_population="not applicable — population is caution-only",
        highest_grade_anchor=EvidenceLevel.B,
        age_band="< 18 years",
        geographies_approved=("no recreational pathway in any major jurisdiction",),
        required_cautions=(
            "Adolescent-onset heavy cannabis use is associated with "
            "elevated risk of psychotic disorder, persistent cognitive "
            "deficits, and CUD; absolute magnitude debated, direction "
            "of association consistent",
            "Counsel against initiation; delay as long as feasible",
            "Screen for early symptoms of psychotic disorder in those "
            "with family history",
        ),
        citations=(
            PopulationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="pregnant or lactating women (avoidance population)",
        indication=(
            "AVOIDANCE population — cannabinoids cross the placenta and "
            "are excreted in breast milk"
        ),
        cannabinoid="any cannabinoid",
        route="any",
        dose_range_population="not applicable — population is avoidance",
        highest_grade_anchor=EvidenceLevel.B,
        age_band="any",
        geographies_approved=("none for this indication",),
        required_cautions=(
            "ACOG / RCOG / SOGC default position is avoidance during "
            "pregnancy and lactation",
            "Observational evidence of modestly lower birth weight and "
            "small effects on offspring cognition; magnitude confounded",
            "No trial-supported safe dose exists for this population",
        ),
        citations=(
            PopulationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    TrialSupportedPopulation(
        label="elderly (≥ 65) and frail older adults",
        indication="various — special-attention population for adverse effects",
        cannabinoid="any cannabinoid (CAUTION population)",
        route="any (oral preferred to inhaled)",
        dose_range_population=(
            "start at lowest trial-supported dose; titrate slowly; "
            "older adults are more sensitive to orthostatic, cognitive, "
            "and sedative effects"
        ),
        highest_grade_anchor=EvidenceLevel.C,
        age_band="≥ 65 years",
        geographies_approved=("no age-specific approval; same as adult labels",),
        required_cautions=(
            "Increased orthostatic-hypotension and fall risk",
            "Increased cognitive-impairment risk on baseline cognitive "
            "decline",
            "Polypharmacy raises interaction surface — check CYP and "
            "PD overlap with chronic medications",
            "Tachycardia in unstable cardiovascular disease",
        ),
        citations=(
            PopulationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
)


def all_populations() -> tuple[TrialSupportedPopulation, ...]:
    """Return the full curated registry (read-only)."""
    return _REGISTRY


def find_populations(
    *,
    label_substring: str | None = None,
    indication_substring: str | None = None,
    cannabinoid_substring: str | None = None,
    min_grade: EvidenceLevel | None = None,
) -> tuple[TrialSupportedPopulation, ...]:
    """Search the registry. Matchers are case-insensitive substring.

    The ``cannabinoid_substring`` filter is normalised so that
    ``Δ9-THC``, ``Δ⁹-THC``, and ``delta-9-THC`` all match the
    registry's canonical ``Δ⁹-THC`` form.
    """
    from cannavec_science._normalize import normalized_contains

    def matches(s: str, q: str | None) -> bool:
        return q is None or q.lower() in s.lower()

    out: list[TrialSupportedPopulation] = []
    for x in _REGISTRY:
        if not matches(x.label, label_substring):
            continue
        if not matches(x.indication, indication_substring):
            continue
        if not normalized_contains(x.cannabinoid, cannabinoid_substring):
            continue
        if min_grade is not None and x.highest_grade_anchor.rank < min_grade.rank:
            continue
        out.append(x)
    return tuple(out)


_POPULATION_KEYWORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bDravet\b", re.IGNORECASE), "paediatric Dravet syndrome"),
    (re.compile(r"\bLennox.?Gastaut\b|\bLGS\b", re.IGNORECASE),
     "paediatric Lennox-Gastaut syndrome"),
    (re.compile(r"\b(?:MS|multiple sclerosis)\b.{0,40}\bspasticity\b|"
                r"\bspasticity\b.{0,40}\b(?:MS|multiple sclerosis)\b",
                re.IGNORECASE), "adult MS spasticity"),
    (re.compile(r"\bneuropathic pain\b|\bchronic neuropathic\b",
                re.IGNORECASE), "adult chronic neuropathic pain"),
    (re.compile(r"\bCINV\b|\bchemo.?induced nausea\b",
                re.IGNORECASE),
     "adult chemotherapy-induced nausea and vomiting (CINV)"),
    (re.compile(r"\bcachexia\b|\bappetite\b.{0,40}\b(?:HIV|AIDS|cancer)\b",
                re.IGNORECASE),
     "adult HIV / cancer cachexia and appetite stimulation"),
    (re.compile(r"\btuberous sclerosis\b|\bTSC\b", re.IGNORECASE),
     "paediatric tuberous sclerosis complex (TSC)"),
    (re.compile(r"\badolescent\w*\b|\bteen\w*\b|\byouth\b",
                re.IGNORECASE),
     "adolescents (caution population, not trial-indicated)"),
    (re.compile(r"\bpregnan\w*\b|\blactation\b|\bbreastfeed\w*\b",
                re.IGNORECASE),
     "pregnant or lactating women (avoidance population)"),
    (re.compile(r"\belderly\b|\bgeriatric\b|\bolder adult\b|"
                r"\bover 65\b|\bover 70\b", re.IGNORECASE),
     "elderly (≥ 65) and frail older adults"),
)


# Indication-keyword fallback. Maps the common indication words a
# clinician uses ("seizures", "epilepsy", "spasticity", "chemo nausea",
# …) to the registered population labels whose indication intersects
# that word. Closes the Oracle Auditor §T12 finding that
# "What does CBD do for seizures?" returned 0 rows even though
# Dravet / LGS / TSC are registered Level-A populations.
_INDICATION_KEYWORD_TO_LABELS: tuple[
    tuple[re.Pattern[str], tuple[str, ...]], ...
] = (
    (re.compile(r"\bseizur\w*\b|\bepilep\w*\b", re.IGNORECASE),
     ("paediatric Dravet syndrome",
      "paediatric Lennox-Gastaut syndrome",
      "paediatric tuberous sclerosis complex (TSC)")),
    (re.compile(r"\bspasticit\w*\b", re.IGNORECASE),
     ("adult MS spasticity",)),
    (re.compile(r"\bchronic pain\b|\bneuropath\w*\b", re.IGNORECASE),
     ("adult chronic neuropathic pain",)),
    (re.compile(r"\bnause\w*\b|\bvomit\w*\b", re.IGNORECASE),
     ("adult chemotherapy-induced nausea and vomiting (CINV)",)),
    (re.compile(r"\bappetit\w*\b|\bcachexi\w*\b|\bwasting\b",
                re.IGNORECASE),
     ("adult HIV / cancer cachexia and appetite stimulation",)),
    # Brand-name detection (cannabis-insight-engine spec 001 US4).
    # Brand → population mapping enables comparative composition:
    # "Compare Sativex and Epidiolex" now lights up both rows.
    (re.compile(r"\b(?:sativex|nabiximols|mevatyl)\b", re.IGNORECASE),
     ("adult MS spasticity",
      "adult chronic neuropathic pain")),
    (re.compile(r"\bepidiolex\b", re.IGNORECASE),
     ("paediatric Dravet syndrome",
      "paediatric Lennox-Gastaut syndrome",
      "paediatric tuberous sclerosis complex (TSC)")),
    (re.compile(r"\bnabilone\b", re.IGNORECASE),
     ("adult chemotherapy-induced nausea and vomiting (CINV)",)),
    (re.compile(r"\bdronabinol\b|\bmarinol\b", re.IGNORECASE),
     ("adult chemotherapy-induced nausea and vomiting (CINV)",
      "adult HIV / cancer cachexia and appetite stimulation")),
)


_POPULATION_CANNABINOID_MAP: dict[str, tuple[str, ...]] = {
    "CBD": ("cbd", "cannabidiol", "nabiximols"),
    "Δ⁹-THC": ("thc", "tetrahydrocannabinol", "nabiximols",
               "nabilone", "dronabinol"),
}


def detect_population_mention(
    text: str,
    *,
    cannabinoid_filter: frozenset[str] | set[str] | None = None,
) -> tuple[TrialSupportedPopulation, ...]:
    """Return registry entries whose label matches a population cue.

    Spec 003 US2 / FR-002: ``cannabinoid_filter`` restricts to rows
    whose ``cannabinoid`` field intersects the filter's mapped name set.
    """
    labels = {label for rx, label in _POPULATION_KEYWORDS if rx.search(text)}
    for rx, fallback_labels in _INDICATION_KEYWORD_TO_LABELS:
        if rx.search(text):
            labels.update(fallback_labels)
    if not labels:
        return ()
    out: list[TrialSupportedPopulation] = []
    seen: set[str] = set()
    for x in _REGISTRY:
        if x.label not in labels or x.label in seen:
            continue
        if cannabinoid_filter is not None:
            if not cannabinoid_filter:
                continue
            allowed = set()
            for cn in cannabinoid_filter:
                allowed.update(_POPULATION_CANNABINOID_MAP.get(cn, ()))
            if not allowed:
                continue
            if not any(a in x.cannabinoid.lower() for a in allowed):
                continue
        out.append(x)
        seen.add(x.label)
    return tuple(out)


# Class-level keywords for the generic-question fallback path. Closes
# the 2026-05-19 Oracle Evaluator §4.3 finding that "What are the
# trial-supported indications for cannabinoids?" returned 0 rows.
_INDICATION_CLASS_KEYWORDS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{kw}\b", flags=re.IGNORECASE)
    for kw in [
        r"indication\w*",
        r"approved use\w*",
        r"approved indication\w*",
        r"trial[- ]supported",
        r"what is the evidence",
        r"clinical evidence",
        r"clinical trial\w*",
        r"clinical use\w*",
        r"clinically validated",
        r"fda[- ]approved",
        r"regulator[- ]approved",
    ]
)


def detect_population_class_mention(
    text: str,
    *,
    cannabinoid_filter: frozenset[str] | set[str] | None = None,
) -> tuple[TrialSupportedPopulation, ...]:
    """Return all trial-supported populations matching a class keyword.

    Spec 003 US2 / FR-002: ``cannabinoid_filter`` (when passed by
    :func:`compose_answer`) restricts to rows whose ``cannabinoid``
    field intersects the filter via :data:`_POPULATION_CANNABINOID_MAP`.

    When called without ``cannabinoid_filter`` (legacy callers), the
    prompt itself is scanned for cannabinoid cues — preserving the
    pre-v0.3 contract for direct callers.
    """
    matched = False
    for rx in _INDICATION_CLASS_KEYWORDS:
        if rx.search(text):
            matched = True
            break
    if not matched:
        return ()

    allowed: set[str] = set()
    if cannabinoid_filter is not None:
        if not cannabinoid_filter:
            return ()
        for cn in cannabinoid_filter:
            allowed.update(_POPULATION_CANNABINOID_MAP.get(cn, ()))
        if not allowed:
            return ()
    else:
        # Legacy single-token prompt scan.
        text_lower = text.lower()
        for cn in ("cannabidiol", "cbd"):
            if re.search(rf"\b{cn}\b", text_lower):
                allowed.add("cbd")
                break
        if not allowed:
            for cn in ("tetrahydrocannabinol", "thc", "delta-9", "delta 9"):
                if re.search(rf"\b{re.escape(cn)}\b", text_lower):
                    allowed.add("thc")
                    break
        if not allowed:
            for cn in ("nabiximols", "sativex"):
                if re.search(rf"\b{cn}\b", text_lower):
                    allowed.add("nabiximols")
                    break

    rows = list(_REGISTRY)
    if allowed:
        rows = [r for r in rows
                if any(a in r.cannabinoid.lower() for a in allowed)]
    seen: set[str] = set()
    out: list[TrialSupportedPopulation] = []
    for r in rows:
        if r.label in seen:
            continue
        seen.add(r.label)
        out.append(r)
    return tuple(out)


def format_for_clinician(
    populations: Iterable[TrialSupportedPopulation],
) -> str:
    """Render a Markdown clinician-facing summary of population entries."""
    items = list(populations)
    if not items:
        return (
            "_No trial-supported population entries matched. Cannavec only "
            "anchors clinical-magnitude population statements when a "
            "pivotal trial or major SR exists for the cannabinoid + "
            "indication + population triple._"
        )
    out: list[str] = []
    for x in items:
        out.append(f"### {x.label}")
        out.append("")
        out.append(f"- **Indication:** {x.indication}")
        out.append(f"- **Cannabinoid:** {x.cannabinoid}")
        out.append(f"- **Route:** {x.route}")
        out.append(
            f"- **Trial-supported dose range (population, not personal):** "
            f"{x.dose_range_population}"
        )
        out.append(
            f"- **Highest evidence grade anchor:** "
            f"{x.highest_grade_anchor.value}"
        )

        # Grade-decay rationale (cannabis-insight-engine spec 001 US7;
        # constitution principle VI). When the deterministic claim
        # grade is lower than the curator's anchor — typically because
        # the single-primary-study cap demoted Level A → Level B —
        # surface the cap rule explicitly so the reader does not see
        # two grades with no explanation.
        supportable = x.supportable_claim_grade()
        if supportable.rank < x.highest_grade_anchor.rank:
            out.append(
                f"- **Claim-supported grade:** {supportable.value} "
                f"— curator-anchored at Level "
                f"{x.highest_grade_anchor.value.split()[-1]}; capped at "
                f"Level {supportable.value.split()[-1]} by the "
                f"single-primary-study rule (only one independent "
                f"primary citation backs this row)."
            )

        out.append(f"- **Age band:** {x.age_band}")
        out.append(
            f"- **Approved geographies:** "
            f"{', '.join(x.geographies_approved)}"
        )
        if x.required_cautions:
            out.append("- **Required cautions:**")
            for c in x.required_cautions:
                out.append(f"  - {c}")
        if x.citations:
            cites = ", ".join(
                f"PMID {c.pmid}" if c.pmid
                else (f"doi:{c.doi}" if c.doi else c.label)
                for c in x.citations
            )
            out.append(f"- **Citations:** {cites}")

        # v2.7 quantitative-effect rendering (P1.8). Surface effect
        # size + CI + NNT + n + primary outcome whenever a citation
        # carries them — the data was always in the registry intent
        # but not exposed to users until v2.7. A clinician deciding
        # whether to start CBD for a Dravet patient reads the actual
        # number, not a generic "trial-supported" line.
        quant_citations = [
            c for c in x.citations
            if c.effect_size or c.confidence_interval or c.nnt
            or c.n or c.primary_outcome
        ]
        if quant_citations:
            out.append("- **Quantitative effect (from cited trials):**")
            for c in quant_citations:
                anchor = (
                    f"PMID {c.pmid}" if c.pmid
                    else (f"doi:{c.doi}" if c.doi else c.label)
                )
                out.append(f"  - **{anchor}**")
                if c.n:
                    out.append(f"    - n: {c.n}")
                if c.comparator:
                    out.append(f"    - Comparator: {c.comparator}")
                if c.primary_outcome:
                    out.append(f"    - Primary outcome: {c.primary_outcome}")
                if c.effect_size:
                    out.append(f"    - Effect size: {c.effect_size}")
                if c.confidence_interval:
                    out.append(f"    - 95% CI: {c.confidence_interval}")
                if c.nnt:
                    out.append(f"    - NNT: {c.nnt}")
                if c.funding:
                    out.append(f"    - Funding: {c.funding}")

        # v2.7 null/negative evidence (P2.14). When a population has
        # known null trials, surface them under a distinct heading so
        # the user sees the evidence on both sides. Visible absence
        # ("None identified at the inclusion bar") is better than
        # hidden absence.
        if x.null_trials:
            out.append("- **Negative or null trials:**")
            for c in x.null_trials:
                anchor = (
                    f"PMID {c.pmid}" if c.pmid
                    else (f"doi:{c.doi}" if c.doi else c.label)
                )
                out.append(f"  - {c.label} — {anchor}")
                if c.primary_outcome:
                    out.append(f"    - Outcome: {c.primary_outcome}")
                if c.effect_size:
                    out.append(f"    - Effect: {c.effect_size}")

        if x.notes:
            out.append(f"- **Notes:** {x.notes}")
        out.append("")
    return "\n".join(out)
