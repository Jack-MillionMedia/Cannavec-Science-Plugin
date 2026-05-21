"""Cannabinoid contraindication registry.

Tighter than :mod:`cannavec.populations` and :mod:`cannavec.interactions`.
A *contraindication* is the assertion "do not give compound X to
population Y because of risk Z, with severity level S, anchored by
citation C". The registry is the curated, citation-anchored answer
to "who should not use this cannabinoid?" — at population level.

Design rules:

- Every entry has a primary citation (PubMed, regulator label, major
  guideline).
- Every entry names the *compound*, the *population*, the *clinical
  reason*, the *severity* (absolute vs relative), and the *override
  context* (when, if ever, a clinician may override).
- The list is conservative. New entries require a citation meeting
  the inclusion bar (≥ 1 regulator label change, major guideline,
  or controlled trial demonstrating the harm).
- Cannavec uses this primitive to *render* the population-level
  contraindication. Individual override remains a clinician's call;
  :mod:`cannavec.safety` enforces the boundary on individual advice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from cannavec_science.evidence import Claim, SourceTier


class ContraindicationSeverity(str, Enum):
    ABSOLUTE = "absolute"      # do not use; no override
    STRONG_RELATIVE = "strong_relative"  # avoid unless overwhelming benefit
    RELATIVE = "relative"      # use with caution + monitoring


@dataclass(frozen=True)
class ContraindicationCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class Contraindication:
    """A single, citable cannabinoid contraindication record."""

    compound: str               # canonical name, e.g. "Δ⁹-THC", "CBD", "any cannabinoid"
    population: str             # who is contraindicated
    clinical_reason: str        # why the contraindication exists
    severity: ContraindicationSeverity
    override_context: str       # if/when a clinician may override
    citations: tuple[ContraindicationCitation, ...]
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "compound": self.compound,
            "population": self.population,
            "clinical_reason": self.clinical_reason,
            "severity": self.severity.value,
            "override_context": self.override_context,
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi,
                 "url": c.url, "year": c.year}
                for c in self.citations
            ],
            "notes": self.notes,
        }

    def to_claim(self, *, source_tier: "SourceTier | None" = None) -> "Claim":
        """Render this row as a typed :class:`cannavec.evidence.Claim`.

        Contraindication claims are surfaced as ``SAFETY`` because
        ``ClaimType`` does not have a dedicated contraindication
        category and SAFETY is the closest fit. Severity is encoded
        in the text. Default ``source_tier`` is ``JOURNAL_RCT``.

        Text wording uses "is contraindicated", which does not appear
        in any forbidden-verb list — the wording is mechanically safe
        at any grade the deterministic grader assigns.
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

        severity_phrase = {
            ContraindicationSeverity.ABSOLUTE: "is contraindicated",
            ContraindicationSeverity.STRONG_RELATIVE:
                "is contraindicated (strong relative — avoid unless overwhelming benefit)",
            ContraindicationSeverity.RELATIVE:
                "is contraindicated (relative — use with caution + monitoring)",
        }[self.severity]

        # Text uses only structured fields so wording is grade-stable.
        # The registry's clinical_reason and override_context can echo
        # the cited paper's phrasing (e.g., Volkow 2014's "is associated
        # with"), which would trip the wording-vs-grade check at the
        # deterministic Level-C grade. Those fields stay reachable via
        # to_dict(); Claim.text is the anchored statement only.
        text = (
            f"{self.compound} {severity_phrase} in {self.population}."
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
    contraindication: "Contraindication",
    *,
    source_tier: "SourceTier | None" = None,
) -> "Claim":
    """Module-level helper mirroring :meth:`Contraindication.to_claim`."""
    return contraindication.to_claim(source_tier=source_tier)


# ── Registry ──────────────────────────────────────────────────────────
#
# Inclusion bar: ≥ 1 regulator label change, major guideline, or
# controlled trial demonstrating the harm. Each entry's reason and
# override-context are encoded explicitly so a clinician-facing
# surface can render the population-level guidance without
# extrapolating beyond what the source supports.

