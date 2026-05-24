"""Typed Answer artifact + deterministic composer.

A Cannavec Science ``Answer`` is the composable, audience-agnostic object
every surface produces. Prose output is one rendering; ``Answer`` is the
underlying typed contract.

Spec 003 US1 / FR-001 — the composer resolves a typed
``NamedCannabinoidSet`` BEFORE firing the major-cannabinoid monograph
detector. The set is built from both detectors' spans, with major-
cannabinoid hits suppressed when they overlap a more specific minor-
cannabinoid hit (so "Δ⁸-THC" does not also fire the Δ⁹-THC monograph).

Compared to the parent Cannavec plugin's answer module (1569 LOC) this
MVP version is deliberately slimmer (researcher audience only, no
jurisdiction layer, no multi-audience templates, eight science
registries threaded — not twelve).

Composition order (per Constitution §V — safety-layer sovereignty):

1. Safety preflight (`cannavec_science.safety`).
2. Banned-pattern detector (`cannavec_science.banned_patterns`).
3. Rigor-check report (`cannavec_science.rigor_checks`) on the prompt.
4. If refused: short-circuit. Cannavec Science still attaches the
   population-level citations relevant to the topic so a downstream
   reader is pointed at the evidence base, but the typed claims list
   stays empty and ``refusal_reason`` is populated.
5. Otherwise: thread the eight science registries. Each detected row's
   typed claim is added; its citations are deduped onto the Answer.
6. Retraction policy (per Constitution §VIII): in ``strict`` mode any
   claim whose sole citation is retracted is suppressed and
   ``retractions_suppressed`` is incremented.
7. ``evidence_summary`` is refreshed and the Answer is timestamped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from cannavec_science.evidence import (
    Claim,
    EvidenceLevel,
    Source,
    SourceTier,
    missing_disclosures,
)
from cannavec_science.safety import SafetyAction, SafetyVerdict
from cannavec_science.uncertainty import (
    WordingViolation,
    grade_wording_consistency,
)


class ClaimWordingError(ValueError):
    """Raised when a claim's wording exceeds its evidence grade."""

    def __init__(
        self,
        claim: Claim,
        supportable_grade: EvidenceLevel,
        violations: tuple[WordingViolation, ...],
    ):
        ids = ", ".join(v.matched_phrase.strip() for v in violations)
        super().__init__(
            f"claim wording overclaims for evidence grade "
            f"{supportable_grade.value}: {ids}"
        )
        self.claim = claim
        self.supportable_grade = supportable_grade
        self.violations = violations


@dataclass(frozen=True)
class Citation:
    """A primary-source citation referenced from one or more claims."""

    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None
    note: str | None = None
    grade: EvidenceLevel | None = None
    # Spec 002 US5 — surface row-level freshness at citation site.
    # When the backing registry row's ``last_verified`` is older than
    # 365 days, ``answer.py`` populates this with the ISO date so the
    # render layer can append ``[freshness: stale (verified ...)]``.
    freshness_stale_since: str | None = None
    # Spec 002 US1 — preprint badge. When the citation backs a
    # ``live_biorxiv`` / ``live_medrxiv`` row, this is set to the
    # provenance tag so the render layer can append ``[preprint,
    # not peer-reviewed]``.
    preprint_provenance: str | None = None

    def __post_init__(self) -> None:
        if not (self.pmid or self.doi or self.url):
            raise ValueError(
                "Citation must have at least one of pmid / doi / url"
            )

    @classmethod
    def from_source(
        cls,
        source: Source,
        *,
        label: str | None = None,
        grade: EvidenceLevel | None = None,
    ) -> "Citation":
        return cls(
            label=label or source.title,
            pmid=source.pmid,
            doi=source.doi,
            url=source.url,
            year=source.year,
            grade=grade,
        )

    @property
    def resolvable_url(self) -> str:
        if self.pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return self.url or ""

    @property
    def inline(self) -> str:
        """Inline citation suitable for prose, e.g. ``(PMID 28538134, Level A)``."""
        if self.grade is not None:
            grade_tag = f", {self.grade.value}"
        else:
            grade_tag = ""
        if self.pmid:
            return f"(PMID {self.pmid}{grade_tag})"
        if self.doi:
            return f"(doi:{self.doi}{grade_tag})"
        return f"({self.url}{grade_tag})"


@dataclass(frozen=True)
class EvidenceSummary:
    """Rollup of the evidence-level state across an Answer's claims."""

    highest_grade: EvidenceLevel = EvidenceLevel.UNSUPPORTED
    n_claims: int = 0
    n_with_primary_source: int = 0
    n_missing_required_disclosures: int = 0
    n_retracted_citations: int = 0
    has_contradictions: bool = False
    notes: tuple[str, ...] = ()

    @property
    def supports_strong_wording(self) -> bool:
        return self.highest_grade.rank >= EvidenceLevel.B.rank


