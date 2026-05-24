"""eCBome enzyme-inhibitor pharmacology registry (spec 005 US4 / FR-004).

Research-grade drug-development translation of the endocannabinoidome
(eCBome) — the clinical-trial landscape for FAAH and MAGL inhibitors
PLUS the BIA 10-2474 Phase 1 safety-disaster reference with explicit
off-target-serine-hydrolase disambiguation. v0.4 surfaced the static
eCBome enzyme reference (FAAH, MAGL) but no inhibitor pharmacology;
v0.5 ships a curated registry under Constitution §IV (researcher-only)
with primary citations per §I.

Topic coverage:

- ``faah_inhibitor_efficacy`` — PF-04457845 (Pfizer) Phase 2 cannabis
  withdrawal trial (D'Souza 2019 PMID 30985083) and Phase 2 osteoarthritis-
  pain trial (Huggins 2012 PMID 22910298). The two best-developed
  clinical translation stories for on-target FAAH inhibition.
- ``faah_inhibitor_safety_disaster`` — BIA 10-2474 (Bial) Phase 1
  Rennes 2016 fatal-and-serious-adverse-event disaster (Kerbrat 2016
  PMID 27806243). CRITICAL — the disaster is attributed to OFF-TARGET
  serine-hydrolase inhibition (van Esbroeck 2017 PMID 28912346), NOT
  to on-target FAAH biology. A researcher conflating BIA 10-2474
  toxicity with FAAH-inhibitor risk in general will reach wrong
  drug-development conclusions.
- ``magl_inhibitor`` — MAGL (monoacylglycerol lipase) inhibitor
  pharmacology. ABX-1431 / lorcaserin / lu AG06466 era — Cisar 2018
  (PMID 29498523) ABX-1431 SAR / pharmacology paper.
- ``dual_inhibitor`` — JZL195 dual FAAH / MAGL inhibitor mechanism
  reference (Long 2009 PMID 19429692) — endocannabinoid-tone elevation
  via simultaneous AEA + 2-AG protection.

Each row carries `to_claim()` returning a typed Claim, identifier-
anchored citations per §I, and is matched by a topic-keyword regex
detector. The module is reference-only.
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
    "EcbomeInhibitorCitation",
    "EcbomeInhibitorRow",
    "EcbomeInhibitorTopic",
    "all_ecbome_inhibitor_rows",
    "find_ecbome_inhibitor_rows",
    "detect_ecbome_inhibitor_mention",
    "render_markdown",
]


class EcbomeInhibitorTopic:
    FAAH_INHIBITOR_EFFICACY = "faah_inhibitor_efficacy"
    FAAH_INHIBITOR_SAFETY_DISASTER = "faah_inhibitor_safety_disaster"
    MAGL_INHIBITOR = "magl_inhibitor"
    DUAL_INHIBITOR = "dual_inhibitor"


@dataclass(frozen=True)
class EcbomeInhibitorCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class EcbomeInhibitorRow:
    """One curated eCBome-inhibitor primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[EcbomeInhibitorCitation, ...]
    target_protein: str = ""   # FAAH / MAGL / both
    compound_id: str = ""      # e.g. PF-04457845, BIA 10-2474, ABX-1431
    chembl_id: str = ""        # ChEMBL identifier when applicable
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"ecbome-inhibitor row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"ecbome-inhibitor row {self.name!r} citation "
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
            "target_protein": self.target_protein,
            "compound_id": self.compound_id,
            "chembl_id": self.chembl_id,
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_notes": list(self.key_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_DSOUZA_2019 = EcbomeInhibitorCitation(
    label="D'Souza DC et al., Lancet Psychiatry 2019, efficacy and safety "
          "of a fatty acid amide hydrolase inhibitor (PF-04457845) in the "
          "treatment of cannabis withdrawal and dependence in men — "
          "double-blind randomised placebo-controlled Phase 2a trial",
    pmid="30985083", year=2019,
)
_HUGGINS_2012 = EcbomeInhibitorCitation(
    label="Huggins JP et al., Pain 2012, an efficient randomised, "
          "placebo-controlled clinical trial with the irreversible "
          "fatty acid amide hydrolase-1 inhibitor PF-04457845, which "
          "modulates endocannabinoids but fails to induce effective "
          "analgesia in patients with pain due to osteoarthritis of the "
          "knee",
    pmid="22910298", year=2012,
)
_KERBRAT_2016 = EcbomeInhibitorCitation(
    label="Kerbrat A et al., NEJM 2016, acute neurologic disorder from "
          "an inhibitor of fatty acid amide hydrolase (BIA 10-2474) — "
          "Rennes Phase 1 fatal-and-serious-adverse-event report",
    pmid="27806243", year=2016,
)
_VAN_ESBROECK_2017 = EcbomeInhibitorCitation(
    label="van Esbroeck ACM et al., Science 2017, activity-based protein "
          "profiling reveals off-target proteins of the FAAH inhibitor "
          "BIA 10-2474 (the molecular explanation for the Rennes "
          "disaster — off-target inhibition of multiple lipases, NOT "
          "on-target FAAH biology)",
    pmid="28912346", year=2017,
)
_CISAR_2018 = EcbomeInhibitorCitation(
    label="Cisar JS et al., J Med Chem 2018, identification of ABX-1431, "
          "a selective inhibitor of monoacylglycerol lipase (MAGL) and "
          "clinical candidate for treatment of neurological disorders",
    pmid="29498523", year=2018,
)
_LONG_2009 = EcbomeInhibitorCitation(
    label="Long JZ et al., Nat Chem Biol 2009, dual blockade of fatty "
          "acid amide hydrolase and monoacylglycerol lipase produces "
          "augmented endocannabinoid anandamide signaling — JZL195 "
          "mechanism characterisation",
    pmid="19429692", year=2009,
)


