"""Cultivation-science registry (spec 004 US2 / FR-002).

Research-grade plant biology, biosynthesis, and botanical taxonomy of
Cannabis sativa — the topics a working horticultural-science PI,
chemotype geneticist, or systematic-botany researcher asks about.

Topic coverage:

- ``light_spectrum`` — UV-B (280-315 nm) effect on cannabinoid
  biosynthesis. The canonical Lydon 1987 (PMID 3628508) study
  established the THC-content response to UV-B; modern phytochrome /
  photosystem work refines the spectrum-dependence.
- ``trichome_biology`` — glandular trichomes are the primary site of
  cannabinoid + terpene biosynthesis. Livingston 2020
  (PMID 31867754) Plant Cell paper on stalked vs sessile vs bulbous
  glandular trichomes; Tanney 2021 review of the secretory cell
  biology.
- ``synthase_genetics`` — THCA-synthase / CBDA-synthase / CBCA-synthase
  allelic dominance. de Meijer 2003 (PMID 12586720) Genetics paper
  established the single-locus segregation model; Onofri 2015 and
  van Bakel 2011 expanded the molecular picture.
- ``botanical_taxonomy`` — Cannabis sativa as one species (Small &
  Cronquist 1976) vs three (Hillig & Mahlberg 2004 / Hillig 2005);
  McPartland 2018 review. Research-grade botany, distinct from the
  banned-pattern indica/sativa-as-pharmacology intent.

Every row carries a `to_claim()` returning a typed
:class:`cannavec_science.evidence.Claim` for the composer.

The botanical-taxonomy row is intentionally a Level C *honest debate*
row — Cannavec Science does NOT pick a winner between the one-species
and multi-species views; it cites both and reports the live scholarly
disagreement. This is the same evidentiary honesty the v0.3
entourage-effect treatment applies.

Stdlib-only. Researcher audience only. Identifier discipline (PMID or
DOI per Constitution §I) enforced at construction time.
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
    "CultivationCitation",
    "CultivationScienceRow",
    "CultivationTopic",
    "all_cultivation_science_rows",
    "find_cultivation_science_rows",
    "detect_cultivation_science_mention",
    "render_markdown",
]


class CultivationTopic:
    LIGHT_SPECTRUM = "light_spectrum"
    TRICHOME_BIOLOGY = "trichome_biology"
    SYNTHASE_GENETICS = "synthase_genetics"
    BOTANICAL_TAXONOMY = "botanical_taxonomy"


@dataclass(frozen=True)
class CultivationCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class CultivationScienceRow:
    """One curated cultivation-science primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[CultivationCitation, ...]
    organism: str = "Cannabis sativa L."
    conditions: str = ""
    last_verified: str = "2026-05-21"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"cultivation-science row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"cultivation-science row {self.name!r} citation "
                    f"{c.label!r} must have a PMID or DOI"
                )
        if not self.watch_pmids:
            object.__setattr__(
                self,
                "watch_pmids",
                tuple(c.pmid for c in self.citations if c.pmid),
            )

    def to_claim(self) -> Claim:
        """Render as a typed :class:`Claim`."""
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
            "organism": self.organism,
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


_LYDON_1987 = CultivationCitation(
    label="Lydon J et al., Photochem Photobiol 1987, UV-B radiation effects "
          "on photosynthesis, growth, and cannabinoid production of two "
          "Cannabis sativa chemotypes",
    pmid="3628508", year=1987,
)
_MAGAGNINI_2018 = CultivationCitation(
    label="Magagnini G et al., Med Cannabis Cannabinoids 2018, the effect "
          "of light spectrum on the morphology and cannabinoid content of "
          "Cannabis sativa L.",
    doi="10.1159/000489030", year=2018,
)
_LIVINGSTON_2020 = CultivationCitation(
    label="Livingston SJ et al., Plant J 2020, cannabis glandular trichomes "
          "alter morphology and metabolite content during flower maturation",
    pmid="31867754", year=2020,
)
_TANNEY_2021 = CultivationCitation(
    label="Tanney CAS et al., Front Plant Sci 2021, cannabis glandular "
          "trichomes — a cellular metabolite factory",
    pmid="34025682", year=2021,
)
_DE_MEIJER_2003 = CultivationCitation(
    label="de Meijer EPM et al., Genetics 2003, the inheritance of "
          "chemical phenotype in Cannabis sativa L.",
    pmid="12586720", year=2003,
)
_ONOFRI_2015 = CultivationCitation(
    label="Onofri C et al., Phytochemistry 2015, sequence heterogeneity "
          "of cannabidiolic- and tetrahydrocannabinolic acid-synthase in "
          "Cannabis sativa L. and its relationship with chemical phenotype",
    pmid="25801039", year=2015,
)
_VAN_BAKEL_2011 = CultivationCitation(
    label="van Bakel H et al., Genome Biol 2011, the draft genome and "
          "transcriptome of Cannabis sativa",
    pmid="22014239", year=2011,
)
_SMALL_CRONQUIST_1976 = CultivationCitation(
    label="Small E & Cronquist A, Taxon 1976, a practical and natural "
          "taxonomy for Cannabis",
    doi="10.2307/1220524", year=1976,
)
_HILLIG_2005 = CultivationCitation(
    label="Hillig KW, Genet Resour Crop Evol 2005, genetic evidence for "
          "speciation in Cannabis (Cannabaceae)",
    doi="10.1007/s10722-003-4452-y", year=2005,
)
_MCPARTLAND_2018 = CultivationCitation(
    label="McPartland JM, Cannabis Cannabinoid Res 2018, Cannabis "
          "systematics at the levels of family, genus, and species",
    doi="10.1089/can.2018.0039", year=2018,
)
_TAURA_2007 = CultivationCitation(
    label="Taura F et al., FEBS Lett 2007, cannabidiolic-acid synthase, "
          "the chemotype-determining enzyme in the fiber-type Cannabis "
          "sativa",
    pmid="17631292", year=2007,
)
_GROTENHERMEN_2003 = CultivationCitation(
    label="Grotenhermen F, Clin Pharmacokinet 2003, clinical "
          "pharmacokinetics of cannabinoids",
    pmid="12648025", year=2003,
)