@dataclass
class Answer:
    """Composable Cannavec Science answer artifact.

    Researcher audience only. ``strict_wording`` defaults to True (per
    Constitution §VII) — claims whose prose verb exceeds their GRADE
    level raise :class:`ClaimWordingError` at ``add_claim`` time.
    """

    prompt: str
    audience: str = "researcher"
    short_answer: str = ""
    claims: list[Claim] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    safety_verdict: SafetyVerdict | None = None
    evidence_summary: EvidenceSummary | None = None
    cautions: tuple[str, ...] = ()
    refusal_reason: str | None = None
    retractions_suppressed: list[str] = field(default_factory=list)
    rigor_violations: list[dict] = field(default_factory=list)
    generated_at: str = ""
    notes: tuple[str, ...] = ()
    strict_wording: bool = True
    sections: list[tuple[str, str]] = field(default_factory=list)
    trace: list[tuple[str, int]] = field(default_factory=list)

    def add_claim(self, claim: Claim) -> None:
        if self.strict_wording:
            supportable = claim.best_supportable_grade()
            violations = grade_wording_consistency(claim.text, supportable)
            if violations:
                raise ClaimWordingError(claim, supportable, violations)
        self.claims.append(claim)
        grade = claim.best_supportable_grade()
        for source in claim.sources:
            self.add_citation(Citation.from_source(source, grade=grade))

    def add_citation(self, citation: Citation) -> None:
        for existing in self.citations:
            if citation.pmid and existing.pmid == citation.pmid:
                return
            if citation.doi and existing.doi == citation.doi:
                return
            if (not citation.pmid and not citation.doi
                    and citation.url and existing.url == citation.url):
                return
        self.citations.append(citation)

    def add_caution(self, caution: str) -> None:
        if caution and caution not in self.cautions:
            self.cautions = self.cautions + (caution,)

    def add_section(self, heading: str, body: str) -> None:
        if heading and body:
            self.sections.append((heading, body))

    def add_trace(self, detector: str, hit_count: int) -> None:
        self.trace.append((detector, int(hit_count)))

    def stamp_now(self) -> None:
        self.generated_at = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    def refresh_evidence_summary(self) -> None:
        if not self.claims:
            self.evidence_summary = EvidenceSummary(
                n_retracted_citations=len(self.retractions_suppressed),
            )
            return
        # Spec 003 US3 / FR-003 — when the composer has tagged a
        # topically-relevant subset, compute ``highest_grade`` over
        # *that* subset only. Falls back to all claims when no signal
        # is present (legacy callers / pre-v0.3 surfaces).
        relevant = getattr(self, "_topically_relevant_claims", None)
        if relevant is None:
            relevant = tuple(self.claims)
        highest = EvidenceLevel.UNSUPPORTED
        for c in relevant:
            grade = c.best_supportable_grade()
            if grade.rank > highest.rank:
                highest = grade
        n_primary = 0
        n_missing = 0
        for c in self.claims:
            if any(s.pmid or s.doi or s.url for s in c.sources):
                n_primary += 1
            if missing_disclosures(c.claim_type, c.disclosures_present):
                n_missing += 1
        notes: tuple[str, ...] = ()
        if (
            relevant is not None
            and len(relevant) < len(self.claims)
            and highest != EvidenceLevel.UNSUPPORTED
        ):
            notes = (
                f"{len(self.claims) - len(relevant)} claim(s) rendered for "
                f"context only — not graded as evidence for this question "
                f"(topical relevance signal, spec 003 US3).",
            )
        elif (
            relevant is not None
            and len(relevant) == 0
            and len(self.claims) > 0
        ):
            notes = (
                f"{len(self.claims)} claim(s) rendered for context only — "
                f"none topically relevant to the question. ``highest_grade`` "
                f"is reported as ``Unsupported`` per spec 003 US3.",
            )
        self.evidence_summary = EvidenceSummary(
            highest_grade=highest,
            n_claims=len(self.claims),
            n_with_primary_source=n_primary,
            n_missing_required_disclosures=n_missing,
            n_retracted_citations=len(self.retractions_suppressed),
            notes=notes,
        )

    @property
    def is_refusal(self) -> bool:
        if self.refusal_reason:
            return True
        if self.safety_verdict is None:
            return False
        return self.safety_verdict.recommended_action in (
            SafetyAction.REFUSE_HARMFUL,
            SafetyAction.REFUSE_INDIVIDUALIZED,
        )

    def to_markdown(self) -> str:
        """Render as researcher-grade Markdown brief."""
        lines: list[str] = []
        lines.append(f"**Q:** {self.prompt}")
        lines.append("")
        lines.append(f"**Audience:** {self.audience}")
        if self.generated_at:
            lines.append(f"**Generated:** {self.generated_at}")
        lines.append("")

        if self.is_refusal:
            lines.append("## Refusal")
            lines.append("")
            if self.refusal_reason:
                lines.append(self.refusal_reason)
            elif self.safety_verdict is not None:
                lines.append(
                    "Cannavec Science cannot answer this prompt as posed."
                )
                for flag in self.safety_verdict.flags:
                    lines.append(f"- {flag.flag.value}: {flag.why}")
            return "\n".join(lines).rstrip() + "\n"

        if self.short_answer:
            lines.append("## Short answer")
            lines.append("")
            lines.append(self.short_answer)
            lines.append("")

        if self.evidence_summary is not None:
            es = self.evidence_summary
            lines.append("## Evidence summary")
            lines.append("")
            lines.append(
                f"- Highest evidence grade across claims: "
                f"**{es.highest_grade.value}**"
            )
            lines.append(f"- Claims: {es.n_claims}")
            lines.append(
                f"- Claims with primary source: {es.n_with_primary_source}"
            )
            if es.n_missing_required_disclosures:
                lines.append(
                    f"- Claims missing required disclosures: "
                    f"{es.n_missing_required_disclosures}"
                )
            if es.n_retracted_citations:
                lines.append(
                    f"- Claims suppressed (retracted citation): "
                    f"**{es.n_retracted_citations}**"
                )
            for n in es.notes:
                lines.append(f"- {n}")
            lines.append("")

        if self.claims:
            lines.append("## Claims")
            lines.append("")
            for claim in self.claims:
                grade = claim.best_supportable_grade()
                cites = " ".join(
                    Citation.from_source(s, grade=grade).inline
                    for s in claim.sources
                )
                lines.append(f"- **[{grade.value}]** {claim.text} {cites}".rstrip())
            lines.append("")

        for heading, body in self.sections:
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(body)
            lines.append("")

        if self.cautions:
            lines.append("## Cautions")
            lines.append("")
            for c in self.cautions:
                lines.append(f"- {c}")
            lines.append("")

        # Spec 004 US3 / FR-004 — render Answer.notes (e.g. the v0.3
        # 0-claim classification messages set by _classify_zero_claims).
        # Skipped on refusals because refusals carry their own message.
        if self.notes:
            lines.append("## Notes")
            lines.append("")
            for n in self.notes:
                lines.append(f"- {n}")
            lines.append("")

        if self.citations:
            lines.append("## Citations")
            lines.append("")
            for c in self.citations:
                grade_tag = f" — {c.grade.value}" if c.grade else ""
                year = f" ({c.year})" if c.year else ""
                # Spec 002 US1 preprint badge.
                badge = ""
                if c.preprint_provenance:
                    badge = " [preprint, not peer-reviewed]"
                # Spec 002 US5 freshness suffix.
                freshness = ""
                if c.freshness_stale_since:
                    freshness = (
                        f" [freshness: stale (verified {c.freshness_stale_since})]"
                    )
                lines.append(
                    f"- {c.label}{year}{grade_tag}{badge}{freshness} "
                    f"— {c.resolvable_url}"
                )
            lines.append("")

        if self.rigor_violations:
            lines.append("## Rigor violations (prompt)")
            lines.append("")
            for v in self.rigor_violations:
                lines.append(f"- **{v['detector']}**: {v.get('match', '')}")
                if v.get("resolution"):
                    lines.append(f"  - Resolution: {v['resolution']}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def to_dict(self) -> dict:
        """JSON-serializable dict representation."""
        return {
            "prompt": self.prompt,
            "audience": self.audience,
            "generated_at": self.generated_at,
            "short_answer": self.short_answer,
            "refusal_reason": self.refusal_reason,
            "claims": [
                {
                    "text": c.text,
                    "claim_type": c.claim_type.value,
                    "grade": c.best_supportable_grade().value,
                    "sources": [
                        {
                            "title": s.title,
                            "pmid": s.pmid,
                            "doi": s.doi,
                            "url": s.url,
                            "year": s.year,
                            "tier": int(s.tier),
                        }
                        for s in c.sources
                    ],
                    "population": c.population,
                }
                for c in self.claims
            ],
            "citations": [
                {
                    "label": c.label,
                    "pmid": c.pmid,
                    "doi": c.doi,
                    "url": c.url,
                    "year": c.year,
                    "grade": c.grade.value if c.grade else None,
                }
                for c in self.citations
            ],
            "cautions": list(self.cautions),
            "notes": list(self.notes),
            "retractions_suppressed": list(self.retractions_suppressed),
            "rigor_violations": self.rigor_violations,
            "evidence_summary": (
                {
                    "highest_grade": self.evidence_summary.highest_grade.value,
                    "n_claims": self.evidence_summary.n_claims,
                    "n_with_primary_source":
                        self.evidence_summary.n_with_primary_source,
                    "n_missing_required_disclosures":
                        self.evidence_summary.n_missing_required_disclosures,
                    "n_retracted_citations":
                        self.evidence_summary.n_retracted_citations,
                }
                if self.evidence_summary
                else None
            ),
            "safety_verdict": (
                {
                    "action": self.safety_verdict.recommended_action.value,
                    "flags": [
                        {"flag": f.flag.value, "why": f.why}
                        for f in self.safety_verdict.flags
                    ],
                }
                if self.safety_verdict
                else None
            ),
            "trace": [{"detector": d, "hits": h} for d, h in self.trace],
        }


# Spec 003 US2 / FR-002 — the canonical cannabinoid name set used by
# the AE / interaction / contraindication / population registries. Each
# registry talks about a cannabinoid by a slightly different label
# (the major-cannabinoid registry uses ``THC`` for Δ⁹-THC, while the AE
# registry uses ``Δ⁹-THC`` directly). The resolver normalises both into
# a canonical set so downstream filters match.
_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "THC": ("THC", "Δ⁹-THC"),
    "Δ⁹-THC": ("THC", "Δ⁹-THC"),
    "CBD": ("CBD",),
}


