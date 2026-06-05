"""Deterministic evidence synthesis from typed claims.

Given a list of :class:`cannavec.evidence.Claim` objects (or an
:class:`cannavec.answer.Answer`), produce a stable, deterministic
synthesis suitable for a research-brief introduction:

- Group claims by grade and by claim-type.
- Compute the rolled-up provenance score across cited sources.
- Surface the contradictions (via :mod:`cannavec.contradiction`).
- Render a Markdown synthesis with a stable section order.

This is *not* an LLM summariser. It is a pure-function rollup. The
narrative wording is whatever was already on the typed Claims; this
module composes the structure.

Design rules:

- Deterministic. Same input → same output.
- Pure (no I/O, no LLM).
- Stable section order so eval harnesses can score against it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from cannavec_science.answer import Answer, Citation
from cannavec_science.contradiction import Contradiction, scan_claims
from cannavec_science.evidence import (
    Claim,
    ClaimType,
    EvidenceLevel,
    ProvenanceScore,
    Source,
    source_authority_weight,
)


# Stable display order for grades — strongest first.
_GRADE_ORDER: tuple[EvidenceLevel, ...] = (
    EvidenceLevel.A,
    EvidenceLevel.B,
    EvidenceLevel.C,
    EvidenceLevel.D,
    EvidenceLevel.E,
    EvidenceLevel.UNSUPPORTED,
)


# Stable display order for claim types — clinical first, opinion last.
_CLAIM_TYPE_ORDER: tuple[ClaimType, ...] = (
    ClaimType.CLINICAL_EFFICACY,
    ClaimType.DOSING,
    ClaimType.PHARMACOKINETIC,
    ClaimType.DRUG_INTERACTION,
    ClaimType.SAFETY,
    ClaimType.MECHANISM,
    ClaimType.PHYTOCHEMISTRY_QUANTITY,
    ClaimType.LEGAL_REGULATORY,
    ClaimType.CULTIVATION_PARAMETER,
    ClaimType.MARKET_DATA,
    ClaimType.EDUCATIONAL,
    ClaimType.OPINION,
)


@dataclass
class GradeBucket:
    grade: EvidenceLevel
    claims: list[Claim] = field(default_factory=list)


@dataclass
class ClaimTypeBucket:
    claim_type: ClaimType
    claims: list[Claim] = field(default_factory=list)


@dataclass
class EvidenceSynthesis:
    """Rolled-up evidence picture across an answer's claims."""

    n_claims: int
    by_grade: list[GradeBucket]
    by_claim_type: list[ClaimTypeBucket]
    highest_grade: EvidenceLevel
    weakest_grade: EvidenceLevel
    n_with_primary_source: int
    n_with_missing_disclosures: int
    n_with_pre_registration: int
    distinct_sources: int
    mean_source_authority: float
    mean_provenance_score: float
    contradictions: list[Contradiction]
    cited_pmids: list[str]
    cited_dois: list[str]

    def to_dict(self) -> dict:
        return {
            "n_claims": self.n_claims,
            "highest_grade": self.highest_grade.value,
            "weakest_grade": self.weakest_grade.value,
            "n_with_primary_source": self.n_with_primary_source,
            "n_with_missing_disclosures": self.n_with_missing_disclosures,
            "n_with_pre_registration": self.n_with_pre_registration,
            "distinct_sources": self.distinct_sources,
            "mean_source_authority": round(self.mean_source_authority, 3),
            "mean_provenance_score": round(self.mean_provenance_score, 3),
            "n_contradictions": len(self.contradictions),
            "cited_pmids": list(self.cited_pmids),
            "cited_dois": list(self.cited_dois),
            "by_grade": [
                {
                    "grade": b.grade.value,
                    "n_claims": len(b.claims),
                }
                for b in self.by_grade if b.claims
            ],
            "by_claim_type": [
                {
                    "claim_type": b.claim_type.value,
                    "n_claims": len(b.claims),
                }
                for b in self.by_claim_type if b.claims
            ],
        }


