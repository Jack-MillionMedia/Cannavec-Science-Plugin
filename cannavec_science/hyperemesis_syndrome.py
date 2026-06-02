"""Cannabinoid hyperemesis syndrome registry (spec 005 US3 / FR-003).

Research-grade clinical evidence on cannabinoid hyperemesis syndrome
(CHS) — diagnostic criteria, Rome IV functional GI framework,
treatment evidence, and cyclic-vomiting-vs-CHS differential. v0.4
returned 0 curated claims for CHS prompts and surfaced only a static
caution; v0.5 ships a curated registry under Constitution §IV
(researcher-only) with primary citations per §I.

Topic coverage:

- ``diagnostic_criteria`` — Sorensen 2017 systematic review (PMID
  28000146) and Allen 2004 original case series (PMID 15082584).
  Cyclic vomiting + abdominal pain + compulsive hot bathing in a
  chronic heavy cannabis user; resolves with cessation.
- ``rome_iv`` — Venkatesan 2019 (PMID 31480576) consensus criteria
  positioning CHS within the Rome IV functional GI disorder framework
  (a subtype of cyclic vomiting syndrome characterised by chronic
  cannabis exposure).
- ``capsaicin_treatment`` — Dezieck 2017 (PMID 28494183) acute-phase
  topical capsaicin treatment with caveat that cessation remains
  the only definitive long-term resolution.
- ``cyclic_vomiting_dx`` — CVS vs CHS differential and post-
  legalization ED epidemiology (Kim 2018 PMID 30049481).

Each row carries `to_claim()` returning a typed Claim, identifier-
anchored citations per §I, and is matched by a topic-keyword regex
detector. The module is reference-only.

The existing static safety caution ("Cannabis hyperemesis syndrome is
paradoxical and requires cessation, not adjustment of cannabis use")
in :mod:`cannavec_science.safety` is preserved unchanged — these
curated rows complement the caution by providing the primary
citations a researcher needs.
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
    "HyperemesisSyndromeCitation",
    "HyperemesisSyndromeRow",
    "HyperemesisSyndromeTopic",
    "all_hyperemesis_syndrome_rows",
    "find_hyperemesis_syndrome_rows",
    "detect_hyperemesis_syndrome_mention",
    "render_markdown",
]


class HyperemesisSyndromeTopic:
    DIAGNOSTIC_CRITERIA = "diagnostic_criteria"
    ROME_IV = "rome_iv"
    CAPSAICIN_TREATMENT = "capsaicin_treatment"
    CYCLIC_VOMITING_DX = "cyclic_vomiting_dx"


@dataclass(frozen=True)
class HyperemesisSyndromeCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class HyperemesisSyndromeRow:
    """One curated CHS primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[HyperemesisSyndromeCitation, ...]
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_clinical_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"hyperemesis-syndrome row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"hyperemesis-syndrome row {self.name!r} citation "
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
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_clinical_notes": list(self.key_clinical_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_SORENSEN_2017 = HyperemesisSyndromeCitation(
    label="Sorensen CJ et al., J Med Toxicol 2017, cannabinoid hyperemesis "
          "syndrome — diagnosis, pathophysiology, and treatment (systematic "
          "review of 64 published case-series and case-reports)",
    pmid="28000146", year=2017,
)
_ALLEN_2004 = HyperemesisSyndromeCitation(
    label="Allen JH et al., Gut 2004, cannabinoid hyperemesis — cyclical "
          "hyperemesis in association with chronic cannabis abuse (original "
          "9-case series naming the syndrome)",
    pmid="15082584", year=2004,
)
_SIMONETTO_2012 = HyperemesisSyndromeCitation(
    label="Simonetto DA et al., Mayo Clin Proc 2012, cannabinoid "
          "hyperemesis — a case series of 98 patients",
    pmid="22305024", year=2012,
)
_VENKATESAN_2019 = HyperemesisSyndromeCitation(
    label="Venkatesan T et al., Neurogastroenterol Motil 2019, ACG "
          "and CAPS expert review on cyclic vomiting syndrome — including "
          "CHS diagnostic considerations within the Rome IV framework",
    pmid="31480576", year=2019,
)
_DEZIECK_2017 = HyperemesisSyndromeCitation(
    label="Dezieck L et al., Clin Toxicol 2017, capsaicin cream for "
          "treatment of cannabinoid hyperemesis syndrome — case series",
    pmid="28494183", year=2017,
)
_RICHARDS_2017 = HyperemesisSyndromeCitation(
    label="Richards JR et al., Ann Pharmacother 2017, treatment of "
          "cannabinoid hyperemesis syndrome — a systematic review",
    pmid="28634640", year=2017,
)
_KIM_2018 = HyperemesisSyndromeCitation(
    label="Kim HS et al., BMJ Open 2018, cyclic vomiting presentations "
          "following marijuana liberalization in Colorado — emergency "
          "department visits before and after legalization",
    pmid="30049481", year=2018,
)


# ── Registry rows ──────────────────────────────────────────────────────


