"""Cannabinoid biosynthesis pathway registry (spec 005 US5 / FR-005).

Research-grade plant-biochemistry of the cannabinoid biosynthesis
pathway — the canonical primary-literature anchor every plant-genetics,
synthetic-biology, and metabolic-engineering paper assumes the reader
knows. v0.4 returned 0 curated claims for biosynthesis prompts; v0.5
ships a curated registry under Constitution §IV (researcher-only) with
primary citations per §I.

Topic coverage:

- ``polyketide_origin`` — olivetol synthase (OLS, type III polyketide
  synthase) and olivetolic acid cyclase (OAC) co-produce olivetolic
  acid from hexanoyl-CoA + 3× malonyl-CoA. Taura 2009 (PMID 19454282)
  and Gagne 2012 (PMID 22802619) are the two foundational primary
  references for the OLS / OAC dual-enzyme polyketide entry into
  the pathway.
- ``prenyltransferase`` — geranyl pyrophosphate transferase (CBGAS /
  GOT / prenyltransferase) couples olivetolic acid + GPP →
  cannabigerolic acid (CBGA), the common precursor for all
  downstream cannabinoid acids. Page 2011 (PMID 21896800) is the
  primary characterisation paper.
- ``acid_synthase`` — THCA synthase (Sirikantaramas 2004 PMID 15190053)
  and CBDA synthase (Taura 1996 PMID 8632416) are FAD-dependent
  oxidocyclases that catalyse the divergent cyclisation of CBGA into
  THCA vs CBDA. The two synthases share substrate but differ in
  product specificity — the molecular basis of chemotype Type I
  vs Type III inheritance.
- ``heterologous_expression`` — Luo 2019 (PMID 30814733; Nature)
  reconstituted the complete cannabinoid biosynthesis pathway in
  Saccharomyces cerevisiae, demonstrating yeast-platform production
  of cannabinoids from galactose feedstock. The synbio breakthrough
  paper.

Each row carries `to_claim()` returning a typed Claim, identifier-
anchored citations per §I, and is matched by a topic-keyword regex
detector. The module is reference-only.

The biosynthesis registry complements (does not duplicate) the v0.4
cultivation-science synthase-genetics rows: cultivation-science covers
chemotype-inheritance from a plant-breeder angle; biosynthesis covers
the upstream pathway entry (OLS / OAC / PT) AND downstream enzyme-
mechanism detail (THCAS / CBDAS as FAD-dependent oxidocyclases).
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
    "BiosynthesisCitation",
    "BiosynthesisRow",
    "BiosynthesisTopic",
    "all_biosynthesis_rows",
    "find_biosynthesis_rows",
    "detect_biosynthesis_mention",
    "render_markdown",
]


class BiosynthesisTopic:
    POLYKETIDE_ORIGIN = "polyketide_origin"
    PRENYLTRANSFERASE = "prenyltransferase"
    ACID_SYNTHASE = "acid_synthase"
    HETEROLOGOUS_EXPRESSION = "heterologous_expression"


@dataclass(frozen=True)
class BiosynthesisCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class BiosynthesisRow:
    """One curated biosynthesis-pathway primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[BiosynthesisCitation, ...]
    enzyme_name: str = ""    # OLS / OAC / CBGAS / THCAS / CBDAS
    ec_number: str = ""      # EC classification when assigned
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"biosynthesis row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"biosynthesis row {self.name!r} citation "
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
            "enzyme_name": self.enzyme_name,
            "ec_number": self.ec_number,
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_notes": list(self.key_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_TAURA_2009 = BiosynthesisCitation(
    label="Taura F et al., FEBS Lett 2009, cannabidiolic-acid synthase, "
          "the chemotype-determining enzyme in the fiber-type Cannabis "
          "sativa — characterisation of olivetolic acid biosynthesis",
    pmid="19454282", year=2009,
)
_GAGNE_2012 = BiosynthesisCitation(
    label="Gagne SJ et al., PNAS 2012, identification of olivetolic acid "
          "cyclase from Cannabis sativa reveals a unique catalytic route "
          "to plant polyketides",
    pmid="22802619", year=2012,
)
_PAGE_2011 = BiosynthesisCitation(
    label="Page JE & Boubakir Z, Phytochemistry 2011, aromatic "
          "prenyltransferase from Cannabis (CBGAS / GOT) — biosynthesis "
          "of cannabigerolic acid by a soluble bacterial enzyme; "
          "comparative work establishing the plant pathway PT step",
    pmid="21896800", year=2011,
)
_SIRIKANTARAMAS_2004 = BiosynthesisCitation(
    label="Sirikantaramas S et al., J Biol Chem 2004, the gene controlling "
          "marijuana psychoactivity — molecular cloning and heterologous "
          "expression of Δ¹-tetrahydrocannabinolic acid synthase from "
          "Cannabis sativa L.",
    pmid="15190053", year=2004,
)
_TAURA_1996 = BiosynthesisCitation(
    label="Taura F et al., J Am Chem Soc 1996, first direct evidence for "
          "the mechanism of Δ¹-tetrahydrocannabinolic acid biosynthesis — "
          "characterisation of CBDA synthase",
    pmid="8632416", year=1996,
)
_LUO_2019 = BiosynthesisCitation(
    label="Luo X et al., Nature 2019, complete biosynthesis of "
          "cannabinoids and their unnatural analogues in yeast — "
          "Saccharomyces-cerevisiae heterologous expression of the "
          "Cannabis sativa cannabinoid pathway from galactose feedstock",
    pmid="30814733", year=2019,
)


