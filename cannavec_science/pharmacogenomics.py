"""Pharmacogenomics of cannabinoid metabolism.

CYP enzymes metabolise the major cannabinoids and vary substantially across
individuals due to genetic polymorphisms. This module provides a curated,
citation-anchored reference for the most clinically relevant
pharmacogenomic interactions between cannabis/cannabinoid use and CYP
enzyme polymorphism status.

Why this matters:

- CYP2C9*3 (poor metaboliser allele, ~6–7 % of Europeans) dramatically
  reduces Δ⁹-THC clearance → higher exposure → elevated impairment and
  adverse-effect risk at standard doses.
- CYP3A4 inducers (e.g., rifampicin, carbamazepine) and inhibitors
  (e.g., ketoconazole, clarithromycin) affect both THC and CBD exposure.
- CBD is a potent CYP2C19 inhibitor — clinically important for clobazam,
  proton pump inhibitors, and other 2C19 substrates.

Design rules:

- Every entry has a primary citation (PMID / DOI / stable URL).
- Allele frequencies are stated with population and source (e.g., PharmGKB).
- Magnitude statements use published AUC/Cmax ratios, not qualitative guesses.
- Individual dosing adjustments remain a clinician's decision — this module
  provides population-level reference data only.
- Stdlib-only; Python ≥3.8.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class PGxClinicalImpact(str, Enum):
    """Estimated clinical impact of the pharmacogenomic finding."""

    HIGH = "high"           # >2-fold change in exposure or documented toxicity/loss-of-effect
    MODERATE = "moderate"   # 1.5–2-fold change; clinically measurable
    LOW = "low"             # <1.5-fold change; usually subthreshold clinically
    UNKNOWN = "unknown"     # insufficient data


class PGxActionability(str, Enum):
    """How actionable the finding is for a prescriber."""

    DOSE_ADJUST = "dose_adjust"
    MONITOR = "monitor"
    AVOID = "avoid"
    INFORM_ONLY = "inform_only"


@dataclass(frozen=True)
class PGxCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class PGxRecord:
    """A single pharmacogenomic record for a CYP–cannabinoid interaction.

    All numeric values are ranges from published studies; state the study
    context in ``measurement_context``.
    """

    enzyme: str                      # e.g., "CYP2C9"
    allele_or_variant: str           # e.g., "CYP2C9*3", "CYP3A4 induction"
    allele_frequency: str            # population-specific, e.g., "6–7 % in Europeans"
    cannabinoid: str                 # e.g., "Δ⁹-THC", "CBD"
    direction: str                   # "increased exposure" | "decreased exposure" | "inhibitor"
    magnitude: str                   # published AUC/Cmax change or IC50, e.g., "AUC ~3-fold ↑"
    clinical_impact: PGxClinicalImpact
    actionability: PGxActionability
    measurement_context: str         # study type, population, limitations
    clinical_notes: str              # clinician-facing guidance
    citations: tuple[PGxCitation, ...]

    def to_dict(self) -> dict:
        return {
            "enzyme": self.enzyme,
            "allele_or_variant": self.allele_or_variant,
            "allele_frequency": self.allele_frequency,
            "cannabinoid": self.cannabinoid,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "clinical_impact": self.clinical_impact.value,
            "actionability": self.actionability.value,
            "measurement_context": self.measurement_context,
            "clinical_notes": self.clinical_notes,
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi,
                 "url": c.url, "year": c.year}
                for c in self.citations
            ],
        }

    def to_claim(self, *, source_tier: "SourceTier | None" = None) -> "Claim":
        """Render this PGx row as a typed :class:`cannavec.evidence.Claim`.

        Produces a ``DRUG_INTERACTION`` claim — pharmacogenomic variation
        is a host-side modifier of the same CYP-mediated interaction
        machinery as a co-administered drug, so the claim type is
        consistent with :mod:`cannavec.interactions`.

        Default ``source_tier`` is ``JOURNAL_RCT`` — the underlying
        primary literature is small PK cross-over studies, which the
        existing grading rules cap at Level C without pre-registration.

        Disclosures are passed as the full required set because the
        curator inclusion bar already validates substrate, modifier,
        CYP isoform, magnitude, and source.
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
        text = (
            f"{self.enzyme} ({self.allele_or_variant}) — "
            f"{self.cannabinoid} {self.direction}. "
            f"Magnitude: {self.magnitude} Clinical impact: "
            f"{self.clinical_impact.value}. Actionability: "
            f"{self.actionability.value}."
        )
        disclosures = required_disclosures(ClaimType.DRUG_INTERACTION)
        return Claim(
            text=text,
            claim_type=ClaimType.DRUG_INTERACTION,
            sources=sources,
            disclosures_present=disclosures,
        )