_DIAGNOSTIC_CRITERIA = HyperemesisSyndromeRow(
    name="CHS diagnostic criteria — Sorensen 2017 systematic review",
    topic=HyperemesisSyndromeTopic.DIAGNOSTIC_CRITERIA,
    claim_text=(
        "Sorensen 2017 systematic review of 64 published CHS case-series "
        "and case-reports synthesised the diagnostic profile: cyclical "
        "severe nausea and vomiting; abdominal pain (especially "
        "epigastric); compulsive hot bathing or showering (relief); "
        "weight loss; resolution with cannabis cessation. Long-duration "
        "(typically > 1 year) heavy cannabis use is a near-universal "
        "feature of confirmed cases. The Allen 2004 original 9-case "
        "series first named the syndrome; Simonetto 2012 (98-case Mayo "
        "Clinic series) is the largest single-institution series. "
        "Differential diagnosis must exclude cyclic vomiting syndrome "
        "(CVS), gastroparesis, intracranial mass, and other organic "
        "causes — CHS is largely a diagnosis of exclusion + cannabis-"
        "cessation response."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    # Case-series systematic review — not a clinical-trial SR. Tier
    # SINGLE_ARM_OR_MECH so the grade aggregation stays honest (Level
    # C on a case-series SR is the right ceiling).
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_SORENSEN_2017, _ALLEN_2004, _SIMONETTO_2012),
    key_clinical_notes=(
        "Compulsive hot-water bathing is the most specific clinical "
        "feature distinguishing CHS from other cyclic vomiting "
        "syndromes — patients report transient symptom relief from "
        "showers / baths at ≥ 41 °C.",
        "Pathophysiology is incompletely understood; competing "
        "hypotheses involve TRPV1 dysregulation, CB1-receptor "
        "downregulation, and chronic exogenous cannabinoid disruption "
        "of brainstem emetic circuitry.",
        "Diagnostic uncertainty is high — Sorensen 2017 estimates "
        "that some confirmed-CHS series likely include misdiagnosed "
        "CVS cases. The cessation-response criterion is therefore "
        "essential.",
    ),
)


_ROME_IV = HyperemesisSyndromeRow(
    name="CHS within Rome IV — Venkatesan 2019 ACG/CAPS expert review",
    topic=HyperemesisSyndromeTopic.ROME_IV,
    claim_text=(
        "The Rome IV functional GI disorder framework (Stanghellini 2016) "
        "positions cyclic vomiting syndrome (CVS) as a distinct entity, "
        "and the Venkatesan 2019 ACG/CAPS (Cyclic Vomiting Syndrome "
        "Association) expert review explicitly addresses CHS as a "
        "diagnostic consideration within the cannabis-using CVS subset. "
        "Per the consensus, cannabis cessation is the diagnostic and "
        "therapeutic test of choice when CHS is suspected in a chronic "
        "cannabis user presenting with cyclic vomiting; failure to "
        "respond to cessation argues against CHS and supports investigating "
        "other CVS aetiologies."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    # Expert-consensus document — not a clinical-trial SR. Honest tier
    # is SINGLE_ARM_OR_MECH; consensus statements cap at Level C.
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_VENKATESAN_2019,),
    key_clinical_notes=(
        "The CVS prodromal-emetic-recovery-interval phase structure is "
        "shared between CHS and idiopathic CVS — the cannabis-cessation "
        "response is the differentiator.",
        "Rome IV positions both CHS and CVS as 'functional' disorders "
        "(no structural pathology) — diagnostic criteria are clinical, "
        "not laboratory or imaging based.",
    ),
)


