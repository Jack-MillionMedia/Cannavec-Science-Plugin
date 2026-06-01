"""Summary-of-Findings composer (spec 017).

Weaves the three quantitative surfaces into the single deliverable an
evidence-review team hands a decision-maker — and threads it into the
``answer`` research brief so a brief carries end-to-end SoF rows:

    certainty (spec 016) → relative effect (spec 011)
        → absolute effect + NNT (spec 015)

Each outcome is pooled from §I-anchored studies (every effect size requires a
primary-source identifier), so the SoF section never introduces an unanchored
number. The assumed comparator risk for the absolute column carries its own
provenance and is flagged when unsourced, exactly as in spec 015. This module
is pure composition over the existing deterministic backbone — no new
statistics, no network, no LLM (§II, §X).

Sidecar shape consumed by ``build_sof`` (and ``answer --sof FILE``):

    {
      "outcomes": [
        {
          "outcome": "≥50% seizure reduction",
          "measure": "RR",
          "studies": [ {"study_id": ..., "events_t": ..., "pmid": ...}, ... ],
          "baseline": {"risk": 0.40, "label": "pooled placebo arms",
                       "pmid": "28538134"},
          "outcome_desirable": false,
          "evidence_base": "rct",
          "risk_of_bias": "not serious",
          "indirectness": "not serious"
        }
      ]
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


__all__ = [
    "SoFError",
    "SummaryOfFindingsRow",
    "SummaryOfFindings",
    "build_sof",
    "render_markdown",
]


class SoFError(ValueError):
    """Raised when a Summary-of-Findings sidecar is malformed."""


@dataclass(frozen=True)
class SummaryOfFindingsRow:
    """One pooled outcome: its pooled estimate, certainty, and absolute effect."""

    outcome: str
    result: object                 # MetaAnalysisResult
    certainty: object              # grade_profile.MetaCertainty
    absolute: Optional[object]     # absolute_effects.AbsoluteEffect | None

    @property
    def k(self) -> int:
        return int(getattr(self.result, "k", 0) or 0)

    def relative_line(self) -> str:
        r = self.result
        est = r.random_estimate_display
        lo, hi = r.random_ci_display
        return f"{r.measure} {_fmt(est)} (95% CI {_fmt(lo)} to {_fmt(hi)})"

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "k": self.k,
            "relative_effect": {
                "measure": self.result.measure,
                "estimate": self.result.random_estimate_display,
                "ci": list(self.result.random_ci_display),
            },
            "certainty": self.certainty.to_dict(),
            "absolute_effect": (
                self.absolute.to_dict() if self.absolute is not None else None
            ),
        }


@dataclass(frozen=True)
class SummaryOfFindings:
    """An ordered set of SoF rows — the pooled-outcome companion to the
    per-claim GRADE evidence-profile table."""

    rows: Tuple[SummaryOfFindingsRow, ...]

    def to_dict(self) -> dict:
        return {"rows": [r.to_dict() for r in self.rows]}


def build_sof(spec: dict) -> SummaryOfFindings:
    """Build a :class:`SummaryOfFindings` from a sidecar dict (see module doc)."""
    from cannavec_science.meta_analysis import (
        MetaAnalysisError,
        effects_from_records,
        egger_test,
        meta_analyze,
    )
    from cannavec_science.grade_profile import certainty_from_meta
    from cannavec_science.absolute_effects import (
        AbsoluteEffectError,
        RiskProvenance,
        absolute_from_meta,
    )

    if not isinstance(spec, dict):
        raise SoFError("SoF spec must be a JSON object")
    outcomes = spec.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        raise SoFError('SoF spec needs a non-empty "outcomes" list')

    rows: list = []
    for i, o in enumerate(outcomes):
        if not isinstance(o, dict):
            raise SoFError(f"outcome #{i + 1} must be an object")
        label = o.get("outcome") or f"outcome {i + 1}"
        measure = o.get("measure", "generic")
        try:
            effects = effects_from_records(o.get("studies", []), measure=measure)
            result = meta_analyze(
                effects,
                measure=(None if str(measure).lower() == "generic" else measure),
            )
        except KeyError as exc:
            raise SoFError(f"{label!r}: study missing required field {exc}")
        except MetaAnalysisError as exc:
            raise SoFError(f"{label!r}: {exc}")

        egger = None
        if len(effects) >= 3:
            try:
                egger = egger_test(effects)
            except MetaAnalysisError:
                egger = None

        certainty = certainty_from_meta(
            result,
            evidence_base=o.get("evidence_base", "rct"),
            risk_of_bias=o.get("risk_of_bias", "not serious"),
            indirectness=o.get("indirectness", "not serious"),
            egger=egger,
        )

        absolute = None
        baseline = o.get("baseline") if isinstance(o.get("baseline"), dict) else {}
        if baseline.get("risk") is not None and result.measure in ("OR", "RR"):
            prov = RiskProvenance(
                label=baseline.get("label", "assumed baseline risk (unsourced)"),
                pmid=baseline.get("pmid"),
                doi=baseline.get("doi"),
                nct=baseline.get("nct"),
                url=baseline.get("url"),
            )
            try:
                absolute = absolute_from_meta(
                    result, acr=float(baseline["risk"]), outcome=label,
                    outcome_desirable=bool(o.get("outcome_desirable", False)),
                    acr_provenance=prov, model=o.get("model", "random"),
                )
            except (AbsoluteEffectError, ValueError) as exc:
                raise SoFError(f"{label!r}: {exc}")

        rows.append(SummaryOfFindingsRow(
            outcome=label, result=result, certainty=certainty, absolute=absolute,
        ))

    return SummaryOfFindings(rows=tuple(rows))


def render_markdown(sof: SummaryOfFindings) -> str:
    """Render the SoF section for the brief (reuses the spec 015/016 renderers)."""
    from cannavec_science.grade_profile import render_certainty
    from cannavec_science.absolute_effects import render_markdown as render_absolute

    out = ["## Summary of Findings",
           "",
           "Pooled-outcome companion to the per-claim GRADE evidence profile. "
           "Every effect size is primary-source anchored (§I); certainty is "
           "computed, not asserted (§VII)."]
    for row in sof.rows:
        out.append("")
        out.append(f"### {row.outcome} — {row.k} studies")
        out.append("")
        out.append(f"- **Relative effect (random):** {row.relative_line()}")
        out.append("")
        out.append(render_certainty(row.certainty))
        if row.absolute is not None:
            out.append("")
            out.append(render_absolute(row.absolute))
    return "\n".join(out)


def _fmt(x: float) -> str:
    s = f"{x:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s