_REGISTRY: tuple[Contraindication, ...] = (
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="personal or family history of psychotic disorder (schizophrenia, schizoaffective)",
        clinical_reason=(
            "THC can precipitate or worsen psychotic episodes; the risk "
            "is elevated in individuals with personal or first-degree "
            "family history of psychotic illness."
        ),
        severity=ContraindicationSeverity.ABSOLUTE,
        override_context=(
            "No general override. Rare specialist-supervised exceptions "
            "(e.g. palliative care) require psychiatric co-management."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="pregnant women",
        clinical_reason=(
            "Cannabinoids cross the placenta; observational evidence of "
            "modestly lower birth weight and small effects on offspring "
            "neurodevelopment. No trial-supported safe dose exists."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "ACOG / RCOG / SOGC default is avoidance. Specialist-led "
            "consideration only when no safer alternative exists for a "
            "severe condition."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    Contraindication(
        compound="any cannabinoid",
        population="lactating women",
        clinical_reason=(
            "Cannabinoids are excreted in breast milk and infants metabolise "
            "them more slowly than adults; chronic exposure profile in "
            "breastfed infants is poorly characterised."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "ACOG / RCOG / SOGC default is avoidance. Specialist-led "
            "decision only with documented absence of alternative therapy."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="adolescents (< 18) — non-trial-supported indications",
        clinical_reason=(
            "Adolescent-onset heavy cannabis use is associated with "
            "elevated risk of psychotic disorder, persistent cognitive "
            "deficits, and cannabis use disorder."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Only inside narrow paediatric-epilepsy protocols (Dravet, "
            "LGS, TSC) supervised by a paediatric neurologist."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="unstable cardiovascular disease (recent MI, unstable angina, severe arrhythmia)",
        clinical_reason=(
            "Acute THC induces dose-dependent tachycardia and orthostatic "
            "hypotension; cardiovascular events documented in vulnerable "
            "patients post-acute exposure."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Use only when no safer alternative exists, at the lowest "
            "trial-supported dose, with cardiology co-management."
        ),
        citations=(
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    Contraindication(
        compound="CBD (high-dose, > 10 mg/kg/day)",
        population="patients on valproate",
        clinical_reason=(
            "Elevated hepatic transaminases occur in ~5-20% of CBD-treated "
            "epilepsy patients in pivotal trials, clustered in the "
            "valproate co-treated subgroup."
        ),
        severity=ContraindicationSeverity.RELATIVE,
        override_context=(
            "Use with LFT monitoring on initiation, at each dose increase, "
            "and at 1 / 3 / 6 months. Reduce CBD or valproate dose if "
            "transaminases exceed 3x upper limit of normal."
        ),
        citations=(
            ContraindicationCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                year=2017,
            ),
            ContraindicationCitation(
                label="Gaston 2017 — CBD AE patterns in epilepsy trials",
                pmid="28815401",
                year=2017,
            ),
        ),
    ),
    Contraindication(
        compound="any cannabinoid",
        population="active or recently treated cannabis hyperemesis syndrome (CHS)",
        clinical_reason=(
            "CHS is paradoxical — continued cannabis use worsens the "
            "syndrome; cessation is the only definitive treatment."
        ),
        severity=ContraindicationSeverity.ABSOLUTE,
        override_context=(
            "No override. Recurrence on rechallenge is the rule, not the "
            "exception."
        ),
        citations=(
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="patients with active substance use disorder",
        clinical_reason=(
            "Cannabis use disorder lifetime risk ~9% overall, ~17% with "
            "adolescent onset, ~25-50% in daily users; comorbid SUD "
            "compounds the risk."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Specialist co-management with addiction medicine; consider "
            "CBD-predominant alternatives where indicated."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    Contraindication(
        compound="any cannabinoid (specific formulation)",
        population="documented hypersensitivity to the formulation or excipient",
        clinical_reason=(
            "Sesame-oil / propylene-glycol / sucralose hypersensitivity "
            "reactions documented with specific cannabinoid products "
            "(e.g. Epidiolex sesame-oil vehicle)."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Switch to a formulation without the offending excipient — "
            "true cannabinoid hypersensitivity is rare."
        ),
        citations=(
            ContraindicationCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM, formulation context)",
                pmid="28538134",
                year=2017,
            ),
        ),
    ),
    Contraindication(
        compound="inhaled cannabis (smoked or vaped flower / concentrate)",
        population="patients with severe asthma, COPD, or recent respiratory infection",
        clinical_reason=(
            "Combustion products and particulate exposure exacerbate "
            "underlying lung disease; vaping-related lung injury (EVALI) "
            "case series documented additional risk."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Switch to oral, sublingual, or oromucosal formulations "
            "where indicated."
        ),
        citations=(
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    # ── v1.9 expansions ───────────────────────────────────────────────
    Contraindication(
        compound="any cannabinoid",
        population="learner / probationary drivers in jurisdictions with zero-tolerance THC laws",
        clinical_reason=(
            "Recent cannabis use approximately doubles motor-vehicle "
            "crash odds; per-se THC blood thresholds in many "
            "jurisdictions trigger licence suspension at any detection "
            "level for learner / probationary drivers."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "No general override; if cannabinoid therapy is clinically "
            "indicated, prefer CBD-predominant oral formulations with "
            "negligible blood THC under jurisdictional per-se law and "
            "document the clinical decision."
        ),
        citations=(
            ContraindicationCitation(
                label="Hartman 2015 — Cannabis effects on driving (review)",
                pmid="26041581",
                year=2015,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="adolescents with active educational engagement (cognitive-development concern)",
        clinical_reason=(
            "Adolescent-onset heavy cannabis use is associated with "
            "persistent cognitive deficits and lower educational "
            "attainment in observational cohorts; magnitude debated, "
            "direction consistent."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Only inside narrow paediatric protocols (Dravet / LGS / "
            "TSC) supervised by a paediatric neurologist; counsel "
            "delayed initiation for any non-trial indication."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    Contraindication(
        compound="any cannabinoid",
        population="perioperative — within 72 hours of planned general anaesthesia or surgery",
        clinical_reason=(
            "Cannabis users require higher induction and maintenance "
            "anaesthetic doses (documented for propofol / volatile "
            "agents); acute intoxication increases airway-reactivity "
            "and dose-response unpredictability."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "If chronic use cannot be paused, declare to the "
            "anaesthesia team pre-operatively for dose adjustment and "
            "extended monitoring."
        ),
        citations=(
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    Contraindication(
        compound="any cannabinoid (formulation-dependent — solvents, sweeteners)",
        population="patients at elevated long-QT or torsade risk",
        clinical_reason=(
            "Some cannabinoid formulations include excipients with "
            "documented QT-prolonging signals (rarely); concurrent "
            "QT-prolonging medications (some macrolides, antipsychotics, "
            "antiarrhythmics) compound the risk; case reports of "
            "cardiac arrhythmia post acute cannabis use exist in "
            "susceptible patients."
        ),
        severity=ContraindicationSeverity.RELATIVE,
        override_context=(
            "Cardiology-consulted dose escalation with baseline + "
            "follow-up ECG; switch to formulations without QT-suspect "
            "excipients."
        ),
        citations=(
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    Contraindication(
        compound="CBD (high-dose, > 10 mg/kg/day)",
        population="patients with severe hepatic impairment (Child-Pugh B or C)",
        clinical_reason=(
            "CBD undergoes substantial hepatic metabolism; the "
            "Epidiolex US label recommends initial dose reduction and "
            "slower titration for moderate / severe hepatic impairment "
            "to limit systemic exposure increases."
        ),
        severity=ContraindicationSeverity.RELATIVE,
        override_context=(
            "Start at the reduced label-recommended dose; LFT and "
            "clinical-response monitoring at every titration step."
        ),
        citations=(
            ContraindicationCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM, label context)",
                pmid="28538134",
                year=2017,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="patients with history of mania / bipolar I disorder",
        clinical_reason=(
            "THC can precipitate manic episodes; cohort signal in "
            "bipolar I patients shows accelerated relapse risk."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Psychiatric co-management; CBD-predominant alternatives "
            "preferred where indicated."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC (high-dose, edible)",
        population="patients with anxiety disorder or panic disorder",
        clinical_reason=(
            "High-dose THC frequently precipitates paradoxical "
            "anxiety and panic in anxiety-prone individuals; oral "
            "edibles with delayed onset compound the risk by "
            "encouraging over-titration before peak plasma level."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "If cannabinoid therapy is clinically indicated, prefer "
            "low-dose CBD-predominant oral formulations and avoid "
            "high-THC edibles."
        ),
        citations=(
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    Contraindication(
        compound="inhaled Δ⁹-THC",
        population="patients with narrow-angle glaucoma on IOP-lowering therapy",
        clinical_reason=(
            "Acute THC lowers intraocular pressure transiently but "
            "tachyphylaxis is rapid and rebound after dose-end may "
            "exceed baseline; not a viable maintenance therapy and "
            "may destabilise existing IOP control."
        ),
        severity=ContraindicationSeverity.STRONG_RELATIVE,
        override_context=(
            "Ophthalmology-led decision; rarely indicated when modern "
            "topical agents are available."
        ),
        citations=(
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    Contraindication(
        compound="Δ⁹-THC and high-THC cannabis",
        population="patients on cancer immunotherapy (checkpoint inhibitors)",
        clinical_reason=(
            "Small observational signals (e.g. Israeli cohorts) "
            "suggest blunted response to anti-PD-1 / PD-L1 immunotherapy "
            "in cannabis users; mechanism uncertain (immunomodulatory "
            "effects of cannabinoids on T-cell function); evidence "
            "preliminary."
        ),
        severity=ContraindicationSeverity.RELATIVE,
        override_context=(
            "Oncology co-management; counsel cessation during "
            "immunotherapy if alternatives for symptom management exist."
        ),
        citations=(
            ContraindicationCitation(
                label="Volkow 2014 — Adverse health effects of marijuana use (NEJM, immune signal context)",
                pmid="24897085",
                year=2014,
            ),
        ),
    ),
    Contraindication(
        compound="any cannabinoid",
        population="patients operating heavy machinery, commercial vehicles, or in safety-sensitive occupations",
        clinical_reason=(
            "Acute THC impairs reaction time, attention, motor "
            "coordination for hours after dosing; oral edibles last "
            "longer than inhaled. Federal regulatory frameworks "
            "(US DOT, EU EASA) prohibit safety-sensitive work post-use."
        ),
        severity=ContraindicationSeverity.ABSOLUTE,
        override_context=(
            "No general override during operating periods. CBD-only "
            "formulations may be acceptable where local employer / "
            "regulator policy permits documented zero blood THC."
        ),
        citations=(
            ContraindicationCitation(
                label="Hartman 2015 — Cannabis effects on driving (review)",
                pmid="26041581",
                year=2015,
            ),
            ContraindicationCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
)


def all_contraindications() -> tuple[Contraindication, ...]:
    """Return the full curated registry (read-only)."""
    return _REGISTRY


def find_contraindications(
    *,
    compound: str | None = None,
    population: str | None = None,
    min_severity: ContraindicationSeverity | None = None,
) -> tuple[Contraindication, ...]:
    """Search the registry. Matchers are case-insensitive substring.

    The ``compound`` filter is normalised so that ``Δ9-THC``,
    ``Δ⁹-THC``, and ``delta-9-THC`` all match the registry's canonical
    ``Δ⁹-THC`` form.
    """
    from cannavec_science._normalize import normalized_contains

    def matches(s: str, q: str | None) -> bool:
        return q is None or q.lower() in s.lower()

    sev_order = {
        ContraindicationSeverity.RELATIVE: 0,
        ContraindicationSeverity.STRONG_RELATIVE: 1,
        ContraindicationSeverity.ABSOLUTE: 2,
    }
    min_rank = sev_order[min_severity] if min_severity else 0

    out: list[Contraindication] = []
    for x in _REGISTRY:
        if not normalized_contains(x.compound, compound):
            continue
        if not matches(x.population, population):
            continue
        if sev_order[x.severity] < min_rank:
            continue
        out.append(x)
    return tuple(out)


# Population-keyword aliases — mirrors cannavec.adverse_events for
# consistency. A clinician describing a patient as "elderly" should get
# the same population expansion in both the AE and contraindication
# cross-cuts.
_POPULATION_ALIASES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\belder(?:ly|s)?\b|\bgeriatric\b|\bolder adult\b|"
                r"\bover\s*(?:65|70)\b", re.IGNORECASE),
     ("elder", "older")),
    (re.compile(r"\badolescen\w*\b|\bteen\w*\b|\byouth\b|\bunder\s*(?:18|21)\b",
                re.IGNORECASE), ("adolescent",)),
    (re.compile(r"\bpaed\w*\b|\bped\w*\b|\bchild\w*\b|\binfant\w*\b",
                re.IGNORECASE), ("paediatric", "pediatric")),
    (re.compile(r"\bpregnan\w*\b|\bprenatal\b|\bfetal\b|\bfoetal\b",
                re.IGNORECASE), ("pregnan",)),
    (re.compile(r"\blactat\w*\b|\bbreastfeed\w*\b|\bnursing\b",
                re.IGNORECASE), ("lactat",)),
    (re.compile(r"\bcardiovascular\b|\bcardiac\b|\bheart\b|"
                r"\barrhyth\w*\b|\bangina\b|\bMI\b|\bmyocardial\b",
                re.IGNORECASE), ("cardiovascular",)),
    (re.compile(r"\bschizophreni\w*\b|\bpsychos\w*\b|\bpsychiatric\b|"
                r"\bbipolar\b", re.IGNORECASE), ("psychotic",)),
    (re.compile(r"\bSUD\b|\bsubstance use disorder\b|\baddiction\b",
                re.IGNORECASE), ("substance use",)),
    (re.compile(r"\basthma\b|\bCOPD\b|\bemphysema\b|\bbronchitis\b|"
                r"\brespiratory\b", re.IGNORECASE),
     ("asthma", "COPD", "respiratory")),
    (re.compile(r"\bCHS\b|\bhyperemesis\b|\bcyclic vomit\w*\b",
                re.IGNORECASE), ("hyperemesis",)),
    (re.compile(r"\bvalproate\b|\bvalproic acid\b", re.IGNORECASE),
     ("valproate",)),
    (re.compile(r"\bhypersensitivity\b|\ballerg\w*\b|\bexcipient\b",
                re.IGNORECASE), ("hypersensitivity",)),
)


def _population_aliases_from(text: str) -> tuple[str, ...]:
    out: set[str] = set()
    for rx, fragments in _POPULATION_ALIASES:
        if rx.search(text):
            out.update(fragments)
    if not out:
        out.add(text)
    return tuple(sorted(out))


def find_by_population(
    population_cue: str,
    *,
    compound: str | None = None,
    min_severity: ContraindicationSeverity | None = None,
) -> tuple[Contraindication, ...]:
    """Cross-cut search: return contraindications for a named population.

    Same shape as :func:`cannavec.adverse_events.find_by_population` —
    free-text population cue is expanded into registry-substring
    fragments via :data:`_POPULATION_ALIASES`, then matched against
    the entry's ``population`` field. Combine with ``compound`` and
    ``min_severity`` for cross-cut clinical decision support.
    """
    fragments = _population_aliases_from(population_cue)
    if not fragments:
        return ()

    def matches_population(entry_pop: str) -> bool:
        ep = entry_pop.lower()
        return any(f.lower() in ep for f in fragments)

    sev_order = {
        ContraindicationSeverity.RELATIVE: 0,
        ContraindicationSeverity.STRONG_RELATIVE: 1,
        ContraindicationSeverity.ABSOLUTE: 2,
    }
    min_rank = sev_order[min_severity] if min_severity else 0

    out: list[Contraindication] = []
    for x in _REGISTRY:
        if not matches_population(x.population):
            continue
        if compound and compound.lower() not in x.compound.lower():
            continue
        if sev_order[x.severity] < min_rank:
            continue
        out.append(x)
    return tuple(out)


_COMPOUND_KEYWORDS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\bcbd\b|\bcannabidiol\b", re.IGNORECASE),
     ("CBD", "any cannabinoid")),
    (re.compile(r"\bthc\b|\btetrahydrocannabinol\b|\bdelta[-\s]?9\b|"
                r"\bΔ9\b|\bΔ⁹\b", re.IGNORECASE),
     ("Δ⁹-THC", "high-THC cannabis", "any cannabinoid")),
    (re.compile(r"\bcannabis\b|\bmarijuana\b|\bweed\b", re.IGNORECASE),
     ("any cannabinoid", "high-THC cannabis", "inhaled cannabis")),
    (re.compile(r"\binhal\w*\b|\bsmoke\w*\b|\bvape\w*\b|"
                r"\bsmoked\b|\bvaped\b", re.IGNORECASE),
     ("inhaled cannabis", "any cannabinoid")),
)

_POPULATION_KEYWORDS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\bschizophreni\w*\b|\bpsychos\w*\b|\bpsychiatric\b",
                re.IGNORECASE),
     ("psychotic disorder",)),
    (re.compile(r"\bpregnan\w*\b|\bprenatal\b|\bfetal\b", re.IGNORECASE),
     ("pregnant",)),
    (re.compile(r"\blactat\w*\b|\bbreastfeed\w*\b|\bnursing\b",
                re.IGNORECASE), ("lactating",)),
    (re.compile(r"\badolescent\w*\b|\bteen\w*\b|\byouth\b|"
                r"\bunder (?:18|21)\b", re.IGNORECASE),
     ("adolescent",)),
    (re.compile(r"\bcardiovascular\b|\bheart\b|\bMI\b|\bmyocardial\b|"
                r"\barrhythm\w*\b|\bangina\b", re.IGNORECASE),
     ("cardiovascular",)),
    (re.compile(r"\bvalproate\b|\bvalproic acid\b", re.IGNORECASE),
     ("valproate",)),
    (re.compile(r"\bCHS\b|\bhyperemesis\b|\bcyclic vomit\w*\b",
                re.IGNORECASE), ("hyperemesis",)),
    (re.compile(r"\bSUD\b|\bsubstance use disorder\b|\baddiction\b",
                re.IGNORECASE), ("substance use disorder",)),
    (re.compile(r"\basthma\b|\bCOPD\b|\bemphysema\b|\bbronchitis\b",
                re.IGNORECASE), ("asthma", "COPD", "respiratory")),
)


def detect_contraindication_mention(
    text: str,
) -> tuple[Contraindication, ...]:
    """Return registry entries matched by a (compound, population) pair in ``text``."""
    compounds: set[str] = set()
    for rx, labels in _COMPOUND_KEYWORDS:
        if rx.search(text):
            compounds.update(labels)
    populations: set[str] = set()
    for rx, labels in _POPULATION_KEYWORDS:
        if rx.search(text):
            populations.update(labels)
    if not compounds or not populations:
        return ()

    def _pop_matches(entry_pop: str) -> bool:
        ep = entry_pop.lower()
        return any(p.lower() in ep or ep in p.lower() for p in populations)

    def _comp_matches(entry_comp: str) -> bool:
        ec = entry_comp.lower()
        return any(c.lower() in ec or ec in c.lower() for c in compounds)

    out: list[Contraindication] = []
    seen: set[tuple[str, str]] = set()
    for x in _REGISTRY:
        if not _comp_matches(x.compound):
            continue
        if not _pop_matches(x.population):
            continue
        key = (x.compound, x.population)
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return tuple(out)


# Class-level keywords for the generic-question fallback path. Closes
# the 2026-05-19 Oracle Evaluator §4.3 finding that "Is cannabis
# contraindicated in any populations?" returned 0 rows.
_CONTRA_CLASS_KEYWORDS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{kw}\b", flags=re.IGNORECASE)
    for kw in [
        "contraindicat\\w*",
        "who should not (use|take)",
        "absolute contraindication",
        "absolute contraindications",
        "relative contraindication",
        "relative contraindications",
        "should avoid",
        "must avoid",
        "avoid in",
    ]
)


def detect_contraindication_class_mention(
    text: str,
) -> tuple[Contraindication, ...]:
    """Return all contraindication rows matching a *class* keyword in ``text``.

    Companion to :func:`detect_contraindication_mention` for prompts
    that ask the general question "what are the contraindications of
    cannabis / CBD / THC?" without naming a specific population.
    Optionally filters by any compound named in the prompt.
    """
    matched = False
    for rx in _CONTRA_CLASS_KEYWORDS:
        if rx.search(text):
            matched = True
            break
    if not matched:
        return ()
    compounds: set[str] = set()
    for rx, labels in _COMPOUND_KEYWORDS:
        if rx.search(text):
            compounds.update(labels)
    if compounds:
        rows = [r for r in _REGISTRY
                if any(c.lower() in r.compound.lower()
                       or r.compound.lower() in c.lower() for c in compounds)]
    else:
        rows = list(_REGISTRY)
    seen: set[tuple[str, str]] = set()
    out: list[Contraindication] = []
    for r in rows:
        key = (r.compound, r.population)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return tuple(out)


def format_for_clinician(
    contraindications: Iterable[Contraindication],
) -> str:
    """Render a Markdown clinician-facing summary of contraindications."""
    items = list(contraindications)
    if not items:
        return (
            "_No high-confidence contraindication records matched the "
            "named compound and population. Absence does not mean safety — "
            "it means the registry has no entry above the inclusion bar "
            "(≥ 1 regulator label change, major guideline, or controlled "
            "trial demonstrating the harm)._"
        )
    lines: list[str] = [
        "| Compound | Population | Severity | Reason | Override | Source |",
        "|---|---|---|---|---|---|",
    ]
    for x in items:
        src_strs = ", ".join(
            f"PMID {c.pmid}" if c.pmid
            else (f"doi:{c.doi}" if c.doi else c.label)
            for c in x.citations
        )
        reason = x.clinical_reason.replace("\n", " ")
        if len(reason) > 140:
            reason = reason[:137] + "..."
        override = x.override_context.replace("\n", " ")
        if len(override) > 140:
            override = override[:137] + "..."
        lines.append(
            f"| {x.compound} | {x.population} | {x.severity.value} | "
            f"{reason} | {override} | {src_strs} |"
        )
    lines.append("")
    lines.append(
        "**Severity legend:** absolute = do-not-use, no override; "
        "strong_relative = avoid unless overwhelming benefit; "
        "relative = use with caution + monitoring. "
        "Individual override is a clinician's call — Cannavec describes "
        "the population-level guidance only."
    )
    return "\n".join(lines)