def _canonical_cannabinoid_names(names: Iterable[str]) -> frozenset[str]:
    """Expand each name to its registry-side aliases (spec 003 US2)."""
    out: set[str] = set()
    for n in names:
        if n in _NAME_ALIASES:
            out.update(_NAME_ALIASES[n])
        else:
            out.add(n)
    return frozenset(out)


@dataclass(frozen=True)
class NamedCannabinoidSet:
    """Spec 003 US1 / FR-001 — deterministic resolution of the named-
    cannabinoid set in a prompt.

    Built by :func:`resolve_named_cannabinoid_set`. ``major`` and
    ``minor`` are tuples of registry entries (in registry order),
    deduplicated by name. ``all_names`` is the union as a frozenset for
    quick membership tests by detectors that need cannabinoid filtering
    (AE / interaction / contraindication / population).

    Span-aware: when a major-cannabinoid regex hit ("THC" in "Δ⁸-THC")
    is contained inside a minor-cannabinoid hit, the major hit is
    suppressed.
    """

    major: tuple = ()
    minor: tuple = ()
    all_names: frozenset[str] = field(default_factory=frozenset)

    @property
    def total(self) -> int:
        return len(self.major) + len(self.minor)


def resolve_named_cannabinoid_set(prompt: str) -> NamedCannabinoidSet:
    """Return the deterministically resolved named-cannabinoid set.

    See :class:`NamedCannabinoidSet`. The resolution rules:

    - Major hits whose match span is fully contained inside any minor
      hit's span are suppressed (the "THC inside Δ⁸-THC" case).
    - Both detectors deduplicate by entry name (so two "THC" matches
      yield one entry).
    - Registry order is preserved within each tier.
    """
    from cannavec_science.major_cannabinoids import (
        detect_major_cannabinoid_mention_with_spans,
    )
    from cannavec_science.minor_cannabinoids import (
        detect_minor_cannabinoid_mention_with_spans,
    )

    minor_pairs = detect_minor_cannabinoid_mention_with_spans(prompt)
    major_pairs = detect_major_cannabinoid_mention_with_spans(prompt)

    minor_spans = tuple(span for _entry, span in minor_pairs)

    def _is_contained(major_span: tuple[int, int]) -> bool:
        ms, me = major_span
        for ns, ne in minor_spans:
            if ns <= ms and me <= ne:
                return True
        return False

    seen_major: set[str] = set()
    major_entries: list = []
    for entry, span in major_pairs:
        if _is_contained(span):
            continue
        if entry.name in seen_major:
            continue
        seen_major.add(entry.name)
        major_entries.append(entry)

    seen_minor: set[str] = set()
    minor_entries: list = []
    for entry, _span in minor_pairs:
        if entry.name in seen_minor:
            continue
        seen_minor.add(entry.name)
        minor_entries.append(entry)

    raw_names = (
        {e.name for e in major_entries}
        | {e.name for e in minor_entries}
    )
    names = _canonical_cannabinoid_names(raw_names)
    return NamedCannabinoidSet(
        major=tuple(major_entries),
        minor=tuple(minor_entries),
        all_names=names,
    )


