"""Typed Answer artifact + deterministic composer.

A Cannavec Science ``Answer`` is the composable, audience-agnostic object
every surface produces. Prose output is one rendering; ``Answer`` is the
underlying typed contract.

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
        highest = EvidenceLevel.UNSUPPORTED
        n_primary = 0
        n_missing = 0
        for c in self.claims:
            grade = c.best_supportable_grade()
            if grade.rank > highest.rank:
                highest = grade
            if any(s.pmid or s.doi or s.url for s in c.sources):
                n_primary += 1
            if missing_disclosures(c.claim_type, c.disclosures_present):
                n_missing += 1
        self.evidence_summary = EvidenceSummary(
            highest_grade=highest,
            n_claims=len(self.claims),
            n_with_primary_source=n_primary,
            n_missing_required_disclosures=n_missing,
            n_retracted_citations=len(self.retractions_suppressed),
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

        if self.citations:
            lines.append("## Citations")
            lines.append("")
            for c in self.citations:
                grade_tag = f" — {c.grade.value}" if c.grade else ""
                year = f" ({c.year})" if c.year else ""
                lines.append(
                    f"- {c.label}{year}{grade_tag} — {c.resolvable_url}"
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

    matched_population_rows = _specific_or_class(
        detect_population_mention(prompt),
        detect_population_class_mention(prompt),
    )
    matched_interaction_rows = _specific_or_class(
        detect_interaction_mention(prompt),
        detect_interaction_class_mention(prompt),
    )
    matched_ae_rows = _specific_or_class(
        detect_adverse_event_mention(prompt),
        detect_adverse_event_class_mention(prompt),
    )
    matched_contraindication_rows = _specific_or_class(
        detect_contraindication_mention(prompt),
        detect_contraindication_class_mention(prompt),
    )
    matched_minor_cb_rows = detect_minor_cannabinoid_mention(prompt)
    # Major-cannabinoid monograph fires only when the prompt names
    # 2+ cannabinoids (comparison intent). A specific "how does CBD
    # interact with clobazam" query should not dump the full CBD
    # monograph — the strict interaction matcher already handles it.
    major_hits_raw = detect_major_cannabinoid_mention(prompt)
    total_compounds_named = len(major_hits_raw) + len(matched_minor_cb_rows)
    matched_major_cb_rows = major_hits_raw if total_compounds_named >= 2 else ()
    matched_terpene_rows = detect_terpene_mention(prompt)
    matched_pgx_rows = find_pgx_hits(prompt)

    a.add_trace("registry.populations", len(matched_population_rows))
    a.add_trace("registry.interactions", len(matched_interaction_rows))
    a.add_trace("registry.adverse_events", len(matched_ae_rows))
    a.add_trace("registry.contraindications", len(matched_contraindication_rows))
    a.add_trace("registry.minor_cannabinoids", len(matched_minor_cb_rows))
    a.add_trace("registry.major_cannabinoids", len(matched_major_cb_rows))
    a.add_trace("registry.terpenes", len(matched_terpene_rows))
    a.add_trace("registry.pharmacogenomics", len(matched_pgx_rows))

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
    )
    for row in all_rows:
        _attach_citations_from_row(a, row)

    if include_claims and not safety_refused and not banned_hits:
        # Six registries with row-level .to_claim() — typed claims.
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
    elif matched_minor_cb_rows or matched_major_cb_rows:
        # Refused prompt: still surface the cannabinoid citations so
        # downstream readers see the evidence base.
        for compound in matched_major_cb_rows:
            _attach_monograph_citations(a, compound)
        for compound in matched_minor_cb_rows:
            _attach_monograph_citations(a, compound)

    a.refresh_evidence_summary()
    return a


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