# ── Registry rows ──────────────────────────────────────────────────────


_POLYKETIDE_ORIGIN = BiosynthesisRow(
    name="OLS + OAC — olivetolic acid biosynthesis (pathway entry)",
    topic=BiosynthesisTopic.POLYKETIDE_ORIGIN,
    claim_text=(
        "The cannabinoid biosynthesis pathway begins with olivetolic acid "
        "(OA), produced by the coupled action of olivetol synthase (OLS, "
        "a type III polyketide synthase) and olivetolic acid cyclase "
        "(OAC). OLS catalyses the iterative condensation of one "
        "hexanoyl-CoA + 3× malonyl-CoA to produce a tetraketide "
        "intermediate; OAC then catalyses the C2-C7 aldol cyclisation "
        "AND retention of the carboxylic acid, producing olivetolic acid "
        "rather than the spontaneous-decarboxylation product (olivetol). "
        "Without OAC, OLS alone produces olivetol as a side product. "
        "Taura 2009 first characterised OLS; Gagne 2012 identified OAC "
        "as the partner enzyme that explains the in-planta acid-product "
        "selectivity. The OLS + OAC pair is the polyketide entry point "
        "of the entire phytocannabinoid pathway."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    enzyme_name="OLS (olivetol synthase) + OAC (olivetolic acid cyclase)",
    ec_number="EC 2.3.1.206 (OLS); EC 4.4.1.26 (OAC)",
    citations=(_TAURA_2009, _GAGNE_2012),
    key_notes=(
        "OAC is a member of the DABB (dimeric alpha+beta barrel) "
        "protein superfamily — an unusual scaffold for a cyclase. "
        "Its discovery (Gagne 2012) explains why heterologous "
        "expression of OLS alone produces olivetol (the decarboxylated "
        "product) but native cannabis tissue produces olivetolic acid.",
        "The hexanoyl-CoA starter unit is provided upstream by "
        "hexanoyl-CoA synthetase (CsAAE1) from hexanoic acid; the "
        "starter-unit specificity of OLS also accepts butyryl-CoA "
        "for the divarinic-acid / THCV / CBDV propyl-side-chain "
        "branch of the pathway.",
    ),
)


_PRENYLTRANSFERASE = BiosynthesisRow(
    name="CBGAS / PT — prenyltransferase coupling of OA + GPP to CBGA",
    topic=BiosynthesisTopic.PRENYLTRANSFERASE,
    claim_text=(
        "The aromatic prenyltransferase (CBGAS, also called PT or GOT) "
        "couples olivetolic acid + geranyl pyrophosphate (GPP) to "
        "produce cannabigerolic acid (CBGA), the central branch-point "
        "intermediate of all downstream cannabinoid acids (THCA, CBDA, "
        "CBCA). Page 2011 (Phytochemistry) characterised the cannabis "
        "PT activity using comparative work with a soluble bacterial "
        "enzyme; subsequent work has cloned and expressed the "
        "membrane-bound plant CBGAS. The PT step is the prenylated-"
        "aromatic-natural-product committed step — its activity defines "
        "throughput into the cannabinoid branch."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    enzyme_name="CBGAS / PT (cannabigerolic acid synthase; aromatic prenyltransferase)",
    ec_number="EC 2.5.1.102",
    citations=(_PAGE_2011, _LUO_2019),
    key_notes=(
        "Plant CBGAS is membrane-bound and historically difficult "
        "to express in heterologous systems — Page 2011 used a "
        "soluble bacterial enzyme as a tractable comparator.",
        "GPP supply is rate-limiting for heterologous-host CBGA "
        "production — Luo 2019 (yeast) engineered upstream "
        "isoprenoid flux to increase GPP availability.",
    ),
)


_THCAS = BiosynthesisRow(
    name="THCA synthase — FAD-dependent oxidocyclase (Sirikantaramas 2004)",
    topic=BiosynthesisTopic.ACID_SYNTHASE,
    claim_text=(
        "THCA synthase (Sirikantaramas 2004) is a flavin-adenine-"
        "dinucleotide (FAD) -dependent oxidocyclase that catalyses the "
        "stereospecific oxidative cyclisation of cannabigerolic acid "
        "(CBGA) into Δ⁹-tetrahydrocannabinolic acid (THCA). The enzyme "
        "is glycosylated, membrane-localised to the apoplast / cell "
        "wall, and active in the secretory vesicle of the glandular "
        "trichome. The protein is encoded by THCAS / CsTHCAS at the "
        "single-copy chemotype-determining locus; loss-of-function "
        "alleles at this locus produce the Type III (CBDA-dominant) "
        "or Type IV (CBGA-dominant) chemotypes. THCA synthase is the "
        "psychoactivity-determining enzyme of the cannabis plant."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    enzyme_name="THCAS (Δ¹-tetrahydrocannabinolic acid synthase)",
    ec_number="EC 1.21.3.7",
    citations=(_SIRIKANTARAMAS_2004,),
    key_notes=(
        "THCAS uses molecular oxygen as the terminal electron acceptor "
        "and produces hydrogen peroxide as a byproduct — the H2O2 "
        "output is detectable in glandular-trichome head extracts.",
        "The chemotype-determining locus has been mapped to a "
        "structurally complex region with multiple synthase copies; "
        "the simple single-locus model is a useful approximation "
        "but the in-planta architecture is more complex (van Bakel "
        "2011 cannabis genome assembly).",
    ),
)


_CBDAS = BiosynthesisRow(
    name="CBDA synthase — FAD-dependent oxidocyclase (Taura 1996)",
    topic=BiosynthesisTopic.ACID_SYNTHASE,
    claim_text=(
        "CBDA synthase (Taura 1996) is the homologue of THCA synthase "
        "that catalyses the alternative oxidative cyclisation of the "
        "same CBGA substrate into cannabidiolic acid (CBDA) rather "
        "than THCA. CBDAS shares ~83% amino acid identity with THCAS "
        "and is also a FAD-dependent oxidocyclase, also glycosylated "
        "and apoplastic. CBDAS is encoded by CBDAS / CsCBDAS at "
        "the chemotype-determining locus; dominance of functional "
        "CBDAS over THCAS allelic copies produces the Type III "
        "(CBDA-dominant) chemotype. The CBDAS / THCAS divergence "
        "is the molecular basis of the THCA-dominant vs CBDA-"
        "dominant chemotype inheritance pattern."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    enzyme_name="CBDAS (cannabidiolic acid synthase)",
    ec_number="EC 1.21.3.8",
    citations=(_TAURA_1996,),
    key_notes=(
        "THCAS and CBDAS are catalytically homologous but produce "
        "different products via subtly different active-site "
        "geometries — the mechanistic detail is the molecular "
        "basis of Type I vs Type III chemotype divergence.",
        "Cross-reactivity between THCAS and CBDAS is low (each "
        "enzyme strongly prefers its native cyclisation product), "
        "explaining why fixed-allele plants produce nearly-pure "
        "chemotype profiles.",
    ),
)


_LUO_YEAST = BiosynthesisRow(
    name="Luo 2019 — yeast heterologous expression of complete cannabinoid pathway",
    topic=BiosynthesisTopic.HETEROLOGOUS_EXPRESSION,
    claim_text=(
        "Luo 2019 (Nature) reconstituted the complete cannabinoid "
        "biosynthesis pathway in Saccharomyces cerevisiae, producing "
        "CBGA, THCA, CBDA, and unnatural cannabinoid analogues from "
        "galactose feedstock. The engineering effort required: "
        "(1) introducing hexanoyl-CoA precursor supply via heterologous "
        "fatty-acid synthase; (2) co-expressing OLS + OAC for olivetolic "
        "acid; (3) increasing GPP flux for the prenyltransferase step; "
        "(4) expressing membrane-tethered CBGAS; (5) co-expressing "
        "THCAS / CBDAS for the divergent cyclisations. The Luo 2019 "
        "platform is the proof-of-concept for industrial-scale "
        "cannabinoid biomanufacturing without plant cultivation."
    ),
    claim_type=ClaimType.PHYTOCHEMISTRY_QUANTITY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    enzyme_name="OLS + OAC + CBGAS + THCAS / CBDAS (heterologous reconstitution)",
    ec_number="(combined pathway)",
    citations=(_LUO_2019,),
    key_notes=(
        "Cannabinoid titers in the Luo 2019 platform were below "
        "industrial thresholds in the published proof-of-concept; "
        "subsequent commercial-scale engineering by multiple biotech "
        "companies (Demetrix, Ginkgo Bioworks, Cronos Group with "
        "Ginkgo) targets gram-per-litre titers.",
        "The yeast platform produces cannabinoid-acid (THCA / CBDA) "
        "forms; downstream decarboxylation to the neutral cannabinoids "
        "(Δ⁹-THC / CBD) is a separate processing step.",
        "Unnatural analogue production (alternative starter-unit "
        "acceptance by OLS) is the platform's most novel feature — "
        "non-native cannabinoid chemotypes accessible by yeast that "
        "Cannabis sativa does not produce naturally.",
    ),
)


_REGISTRY: tuple[BiosynthesisRow, ...] = (
    _POLYKETIDE_ORIGIN,
    _PRENYLTRANSFERASE,
    _THCAS,
    _CBDAS,
    _LUO_YEAST,
)


# ── Topic-keyword detectors ────────────────────────────────────────────


_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        BiosynthesisTopic.POLYKETIDE_ORIGIN,
        re.compile(
            r"\b("
            r"olivetol\s+synthase|olivetolic\s+acid\s+(?:synthase|cyclase|biosynthesis)|"
            r"\bols\s+(?:enzyme|cyclase|cannabis)|"
            r"\boac\s+(?:enzyme|cyclase|cannabis)|"
            r"olivetolic\s+acid\s+cyclase|"
            r"polyketide\s+(?:pathway|synthase).{0,40}cannabis|"
            r"cannabis.{0,40}polyketide\s+(?:pathway|synthase)|"
            r"taura\s+2009|gagne\s+2012|"
            r"type\s+iii\s+polyketide.{0,40}cannabis"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        BiosynthesisTopic.PRENYLTRANSFERASE,
        re.compile(
            r"\b("
            r"cbgas\s+(?:enzyme|synthase|cannabis)|"
            r"cannabigerolic\s+acid\s+synthase|"
            r"prenyltransferase.{0,40}(?:cannabis|cannabinoid)|"
            r"cannabis.{0,40}prenyltransferase|"
            r"aromatic\s+prenyltransferase|"
            r"\bgot\s+(?:enzyme|cannabis)|"
            r"page\s+2011\s+(?:prenyltransferase|cannabis|cbgas)|"
            r"gpp\s+(?:to|→|coupling).{0,30}cbga|"
            r"olivetolic\s+acid.{0,30}gpp"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        BiosynthesisTopic.ACID_SYNTHASE,
        re.compile(
            r"\b("
            r"thca[- ]?synthase\s+(?:enzym\w*|mechanism|fad)|"
            r"cbda[- ]?synthase\s+(?:enzym\w*|mechanism|fad)|"
            r"fad[- ]?dependent\s+oxidocyclase|"
            r"sirikantaramas\s+2004|taura\s+1996|"
            r"thcas\s+(?:mechanism|crystal|fad|oxidocyclase)|"
            r"cbdas\s+(?:mechanism|crystal|fad|oxidocyclase)|"
            r"glandular\s+trichome\s+(?:apoplast|secret\w*)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        BiosynthesisTopic.HETEROLOGOUS_EXPRESSION,
        re.compile(
            r"\b("
            r"heterologous\s+(?:expression|production).{0,30}cannabinoid|"
            r"yeast\s+(?:cannabinoid|cannabis)|"
            r"saccharomyces.{0,30}cannabinoid|"
            r"luo\s+2019|"
            r"cannabinoid.{0,30}(?:yeast|biomanufactur\w*|synbio|"
            r"synthetic\s+biology|industrial\s+production)|"
            r"galactose.{0,30}cannabinoid|"
            r"demetrix|ginkgo\s+(?:cannabinoid|cannabis)|"
            r"biosynthesis.{0,40}(?:pathway|yeast|heterologous)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_biosynthesis_rows() -> tuple[BiosynthesisRow, ...]:
    return _REGISTRY


def find_biosynthesis_rows(topic_or_name: str) -> tuple[BiosynthesisRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[BiosynthesisRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_biosynthesis_mention(text: str) -> tuple[BiosynthesisRow, ...]:
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
    BiosynthesisTopic.POLYKETIDE_ORIGIN: "Polyketide entry — OLS + OAC (olivetolic acid)",
    BiosynthesisTopic.PRENYLTRANSFERASE: "Prenyltransferase — CBGAS (CBGA formation)",
    BiosynthesisTopic.ACID_SYNTHASE: "Acid synthases — THCAS / CBDAS (oxidocyclases)",
    BiosynthesisTopic.HETEROLOGOUS_EXPRESSION: "Heterologous expression (Luo 2019 yeast)",
}


def render_markdown(rows: Iterable[BiosynthesisRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[BiosynthesisRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## Cannabinoid biosynthesis pathway registry")
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
            if r.enzyme_name:
                lines.append(f"  - Enzyme: {r.enzyme_name}")
            if r.ec_number:
                lines.append(f"  - EC: {r.ec_number}")
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