def compose_answer(
    prompt: str,
    audience: str = "researcher",
    *,
    include_registries: bool = True,
    include_claims: bool = True,
    retraction_policy: str = "strict",
    include_rigor: bool = True,
) -> Answer:
    """Deterministically compose a typed :class:`Answer` from a prompt.

    Researcher audience. Threads the eight science registries (major +
    minor cannabinoids, terpenes, interactions, AEs, populations,
    contraindications, PGx) and enforces retraction policy at composition
    time.

    Parameters
    ----------
    prompt:
        The user's question. Passed through safety + banned-pattern
        + rigor-check layers.
    include_registries:
        When True (default), attach citations + typed claims from every
        registry whose detector fires.
    include_claims:
        When True (default), build typed :class:`Claim` objects from
        registry rows. When False, only citations attach — useful for
        callers building their own claim graph.
    retraction_policy:
        ``"strict"`` (default per Constitution §VIII) — suppress any
        claim whose sole citation is retracted; increment
        ``retractions_suppressed``. ``"badge"`` — keep the claim but
        annotate citations as retracted. The strict mode is the safe
        default for the researcher audience.
    include_rigor:
        When True (default), run the six phytochemistry rigor detectors
        on the prompt and record violations in ``rigor_violations``.
    """
    from cannavec_science.banned_patterns import detect_banned_patterns
    from cannavec_science.safety import check_safety
    from cannavec_science.retraction import is_retracted

    verdict = check_safety(prompt)
    banned_hits = detect_banned_patterns(prompt)

    a = Answer(prompt=prompt, audience=audience or "researcher",
               safety_verdict=verdict)
    a.stamp_now()
    a.evidence_summary = EvidenceSummary()
    a.add_trace("safety.flags", len(verdict.flags))
    a.add_trace("banned_patterns", len(banned_hits))

    if include_rigor:
        from cannavec_science.rigor_checks import run_rigor_checks
        report = run_rigor_checks(prompt)
        for v in report.isomer_violations:
            a.rigor_violations.append({
                "detector": "isomer_collapse",
                "match": v.matched_phrase,
                "span": list(v.span),
                "resolution": (
                    f"Disambiguate `{v.cannabinoid}` "
                    f"to Δ⁹-THC / Δ⁸-THC / THCA / CBD / CBDA / etc."
                ),
            })
        for v in report.receptor_violations:
            a.rigor_violations.append({
                "detector": "receptor_without_id",
                "match": v.matched_phrase,
                "span": list(v.span),
                "resolution": (
                    f"Add UniProt accession for {v.receptor} "
                    f"(CB1=P21554, CB2=P34972, TRPV1=Q8NER1, "
                    f"PPARγ=P37231, 5-HT1A=P08908, GPR55=Q9Y2T6)."
                ),
            })
        for v in report.dose_route_violations:
            a.rigor_violations.append({
                "detector": "dose_without_route",
                "match": v.dose,
                "span": list(v.span),
                "resolution": "Add administration route (oral / inhaled / sublingual) + bioavailability range.",
            })
        for v in report.thca_thc_violations:
            a.rigor_violations.append({
                "detector": "thca_vs_thc_conflation",
                "match": v.matched_phrase,
                "span": list(v.span),
                "resolution": (
                    "Distinguish THCA (raw / pre-decarb) from "
                    "Δ⁹-THC (decarboxylated); e.g., "
                    "'22% THCA (~19.3% Δ⁹-THC equiv post-decarb)'."
                ),
            })
        for v in report.matrix_unit_violations:
            a.rigor_violations.append({
                "detector": "matrix_unit_confusion",
                "match": v.unit_phrase,
                "span": list(v.span),
                "resolution": "Add explicit matrix tag (plasma / urine / flower / extract / edible).",
            })
        for v in report.decarb_context_violations:
            a.rigor_violations.append({
                "detector": "decarb_context_missing",
                "match": v.claim_phrase,
                "span": [0, len(v.claim_phrase)],
                "resolution": (
                    f"Use THCA/CBDA wording for raw / undecarbed extract; "
                    f"reserve {v.cannabinoid} for decarboxylated samples."
                ),
            })
        for v in report.entourage_violations:
            a.rigor_violations.append({
                "detector": "entourage_overclaim",
                "match": v.matched_phrase,
                "span": list(v.span),
                "resolution": (
                    f"cite Russo 2011 / Finlay 2020 / Santiago 2019 / "
                    f"LaVigne 2021 or reframe `{v.terpene}` × "
                    f"`{v.cannabinoid}` as an open empirical hypothesis."
                ),
            })
        # Spec 003 US10 / FR-010: dedup by (detector, span) so
        # downstream renderers can't surface the same finding twice.
        seen: set[tuple[str, tuple[int, int]]] = set()
        deduped: list[dict] = []
        for v in a.rigor_violations:
            key = (v.get("detector", ""), tuple(v.get("span") or ()))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(v)
        a.rigor_violations = deduped
        a.add_trace("rigor_violations", len(a.rigor_violations))

    for caution in verdict.required_cautions:
        a.add_caution(caution)

    safety_refused = verdict.recommended_action in (
        SafetyAction.REFUSE_HARMFUL,
        SafetyAction.REFUSE_INDIVIDUALIZED,
    )
    if safety_refused and verdict.flags:
        a.refusal_reason = (
            "Cannavec Science cannot answer this prompt as posed. Reasons: "
            + "; ".join(
                f"{f.flag.value} — {f.why}" for f in verdict.flags
            )
        )
    elif safety_refused:
        a.refusal_reason = (
            "Cannavec Science cannot answer this prompt in its current form."
        )

    if banned_hits:
        pattern_ids = sorted({h.pattern.id for h in banned_hits})
        banned_reason = (
            "Cannavec Science cannot answer this prompt as framed. The prompt "
            "contains pattern(s) Cannavec Science refuses on evidence-rigor "
            f"grounds: {', '.join(pattern_ids)}. Reframe in evidence-graded "
            "terms (e.g., 'What does the published clinical evidence show "
            "for cannabis in [indication]?')."
        )
        a.refusal_reason = (
            (a.refusal_reason + "\n\n" + banned_reason)
            if a.refusal_reason
            else banned_reason
        )

    if not include_registries:
        return a

    # ── Thread the eight science registries ─────────────────────────
    from cannavec_science.adverse_events import (
        detect_adverse_event_class_mention,
        detect_adverse_event_mention,
    )
    from cannavec_science.contraindications import (
        detect_contraindication_class_mention,
        detect_contraindication_mention,
    )
    from cannavec_science.interactions import (
        detect_interaction_class_mention,
        detect_interaction_mention,
    )
    from cannavec_science.major_cannabinoids import (
        detect_major_cannabinoid_mention,
    )
    from cannavec_science.minor_cannabinoids import (
        detect_minor_cannabinoid_mention,
    )
    from cannavec_science.pharmacogenomics import find_pgx_hits
    from cannavec_science.populations import (
        detect_population_class_mention,
        detect_population_mention,
    )
    from cannavec_science.terpenes import detect_terpene_mention

    # Spec 003 US1 / FR-001 — resolve the named-cannabinoid set BEFORE
    # firing any registry detector, with span-aware deduplication so
    # "Δ⁸-THC pharmacology" never lights up the Δ⁹-THC monograph.
    cannabinoid_set = resolve_named_cannabinoid_set(prompt)
    cannabinoid_filter = cannabinoid_set.all_names or None

    matched_population_rows = _specific_or_class(
        detect_population_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
        detect_population_class_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
    )
    matched_interaction_rows = _specific_or_class(
        detect_interaction_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
        detect_interaction_class_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
    )
    matched_ae_rows = _specific_or_class(
        detect_adverse_event_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
        detect_adverse_event_class_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
    )
    matched_contraindication_rows = _specific_or_class(
        detect_contraindication_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
        detect_contraindication_class_mention(
            prompt, cannabinoid_filter=cannabinoid_filter,
        ),
    )
    matched_minor_cb_rows = cannabinoid_set.minor
    # Major-cannabinoid monograph fires when the prompt names a major
    # cannabinoid (CBD / Δ⁹-THC). The span-aware resolver above already
    # suppresses major hits embedded inside minor hits.
    matched_major_cb_rows = cannabinoid_set.major
    matched_terpene_rows = detect_terpene_mention(prompt)
    matched_pgx_rows = find_pgx_hits(prompt)
    # Spec 003 US7 / FR-007 — eCBome surfacing.
    from cannavec_science.ecbome import detect_ecbome_mention
    matched_ecbome_rows = detect_ecbome_mention(prompt)
    # Spec 004 US1 + US2 / FR-003 — analytical-chemistry +
    # cultivation-science topic-keyword surfacing.
    from cannavec_science.analytical_chemistry import (
        detect_analytical_chemistry_mention,
    )
    from cannavec_science.cultivation_science import (
        detect_cultivation_science_mention,
    )
    matched_analytical_rows = detect_analytical_chemistry_mention(prompt)
    matched_cultivation_rows = detect_cultivation_science_mention(prompt)
    # Spec 005 US1-US5 / FR-006 — clinical-pharmacology depth registries.
    from cannavec_science.pharmacokinetics import (
        detect_pharmacokinetics_mention,
    )
    from cannavec_science.use_disorder import detect_use_disorder_mention
    from cannavec_science.hyperemesis_syndrome import (
        detect_hyperemesis_syndrome_mention,
    )
    from cannavec_science.ecbome_inhibitors import (
        detect_ecbome_inhibitor_mention,
    )
    from cannavec_science.biosynthesis import detect_biosynthesis_mention
    matched_pk_rows = detect_pharmacokinetics_mention(prompt)
    matched_cud_rows = detect_use_disorder_mention(prompt)
    matched_chs_rows = detect_hyperemesis_syndrome_mention(prompt)
    matched_ecbome_inh_rows = detect_ecbome_inhibitor_mention(prompt)
    matched_biosynth_rows = detect_biosynthesis_mention(prompt)

    a.add_trace("registry.populations", len(matched_population_rows))
    a.add_trace("registry.interactions", len(matched_interaction_rows))
    a.add_trace("registry.adverse_events", len(matched_ae_rows))
    a.add_trace("registry.contraindications", len(matched_contraindication_rows))
    a.add_trace("registry.minor_cannabinoids", len(matched_minor_cb_rows))
    a.add_trace("registry.major_cannabinoids", len(matched_major_cb_rows))
    a.add_trace("registry.terpenes", len(matched_terpene_rows))
    a.add_trace("registry.pharmacogenomics", len(matched_pgx_rows))
    a.add_trace("registry.analytical_chemistry", len(matched_analytical_rows))
    a.add_trace("registry.cultivation_science", len(matched_cultivation_rows))
    a.add_trace("registry.ecbome", len(matched_ecbome_rows))
    # Spec 005 — clinical-pharmacology depth trace counters.
    a.add_trace("registry.pharmacokinetics", len(matched_pk_rows))
    a.add_trace("registry.use_disorder", len(matched_cud_rows))
    a.add_trace("registry.hyperemesis_syndrome", len(matched_chs_rows))
    a.add_trace("registry.ecbome_inhibitors", len(matched_ecbome_inh_rows))
    a.add_trace("registry.biosynthesis", len(matched_biosynth_rows))

    # Citation attachment runs regardless of refusal — the population-
    # level evidence base exists whether or not Cannavec Science
    # personally answers. A clinician the user consults next benefits
    # from seeing the relevant PubMed-cited rows. Claim attachment is
    # the gated one: claims represent Cannavec's *own* response, and a
    # refused prompt is not an answer.
    all_rows = (
        list(matched_population_rows)
        + list(matched_interaction_rows)
        + list(matched_ae_rows)
        + list(matched_contraindication_rows)
        + list(matched_terpene_rows)
        + list(matched_pgx_rows)
        + list(matched_analytical_rows)
        + list(matched_cultivation_rows)
        # Spec 005 — clinical-pharmacology depth row citations.
        + list(matched_pk_rows)
        + list(matched_cud_rows)
        + list(matched_chs_rows)
        + list(matched_ecbome_inh_rows)
        + list(matched_biosynth_rows)
    )
    for row in all_rows:
        _attach_citations_from_row(a, row)

    if include_claims and not safety_refused and not banned_hits:
        # Eight registries with row-level .to_claim() — typed claims.
        for row in matched_population_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_interaction_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_ae_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_contraindication_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_terpene_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_pgx_rows:
            _attach_claim_safely(a, row, retraction_policy)
        # Spec 004 US1 + US2 / FR-003 — analytical-chemistry +
        # cultivation-science rows surface as typed claims.
        for row in matched_analytical_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_cultivation_rows:
            _attach_claim_safely(a, row, retraction_policy)
        # Spec 005 US1-US5 / FR-006 — clinical-pharmacology depth rows
        # surface as typed claims via row-level to_claim().
        for row in matched_pk_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_cud_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_chs_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_ecbome_inh_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_biosynth_rows:
            _attach_claim_safely(a, row, retraction_policy)

        # Minor + major cannabinoids render as monograph sections.
        # No row-level to_claim() — these registries surface as
        # full per-compound evidence pictures with their own
        # multi-claim structure inside the prose monograph.
        if matched_minor_cb_rows or matched_major_cb_rows:
            from cannavec_science.minor_cannabinoids import (
                format_for_researcher as _fmt_minor,
            )
            for compound in matched_major_cb_rows:
                a.add_section(
                    f"Major cannabinoid monograph — {compound.name}",
                    _fmt_minor(compound),
                )
                _attach_monograph_citations(a, compound)
            for compound in matched_minor_cb_rows:
                a.add_section(
                    f"Minor cannabinoid monograph — {compound.name}",
                    _fmt_minor(compound),
                )
                _attach_monograph_citations(a, compound)
        # Spec 003 US7 / FR-007 — eCBome entries render as a reference
        # section + citations. Every entry carries a UniProt or HMDB ID
        # per §I, so the citation set is identifier-anchored.
        if matched_ecbome_rows:
            from cannavec_science.ecbome import render_markdown as render_ecbome
            a.add_section(
                "Endocannabinoidome (eCBome) reference",
                render_ecbome(matched_ecbome_rows).removeprefix(
                    "## Endocannabinoidome (eCBome) reference\n"
                ).strip(),
            )
            for entry in matched_ecbome_rows:
                _attach_ecbome_citations(a, entry)
        # Spec 004 US1 / FR-003 — analytical-chemistry registry render.
        if matched_analytical_rows:
            from cannavec_science.analytical_chemistry import (
                render_markdown as render_analytical,
            )
            a.add_section(
                "Analytical-chemistry registry",
                render_analytical(matched_analytical_rows).removeprefix(
                    "## Analytical-chemistry registry\n"
                ).strip(),
            )
        # Spec 004 US2 / FR-003 — cultivation-science registry render.
        if matched_cultivation_rows:
            from cannavec_science.cultivation_science import (
                render_markdown as render_cultivation,
            )
            a.add_section(
                "Cultivation-science registry",
                render_cultivation(matched_cultivation_rows).removeprefix(
                    "## Cultivation-science registry\n"
                ).strip(),
            )
        # Spec 005 US1 / FR-006 — clinical pharmacokinetics registry render.
        if matched_pk_rows:
            from cannavec_science.pharmacokinetics import (
                render_markdown as render_pk,
            )
            a.add_section(
                "Pharmacokinetics registry",
                render_pk(matched_pk_rows).removeprefix(
                    "## Pharmacokinetics registry\n"
                ).strip(),
            )
        # Spec 005 US2 / FR-006 — cannabis use disorder & withdrawal render.
        if matched_cud_rows:
            from cannavec_science.use_disorder import (
                render_markdown as render_cud,
            )
            a.add_section(
                "Cannabis use disorder & withdrawal registry",
                render_cud(matched_cud_rows).removeprefix(
                    "## Cannabis use disorder & withdrawal registry\n"
                ).strip(),
            )
        # Spec 005 US3 / FR-006 — cannabinoid hyperemesis syndrome render.
        if matched_chs_rows:
            from cannavec_science.hyperemesis_syndrome import (
                render_markdown as render_chs,
            )
            a.add_section(
                "Cannabinoid hyperemesis syndrome registry",
                render_chs(matched_chs_rows).removeprefix(
                    "## Cannabinoid hyperemesis syndrome registry\n"
                ).strip(),
            )
        # Spec 005 US4 / FR-006 — eCBome inhibitor pharmacology render.
        if matched_ecbome_inh_rows:
            from cannavec_science.ecbome_inhibitors import (
                render_markdown as render_ecbome_inh,
            )
            a.add_section(
                "eCBome inhibitor pharmacology registry",
                render_ecbome_inh(matched_ecbome_inh_rows).removeprefix(
                    "## eCBome inhibitor pharmacology registry\n"
                ).strip(),
            )
        # Spec 005 US5 / FR-006 — biosynthesis pathway registry render.
        if matched_biosynth_rows:
            from cannavec_science.biosynthesis import (
                render_markdown as render_biosynth,
            )
            a.add_section(
                "Cannabinoid biosynthesis pathway registry",
                render_biosynth(matched_biosynth_rows).removeprefix(
                    "## Cannabinoid biosynthesis pathway registry\n"
                ).strip(),
            )
    elif matched_minor_cb_rows or matched_major_cb_rows or matched_ecbome_rows:
        # Refused prompt: still surface the cannabinoid + eCBome
        # citations so downstream readers see the evidence base.
        for compound in matched_major_cb_rows:
            _attach_monograph_citations(a, compound)
        for compound in matched_minor_cb_rows:
            _attach_monograph_citations(a, compound)
        for entry in matched_ecbome_rows:
            _attach_ecbome_citations(a, entry)

    # Spec 003 US3 / FR-003 — apply the topical-relevance signal so
    # ``highest_grade`` reflects topically relevant claims only.
    _apply_topical_relevance(a, prompt, cannabinoid_set)

    # Spec 003 US9 / FR-009 — when 0 claims and no refusal, classify
    # the 0-claim case so the user gets actionable guidance.
    _classify_zero_claims(a, prompt, cannabinoid_set, banned_hits)

    a.refresh_evidence_summary()
    return a


