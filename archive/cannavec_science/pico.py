"""PICO drafter (spec 002 US2).

Deterministic Population / Intervention / Comparator / Outcomes
composer. Pure function — no LLM, no I/O — same input → same output.

The block is derived from three signals already present in the typed
``Answer``:

1. Intent classifier (efficacy / safety / mechanism / dosing /
   interaction / definition).
2. Population registry hits — every TrialSupportedPopulation row
   carries the population label, indication, route, dose range,
   and required cautions.
3. Cannabinoid + claim text — the intervention is the cannabinoid the
   prompt names; the outcome is the indication the population registry
   row attaches.

The output is a typed :class:`PICOBlock` plus a Markdown renderer
suitable for inline insertion into the ``Answer.to_markdown()``
output.

Caller contract:

- Always returns a ``PICOBlock`` — even when fields are unresolvable
  the block is emitted with explicit ``unresolved`` markers (per
  FR-203: "MUST emit a PICO block deterministically").
- The block carries a confidence label (``high`` / ``medium`` /
  ``low``) so the reader sees whether the composer pulled real
  registry data or fell back to a generic frame.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


__all__ = [
    "PICOBlock",
    "build_pico",
    "render_markdown",
]


@dataclass(frozen=True)
class PICOBlock:
    """Deterministic PICO frame for a research brief.

    Every field is a string; ``unresolved`` is the sentinel for a
    field the deterministic composer could not pull from the
    typed Answer. Callers that need a confidence signal read
    ``confidence``.
    """

    population: str
    intervention: str
    comparator: str
    outcomes: tuple[str, ...]
    confidence: str = "medium"
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["outcomes"] = list(self.outcomes)
        d["notes"] = list(self.notes)
        return d


_UNRESOLVED = "unresolved"


# ── Heuristics ──────────────────────────────────────────────────────


def _intervention_from_prompt(prompt: str) -> str:
    """Pull the cannabinoid / botanical the prompt names.

    Searches in priority order: explicit isomer (Δ⁹-THC, Δ⁸-THC,
    THCA, CBDA) → major cannabinoid (CBD, THC) → minor cannabinoid
    (THCV, CBDV, CBG, CBN, CBC) → generic terpene → "cannabis".
    """
    lower = prompt.lower()
    # Explicit isomers first — the precision the constitution requires.
    for tag, canonical in (
        ("δ⁹-thc", "Δ⁹-THC"),
        ("delta-9 thc", "Δ⁹-THC"),
        ("delta-9-thc", "Δ⁹-THC"),
        ("δ⁸-thc", "Δ⁸-THC"),
        ("delta-8 thc", "Δ⁸-THC"),
        ("delta-8-thc", "Δ⁸-THC"),
        ("thca", "THCA"),
        ("cbda", "CBDA"),
        ("hhc", "HHC"),
        ("thco", "THCO"),
        ("thcp", "THCP"),
    ):
        if tag in lower:
            return canonical
    # Major cannabinoids
    for needle, canonical in (
        ("cannabidiol", "CBD"),
        ("epidiolex", "CBD (Epidiolex)"),
        ("cbd", "CBD"),
        ("tetrahydrocannabinol", "Δ⁹-THC"),
        ("dronabinol", "Δ⁹-THC (dronabinol)"),
        ("nabilone", "nabilone"),
        ("sativex", "nabiximols (Sativex)"),
        ("nabiximols", "nabiximols"),
    ):
        if needle in lower:
            return canonical
    # Minor cannabinoids
    for needle, canonical in (
        ("thcv", "THCV"),
        ("cbdv", "CBDV"),
        ("cbg", "CBG"),
        ("cbn", "CBN"),
        ("cbc", "CBC"),
    ):
        if needle in lower:
            return canonical
    # Bare "thc" only if no isomer prefix found
    if "thc" in lower:
        return "THC (isomer unspecified — clarify in protocol)"
    # Fall back to generic
    if "cannabis" in lower or "marijuana" in lower:
        return "cannabis"
    if "hemp" in lower:
        return "hemp-derived cannabinoid (unspecified isomer)"
    return _UNRESOLVED


def _population_from_registry_hits(rows: tuple) -> tuple[str, str]:
    """Return ``(population_label, indication)`` from the first
    population-registry hit, or ``(_UNRESOLVED, _UNRESOLVED)``."""
    if not rows:
        return _UNRESOLVED, _UNRESOLVED
    row = rows[0]
    pop = getattr(row, "label", None) or getattr(row, "population", None)
    indication = getattr(row, "indication", None) or getattr(row, "primary_outcome", None)
    return (pop or _UNRESOLVED, indication or _UNRESOLVED)


def _comparator_default(intent_value: str, intervention: str) -> str:
    """Pick the conventional comparator for a cannabinoid trial.

    Most cannabinoid efficacy work uses placebo-controlled or
    add-on-to-standard-of-care designs. We pick the conventional
    comparator for the intent and let the PI override.
    """
    if intent_value in ("efficacy", "dosing"):
        return "placebo (or add-on to standard of care)"
    if intent_value == "interaction":
        return "no-cannabinoid baseline (within-subject crossover)"
    if intent_value == "safety_risk":
        return "matched non-exposed cohort"
    if intent_value == "mechanism":
        return "vehicle control"
    return _UNRESOLVED


def _outcomes_from_claims(claims: tuple, indication: str) -> tuple[str, ...]:
    """Lift candidate primary + secondary outcomes from the answer's
    claim list and any indication string.
    """
    out: list[str] = []
    if indication and indication != _UNRESOLVED:
        out.append(f"Primary: {indication}")
    seen_lower = {o.lower() for o in out}
    # Each claim's first sentence becomes a candidate outcome.
    for c in claims[:6]:
        text = getattr(c, "text", "") or ""
        # First clause up to a period or 120 chars.
        clause = text.split(".")[0].strip()
        if not clause:
            continue
        if len(clause) > 120:
            clause = clause[:117] + "…"
        if clause.lower() in seen_lower:
            continue
        out.append(f"Secondary: {clause}")
        seen_lower.add(clause.lower())
    if not out:
        out.append("Outcomes: unresolved — specify primary endpoint + " "validated outcome measure")
    return tuple(out)


# ── Public entry point ──────────────────────────────────────────────


def build_pico(answer: object) -> PICOBlock:
    """Deterministically build a PICO frame for ``answer``.

    ``answer`` is a :class:`cannavec_science.answer.Answer`. Pulls
    on its ``prompt``, ``claims``, and (via the registry detectors)
    the population row that the prompt resolves to.
    """
    from cannavec_science.intent import classify_intent
    from cannavec_science.populations import (
        detect_population_class_mention,
        detect_population_mention,
    )

    prompt = getattr(answer, "prompt", "") or ""
    claims = tuple(getattr(answer, "claims", ()) or ())

    intent = classify_intent(prompt)
    intervention = _intervention_from_prompt(prompt)

    population_rows = detect_population_mention(prompt)
    if not population_rows:
        population_rows = detect_population_class_mention(prompt)
    population, indication = _population_from_registry_hits(population_rows)
    if population == _UNRESOLVED:
        # Heuristic fallback from claims: look at the first claim's
        # ``population`` attribute.
        for c in claims:
            cp = getattr(c, "population", None)
            if cp:
                population = cp
                break

    comparator = _comparator_default(intent.value, intervention)
    outcomes = _outcomes_from_claims(claims, indication)

    # Confidence: high when population registry resolved + intervention is
    # explicit; medium when one is fallback; low when both are unresolved.
    high_pop = population != _UNRESOLVED
    high_int = intervention != _UNRESOLVED and "isomer unspecified" not in intervention
    if high_pop and high_int:
        confidence = "high"
    elif high_pop or high_int:
        confidence = "medium"
    else:
        confidence = "low"

    notes: list[str] = []
    if "isomer unspecified" in intervention:
        notes.append(
            "Intervention isomer ambiguous; clarify Δ⁹-THC vs Δ⁸-THC "
            "vs THCA before IRB submission."
        )
    if population == _UNRESOLVED:
        notes.append(
            "Population unresolved from prompt; PI should specify "
            "inclusion / exclusion criteria explicitly."
        )
    if comparator == _UNRESOLVED:
        notes.append(
            "Comparator unresolved; specify placebo / vehicle / "
            "active-control."
        )

    return PICOBlock(
        population=population,
        intervention=intervention,
        comparator=comparator,
        outcomes=outcomes,
        confidence=confidence,
        notes=tuple(notes),
    )


def render_markdown(block: PICOBlock) -> str:
    """Insertable Markdown block — appended to the brief by ``answer.py``."""
    lines: list[str] = []
    lines.append("## PICO frame (deterministic draft)")
    lines.append("")
    lines.append(f"- **Population:** {block.population}")
    lines.append(f"- **Intervention:** {block.intervention}")
    lines.append(f"- **Comparator:** {block.comparator}")
    lines.append("- **Outcomes:**")
    for o in block.outcomes:
        lines.append(f"  - {o}")
    lines.append(f"- **Confidence:** {block.confidence}")
    if block.notes:
        lines.append("- **PI notes:**")
        for n in block.notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)
