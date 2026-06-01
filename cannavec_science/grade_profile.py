"""GRADE evidence-profile table (spec 002 US2).

Emits the table journals + IRBs ask for: per-outcome × number-of-studies
× risk-of-bias × inconsistency × indirectness × imprecision × publication-
bias × effect estimate × certainty. The output is deterministic — same
input ``Answer`` → same table.

Markdown is the default rendering; CSV is available via
``render_csv`` for spreadsheet import.

The certainty column derives from the typed ``Answer.evidence_summary``
+ per-claim ``best_supportable_grade()``. The downgrade columns
(risk-of-bias / inconsistency / indirectness / imprecision /
publication-bias) reflect whether the GRADE adapter recorded the
corresponding flag during composition — read off the claim sources.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable


__all__ = [
    "GradeProfileRow",
    "GradeProfile",
    "build_profile",
    "render_markdown",
    "render_csv",
    "CertaintyDomain",
    "MetaCertainty",
    "certainty_from_meta",
    "render_certainty",
]


@dataclass(frozen=True)
class GradeProfileRow:
    """One outcome row in the GRADE evidence-profile table."""

    outcome: str
    n_studies: int
    study_designs: tuple[str, ...]
    risk_of_bias: str = "not serious"
    inconsistency: str = "not serious"
    indirectness: str = "not serious"
    imprecision: str = "not serious"
    publication_bias: str = "undetected"
    effect_estimate: str = "—"
    certainty: str = "Unsupported"
    n_pmids: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["study_designs"] = list(self.study_designs)
        return d


@dataclass(frozen=True)
class GradeProfile:
    """Deterministic GRADE evidence-profile table for an Answer."""

    rows: tuple[GradeProfileRow, ...]
    answer_prompt: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "answer_prompt": self.answer_prompt,
            "generated_at": self.generated_at,
            "rows": [r.to_dict() for r in self.rows],
        }


# ── Builder ─────────────────────────────────────────────────────────


def _outcome_label(claim: object, idx: int) -> str:
    """Pick a human-readable outcome label for the row.

    Prefers the claim's ``primary_outcome``-shaped attribute when
    available; falls back to the first clause of the claim text.
    """
    for attr in ("primary_outcome", "indication", "outcome"):
        v = getattr(claim, attr, None)
        if v:
            return str(v)[:90]
    text = getattr(claim, "text", "") or ""
    clause = text.split(".")[0].strip()
    if not clause:
        return f"Outcome {idx + 1}"
    return clause[:90]


def _study_design_of_source(source: object) -> str:
    """Map a Source to a GRADE study-design label."""
    explicit = getattr(source, "study_design", None)
    if explicit:
        return str(explicit)
    tier = getattr(source, "tier", None)
    try:
        tier_value = int(tier) if tier is not None else 8
    except (TypeError, ValueError):
        tier_value = 8
    return {
        1: "SR / flagship RCT",
        2: "RCT (specialist journal)",
        3: "single-arm / mechanistic",
        4: "preprint / small case series",
        5: "regulator / pharmacopoeia",
        6: "industry / conference",
        7: "trade press / advocacy",
        8: "anonymous / unsigned",
    }.get(tier_value, "unknown")


def _imprecision(sources: tuple) -> str:
    """Imprecision = serious if any cited source has sample_size < 50 OR
    no sources cite a sample size and there is only one source."""
    sample_sizes = [
        getattr(s, "sample_size", None) for s in sources
        if getattr(s, "sample_size", None) is not None
    ]
    if not sources:
        return "n/a"
    if not sample_sizes:
        return "serious (sample sizes not reported)" if len(sources) <= 1 else "not serious"
    smallest = min(sample_sizes)
    if smallest < 50:
        return f"serious (n_min = {smallest})"
    return "not serious"


def _publication_bias(sources: tuple) -> str:
    """Publication-bias heuristic: serious when only one source AND it
    is not pre-registered. Otherwise undetected. (GRADE's actual
    publication-bias inference requires a funnel plot; this is a
    conservative deterministic proxy.)"""
    if len(sources) <= 1:
        any_prereg = any(getattr(s, "pre_registered", False) for s in sources)
        if not any_prereg:
            return "strongly suspected (single non-prereg source)"
        return "undetected"
    return "undetected"


def _risk_of_bias(sources: tuple) -> str:
    """Serious if any source has undeclared COI, or is at tier ≥ 6."""
    serious_flags: list[str] = []
    for s in sources:
        if getattr(s, "coi_undeclared_surfaced", False):
            serious_flags.append("undeclared COI")
        try:
            tier_value = int(getattr(s, "tier", 8))
        except (TypeError, ValueError):
            tier_value = 8
        if tier_value >= 6:
            serious_flags.append(f"tier {tier_value}")
    if serious_flags:
        unique = sorted(set(serious_flags))
        return f"serious ({'; '.join(unique)})"
    return "not serious"


def _effect_estimate(claim: object) -> str:
    """Pull a free-text effect estimate from the claim, if present."""
    for attr in ("effect_size", "magnitude_note", "magnitude"):
        v = getattr(claim, attr, None)
        if v:
            return str(v)[:120]
    text = getattr(claim, "text", "") or ""
    # Look for percentage / mean-difference / OR / RR / HR shapes.
    import re
    m = re.search(
        r"(?:reduced|increased|absolute|relative|HR|OR|RR|MD)"
        r".{0,40}?\d+(?:\.\d+)?\s*%?(?:\s*\([^)]*\))?",
        text, flags=re.IGNORECASE,
    )
    if m:
        return m.group(0)[:120]
    return "—"


def _downgrade_certainty(certainty: object, steps: int) -> str:
    """Downgrade a certainty grade by ``steps`` GRADE levels.

    Routes quantitative downgrade findings (spec 011 inconsistency, spec 012
    publication bias) through the same ``evidence._downgrade`` ladder the
    GRADE adapter uses, so the profile's certainty column stays consistent
    with :func:`evidence.apply_grade_modifiers`. Accepts ``certainty`` as
    either an :class:`~cannavec_science.evidence.EvidenceLevel` or its label.
    """
    label = getattr(certainty, "value", str(certainty))
    if steps <= 0:
        return label
    from cannavec_science.evidence import EvidenceLevel, _downgrade

    level = certainty if isinstance(certainty, EvidenceLevel) else None
    if level is None:
        for lvl in EvidenceLevel:
            if lvl.value == label:
                level = lvl
                break
    if level is None:
        return label
    return _downgrade(level, steps).value


def build_profile(
    answer: object,
    *,
    meta_by_outcome: dict | None = None,
    pubbias_by_outcome: dict | None = None,
) -> GradeProfile:
    """Build a GRADE evidence-profile table for ``answer``.

    One row per claim. When ``answer`` has no claims, returns a
    single-row table with the "no admissible evidence" message
    (per the spec's zero-claim edge case).

    ``meta_by_outcome`` (spec 011) optionally maps an outcome label to a
    :class:`cannavec_science.meta_analysis.MetaAnalysisResult`. When a row's
    outcome label matches a key, the row's *inconsistency* column is taken
    from the quantitative heterogeneity verdict instead of the conservative
    ``"not serious"`` default.

    ``pubbias_by_outcome`` (spec 012) optionally maps an outcome label to an
    :class:`cannavec_science.meta_analysis.EggerResult`. When matched, the
    *publication-bias* column is taken from Egger's small-study-effects test.

    Both findings downgrade the certainty grade cumulatively through the same
    ``evidence._downgrade`` ladder the GRADE adapter uses. Both parameters
    default to ``None`` — existing callers and tests are unaffected.
    """
    claims = tuple(getattr(answer, "claims", ()) or ())
    prompt = getattr(answer, "prompt", "") or ""
    generated_at = getattr(answer, "generated_at", "") or ""

    if not claims:
        return GradeProfile(
            rows=(
                GradeProfileRow(
                    outcome="No admissible evidence",
                    n_studies=0,
                    study_designs=(),
                    risk_of_bias="n/a",
                    inconsistency="n/a",
                    indirectness="n/a",
                    imprecision="n/a",
                    publication_bias="n/a",
                    effect_estimate="—",
                    certainty="Unsupported",
                    n_pmids=0,
                ),
            ),
            answer_prompt=prompt,
            generated_at=generated_at,
        )

    rows: list[GradeProfileRow] = []
    for idx, claim in enumerate(claims):
        sources = tuple(getattr(claim, "sources", ()) or ())
        # Inconsistency: if multiple sources exist, deterministically
        # default to "not serious" — the citation_network signal can
        # set this to "serious" downstream via apply_grade_modifiers
        # (US4). Indirectness: serious if the source population type
        # differs from the claim's population.
        rob = _risk_of_bias(sources)
        imprec = _imprecision(sources)
        pubbias = _publication_bias(sources)
        certainty = (
            getattr(claim, "best_supportable_grade", lambda: None)() or "Unsupported"
        )
        # Convert EvidenceLevel → string label.
        certainty_label = getattr(certainty, "value", str(certainty))
        designs = tuple(sorted({_study_design_of_source(s) for s in sources}))
        n_pmids = sum(1 for s in sources if getattr(s, "pmid", None))

        # Inconsistency (spec 011) and publication bias (spec 012) become
        # data-driven when a quantitative result is supplied for this
        # outcome; both default to the conservative heuristic otherwise. The
        # two findings downgrade the certainty grade cumulatively through the
        # same GRADE ladder the adapter uses.
        outcome_label = _outcome_label(claim, idx)
        extra_steps = 0

        inconsistency_label = "not serious"
        meta = (meta_by_outcome or {}).get(outcome_label)
        if meta is not None:
            inconsistency_label = getattr(meta, "inconsistency", "not serious")
            extra_steps += int(getattr(meta, "downgrade_steps", 0) or 0)

        pubbias_label = pubbias
        egger = (pubbias_by_outcome or {}).get(outcome_label)
        if egger is not None:
            from cannavec_science.meta_analysis import grade_publication_bias
            pb_label, pb_serious, _rationale = grade_publication_bias(egger)
            pubbias_label = pb_label
            if pb_serious:
                extra_steps += 1

        certainty_label = _downgrade_certainty(certainty, extra_steps)

        rows.append(GradeProfileRow(
            outcome=outcome_label,
            n_studies=len(sources),
            study_designs=designs,
            risk_of_bias=rob,
            inconsistency=inconsistency_label,
            indirectness="not serious",
            imprecision=imprec,
            publication_bias=pubbias_label,
            effect_estimate=_effect_estimate(claim),
            certainty=certainty_label,
            n_pmids=n_pmids,
        ))
    return GradeProfile(
        rows=tuple(rows),
        answer_prompt=prompt,
        generated_at=generated_at,
    )


# ── Renderers ───────────────────────────────────────────────────────


def render_markdown(profile: GradeProfile) -> str:
    """Markdown rendering — column shape matches journal expectations."""
    lines: list[str] = []
    lines.append("## GRADE evidence-profile table")
    lines.append("")
    lines.append(
        "| Outcome | #studies | Design | Risk of bias | Inconsistency | "
        "Indirectness | Imprecision | Publication bias | Effect | Certainty |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in profile.rows:
        outcome = r.outcome.replace("|", "\\|")
        if len(outcome) > 60:
            outcome = outcome[:57] + "…"
        designs = ", ".join(r.study_designs) if r.study_designs else "—"
        if len(designs) > 60:
            designs = designs[:57] + "…"
        effect = r.effect_estimate.replace("|", "\\|")
        if len(effect) > 60:
            effect = effect[:57] + "…"
        lines.append(
            f"| {outcome} | {r.n_studies} | {designs} | {r.risk_of_bias} | "
            f"{r.inconsistency} | {r.indirectness} | {r.imprecision} | "
            f"{r.publication_bias} | {effect} | **{r.certainty}** |"
        )
    lines.append("")
    lines.append(
        "_GRADE per Schünemann et al. 2013. Risk-of-bias, inconsistency, "
        "indirectness, imprecision, and publication-bias columns "
        "deterministically derive from cited Source metadata; certainty "
        "from the per-claim ``best_supportable_grade``._"
    )
    return "\n".join(lines)


def render_csv(profile: GradeProfile) -> str:
    """CSV rendering — spreadsheet-importable."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "outcome", "n_studies", "study_designs",
        "risk_of_bias", "inconsistency", "indirectness",
        "imprecision", "publication_bias",
        "effect_estimate", "certainty", "n_pmids",
    ])
    for r in profile.rows:
        w.writerow([
            r.outcome, r.n_studies, "; ".join(r.study_designs),
            r.risk_of_bias, r.inconsistency, r.indirectness,
            r.imprecision, r.publication_bias,
            r.effect_estimate, r.certainty, r.n_pmids,
        ])
    return buf.getvalue()


