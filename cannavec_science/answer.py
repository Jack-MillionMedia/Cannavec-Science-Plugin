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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable

from cannavec_science.evidence import (
    CitationMissingError,
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
    grade_rationale,
    missing_disclosures,
)
from cannavec_science.intent import Intent, classify_intent
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
    # Per-citation provenance timestamps. ``fetched_at`` records when
    # the upstream source was last pulled (e.g. PubMed esummary fetch);
    # ``retraction_checked_at`` records when the retraction registry
    # was last consulted for this identifier. Both default to ``None``
    # so existing constructors are unchanged; the render layer emits a
    # ``[checked YYYY-MM-DD]`` suffix only when populated.
    fetched_at: str | None = None
    retraction_checked_at: str | None = None

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
            grade_tag = f", {self.grade.certainty} certainty"
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


def _is_same_citation(new: Citation, existing: Citation) -> bool:
    """True when ``new`` duplicates ``existing`` by primary identifier.

    Identity precedence mirrors the Source-or-Refuse hierarchy: match on PMID,
    then DOI, then — only when ``new`` carries neither — URL. This is the single
    source of truth shared by :meth:`Answer.add_citation` and
    :func:`merge_citations`, so the two dedup paths cannot drift apart (they
    previously disagreed on the URL-only case).
    """
    if new.pmid and existing.pmid == new.pmid:
        return True
    if new.doi and existing.doi == new.doi:
        return True
    if (
        not new.pmid
        and not new.doi
        and new.url
        and existing.url == new.url
    ):
        return True
    return False


def _stronger_grade(
    a: "EvidenceLevel | None", b: "EvidenceLevel | None"
) -> "EvidenceLevel | None":
    """The higher-rank of two optional grades (A > B > C > D > E > Unsupported).

    ``None`` only when both are ``None``. Used by
    :meth:`Answer._citation_grade_map` so that when two surviving claims cite the
    same source the citation keeps the STRONGEST of their grades — matching
    :func:`bibliography._evidence_level_for_citation`, the other place that
    resolves a citation's grade from its claims.
    """
    if a is None:
        return b
    if b is None:
        return a
    return a if a.rank >= b.rank else b