# ── Registry rows ──────────────────────────────────────────────────────


_PF_04457845_CANNABIS_WITHDRAWAL = EcbomeInhibitorRow(
    name="PF-04457845 (Pfizer FAAH inhibitor) — cannabis withdrawal Phase 2a",
    topic=EcbomeInhibitorTopic.FAAH_INHIBITOR_EFFICACY,
    claim_text=(
        "PF-04457845 (Pfizer; irreversible covalent FAAH inhibitor) showed "
        "evidence of efficacy in a double-blind, placebo-controlled Phase "
        "2a trial in men with cannabis use disorder during medically-"
        "supervised cannabis withdrawal (D'Souza 2019 Lancet Psychiatry, "
        "n=70, 4 mg PO daily × 28 days). The PF-04457845 arm experienced "
        "less withdrawal-symptom severity (significantly lower CWS "
        "scores) and reduced cannabis self-administration vs placebo. The "
        "trial is the proof-of-concept for FAAH inhibition as a cannabis-"
        "withdrawal pharmacotherapy and the only positive Phase 2 trial "
        "in this indication."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    target_protein="FAAH (fatty acid amide hydrolase; UniProt O00519)",
    compound_id="PF-04457845",
    chembl_id="CHEMBL2105751",
    citations=(_DSOUZA_2019,),
    key_notes=(
        "Single-trial Level B (Phase 2a; n=70 males only). Level A would "
        "require independent replication or a Phase 3 trial — neither "
        "exists yet for PF-04457845 in cannabis-withdrawal.",
        "Mechanism: FAAH inhibition raises endogenous anandamide (AEA), "
        "PEA, and OEA tone — the hypothesised endocannabinoid-tone "
        "elevation is presumed to attenuate withdrawal dysphoria.",
        "PF-04457845 was developed for inflammatory pain and OA (see "
        "Huggins 2012 — negative trial there) before being repositioned "
        "to cannabis-withdrawal.",
    ),
)


_PF_04457845_OSTEOARTHRITIS = EcbomeInhibitorRow(
    name="PF-04457845 (Pfizer FAAH inhibitor) — osteoarthritis pain Phase 2",
    topic=EcbomeInhibitorTopic.FAAH_INHIBITOR_EFFICACY,
    claim_text=(
        "PF-04457845 did NOT show clinically meaningful analgesia in a "
        "randomised placebo- and naproxen-controlled Phase 2 trial in "
        "knee-OA pain (Huggins 2012 Pain, n=74). Despite verified target "
        "engagement (peripheral and central FAAH activity reduced, "
        "endocannabinoid tone elevated), PF-04457845 failed to reduce "
        "the WOMAC-pain primary endpoint vs placebo; naproxen produced "
        "the expected analgesia. The negative result is influential — "
        "it argues against an exclusive FAAH-mediated mechanism in "
        "OA pain and explains the field's redirection toward "
        "cannabis-withdrawal and PTSD indications."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    target_protein="FAAH (fatty acid amide hydrolase; UniProt O00519)",
    compound_id="PF-04457845",
    chembl_id="CHEMBL2105751",
    citations=(_HUGGINS_2012,),
    key_notes=(
        "Negative trial with verified target engagement is the most "
        "informative possible outcome — it rules out PK / dose / "
        "engagement issues as confounders and isolates the "
        "FAAH-mediated-mechanism hypothesis as the failure point.",
        "The Huggins 2012 result is essential pedagogical context "
        "for any researcher considering FAAH inhibition for a "
        "pain indication.",
    ),
)


_BIA_10_2474_DISASTER = EcbomeInhibitorRow(
    name="BIA 10-2474 (Bial) Phase 1 Rennes 2016 disaster — OFF-TARGET, not FAAH",
    topic=EcbomeInhibitorTopic.FAAH_INHIBITOR_SAFETY_DISASTER,
    claim_text=(
        "CRITICAL DISAMBIGUATION — the BIA 10-2474 (Bial) Phase 1 "
        "disaster (Rennes, January 2016; 1 death, 4 serious neurological "
        "injuries; Kerbrat 2016 NEJM) is attributed to OFF-TARGET serine-"
        "hydrolase inhibition by BIA 10-2474, NOT to on-target FAAH "
        "biology. Activity-based protein profiling (van Esbroeck 2017 "
        "Science) demonstrated BIA 10-2474 inhibits multiple lipases "
        "and serine hydrolases beyond FAAH at therapeutic concentrations "
        "— it is a poor-quality FAAH inhibitor with poor selectivity. "
        "PF-04457845, by contrast, is a high-selectivity covalent FAAH "
        "inhibitor with no comparable off-target liability and a clean "
        "Phase 1-2 safety profile across multiple indications. A "
        "researcher who conflates BIA 10-2474 toxicology with FAAH-"
        "inhibitor risk in general reaches the wrong drug-development "
        "conclusion."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    target_protein="FAAH (claimed) + off-target lipases / serine hydrolases (actual)",
    compound_id="BIA 10-2474",
    chembl_id="CHEMBL3989775",
    citations=(_KERBRAT_2016, _VAN_ESBROECK_2017),
    key_notes=(
        "The off-target serine-hydrolase disambiguation is the row's "
        "central pedagogical content — every FAAH-inhibitor literature "
        "citation MUST distinguish on-target (PF-04457845-class) from "
        "off-target (BIA 10-2474-class) chemistry.",
        "van Esbroeck 2017 (Science) is the definitive activity-based "
        "protein profiling paper establishing the off-target target "
        "set; the BIA 10-2474 disaster is now the textbook example "
        "of why selectivity-screening must be done before Phase 1.",
        "The Bial trial also had multiple-ascending-dose protocol design "
        "issues (rapid dose escalation; no adequate inter-cohort safety "
        "review) that contributed to the disaster magnitude.",
    ),
)


_MAGL_ABX_1431 = EcbomeInhibitorRow(
    name="ABX-1431 / Lu AG06466 — selective MAGL inhibitor",
    topic=EcbomeInhibitorTopic.MAGL_INHIBITOR,
    claim_text=(
        "ABX-1431 (Abide Therapeutics / H. Lundbeck Lu AG06466) is a "
        "selective covalent MAGL (monoacylglycerol lipase; UniProt Q99685) "
        "inhibitor that raises endogenous 2-arachidonoylglycerol (2-AG) "
        "tone — the cognate ligand of CB1 and CB2 — providing pharmacologic "
        "augmentation of endocannabinoid signalling without exogenous "
        "cannabinoid administration. Cisar 2018 (J Med Chem) described the "
        "ABX-1431 SAR campaign that achieved MAGL selectivity over FAAH "
        "and other serine hydrolases. Clinical development has targeted "
        "Tourette syndrome, neuropathic pain, and other neurological "
        "indications. ABX-1431 / Lu AG06466 represents the lead MAGL-"
        "inhibitor class in clinical development; Phase 2 results are "
        "mixed and the indication landscape is still being defined."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    target_protein="MAGL (monoacylglycerol lipase; UniProt Q99685)",
    compound_id="ABX-1431 / Lu AG06466",
    chembl_id="CHEMBL4302093",
    citations=(_CISAR_2018,),
    key_notes=(
        "Selectivity over FAAH is the key SAR challenge for MAGL "
        "inhibitors — the two enzymes share a serine-hydrolase "
        "catalytic motif but distinct substrate preferences.",
        "2-AG is ~200-fold more abundant than AEA in the CNS; MAGL "
        "inhibition has larger effect on absolute endocannabinoid "
        "tone than FAAH inhibition.",
        "Chronic MAGL blockade has produced CB1-receptor desensitisation "
        "and tolerance in preclinical models — a translational caveat "
        "for sustained-dose clinical use.",
    ),
)


_JZL195_DUAL = EcbomeInhibitorRow(
    name="JZL195 — dual FAAH + MAGL inhibitor mechanism reference",
    topic=EcbomeInhibitorTopic.DUAL_INHIBITOR,
    claim_text=(
        "JZL195 (Long 2009 Nat Chem Biol) is the prototype dual "
        "FAAH + MAGL inhibitor — simultaneously raises both anandamide "
        "(via FAAH blockade) and 2-arachidonoylglycerol (via MAGL "
        "blockade) endogenous tones. JZL195 is a research-tool compound, "
        "not a clinical candidate; its primary use is preclinical "
        "validation of dual-target endocannabinoid-tone elevation. The "
        "dual-blockade approach produces stronger CB1-receptor-mediated "
        "behavioural effects than single-target inhibitors but also "
        "produces stronger Δ⁹-THC-like 'tetrad' effects (catalepsy, "
        "hypothermia, hypolocomotion, analgesia), suggesting that "
        "dual-target chronic dosing would produce cannabis-like "
        "subjective effects clinically."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.D,
    source_tier=SourceTier.PREPRINT_OR_SMALL,
    target_protein="FAAH + MAGL (dual; UniProt O00519 + Q99685)",
    compound_id="JZL195",
    chembl_id="CHEMBL2364146",
    citations=(_LONG_2009,),
    key_notes=(
        "JZL195 has not progressed to clinical development; clinical "
        "interest in dual FAAH / MAGL inhibition is largely theoretical.",
        "The 'cannabimimetic full agonist'-like profile of dual "
        "inhibition is the principal translational caveat — selective "
        "single-target inhibitors are preferred for non-cannabis-"
        "subjective-effect therapeutic indications.",
    ),
)


_REGISTRY: tuple[EcbomeInhibitorRow, ...] = (
    _PF_04457845_CANNABIS_WITHDRAWAL,
    _PF_04457845_OSTEOARTHRITIS,
    _BIA_10_2474_DISASTER,
    _MAGL_ABX_1431,
    _JZL195_DUAL,
)


# ── Topic-keyword detectors ────────────────────────────────────────────


_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        EcbomeInhibitorTopic.FAAH_INHIBITOR_EFFICACY,
        re.compile(
            r"\b("
            r"pf[- ]?04457845|"
            r"pfizer\s+faah|"
            r"faah\s+(?:inhibitor|inhibition)\s+(?:cannabis|withdrawal|trial|phase|clinical)|"
            r"d.?souza\s+2019|huggins\s+2012|"
            r"faah\s+(?:inhibitor|inhibition).{0,40}(?:osteoarthritis|pain|cannabis|withdrawal)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        EcbomeInhibitorTopic.FAAH_INHIBITOR_SAFETY_DISASTER,
        re.compile(
            r"\b("
            r"bia\s*10[- ]?2474|"
            r"bia[- ]?10[- ]?2474|"
            r"rennes\s+(?:disaster|phase\s+1|trial|2016)|"
            r"kerbrat\s+2016|van\s+esbroeck\s+2017|"
            r"bial\s+(?:disaster|phase\s+1|trial|2016)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        EcbomeInhibitorTopic.MAGL_INHIBITOR,
        re.compile(
            r"\b("
            r"abx[- ]?1431|"
            r"lu\s*ag\s*06466|"
            r"magl\s+(?:inhibitor|inhibition)|"
            r"monoacylglycerol\s+lipase\s+(?:inhibitor|inhibition)|"
            r"cisar\s+2018|"
            r"2[- ]?ag\s+(?:tone|elevation|degradation)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        EcbomeInhibitorTopic.DUAL_INHIBITOR,
        re.compile(
            r"\b("
            r"jzl195|jzl[- ]?195|"
            r"dual\s+(?:faah|magl)\s+(?:and|&)\s+(?:faah|magl)|"
            r"dual\s+faah[- ]?magl|"
            r"long\s+2009|"
            r"dual[- ]?target\s+endocannabinoid"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_ecbome_inhibitor_rows() -> tuple[EcbomeInhibitorRow, ...]:
    return _REGISTRY


def find_ecbome_inhibitor_rows(
    topic_or_name: str,
) -> tuple[EcbomeInhibitorRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[EcbomeInhibitorRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_ecbome_inhibitor_mention(
    text: str,
) -> tuple[EcbomeInhibitorRow, ...]:
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
    EcbomeInhibitorTopic.FAAH_INHIBITOR_EFFICACY: "FAAH inhibitor efficacy (PF-04457845)",
    EcbomeInhibitorTopic.FAAH_INHIBITOR_SAFETY_DISASTER: "FAAH 'safety disaster' — BIA 10-2474 (OFF-TARGET, not on-target FAAH)",
    EcbomeInhibitorTopic.MAGL_INHIBITOR: "MAGL inhibitor pharmacology (ABX-1431 / Lu AG06466)",
    EcbomeInhibitorTopic.DUAL_INHIBITOR: "Dual FAAH + MAGL inhibitor mechanism (JZL195)",
}


def render_markdown(rows: Iterable[EcbomeInhibitorRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[EcbomeInhibitorRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## eCBome inhibitor pharmacology registry")
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
            if r.target_protein:
                lines.append(f"  - Target: {r.target_protein}")
            if r.compound_id:
                lines.append(f"  - Compound: {r.compound_id}")
            if r.chembl_id:
                lines.append(f"  - ChEMBL: {r.chembl_id}")
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