# ── Registry rows ──────────────────────────────────────────────────────


_UVB_BIOSYNTHESIS = CultivationScienceRow(
    name="UV-B (280-315 nm) exposure increases Δ⁹-THC content "
         "(canonical Lydon 1987 finding)",
    topic=CultivationTopic.LIGHT_SPECTRUM,
    claim_text=(
        "Sustained UV-B (280-315 nm) supplementation during the "
        "flowering phase of Δ⁹-THC-chemotype Cannabis sativa increases "
        "Δ⁹-THC content of glandular trichomes; CBD-chemotype plants do "
        "NOT show the equivalent CBD increase in the same experiment. "
        "The Lydon 1987 finding is the field-foundational result; "
        "modern replication studies are mixed and stress dose-dependence "
        "of the response."
    ),
    claim_type=ClaimType.CULTIVATION_PARAMETER,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    organism="Cannabis sativa L. (THC-chemotype + CBD-chemotype, controlled chamber)",
    conditions=(
        "UV-B supplementation 280-315 nm, intensity 5-15 kJ/m²/day, "
        "applied during the photoperiod-induced flowering phase"
    ),
    citations=(_LYDON_1987, _MAGAGNINI_2018),
    key_notes=(
        "The UV-B response is chemotype-specific — Type I (THC-dominant) "
        "plants increase Δ⁹-THC content; Type III (CBD-dominant) plants "
        "do not show a proportional CBD increase. The mechanism is not "
        "fully resolved (UV-induced trichome density vs in-trichome "
        "biosynthesis rate).",
        "Practical caveat: UV-B is also a stressor — beyond 15 kJ/m²/day "
        "yield and photosynthesis decline. The cannabinoid response is "
        "not a monotonic 'more UV-B = more THC' relationship.",
    ),
)


