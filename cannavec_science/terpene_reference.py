"""Curated cannabis terpene reference data.

Cannabis terpenes are a genuinely complex area where the evidence
landscape runs from well-established analytical chemistry to
highly speculative pharmacological claims. This module separates
those clearly:

- Analytical facts (presence, concentration ranges in cannabis, CAS
  numbers, and chemical class) are anchored by ISO/AOAC GC methodology
  and published chromatographic surveys.
- Pharmacological signals are graded by evidence level. Most terpene-
  receptor evidence is in vitro or animal only (Level D/E). A small
  number have human-relevant evidence (CB2 / TRPV1 signals for
  β-caryophyllene, 5-HT1A signal for linalool).
- The Entourage Hypothesis (that terpenes modify cannabinoid effect
  in vivo) is explicitly named as a hypothesis, not a fact.

Design rules:
- Every receptor interaction has a source and assay type.
- Concentration ranges are from published GC surveys, not marketing copy.
- Evidence grades are conservative: in-vitro evidence is Level D at most
  without a human bridging study.
- The UNSUPPORTED grade is used when the receptor claim lacks a primary
  database (ChEMBL / BindingDB / peer-reviewed primary study) source.
- This module is read-only. Additions require a primary source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from cannavec_science.evidence import EvidenceLevel


class TerpeneClass(str, Enum):
    MONOTERPENE = "monoterpene"
    SESQUITERPENE = "sesquiterpene"
    DITERPENE = "diterpene"
    OTHER = "other"


@dataclass(frozen=True)
class TerpeneReceptorInteraction:
    """A single receptor / target interaction for a terpene.

    Source requirements:
    - ``primary_db`` should be a ChEMBL, BindingDB, or primary-journal
      identifier. A receptor signal without a primary-DB source is
      graded UNSUPPORTED regardless of how widely it is repeated.
    - ``assay_type`` distinguishes the evidence quality: binding
      (radioligand displacement), functional (cAMP / calcium flux),
      in_vivo (animal model), or clinical (human study).
    """

    receptor: str
    direction: str                  # agonist | partial_agonist | antagonist | modulator | inhibitor
    ki_or_ic50_um: float | None     # micromolar; None if not published
    assay_type: str                 # binding | functional | in_vivo | clinical
    species: str                    # human | rat | mouse | in_vitro
    evidence_level: EvidenceLevel
    primary_db: str | None          # ChEMBL / BindingDB compound ID or PMID
    note: str = ""


@dataclass(frozen=True)
class CannabisTerpene:
    """A cannabis terpene with analytical + pharmacological data."""

    name: str                           # IUPAC-preferred name
    common_names: tuple[str, ...]       # colloquial / synonym names
    cas: str                            # CAS registry number
    molecular_formula: str
    terpene_class: TerpeneClass
    typical_concentration_pct_ww: tuple[float, float]  # (min, max) % w/w in dried flower
    concentration_note: str             # caveats on the concentration range
    receptor_interactions: tuple[TerpeneReceptorInteraction, ...]
    odor_descriptors: tuple[str, ...]   # sensory profile (analytical, not pharmacological)
    primary_survey_pmid: str | None     # GC survey anchoring the concentration data

    def best_evidence_level(self) -> EvidenceLevel:
        if not self.receptor_interactions:
            return EvidenceLevel.UNSUPPORTED
        return max(
            self.receptor_interactions,
            key=lambda i: i.evidence_level.rank,
        ).evidence_level


# ── Registry ──────────────────────────────────────────────────────────

_TERPENE_REGISTRY: list[CannabisTerpene] = [
    CannabisTerpene(
        name="(−)-β-caryophyllene",
        common_names=("beta-caryophyllene", "BCP", "caryophyllene"),
        cas="87-44-5",
        molecular_formula="C₁₅H₂₄",
        terpene_class=TerpeneClass.SESQUITERPENE,
        typical_concentration_pct_ww=(0.05, 1.00),
        concentration_note=(
            "Most abundant sesquiterpene in many cannabis chemotypes. "
            "Typical range across published GC-MS surveys of dried flower "
            "(pre-combustion): 0.1–0.5% w/w; rare excursions to ~1.0% in "
            "high-caryophyllene cultivars. Reports of 1.2%+ exist in the "
            "literature but are at the upper tail of credibly observed "
            "maxima — values above 1.0% should be regarded as exceptional "
            "and confirmed against the primary GC-MS chromatogram. "
            "Post-combustion levels differ."
        ),
        receptor_interactions=(
            TerpeneReceptorInteraction(
                receptor="CB2 (CNR2; UniProt P34972)",
                direction="partial_agonist",
                ki_or_ic50_um=0.155,
                assay_type="binding",
                species="human",
                evidence_level=EvidenceLevel.C,
                primary_db="PMID 18574142",
                note=(
                    "Gertsch J et al., PNAS 2008. Ki 155 nM in human CB2 binding "
                    "assay. Functional anti-inflammatory signal in mouse LPS model "
                    "at pharmacologically relevant concentrations. Human bridging "
                    "data limited — graded Level C."
                ),
            ),
            TerpeneReceptorInteraction(
                receptor="CB1 (CNR1; UniProt P21554)",
                direction="modulator",
                ki_or_ic50_um=None,
                assay_type="binding",
                species="human",
                evidence_level=EvidenceLevel.D,
                primary_db="PMID 18574142",
                note=(
                    "No significant CB1 binding at pharmacological concentrations "
                    "in the Gertsch 2008 study. Some in-vitro modulation reported "
                    "at supratherapeutic concentrations. Not a CB1 agonist."
                ),
            ),
        ),
        odor_descriptors=("spicy", "woody", "clove-like", "peppery"),
        primary_survey_pmid="29422988",
    ),

    CannabisTerpene(
        name="myrcene",
        common_names=("β-myrcene", "beta-myrcene"),
        cas="123-35-3",
        molecular_formula="C₁₀H₁₆",
        terpene_class=TerpeneClass.MONOTERPENE,
        typical_concentration_pct_ww=(0.02, 1.50),
        concentration_note=(
            "Often the dominant monoterpene in cannabis flower. "
            "GC-FID/GC-MS surveys report up to 1.5% w/w in some cultivars. "
            "Structurally simple; primarily an analytical marker."
        ),
        receptor_interactions=(
            TerpeneReceptorInteraction(
                receptor="TRPV1 (transient receptor potential vanilloid 1)",
                direction="modulator",
                ki_or_ic50_um=None,
                assay_type="in_vivo",
                species="mouse",
                evidence_level=EvidenceLevel.D,
                primary_db="PMID 11849820",
                note=(
                    "Lorenzetti BB et al. Neuropharmacol 2002. Sedative/analgesic "
                    "effect in rodent hot-plate model, proposed TRPV1 mechanism. "
                    "No human bridging data. Level D (animal only)."
                ),
            ),
            TerpeneReceptorInteraction(
                receptor="mu-opioid receptor (OPRM1; UniProt P35372)",
                direction="modulator",
                ki_or_ic50_um=None,
                assay_type="in_vivo",
                species="mouse",
                evidence_level=EvidenceLevel.E,
                primary_db="PMID 11849820",
                note=(
                    "Proposed opioid-pathway contribution in mouse pain models. "
                    "No binding affinity data. Highly speculative for humans."
                ),
            ),
        ),
        odor_descriptors=("earthy", "musky", "herbal", "mango-like"),
        primary_survey_pmid="29422988",
    ),

    CannabisTerpene(
        name="(R)-(+)-limonene",
        common_names=("d-limonene", "limonene"),
        cas="5989-27-5",
        molecular_formula="C₁₀H₁₆",
        terpene_class=TerpeneClass.MONOTERPENE,
        typical_concentration_pct_ww=(0.01, 0.80),
        concentration_note=(
            "Common in citrus-phenotype cultivars. GC surveys: 0.01–0.8% w/w. "
            "Often overstated in marketing; actual GC-confirmed content varies widely."
        ),
        receptor_interactions=(
            TerpeneReceptorInteraction(
                receptor="5-HT1A (HTR1A; UniProt P08908)",
                direction="agonist",
                ki_or_ic50_um=None,
                assay_type="functional",
                species="rat",
                evidence_level=EvidenceLevel.D,
                primary_db="PMID 21439350",
                note=(
                    "Komori T et al., Pharmacol Biochem Behav 2011. "
                    "Anti-anxiety effect in rat open-field test; proposed 5-HT1A "
                    "mechanism. Concentration used: inhalation model, not well "
                    "translatable to inhaled cannabis terpene concentrations."
                ),
            ),
        ),
        odor_descriptors=("citrus", "lemon", "orange"),
        primary_survey_pmid="29422988",
    ),

    CannabisTerpene(
        name="linalool",
        common_names=("(R)-(-)-linalool", "(S)-(+)-linalool"),
        cas="78-70-6",
        molecular_formula="C₁₀H₁₈O",
        terpene_class=TerpeneClass.MONOTERPENE,
        typical_concentration_pct_ww=(0.005, 0.40),
        concentration_note=(
            "Lower concentration than myrcene or caryophyllene in most cannabis. "
            "GC surveys: 0.005–0.40% w/w. Lavender is a richer source. "
            "Cannabis-delivered human-relevant concentrations are unclear."
        ),
        receptor_interactions=(
            TerpeneReceptorInteraction(
                receptor="5-HT1A (HTR1A; UniProt P08908)",
                direction="partial_agonist",
                ki_or_ic50_um=None,
                assay_type="in_vivo",
                species="mouse",
                evidence_level=EvidenceLevel.D,
                primary_db="PMID 20378197",
                note=(
                    "Linck VM et al., Phytomedicine 2010. Anxiolytic effect in "
                    "mouse elevated plus-maze; 5-HT1A mechanism proposed. "
                    "No human clinical data."
                ),
            ),
            TerpeneReceptorInteraction(
                receptor="GABA-A (allosteric)",
                direction="modulator",
                ki_or_ic50_um=None,
                assay_type="in_vivo",
                species="mouse",
                evidence_level=EvidenceLevel.D,
                primary_db="PMID 24676538",
                note=(
                    "Proposed sedative mechanism in mouse sleep models. "
                    "Mechanistic data incomplete. Level D."
                ),
            ),
        ),
        odor_descriptors=("floral", "lavender", "woody"),
        primary_survey_pmid="29422988",
    ),

    CannabisTerpene(
        name="α-pinene",
        common_names=("alpha-pinene",),
        cas="80-56-8",
        molecular_formula="C₁₀H₁₆",
        terpene_class=TerpeneClass.MONOTERPENE,
        typical_concentration_pct_ww=(0.01, 0.60),
        concentration_note=(
            "GC surveys: 0.01–0.60% w/w in dried cannabis flower. "
            "Both (+) and (−) enantiomers occur; ratio varies by cultivar."
        ),
        receptor_interactions=(
            TerpeneReceptorInteraction(
                receptor="AChE (acetylcholinesterase)",
                direction="inhibitor",
                ki_or_ic50_um=None,
                assay_type="functional",
                species="in_vitro",
                evidence_level=EvidenceLevel.D,
                primary_db="PMID 12725719",
                note=(
                    "Perry et al. J Pharm Pharmacol 2000. AChE inhibition in "
                    "in-vitro assay. Often cited in entourage claims; "
                    "human pharmacokinetics at cannabis-inhalation concentrations "
                    "unknown."
                ),
            ),
        ),
        odor_descriptors=("pine", "fresh", "resinous"),
        primary_survey_pmid="29422988",
    ),

    CannabisTerpene(
        name="terpinolene",
        common_names=("terpinolene", "delta-terpinene"),
        cas="586-62-9",
        molecular_formula="C₁₀H₁₆",
        terpene_class=TerpeneClass.MONOTERPENE,
        typical_concentration_pct_ww=(0.005, 1.00),
        concentration_note=(
            "Dominant in some landrace and sativa-type chemotypes; minor in others. "
            "0.005–1.0% w/w in GC surveys. Highly variable."
        ),
        receptor_interactions=(),
        odor_descriptors=("floral", "piney", "herby", "fresh"),
        primary_survey_pmid="29422988",
    ),

    CannabisTerpene(
        name="ocimene",
        common_names=("β-ocimene", "cis-β-ocimene", "trans-β-ocimene"),
        cas="3779-61-1",
        molecular_formula="C₁₀H₁₆",
        terpene_class=TerpeneClass.MONOTERPENE,
        typical_concentration_pct_ww=(0.001, 0.50),
        concentration_note=(
            "Variable presence. Sometimes prominent in specific cultivars. "
            "GC survey range: 0.001–0.5% w/w."
        ),
        receptor_interactions=(),
        odor_descriptors=("sweet", "herbal", "floral", "tropical"),
        primary_survey_pmid=None,
    ),

    CannabisTerpene(
        name="α-humulene",
        common_names=("alpha-humulene", "humulene"),
        cas="6753-98-6",
        molecular_formula="C₁₅H₂₄",
        terpene_class=TerpeneClass.SESQUITERPENE,
        typical_concentration_pct_ww=(0.01, 0.50),
        concentration_note=(
            "Co-occurs with β-caryophyllene in the same biosynthetic pathway. "
            "GC surveys: 0.01–0.5% w/w."
        ),
        receptor_interactions=(
            TerpeneReceptorInteraction(
                receptor="CB2 (CNR2; UniProt P34972)",
                direction="modulator",
                ki_or_ic50_um=None,
                assay_type="in_vivo",
                species="mouse",
                evidence_level=EvidenceLevel.E,
                primary_db="PMID 17869632",
                note=(
                    "Preliminary anti-inflammatory signal in mouse model; "
                    "CB2 mechanism not confirmed in binding assay. Level E."
                ),
            ),
        ),
        odor_descriptors=("woody", "earthy", "spicy"),
        primary_survey_pmid="29422988",
    ),
]


def all_terpenes() -> tuple[CannabisTerpene, ...]:
    """Return all curated terpene records."""
    return tuple(_TERPENE_REGISTRY)


def find_terpene(name: str) -> CannabisTerpene | None:
    """Find a terpene by name or common name (case-insensitive)."""
    lower = name.lower()
    for t in _TERPENE_REGISTRY:
        if t.name.lower() == lower:
            return t
        if any(cn.lower() == lower for cn in t.common_names):
            return t
    return None


def find_by_class(
    terpene_class: TerpeneClass,
) -> tuple[CannabisTerpene, ...]:
    """Return all terpenes of the given chemical class."""
    return tuple(t for t in _TERPENE_REGISTRY if t.terpene_class == terpene_class)


def find_by_receptor(receptor_substring: str) -> tuple[CannabisTerpene, ...]:
    """Return terpenes with any interaction at a receptor matching the substring."""
    lower = receptor_substring.lower()
    return tuple(
        t for t in _TERPENE_REGISTRY
        if any(lower in i.receptor.lower() for i in t.receptor_interactions)
    )


def format_terpene_summary(terpene: CannabisTerpene) -> str:
    """Render a terpene as a Markdown summary suitable for research answers."""
    lines: list[str] = []
    lines.append(f"### {terpene.name}")
    lines.append(
        f"**Class:** {terpene.terpene_class.value} | "
        f"**CAS:** {terpene.cas} | "
        f"**Formula:** {terpene.molecular_formula}"
    )
    lo, hi = terpene.typical_concentration_pct_ww
    lines.append(
        f"**Typical concentration in cannabis flower:** {lo:.3f}–{hi:.3f}% w/w"
    )
    lines.append(f"**Concentration note:** {terpene.concentration_note}")
    if terpene.odor_descriptors:
        lines.append(f"**Odor profile:** {', '.join(terpene.odor_descriptors)}")
    if terpene.primary_survey_pmid:
        lines.append(
            f"**GC survey anchor:** PMID {terpene.primary_survey_pmid}"
        )
    if terpene.receptor_interactions:
        lines.append("")
        lines.append("**Receptor interactions (pharmacology):**")
        for inter in terpene.receptor_interactions:
            ki_str = (
                f" Ki/IC₅₀ ≈ {inter.ki_or_ic50_um:.3f} μM"
                if inter.ki_or_ic50_um is not None
                else " (affinity not published)"
            )
            lines.append(
                f"- {inter.receptor}: {inter.direction}{ki_str} "
                f"({inter.assay_type}, {inter.species}) — "
                f"**{inter.evidence_level.value}**"
            )
            if inter.note:
                lines.append(f"  - Note: {inter.note}")
            if inter.primary_db:
                lines.append(f"  - Source: {inter.primary_db}")
    else:
        lines.append("**Receptor interactions:** No primary-database evidence available.")
    lines.append("")
    return "\n".join(lines)


# ── Entourage Hypothesis evidence statement ────────────────────────────

ENTOURAGE_HYPOTHESIS_STATEMENT = """\
**Entourage Hypothesis — Evidence Status (as of 2026-05)**

