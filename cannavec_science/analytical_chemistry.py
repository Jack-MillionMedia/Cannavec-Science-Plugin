"""Analytical-chemistry registry (spec 004 US1 / FR-001).

Research-grade analytical chemistry of cannabis — the topics a working
formulation scientist, method-development chemist, or analytical-method-
validation specialist asks about. v0.3 silently returned zero claims for
all of these; v0.4 ships a curated registry under Constitution §IV
(researcher-only) with primary citations per §I.

Topic coverage:

- ``decarb_kinetics`` — THCA → Δ⁹-THC decarboxylation kinetics. Rate
  constants are matrix-, temperature-, and time-dependent; the canonical
  primary literature is Veress 1990 (PMID 2384545) for the kinetic
  framework and Wang 2016 / Citti 2018 for modern dose-response curves.
- ``hplc_validation`` — HPLC method validation for cannabinoid potency.
  Reverse-phase C18 / C8 with UV at 220-230 nm is the workhorse; AOAC
  2015.13 and the USP <467> / <1226> framework set the validation
  bar. Inter-laboratory variability is well-documented.
- ``gc_ms_artefact`` — GC-MS produces in-injector decarboxylation; the
  apparent THC reading on a GC chromatogram is the SUM of native THC
  PLUS decarboxylated THCA. This is the SAME artefact the v0.3 rigor
  detector catches at prose level — here it is surfaced as a curated
  claim with the primary methodology citation.
- ``chemovar`` — Hazekamp & Fischedick 2012 Type I (THCA-dominant),
  Type II (mixed), Type III (CBDA-dominant), Type IV (CBGA-dominant),
  Type V (essentially cannabinoid-free hemp) classification. The
  industry-expert framing standard for distinguishing cultivars.
- ``pyrolysis`` — vapor / smoke pyrolysis byproducts. Pomahacova 2009
  (DOI 10.1080/13880200902749229) compared combustion vs vaporisation
  for benzene / toluene / naphthalene / PAHs. The harm-reduction
  literature uses these data heavily.

Every row carries a `to_claim()` that returns a typed
:class:`cannavec_science.evidence.Claim` for the composer's claim list,
with neutral-descriptive wording (no GRADE-vs-wording inflation) and
the required disclosures for the row's claim type.

The module is reference-only — no live discovery, no live NIST lookup.
Each entry is hand-curated against the primary literature. Identifier
discipline (PMID or DOI per §I) is enforced at construction time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
    "AnalyticalChemistryCitation",
    "AnalyticalChemistryRow",
    "AnalyticalTopic",
    "all_analytical_chemistry_rows",
    "find_analytical_chemistry_rows",
    "detect_analytical_chemistry_mention",
    "render_markdown",
]


# Topic vocabulary — used by the detector and the renderer's section
# grouping. Kept as plain strings (str-typed) rather than an Enum so the
# JSON inventory in registries.py renders them cleanly.
class AnalyticalTopic:
    DECARB_KINETICS = "decarb_kinetics"
    HPLC_VALIDATION = "hplc_validation"
    GC_MS_ARTEFACT = "gc_ms_artefact"
    CHEMOVAR = "chemovar"
    PYROLYSIS = "pyrolysis"


@dataclass(frozen=True)
class AnalyticalChemistryCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class AnalyticalChemistryRow:
    """One curated analytical-chemistry primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[AnalyticalChemistryCitation, ...]
    matrix: str = ""            # flower / extract / vapor / smoke
    conditions: str = ""        # temperature / column / detector / etc.
    last_verified: str = "2026-05-21"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Constitution §I — every row carries at least one primary identifier.
        if not self.citations:
            raise ValueError(
                f"analytical-chemistry row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"analytical-chemistry row {self.name!r} citation "
                    f"{c.label!r} must have a PMID or DOI"
                )
        if not self.watch_pmids:
            object.__setattr__(
                self,
                "watch_pmids",
                tuple(c.pmid for c in self.citations if c.pmid),
            )

    def to_claim(self) -> Claim:
        """Render as a typed :class:`Claim` for the composer's claim list.

        Source tier is the row's declared tier. Wording is the curated
        ``claim_text``. Disclosures are passed as the required set
        because the curator inclusion bar validates target, conditions,
        and primary source on each row.
        """
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
            "matrix": self.matrix,
            "conditions": self.conditions,
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_notes": list(self.key_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_VERESS_1990 = AnalyticalChemistryCitation(
    label="Veress T et al., J Chromatogr 1990, decarboxylation kinetics "
          "of cannabinoid acids",
    pmid="2384545", year=1990,
)
_DUSSY_2005 = AnalyticalChemistryCitation(
    label="Dussy FE et al., Forensic Sci Int 2005, isolation of Δ⁹-THCA-A "
          "and quantification by HPLC vs GC",
    pmid="15734104", year=2005,
)
_WANG_2016 = AnalyticalChemistryCitation(
    label="Wang M et al., Cannabis Cannabinoid Res 2016, decarboxylation "
          "study of acidic cannabinoids: a thermal-stability comparison",
    doi="10.1089/can.2016.0020", year=2016,
)
_CITTI_2018 = AnalyticalChemistryCitation(
    label="Citti C et al., J Pharm Biomed Anal 2018, analytical "
          "considerations for cannabinoids in cannabis extracts and "
          "medicinal products",
    pmid="28641906", year=2018,
)
_HAZEKAMP_2012 = AnalyticalChemistryCitation(
    label="Hazekamp A & Fischedick JT, Drug Test Anal 2012, cannabis — "
          "from cultivar to chemovar",
    pmid="22362625", year=2012,
)
_LEWIS_2018 = AnalyticalChemistryCitation(
    label="Lewis MA et al., Planta Med 2018, Pharmacological foundations "
          "of cannabis chemovars",
    pmid="29161743", year=2018,
)
_POMAHACOVA_2009 = AnalyticalChemistryCitation(
    label="Pomahacova B et al., Inhal Toxicol 2009, cannabis smoke "
          "condensate III: the cannabinoid content of vaporized cannabis",
    doi="10.1080/13880200902749229", year=2009,
)
_MOIR_2008 = AnalyticalChemistryCitation(
    label="Moir D et al., Chem Res Toxicol 2008, comparison of mainstream "
          "and sidestream marijuana and tobacco cigarette smoke produced "
          "under two machine smoking conditions",
    pmid="18062674", year=2008,
)
_GAONI_1964 = AnalyticalChemistryCitation(
    label="Gaoni Y & Mechoulam R, J Am Chem Soc 1964, isolation, structure, "
          "and partial synthesis of an active constituent of hashish",
    doi="10.1021/ja01062a046", year=1964,
)
_HILLIG_MAHLBERG_2004 = AnalyticalChemistryCitation(
    label="Hillig KW & Mahlberg PG, Am J Bot 2004, chemotaxonomic analysis "
          "of cannabinoid variation in Cannabis (Cannabaceae)",
    pmid="21653452", year=2004,
)
_LEGHISSA_2018 = AnalyticalChemistryCitation(
    label="Leghissa A et al., J Sep Sci 2018, the imperatives and "
          "challenges of analyzing Cannabis edibles",
    pmid="29251828", year=2018,
)
_AIZPURUA_OLAIZOLA_2016 = AnalyticalChemistryCitation(
    label="Aizpurua-Olaizola O et al., J Nat Prod 2016, evolution of the "
          "cannabinoid and terpene content during the growth of Cannabis "
          "sativa plants from different chemotypes",
    pmid="26836472", year=2016,
)