# ── GRADE certainty rating for a meta-analysis pool (spec 016) ───────
#
# Completes the Summary-of-Findings deliverable: spec 015 gives the absolute
# effect + NNT columns; this gives the certainty column. It composes the five
# GRADE downgrade domains through the *same* ``evidence._downgrade`` ladder the
# evidence-profile table and ``apply_grade_modifiers`` use — three domains are
# computed from the pooled body of evidence, two are honest reviewer inputs.

# The A↔High / B↔Moderate / C↔Low / D,E↔Very Low correspondence is the inverse
# of ``uncertainty._GRADE_FROM_STR`` — kept consistent on purpose (§II).
_GRADE_WORD = {
    "Level A": "High",
    "Level B": "Moderate",
    "Level C": "Low",
    "Level D": "Very Low",
    "Level E": "Very Low",
    "Unsupported": "Unsupported",
}
_GRADE_GLYPH = {
    "High": "⊕⊕⊕⊕",
    "Moderate": "⊕⊕⊕⊝",
    "Low": "⊕⊕⊝⊝",
    "Very Low": "⊕⊝⊝⊝",
    "Unsupported": "⊝⊝⊝⊝",
}
_SERIOUSNESS_STEPS = {"not serious": 0, "serious": 1, "very serious": 2}


def _norm_seriousness(value: object) -> str:
    """Normalise ``not-serious`` / ``very_serious`` / etc. to canonical text."""
    text = str(value).strip().lower().replace("-", " ").replace("_", " ")
    text = " ".join(text.split())
    return text if text in _SERIOUSNESS_STEPS else "not serious"


