"""Clinical-pharmacokinetics registry (spec 005 US1 / FR-001).

Research-grade clinical pharmacokinetics of cannabis cannabinoids —
the topics a working clinical-pharmacology PI, formulation scientist,
or clinical-trial protocol author asks about. v0.4 silently returned
zero claims for every PK question; v0.5 ships a curated registry under
Constitution §IV (researcher-only) with primary citations per §I.

Topic coverage:

- ``inhaled_pk`` — Δ⁹-THC pharmacokinetics by inhaled route (smoked +
  vaped). Huestis 2005 (PMID 16596792) is the canonical reference for
  rapid-onset PK; vaped data from Spindle 2018 (PMID 30646391).
- ``oral_pk`` — Δ⁹-THC pharmacokinetics by oral route. Wall 1983
  (PMID 6309462) is the classic study; modern dronabinol PK is
  consistent.
- ``food_effect`` — CBD oral PK food effect. Birnbaum 2019 (PMID
  31247132) showed a 4-5 fold AUC increase with high-fat meal, which
  is now the FDA-recognised Epidiolex food-effect label.
- ``active_metabolite`` — 11-OH-Δ⁹-THC active-metabolite PK. Wall
  1983 (PMID 6309462) established the equimolar-after-oral vs
  ~10%-after-inhaled AUC ratio — the first-pass-effect explanation
  for why edibles produce a different subjective profile from
  smoked cannabis.
- ``oromucosal_pk`` — nabiximols (Sativex) oromucosal PK. Karschner
  2011 (PMID 21078841) for the absorption profile.
- ``distribution`` — plasma protein binding (~95-99%, dominated by
  lipoprotein-association rather than albumin), lipid sequestration in
  adipose tissue (long terminal half-life from slow release), and
  brain partitioning. Garrett & Hunt 1977 (PMID 845807) is the classic
  distribution reference.
- ``detection_window`` — urine cannabinoid detection window. THC-COOH
  metabolite detectable for days-to-weeks after cessation depending on
  chronicity of use; Huestis 1996 (PMID 1320536) is the classic
  controlled-dose reference.

Every row carries a `to_claim()` returning a typed
:class:`cannavec_science.evidence.Claim` for the composer's claim list,
with neutral-descriptive wording (no GRADE-vs-wording inflation) and
the required disclosures for the row's claim type.

The module is reference-only — no live discovery, no live drug-bank
lookup. Each entry is hand-curated against the primary literature.
Identifier discipline (PMID or DOI per §I) is enforced at construction
time. Cannabinoid isomer naming discipline per §VI is enforced by
unit test (Δ⁹-THC, 11-OH-Δ⁹-THC, CBD spelled correctly throughout).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from cannavec_science.evidence import (
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
    required_disclosures,
)


__all__ = [
    "PharmacokineticsCitation",
    "PharmacokineticsRow",
    "PharmacokineticsTopic",
    "all_pharmacokinetics_rows",
    "find_pharmacokinetics_rows",
    "detect_pharmacokinetics_mention",
    "render_markdown",
]


class PharmacokineticsTopic:
    INHALED_PK = "inhaled_pk"
    ORAL_PK = "oral_pk"
    FOOD_EFFECT = "food_effect"
    ACTIVE_METABOLITE = "active_metabolite"
    OROMUCOSAL_PK = "oromucosal_pk"
    DISTRIBUTION = "distribution"
    DETECTION_WINDOW = "detection_window"


@dataclass(frozen=True)
class PharmacokineticsCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class PharmacokineticsRow:
    """One curated clinical-pharmacokinetics primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[PharmacokineticsCitation, ...]
    route: str = ""          # smoked / vaped / oral / oromucosal / IV
    matrix: str = ""         # plasma / urine / saliva / hair / breath
    key_pk_params: tuple[str, ...] = ()  # Tmax=..., Cmax=..., t½=...
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Constitution §I — every row carries at least one primary identifier.
        if not self.citations:
            raise ValueError(
                f"pharmacokinetics row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"pharmacokinetics row {self.name!r} citation "
                    f"{c.label!r} must have a PMID or DOI"
                )
        if not self.watch_pmids:
            object.__setattr__(
                self,
                "watch_pmids",
                tuple(c.pmid for c in self.citations if c.pmid),
            )

    def to_claim(self) -> Claim:
        sources = tuple(
            Source(
                title=c.label,
                tier=self.source_tier,
                pmid=c.pmid,
                doi=c.doi,
                year=c.year,
            )
            for c in self.citations
        )
        return Claim(
            text=self.claim_text,
            claim_type=self.claim_type,
            sources=sources,
            disclosures_present=required_disclosures(self.claim_type),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "topic": self.topic,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type.value,
            "evidence_level": self.evidence_level.value,
            "source_tier": int(self.source_tier),
            "route": self.route,
            "matrix": self.matrix,
            "key_pk_params": list(self.key_pk_params),
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_notes": list(self.key_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_HUESTIS_2005 = PharmacokineticsCitation(
    label="Huestis MA, Handb Exp Pharmacol 2005, human cannabinoid pharmacokinetics "
          "(canonical PK review)",
    pmid="16596792", year=2005,
)
_HUESTIS_1992 = PharmacokineticsCitation(
    label="Huestis MA et al., J Anal Toxicol 1992, blood cannabinoids I — "
          "absorption of THC and formation of 11-OH-THC and THC-COOH during "
          "and after smoking marijuana",
    pmid="1338215", year=1992,
)
_WALL_1983 = PharmacokineticsCitation(
    label="Wall ME et al., Clin Pharmacol Ther 1983, metabolism, "
          "disposition, and kinetics of Δ⁹-tetrahydrocannabinol in men and "
          "women",
    pmid="6309462", year=1983,
)
_SPINDLE_2018 = PharmacokineticsCitation(
    label="Spindle TR et al., JAMA Netw Open 2018, acute effects of smoked "
          "and vaporized cannabis in healthy adults who infrequently use "
          "cannabis",
    pmid="30646391", year=2018,
)
_BIRNBAUM_2019 = PharmacokineticsCitation(
    label="Birnbaum AK et al., Epilepsia 2019, food effect on cannabidiol "
          "(CBD) oral pharmacokinetics — high-fat meal increases CBD AUC "
          "approximately 4-5 fold (Epidiolex label-supporting data)",
    pmid="31247132", year=2019,
)
_KARSCHNER_2011 = PharmacokineticsCitation(
    label="Karschner EL et al., Clin Chem 2011, pharmacokinetics of "
          "Δ⁹-tetrahydrocannabinol after oromucosal Sativex administration",
    pmid="21078841", year=2011,
)
_GARRETT_1977 = PharmacokineticsCitation(
    label="Garrett ER & Hunt CA, J Pharm Sci 1977, pharmacokinetics of "
          "Δ⁹-THC in dogs",
    pmid="845807", year=1977,
)
_HUESTIS_1996 = PharmacokineticsCitation(
    label="Huestis MA et al., J Anal Toxicol 1996, characterization of the "
          "absorption phase of marijuana smoking — urine cannabinoid "
          "detection window",
    pmid="1320536", year=1996,
)
_DEVINSKY_2018_LGS = PharmacokineticsCitation(
    label="Devinsky O et al., NEJM 2018, effect of cannabidiol on drop "
          "seizures in Lennox-Gastaut syndrome — PK section (Epidiolex 10-20 "
          "mg/kg/day oral)",
    pmid="29768152", year=2018,
)