def synthesise(claims: Iterable[Claim]) -> EvidenceSynthesis:
    """Roll up a list of claims into an :class:`EvidenceSynthesis`."""
    claim_list = list(claims)
    n = len(claim_list)

    by_grade_map: dict[EvidenceLevel, list[Claim]] = defaultdict(list)
    by_type_map: dict[ClaimType, list[Claim]] = defaultdict(list)
    n_primary = 0
    n_missing_disclosures = 0
    n_pre_reg = 0
    distinct_sources: dict[tuple[str | None, str | None, str | None], Source] = {}
    authorities: list[float] = []
    provenance_scores: list[float] = []
    cited_pmids: list[str] = []
    cited_dois: list[str] = []

    from cannavec_science.evidence import missing_disclosures

    for c in claim_list:
        grade = c.best_supportable_grade()
        by_grade_map[grade].append(c)
        by_type_map[c.claim_type].append(c)
        if any(s.pmid or s.doi or s.url for s in c.sources):
            n_primary += 1
        if missing_disclosures(c.claim_type, c.disclosures_present):
            n_missing_disclosures += 1
        if any(s.pre_registered for s in c.sources):
            n_pre_reg += 1
        for s in c.sources:
            key = (s.pmid, s.doi, s.url)
            if key in distinct_sources:
                continue
            distinct_sources[key] = s
            authorities.append(source_authority_weight(s))
            link_factor = (0.0 if s.retraction_status == "retracted" else 1.0)
            retraction_factor = {
                "clean": 1.0,
                "expression_of_concern": 0.5,
                "under_correction": 0.3,
                "retracted": 0.0,
            }.get(s.retraction_status, 1.0)
            p = ProvenanceScore(
                link_liveness_factor=link_factor,
                retraction_factor=retraction_factor,
                source_authority_weight=source_authority_weight(s),
            )
            provenance_scores.append(p.score)
            if s.pmid and s.pmid not in cited_pmids:
                cited_pmids.append(s.pmid)
            if s.doi and s.doi not in cited_dois:
                cited_dois.append(s.doi)

    by_grade = [
        GradeBucket(grade=g, claims=by_grade_map.get(g, []))
        for g in _GRADE_ORDER
    ]
    by_type = [
        ClaimTypeBucket(claim_type=t, claims=by_type_map.get(t, []))
        for t in _CLAIM_TYPE_ORDER
    ]

    if claim_list:
        grades_present = [c.best_supportable_grade() for c in claim_list]
        highest = max(grades_present, key=lambda g: g.rank)
        weakest = min(grades_present, key=lambda g: g.rank)
    else:
        highest = EvidenceLevel.UNSUPPORTED
        weakest = EvidenceLevel.UNSUPPORTED

    contradictions = list(scan_claims([c.text for c in claim_list]))

    return EvidenceSynthesis(
        n_claims=n,
        by_grade=by_grade,
        by_claim_type=by_type,
        highest_grade=highest,
        weakest_grade=weakest,
        n_with_primary_source=n_primary,
        n_with_missing_disclosures=n_missing_disclosures,
        n_with_pre_registration=n_pre_reg,
        distinct_sources=len(distinct_sources),
        mean_source_authority=(
            sum(authorities) / len(authorities) if authorities else 0.0
        ),
        mean_provenance_score=(
            sum(provenance_scores) / len(provenance_scores)
            if provenance_scores else 0.0
        ),
        contradictions=contradictions,
        cited_pmids=cited_pmids,
        cited_dois=cited_dois,
    )


def synthesise_answer(answer: Answer) -> EvidenceSynthesis:
    """Convenience wrapper — synthesise the claims in an Answer."""
    return synthesise(answer.claims)


def to_markdown(synth: EvidenceSynthesis) -> str:
    """Render the synthesis as Markdown with a stable section order."""
    if synth.n_claims == 0:
        return (
            "## Evidence synthesis\n\n"
            "_No claims to synthesise. Add at least one Claim to the "
            "Answer before requesting synthesis._\n"
        )
    lines: list[str] = ["## Evidence synthesis", ""]
    lines.append(
        f"**Claims:** {synth.n_claims} • "
        f"**Highest grade:** {synth.highest_grade.value} • "
        f"**Weakest grade:** {synth.weakest_grade.value}"
    )
    lines.append(
        f"**Distinct sources:** {synth.distinct_sources} • "
        f"**Mean source authority:** {synth.mean_source_authority:.2f} • "
        f"**Mean provenance score:** {synth.mean_provenance_score:.2f}"
    )
    lines.append(
        f"**Claims with primary source:** {synth.n_with_primary_source} • "
        f"**Claims missing required disclosures:** "
        f"{synth.n_with_missing_disclosures} • "
        f"**Claims with pre-registration:** {synth.n_with_pre_registration}"
    )
    lines.append("")

    # By grade — strongest first.
    non_empty_grade = [b for b in synth.by_grade if b.claims]
    if non_empty_grade:
        lines.append("### Claims by evidence grade")
        lines.append("")
        for b in non_empty_grade:
            lines.append(f"- **{b.grade.value}** — {len(b.claims)} claim(s)")
            for c in b.claims:
                snippet = c.text.strip()
                if len(snippet) > 140:
                    snippet = snippet[:137] + "..."
                lines.append(f"  - *{c.claim_type.value}*: {snippet}")
        lines.append("")

    # By claim type.
    non_empty_type = [b for b in synth.by_claim_type if b.claims]
    if non_empty_type:
        lines.append("### Claims by type")
        lines.append("")
        for b in non_empty_type:
            lines.append(f"- **{b.claim_type.value}** — {len(b.claims)} claim(s)")
        lines.append("")

    # Citations summary.
    if synth.cited_pmids or synth.cited_dois:
        lines.append("### Citations")
        lines.append("")
        for pmid in synth.cited_pmids:
            lines.append(
                f"- PMID {pmid} — "
                f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            )
        for doi in synth.cited_dois:
            lines.append(f"- doi:{doi} — https://doi.org/{doi}")
        lines.append("")

    if synth.contradictions:
        lines.append("### Contradictions detected")
        lines.append("")
        for c in synth.contradictions:
            lines.append(f"- *{c.kind.value}* — {c.topic}: {c.detail}")
        lines.append("")

    return "\n".join(lines)