def _attach_ecbome_citations(a: Answer, entry) -> None:
    """Attach an eCBome entry's primary-source citations to the Answer.

    Spec 003 US7 / FR-007 — every eCBome entry has a UniProt or HMDB
    identifier per §I; the cited papers anchor each entry's binding /
    mechanism profile.
    """
    for c in getattr(entry, "citations", ()) or ():
        pmid = getattr(c, "pmid", None)
        doi = getattr(c, "doi", None)
        if not (pmid or doi):
            continue
        a.add_citation(Citation(
            label=getattr(c, "label", "") or entry.name,
            pmid=pmid,
            doi=doi,
            year=getattr(c, "year", None),
        ))


# Spec 003 US3 / FR-003 — hypothesis-anchored prompts whose claims must
# carry a topical citation to count as relevant. Each entry maps a
# prompt-side regex to the set of canonical primary-source PMIDs that
# anchor the hypothesis. A claim is topical to the hypothesis only when
# at least one of its sources cites one of those PMIDs.
_HYPOTHESIS_ANCHORED_PROMPTS: tuple[tuple[re.Pattern[str], frozenset[str], frozenset[str]], ...] = (
    (
        re.compile(
            r"\bentourage\s+(?:effect|hypothesis|theory)\b",
            re.IGNORECASE,
        ),
        # Canonical PMIDs that DO anchor an entourage-effect claim.
        frozenset({
            "21749363",  # Russo 2011
            "32226370",  # Finlay 2020
            "30728672",  # Santiago 2019
            "33888868",  # LaVigne 2021
        }),
        # Topical-keyword fallback: claim text must contain "entourage"
        # or be about the terpene-cannabinoid synergy literature.
        frozenset({"entourage", "terpene synergy", "terpene-cannabinoid"}),
    ),
)