# ── Registry rows ──────────────────────────────────────────────────────

_INHALED_PK_SMOKED = PharmacokineticsRow(
    name="Δ⁹-THC inhaled (smoked) pharmacokinetics",
    topic=PharmacokineticsTopic.INHALED_PK,
    claim_text=(
        "Smoked Δ⁹-THC reaches plasma Cmax within ~3-10 minutes of the "
        "first inhalation, with Tmax typically 6-10 minutes. Bioavailability "
        "is highly user- and device-dependent, reported as ~10-35% (with "
        "experienced users at the upper end of the range due to inhalation-"
        "technique efficiency). Terminal plasma half-life is ~20-30 hours "
        "in occasional users and longer (often 4-5 days) in chronic users "
        "due to slow redistribution from adipose tissue. Smoked Δ⁹-THC "
        "produces a low 11-OH-Δ⁹-THC : Δ⁹-THC AUC ratio (~5-15%) compared "
        "to the oral route (see active_metabolite row)."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    route="smoked (combusted flower or extract)",
    matrix="plasma (whole blood when distinguished)",
    key_pk_params=(
        "Tmax ≈ 6-10 min",
        "Cmax ≈ 50-270 ng/mL depending on dose / device / experience",
        "Bioavailability ≈ 10-35%",
        "Terminal t½ ≈ 20-30 h (occasional) up to ~4-5 d (chronic)",
    ),
    citations=(_HUESTIS_2005, _HUESTIS_1992),
    key_notes=(
        "Inter-subject variability is substantial — inhalation technique, "
        "pull volume, breath-hold duration, and device combustion "
        "temperature all alter delivered dose. Controlled-dose research "
        "studies use standardised puff procedures (e.g. the Foltin puff "
        "procedure) to reduce this.",
        "Whole-blood vs plasma matrix matters in DUI contexts — whole-"
        "blood THC concentrations are roughly half plasma concentrations "
        "because THC partitions away from red cells.",
    ),
)


_INHALED_PK_VAPED = PharmacokineticsRow(
    name="Δ⁹-THC inhaled (vaporized) pharmacokinetics",
    topic=PharmacokineticsTopic.INHALED_PK,
    claim_text=(
        "Vaporized Δ⁹-THC produces a similar PK profile to smoked Δ⁹-THC "
        "in terms of Tmax (5-15 min) and Cmax magnitude per delivered dose. "
        "Spindle 2018 (controlled-dose crossover in infrequent users) found "
        "vaporized cannabis produced higher plasma Δ⁹-THC concentrations "
        "and stronger subjective drug effects than smoked cannabis at the "
        "same nominal Δ⁹-THC dose — attributed to higher delivery efficiency "
        "(less pyrolytic loss). The combustion vs vaporization comparison "
        "is the only route-comparison study with controlled cannabinoid-"
        "content flower at multiple doses."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    route="vaporized (device-mediated)",
    matrix="plasma",
    key_pk_params=(
        "Tmax ≈ 5-15 min",
        "Cmax substantially higher than smoked at matched dose (Spindle 2018)",
        "Bioavailability not directly measured in route-comparison studies",
    ),
    citations=(_SPINDLE_2018, _HUESTIS_2005),
    key_notes=(
        "Spindle 2018 used a Volcano vaporizer at 200 °C — different "
        "vape devices, temperatures, and cartridge formulations alter "
        "the delivered cannabinoid dose substantially.",
        "Vaporization reduces (but does not eliminate) pyrolysis "
        "byproducts vs combustion — see analytical_chemistry "
        "pyrolysis row.",
    ),
)


_ORAL_PK = PharmacokineticsRow(
    name="Δ⁹-THC oral (dronabinol) pharmacokinetics",
    topic=PharmacokineticsTopic.ORAL_PK,
    claim_text=(
        "Oral Δ⁹-THC (dronabinol, sesame-oil capsule) has low and erratic "
        "absolute bioavailability (~6-20%) due to extensive first-pass "
        "hepatic metabolism by CYP2C9 / CYP3A4. Tmax is delayed to "
        "~1-3 hours post-dose and Cmax is much lower than inhaled at "
        "matched nominal dose. The oral route produces approximately "
        "equimolar 11-OH-Δ⁹-THC AUC to parent Δ⁹-THC AUC (see "
        "active_metabolite row) because of the obligate first-pass "
        "metabolism — this is the pharmacological basis of the "
        "edibles-feel-different-from-smoked subjective profile."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    route="oral (gelatin capsule in sesame oil; dronabinol)",
    matrix="plasma",
    key_pk_params=(
        "Tmax ≈ 1-3 h",
        "Cmax substantially lower than inhaled at matched dose",
        "Bioavailability ≈ 6-20%",
        "Terminal t½ ≈ 20-30 h (similar to inhaled)",
    ),
    citations=(_WALL_1983, _HUESTIS_2005),
    key_notes=(
        "Oral Δ⁹-THC bioavailability is depressed further in fasted "
        "state (food increases absorption of the lipophilic molecule).",
        "Dronabinol PK is a useful reference for edibles PK but the "
        "matrix (sesame oil vs gummy / chocolate / lipid extract) "
        "and meal context shift absorption substantially.",
    ),
)


_CBD_FOOD_EFFECT = PharmacokineticsRow(
    name="Cannabidiol (CBD) oral food effect (Epidiolex)",
    topic=PharmacokineticsTopic.FOOD_EFFECT,
    claim_text=(
        "Oral CBD (Epidiolex 750 mg single dose, healthy adults, crossover) "
        "exhibits a 4-5 fold increase in plasma AUC and ~5-fold increase "
        "in Cmax when administered with a high-fat / high-calorie meal "
        "compared to fasted state (Birnbaum 2019). This food effect is "
        "now the FDA-recognised Epidiolex label-supporting data and "
        "explains substantial intra-subject variability in clinical PK "
        "if dosing time relative to meals is not controlled."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    route="oral (Epidiolex 100 mg/mL solution)",
    matrix="plasma",
    key_pk_params=(
        "Fed/fasted AUC ratio ≈ 4-5×",
        "Fed/fasted Cmax ratio ≈ 5×",
        "Tmax delayed by ~1-2 h in fed state",
    ),
    citations=(_BIRNBAUM_2019, _DEVINSKY_2018_LGS),
    key_notes=(
        "The high-fat meal effect is mechanistically explained by "
        "improved lipid solubilisation of the highly lipophilic CBD "
        "molecule (logP ≈ 6.3) and slower gastric emptying.",
        "Clinical implication: Epidiolex dose should be administered "
        "consistently with respect to meals to reduce inter-dose "
        "variability — the SmPC explicitly notes the food effect.",
    ),
)


_ACTIVE_METABOLITE = PharmacokineticsRow(
    name="11-OH-Δ⁹-THC active metabolite PK and oral/inhaled AUC ratio",
    topic=PharmacokineticsTopic.ACTIVE_METABOLITE,
    claim_text=(
        "11-OH-Δ⁹-THC is the major active phase-1 metabolite of Δ⁹-THC, "
        "produced by CYP2C9 (predominant) and CYP3A4 (minor). 11-OH-Δ⁹-THC "
        "is itself a CB1 partial agonist with potency comparable to the "
        "parent. The oral route produces approximately equimolar 11-OH-"
        "Δ⁹-THC : Δ⁹-THC AUC because of obligate first-pass hepatic "
        "metabolism, whereas the inhaled route produces 11-OH-Δ⁹-THC at "
        "only ~5-15% of parent AUC (it forms after systemic distribution "
        "and re-exposure to hepatic enzymes). The first-pass effect on "
        "the oral route is the pharmacological basis of why edibles "
        "produce a longer-lasting and qualitatively different subjective "
        "profile than smoked / vaped cannabis at the same nominal Δ⁹-THC "
        "dose. The downstream metabolite 11-COOH-Δ⁹-THC (THC-COOH) is "
        "inactive but is the analyte detected in urine drug-screening."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    route="oral vs inhaled (comparison)",
    matrix="plasma (parent + metabolite)",
    key_pk_params=(
        "Oral 11-OH-Δ⁹-THC : Δ⁹-THC AUC ratio ≈ 1.0 (equimolar)",
        "Inhaled 11-OH-Δ⁹-THC : Δ⁹-THC AUC ratio ≈ 0.05-0.15",
        "11-OH-Δ⁹-THC plasma t½ similar to parent (~20-30 h)",
    ),
    citations=(_WALL_1983, _HUESTIS_2005, _HUESTIS_1992),
    key_notes=(
        "The CYP2C9 first-pass step means CYP2C9 poor metabolisers "
        "(CYP2C9*3 carriers) accumulate parent Δ⁹-THC and produce less "
        "11-OH-Δ⁹-THC after oral dosing — see pharmacogenomics registry "
        "for the CYP2C9 × Δ⁹-THC PGx entry.",
        "11-OH-Δ⁹-THC is the molecule the subjective-effects literature "
        "increasingly attributes the edibles-feel-different phenomenology "
        "to — not strictly the dose-route per se but the metabolite "
        "AUC contribution.",
    ),
)


_OROMUCOSAL_PK = PharmacokineticsRow(
    name="Nabiximols (Sativex) oromucosal pharmacokinetics",
    topic=PharmacokineticsTopic.OROMUCOSAL_PK,
    claim_text=(
        "Nabiximols (1:1 Δ⁹-THC:CBD oromucosal spray, 2.7 mg Δ⁹-THC + "
        "2.5 mg CBD per spray) exhibits intermediate PK between oral and "
        "inhaled routes. Tmax is delayed (median ~1.6-2.5 h for Δ⁹-THC) "
        "consistent with mucosal absorption followed by some swallowed-"
        "and-orally-absorbed component; Cmax is much lower than inhaled "
        "and only modestly higher than oral at matched dose. The 11-OH-"
        "Δ⁹-THC : Δ⁹-THC AUC ratio is intermediate (~0.3-0.5), consistent "
        "with partial bypass of hepatic first-pass via the mucosal route."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    route="oromucosal spray",
    matrix="plasma",
    key_pk_params=(
        "Tmax (Δ⁹-THC) ≈ 1.6-2.5 h",
        "Tmax (CBD) ≈ 2-3 h",
        "Cmax substantially lower than inhaled at matched cumulative dose",
        "11-OH-Δ⁹-THC : Δ⁹-THC AUC ratio ≈ 0.3-0.5",
    ),
    citations=(_KARSCHNER_2011, _HUESTIS_2005),
    key_notes=(
        "Spray-formulation PK is sensitive to the area of mucosal contact "
        "(under-tongue vs cheek) and saliva flow rate. Clinical guidance "
        "is to apply to alternating sites.",
        "The 1:1 Δ⁹-THC:CBD ratio in nabiximols is also a PD story — CBD "
        "is hypothesised to attenuate Δ⁹-THC psychotomimetic adverse "
        "effects, though the mechanism (PK vs PD) is debated.",
    ),
)


_DISTRIBUTION = PharmacokineticsRow(
    name="Cannabinoid plasma protein binding and adipose distribution",
    topic=PharmacokineticsTopic.DISTRIBUTION,
    claim_text=(
        "Δ⁹-THC is ~95-99% bound in plasma, dominated by lipoprotein-"
        "association (LDL / HDL fractions) rather than albumin (a "
        "distinct binding profile from most small-molecule drugs). The "
        "molecule is highly lipophilic (logP ≈ 6.97) and partitions "
        "rapidly into adipose tissue, where it accumulates with chronic "
        "use. Slow redistribution from adipose back into plasma is the "
        "mechanism behind the long terminal half-life (4-5 days in "
        "chronic users) and the prolonged urine detection window. "
        "Volume of distribution is large (~3-10 L/kg)."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    route="systemic (post-distribution)",
    matrix="plasma + adipose",
    key_pk_params=(
        "Plasma protein binding ≈ 95-99% (lipoprotein-dominant)",
        "logP (Δ⁹-THC) ≈ 6.97",
        "logP (CBD) ≈ 6.3",
        "Volume of distribution ≈ 3-10 L/kg",
        "Adipose:plasma partition coefficient strongly favours adipose",
    ),
    citations=(_GARRETT_1977, _HUESTIS_2005),
    key_notes=(
        "Lipoprotein-dominant binding means that lipid-lowering "
        "interventions, post-prandial state, and lipemic samples can "
        "alter free-fraction concentrations — a methodological caveat "
        "for any PK study reporting total plasma THC.",
        "Adipose sequestration explains why chronic-user PK profiles "
        "during cessation show prolonged low-level THC release for "
        "weeks — this is not ongoing exposure but redistribution.",
    ),
)


_DETECTION_WINDOW = PharmacokineticsRow(
    name="Urine cannabinoid detection window (11-COOH-THC, THC-COOH)",
    topic=PharmacokineticsTopic.DETECTION_WINDOW,
    claim_text=(
        "Urine cannabinoid screening detects 11-nor-9-carboxy-Δ⁹-THC "
        "(THC-COOH, the inactive phase-2 conjugate), not parent Δ⁹-THC. "
        "Detection window after last use depends primarily on chronicity: "
        "single-occasion use typically detects for ~2-7 days at the SAMHSA "
        "50 ng/mL screening cutoff; daily use detects for 10-30+ days "
        "after cessation due to slow adipose-tissue release. Huestis 1996 "
        "established the controlled-dose framework with sequential urine "
        "sampling — this is the citation modern detection-window "
        "guidance traces to. Single positive screens DO NOT establish "
        "recency of use because of the long detection window from adipose "
        "redistribution."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    route="post-systemic urinary excretion",
    matrix="urine",
    key_pk_params=(
        "Screening cutoff (SAMHSA) = 50 ng/mL THC-COOH",
        "Confirmatory cutoff (SAMHSA) = 15 ng/mL THC-COOH",
        "Single-use detection window ≈ 2-7 days",
        "Chronic-use detection window ≈ 10-30+ days post-cessation",
    ),
    citations=(_HUESTIS_1996, _HUESTIS_2005),
    key_notes=(
        "Creatinine normalisation (ng THC-COOH per mg creatinine) is "
        "standard for serial monitoring in cessation trials — raw "
        "concentrations vary with hydration.",
        "Hair and oral-fluid windows are different surfaces — hair "
        "detects months of use history; oral fluid detects hours-to-day "
        "windows. Urine is the long-window standard.",
    ),
)


_REGISTRY: tuple[PharmacokineticsRow, ...] = (
    _INHALED_PK_SMOKED,
    _INHALED_PK_VAPED,
    _ORAL_PK,
    _CBD_FOOD_EFFECT,
    _ACTIVE_METABOLITE,
    _OROMUCOSAL_PK,
    _DISTRIBUTION,
    _DETECTION_WINDOW,
)


# ── Topic-keyword detectors ────────────────────────────────────────────

_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        PharmacokineticsTopic.INHALED_PK,
        re.compile(
            r"\b("
            r"inhaled\s+(?:thc|cannabinoid|cannabis)|"
            r"smoked\s+(?:thc|cannabinoid|cannabis|marijuana)|"
            r"vaped\s+(?:thc|cannabinoid|cannabis)|"
            r"vapori[sz]ed\s+(?:thc|cannabinoid|cannabis)|"
            r"(?:thc|cannabinoid|cannabis)\s+inhaled|"
            r"(?:thc|cannabinoid|cannabis)\s+smoked|"
            r"(?:inhaled|smoked|vaped|vapori[sz]ed)\s+(?:vs|versus)|"
            r"spindle\s+2018|huestis\s+(?:2005|1992|2005a|2005b)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PharmacokineticsTopic.ORAL_PK,
        re.compile(
            r"\b("
            r"oral\s+(?:thc|delta[- ]?9[- ]?thc|dronabinol|cannabinoid)|"
            r"dronabinol\s+pharmacokinetic\w*|"
            r"(?:marinol|syndros)\s+(?:pk|pharmacokinetic\w*)|"
            r"(?:thc|delta[- ]?9[- ]?thc)\s+oral\s+(?:pk|bioavail\w*|absor\w*)|"
            r"oral\s+(?:bioavail\w*|absor\w*)\s+(?:thc|cannabis|cannabinoid)|"
            r"first[- ]?pass\s+(?:metabol\w*|effect)|"
            r"wall\s+1983"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PharmacokineticsTopic.FOOD_EFFECT,
        re.compile(
            r"\b("
            r"food\s+effect|"
            r"fed\s+(?:vs|versus)\s+fasted|fasted\s+(?:vs|versus)\s+fed|"
            r"high[- ]?fat\s+meal|"
            r"(?:cbd|epidiolex|cannabidiol).*?(?:food|meal|fed|fasted)|"
            r"birnbaum\s+2019|"
            r"epidiolex\s+(?:auc|food|meal)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PharmacokineticsTopic.ACTIVE_METABOLITE,
        re.compile(
            r"\b("
            r"11[- ]?(?:hydroxy|oh)[- ]?(?:thc|delta[- ]?9[- ]?thc)|"
            r"11[- ]?oh[- ]?thc|"
            r"active\s+metabolite\s+(?:of\s+)?(?:thc|cannabinoid)|"
            r"(?:thc|delta[- ]?9[- ]?thc)\s+(?:active\s+)?metabolite|"
            r"thc[- ]?cooh|11[- ]?(?:nor[- ]?)?(?:9[- ]?)?carboxy[- ]?thc"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PharmacokineticsTopic.OROMUCOSAL_PK,
        re.compile(
            r"\b("
            r"oromucosal|sublingual\s+(?:cannabinoid|thc|cbd)|"
            r"nabiximols\s+(?:pk|pharmacokinetic\w*|absor\w*)|"
            r"sativex\s+(?:pk|pharmacokinetic\w*|absor\w*)|"
            r"(?:sativex|nabiximols|mevatyl)\s+oromucosal|"
            r"karschner\s+2011"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PharmacokineticsTopic.DISTRIBUTION,
        re.compile(
            r"\b("
            r"plasma\s+protein\s+bind\w*|protein\s+bind\w*\s+(?:of\s+)?(?:thc|cannabinoid)|"
            r"adipose\s+(?:tissue|sequest\w*|distribut\w*)\s+(?:thc|cannabinoid)|"
            r"(?:thc|cannabinoid)\s+(?:adipose|fat)\s+(?:sequest\w*|distribut\w*)|"
            r"volume\s+of\s+distribution\s+(?:of\s+)?(?:thc|cannabinoid)|"
            r"(?:thc|cannabinoid)\s+log\s*p|"
            r"lipophilic\s+(?:thc|cannabinoid)|"
            r"garrett\s+1977"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PharmacokineticsTopic.DETECTION_WINDOW,
        re.compile(
            r"\b("
            r"urine\s+(?:detection|cannabinoid|drug[- ]?screen\w*|test\w*)|"
            r"(?:detection|drug[- ]?test\w*)\s+window\s+(?:cannabis|thc|cannabinoid)|"
            r"(?:cannabis|thc|cannabinoid)\s+(?:detection|drug[- ]?test\w*)\s+window|"
            r"thc[- ]?cooh\s+(?:cutoff|screen\w*|positive)|"
            r"samhsa\s+(?:50|15)\s+ng|"
            r"creatinine\s+normali[sz]ed\s+(?:thc|cannabinoid)|"
            r"huestis\s+1996"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    # Cross-topic Tmax / Cmax / half-life / bioavailability framings.
    (
        PharmacokineticsTopic.INHALED_PK,
        re.compile(
            r"\b("
            r"(?:thc|delta[- ]?9[- ]?thc|cannabis|cannabinoid).{0,40}"
            r"(?:tmax|cmax|t\s*1/2|half[- ]?life|bioavail\w*|auc)"
            r"|"
            r"(?:tmax|cmax|t\s*1/2|half[- ]?life|bioavail\w*|auc).{0,40}"
            r"(?:thc|delta[- ]?9[- ]?thc|cannabis|cannabinoid)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_pharmacokinetics_rows() -> tuple[PharmacokineticsRow, ...]:
    """Return every curated pharmacokinetics row."""
    return _REGISTRY


def find_pharmacokinetics_rows(
    topic_or_name: str,
) -> tuple[PharmacokineticsRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[PharmacokineticsRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_pharmacokinetics_mention(
    text: str,
) -> tuple[PharmacokineticsRow, ...]:
    """Return rows whose topic-keyword regex matches ``text``."""
    if not text:
        return ()
    matched_topics: set[str] = set()
    for topic, rx in _TOPIC_KEYWORDS:
        if rx.search(text):
            matched_topics.add(topic)
    if not matched_topics:
        return ()
    return tuple(r for r in _REGISTRY if r.topic in matched_topics)


# ── Renderer ───────────────────────────────────────────────────────────


_TOPIC_DISPLAY_NAMES = {
    PharmacokineticsTopic.INHALED_PK: "Inhaled-route PK (smoked + vaped)",
    PharmacokineticsTopic.ORAL_PK: "Oral-route PK (dronabinol / capsule)",
    PharmacokineticsTopic.FOOD_EFFECT: "CBD food effect (Epidiolex)",
    PharmacokineticsTopic.ACTIVE_METABOLITE: "Active metabolite (11-OH-Δ⁹-THC)",
    PharmacokineticsTopic.OROMUCOSAL_PK: "Oromucosal PK (nabiximols)",
    PharmacokineticsTopic.DISTRIBUTION: "Distribution + protein binding",
    PharmacokineticsTopic.DETECTION_WINDOW: "Urine detection window",
}


def render_markdown(rows: Iterable[PharmacokineticsRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[PharmacokineticsRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## Pharmacokinetics registry")
    lines.append("")
    for topic, display in _TOPIC_DISPLAY_NAMES.items():
        bucket = by_topic.get(topic)
        if not bucket:
            continue
        lines.append(f"### {display}")
        lines.append("")
        for r in bucket:
            lines.append(f"- **{r.name}** ({r.evidence_level.value})")
            lines.append(f"  - {r.claim_text}")
            if r.route:
                lines.append(f"  - Route: {r.route}")
            if r.matrix:
                lines.append(f"  - Matrix: {r.matrix}")
            for p in r.key_pk_params:
                lines.append(f"  - PK: {p}")
            for c in r.citations:
                ident = []
                if c.pmid:
                    ident.append(f"PMID {c.pmid}")
                if c.doi:
                    ident.append(f"doi:{c.doi}")
                lines.append(
                    f"  - Source: {c.label}"
                    + (f" — {' / '.join(ident)}" if ident else "")
                )
        lines.append("")
    return "\n".join(lines).rstrip()