_TRICHOME_FACTORY = CultivationScienceRow(
    name="Glandular trichomes are the primary site of cannabinoid + "
         "terpene biosynthesis",
    topic=CultivationTopic.TRICHOME_BIOLOGY,
    claim_text=(
        "Stalked glandular trichomes on the flowers and surrounding "
        "bracts of female Cannabis sativa are the primary site of "
        "cannabinoid acid (THCA / CBDA / CBGA) and monoterpene / "
        "sesquiterpene biosynthesis. Trichome density × per-trichome "
        "metabolic capacity sets the maximum potential cannabinoid yield "
        "for a given cultivar × environment combination. Trichome "
        "maturation involves morphological change (clear → milky → amber) "
        "that the Livingston 2020 study links to cannabinoid + terpene "
        "profile shifts."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    organism="Cannabis sativa L. (female flowering plants)",
    conditions="Stalked glandular trichomes; flowering-phase development",
    citations=(_LIVINGSTON_2020, _TANNEY_2021),
    key_notes=(
        "Three morphological trichome classes (bulbous, capitate-sessile, "
        "capitate-stalked); the capitate-stalked class dominates flower "
        "cannabinoid yield in mature plants.",
        "Trichome maturity ≠ ripeness as a harvest indicator on its own — "
        "the colour gradient (clear → milky → amber) is a rough proxy "
        "for cannabinoid acid oxidation and CBN accumulation, not a "
        "monotonic THC potency curve.",
    ),
)


_THCA_SYNTHASE_GENETICS = CultivationScienceRow(
    name="Single-locus inheritance of THCA-/CBDA-synthase chemotype "
         "(de Meijer 2003)",
    topic=CultivationTopic.SYNTHASE_GENETICS,
    claim_text=(
        "The inheritance of Type I (THCA-dominant), Type II (mixed), "
        "and Type III (CBDA-dominant) chemotype in Cannabis sativa "
        "segregating populations follows a single-locus Mendelian model "
        "with co-dominant alleles BD (functional CBDA-synthase) and BT "
        "(functional THCA-synthase). Homozygous BT/BT → Type I; "
        "heterozygous BT/BD → Type II (intermediate); BD/BD → Type III. "
        "The locus is structurally complex with multiple synthase copies "
        "(van Bakel 2011, Onofri 2015), but the single-locus segregation "
        "model holds at the phenotypic level."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    organism="Cannabis sativa L. segregating progeny populations",
    conditions=(
        "F2 segregation analysis of THC- × CBD-chemotype parental "
        "crosses; allele-specific PCR or sequencing"
    ),
    citations=(_DE_MEIJER_2003, _ONOFRI_2015, _VAN_BAKEL_2011),
    key_notes=(
        "Type IV (CBGA-dominant) chemotype arises from loss-of-function "
        "alleles at both BT and BD — CBGA accumulates because downstream "
        "conversion to either THCA or CBDA is blocked. This is a "
        "distinct genotype rather than a continuous-trait extreme.",
        "Modern breeding programmes use synthase-locus allele-specific "
        "PCR to genotype seedlings BEFORE chemovar phenotype is "
        "measurable at maturity.",
    ),
)


_CBDA_SYNTHASE_BIOCHEMISTRY = CultivationScienceRow(
    name="CBDA-synthase enzymology (Taura 2007 cloning)",
    topic=CultivationTopic.SYNTHASE_GENETICS,
    claim_text=(
        "CBDA-synthase (BAHD / FAD-dependent oxidocyclase) converts "
        "CBGA → CBDA through an FAD-mediated oxidative cyclisation. "
        "Taura 2007 cloned the enzyme from fibre-type Cannabis sativa "
        "and confirmed it is a distinct molecular species from "
        "THCA-synthase, with both enzymes sharing the CBGA substrate "
        "but channeling it to different products."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    organism="Cannabis sativa L. (fibre-type; CBDA-synthase isoform)",
    conditions="Heterologous expression + enzymological characterisation",
    citations=(_TAURA_2007,),
    key_notes=(
        "The CBGA → CBDA conversion is the product-determining step in "
        "Type III chemotypes; THCA-synthase competition shapes the "
        "phenotype of Type II / heterozygote plants.",
        "Substrate selectivity at the CBGA → product step is a target "
        "for engineered cannabinoid biosynthesis — yeast / E. coli "
        "biosynthesis programmes start with this enzyme pair.",
    ),
)


_CHEMOTYPE_DOMINANCE = CultivationScienceRow(
    name="Chemotype dominance — F1 heterozygotes are mixed-chemotype",
    topic=CultivationTopic.SYNTHASE_GENETICS,
    claim_text=(
        "F1 heterozygote progeny of a Type I (THC-dominant) × Type III "
        "(CBD-dominant) parental cross are uniformly Type II "
        "(mixed-chemotype, with comparable THCA and CBDA accumulation), "
        "not skewed toward either parent. This is the inheritance "
        "pattern that distinguishes co-dominant single-locus segregation "
        "from polygenic continuous inheritance, and it underlies modern "
        "breeding for Type II / 1:1 cultivars."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    organism="Cannabis sativa L. F1 progeny from Type I × Type III cross",
    conditions="F1 chemovar quantification by HPLC potency analysis",
    citations=(_DE_MEIJER_2003,),
    key_notes=(
        "The 1:1 (Type II) phenotype is the canonical 'balanced' "
        "preparation in medical cannabis research (Sativex / nabiximols "
        "is essentially a Type II preparation).",
        "Co-dominance vs additivity matters for breeding: F2 "
        "Type II × Type II crosses re-segregate into 1:2:1 Type I : "
        "Type II : Type III progeny.",
    ),
)


_BOTANICAL_TAXONOMY = CultivationScienceRow(
    name="Cannabis sativa as one species (Small & Cronquist 1976) "
         "vs three (Hillig 2005)",
    topic=CultivationTopic.BOTANICAL_TAXONOMY,
    claim_text=(
        "The botanical taxonomy of the genus Cannabis is a live "
        "scientific debate. The Small & Cronquist 1976 single-species "
        "framework (Cannabis sativa L. as monotypic with subspecies "
        "sativa / indica / ruderalis) remains the formal taxonomic "
        "consensus. The Hillig 2005 chemotaxonomic and genetic analyses "
        "support a three-species view (C. sativa / C. indica / "
        "C. ruderalis). McPartland 2018 reviews both positions and "
        "argues for taxonomic stability against repeated re-naming. "
        "This is a research-grade systematics question distinct from "
        "the popular indica-vs-sativa pharmacology framing (which is "
        "not biochemically meaningful — see banned-pattern registry)."
    ),
    claim_type=ClaimType.EDUCATIONAL,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    organism="Cannabis spp. (taxonomy of the genus)",
    conditions="Chemotaxonomic + genetic systematic analyses",
    citations=(_SMALL_CRONQUIST_1976, _HILLIG_2005, _MCPARTLAND_2018),
    key_notes=(
        "The taxonomic question is OPEN. Cannavec Science does NOT "
        "endorse either position; both citations are surfaced so the "
        "researcher can read them and form their own view.",
        "Critically: the taxonomic question of WHETHER indica and "
        "sativa are distinct species is research-grade botany. The "
        "popular indica/sativa pharmacology framing — 'indica = "
        "sedating, sativa = energising' — does NOT survive the "
        "chemovar / terpene analyses (Hazekamp 2012, Lewis 2018) and "
        "Cannavec Science rejects it via the banned-pattern detector.",
    ),
)


_REGISTRY: tuple[CultivationScienceRow, ...] = (
    _UVB_BIOSYNTHESIS,
    _TRICHOME_FACTORY,
    _THCA_SYNTHASE_GENETICS,
    _CBDA_SYNTHASE_BIOCHEMISTRY,
    _CHEMOTYPE_DOMINANCE,
    _BOTANICAL_TAXONOMY,
)


# ── Topic-keyword regex (the detector) ─────────────────────────────────


_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        CultivationTopic.LIGHT_SPECTRUM,
        re.compile(
            r"\b("
            r"uv[- ]?b|ultraviolet[- ]?b|"
            r"light\s+spectrum|"
            r"red\s*:\s*blue\s+(?:ratio|spectrum)|"
            r"blue\s*:\s*red\s+(?:ratio|spectrum)|"
            r"photosynthet\w*\s+spectrum|"
            r"cannabinoid\s+biosynthesi[sz]"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        CultivationTopic.TRICHOME_BIOLOGY,
        re.compile(
            r"\b("
            r"trichom\w*|"
            r"glandular\s+secret\w*|"
            r"capitate[- ]?stalked|capitate[- ]?sessile|"
            r"bulbous\s+trichom\w*"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        CultivationTopic.SYNTHASE_GENETICS,
        re.compile(
            r"\b("
            r"thca[- ]?synthase|cbda[- ]?synthase|cbca[- ]?synthase|"
            r"cannabinoid\s+synthase|"
            r"chemotype\s+inherit\w*|"
            r"chemovar\s+inherit\w*|"
            r"de\s+meijer\s+2003|"
            r"segregation\s+(?:of\s+)?(?:thc|cbd|chemotype)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        CultivationTopic.BOTANICAL_TAXONOMY,
        re.compile(
            r"\b("
            r"botanical\s+taxonom\w*|"
            r"cannabis\s+(?:systematic\w*|taxonom\w*)|"
            r"cannabis\s+sativa\s+l\.?(?:\s+species)?|"
            r"sativa\s+l\.\s+(?:taxonom\w*|species|systemati\w*)|"
            r"(?:one|1|single)\s+species\s+or\s+(?:three|3|multiple)|"
            r"species\s+debate|"
            r"hillig\s+(?:&\s+)?mahlberg|"
            r"small\s+(?:&\s+)?cronquist|"
            r"mcpartland\s+2018"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_cultivation_science_rows() -> tuple[CultivationScienceRow, ...]:
    """Return every curated cultivation-science row."""
    return _REGISTRY


def find_cultivation_science_rows(
    topic_or_name: str,
) -> tuple[CultivationScienceRow, ...]:
    """Lookup rows by topic name or row name (case-insensitive)."""
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[CultivationScienceRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_cultivation_science_mention(
    text: str,
) -> tuple[CultivationScienceRow, ...]:
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
    CultivationTopic.LIGHT_SPECTRUM: "Light spectrum + cannabinoid biosynthesis",
    CultivationTopic.TRICHOME_BIOLOGY: "Trichome biology",
    CultivationTopic.SYNTHASE_GENETICS: "Cannabinoid-synthase genetics",
    CultivationTopic.BOTANICAL_TAXONOMY: "Botanical taxonomy",
}


def render_markdown(rows: Iterable[CultivationScienceRow]) -> str:
    """Render the matched rows as a clean Markdown section."""
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[CultivationScienceRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## Cultivation-science registry")
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