def build_claim(
    record: "PGxRecord",
    *,
    source_tier: "SourceTier | None" = None,
) -> "Claim":
    """Module-level helper mirroring :meth:`PGxRecord.to_claim`."""
    return record.to_claim(source_tier=source_tier)


# ── Registry ──────────────────────────────────────────────────────────
#
# Inclusion bar: published pharmacokinetic or pharmacogenomic study
# with quantitative exposure data or documented clinical significance.

_REGISTRY: tuple[PGxRecord, ...] = (
    PGxRecord(
        enzyme="CYP2C9",
        allele_or_variant="CYP2C9*3 (poor metaboliser)",
        allele_frequency="~6–7 % of Europeans; ~1 % of East Asians",
        cannabinoid="Δ⁹-THC",
        direction="increased exposure (reduced clearance)",
        magnitude=(
            "THC AUC ~2–3-fold higher in *3/*3 compared to *1/*1; "
            "11-OH-THC formation reduced. Psychomotor impairment "
            "significantly prolonged in poor metabolisers."
        ),
        clinical_impact=PGxClinicalImpact.HIGH,
        actionability=PGxActionability.MONITOR,
        measurement_context=(
            "Small cross-over PK studies in healthy volunteers. "
            "Largest data: Sachse-Seeboth 2009 (n=22 genotyped volunteers). "
            "Limited to single-dose inhaled THC; clinical implications "
            "with repeated dosing or oral route need further study."
        ),
        clinical_notes=(
            "Patients with CYP2C9*3/*3 genotype (poor metabolisers) may "
            "experience substantially stronger and longer-lasting impairment "
            "from the same inhaled or oral THC dose as *1/*1 (extensive "
            "metabolisers). CYP2C9 genotyping is not standard of care "
            "before cannabis prescribing but is relevant in high-dose "
            "medical cannabis protocols."
        ),
        citations=(
            PGxCitation(
                label="Sachse-Seeboth 2009 — CYP2C9 polymorphism and THC pharmacokinetics",
                doi="10.1038/clpt.2008.229",
                year=2009,
            ),
            PGxCitation(
                label="Stott 2013 — Cannabis pharmacokinetics review",
                doi="10.2217/fca.13.87",
                year=2013,
            ),
        ),
    ),
    PGxRecord(
        enzyme="CYP2C9",
        allele_or_variant="CYP2C9 — all phenotypes",
        allele_frequency="varies; *1 extensive ~65 % Europeans",
        cannabinoid="Δ⁹-THC",
        direction="primary metabolising enzyme",
        magnitude=(
            "CYP2C9 is the primary enzyme for conversion of Δ⁹-THC "
            "to 11-OH-THC. CYP3A4 is a secondary pathway, especially "
            "at higher THC concentrations."
        ),
        clinical_impact=PGxClinicalImpact.HIGH,
        actionability=PGxActionability.INFORM_ONLY,
        measurement_context=(
            "In vitro human liver microsome studies; recombinant enzyme "
            "studies. CYP2C9 contribution is concentration-dependent "
            "(major at therapeutic concentrations, CYP3A4 increasingly "
            "important at higher concentrations)."
        ),
        clinical_notes=(
            "Warfarin is also primarily metabolised by CYP2C9. "
            "Concurrent warfarin + THC use requires INR monitoring because "
            "competition for CYP2C9 can elevate warfarin exposure."
        ),
        citations=(
            PGxCitation(
                label="Stott 2013 — Cannabis pharmacokinetics review",
                doi="10.2217/fca.13.87",
                year=2013,
            ),
        ),
    ),
    PGxRecord(
        enzyme="CYP3A4",
        allele_or_variant="CYP3A4 — induction by rifampicin/carbamazepine/St John's wort",
        allele_frequency="not a genetic variant; drug-drug interaction via induction",
        cannabinoid="Δ⁹-THC and CBD",
        direction="decreased exposure (increased clearance)",
        magnitude=(
            "CYP3A4 inducers (rifampicin, carbamazepine, phenytoin, "
            "St John's wort) can increase THC and CBD clearance by "
            "≥50 % estimated from pharmacokinetic modelling; "
            "direct human trial data limited for this combination."
        ),
        clinical_impact=PGxClinicalImpact.MODERATE,
        actionability=PGxActionability.MONITOR,
        measurement_context=(
            "Inferred from known CYP3A4 induction magnitude with other "
            "substrates and cannabis pharmacokinetic pathway share. "
            "Direct human data for THC + strong CYP3A4 inducer are sparse."
        ),
        clinical_notes=(
            "Patients on enzyme-inducing antiepileptic drugs "
            "(carbamazepine, phenytoin, phenobarbital) may require higher "
            "cannabinoid doses to achieve the same plasma exposure. "
            "Conversely, stopping an inducer may cause cannabinoid toxicity "
            "at previously tolerated doses."
        ),
        citations=(
            PGxCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    PGxRecord(
        enzyme="CYP3A4",
        allele_or_variant="CYP3A4 — inhibition by ketoconazole/clarithromycin/grapefruit",
        allele_frequency="not a genetic variant; drug-drug interaction via inhibition",
        cannabinoid="Δ⁹-THC and CBD",
        direction="increased exposure (reduced clearance)",
        magnitude=(
            "Strong CYP3A4 inhibitors can increase AUC of CYP3A4 substrates "
            "by 5–20-fold in general. For THC/CBD specifically, magnitude is "
            "estimated moderate–high; controlled human data limited."
        ),
        clinical_impact=PGxClinicalImpact.MODERATE,
        actionability=PGxActionability.MONITOR,
        measurement_context=(
            "Extrapolated from CYP3A4 inhibitor mechanism; "
            "cannabis-specific data very limited. "
            "Ketoconazole + THC interaction is documented in animal models."
        ),
        clinical_notes=(
            "Strong CYP3A4 inhibitors (azole antifungals, macrolide antibiotics, "
            "HIV protease inhibitors) may substantially elevate THC and CBD "
            "plasma levels. Counsel patients accordingly; reduce dose "
            "empirically if adverse effects emerge."
        ),
        citations=(
            PGxCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    PGxRecord(
        enzyme="CYP2C19",
        allele_or_variant="CYP2C19 — inhibition by CBD",
        allele_frequency="relevant to all CYP2C19 substrate users regardless of genotype",
        cannabinoid="CBD",
        direction="inhibitor (CBD inhibits CYP2C19)",
        magnitude=(
            "CBD IC50 for CYP2C19 inhibition: ~2 µM in human liver microsomes "
            "(Stout 2012). At therapeutic CBD doses (≥5 mg/kg/day in Epidiolex "
            "trials), clinically significant CYP2C19 inhibition is expected."
        ),
        clinical_impact=PGxClinicalImpact.HIGH,
        actionability=PGxActionability.MONITOR,
        measurement_context=(
            "In vitro HLM studies (Stout 2012). Clinical evidence from "
            "Epidiolex trials showing N-desmethylclobazam (a CYP2C19 substrate) "
            "AUC increased ~3-fold with concurrent high-dose CBD. "
            "This is the most clinically documented cannabinoid PGx interaction."
        ),
        clinical_notes=(
            "CBD substantially inhibits CYP2C19. Key substrates affected: "
            "clobazam (→ elevated active metabolite N-desmethylclobazam, "
            "causing somnolence), omeprazole, escitalopram, clopidogrel "
            "(→ reduced antiplatelet effect). "
            "The clobazam interaction is well-documented and requires "
            "proactive dose reduction of clobazam when initiating Epidiolex."
        ),
        citations=(
            PGxCitation(
                label="Stout 2012 — CBD CYP inhibition in vitro (Drug Metabolism Letters)",
                doi="10.2174/187231212800229578",
                year=2012,
            ),
            PGxCitation(
                label="Devinsky 2017 — CBD in Dravet (NEJM) — clobazam interaction reported",
                pmid="28538134",
                year=2017,
            ),
        ),
    ),
    PGxRecord(
        enzyme="CYP2C19",
        allele_or_variant="CYP2C19*2 and *3 (poor metaboliser alleles)",
        allele_frequency=(
            "CYP2C19*2: ~15 % of Europeans, ~30 % of East Asians; "
            "CYP2C19*3: ~5 % of East Asians, <1 % of Europeans"
        ),
        cannabinoid="CBD (via CYP2C19 inhibition cascade)",
        direction="additive risk — poor metabolisers accumulate CYP2C19 substrates faster",
        magnitude=(
            "A CBD-treated poor metaboliser of CYP2C19 accumulates clobazam's "
            "active metabolite faster (reduced baseline clearance) AND "
            "CBD further inhibits CYP2C19. Compounding effect."
        ),
        clinical_impact=PGxClinicalImpact.HIGH,
        actionability=PGxActionability.MONITOR,
        measurement_context=(
            "Pharmacokinetic modelling; no prospective PGx trial. "
            "Clinical concern based on known pharmacology."
        ),
        clinical_notes=(
            "East Asian patients on clobazam + CBD may be at elevated risk "
            "of somnolence due to higher CYP2C19*3 frequency compounding "
            "CBD-driven CYP2C19 inhibition. CYP2C19 genotyping may be "
            "informative in cases of unexpected sedation."
        ),
        citations=(
            PGxCitation(
                label="Stout 2012 — CBD CYP inhibition in vitro",
                doi="10.2174/187231212800229578",
                year=2012,
            ),
        ),
    ),
    PGxRecord(
        enzyme="CYP1A2",
        allele_or_variant="CYP1A2 — induction by inhaled cannabis smoke",
        allele_frequency="effect applies to all smokers regardless of genotype",
        cannabinoid="cannabis smoke (polycyclic aromatic hydrocarbons, not cannabinoids per se)",
        direction="CYP1A2 induction by combustion products",
        magnitude=(
            "Regular cannabis smoking increases CYP1A2 activity by "
            "~25–40 % (estimated from similar PAH exposure in tobacco smoking studies). "
            "Cannabis-specific human CYP1A2 induction data sparse."
        ),
        clinical_impact=PGxClinicalImpact.LOW,
        actionability=PGxActionability.INFORM_ONLY,
        measurement_context=(
            "Mechanism inferred from PAH chemistry (same combustion products "
            "as tobacco). Direct human cannabis-smoking CYP1A2 induction "
            "studies are limited."
        ),
        clinical_notes=(
            "Relevant for CYP1A2 substrates with narrow therapeutic index "
            "(clozapine, olanzapine, theophylline). Cannabis smoking cessation "
            "may increase clozapine/olanzapine levels — monitor for toxicity. "
            "Not relevant for non-combusted routes (vaporisation, oral, "
            "sublingual)."
        ),
        citations=(
            PGxCitation(
                label="Hajos 2014 — Cannabis and drug interactions (Curr Psychiatry Rep)",
                doi="10.1007/s11920-014-0524-4",
                year=2014,
            ),
        ),
    ),
    PGxRecord(
        enzyme="UGT1A9 / UGT2B7",
        allele_or_variant="CBD glucuronidation — phase II pathway",
        allele_frequency="UGT polymorphisms common but clinical cannabis impact understudied",
        cannabinoid="CBD",
        direction="CBD is a UGT1A9 substrate and inhibitor",
        magnitude=(
            "CBD inhibits UGT1A9 in vitro (IC50 ~3–6 µM). "
            "Relevance to clinical drug interactions with UGT substrates "
            "(e.g., mycophenolate, zidovudine) is plausible but unquantified "
            "in humans."
        ),
        clinical_impact=PGxClinicalImpact.UNKNOWN,
        actionability=PGxActionability.INFORM_ONLY,
        measurement_context=(
            "In vitro HLM data only. No clinical PK study in humans "
            "on CBD + UGT substrate co-administration."
        ),
        clinical_notes=(
            "The tacrolimus + CBD interaction may involve UGT inhibition "
            "in addition to CYP3A4. Monitor tacrolimus trough levels "
            "when initiating or stopping CBD in transplant patients."
        ),
        citations=(
            PGxCitation(
                label="Stout 2012 — CBD CYP/UGT inhibition in vitro",
                doi="10.2174/187231212800229578",
                year=2012,
            ),
        ),
    ),
)


def all_pgx_records() -> tuple[PGxRecord, ...]:
    """Return the full pharmacogenomics registry (read-only)."""
    return _REGISTRY


def find_by_enzyme(enzyme: str) -> list[PGxRecord]:
    """Return records involving a named CYP or UGT enzyme (case-insensitive)."""
    lower = enzyme.lower()
    return [r for r in _REGISTRY if lower in r.enzyme.lower()]


def find_by_cannabinoid(cannabinoid: str) -> list[PGxRecord]:
    """Return records relevant to a named cannabinoid (case-insensitive)."""
    lower = cannabinoid.lower()
    return [r for r in _REGISTRY if lower in r.cannabinoid.lower()]


def find_high_impact() -> list[PGxRecord]:
    """Return records classified HIGH clinical impact."""
    return [r for r in _REGISTRY if r.clinical_impact == PGxClinicalImpact.HIGH]


_PGX_MENTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "cyp2c9": re.compile(r"\bcyp2c9\b|\b2c9\b|\bp11712\b", re.IGNORECASE),
    "cyp2c19": re.compile(r"\bcyp2c19\b|\b2c19\b", re.IGNORECASE),
    "cyp3a4": re.compile(r"\bcyp3a4\b|\b3a4\b", re.IGNORECASE),
    "cyp1a2": re.compile(r"\bcyp1a2\b|\b1a2\b", re.IGNORECASE),
    "polymorphism": re.compile(
        r"\bpolymorphism\b|\ballele\b|\bpoor metaboli[sz]er\b|\bextensive metaboli[sz]er\b"
        r"|\bpharmacokinetic variation\b",
        re.IGNORECASE,
    ),
}


def detect_pgx_mention(text: str) -> list[str]:
    """Return enzyme/topic names mentioned in ``text``."""
    return [name for name, pattern in _PGX_MENTION_PATTERNS.items() if pattern.search(text)]


def find_pgx_hits(text: str) -> list[PGxRecord]:
    """Return registry rows whose enzyme is mentioned in ``text``.

    Bridges :func:`detect_pgx_mention` (which returns enzyme/topic
    *strings*) to the row-level objects ``compose_answer`` needs to walk
    citations and produce typed claims. Falls back to all rows when the
    prompt names a class-level keyword (``polymorphism``,
    ``pharmacogenomic``, ``pharmacogenetics``) but no specific enzyme —
    so generic PGx questions surface the full registry rather than
    nothing.
    """
    enzymes = detect_pgx_mention(text)
    rows: list[PGxRecord] = []
    seen: set[tuple[str, str]] = set()
    for r in _REGISTRY:
        for enz in enzymes:
            if enz.lower() in r.enzyme.lower() or enz.lower() in r.allele_or_variant.lower():
                key = (r.enzyme, r.allele_or_variant)
                if key not in seen:
                    seen.add(key)
                    rows.append(r)
                break
    if rows:
        return rows
    # Class-level fallback: did the prompt name "polymorphism" /
    # "pharmacogenomic" without a specific enzyme? Return the full
    # registry so the answer pipeline can render a meaningful section.
    if any(kw in text.lower() for kw in (
        "polymorphism", "pharmacogenomic", "pharmacogenetic",
        "poor metaboliser", "poor metabolizer",
        "extensive metaboliser", "extensive metabolizer",
        "ultra-rapid metaboliser", "ultra-rapid metabolizer",
        "cyp variant", "cyp variants", "metaboliser status",
        "metabolizer status",
    )):
        return list(_REGISTRY)
    return []


def format_for_clinician(records: Iterable[PGxRecord]) -> str:
    """Render a Markdown clinician-facing pharmacogenomics summary."""
    items = list(records)
    if not items:
        return (
            "_No pharmacogenomic records matched. "
            "Only well-documented CYP interactions with cannabinoids are registered._"
        )
    out: list[str] = []
    for r in items:
        out.append(f"### {r.enzyme} — {r.allele_or_variant}")
        out.append("")
        out.append(f"- **Cannabinoid:** {r.cannabinoid}")
        out.append(f"- **Effect direction:** {r.direction}")
        out.append(f"- **Magnitude:** {r.magnitude}")
        out.append(f"- **Clinical impact:** {r.clinical_impact.value}")
        out.append(f"- **Actionability:** {r.actionability.value}")
        out.append(f"- **Allele frequency:** {r.allele_frequency}")
        out.append(f"- **Measurement context:** {r.measurement_context}")
        out.append(f"- **Clinical notes:** {r.clinical_notes}")
        if r.citations:
            cites = "; ".join(
                f"PMID {c.pmid}" if c.pmid else f"doi:{c.doi}" if c.doi else c.label
                for c in r.citations
            )
            out.append(f"- **Citations:** {cites}")
        out.append("")
    return "\n".join(out)