def _lookup_citation_grade(grade_map: dict, citation: Citation):
    """Resolve a citation's serialized grade from the surviving-claims grade map
    (PMID, then DOI, then URL), or ``None`` if no surviving claim grades it."""
    for key in (citation.pmid, citation.doi, citation.url):
        if key and key in grade_map:
            return grade_map[key].value
    return None


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
    # Opt-in defence-in-depth on Constitution §I. When True,
    # :meth:`add_claim` raises :class:`CitationMissingError` for any
    # non-EDUCATIONAL claim that arrives with an empty ``sources`` tuple
    # (rather than silently grading it UNSUPPORTED). Defaults to False
    # to preserve back-compat with the 1,501 tests pinned against the
    # current behaviour; flip to True at the call site for stricter runs.
    strict_citation_mandate: bool = False
    sections: list[tuple[str, str]] = field(default_factory=list)
    trace: list[tuple[str, int]] = field(default_factory=list)
    # Unverified live-discovery hits (Constitution §IX). Provenance-tagged,
    # provisionally graded, never promoted into the curated grade — a fenced
    # "frontier" surface that augments a thin curated answer.
    live_findings: list[dict] = field(default_factory=list)
    # Cross-source synthesis verdict over the live tier (Constitution §IX):
    # STRONG / MIXED / WEAK / NONE convergence + per-source counts +
    # disagreement, as produced by ``cannavec_science.synthesis.synthesize``.
    # ``None`` until a live fan-out is woven into the brief — so an offline
    # ``compose_answer`` (the default) leaves the pinned JSON / Markdown
    # unchanged, and only a blended brief carries the verdict.
    live_synthesis: "dict | None" = None
    # Verified-tier breadth (Constitution §IX flywheel): primary sources that
    # cleared the SAME admission gate as a curated row AND were promoted by a
    # named human curator. The middle tier — more than provisional live, less
    # than a hand-authored registry claim. Provenance-tagged ``verified``,
    # carries a conservative single-source GRADE + a verbatim quote, and NEVER
    # touches the curated ``evidence_summary`` grade (breadth augments the core,
    # it does not re-grade it). Empty by default so an un-woven brief's pinned
    # JSON / Markdown is unchanged.
    verified_findings: list[dict] = field(default_factory=list)

    def add_claim(self, claim: Claim) -> None:
        if (
            self.strict_citation_mandate
            and not claim.sources
            and claim.claim_type != ClaimType.EDUCATIONAL
        ):
            raise CitationMissingError(
                f"claim of type {claim.claim_type.value} requires at least "
                f"one primary source (PMID / DOI / ChEMBL / NCT / UniProt) "
                f"per Constitution §I; got none for: {claim.text[:80]!r}"
            )
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
            if _is_same_citation(citation, existing):
                return
        self.citations.append(citation)

    def _citation_grade_map(self) -> "dict[str, EvidenceLevel]":
        """Best grade per source identifier, derived from the SURVIVING claims.

        GRADE authoritatively lives on the claim. Serialization recomputes each
        citation's grade from the *current* ``self.claims`` rather than a value
        stored when the citation was attached — so a claim dropped afterward
        (e.g. a wrong-indication efficacy claim removed by the off-KB gate, whose
        citation is correctly retained for the bibliography under §I) leaves NO
        orphaned Level-A/B grade on the citation. Without this, a "no curated
        evidence for X" answer could still export a Level-A-stamped bibliography
        for X — the citation→claim binding lie this project exists to prevent
        (§I / §VII / M2). The strongest grade across claims citing a source wins
        (matches :func:`bibliography._evidence_level_for_citation`).
        """
        by_id: "dict[str, EvidenceLevel]" = {}
        for claim in self.claims:
            try:
                g = claim.best_supportable_grade()
            except Exception:
                continue
            for s in claim.sources:
                for key in (s.pmid, s.doi, s.url):
                    if key:
                        by_id[key] = _stronger_grade(by_id.get(key), g)
        return by_id

    def add_caution(self, caution: str) -> None:
        if caution and caution not in self.cautions:
            self.cautions = self.cautions + (caution,)

    def add_section(self, heading: str, body: str) -> None:
        if heading and body:
            self.sections.append((heading, body))

    def add_trace(self, detector: str, hit_count: int) -> None:
        self.trace.append((detector, int(hit_count)))

    def add_live_finding(
        self,
        *,
        label: str,
        identifier: str,
        source_tag: str,
        url: str = "",
        provisional_grade: str = "provisional (live, unverified)",
        year: "str | int | None" = None,
        retraction_status: str = "clean",
    ) -> None:
        """Attach one unverified live-discovery hit (Constitution §IX).

        Live findings are tagged by provenance, carry only a *provisional*
        grade, and NEVER affect the curated ``evidence_summary`` grade or
        auto-promote into the knowledge base. De-duplicated by identifier.

        ``retraction_status`` is the live tier's §VIII check: a finding whose
        identifier matches the retraction registry is kept (so the researcher
        is warned the paper exists) but badged ⚠ and pinned last by the ranker
        — never silently surfaced as citable evidence.
        """
        if not (label or identifier):
            return
        for existing in self.live_findings:
            if identifier and existing.get("identifier") == identifier:
                return
        self.live_findings.append({
            "label": label,
            "identifier": identifier,
            "source_tag": source_tag,
            "url": url,
            "provisional_grade": provisional_grade,
            "year": str(year) if year not in (None, "") else "",
            "retraction_status": retraction_status or "clean",
        })

    def add_verified_finding(
        self,
        *,
        label: str,
        identifier: str,
        grade: str,
        url: str = "",
        quote: str = "",
        approver: str = "",
        topic: str = "",
        year: "str | int | None" = None,
        retraction_status: str = "clean",
        source_tag: str = "verified",
    ) -> None:
        """Attach one verified-tier breadth source (Constitution §IX flywheel).

        Unlike a live finding, a verified finding cleared the full admission
        gate and a human curator approved it — so it carries a real conservative
        GRADE and a verbatim support quote. Like a live finding, it is a
        *breadth* row: clearly tagged, never folded into the curated claim set,
        and it NEVER changes ``evidence_summary``. De-duplicated by identifier;
        a flagged ``retraction_status`` is badged and pinned last by the weaver.
        """
        if not (label or identifier):
            return
        for existing in self.verified_findings:
            if identifier and existing.get("identifier") == identifier:
                return
        self.verified_findings.append({
            "label": label,
            "identifier": identifier,
            "source_tag": source_tag,
            "grade": grade,
            "url": url,
            "quote": quote,
            "approver": approver,
            "topic": topic,
            "year": str(year) if year not in (None, "") else "",
            "retraction_status": retraction_status or "clean",
        })

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
                f"**{es.highest_grade.display()}**"
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
                lines.append(f"- **[{grade.display()}]** {claim.text} {cites}".rstrip())
                # WP-RETRIEVAL #5 — surface the cited trial's effect size,
                # 95% CI, and P at the citation site, and guard a curated NNT
                # derived from a non-significant endpoint with an explicit
                # caveat. Renders only when the registry holds the numbers.
                for est in _effect_estimates_for_claim(claim):
                    lines.append(f"  - Effect (PMID {est.pmid}):")
                    if est.n is not None:
                        lines.append(f"    - n: {est.n}")
                    if est.comparator:
                        lines.append(f"    - Comparator: {est.comparator}")
                    if est.primary_outcome:
                        lines.append(
                            f"    - Primary outcome: {est.primary_outcome}"
                        )
                    if est.effect_size:
                        lines.append(f"    - Effect size: {est.effect_size}")
                    if est.confidence_interval:
                        lines.append(f"    - 95% CI / P: {est.confidence_interval}")
                    if est.nnt:
                        lines.append(f"    - NNT: {est.nnt}")
                    if est.nnt_caveat:
                        lines.append(
                            f"    - ⚠ NNT caveat: {est.nnt_caveat}."
                        )
            lines.append("")

        if self.sections:
            lines.append(
                "> **Background.** Compound pharmacology and related-indication "
                "context from the curated registries — not specific efficacy "
                "evidence for this question. Confirm each source before citing."
            )
            lines.append("")
        for heading, body in self.sections:
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(body)
            lines.append("")

        if self.verified_findings:
            lines.append("## Verified breadth — gate-passed, human-approved")
            lines.append("")
            lines.append(
                "_Primary sources that cleared the full admission gate "
                "(identifier audit · not-retracted · claim-support with a "
                "verbatim quote · phytochemistry rigor) and a named-curator "
                "review. Each carries a conservative single-source GRADE — the "
                "middle tier between the curated core above and the provisional "
                "live frontier below, and it never re-grades the core._"
            )
            lines.append("")
            for f in self.verified_findings:
                yr = f" ({f['year']})" if f.get("year") else ""
                url = f" — {f['url']}" if f.get("url") else ""
                by = f" — approved by {f['approver']}" if f.get("approver") else ""
                status = f.get("retraction_status", "clean")
                badge = f" ⚠ {status.upper()}" if status in _LIVE_FLAGGED_STATUSES else ""
                grade = f.get("grade") or "verified"
                lines.append(
                    f"- [{f['source_tag']} · {grade}]{badge} `{f['identifier']}`{yr} "
                    f"{f.get('label', '')}{by}{url}".rstrip()
                )
                if f.get("quote"):
                    lines.append(f"  > “{f['quote']}”")
            lines.append("")

        if self.live_findings or self.live_synthesis:
            lines.append("## Live discovery — provisional, not curated")
            lines.append("")
            lines.append(
                "_Live-source breadth woven onto the verified curated core "
                "above. Each hit is provenance-tagged (`live_<source>`), "
                "reranked, and checked against the retraction registry, but "
                "carries no curated grade and never auto-promotes into the "
                "knowledge base — confirm each source before citing._"
            )
            lines.append("")
            if self.live_synthesis:
                conv = self.live_synthesis.get("convergence", "NONE")
                counts = self.live_synthesis.get("per_source_counts", {}) or {}
                present = ", ".join(
                    f"{k} {v}" for k, v in sorted(counts.items()) if v
                ) or "no live rows returned"
                lines.append(
                    f"**Cross-source synthesis: {conv}** — convergence across "
                    f"the live primary-source tier ({present})."
                )
                dis = self.live_synthesis.get("disagreement")
                if dis:
                    lines.append(f"- Disagreement flagged: {dis}")
                unreachable = self.live_synthesis.get("unreachable_sources") or []
                if unreachable:
                    lines.append(
                        f"- Sources unreachable at fetch time: "
                        f"{', '.join(unreachable)}"
                    )
                lines.append("")
            for f in self.live_findings:
                yr = f" ({f['year']})" if f.get("year") else ""
                url = f" — {f['url']}" if f.get("url") else ""
                label = f" {f['label']}" if f.get("label") else ""
                status = f.get("retraction_status", "clean")
                badge = (
                    f" ⚠ {status.upper()}"
                    if status in _LIVE_FLAGGED_STATUSES
                    else ""
                )
                lines.append(
                    f"- [{f['source_tag']}]{badge} `{f['identifier']}`{yr}{label} "
                    f"— provisional grade: {f['provisional_grade']}{url}".rstrip()
                )
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
            # Grade from the surviving claims (same recompute as to_dict) so the
            # Markdown references and the JSON citations carry identical grades
            # and a dropped claim never orphans a grade here either (§XI/§I).
            _cite_grades = self._citation_grade_map()
            for c in self.citations:
                _g = _lookup_citation_grade(_cite_grades, c)
                grade_tag = f" — {EvidenceLevel(_g).display()}" if _g else ""
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
                # Per-citation provenance timestamps (Citation.fetched_at
                # / .retraction_checked_at). Render only when populated
                # so the existing pinned markdown stays unchanged.
                provenance = ""
                if c.fetched_at:
                    provenance += f" [fetched {c.fetched_at}]"
                if c.retraction_checked_at:
                    provenance += (
                        f" [retraction-checked {c.retraction_checked_at}]"
                    )
                lines.append(
                    f"- {c.label}{year}{grade_tag}{badge}{freshness}{provenance} "
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
        # Per-citation grade is recomputed from the surviving claims so a
        # dropped claim never orphans a grade onto its retained citation
        # (§I/§VII — see _citation_grade_map).
        _cite_grades = self._citation_grade_map()
        return {
            "prompt": self.prompt,
            "audience": self.audience,
            "generated_at": self.generated_at,
            "short_answer": self.short_answer,
            "refusal_reason": self.refusal_reason,
            # First-class refusal flag (§V / §XI) — a refusal still serializes its
            # reference citations, so a /cv output skill must be able to detect the
            # refusal state directly rather than infer it from citations being
            # present. Mirrors the ``is_refusal`` property.
            "is_refusal": self.is_refusal,
            "claims": [
                {
                    "text": c.text,
                    "claim_type": c.claim_type.value,
                    "grade": c.best_supportable_grade().value,
                    "certainty": c.best_supportable_grade().certainty,
                    "grade_rationale": grade_rationale(c).summary(),
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
                    # WP-RETRIEVAL #5 — effect size / 95% CI / P / NNT (+ a
                    # non-significance caveat where applicable) at the citation
                    # site. Emitted only when the registry holds them, so a
                    # claim without quantitative data keeps the pinned shape.
                    **(
                        {"effect_estimates": [e.to_dict() for e in _ests]}
                        if (_ests := _effect_estimates_for_claim(c))
                        else {}
                    ),
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
                    "grade": _lookup_citation_grade(_cite_grades, c),
                    # Per-citation provenance timestamps. Emitted only
                    # when populated so the existing pinned JSON shape
                    # stays unchanged for any citation that doesn't
                    # carry these fields.
                    **({"fetched_at": c.fetched_at} if c.fetched_at else {}),
                    **(
                        {"retraction_checked_at": c.retraction_checked_at}
                        if c.retraction_checked_at
                        else {}
                    ),
                }
                for c in self.citations
            ],
            "cautions": list(self.cautions),
            "notes": list(self.notes),
            # Monograph sections (major/minor-cannabinoid monographs, etc.) are
            # structured prose, not typed claims. Expose them so JSON / "at
            # scale" consumers receive the monograph the Markdown brief shows —
            # a CBG/CBC/CBN query carries a full Unsupported-graded monograph
            # here, not just in to_markdown(). Emitted only when present, so the
            # pinned JSON shape is unchanged for section-less briefs.
            **(
                {"sections": [
                    {"heading": h, "body": b} for h, b in self.sections
                ]}
                if self.sections
                else {}
            ),
            "live_findings": list(self.live_findings),
            # Emitted only when a live fan-out was woven in, so the pinned
            # offline-answer JSON shape stays unchanged for curated-only briefs.
            **(
                {"live_synthesis": self.live_synthesis}
                if self.live_synthesis
                else {}
            ),
            # Likewise emitted only when verified-tier breadth was woven in, so a
            # curated-only brief's pinned JSON shape is unchanged (§IX flywheel).
            **(
                {"verified_findings": list(self.verified_findings)}
                if self.verified_findings
                else {}
            ),
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


# ── "Answer the question, not the entity" — intent → monograph sections ──
# For question types we can detect with confidence, render only the
# sub-sections that answer that question, so a focused query is not buried
# under the full entity monograph. Broad / ambiguous intents (COMPARISON,
# LITERATURE_REVIEW, PRODUCT_CLAIM_CHECK, LEGAL_STATUS, RECOMMENDATION,
# HOW_TO_PROCEDURAL, OPEN_QUESTION — e.g. "write a monograph on X") fall back
# to the full monograph (None) so we never hide evidence a reader wanted.
# ``uncertainties`` + ``citations`` ride along with every focused set to keep
# the honesty + traceability surface intact.
_MONOGRAPH_SECTIONS_BY_INTENT: "dict[Intent, frozenset[str]]" = {
    Intent.MECHANISM: frozenset(
        {"chemistry", "receptor", "preclinical", "uncertainties", "citations"}
    ),
    Intent.DOSING: frozenset(
        {"chemistry", "clinical", "pk", "safety", "uncertainties", "citations"}
    ),
    Intent.SAFETY_RISK: frozenset(
        {"clinical", "safety", "uncertainties", "misconceptions", "citations"}
    ),
    Intent.INTERACTION: frozenset(
        {"pk", "safety", "uncertainties", "citations"}
    ),
    Intent.DEFINITION: frozenset(
        {"chemistry", "receptor", "uncertainties", "citations"}
    ),
    Intent.EFFICACY: frozenset(
        {"clinical", "preclinical", "safety", "uncertainties",
         "misconceptions", "citations"}
    ),
}


def _monograph_sections_for(prompt: str) -> "frozenset[str] | None":
    """Pick the monograph sub-sections that answer this prompt's intent.

    ``None`` (full monograph) for broad / ambiguous intents.
    """
    return _MONOGRAPH_SECTIONS_BY_INTENT.get(classify_intent(prompt))


# Factual descriptions of each evidence tier for the BLUF lead. These
# describe the grade; they are NOT efficacy verbs, so prefixing them to an
# already grade-validated claim cannot over-claim (Constitution §VII).
_GRADE_FRAME: "dict[EvidenceLevel, str]" = {
    EvidenceLevel.A: (
        "High certainty (Level A — systematic review / "
        "meta-analysis or ≥ 2 aligned RCTs)"
    ),
    EvidenceLevel.B: (
        "Moderate certainty (Level B — single adequately-powered RCT)"
    ),
    EvidenceLevel.C: (
        "Low certainty (Level C — observational / single small trial)"
    ),
    EvidenceLevel.D: "Very low certainty (Level D — preclinical evidence only)",
    EvidenceLevel.E: "Very low certainty (Level E — traditional-use evidence only)",
    EvidenceLevel.UNSUPPORTED: "No admissible primary evidence",
}


# Tokens too generic to signal topical alignment in the BLUF tie-break.
_SHORT_ANSWER_STOPWORDS = frozenset({
    "cannabis", "cannabinoid", "cannabinoids", "patients", "patient",
    "evidence", "study", "studies", "human", "humans", "level", "effect",
    "effects", "with", "from", "that", "this", "their", "have", "been",
    "which", "while", "data", "than", "into", "also", "about", "after",
})


def _content_tokens(text: str) -> frozenset[str]:
    """Lowercased content words (length ≥ 4, non-stopword) for overlap scoring."""
    toks = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", text.lower())
    return frozenset(t for t in toks if t not in _SHORT_ANSWER_STOPWORDS)


# ── Effect-estimate precision at the citation site (WP-RETRIEVAL #5) ─────────
#
# The curated populations registry already records the quantitative effect of
# each pivotal trial — effect size, 95% CI, P, NNT, n, comparator, primary
# outcome — on its ``PopulationCitation`` rows. Those numbers render in the
# population *monograph* but were absent from the typed-``Claim`` citation site
# (the ``## Claims`` section + the JSON), where the brief simply read
# "(PMID …, Level B)". A researcher choosing whether to act on a Level-B claim
# needs the actual interval and P at that site, not a bare grade.
#
# We harvest those numbers once (read-only) and key them by PMID, then surface
# them under each claim's matching citation. The registry stays the single
# source of truth — ``answer.py`` only *renders* what populations already holds.


@dataclass(frozen=True)
class EffectEstimate:
    """The quantitative effect a single cited trial reports, for inline render."""

    pmid: str
    n: "int | None" = None
    comparator: "str | None" = None
    primary_outcome: "str | None" = None
    effect_size: "str | None" = None
    confidence_interval: "str | None" = None
    nnt: "str | None" = None
    nnt_caveat: "str | None" = None

    @property
    def has_any(self) -> bool:
        return any((
            self.effect_size, self.confidence_interval, self.nnt,
            self.primary_outcome, self.comparator, self.n is not None,
        ))

    def to_dict(self) -> dict:
        out: dict = {"pmid": self.pmid}
        if self.n is not None:
            out["n"] = self.n
        for k in ("comparator", "primary_outcome", "effect_size",
                  "confidence_interval", "nnt", "nnt_caveat"):
            v = getattr(self, k)
            if v:
                out[k] = v
        return out


# §VII honesty guard (WP-RETRIEVAL #5). A curated NNT can be quoted against a
# *responder* endpoint that — unlike the trial's primary endpoint — did not
# reach significance. Devinsky 2017 (PMID 28538134) is the ground-truthed case:
# its ≥50%-responder analysis was OR 2.00 (95% CI 0.93–4.30, P=0.08), NOT
# significant, while the PRIMARY monthly-convulsive-seizure-frequency endpoint
# WAS (adjusted median difference −22.8%, P=0.01). Rather than blanket-flag
# every ≥50% NNT, we attach a precise, sourced caveat ONLY where the mismatch
# is documented — keyed by PMID and gated on the NNT actually naming a ≥50%
# responder/reduction endpoint, so a different trial's responder NNT is never
# mis-caveated.
_NNT_SIGNIFICANCE_CAVEATS: "dict[str, tuple[re.Pattern[str], str]]" = {
    "28538134": (
        re.compile(r"≥\s*50\s*%|>=\s*50\s*%|50\s*%\s*(?:respon|reduct)",
                   re.IGNORECASE),
        "the ≥50%-responder endpoint this NNT is derived from was NOT "
        "statistically significant (OR 2.00, 95% CI 0.93-4.30, p=0.08); the "
        "significant primary endpoint was monthly convulsive-seizure frequency "
        "(adjusted median difference -22.8%, p=0.01), to which any NNT should "
        "be anchored",
    ),
}


def _nnt_caveat_for(pmid: "str | None", nnt: "str | None") -> "str | None":
    """Return the non-significance caveat for a curated NNT, if one applies."""
    if not pmid or not nnt:
        return None
    entry = _NNT_SIGNIFICANCE_CAVEATS.get(str(pmid))
    if entry is None:
        return None
    pattern, caveat = entry
    return caveat if pattern.search(nnt) else None


@lru_cache(maxsize=1)
def _build_population_effect_index() -> "dict[str, EffectEstimate]":
    """Build ``{pmid: EffectEstimate}`` from the curated populations registry.

    Read-only: ``answer.py`` consumes what ``populations`` already curates (it
    never edits the registry). Built once. A row without quantitative fields
    contributes nothing, so the map is small and only holds the trials that
    carry an effect estimate.

    Raises on registry failure ON PURPOSE: ``functools.lru_cache`` never
    memoises a call that raised, so a transient fault cannot be cached. The
    public wrapper :func:`_population_effect_index` turns that into a safe,
    *uncached* empty result.
    """
    from cannavec_science.populations import all_populations

    rows = all_populations()
    index: dict[str, EffectEstimate] = {}
    for row in rows:
        for c in getattr(row, "citations", ()) or ():
            pmid = getattr(c, "pmid", None)
            if not pmid:
                continue
            nnt = getattr(c, "nnt", None)
            est = EffectEstimate(
                pmid=str(pmid),
                n=getattr(c, "n", None),
                comparator=getattr(c, "comparator", None),
                primary_outcome=getattr(c, "primary_outcome", None),
                effect_size=getattr(c, "effect_size", None),
                confidence_interval=getattr(c, "confidence_interval", None),
                nnt=nnt,
                nnt_caveat=_nnt_caveat_for(pmid, nnt),
            )
            if est.has_any:
                index[str(pmid)] = est
    return index


def _population_effect_index() -> "dict[str, EffectEstimate]":
    """Cached effect index with a safe, *uncached* empty fallback.

    Previously this function was ``@lru_cache``-wrapped directly with the
    registry read inside a bare ``try/except`` that returned ``{}`` — so the
    FIRST call's failure cached an empty index for the whole process and every
    effect estimate (n / 95% CI / NNT) silently vanished for the session. Now
    only a *successful* build is memoised; a fault degrades to empty and the
    next call retries.
    """
    try:
        return _build_population_effect_index()
    except Exception:  # noqa: BLE001 — registry fault: degrade, do not poison cache
        return {}


def _effect_estimates_for_claim(claim: Claim) -> "list[EffectEstimate]":
    """Effect estimates for a claim, keyed off its sources' PMIDs.

    Only clinical-efficacy claims carry a population effect estimate; other
    claim types return ``[]`` so no spurious block is rendered for them.
    """
    if claim.claim_type != ClaimType.CLINICAL_EFFICACY:
        return []
    index = _population_effect_index()
    out: list[EffectEstimate] = []
    seen: set[str] = set()
    for s in claim.sources:
        if not s.pmid or s.pmid in seen:
            continue
        est = index.get(str(s.pmid))
        if est is not None:
            out.append(est)
            seen.add(s.pmid)
    return out


def _set_short_answer(a: Answer) -> None:
    """Populate the BLUF lead: one grade-honest bottom line at the top.

    Reuses the highest-grade topically-relevant claim's *already
    grade-validated* text (never freshly-generated prose), prefixed with a
    factual description of the evidence tier. The claim verb was checked at
    ``add_claim`` time, so the lead cannot over-claim (§VII). No-ops on a
    refusal, when no claim is topically relevant, or when a caller already
    set ``short_answer``.

    Selection key is ``(grade_rank, prompt_overlap)``: grade dominates (the
    BLUF is always the strongest-evidence claim), but ties are broken toward
    the claim most lexically aligned with the question — so an on-topic
    endocrine/metabolic claim leads over a generic same-grade caution that
    merely shares a population keyword.
    """
    if a.is_refusal or a.short_answer:
        return
    # §I / M2 / §VII — when the prompt names a recognised indication the curated
    # KB has no graded efficacy claim for, the bottom line must say so, never
    # lead with a wrong-indication efficacy claim. Shares
    # _uncovered_offkb_indications with the note + drop so the BLUF can never
    # contradict them (the desync that surfaced a Level A bottom line about the
    # wrong disease was the reproduced defect). The wrong-indication efficacy
    # claims are already dropped upstream; any claims that remain are adjacent
    # context the note flags as not-evidence-for-this-indication.
    # Vocabulary OR the structural "<cannabinoid> for <indication>" frame, so an
    # off-lexicon disease (diabetes / breast cancer / lupus) refuses as honestly
    # as a recognised one — the gate is claim coverage, not a hardcoded
    # disease list.
    uncovered_label = _uncovered_efficacy_indication_label(
        a, getattr(a, "prompt", "") or ""
    )
    # Fire the honest override only when the named indication is uncurated AND no
    # surviving efficacy claim actually COVERS the query. "Covers" is on-topic,
    # not merely-present: a chronic-pain SR recovered for a breast-cancer question
    # does not count (see _query_efficacy_is_covered). A mixed "Dravet and autism"
    # query keeps its real Level B Dravet BLUF (Dravet covers); only an
    # all-uncurated query gets the "no curated efficacy evidence" bottom line.
    if uncovered_label and not _query_efficacy_is_covered(
        a, getattr(a, "prompt", "") or ""
    ):
        pretty = uncovered_label
        a.short_answer = (
            f"**No curated efficacy evidence for {pretty}.** The Cannavec "
            f"Science knowledge base holds no graded trial-efficacy claim for "
            f"this indication; any curated context below is adjacent (e.g. "
            f"compound pharmacology or a different indication), not evidence "
            f"that the cannabinoid works for {pretty}. Use the `discover` "
            f"subcommand for a live PubMed / ClinicalTrials.gov search."
        )
        return
    relevant = getattr(a, "_topically_relevant_claims", None)
    if not relevant:
        relevant = tuple(a.claims)
    if not relevant:
        return
    prompt_tokens = _content_tokens(getattr(a, "prompt", "") or "")

    def _key(c: Claim) -> tuple[int, int]:
        return (
            c.best_supportable_grade().rank,
            len(prompt_tokens & _content_tokens(c.text)),
        )

    top = max(relevant, key=_key)
    grade = top.best_supportable_grade()
    frame = _GRADE_FRAME.get(grade, f"Level {grade.value}")
    cites = " ".join(
        Citation.from_source(s, grade=grade).inline for s in top.sources
    )
    text = top.text.rstrip()
    if text and text[-1] not in ".!?":
        text += "."
    a.short_answer = f"**{frame}.** {text} {cites}".rstrip()


# Live lanes that are not peer-reviewed cap at Level D (preprint).
_PREPRINT_LIVE_SOURCES = frozenset({"biorxiv", "medrxiv", "preprint"})

# Live-tier §VIII statuses that warrant a "do not / verify before cite" badge
# AND a last-place rank (a flagged paper must never lead the live breadth). A
# plain CORRECTION is excluded — a correction means the paper stands, so it is
# neither badged nor sunk.
_LIVE_FLAGGED_STATUSES = frozenset(
    {"retracted", "expression_of_concern", "under_correction"}
)
_LIVE_FLAG_LABEL = {
    "retracted": "RETRACTED — do not cite",
    "expression_of_concern": "EXPRESSION OF CONCERN — verify before citing",
    "under_correction": "UNDER CORRECTION — verify before citing",
}


def live_finding_from_row(source_key: str, row: dict) -> "dict | None":
    """Map a live-discovery row (a lane's ``.to_dict()``) to a provisional
    live-finding dict for :meth:`Answer.add_live_finding`.

    Mirrors the identifier / title extraction the ``discover`` CLI uses, so
    the two surfaces agree on a row's headline identifier. Returns ``None``
    when the row carries no primary identifier (nothing citable per §I).
    """
    ident = (
        row.get("pmid") or row.get("nct_id") or row.get("activity_id")
        or row.get("cid") or row.get("pdb_id") or row.get("accession_id")
        or row.get("ensembl_id") or row.get("monomer_id")
        or row.get("chembl_id") or row.get("chebi_id") or row.get("go_id")
        or row.get("doi")
        # NOTE: efo_id and pathway_id are intentionally NOT in this chain.
        # An EFO/ontology id is not a §I primary source (normalization only),
        # and a Reactome pathway weaves only via its literature `pmid` above —
        # a pathway id alone is not citable. Do not add them here.
    )
    if not ident:
        return None
    title = (
        row.get("title") or row.get("brief_title") or row.get("disease_name")
        or row.get("compound") or row.get("chebi_name") or row.get("go_name")
        or ""
    )
    year = row.get("year") or row.get("start_year") or ""
    ident_label = (
        f"PMID {ident}"
        if source_key == "pubmed" and str(ident).isdigit()
        else str(ident)
    )
    grade = (
        "Level D (preprint, not peer-reviewed)"
        if source_key in _PREPRINT_LIVE_SOURCES
        else "provisional (live, unverified)"
    )
    # §VIII for the live tier: citation-check the row's identifier against the
    # retraction registry. A retracted live hit is never silently surfaced —
    # it is badged (and pinned last by the ranker) so a researcher does not
    # cite it. Offline + deterministic (the registry is local).
    from cannavec_science.retraction import is_retracted
    rec = None
    if row.get("pmid"):
        rec = is_retracted(pmid=str(row.get("pmid")))
    if rec is None and row.get("doi"):
        rec = is_retracted(doi=str(row.get("doi")))
    retraction_status = rec.status.value if rec is not None else "clean"
    if retraction_status in _LIVE_FLAGGED_STATUSES:
        grade = f"{_LIVE_FLAG_LABEL[retraction_status]} ({retraction_status})"
    return {
        "label": title,
        "identifier": ident_label,
        "source_tag": f"live_{source_key}",
        "url": row.get("url") or row.get("link") or "",
        "provisional_grade": grade,
        "year": str(year) if year else "",
        "retraction_status": retraction_status,
    }


def compose_answer(
    prompt: str,
    audience: str = "researcher",
    *,
    include_registries: bool = True,
    include_claims: bool = True,
    retraction_policy: str = "strict",
    include_rigor: bool = True,
    retrieval: str = "fallback",
    live: "bool | Mapping[str, object] | None" = None,
    live_sources: "Sequence[str] | None" = None,
    live_max: int = 5,
    live_since: "str | None" = None,
    verified: bool = False,
    verified_store_dir: "str | None" = None,
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
    retrieval:
        Cross-registry BM25 retrieval recovery for the
        "we-have-it-but-didn't-find-it" failure (Improvement Plan §1). The
        per-registry keyword detectors are brittle (word-order / phrasing
        sensitive), so a prompt like "how does THC impair driving" can miss
        the driving rows the KB holds. Modes:

        - ``"fallback"`` (default) — run :mod:`cannavec_science.retrieval`
          only when the deterministic detectors produced **no claims**, then
          attach the best-matching curated rows. Fallback-only means it never
          disturbs a prompt the detectors already answered, so it cannot
          regress existing coverage; it only recovers misses.
        - ``"augment"`` — always union retrieval hits with detector hits
          (retrieval as the primary path; detectors as a precision booster).
        - ``"off"`` — disable retrieval entirely (pre-§1 behaviour).

        Retrieval surfaces **curated** rows only; each keeps its own
        identifier-anchored citations and GRADE (§I / §VII / §IX).
    live:
        Opt-in live-discovery blend (Constitution §IX / §IV) — the
        "one answer, not two endpoints" path. When falsy / ``None``
        (default) ``compose_answer`` stays fully offline and deterministic,
        so the pinned test suite is unchanged. When truthy, after the
        curated core is composed (and unless the prompt was refused), the
        live primary-source tier is fanned out and woven onto the **same**
        brief: provenance-tagged (`live_<source>`), reranked, retraction-
        checked findings under a clearly fenced section, plus the
        deterministic cross-source synthesis verdict
        (STRONG / MIXED / WEAK / NONE) in ``Answer.live_synthesis``. The
        curated claims keep their verified GRADE; the live tier never
        promotes into it. ``True`` uses the production searchers; pass a
        ``Mapping`` of ``{source: runner}`` to inject fakes for offline
        tests. The blend degrades silently — any refusal, offline lane, or
        error leaves the curated brief intact.
    live_sources / live_max / live_since:
        Forwarded to the live fan-out when ``live`` is truthy (which lanes,
        per-lane row cap, and an optional ``YYYY-MM-DD`` recency floor).
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
    # Spec 006 US1-US4 / FR-006 — research-domain-breadth registries.
    from cannavec_science.pain_medicine import detect_pain_medicine_mention
    from cannavec_science.psychiatry import detect_psychiatry_mention
    from cannavec_science.driving_impairment import (
        detect_driving_impairment_mention,
    )
    from cannavec_science.ptsd_anxiety_sleep import (
        detect_ptsd_anxiety_sleep_mention,
    )
    matched_pain_rows = detect_pain_medicine_mention(prompt)
    matched_psychiatry_rows = detect_psychiatry_mention(prompt)
    matched_driving_rows = detect_driving_impairment_mention(prompt)
    matched_ptsd_rows = detect_ptsd_anxiety_sleep_mention(prompt)
    # Spec 026 US1 / FR-026 — cannabis-endocrinology registry (metabolic,
    # reproductive, thyroid, adrenal, somatotropic, skeletal axes).
    from cannavec_science.endocrine import detect_endocrine_mention
    matched_endocrine_rows = detect_endocrine_mention(prompt)

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
    # Spec 006 — research-domain-breadth trace counters.
    a.add_trace("registry.pain_medicine", len(matched_pain_rows))
    a.add_trace("registry.psychiatry", len(matched_psychiatry_rows))
    a.add_trace("registry.driving_impairment", len(matched_driving_rows))
    a.add_trace("registry.ptsd_anxiety_sleep", len(matched_ptsd_rows))
    # Spec 026 — endocrinology trace counter.
    a.add_trace("registry.endocrine", len(matched_endocrine_rows))

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
        # Spec 006 — research-domain-breadth row citations.
        + list(matched_pain_rows)
        + list(matched_psychiatry_rows)
        + list(matched_driving_rows)
        + list(matched_ptsd_rows)
        # Spec 026 — endocrinology row citations.
        + list(matched_endocrine_rows)
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
        # Spec 006 US1-US4 / FR-006 — research-domain-breadth rows.
        for row in matched_pain_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_psychiatry_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_driving_rows:
            _attach_claim_safely(a, row, retraction_policy)
        for row in matched_ptsd_rows:
            _attach_claim_safely(a, row, retraction_policy)
        # Spec 026 US1 / FR-026 — endocrinology rows surface as typed claims.
        for row in matched_endocrine_rows:
            _attach_claim_safely(a, row, retraction_policy)

        # c04 — the population detector fans a seizure/epilepsy keyword out to
        # all three paediatric epilepsy rows (Dravet / LGS / TSC) for recall;
        # when the prompt names a *specific* sub-condition, drop the sibling
        # efficacy claims so a citation binds to a claim only for the indication
        # the prompt actually named. Runs after every primary attach (so it sees
        # the full sibling set) and before the MECHANISM block + all downstream
        # BLUF / grade / zero-claim consumers, which key off ``a.claims``.
        _drop_wrong_sibling_indication_claims(a, prompt)

        # §I / M2 — when the prompt names a recognised indication the curated KB
        # has no efficacy claim for (Tourette / autism / migraine / …), drop the
        # wrong-disease efficacy claims the high-recall populations detector
        # fanned in, so the answer never substitutes a different disease's
        # efficacy as the bottom line. Complements the sibling drop above
        # (curated siblings) and the recovery-path gate (BM25); this closes the
        # PRIMARY detector path. No-op for curated / condition-agnostic queries.
        _drop_offkb_indication_efficacy_claims(a, prompt)

        # c08 — when the question is specifically about MECHANISM ("CBD at
        # 5-HT1A / TRPV1", "Δ⁹-THC CB1 binding affinity", "CBG α2-adrenoceptor",
        # "THCV CB1"), surface the matched cannabinoid's curated receptor
        # activity as first-class typed MECHANISM claims (Russo 2005, Bisogno
        # 2001, Pertwee 2008, Cascio 2010, …), not only monograph prose. Covers
        # BOTH major (CBD, Δ⁹-THC) and minor (CBG, THCV, CBN, CBC, CBDV)
        # cannabinoids — they share the ReceptorActivity schema. This answers
        # the question on-target AND, by making the answer non-thin, stops the
        # BM25 fallback from recovering an off-target mechanism row for a
        # compound-named query.
        if classify_intent(prompt) == Intent.MECHANISM:
            added_mech = 0
            for entry in (*matched_major_cb_rows, *matched_minor_cb_rows):
                for claim in _mechanism_claims_from_cannabinoid_entry(entry):
                    before = len(a.claims)
                    try:
                        a.add_claim(claim)
                    except ClaimWordingError:
                        continue
                    if len(a.claims) > before:
                        added_mech += 1
            if added_mech:
                a.add_trace("mechanism.receptor_claims", added_mech)

        # Minor + major cannabinoids render as monograph sections.
        # No row-level to_claim() — these registries surface as
        # full per-compound evidence pictures with their own
        # multi-claim structure inside the prose monograph.
        if matched_minor_cb_rows or matched_major_cb_rows:
            from cannavec_science.minor_cannabinoids import (
                format_for_researcher as _fmt_minor,
            )
            # Nested under the Answer's ``##`` section heading, which already
            # names the compound: suppress the monograph's own title and render
            # sub-sections at ``###`` so the brief keeps one clean heading tree.
            # ``sections`` narrows the monograph to what the question's intent
            # actually asks for (None = full monograph for broad queries).
            monograph_sections = _monograph_sections_for(prompt)
            for compound in matched_major_cb_rows:
                a.add_section(
                    f"Major cannabinoid monograph — {compound.name}",
                    _fmt_minor(
                        compound, title=False, heading_level=2,
                        sections=monograph_sections,
                    ),
                )
                _attach_monograph_citations(a, compound)
            for compound in matched_minor_cb_rows:
                a.add_section(
                    f"Minor cannabinoid monograph — {compound.name}",
                    _fmt_minor(
                        compound, title=False, heading_level=2,
                        sections=monograph_sections,
                    ),
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
        # Spec 026 US1 / FR-026 — endocrinology registry render.
        if matched_endocrine_rows:
            from cannavec_science.endocrine import (
                render_markdown as render_endocrine,
            )
            a.add_section(
                "Endocrinology registry",
                render_endocrine(matched_endocrine_rows).removeprefix(
                    "## Endocrinology registry\n"
                ).strip(),
            )

        # Improvement Plan §1 — retrieval recovery. The per-registry keyword
        # detectors above are high-precision but brittle; when they surface no
        # typed claim for a prompt the curated KB can actually answer, recover
        # the missed rows by BM25 retrieval over every curated row (e.g. "how
        # does THC impair driving" → the driving registry). ``"fallback"``
        # (default) fires only on a 0-claim result, so it never disturbs a
        # prompt the detectors already answered; ``"augment"`` unions retrieval
        # with the detector hits as the primary path. Retrieval does NOT
        # override the deliberate out-of-scope / deferred guidance notes
        # (spec 003 US9) — those prompts are steered to the parent plugin / a
        # later horizon on purpose, so retrieval is a recovery path for
        # IN-SCOPE misses only.
        if (retrieval == "augment" or (retrieval != "off" and not a.claims)) \
                and not _ZERO_CLAIM_OUT_OF_SCOPE_AUDIENCE_RE.search(prompt) \
                and not _ZERO_CLAIM_DEFERRED_RE.search(prompt):
            _augment_with_retrieval(
                a, prompt, retraction_policy, all_rows, cannabinoid_set,
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

    # §I / M2 / §VII — vocabulary-independent backstop. When the prompt asks
    # efficacy about an indication the curated KB has no clinical-efficacy claim
    # for (a recognised one OR an off-lexicon one like diabetes / breast cancer /
    # lupus via the structural "<cannabinoid> for <indication>" frame), clear the
    # off-topic claims the BM25 recovery / high-recall detectors fanned in so the
    # graded body matches the honest BLUF (no confident "Level C" lead on a
    # wrong-disease mechanism / interaction row). Runs after recovery so it sees
    # the full claim set, and before the note / summary / BLUF that key off it.
    _clear_claims_for_uncovered_efficacy_indication(a, prompt)

    # WP-RETRIEVAL #2 — when the prompt names a specific indication the KB does
    # not curate (e.g. Tourette / Parkinson / glaucoma), say so explicitly so a
    # dropped wrong-indication claim is not silently replaced by adjacent
    # context. Honest "not curated" rather than a confident wrong answer.
    _note_uncurated_indication(a, prompt)

    a.refresh_evidence_summary()
    _set_short_answer(a)

    # ── Verified breadth: gate-passed, human-approved sources (§IX flywheel) ──
    # The middle tier between the curated registry core and the provisional live
    # frontier. Opt-in and fully offline (reads the local verified store — no
    # network), so the default brief is unchanged. Never touches
    # ``evidence_summary`` — breadth augments the core, it does not re-grade it.
    if verified and not a.is_refusal:
        try:
            from cannavec_science.flywheel import weave_verified_findings
            weave_verified_findings(a, prompt=prompt, store_dir=verified_store_dir)
        except Exception:  # noqa: BLE001 — best-effort; the curated core stands
            pass

    # ── Blend: weave citation-checked live breadth onto the curated core ──
    # Constitution §IX (live-discovery contract) + §IV (research-grade breadth
    # without lowering the bar). Opt-in via ``live`` and best-effort: the
    # curated brief above always stands. The weave attaches reranked,
    # retraction-checked, provenance-tagged live findings AND the cross-source
    # synthesis verdict, but never touches ``evidence_summary`` (the curated
    # grade is computed from curated claims only — a live row cannot raise it).
    if live and not a.is_refusal:
        from cannavec_science import live as _live

        runners = live if isinstance(live, Mapping) else None
        try:
            _live.augment_answer(
                a,
                sources=live_sources,
                max_results=live_max,
                since=live_since,
                runners=runners,
            )
        except Exception:  # noqa: BLE001 — blend is best-effort; curated stands
            pass
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
            "see the parent Cannavec plugin for those surfaces. Cannavec "
            "Science is researcher-grade.",
        )
        return
    if _ZERO_CLAIM_DEFERRED_RE.search(prompt):
        a.notes = a.notes + (
            "0 curated claims: this is a research-grade question but sits "
            "in the v0.4 analytical-chemistry / cultivation-science "
            "horizon. Use the `discover` subcommand for a live "
            "PubMed / ChEMBL search.",
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


# WP-RETRIEVAL #2 — human-readable label for each indication tag, used in the
# honest "no curated evidence for <indication>" note. Only the OFF-knowledge-
# base conditions need a label here; a curated indication never reaches the
# note (its efficacy claim covers it). The curated tags map to their own names
# as a safe default so a future curated→uncurated drift still reads cleanly.
_INDICATION_LABEL: "dict[str, str]" = {
    "tourette": "Tourette syndrome",
    "parkinson": "Parkinson's disease",
    "glaucoma": "glaucoma",
    "autism": "autism spectrum disorder",
    "fibromyalgia": "fibromyalgia",
    "als": "ALS / motor neurone disease",
    "ibd": "inflammatory bowel disease",
    "crohn": "Crohn's disease",
    "gvhd": "graft-versus-host disease",
    "alzheimer": "Alzheimer's disease / dementia",
    "migraine": "migraine",
    "ptsd": "PTSD",
    "schizophrenia": "schizophrenia / psychosis",
    "covid": "COVID-19",
}

# The curated indication tags — an efficacy claim about one of these IS in the
# knowledge base, so naming it never triggers the "uncurated" note.
_CURATED_INDICATION_TAGS = frozenset({
    "epilepsy", "dravet", "lennox-gastaut", "tsc", "spasticity",
    "neuropathic_pain", "nausea_vomiting", "cachexia_appetite",
})


def _uncovered_offkb_indications(a: Answer, prompt: str) -> "set[str]":
    """Recognised indications named in the prompt that the curated KB has NO
    graded clinical-efficacy claim for (and that are not curated tags).

    Single source of truth shared by the uncurated-indication note
    (``_note_uncurated_indication``), the wrong-indication efficacy drop
    (``_drop_offkb_indication_efficacy_claims``), and the honest BLUF override
    (``_set_short_answer``) so the three can never disagree — the desync between
    a silent wrong-disease BLUF and a contradictory "not curated" note was the
    reproduced §I/M2 defect. Empty for curated-indication and condition-agnostic
    prompts (no recognised off-KB indication named).
    """
    from cannavec_science.intent import indication_terms

    prompt_indications = indication_terms(prompt)
    if not prompt_indications:
        return set()
    covered: set[str] = set()
    for c in a.claims:
        if c.claim_type == ClaimType.CLINICAL_EFFICACY and c.population:
            covered |= indication_terms(f"{c.population} {c.text}")
    uncovered = prompt_indications - covered
    return {t for t in uncovered if t not in _CURATED_INDICATION_TAGS}


def _note_uncurated_indication(
    a: Answer,
    prompt: str,
) -> None:
    """WP-RETRIEVAL #2 — when the prompt names a condition the curated KB has
    NO trial-supported efficacy claim for, say so explicitly.

    This is the honest other half of the indication gate: after a
    wrong-indication efficacy claim is dropped, the user must not be left
    either with silence or with tangential context masquerading as an answer.
    The note names the uncovered indication and points at the live frontier,
    so "CBD for Tourette" returns "no curated evidence for Tourette syndrome"
    rather than a confident epilepsy brief.

    Fires only when a *recognised* indication is named and NO surviving
    clinical-efficacy claim covers it. It never fires for an on-topic curated
    query (the matching efficacy claim covers the tag) nor for a
    condition-agnostic prompt (no indication tag at all). Skipped on refusals.
    """
    if a.is_refusal:
        return
    # Conditions genuinely outside the curated set — a curated tag that simply
    # didn't surface this run is handled by the zero-claim classifier, not here.
    uncovered_offkb = _uncovered_offkb_indications(a, prompt)
    if not uncovered_offkb:
        return
    names = sorted(_INDICATION_LABEL.get(t, t) for t in uncovered_offkb)
    pretty = ", ".join(names)
    a.notes = a.notes + (
        f"No curated trial evidence for {pretty}: the Cannavec Science "
        f"knowledge base holds no graded efficacy claim for this indication, "
        f"so any curated context shown above is adjacent (e.g. compound "
        f"pharmacology), NOT evidence that the cannabinoid works for "
        f"{pretty}. Use the `discover` subcommand (or the live blend) for a "
        f"PubMed / ClinicalTrials.gov frontier search on this indication.",
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


def _mechanism_claims_from_cannabinoid_entry(entry) -> "list[Claim]":
    """Build typed MECHANISM claims from a cannabinoid's curated
    ``receptor_activity`` rows (c08 recall fix).

    A cannabinoid monograph (major OR minor — both share the
    ``ReceptorActivity`` schema) carries its receptor pharmacology as structured
    rows, but historically those surfaced only as monograph *prose* — so a
    MECHANISM-intent query ("CBD at 5-HT1A / TRPV1", "Δ⁹-THC CB1 binding
    affinity", "CBG α2-adrenoceptor", "THCV CB1") returned no on-target typed
    claim, and the
    thin answer let the BM25 fallback recover an *off-target* mechanism row
    (e.g. a Δ⁹-THC CB1-desensitization row for a CBD query). Emitting one
    primary-source-anchored MECHANISM claim per receptor row fixes both: the
    on-target receptor pharmacology becomes a first-class claim, and the answer
    is no longer thin so the off-target fallback never fires.

    Each row → one Claim graded at the mechanism tier (``SINGLE_ARM_OR_MECH`` →
    Level C). Rows whose receptor activity carries no primary identifier are
    skipped (§I). Wording is a neutral receptor descriptor ("— <activity> at
    <target>"), never an efficacy verb, so it passes the §VII wording check at
    Level C. Robust to entries lacking ``receptor_activity`` (returns []).
    """
    from cannavec_science.evidence import (
        Claim,
        ClaimType,
        Source,
        SourceTier,
        required_disclosures,
    )

    name = getattr(entry, "name", "") or ""
    long_name = getattr(entry, "long_name", "") or name
    out: list[Claim] = []
    for ra in getattr(entry, "receptor_activity", ()) or ():
        sources = tuple(
            Source(
                title=c.label,
                tier=SourceTier.SINGLE_ARM_OR_MECH,
                pmid=c.pmid,
                doi=c.doi,
                url=getattr(c, "url", None),
                year=c.year,
            )
            for c in (getattr(ra, "citations", ()) or ())
            if (c.pmid or c.doi or getattr(c, "url", None))
        )
        if not sources:
            continue  # §I — no verifiable primary identifier; do not emit
        tags = []
        if getattr(ra, "uniprot", None):
            tags.append(f"UniProt {ra.uniprot}")
        if getattr(ra, "gene_symbol", None):
            tags.append(str(ra.gene_symbol))
        tag_str = f" ({'; '.join(tags)})" if tags else ""
        text = f"{long_name} ({name}) — {ra.activity} at {ra.target}{tag_str}."
        note = (getattr(ra, "affinity_note", "") or "").strip()
        if note:
            text += f" {note}"
        caveat = (getattr(ra, "translation_caveat", None) or "").strip()
        if caveat:
            text += f" {caveat}"
        out.append(
            Claim(
                text=text,
                claim_type=ClaimType.MECHANISM,
                sources=sources,
                disclosures_present=required_disclosures(ClaimType.MECHANISM),
            )
        )
    return out


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
    except Exception:  # noqa: BLE001 — malformed row: drop it, but make it auditable
        a.add_trace("claim_build_error", 1)
        return
    if claim is None:
        return

    live_sources = []
    retracted_pmids = []
    for s in claim.sources:
        rec = None
        try:
            if s.pmid:
                rec = is_retracted(pmid=s.pmid)
            if rec is None and s.doi:
                rec = is_retracted(doi=s.doi)
        except Exception:  # noqa: BLE001 — a retraction-registry fault must not
            # crash the whole composition (it used to propagate and kill every
            # remaining row) AND must never silently promote an unverifiable
            # source as "clean". Keep the source, but surface the uncertainty.
            a.add_trace("retraction_check_error", 1)
            a.add_caution(
                "Retraction status could not be verified for one or more "
                "cited sources; treat their currency with caution."
            )
            live_sources.append(s)
            continue
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
        # Some sources retracted, some clean: keep only the clean ones.
        # ``replace`` copies every OTHER field verbatim, so a future field on
        # ``Claim`` can never be silently dropped here — the previous rebuild
        # hand-enumerated nine fields by name and would have lost any new one.
        claim = replace(claim, sources=tuple(live_sources))

    try:
        a.add_claim(claim)
    except ClaimWordingError:
        # Strict-wording mode rejected an over-claim. Record it so the
        # suppression is auditable — the prior comment promised "record but do
        # not crash" yet the body silently dropped the claim with no signal.
        a.add_trace("wording_rejected", 1)


# Improvement Plan §1 — how many recovered rows the retrieval fallback may
# attach. Small by design: it is a recovery path for a thin answer, not a
# firehose. Each attached row still passes the retraction / GRADE / wording
# checks in ``_attach_claim_safely``.
_RETRIEVAL_FALLBACK_K = 6


# c04 — the curated epilepsy family (Dravet / LGS / TSC) is the one place where
# several curated indications share a broader family tag ('epilepsy'), so a
# plain indication-tag intersection cannot separate a query for one
# sub-condition from a sibling's claim. These specific sub-tags drive the
# sibling-precision filter (``_drop_wrong_sibling_indication_claims``) and the
# matching refinement inside ``_recovered_claim_is_wrong_indication``.
_SPECIFIC_INDICATION_SUBTAGS: "frozenset[str]" = frozenset(
    {"dravet", "lennox-gastaut", "tsc"}
)


def _recovered_claim_is_wrong_indication(
    claim: Claim,
    prompt_indications: "frozenset[str]",
) -> bool:
    """WP-RETRIEVAL #2 — is this a recovered efficacy claim for the WRONG
    indication?

    The BM25 recovery path is high-recall: a *clinical-efficacy* row can match
    a prompt on the compound + a generic head noun ("cannabidiol" + "syndrome")
    while being about a completely different condition than the one the prompt
    names — e.g. surfacing the Dravet / LGS / TSC epilepsy rows for "CBD for
    Tourette syndrome tics". Presenting that as a confident graded answer is
    answering a *different question*.

    The gate is deliberately narrow, mirroring the cannabinoid-scope filter:

    - It applies ONLY to a condition-specific claim — a
      :class:`ClaimType.CLINICAL_EFFICACY` claim that carries a ``population``.
      Condition-agnostic recoveries (safety / drug-interaction / PK /
      mechanism / phytochemistry — the driving, CYP, CHS, withdrawal rows the
      retrieval layer exists to recover) are never gated; they answer the
      question regardless of indication.
    - For a condition-specific claim (its own ``indication_terms`` are
      non-empty), it fires when the prompt's condition tags do NOT overlap the
      claim's — including the case where the prompt names NO condition at all
      (a condition-less query must not be answered with a specific
      clinical-efficacy claim recovered by BM25; that is the retrieval layer
      overreaching). A claim that itself names no recognised condition is kept
      (we cannot prove a mismatch).
    """
    from cannavec_science.intent import indication_terms

    if claim.claim_type != ClaimType.CLINICAL_EFFICACY or not claim.population:
        return False
    claim_indications = indication_terms(
        f"{claim.population} {claim.text}"
    )
    # If the claim names no recognised condition either, we cannot prove a
    # mismatch — keep it (conservative; the gate only drops a claim whose
    # condition is *known and different*).
    if not claim_indications:
        return False
    # The claim IS about a specific condition. If the prompt names NO condition
    # at all, a condition-specific clinical-efficacy claim surfaced by BM25 is
    # answering a question the user did not ask — e.g. a generic "muscle spasm"
    # / assay-timing query ("...200 ms after stimulation") recovering the
    # MS-spasticity nabiximols claim (Level B). The retrieval layer exists for
    # condition-AGNOSTIC recoveries (driving / CYP / PK), not for binding a
    # specific clinical-efficacy claim to a condition-less query — so drop it.
    if not prompt_indications:
        return True
    # Sub-tag precision (c04): siblings in one condition family share the family
    # tag (Dravet / LGS / TSC all carry 'epilepsy'), so a plain intersection
    # cannot tell "CBD for TSC" apart from the Dravet row. When the prompt names
    # a *specific* sub-condition and the claim is about a *different* specific
    # sub-condition, it is the wrong indication even though the family tag
    # overlaps. (When the prompt names no specific sub-tag, this is inert and the
    # original family-level intersection governs — broad-query recall preserved.)
    prompt_specific = prompt_indications & _SPECIFIC_INDICATION_SUBTAGS
    claim_specific = claim_indications & _SPECIFIC_INDICATION_SUBTAGS
    if prompt_specific and claim_specific and not (prompt_specific & claim_specific):
        return True
    return not (prompt_indications & claim_indications)


def _drop_wrong_sibling_indication_claims(a: Answer, prompt: str) -> int:
    """Drop efficacy claims for the WRONG sibling sub-condition (closes c04).

    The population detector is deliberately high-recall: a seizure/epilepsy
    keyword fans out to all three paediatric epilepsy rows (Dravet, LGS, TSC)
    because they share the 'epilepsy' family tag. When the prompt names a
    *specific* sub-condition, only that sub-condition's clinical-efficacy claim
    is on-topic — the siblings are real, correctly-cited rows that answer a
    *different* question (e.g. "CBD for TSC seizures" must not lead the BLUF
    with the Dravet trial's 10-20 mg/kg/day convulsive-seizure numbers).

    This guards the PRIMARY detector attach path; the BM25 recovery path applies
    the same sub-tag rule via ``_recovered_claim_is_wrong_indication``. A dropped
    sibling's CITATIONS stay in the bibliography (attached upstream, independent
    of claim gating — §I); only Cannavec's own answer-claim is withheld.

    No-op when the prompt names no specific sub-condition (a broad "CBD for
    epilepsy" / "CBD for seizures" keeps all three — recall preserved). Returns
    the number of claims dropped, also recorded as the
    ``binding.wrong_sibling_dropped`` trace counter (fail-loud, no silent
    swallow).
    """
    from cannavec_science.intent import indication_terms

    prompt_specific = indication_terms(prompt) & _SPECIFIC_INDICATION_SUBTAGS
    if not prompt_specific:
        return 0
    kept: list[Claim] = []
    dropped = 0
    for claim in a.claims:
        if (
            claim.claim_type == ClaimType.CLINICAL_EFFICACY
            and claim.population
        ):
            claim_specific = (
                indication_terms(f"{claim.population} {claim.text}")
                & _SPECIFIC_INDICATION_SUBTAGS
            )
            if claim_specific and not (claim_specific & prompt_specific):
                dropped += 1
                continue
        kept.append(claim)
    if dropped:
        a.claims = kept
        a.add_trace("binding.wrong_sibling_dropped", dropped)
    return dropped


def _drop_offkb_indication_efficacy_claims(a: Answer, prompt: str) -> int:
    """§I / M2 — when the prompt names a recognised indication the curated KB
    has NO graded efficacy claim for, drop the wrong-indication
    CLINICAL_EFFICACY claims the high-recall populations DETECTOR fanned in.

    Closes the primary populations-detector path for an *off-knowledge-base*
    indication (Tourette / autism / Parkinson / migraine / IBD …) — the case the
    two narrower gates miss: ``_drop_wrong_sibling_indication_claims`` only
    separates curated epilepsy *siblings*, and
    ``_recovered_claim_is_wrong_indication`` only gates the BM25 *recovery* path.
    Without this, the detector surfaced a different curated disease's efficacy as
    a confident bottom line for an uncurated query (the reproduced demo-killer:
    "What is the evidence for CBD in Tourette syndrome?" → a Level A neuropathic-
    pain brief).

    Scope limit: "uncurated indication" is detected via
    ``intent.indication_terms``, so this only covers indications that
    recogniser knows (Tourette / autism / Parkinson / glaucoma / migraine /
    IBD / Crohn / ALS / PTSD / …). An indication outside that vocabulary is not
    yet recognised as off-KB and can still leak — widening the recogniser's
    vocabulary is the tracked follow-up.

    Tightly scoped — fires ONLY when ``_uncovered_offkb_indications`` is
    non-empty (the prompt names an uncurated indication), so curated-indication
    and condition-agnostic queries are untouched (recall preserved). It reuses
    the already-tested ``_recovered_claim_is_wrong_indication`` predicate, so an
    efficacy claim is dropped only when its OWN indication does not overlap the
    prompt's (a mixed "Dravet and autism" query keeps the Dravet claim). Only
    CLINICAL_EFFICACY claims are touched; adjacent PK / AE / interaction /
    mechanism context is kept and self-labelled by the uncurated-indication note.
    A dropped claim's CITATIONS stay in the bibliography (attached upstream, §I).
    Returns the count, traced as ``binding.offkb_indication_dropped``
    (fail-loud, never silently swallowed).
    """
    from cannavec_science.intent import indication_terms

    if not _uncovered_offkb_indications(a, prompt):
        return 0
    prompt_indications = indication_terms(prompt)
    kept: list[Claim] = []
    dropped = 0
    for claim in a.claims:
        if _recovered_claim_is_wrong_indication(claim, prompt_indications):
            dropped += 1
            continue
        kept.append(claim)
    if dropped:
        a.claims = kept
        a.add_trace("binding.offkb_indication_dropped", dropped)
    return dropped


# ── Vocabulary-independent off-KB efficacy refusal ──────────────────────────
# The closed indication lexicon (``intent._INDICATION_PATTERNS``) cannot
# enumerate every disease a researcher probes, so an off-list disease (diabetes,
# breast cancer, lupus, Graves, endometriosis …) used to fall through to a
# confident grade-led BLUF stitched onto a BM25-recovered off-topic mechanism /
# interaction row — the citation->claim binding lie this project exists to
# prevent (§I / M2 / §VII). This structural frame is the backstop: a
# "<cannabinoid> for/to-treat <indication>" efficacy question. It is high
# precision by construction — it requires a cannabis cue AND the efficacy
# preposition AND a captured indication object, and the caller fires the honest
# refusal ONLY when no on-topic curated clinical-efficacy claim survives, so
# curated indications and condition-agnostic pharmacology / PK / mechanism
# questions (which carry no "for <indication>" frame) are never swept in. The
# safe failure direction is over-refusal (an honest "no curated efficacy"), never
# a confident wrong answer.
_EFFICACY_FRAME_RX = re.compile(
    r"\b(?:for|to\s+treat|treating|treatment\s+of|therapy\s+for|"
    r"manage|managing|against)\s+"
    r"(?P<indication>[A-Za-z][A-Za-z0-9'’\-]*"
    r"(?:\s+[A-Za-z0-9'’\-]+){0,4})",
    flags=re.IGNORECASE,
)

# Objects after the efficacy preposition that are NOT an indication — model
# systems, study scaffolding, and obvious non-disease nouns. Keeps the structural
# refusal from naming a nonsense "indication" (e.g. "CBD for sale").
_NON_INDICATION_OBJECTS = frozenset({
    "sale", "research", "study", "studies", "trial", "trials", "review",
    "humans", "human", "animals", "animal", "mice", "rats", "dogs", "cats",
    "adults", "adult", "children", "child", "patients", "patient",
    "beginners", "vitro", "vivo", "you", "me", "us", "them", "the", "use",
})

# Cannabis cue — the structural refusal applies only to a "<cannabinoid> for
# <indication>" efficacy frame, never to arbitrary "for X" prose.
_CANNABIS_CUE_RX = re.compile(
    r"\b(?:cannabi\w*|cbd|cannabidiol|thc\w*|tetrahydrocannabinol|cbg\w*|"
    r"cbn|cbc|cbdv|thcv|cbda|thca|marijuana|hemp|cannabinoid\w*|"
    r"nabiximols|sativex|epidiolex|epidyolex|dronabinol|delta.?[89])\b",
    flags=re.IGNORECASE,
)


def _structural_efficacy_indication(prompt: str) -> "str | None":
    """Extract the indication of a "<cannabinoid> for <indication>" efficacy
    question, or ``None`` when the prompt is not that shape.

    Vocabulary-independent — the backstop for diseases ``indication_terms`` does
    not recognise. Conservative: requires a cannabis cue, the efficacy
    preposition, and an indication object that is neither a model-system /
    non-disease noun nor a cannabinoid. Returns the trimmed indication phrase for
    the honest BLUF.
    """
    if not prompt or not _CANNABIS_CUE_RX.search(prompt):
        return None
    m = _EFFICACY_FRAME_RX.search(prompt)
    if not m:
        return None
    phrase = m.group("indication").strip().strip("'’-").strip()
    if len(phrase) < 3:
        return None
    head = phrase.split()[0].lower().strip("'’-")
    if head in _NON_INDICATION_OBJECTS:
        return None
    # An object that is itself a cannabinoid ("THC for CBD") is not an indication.
    if _CANNABIS_CUE_RX.fullmatch(head) or _CANNABIS_CUE_RX.fullmatch(phrase):
        return None
    return phrase


def _uncovered_efficacy_indication_label(a: Answer, prompt: str) -> "str | None":
    """Display label for an indication the prompt asks efficacy about but the
    curated KB has NO clinical-efficacy claim for — vocabulary first (nice
    labels for the recognised diseases), the structural frame as the backstop for
    the long tail. ``None`` when the prompt names no such indication. The caller
    fires the honest refusal only when no curated efficacy claim survives, so this
    never suppresses a real curated answer (Dravet, chronic pain) or a
    condition-agnostic pharmacology question."""
    offkb = _uncovered_offkb_indications(a, prompt)
    if offkb:
        return ", ".join(sorted(_INDICATION_LABEL.get(t, t) for t in offkb))
    return _structural_efficacy_indication(prompt)


def _claim_text_names_indication(claim: Claim, indication: str) -> bool:
    """Does ``claim`` actually name ``indication`` (an OFF-vocabulary structural
    indication the tag lexicon does not recognise)? Discrete whole-phrase match
    over the claim's population + text. A ``cancer`` indication excludes the
    negated "non-cancer", so a chronic-NON-cancer-pain SR does not "cover" a
    breast-cancer question."""
    hay = f"{claim.population or ''} {claim.text}".lower()
    needle = re.escape(indication.lower().strip())
    if re.search(r"\bcancer\b", indication.lower()):
        return re.search(rf"(?<!non.)\b{needle}\b", hay) is not None
    return re.search(rf"\b{needle}\b", hay) is not None


def _query_efficacy_is_covered(a: Answer, prompt: str) -> bool:
    """Is the prompt's efficacy question actually COVERED by a surviving
    clinical-efficacy claim — as opposed to merely having *some* efficacy claim?

    The distinction is the §I/M2 fix for the off-vocabulary long tail. A BM25
    recovery can attach a clinical-efficacy claim about a DIFFERENT condition
    (a chronic-pain SR for a "cannabis for breast cancer" question); its mere
    presence must not count as "the KB has efficacy evidence for breast cancer".

    - No clinical-efficacy claim at all → not covered.
    - The prompt names an IN-vocabulary indication → covered when any efficacy
      claim survives (the wrong-indication claims for these are already removed
      upstream by the indication-tag drops; preserved behaviour, no new coupling).
    - The prompt is an OFF-vocabulary structural "<cannabinoid> for <indication>"
      frame (no tag exists) → covered ONLY when a surviving efficacy claim's text
      actually names that indication (so the Suraev sleep SR covers "sleep" but a
      chronic-pain SR does not cover "breast cancer")."""
    eff = [c for c in a.claims if c.claim_type == ClaimType.CLINICAL_EFFICACY]
    if not eff:
        return False
    from cannavec_science.intent import indication_terms
    if indication_terms(prompt):
        return True
    structural = _structural_efficacy_indication(prompt)
    if not structural:
        return True
    return any(_claim_text_names_indication(c, structural) for c in eff)


def _clear_claims_for_uncovered_efficacy_indication(
    a: Answer, prompt: str
) -> int:
    """§I / M2 / §VII — an efficacy question about an indication with NO curated
    clinical-efficacy claim must surface an honest refusal with an EMPTY graded
    claim set, never a BM25-recovered off-topic mechanism / interaction /
    wrong-disease row stamped with a clinical-evidence grade frame.

    The vocabulary-independent generalisation of
    ``_drop_offkb_indication_efficacy_claims`` AND the citation->claim binding
    fix (closes the Hashimoto's-thyroiditis leak into Alzheimer's / Parkinson's /
    Crohn's, and the confident "Level C" BLUF for diabetes / breast cancer /
    lupus). Fires only when the prompt asks efficacy about an indication
    (vocabulary OR the structural "<cannabinoid> for <indication>" frame) AND no
    surviving CLINICAL_EFFICACY claim covers ANY part of the query. In that
    refuse state every remaining claim is, by construction, adjacent context the
    honest BLUF already demotes — so it is removed from the graded body (its
    CITATIONS stay in the bibliography, §I; the compound monograph stays as fenced
    reference). No-op for curated indications (a covering efficacy claim survives)
    and condition-agnostic queries (no efficacy frame). Returns the count, traced
    as ``binding.uncovered_indication_cleared`` (fail-loud, never silent)."""
    if a.is_refusal:
        return 0
    if _query_efficacy_is_covered(a, prompt):
        return 0
    if not _uncovered_efficacy_indication_label(a, prompt):
        return 0
    dropped = len(a.claims)
    if dropped:
        a.claims = []
        a._topically_relevant_claims = ()
        a.add_trace("binding.uncovered_indication_cleared", dropped)
    return dropped


def _augment_with_retrieval(
    a: Answer,
    prompt: str,
    retraction_policy: str,
    matched_rows: Iterable,
    cannabinoid_set: "NamedCannabinoidSet",
) -> int:
    """Recover curated rows the brittle keyword detectors missed (Plan §1).

    BM25-retrieves the best-matching curated rows for ``prompt`` and attaches
    any not already surfaced by a detector, through the normal claim path so
    retraction / GRADE / wording enforcement all still apply. Best-effort: any
    failure leaves the answer untouched and returns 0. Returns the number of
    claims added.

    Cannabinoid scope filter (spec 003 US2): when the prompt names specific
    cannabinoids, a retrieved row that is specifically *about a different
    cannabinoid* (e.g. a Δ⁹-THC adverse-event row surfacing for an HHC
    question) is skipped, so retrieval never attributes one cannabinoid's
    evidence to another. Cannabinoid-agnostic topic rows (PK, driving, CHS, …)
    are unaffected.
    """
    try:
        from cannavec_science.retrieval import retrieve
        hits = retrieve(prompt, k=_RETRIEVAL_FALLBACK_K)
    except Exception:  # noqa: BLE001 — retrieval is best-effort; never break compose
        return 0
    if not hits:
        return 0
    allowed = cannabinoid_set.all_names if cannabinoid_set else frozenset()
    # WP-RETRIEVAL #2 — the condition(s) the prompt actually names. Used to
    # reject a recovered efficacy claim about a *different* condition.
    from cannavec_science.intent import indication_terms
    prompt_indications = indication_terms(prompt)
    already = {id(r) for r in matched_rows}
    added = 0
    for h in hits:
        if id(h.row) in already or not hasattr(h.row, "to_claim"):
            continue
        try:
            claim = h.row.to_claim()
        except Exception:  # noqa: BLE001 — malformed recovered row: skip, audibly
            a.add_trace("retrieval.claim_build_error", 1)
            claim = None
        if claim is None:
            continue
        # Indication-scope filter (mirrors the cannabinoid-scope filter below):
        # never present a curated efficacy claim about a different condition as
        # the answer to a question that names a specific indication.
        if _recovered_claim_is_wrong_indication(claim, prompt_indications):
            continue
        if allowed:
            # The prompt names a specific cannabinoid, so a recovered row must
            # actually be about it. This skips both wrong-cannabinoid rows
            # (a Δ⁹-THC AE row for an HHC query) and cannabinoid-agnostic rows
            # (a generic FAAH-inhibitor row), so retrieval never attributes
            # unrelated evidence to the queried cannabinoid (spec 003 US2). A
            # topic row that names the cannabinoid in its claim (e.g. the
            # driving rows cite Δ⁹-THC) still resolves into scope and passes.
            disc = (
                getattr(h.row, "cannabinoid", None)
                or getattr(h.row, "compound", None)
                or ""
            )
            row_cb = resolve_named_cannabinoid_set(
                f"{disc} {claim.text}"
            ).all_names
            if not (row_cb & allowed):
                continue
        before = len(a.claims)
        _attach_citations_from_row(a, h.row)
        _attach_claim_safely(a, h.row, retraction_policy)
        if len(a.claims) > before:
            already.add(id(h.row))
            added += 1
    if added:
        a.add_trace("retrieval.recovered", added)
    return added


def merge_citations(answers: Iterable[Answer]) -> list[Citation]:
    """Deduplicate Citations across multiple Answers.

    Uses the same :func:`_is_same_citation` identity rule as
    :meth:`Answer.add_citation`, so the single-answer and merged bibliographies
    cannot disagree (they previously diverged on URL-only matches).
    """
    out: list[Citation] = []
    for a in answers:
        for c in a.citations:
            if not any(_is_same_citation(c, existing) for existing in out):
                out.append(c)
    return out