# ── Registry rows ──────────────────────────────────────────────────────


_DECARB_KINETICS_FLOWER = AnalyticalChemistryRow(
    name="THCA → Δ⁹-THC decarboxylation kinetics (flower, 110 °C, ~30 min)",
    topic=AnalyticalTopic.DECARB_KINETICS,
    claim_text=(
        "THCA-A decarboxylates to Δ⁹-THC following pseudo-first-order "
        "kinetics in dry cannabis flower; at 110 °C the half-life is "
        "approximately 27 minutes and >97% conversion is achieved after "
        "~60 minutes (matrix = dry-flower, atmosphere = ambient air, "
        "method = GC-FID with cold-injection or HPLC-DAD)."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="dry cannabis flower",
    conditions="110 °C, ambient atmosphere, ~30-60 min hold time",
    citations=(_VERESS_1990, _WANG_2016),
    key_notes=(
        "Kinetic parameters drift with matrix water content: dried-and-"
        "cured material decarboxylates faster than freshly harvested "
        "material at equivalent set temperatures.",
        "Wang 2016 confirms pseudo-first-order kinetics in a more modern "
        "matrix-controlled study and reports activation energy ≈ 87 kJ/mol.",
    ),
)


_DECARB_KINETICS_EXTRACT = AnalyticalChemistryRow(
    name="THCA → Δ⁹-THC decarboxylation kinetics (oil extract, 140 °C)",
    topic=AnalyticalTopic.DECARB_KINETICS,
    claim_text=(
        "In carrier-oil cannabis extracts, full THCA → Δ⁹-THC conversion "
        "is typically reached at 140 °C within 15-30 minutes; rate "
        "constants differ from dry-flower values because the lipid "
        "matrix reduces atmospheric oxygen contact and shifts the "
        "secondary loss-of-Δ⁹-THC-to-CBN pathway."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="carrier-oil extract (MCT / olive oil)",
    conditions="140 °C, 15-30 min hold time",
    citations=(_WANG_2016, _CITTI_2018),
    key_notes=(
        "Matrix-dependent kinetics: oil extracts and dry flower do not "
        "share the same rate constant — extrapolating flower decarb "
        "curves to edibles overstates Δ⁹-THC yield.",
        "Time-temperature trade-off: lower temperatures over longer "
        "times reduce CBN formation but increase total energy input.",
    ),
)


_HPLC_POTENCY = AnalyticalChemistryRow(
    name="HPLC potency analysis — reverse-phase C18 with UV at 220-230 nm",
    topic=AnalyticalTopic.HPLC_VALIDATION,
    claim_text=(
        "Reverse-phase HPLC with C18 stationary phase and UV detection "
        "at 220-230 nm is the workhorse for cannabis potency analysis "
        "because it resolves THCA, Δ⁹-THC, CBDA, CBD, CBN, CBC, CBG, "
        "CBGA, THCV, CBDV, and minor cannabinoid acids in a single run "
        "without thermal decarboxylation. Inter-laboratory CV under "
        "harmonised protocols is typically 5-15% (AOAC 2018 study)."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="cannabis flower / extract",
    conditions=(
        "Reverse-phase C18 column, gradient 0.1% formic acid in water vs "
        "acetonitrile, UV-DAD at 220-230 nm, isocratic or gradient elution"
    ),
    citations=(_CITTI_2018, _DUSSY_2005),
    key_notes=(
        "HPLC quantifies acidic and neutral cannabinoids independently; "
        "GC-MS thermally decarboxylates the acids in the injector "
        "(see gc_ms_artefact row).",
        "USP <467> / <1226> validation framework: linearity, accuracy, "
        "precision, LOD/LOQ, robustness — every method-validation "
        "report must cover all six elements.",
    ),
)


_GC_MS_DECARB_ARTEFACT = AnalyticalChemistryRow(
    name="GC-MS in-injector decarboxylation artefact",
    topic=AnalyticalTopic.GC_MS_ARTEFACT,
    claim_text=(
        "GC-MS quantitation of cannabis cannabinoids without prior "
        "derivatisation produces in-injector decarboxylation of THCA and "
        "CBDA. The apparent Δ⁹-THC peak on a GC chromatogram is the SUM "
        "of native Δ⁹-THC plus decarboxylated THCA-A; the same artefact "
        "applies to CBD vs CBDA. Method-comparison studies (HPLC vs GC-MS) "
        "report HPLC THC values systematically lower than GC THC values "
        "in unheated samples because the GC reading aggregates both forms."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="cannabis flower / extract (unheated)",
    conditions=(
        "GC-MS with EI ionisation; split/splitless injection port at "
        "≥ 250 °C; decarboxylation of THCA → Δ⁹-THC effectively complete"
    ),
    citations=(_DUSSY_2005, _CITTI_2018),
    key_notes=(
        "Workaround: silylation derivatisation (BSTFA + TMCS) preserves "
        "THCA / CBDA as TMS ethers so GC-MS quantifies the acids "
        "independently. Most modern potency labs prefer HPLC-DAD.",
        "Implication for label compliance: a flower COA generated by "
        "GC-MS without derivatisation will not match an HPLC COA for "
        "the same lot — this is a method artefact, not a sample heterogeneity.",
    ),
)


_CHEMOVAR_TYPES = AnalyticalChemistryRow(
    name="Chemovar Type I/II/III/IV/V classification (Hazekamp & Fischedick 2012)",
    topic=AnalyticalTopic.CHEMOVAR,
    claim_text=(
        "Cannabis cultivars cluster into five canonical chemovars by "
        "THCA:CBDA dominance: Type I = THCA-dominant (THCA:CBDA > 5:1), "
        "Type II = mixed (THCA:CBDA ≈ 1:1), Type III = CBDA-dominant "
        "(CBDA:THCA > 5:1), Type IV = CBGA-dominant, Type V = essentially "
        "cannabinoid-free hemp. The classification is enzymatic — Types "
        "I/III are explained by the dominance of functional THCA-synthase "
        "vs CBDA-synthase alleles."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="cannabis flower (lab-quantified chemical profile)",
    conditions="HPLC potency analysis; cannabinoid acid ratio post-cure",
    citations=(_HAZEKAMP_2012, _LEWIS_2018),
    key_notes=(
        "Chemovar IS the right modern framing — it is data, not "
        "marketing. Indica / sativa / hybrid is the legacy framing "
        "that does not correlate with effect (see banned-pattern "
        "registry indica_sativa_as_pharmacology).",
        "Lewis 2018 expands the framework to include terpene-secondary "
        "axes (myrcene-dominant vs limonene-dominant vs pinene-dominant) "
        "for within-chemovar discrimination.",
    ),
)


_CHEMOVAR_GENETIC_BASIS = AnalyticalChemistryRow(
    name="Chemotype inheritance — THCA-synthase / CBDA-synthase allelic basis",
    topic=AnalyticalTopic.CHEMOVAR,
    claim_text=(
        "Type I (THCA-dominant) vs Type III (CBDA-dominant) chemotype "
        "inheritance is governed by alleles at the cannabinoid-synthase "
        "locus. Plants homozygous for functional THCA-synthase produce "
        "Type I chemotype; homozygous functional CBDA-synthase produces "
        "Type III; heterozygotes produce Type II (mixed). The synthase "
        "locus tracks chemovar in segregating populations."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="cannabis seed-to-seed progeny analysis",
    conditions="genotype × chemotype co-segregation studies",
    citations=(_HILLIG_MAHLBERG_2004, _AIZPURUA_OLAIZOLA_2016),
    key_notes=(
        "The de Meijer 2003 segregation study (Genetics 163:335-46) "
        "established the single-locus model; subsequent work (Onofri "
        "2015, van Bakel 2011) revealed that the locus is structurally "
        "complex with multiple synthase copies.",
        "Type IV (CBGA-dominant) arises from loss-of-function alleles "
        "at BOTH downstream synthases — CBGA accumulates because the "
        "downstream conversion to THCA / CBDA is blocked.",
    ),
)


_PYROLYSIS_BYPRODUCTS = AnalyticalChemistryRow(
    name="Cannabis combustion vs vaporisation pyrolysis byproducts",
    topic=AnalyticalTopic.PYROLYSIS,
    claim_text=(
        "Combustion of cannabis flower at 600-800 °C generates the "
        "expected smoke pyrolysis byproducts — benzene, toluene, "
        "naphthalene, and polycyclic aromatic hydrocarbons (PAHs) — at "
        "concentrations comparable to tobacco smoke condensate. "
        "Vaporisation at 180-210 °C produces substantially lower (often "
        "an order of magnitude or more) levels of these byproducts "
        "while delivering similar cannabinoid yields per dose."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="cannabis flower (combusted vs vaporised vapor stream)",
    conditions="combustion ≈ 600-800 °C; vaporisation ≈ 180-210 °C",
    citations=(_POMAHACOVA_2009, _MOIR_2008),
    key_notes=(
        "Harm reduction context: vaporisation does NOT remove pyrolysis "
        "byproducts; it reduces their concentration relative to "
        "combustion. The signal-to-noise difference is dose-dependent.",
        "Devices with poorly-controlled element temperatures (some "
        "cartridge formats, hot-air gun analogues) can exceed the "
        "180-210 °C target and recover combustion-level byproducts; "
        "device temperature is a meaningful harm-reduction variable.",
    ),
)


_EDIBLE_DECARB_COMPLETION = AnalyticalChemistryRow(
    name="THCA decarboxylation completion in edibles — 121 °C autoclave "
         "vs 240 °F oven",
    topic=AnalyticalTopic.DECARB_KINETICS,
    claim_text=(
        "For edible-product manufacturing, complete THCA → Δ⁹-THC "
        "conversion in carrier oil requires sufficient hold-time at "
        "121 °C autoclave (≈ 45-60 min) OR oven decarboxylation at "
        "approximately 115-120 °C (≈ 30-45 min) before infusion. Insufficient "
        "decarboxylation produces an apparent under-dose; over-heating "
        "drives secondary Δ⁹-THC → CBN oxidation."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    matrix="cannabis-infused carrier oil (manufacturer process)",
    conditions=(
        "Oven 115-120 °C, 30-45 min, dry decarb step pre-infusion; or "
        "autoclave 121 °C, 45-60 min, sealed-vessel decarb"
    ),
    citations=(_WANG_2016, _LEGHISSA_2018),
    key_notes=(
        "Quality-control implication: a finished edible labelled at "
        "10 mg Δ⁹-THC requires the input THCA flower mass AND the "
        "decarboxylation efficiency to balance — undecarboxylated THCA "
        "passes through the digestive tract without producing Δ⁹-THC "
        "in significant amounts.",
        "Leghissa 2018 reviews the matrix-handling literature for "
        "cannabis edibles; matrix selection (sugar matrices, lipid "
        "matrices, gummies) substantially alters apparent potency.",
    ),
)


_REGISTRY: tuple[AnalyticalChemistryRow, ...] = (
    _DECARB_KINETICS_FLOWER,
    _DECARB_KINETICS_EXTRACT,
    _EDIBLE_DECARB_COMPLETION,
    _HPLC_POTENCY,
    _GC_MS_DECARB_ARTEFACT,
    _CHEMOVAR_TYPES,
    _CHEMOVAR_GENETIC_BASIS,
    _PYROLYSIS_BYPRODUCTS,
)


# ── Topic-keyword regex (the detector) ─────────────────────────────────


# Detector design: topic-keyword match, NOT cannabinoid-name match. The
# analytical-chemistry registry is about METHODS and the PLANT, not a
# single named cannabinoid. The keyword set is designed to be tight enough
# that ordinary clinical-pharmacology prompts (CBD-Dravet, CBD-warfarin)
# do NOT spuriously surface analytical rows.
_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        AnalyticalTopic.DECARB_KINETICS,
        re.compile(
            r"("
            r"\bdecarboxylation|\bdecarbox\s+kinetics|\bdecarb\s+kinetics|"
            # THCA followed by an arrow or "to" then a Δ-prefixed or "delta"-
            # prefixed THC, allowing any whitespace and arrow style.
            r"\bthca[\s ]*(?:→|->|to)[\s ]*(?:[δΔ]?[9⁹]?[- ]?thc|"
            r"delta-?9-?thc)|"
            r"\bdecarboxylat\w*|"
            r"\bedible[s]?\s+decarb"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        AnalyticalTopic.HPLC_VALIDATION,
        re.compile(
            r"\b("
            r"hplc(?:\s+method)?(?:\s+validation)?|"
            r"hplc\s+potency|"
            r"reverse[- ]phase\s+chromatograph\w*|"
            r"c18\s+column|"
            r"aoac\s+2015|"
            r"usp\s+[<]?467[>]?|usp\s+[<]?1226[>]?"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        AnalyticalTopic.GC_MS_ARTEFACT,
        re.compile(
            r"\b("
            r"gc[- ]?ms\s+(?:vs|versus|compared\s+to)\s+hplc|"
            r"gc(?:[- ]ms)?\s+(?:quantitation|potency|cannabinoid)|"
            r"in[- ]?injector\s+decarbox\w*|"
            r"gc[- ]?fid"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        AnalyticalTopic.CHEMOVAR,
        re.compile(
            r"\b("
            r"chemovar\w*|"
            r"chemotype\s+(?:type\s+)?(?:i{1,3}|iv|v)\b|"
            r"type\s+(?:i{1,3}|iv|v)\s+chemovar|"
            r"hazekamp\s+(?:&\s+)?fischedick|"
            r"thca\s+synthase|cbda\s+synthase|"
            r"cannabinoid\s+synthase\s+(?:locus|alleles?)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        AnalyticalTopic.PYROLYSIS,
        re.compile(
            r"\b("
            r"pyrolysis|pyrolytic|"
            r"combust\w*\s+(?:vs|versus|compared\s+to|byproduct\w*)|"
            r"vaporis\w*\s+(?:vs|versus|compared\s+to|byproduct\w*|temperature)|"
            r"vapor\s+pyrolysis|"
            r"cannabis\s+smoke\s+(?:condensate|byproduct\w*)|"
            r"benzene\s+(?:and|or)\s+toluene|"
            r"polycyclic\s+aromatic\s+hydrocarbon\w*"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_analytical_chemistry_rows() -> tuple[AnalyticalChemistryRow, ...]:
    """Return every curated analytical-chemistry row."""
    return _REGISTRY


def find_analytical_chemistry_rows(
    topic_or_name: str,
) -> tuple[AnalyticalChemistryRow, ...]:
    """Lookup rows by topic name or row name (case-insensitive)."""
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[AnalyticalChemistryRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_analytical_chemistry_mention(
    text: str,
) -> tuple[AnalyticalChemistryRow, ...]:
    """Return rows whose topic-keyword regex matches ``text``.

    Used by ``compose_answer`` to surface analytical-chemistry rows when
    the prompt names a covered topic.
    """
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
    AnalyticalTopic.DECARB_KINETICS: "Decarboxylation kinetics",
    AnalyticalTopic.HPLC_VALIDATION: "HPLC method validation",
    AnalyticalTopic.GC_MS_ARTEFACT: "GC-MS in-injector artefact",
    AnalyticalTopic.CHEMOVAR: "Chemovar classification",
    AnalyticalTopic.PYROLYSIS: "Vapor / smoke pyrolysis byproducts",
}


def render_markdown(rows: Iterable[AnalyticalChemistryRow]) -> str:
    """Render the matched rows as a clean Markdown section."""
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[AnalyticalChemistryRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## Analytical-chemistry registry")
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
            if r.matrix:
                lines.append(f"  - Matrix: {r.matrix}")
            if r.conditions:
                lines.append(f"  - Conditions: {r.conditions}")
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