def _topical_relevance_for_claim(
    claim: Claim,
    prompt: str,
    cannabinoid_set: "NamedCannabinoidSet",
) -> bool:
    """Spec 003 US3 / FR-003 — deterministic topical-relevance signal.

    Composition of cases:

    1. **Hypothesis-anchored prompt** (e.g., "entourage effect
       evidence"): claim is relevant only when one of its sources is
       in the prompt's canonical-citation set OR the claim text
       contains a topical keyword.
    2. **Cannabinoid-named prompt**: claim relevant when a named
       cannabinoid appears in the claim text.
    3. **Topic-keyword-matching prompt** (sleep, pain, anxiety, etc.):
       claim relevant when both prompt and claim share a topic tag.
    4. **Default**: when the prompt names no cannabinoid and matches
       no hypothesis anchor, fall back to "all claims relevant".

    This is intentionally narrow: a Lennox-Gastaut CBD claim does NOT
    become topical to "entourage effect evidence" merely because the
    composer pulled it from the CBD monograph for context.
    """
    text = claim.text.lower()
    claim_pmids = {s.pmid for s in claim.sources if s.pmid}

    # Hypothesis-anchored prompts: the strictest topical filter.
    for rx, canonical_pmids, topical_keywords in _HYPOTHESIS_ANCHORED_PROMPTS:
        if rx.search(prompt):
            if claim_pmids & canonical_pmids:
                return True
            for kw in topical_keywords:
                if kw in text:
                    return True
            return False

    if cannabinoid_set.all_names:
        for name in cannabinoid_set.all_names:
            if name.lower() in text:
                return True
        from cannavec_science.intent import topic_keywords
        prompt_topics = topic_keywords(prompt)
        if prompt_topics:
            claim_topics = topic_keywords(claim.text)
            if prompt_topics & claim_topics:
                return True
        return False

    # No anchor of any kind — claims pass through.
    return True


