"""IRB / protocol skeleton (spec 002 US2).

Deterministic 9-section IRB-ready protocol stub. Pre-populated from the
Answer's claims + PICO block; emits a hard watermark on line 1:
``Auto-generated skeleton — PI must review and supplement.``

The skeleton is NOT a substitute for protocol authorship — it is a
deterministic scaffold the PI fills in. Every section carries explicit
placeholders ("[PI to specify]") where deterministic composition cannot
supply the content.

Word cap: < 1500 words by construction. The composer truncates long
free-text inputs (claim text, citation labels) to keep within bound.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


__all__ = [
    "ProtocolSkeleton",
    "build_skeleton",
    "render_markdown",
]


WATERMARK: str = (
    "_**Auto-generated skeleton — PI must review and supplement. "
    "Not a substitute for protocol authorship.**_"
)


@dataclass(frozen=True)
class ProtocolSkeleton:
    """Nine-section IRB protocol stub.

    Each field is the body Markdown of that section. The renderer
    composes the full document with the watermark + section headers.
    """

    background: str
    hypothesis: str
    specific_aims: str
    study_design: str
    population: str
    intervention: str
    endpoints: str
    statistical_analysis: str
    safety_monitoring: str
    word_count: int = 0
    answer_prompt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Builder ─────────────────────────────────────────────────────────


def _truncate(s: str, n: int) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _join_citations(answer: object, cap: int = 5) -> str:
    citations = list(getattr(answer, "citations", []) or [])
    if not citations:
        return "_(no citations available — PI to add primary sources)_"
    out: list[str] = []
    for c in citations[:cap]:
        pmid = getattr(c, "pmid", None)
        label = getattr(c, "label", "") or "Untitled"
        year = getattr(c, "year", None)
        if pmid:
            tag = f"PMID {pmid}"
        elif getattr(c, "doi", None):
            tag = f"doi:{c.doi}"
        else:
            tag = "URL"
        suffix = f" ({year})" if year else ""
        out.append(f"- {_truncate(label, 100)}{suffix} [{tag}]")
    if len(citations) > cap:
        out.append(f"- … plus {len(citations) - cap} more citations")
    return "\n".join(out)


def _summarise_claims(answer: object, cap: int = 3) -> str:
    claims = list(getattr(answer, "claims", []) or [])
    if not claims:
        return "_(no curated-registry claims fired — PI to specify background)_"
    out: list[str] = []
    for c in claims[:cap]:
        grade = getattr(c, "best_supportable_grade", lambda: None)()
        grade_label = getattr(grade, "value", "Unsupported")
        text = _truncate(getattr(c, "text", ""), 220)
        out.append(f"- [{grade_label}] {text}")
    return "\n".join(out)


def build_skeleton(
    answer: object,
    pico: object = None,
) -> ProtocolSkeleton:
    """Build a 9-section protocol stub from an Answer (+ optional PICO).

    The composer reads from the typed Answer's claims and citations,
    and from the PICOBlock if one is supplied. Both are optional —
    missing inputs surface as "[PI to specify]".
    """
    prompt = getattr(answer, "prompt", "") or ""

    # 1. Background — claim summary + citation list.
    background = (
        f"Cannavec Science research brief identified the following "
        f"curated-registry evidence relevant to the protocol question "
        f"\"{_truncate(prompt, 120)}\":\n\n"
        f"{_summarise_claims(answer)}\n\n"
        f"Primary sources surfaced for this brief:\n\n"
        f"{_join_citations(answer)}"
    )

    # 2. Hypothesis — from intent + PICO intervention.
    if pico is not None:
        intervention = getattr(pico, "intervention", "[PI to specify]")
        population_label = getattr(pico, "population", "[PI to specify]")
    else:
        intervention = "[PI to specify]"
        population_label = "[PI to specify]"

    hypothesis = (
        f"In the population of {population_label}, "
        f"administration of {intervention} versus comparator will "
        f"produce a measurable change in the primary outcome (specify "
        f"effect direction and magnitude). [PI to refine.]"
    )

    # 3. Specific Aims — derived from PICO outcomes.
    if pico is not None and getattr(pico, "outcomes", None):
        aim_lines = []
        for i, o in enumerate(getattr(pico, "outcomes")[:3], start=1):
            aim_lines.append(f"{i}. {o}")
        specific_aims = "\n".join(aim_lines)
    else:
        specific_aims = (
            "1. [PI to specify primary aim — outcome measure + timepoint]\n"
            "2. [PI to specify secondary aim — mechanism / pharmacology]\n"
            "3. [PI to specify exploratory aim — biomarkers / subgroup]"
        )

    # 4. Study Design — based on intent classifier of the prompt.
    from cannavec_science.intent import classify_intent
    intent = classify_intent(prompt)
    intent_value = intent.value
    if intent_value in ("efficacy", "dosing"):
        design_default = (
            "Randomised, double-blind, placebo-controlled, parallel-arm "
            "trial. Block-randomised by site if multi-site. Allocation "
            "concealed via central web-based system."
        )
    elif intent_value == "interaction":
        design_default = (
            "Within-subject crossover pharmacokinetic study with two "
            "treatment periods separated by ≥ 7 half-lives of the "
            "longer-lived agent. Order randomised."
        )
    elif intent_value == "safety_risk":
        design_default = (
            "Prospective observational cohort with matched "
            "non-exposed controls. Active surveillance for the index "
            "adverse-event class with adjudication committee."
        )
    elif intent_value == "mechanism":
        design_default = (
            "Pre-registered mechanism-of-action study with primary "
            "in-vitro / ex-vivo readouts followed by confirmatory "
            "in-vivo validation. Vehicle-controlled."
        )
    else:
        design_default = (
            "[PI to specify design — RCT / cohort / case-control / "
            "crossover / mechanism]"
        )
    study_design = (
        f"Intent classified as `{intent_value}` from the protocol "
        f"question. Recommended starting design:\n\n{design_default}\n\n"
        f"PI to confirm and add: site count, randomisation block size, "
        f"blinding strategy, allocation concealment mechanism."
    )

    # 5. Population.
    population = (
        f"{population_label}\n\n"
        f"Inclusion criteria: [PI to specify — age band, diagnostic "
        f"criteria, prior-treatment history].\n\n"
        f"Exclusion criteria: [PI to specify — pregnancy, controlled "
        f"substance use disorder, hepatic / renal impairment, "
        f"contraindicating concomitant medications]."
    )

    # 6. Intervention.
    intervention_section = (
        f"Intervention: {intervention}.\n\n"
        f"Route: [PI to specify — oral / sublingual / inhaled / "
        f"transdermal].\n\n"
        f"Dose + titration: [PI to specify — starting dose, escalation "
        f"schedule, maximum dose, fixed-vs-titrated]. Note: dosing "
        f"specification is per-protocol; default to evidence-supported "
        f"trial-tested ranges from the cited literature.\n\n"
        f"Comparator: {getattr(pico, 'comparator', '[PI to specify]') if pico else '[PI to specify]'}."
    )

    # 7. Endpoints.
    endpoints = (
        "Primary endpoint: [PI to specify — validated outcome measure + "
        "timepoint].\n\n"
        "Secondary endpoints: [safety profile, quality-of-life, "
        "pharmacokinetic parameters as appropriate].\n\n"
        "Exploratory endpoints: [mechanism biomarkers, subgroup "
        "analyses by genotype / phenotype]."
    )

    # 8. Statistical Analysis.
    statistical_analysis = (
        "Statistical analysis plan locked before unblinding. "
        "Primary analysis: intention-to-treat. Two-sided α = 0.05, "
        "power ≥ 0.80. Sample size calculated per the deterministic "
        "power-calc surface (`cannavec_science.power_calc`) using the "
        "minimal clinically important difference from the cited "
        "literature. Pre-specify handling of missing data (multiple "
        "imputation default; sensitivity analyses with worst-case / "
        "best-case / last-observation-carried-forward). Pre-specify "
        "subgroup analyses + interaction tests; treat as exploratory "
        "if not pre-registered."
    )

    # 9. Safety Monitoring.
    safety_monitoring = (
        "Independent Data Safety Monitoring Board (DSMB) convened "
        "before first subject enrolled. Pre-specified stopping rules "
        "for: (1) cumulative ≥ Grade 3 hepatic AE (per CTCAE 5.0), "
        "(2) any unexpected serious adverse event temporally linked to "
        "intervention. AEs coded with MedDRA; reported per ICH-E2A. "
        "Cannabinoid-specific safety pre-screens to consider: hepatic "
        "function (CBD-elevated transaminases), psychotomimetic "
        "screening (Δ⁹-THC), concomitant CYP3A4 / CYP2C9 / CYP2C19 "
        "inhibitors / inducers (interaction screening per Cannavec's "
        "interactions registry)."
    )

    # Build the skeleton; compute word count.
    word_count = sum(
        len(s.split())
        for s in (
            background, hypothesis, specific_aims, study_design,
            population, intervention_section, endpoints,
            statistical_analysis, safety_monitoring,
        )
    )

    return ProtocolSkeleton(
        background=background,
        hypothesis=hypothesis,
        specific_aims=specific_aims,
        study_design=study_design,
        population=population,
        intervention=intervention_section,
        endpoints=endpoints,
        statistical_analysis=statistical_analysis,
        safety_monitoring=safety_monitoring,
        word_count=word_count,
        answer_prompt=prompt,
    )


# ── Renderer ────────────────────────────────────────────────────────


def render_markdown(skeleton: ProtocolSkeleton) -> str:
    """Render the skeleton with the watermark on line 1.

    Line-1 watermark contract: ``tests/test_protocol_skeleton.py``
    asserts the first non-empty line carries the watermark.
    """
    lines: list[str] = []
    lines.append(WATERMARK)
    lines.append("")
    lines.append(
        f"_Protocol skeleton — derived from prompt: "
        f"\"{_truncate(skeleton.answer_prompt, 100)}\". "
        f"Word count: ~{skeleton.word_count} words._"
    )
    lines.append("")
    sections = (
        ("Background", skeleton.background),
        ("Hypothesis", skeleton.hypothesis),
        ("Specific Aims", skeleton.specific_aims),
        ("Study Design", skeleton.study_design),
        ("Population", skeleton.population),
        ("Intervention", skeleton.intervention),
        ("Endpoints", skeleton.endpoints),
        ("Statistical Analysis", skeleton.statistical_analysis),
        ("Safety Monitoring", skeleton.safety_monitoring),
    )
    for heading, body in sections:
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
