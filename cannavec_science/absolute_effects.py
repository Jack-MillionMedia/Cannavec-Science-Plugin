"""Absolute effects & Number-Needed-to-Treat (spec 015).

A pooled *relative* effect (a risk ratio or odds ratio) is not yet a
decision. The GRADE Summary-of-Findings (SoF) table turns it into one by
anchoring it to an **assumed comparator risk (ACR)** and reading off the
**anticipated absolute effect**: the corresponding intervention risk, the
risk difference per 1000, and the Number-Needed-to-Treat. This module is the
backbone's clinical translator — it takes the :mod:`cannavec_science.meta_analysis`
output and produces that SoF row.

Constitutional gates:

- **§I (Primary-Source-Or-Refuse).** The relative effect is §I-anchored by
  construction (every :class:`~cannavec_science.meta_analysis.EffectSize`
  feeding the pooled estimate required a primary-source identifier). The
  *assumed comparator risk* carries its own :class:`RiskProvenance`; GRADE
  permits an assumed/illustrative baseline, but an unsourced one is flagged
  ``acr_sourced=False`` and rendered with a visible caveat so it is never
  laundered as measured fact.
- **§II / §VII (Deterministic GRADE honesty).** Direction (NNTB vs NNTH) is
  derived from outcome desirability, never guessed. When the relative-effect
  CI crosses the null the NNT interval is reported with the Altman (1998)
  ``NNTB a → ∞ → NNTH b`` convention rather than a naive finite range that
  hides the discontinuity. Same input → byte-identical output.
- **§X (Stdlib-only).** Only :mod:`math` and :mod:`dataclasses`.

Reference: Altman DG. *Confidence intervals for the number needed to treat.*
BMJ 1998;317:1309-12. GRADE handbook, "Summary of Findings tables".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple


__all__ = [
    "AbsoluteEffectError",
    "RiskProvenance",
    "AbsoluteEffect",
    "absolute_effect",
    "absolute_from_meta",
    "render_markdown",
]


class AbsoluteEffectError(ValueError):
    """Raised when an absolute-effect translation is ill-posed."""


# ── provenance for the assumed comparator (baseline) risk ────────────


@dataclass(frozen=True)
class RiskProvenance:
    """Where the assumed comparator risk comes from (§I).

    A *label* is always required; identifiers are optional but, when present,
    promote the baseline from "assumed/illustrative" to primary-source
    anchored. The scheme priority mirrors
    :class:`cannavec_science.meta_analysis.EffectSize`.
    """

    label: str
    pmid: Optional[str] = None
    doi: Optional[str] = None
    nct: Optional[str] = None
    url: Optional[str] = None

    @property
    def identifier(self) -> Optional[str]:
        for scheme, value in (
            ("PMID", self.pmid),
            ("DOI", self.doi),
            ("NCT", self.nct),
            ("URL", self.url),
        ):
            if value:
                return f"{scheme}:{value}"
        return None

    @property
    def sourced(self) -> bool:
        return self.identifier is not None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "identifier": self.identifier,
            "sourced": self.sourced,
        }


# ── the absolute-effect record ───────────────────────────────────────


@dataclass(frozen=True)
class AbsoluteEffect:
    """A GRADE Summary-of-Findings row derived from a pooled relative effect.

    All risks are probabilities in [0, 1]; ``rd`` is the signed risk
    difference (EER − ACR). NNT fields follow the Altman convention — see the
    module docstring.
    """

    measure: str                       # "RR" | "OR"
    outcome: str
    outcome_desirable: bool
    confidence: float

    acr: float
    acr_provenance: RiskProvenance

    relative_estimate: float
    relative_ci: Tuple[float, float]

    eer: float
    eer_ci: Tuple[float, float]
    eer_clamped: bool

    rd: float
    rd_ci: Tuple[float, float]

    benefit: Optional[bool]            # does the point estimate favour treatment?
    nnt: Optional[float]               # |1/RD|; None when RD == 0
    nnt_kind: str                      # "NNTB" | "NNTH" | "none"
    nnt_crosses_null: bool
    nnt_ci: Optional[Tuple[float, float]]      # finite same-side CI, else None
    nnt_benefit_bound: Optional[float]         # crossing case only
    nnt_harm_bound: Optional[float]            # crossing case only

    certainty_note: Optional[str] = None

    # ── helpers ──

    @property
    def acr_sourced(self) -> bool:
        return self.acr_provenance.sourced

    @property
    def null_value(self) -> float:
        return 1.0  # ratio measures only

    def per_1000(self, risk: float) -> int:
        return int(_round_half_up(risk * 1000.0))

    def nnt_label(self) -> str:
        """Human-readable NNT with its CI (Altman convention when crossing)."""
        if self.nnt is None:
            return "Not estimable (no difference at the point estimate)"
        point = f"{self.nnt_kind} {_fmt(self.nnt)}"
        pct = _pct(self.confidence)
        if self.nnt_crosses_null:
            b = "∞" if self.nnt_benefit_bound is None else _fmt(self.nnt_benefit_bound)
            h = "∞" if self.nnt_harm_bound is None else _fmt(self.nnt_harm_bound)
            return f"{point} ({pct} CI: NNTB {b} to ∞ to NNTH {h})"
        if self.nnt_ci is not None:
            lo, hi = self.nnt_ci
            return f"{point} ({pct} CI {_fmt(lo)} to {_fmt(hi)})"
        return point

    def to_dict(self) -> dict:
        return {
            "measure": self.measure,
            "outcome": self.outcome,
            "outcome_desirable": self.outcome_desirable,
            "confidence": self.confidence,
            "acr": self.acr,
            "acr_per_1000": self.per_1000(self.acr),
            "acr_sourced": self.acr_sourced,
            "acr_provenance": self.acr_provenance.to_dict(),
            "relative_effect": {
                "measure": self.measure,
                "estimate": self.relative_estimate,
                "ci": list(self.relative_ci),
            },
            "eer": self.eer,
            "eer_ci": list(self.eer_ci),
            "eer_per_1000": self.per_1000(self.eer),
            "eer_clamped": self.eer_clamped,
            "risk_difference": self.rd,
            "risk_difference_ci": list(self.rd_ci),
            "risk_difference_per_1000": int(_round_half_up(self.rd * 1000.0)),
            "nnt": {
                "kind": self.nnt_kind,
                "value": self.nnt,
                "benefit": self.benefit,
                "crosses_null": self.nnt_crosses_null,
                "ci": list(self.nnt_ci) if self.nnt_ci is not None else None,
                "benefit_bound": self.nnt_benefit_bound,
                "harm_bound": self.nnt_harm_bound,
                "label": self.nnt_label(),
            },
            "certainty_note": self.certainty_note,
        }


# ── core math ────────────────────────────────────────────────────────


def _eer(measure: str, relative: float, acr: float) -> float:
    """Predicted intervention (experimental) event rate from a relative effect."""
    if measure == "RR":
        return relative * acr
    # OR — GRADE handbook odds→risk transform.
    return (relative * acr) / (1.0 - acr + relative * acr)


def _clamp_unit(x: float) -> Tuple[float, bool]:
    if x < 0.0:
        return 0.0, True
    if x > 1.0:
        return 1.0, True
    return x, False


def _is_benefit(rd_value: float, desirable: bool) -> Optional[bool]:
    """Does a signed risk difference favour the intervention?"""
    if rd_value == 0.0:
        return None
    return (rd_value > 0.0) if desirable else (rd_value < 0.0)


def absolute_effect(
    *,
    measure: str,
    estimate: float,
    ci: Tuple[float, float],
    acr: float,
    outcome: str,
    outcome_desirable: bool,
    acr_provenance: Optional[RiskProvenance] = None,
    confidence: float = 0.95,
    certainty_note: Optional[str] = None,
) -> AbsoluteEffect:
    """Translate a relative effect + assumed comparator risk into an absolute one.

    ``measure`` is ``"RR"`` or ``"OR"``; ``estimate`` and ``ci`` are on the
    natural (exponentiated) display scale, ``acr`` is the assumed comparator
    risk in the open interval (0, 1). ``outcome_desirable`` is required — the
    benefit/harm direction is never guessed (§VII).
    """
    measure = str(measure).upper()
    if measure not in ("RR", "OR"):
        raise AbsoluteEffectError(
            f"absolute effects are defined only for ratio measures (RR/OR); "
            f"got {measure!r}. A continuous mean difference has no risk difference."
        )
    if not isinstance(outcome_desirable, bool):
        raise AbsoluteEffectError("outcome_desirable must be an explicit bool")
    lo, hi = float(ci[0]), float(ci[1])
    if not (estimate > 0 and lo > 0 and hi > 0):
        raise AbsoluteEffectError("relative estimate and CI bounds must be > 0")
    if lo > hi:
        raise AbsoluteEffectError(f"CI is reversed: lower {lo} > upper {hi}")
    if not (math.isfinite(acr) and 0.0 < acr < 1.0):
        raise AbsoluteEffectError(
            f"assumed comparator risk must be a probability in (0, 1); got {acr!r}"
        )

    if acr_provenance is None:
        acr_provenance = RiskProvenance(label="assumed baseline risk (unsourced)")

    # Intervention risk at the point estimate and at each relative-CI bound.
    eer_raw, eer_clamped = _clamp_unit(_eer(measure, estimate, acr))
    eer_lo, c_lo = _clamp_unit(_eer(measure, lo, acr))
    eer_hi, c_hi = _clamp_unit(_eer(measure, hi, acr))
    eer_clamped = eer_clamped or c_lo or c_hi

    rd = eer_raw - acr
    rd_lo = eer_lo - acr
    rd_hi = eer_hi - acr
    if rd_lo > rd_hi:                       # defensive; transforms are monotone
        rd_lo, rd_hi = rd_hi, rd_lo

    benefit = _is_benefit(rd, outcome_desirable)
    nnt = None if rd == 0.0 else 1.0 / abs(rd)
    nnt_kind = "none" if benefit is None else ("NNTB" if benefit else "NNTH")

    contains_zero = rd_lo <= 0.0 <= rd_hi
    nnt_ci: Optional[Tuple[float, float]] = None
    benefit_bound: Optional[float] = None
    harm_bound: Optional[float] = None
    if not contains_zero:
        mags = sorted((abs(rd_lo), abs(rd_hi)))   # [smaller |RD|, larger |RD|]
        nnt_ci = (1.0 / mags[1], 1.0 / mags[0])   # (smaller NNT, larger NNT)
    else:
        for rdv in (rd_lo, rd_hi):
            if rdv == 0.0:
                continue
            if _is_benefit(rdv, outcome_desirable):
                benefit_bound = 1.0 / abs(rdv)
            else:
                harm_bound = 1.0 / abs(rdv)

    return AbsoluteEffect(
        measure=measure,
        outcome=outcome,
        outcome_desirable=outcome_desirable,
        confidence=float(confidence),
        acr=float(acr),
        acr_provenance=acr_provenance,
        relative_estimate=float(estimate),
        relative_ci=(lo, hi),
        eer=eer_raw,
        eer_ci=(eer_lo, eer_hi),
        eer_clamped=eer_clamped,
        rd=rd,
        rd_ci=(rd_lo, rd_hi),
        benefit=benefit,
        nnt=nnt,
        nnt_kind=nnt_kind,
        nnt_crosses_null=contains_zero,
        nnt_ci=nnt_ci,
        nnt_benefit_bound=benefit_bound,
        nnt_harm_bound=harm_bound,
        certainty_note=certainty_note,
    )


def absolute_from_meta(
    result,
    *,
    acr: float,
    outcome: str,
    outcome_desirable: bool,
    acr_provenance: Optional[RiskProvenance] = None,
    model: str = "random",
) -> AbsoluteEffect:
    """Build an :class:`AbsoluteEffect` from a ratio :class:`MetaAnalysisResult`.

    ``model`` selects the ``"random"`` (default) or ``"fixed"`` pooled
    estimate. A continuous (MD/SMD) result is refused — a mean difference has
    no risk difference.
    """
    measure = str(getattr(result, "measure", "")).upper()
    if measure not in ("RR", "OR") or not getattr(result, "log_scale", False):
        raise AbsoluteEffectError(
            f"absolute effects require a ratio meta-analysis (OR/RR); "
            f"got measure={measure!r}"
        )
    if model == "random":
        estimate = result.random_estimate_display
        ci = result.random_ci_display
    elif model == "fixed":
        estimate = result.fixed_estimate_display
        ci = result.fixed_ci_display
    else:
        raise AbsoluteEffectError("model must be 'random' or 'fixed'")

    note = (
        f"Absolute effect inherits the pooled certainty — GRADE inconsistency: "
        f"{result.inconsistency} (I²={result.i_squared:.0f}%, "
        f"downgrade {result.downgrade_steps} step(s)). The assumed comparator "
        f"risk is a baseline choice, not a pooled quantity."
    )
    return absolute_effect(
        measure=measure,
        estimate=estimate,
        ci=ci,
        acr=acr,
        outcome=outcome,
        outcome_desirable=outcome_desirable,
        acr_provenance=acr_provenance,
        confidence=float(getattr(result, "confidence", 0.95)),
        certainty_note=note,
    )


# ── rendering ────────────────────────────────────────────────────────


def _per1000_phrase(rd_value: float) -> str:
    n = int(_round_half_up(abs(rd_value) * 1000.0))
    if rd_value < 0:
        return f"{n} fewer"
    if rd_value > 0:
        return f"{n} more"
    return "0 (no difference)"


def render_markdown(ae: AbsoluteEffect) -> str:
    """Render a GRADE Summary-of-Findings-style block (Markdown)."""
    pct = _pct(ae.confidence)
    lo, hi = ae.relative_ci
    eer_lo, eer_hi = ae.eer_ci
    rd_lo, rd_hi = ae.rd_ci

    lines = [
        f"### Anticipated absolute effects — {ae.outcome}",
        "",
        f"- **Relative effect:** {ae.measure} {_fmt(ae.relative_estimate)} "
        f"({pct} CI {_fmt(lo)} to {_fmt(hi)})",
        f"- **Assumed comparator risk:** {ae.per_1000(ae.acr)} per 1000 "
        f"({_fmt(ae.acr * 100)}%) — {ae.acr_provenance.label}"
        + (f" [{ae.acr_provenance.identifier}]" if ae.acr_sourced else ""),
        f"- **Corresponding intervention risk:** {ae.per_1000(ae.eer)} per 1000 "
        f"({pct} CI {ae.per_1000(eer_lo)} to {ae.per_1000(eer_hi)})"
        + (" *(clamped to ≤1000)*" if ae.eer_clamped else ""),
        f"- **Risk difference:** {_per1000_phrase(ae.rd)} per 1000 "
        f"({pct} CI {_per1000_phrase(rd_lo)} to {_per1000_phrase(rd_hi)})",
        f"- **Number needed to treat:** {ae.nnt_label()}",
    ]
    if not ae.acr_sourced:
        lines.append(
            "- ⚠️ **Assumed baseline risk is not primary-source anchored** — "
            "the absolute numbers are illustrative; supply a sourced comparator "
            "risk (e.g. pooled control arms) to anchor them (§I)."
        )
    if ae.certainty_note:
        lines.append(f"- _{ae.certainty_note}_")
    return "\n".join(lines)


# ── small deterministic formatting helpers ──────────────────────────


def _round_half_up(x: float) -> float:
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def _pct(confidence: float) -> str:
    p = confidence * 100.0
    return f"{int(p)}%" if abs(p - round(p)) < 1e-9 else f"{p:g}%"


def _fmt(x: float) -> str:
    """Compact fixed-point: 2 decimals, trailing zeros trimmed."""
    s = f"{x:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s