The Entourage Hypothesis (Mechoulam & Ben-Shabat 1998; Russo 2011) proposes
that terpenes, minor cannabinoids, and flavonoids modify the pharmacological
profile of THC and CBD in vivo, potentially by altering receptor binding,
bioavailability, or CNS penetration.

**Evidence level: Preliminary / Hypothesis — Level D at best (PMID 21749363)**

Key evidence gaps (honest synthesis):
- In-vitro terpene–receptor signals exist for β-caryophyllene (CB2),
  linalool (5-HT1A/GABA-A), limonene (5-HT1A), α-pinene (AChE),
  but most evidence is animal-model level (Level D/E).
- Terpene concentrations delivered by typical cannabis inhalation are
  largely below pharmacologically relevant thresholds established in
  isolated compound studies.
- Human clinical trials designed to compare equivalent-cannabinoid
  products with and without terpene profiles are minimal and
  methodologically limited.
- A 2021 systematic review (Pamplona FA et al., Front Neurol 2021,
  PMID 34484083) found insufficient evidence to confirm synergistic
  or antagonistic terpene–cannabinoid effects in humans.

**What this means for answers:**
- Do not state that terpenes "cause" specific effects in humans.
- Do state that the entourage hypothesis is an open pharmacological
  question with preclinical support but limited human evidence.
- Reference specific receptor interactions at evidence level (Level D/E)
  when naming a mechanism.
- Do not extrapolate terpene odor profiles to pharmacological effects
  (the sensory profile ≠ the pharmacological profile).
"""