_CAPSAICIN_TREATMENT = HyperemesisSyndromeRow(
    name="Topical capsaicin acute-phase CHS treatment — Dezieck 2017",
    topic=HyperemesisSyndromeTopic.CAPSAICIN_TREATMENT,
    claim_text=(
        "Topical capsaicin cream (0.025-0.075%) applied to the abdomen / "
        "back has been reported in case series (Dezieck 2017, Richards "
        "2017 SR) to acutely reduce CHS-associated nausea and vomiting, "
        "presumed to act via TRPV1 agonism that mimics the symptomatic "
        "relief patients report from hot-water bathing. Capsaicin is "
        "useful only in the acute hyperemetic phase; it does not "
        "prevent recurrence. The only definitive long-term resolution "
        "is sustained cannabis cessation. Anti-emetic monotherapy "
        "(ondansetron, metoclopramide) is typically inadequate for "
        "the hyperemetic phase; benzodiazepines and haloperidol have "
        "been used as adjuncts with limited high-quality evidence."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.D,
    source_tier=SourceTier.PREPRINT_OR_SMALL,
    citations=(_DEZIECK_2017, _RICHARDS_2017),
    key_clinical_notes=(
        "Capsaicin cream evidence base is case-series only — no RCT "
        "has been published. Effect size estimates are uncertain.",
        "TRPV1-agonist mechanism is theoretically consistent with the "
        "hot-water-relief phenomenology, but the mechanistic link is "
        "inferred, not directly established.",
        "Cannabis cessation remains the only treatment with consistent "
        "long-term efficacy. Multi-modal cessation support (CBT for CUD, "
        "motivational enhancement) is recommended.",
    ),
)


_CYCLIC_VOMITING_DIFFERENTIAL = HyperemesisSyndromeRow(
    name="CHS vs CVS differential and post-legalization ED epidemiology",
    topic=HyperemesisSyndromeTopic.CYCLIC_VOMITING_DX,
    claim_text=(
        "Kim 2018 BMJ Open analysed Colorado emergency-department data "
        "before and after recreational-cannabis legalization (2014) and "
        "found that cyclic-vomiting ED presentations per 100,000 ED "
        "visits approximately doubled in the post-legalization period, "
        "consistent with previously under-diagnosed CHS becoming more "
        "common (or more recognised) as cannabis use prevalence rose. "
        "Differential diagnosis remains important: CHS requires chronic "
        "cannabis exposure and cessation-response; idiopathic CVS, "
        "gastroparesis (especially diabetic), intracranial mass, and "
        "metabolic causes must be excluded. The post-legalization data "
        "also raise calibration concerns — some excess presentations may "
        "be acute cannabis intoxication or edible-overdose, not true CHS."
    ),
    claim_type=ClaimType.EDUCATIONAL,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_KIM_2018, _VENKATESAN_2019),
    key_clinical_notes=(
        "Kim 2018 used ICD-coding-based identification of cyclic-"
        "vomiting cases; the granularity does not separate CHS from "
        "idiopathic CVS within the cyclic-vomiting bucket. The "
        "interpretation that legalization-associated rise reflects "
        "increased CHS is inferential.",
        "The post-legalization rise in acute-cannabis ED presentations "
        "is well-documented across multiple US states — it is "
        "broader than the CHS-specific signal.",
    ),
)


_REGISTRY: tuple[HyperemesisSyndromeRow, ...] = (
    _DIAGNOSTIC_CRITERIA,
    _ROME_IV,
    _CAPSAICIN_TREATMENT,
    _CYCLIC_VOMITING_DIFFERENTIAL,
)


# ── Topic-keyword detectors ────────────────────────────────────────────


_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        HyperemesisSyndromeTopic.DIAGNOSTIC_CRITERIA,
        re.compile(
            r"\b("
            r"cannabinoid\s+hyperemesis|"
            r"cannabis\s+hyperemesis|"
            r"chs\s+(?:diagnost\w*|criteria|syndrome|hyperemes\w*)|"
            r"hyperemesis\s+syndrome|"
            r"allen\s+2004|sorensen\s+2017|simonetto\s+2012|"
            r"hot[- ]?water\s+bath\w*|"
            r"compulsive\s+(?:bath\w*|shower\w*)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        HyperemesisSyndromeTopic.ROME_IV,
        re.compile(
            r"\b("
            r"rome\s+iv|rome[- ]?4|"
            r"functional\s+gi\s+(?:disorder|criteria|framework)|"
            r"venkatesan\s+2019|"
            r"acg.{0,15}caps|caps.{0,15}cyclic"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        HyperemesisSyndromeTopic.CAPSAICIN_TREATMENT,
        re.compile(
            r"\b("
            r"capsaicin|"
            r"trpv1\s+agonist\s+(?:cream|topical|treatment)|"
            r"dezieck\s+2017|richards\s+2017|"
            r"(?:chs|hyperemesis)\s+(?:treatment|management|therapy)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        HyperemesisSyndromeTopic.CYCLIC_VOMITING_DX,
        re.compile(
            r"\b("
            r"cyclic\s+vomiting\s+syndrome|cvs\s+(?:vs|differential|cyclic)|"
            r"(?:chs|hyperemesis).{0,20}(?:differential|cvs)|"
            r"kim\s+2018\s+(?:colorado|legali[sz]ation|cyclic)|"
            r"post[- ]?legali[sz]ation\s+(?:ed|emergency|chs|cyclic|cannabis)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_hyperemesis_syndrome_rows() -> tuple[HyperemesisSyndromeRow, ...]:
    return _REGISTRY


def find_hyperemesis_syndrome_rows(
    topic_or_name: str,
) -> tuple[HyperemesisSyndromeRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[HyperemesisSyndromeRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_hyperemesis_syndrome_mention(
    text: str,
) -> tuple[HyperemesisSyndromeRow, ...]:
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
    HyperemesisSyndromeTopic.DIAGNOSTIC_CRITERIA: "CHS diagnostic criteria",
    HyperemesisSyndromeTopic.ROME_IV: "CHS within Rome IV / cyclic vomiting framework",
    HyperemesisSyndromeTopic.CAPSAICIN_TREATMENT: "Topical capsaicin (acute-phase treatment)",
    HyperemesisSyndromeTopic.CYCLIC_VOMITING_DX: "CVS vs CHS differential + epidemiology",
}


def render_markdown(rows: Iterable[HyperemesisSyndromeRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[HyperemesisSyndromeRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## Cannabinoid hyperemesis syndrome registry")
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