@dataclass(frozen=True)
class CertaintyDomain:
    """One GRADE certainty domain and its contribution to the rating."""

    name: str
    assessment: str
    steps: int
    basis: str            # "computed (...)" | "reviewer-assessed" | ...

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MetaCertainty:
    """A deterministic GRADE certainty rating for a pooled body of evidence."""

    base_grade: str
    level: str
    grade_word: str
    glyph: str
    total_steps: int
    domains: tuple[CertaintyDomain, ...]
    rationale: str

    def to_dict(self) -> dict:
        return {
            "base_grade": self.base_grade,
            "level": self.level,
            "grade_word": self.grade_word,
            "glyph": self.glyph,
            "total_steps": self.total_steps,
            "domains": [d.to_dict() for d in self.domains],
            "rationale": self.rationale,
        }


def certainty_from_meta(
    result,
    *,
    evidence_base: str = "rct",
    risk_of_bias: str = "not serious",
    indirectness: str = "not serious",
    egger=None,
) -> MetaCertainty:
    """Rate the certainty of a :class:`MetaAnalysisResult`'s pooled estimate.

    Computed domains: **inconsistency** (spec 011 I² verdict), **imprecision**
    (the pooled 95% CI crossing the null), and **publication bias** (Egger,
    when supplied, with the spec 012 ``k ≥ 10`` honesty). Reviewer inputs:
    **risk of bias** and **indirectness** (``not serious`` / ``serious`` /
    ``very serious``). The starting grade is the body design — a randomised
    body starts High (Level A), an observational body Low (Level C), per §VII.
    """
    from cannavec_science.evidence import EvidenceLevel, _downgrade

    base = (
        EvidenceLevel.A
        if str(evidence_base).strip().lower() in
        ("rct", "rcts", "randomized", "randomised", "trial", "trials")
        else EvidenceLevel.C
    )

    rob = _norm_seriousness(risk_of_bias)
    ind = _norm_seriousness(indirectness)
    inc_steps = int(getattr(result, "downgrade_steps", 0) or 0)
    inc_label = str(getattr(result, "inconsistency", "not serious"))

    lo, hi = result.random_ci_display
    null = result.null_value_display
    imprecise = lo <= null <= hi

    if egger is not None:
        from cannavec_science.meta_analysis import grade_publication_bias
        pb_label, pb_serious, _rationale = grade_publication_bias(egger)
        pb_steps = 1 if pb_serious else 0
        pb_basis = f"computed (Egger, k={getattr(egger, 'k', '?')})"
    else:
        pb_label, pb_steps = "not assessed", 0
        pb_basis = "not assessed (run --diagnostics)"

    domains = (
        CertaintyDomain("Risk of bias", rob, _SERIOUSNESS_STEPS[rob],
                        "reviewer-assessed"),
        CertaintyDomain("Inconsistency", inc_label, inc_steps,
                        f"computed (I²={result.i_squared:.0f}%)"),
        CertaintyDomain("Indirectness", ind, _SERIOUSNESS_STEPS[ind],
                        "reviewer-assessed"),
        CertaintyDomain(
            "Imprecision",
            "serious — 95% CI crosses the null" if imprecise else "not serious",
            1 if imprecise else 0,
            "computed (pooled 95% CI vs null)",
        ),
        CertaintyDomain("Publication bias", pb_label, pb_steps, pb_basis),
    )

    total = sum(d.steps for d in domains)
    level = _downgrade(base, total)
    word = _GRADE_WORD.get(level.value, "Very Low")
    glyph = _GRADE_GLYPH.get(word, "⊝⊝⊝⊝")

    serious = [d.name.lower() for d in domains if d.steps > 0]
    if serious:
        why = "downgraded for " + ", ".join(serious)
    else:
        why = "no serious limitations across the five GRADE domains"
    rationale = (
        f"Started at {base.value} ({_GRADE_WORD[base.value]}) for a "
        f"{'randomised-trial' if base is EvidenceLevel.A else 'observational'} "
        f"body; {why}; final certainty {level.value} ({word})."
    )

    return MetaCertainty(
        base_grade=base.value,
        level=level.value,
        grade_word=word,
        glyph=glyph,
        total_steps=total,
        domains=domains,
        rationale=rationale,
    )


def render_certainty(mc: MetaCertainty) -> str:
    """Render the certainty rating as a Markdown block for the SoF deliverable."""
    lines = [
        "### GRADE certainty of evidence",
        "",
        f"**{mc.glyph} {mc.grade_word}** ({mc.level}) — "
        f"{mc.total_steps} downgrade step(s) from {mc.base_grade}.",
        "",
        "| Domain | Assessment | Downgrade | Basis |",
        "|---|---|---|---|",
    ]
    for d in mc.domains:
        step = "—" if d.steps == 0 else f"−{d.steps}"
        assessment = d.assessment.replace("|", "\\|")
        lines.append(f"| {d.name} | {assessment} | {step} | {d.basis} |")
    lines.append("")
    lines.append(
        "- _Risk of bias and indirectness are reviewer-assessed inputs, not "
        "computed — supply `--risk-of-bias` / `--indirectness` to record your "
        "assessment (§II)._"
    )
    lines.append(f"- _{mc.rationale}_")
    return "\n".join(lines)