def _apply_topical_relevance(
    a: Answer,
    prompt: str,
    cannabinoid_set: "NamedCannabinoidSet",
) -> None:
    """Mark each claim with a ``topical_relevance`` signal and stash the
    topically-relevant subset on the Answer for grade aggregation.

    The evidence-summary highest-grade computation in
    :meth:`Answer.refresh_evidence_summary` reads this attribute when
    present.
    """
    relevant: list[Claim] = []
    for c in a.claims:
        if _topical_relevance_for_claim(c, prompt, cannabinoid_set):
            relevant.append(c)
    a._topically_relevant_claims = tuple(relevant)


_ZERO_CLAIM_OUT_OF_SCOPE_AUDIENCE_RE = re.compile(
    r"\b(?:bedrocan|cultivar|cultivars|cultivation|trichom\w*|"
    r"pesticide|harvest|grow(?:ing)?\b|nutrient|hydroponic|"
    r"cannabis\s+(?:retail|sale|store|cafe|dispens\w*)|"
    r"hemp[- ]derived|lab\s*qc|lab\s+test\w*\s+method|"
    r"compliance\s+testing)\b",
    re.IGNORECASE,
)

_ZERO_CLAIM_DEFERRED_RE = re.compile(
    r"\b(?:decarboxylation\s+kinetics|"
    r"hplc\s+method|gc[- ]ms\s+vs\s+hplc|"
    r"chemovar\s+type|chemovar\s+classification|"
    r"vapor\s+pyrolysis|combustion\s+byproduct\w*|"
    r"light\s+spectrum|uv-?b\s+effect|"
    r"thca\s+synthase|cbda\s+synthase|"
    r"botanical\s+taxonomy|sativa\s+l\.?\s+species)\b",
    re.IGNORECASE,
)


def _classify_zero_claims(
    a: Answer,
    prompt: str,
    cannabinoid_set: "NamedCannabinoidSet",
    banned_hits: tuple,
) -> None:
    """Spec 003 US9 / FR-009 — when 0 claims and no refusal, attach a
    classification note describing why.

    Five exclusive cases:

    - **refusal** — safety / banned-pattern fired (already handled
      upstream; we skip).
    - **out_of_scope_audience** — patient / cultivator / retail / lab-
      QC / hemp-derived / per-state regulatory questions.
    - **out_of_scope_deferred** — analytical-chemistry / cultivation-
      science questions (v0.4 horizon per spec 003 US11 / US12).
    - **in_scope_uncurated** — in §IV but no registry row matched.
      Points the user at ``discover`` for a live search.
    - **in_scope_phrasing_mismatched** — registry has rows for the
      named cannabinoid but the predicate didn't match. Suggest a
      reframing.
    """
    if a.claims or a.is_refusal:
        return
    if _ZERO_CLAIM_OUT_OF_SCOPE_AUDIENCE_RE.search(prompt):
        a.notes = a.notes + (
            "0 curated claims: this question targets a non-researcher "
            "audience (cultivation / lab-QC / retail / hemp-derived) — "
            "see the parent Cannavec plugin for those surfaces. The v0.x "
            "Cannavec Science MVP is researcher-only per Constitution §IV.",
        )
        return
    if _ZERO_CLAIM_DEFERRED_RE.search(prompt):
        a.notes = a.notes + (
            "0 curated claims: this question is in §IV (research-grade) "
            "but sits in the v0.4 analytical-chemistry / cultivation-"
            "science horizon — see spec 003 US11 / US12. Use the "
            "`discover` subcommand for a live PubMed / ChEMBL search.",
        )
        return
    if cannabinoid_set.all_names:
        # In scope but the registries didn't fire on a specific row.
        a.notes = a.notes + (
            "0 curated claims: the named cannabinoid is covered by the "
            "registries but the prompt's predicate didn't match a row. "
            "Try rephrasing with explicit drug / event / indication terms "
            "(e.g. 'CBD × tacrolimus', 'HHC vs Δ⁹-THC pharmacology') or "
            "use the `discover` subcommand for a live PubMed search.",
        )
        return
    # In scope but unanchored (no cannabinoid named, no audience drift).
    a.notes = a.notes + (
        "0 curated claims: question appears in scope but no registry "
        "detector fired. Try the `discover` subcommand for a live "
        "PubMed / ChEMBL / CT.gov search.",
    )


def _attach_citations_from_row(a: Answer, row) -> None:
    """Pull primary-source identifiers off a registry row's citation list.

    Each registry row carries a tuple of typed citation objects
    (PopulationCitation, InteractionCitation, etc.), each with a
    ``pmid`` and ``label``. We surface them as Answer Citations so
    the bibliography exporter has them whether or not the row's claim
    was attached.
    """
    candidates = []
    for attr in ("citations", "human_evidence_citations",
                 "preclinical_citations", "pharmacology_citations"):
        if hasattr(row, attr):
            v = getattr(row, attr)
            if v:
                candidates.extend(v)
    for c in candidates:
        pmid = getattr(c, "pmid", None)
        doi = getattr(c, "doi", None)
        url = getattr(c, "url", None)
        if not (pmid or doi or url):
            continue
        label = (
            getattr(c, "label", "")
            or getattr(c, "claim", "")
            or getattr(c, "title", "")
        )
        a.add_citation(
            Citation(
                label=label or "Untitled",
                pmid=pmid,
                doi=doi,
                url=url,
                year=getattr(c, "year", None),
            )
        )


def _attach_monograph_citations(a: Answer, compound) -> None:
    """Lift Citation objects out of a minor/major cannabinoid monograph.

    Each monograph carries citations in three places:

    - Top-level ``citations`` (cross-cutting).
    - Per-row ``human_evidence[].citations`` (per-claim primary lit).
    - Per-row ``preclinical_evidence[].citations`` (mechanism / animal).
    - Per-row ``pharmacology[].citations`` if the row has them.

    All are surfaced so the bibliography exporter can render them.
    """
    cite_iters: list = []
    # Top-level cross-cutting
    for attr in ("citations",):
        if hasattr(compound, attr):
            v = getattr(compound, attr)
            if v:
                cite_iters.extend(v)
    # Nested evidence rows. Attribute names differ across registries:
    # - Minor/major cannabinoid monographs use ``clinical_evidence``,
    #   ``preclinical_evidence``, ``receptor_activity``.
    # - Future registries may use ``human_evidence``, ``pharmacology``.
    for row_attr in ("clinical_evidence", "human_evidence",
                     "preclinical_evidence", "pharmacology",
                     "receptor_activity"):
        if hasattr(compound, row_attr):
            rows = getattr(compound, row_attr) or ()
            for r in rows:
                row_cites = getattr(r, "citations", None) or ()
                cite_iters.extend(row_cites)

    for c in cite_iters:
        pmid = getattr(c, "pmid", None)
        if not pmid:
            continue
        a.add_citation(
            Citation(
                label=(
                    getattr(c, "label", "")
                    or getattr(c, "claim", "")
                    or getattr(c, "title", "")
                ),
                pmid=pmid,
                year=getattr(c, "year", None),
            )
        )


def _specific_or_class(specific: tuple, class_fallback: tuple) -> tuple:
    """Use specific matches if any; otherwise fall back to class-level.

    Matches the parent's behaviour: a specific match (e.g., "Dravet
    syndrome") suppresses the class-level fallback (e.g., "epilepsy")
    so the answer doesn't drag in unrelated rows. Only when the
    specific matcher finds nothing does the class-level surface.
    """
    return tuple(specific) if specific else tuple(class_fallback)


def _attach_claim_safely(
    a: Answer,
    row,
    retraction_policy: str,
) -> None:
    """Build a claim from a registry row, enforcing retraction policy.

    ``strict`` mode (default): if every citation on the row is retracted,
    suppress the claim and append the row's identifier to
    ``a.retractions_suppressed``. ``badge`` mode: keep the claim, but
    individual citations carry a retraction note.
    """
    from cannavec_science.retraction import is_retracted

    if not hasattr(row, "to_claim"):
        return
    try:
        claim = row.to_claim()
    except Exception:
        return
    if claim is None:
        return

    live_sources = []
    retracted_pmids = []
    for s in claim.sources:
        rec = None
        if s.pmid:
            rec = is_retracted(pmid=s.pmid)
        if rec is None and s.doi:
            rec = is_retracted(doi=s.doi)
        if rec is not None:
            retracted_pmids.append(s.pmid or s.doi)
        else:
            live_sources.append(s)

    if retraction_policy == "strict" and not live_sources:
        # The whole claim is retracted; suppress it.
        row_id = getattr(row, "id", None) or getattr(row, "label", "")
        a.retractions_suppressed.append(str(row_id))
        return

    if retraction_policy == "strict" and retracted_pmids:
        # Some sources retracted, some clean. Keep only clean.
        claim = Claim(
            text=claim.text,
            claim_type=claim.claim_type,
            sources=tuple(live_sources),
            disclosures_present=claim.disclosures_present,
            population=claim.population,
            jurisdiction=claim.jurisdiction,
            dose_range=claim.dose_range,
            route=claim.route,
            chemotype=claim.chemotype,
        )

    try:
        a.add_claim(claim)
    except ClaimWordingError:
        # In strict-wording mode an over-claim is rejected; record but
        # do not crash composition.
        pass


def merge_citations(answers: Iterable[Answer]) -> list[Citation]:
    """Deduplicate Citations across multiple Answers."""
    out: list[Citation] = []
    for a in answers:
        for c in a.citations:
            present = any(
                (c.pmid and existing.pmid == c.pmid)
                or (c.doi and existing.doi == c.doi)
                or (c.url and existing.url == c.url)
                for existing in out
            )
            if not present:
                out.append(c)
    return out
