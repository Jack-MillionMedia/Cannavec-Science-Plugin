"""Sample-size / power calculator (spec 002 US2).

Stdlib-only implementation of the standard two-arm sample-size
formulas. ``math.erf`` provides the normal CDF; no scipy / numpy /
statsmodels. Same input → same output, every time.

Methods supported:

- **Continuous, two-arm parallel** — Cohen's d. Formula from Cohen
  (1988), Statistical Power Analysis for the Behavioral Sciences,
  §2.3.1::

      n_per_arm = 2 × ((z_α/2 + z_β) / d)²

- **Dichotomous, two-arm parallel** — proportion difference. Formula
  from Fleiss (1981), Statistical Methods for Rates and Proportions,
  §2.1::

      n_per_arm = ((z_α/2 × √(2p̄q̄) + z_β × √(p₁q₁ + p₂q₂)) / (p₁ − p₂))²

  where p̄ = (p₁ + p₂)/2, q = 1 − p, etc.

- **Odds ratio, two-arm parallel** — converts OR + baseline rate
  to ``(p₁, p₂)`` via ``p₂ = OR × p₁ / (1 − p₁ + OR × p₁)``, then
  defers to the proportion-difference formula above.

Refused designs (returned as ``method_not_supported``):

- Single-arm / open-label (no comparator → power requires effect-magnitude
  vs historical control).
- Non-inferiority (needs the non-inferiority margin specified).
- Adaptive designs (requires simulation).
- Cluster-randomised (requires the design effect / ICC).

Refusal is **honest**, not a guess: an unsupported design returns a
``PowerCalculation`` with ``method_not_supported=True`` and a
``message`` explaining what input the caller needs to supply.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Optional


__all__ = [
    "PowerCalculation",
    "calc_continuous_two_arm",
    "calc_proportion_two_arm",
    "calc_odds_ratio_two_arm",
    "z_for_alpha",
    "z_for_power",
    "render_markdown",
]


# ── Statistical primitives ──────────────────────────────────────────


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via :func:`math.erf` — no scipy needed."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _inverse_norm_cdf(p: float) -> float:
    """Inverse normal CDF (probit) via Beasley-Springer-Moro.

    Accurate to ~1e-9 across (0.001, 0.999). Within the band the
    caller needs for α/β values in clinical trials (0.001 – 0.50)
    the error is well below the rounding the caller will do on the
    returned sample size.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1); got {p}")
    a = (
        -3.969683028665376e1,
        2.209460984245205e2,
        -2.759285104469687e2,
        1.383577518672690e2,
        -3.066479806614716e1,
        2.506628277459239e0,
    )
    b = (
        -5.447609879822406e1,
        1.615858368580409e2,
        -1.556989798598866e2,
        6.680131188771972e1,
        -1.328068155288572e1,
    )
    c = (
        -7.784894002430293e-3,
        -3.223964580411365e-1,
        -2.400758277161838e0,
        -2.549732539343734e0,
        4.374664141464968e0,
        2.938163982698783e0,
    )
    d = (
        7.784695709041462e-3,
        3.224671290700398e-1,
        2.445134137142996e0,
        3.754408661907416e0,
    )
    p_low, p_high = 0.02425, 0.97575
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        ) / (
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(
        ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
    ) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def z_for_alpha(alpha: float, two_sided: bool = True) -> float:
    """``z_{α/2}`` for the supplied α; or ``z_α`` when one-sided."""
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1); got {alpha}")
    tail = alpha / 2.0 if two_sided else alpha
    return _inverse_norm_cdf(1.0 - tail)


def z_for_power(power: float) -> float:
    """``z_β`` for the supplied power = 1 − β."""
    if not 0.0 < power < 1.0:
        raise ValueError(f"power must be in (0, 1); got {power}")
    beta = 1.0 - power
    return _inverse_norm_cdf(1.0 - beta)


# ── Dataclass ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class PowerCalculation:
    """A single sample-size estimate for one outcome.

    Either ``n_per_arm`` / ``n_total`` are populated (a real estimate),
    or ``method_not_supported=True`` and ``message`` explains why.
    """

    outcome: str
    method: str
    inputs: dict
    alpha: float = 0.05
    power: float = 0.80
    n_per_arm: Optional[int] = None
    n_total: Optional[int] = None
    method_not_supported: bool = False
    message: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


# ── Continuous two-arm — Cohen's d ──────────────────────────────────


def calc_continuous_two_arm(
    *,
    outcome: str,
    mean_diff: float,
    sd: float,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
    notes: tuple[str, ...] = (),
) -> PowerCalculation:
    """Cohen's d two-arm sample size.

    n_per_arm = 2 × ((z_α/2 + z_β) / d)² + 1 (small-sample correction)
    """
    inputs = {
        "mean_diff": mean_diff, "sd": sd,
        "alpha": alpha, "power": power, "two_sided": two_sided,
    }
    if sd <= 0.0:
        return PowerCalculation(
            outcome=outcome, method="cohens_d_two_arm",
            inputs=inputs, alpha=alpha, power=power,
            method_not_supported=True,
            message="standard deviation must be > 0; got %g" % sd,
        )
    if mean_diff == 0.0:
        return PowerCalculation(
            outcome=outcome, method="cohens_d_two_arm",
            inputs=inputs, alpha=alpha, power=power,
            method_not_supported=True,
            message=(
                "mean difference is zero — sample size is infinite. "
                "Specify a non-zero minimal clinically important "
                "difference."
            ),
        )
    d = abs(mean_diff) / sd
    z_a = z_for_alpha(alpha, two_sided=two_sided)
    z_b = z_for_power(power)
    n_per_arm = math.ceil(2.0 * ((z_a + z_b) / d) ** 2)
    # Conventional small-sample correction (Cohen 1988 §2.4): +1
    n_per_arm += 1
    return PowerCalculation(
        outcome=outcome, method="cohens_d_two_arm",
        inputs=inputs, alpha=alpha, power=power,
        n_per_arm=n_per_arm, n_total=n_per_arm * 2,
        notes=notes,
    )


# ── Dichotomous two-arm — proportion difference ─────────────────────


def calc_proportion_two_arm(
    *,
    outcome: str,
    p1: float,
    p2: float,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
    continuity_correction: bool = True,
    notes: tuple[str, ...] = (),
) -> PowerCalculation:
    """Fleiss (1981) two-arm proportion sample size.

    p₁ = control event rate, p₂ = experimental event rate.

    Defaults apply the Yates continuity correction (Fleiss, Tytun &
    Ury 1980) — standard in clinical-trial practice; passes the
    Fleiss 1981 Table 2.1 worked example. Set
    ``continuity_correction=False`` for the asymptotic / uncorrected
    formula.
    """
    inputs = {
        "p1": p1, "p2": p2,
        "alpha": alpha, "power": power, "two_sided": two_sided,
        "continuity_correction": continuity_correction,
    }
    for p, name in ((p1, "p1"), (p2, "p2")):
        if not 0.0 < p < 1.0:
            return PowerCalculation(
                outcome=outcome, method="proportion_two_arm",
                inputs=inputs, alpha=alpha, power=power,
                method_not_supported=True,
                message=f"{name} must be in (0, 1); got {p}",
            )
    if p1 == p2:
        return PowerCalculation(
            outcome=outcome, method="proportion_two_arm",
            inputs=inputs, alpha=alpha, power=power,
            method_not_supported=True,
            message="p1 == p2 → sample size is infinite. Specify a non-zero treatment effect.",
        )
    pbar = (p1 + p2) / 2.0
    qbar = 1.0 - pbar
    q1 = 1.0 - p1
    q2 = 1.0 - p2
    z_a = z_for_alpha(alpha, two_sided=two_sided)
    z_b = z_for_power(power)
    numer = z_a * math.sqrt(2.0 * pbar * qbar) + z_b * math.sqrt(p1 * q1 + p2 * q2)
    denom = abs(p1 - p2)
    n_uncorrected = math.ceil((numer / denom) ** 2)
    if continuity_correction:
        # Fleiss-Tytun-Ury continuity correction: inflate by
        # (1 + sqrt(1 + 4/(n × |p1 - p2|)))² / 4. The closed-form
        # expression is in Fleiss 1981 §2.1.
        inflate = (1.0 + math.sqrt(
            1.0 + 4.0 / (n_uncorrected * denom)
        )) ** 2 / 4.0
        n_per_arm = math.ceil(n_uncorrected * inflate)
    else:
        n_per_arm = n_uncorrected
    return PowerCalculation(
        outcome=outcome, method="proportion_two_arm",
        inputs=inputs, alpha=alpha, power=power,
        n_per_arm=n_per_arm, n_total=n_per_arm * 2,
        notes=notes,
    )


# ── Dichotomous two-arm — odds ratio ────────────────────────────────


def calc_odds_ratio_two_arm(
    *,
    outcome: str,
    odds_ratio: float,
    baseline_p: float,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
    notes: tuple[str, ...] = (),
) -> PowerCalculation:
    """OR + baseline rate → proportion difference → Fleiss formula.

    p₂ = OR × p₁ / (1 − p₁ + OR × p₁)
    """
    inputs = {
        "odds_ratio": odds_ratio, "baseline_p": baseline_p,
        "alpha": alpha, "power": power, "two_sided": two_sided,
    }
    if odds_ratio <= 0.0:
        return PowerCalculation(
            outcome=outcome, method="odds_ratio_two_arm",
            inputs=inputs, alpha=alpha, power=power,
            method_not_supported=True,
            message=f"odds_ratio must be > 0; got {odds_ratio}",
        )
    if not 0.0 < baseline_p < 1.0:
        return PowerCalculation(
            outcome=outcome, method="odds_ratio_two_arm",
            inputs=inputs, alpha=alpha, power=power,
            method_not_supported=True,
            message=f"baseline_p must be in (0, 1); got {baseline_p}",
        )
    if odds_ratio == 1.0:
        return PowerCalculation(
            outcome=outcome, method="odds_ratio_two_arm",
            inputs=inputs, alpha=alpha, power=power,
            method_not_supported=True,
            message="OR == 1 → no treatment effect; sample size is infinite.",
        )
    p1 = baseline_p
    p2 = (odds_ratio * p1) / (1.0 - p1 + odds_ratio * p1)
    inner = calc_proportion_two_arm(
        outcome=outcome, p1=p1, p2=p2,
        alpha=alpha, power=power, two_sided=two_sided, notes=notes,
    )
    # Re-tag method label so the caller knows the OR path was used.
    return PowerCalculation(
        outcome=inner.outcome,
        method="odds_ratio_two_arm",
        inputs=inputs,
        alpha=inner.alpha,
        power=inner.power,
        n_per_arm=inner.n_per_arm,
        n_total=inner.n_total,
        method_not_supported=inner.method_not_supported,
        message=inner.message,
        notes=inner.notes + (f"Converted to proportions: p1={p1:.3f}, p2={p2:.3f}",),
    )


def calc_unsupported(
    *,
    outcome: str,
    reason: str,
    inputs: Optional[dict] = None,
) -> PowerCalculation:
    """Explicit honest-failure builder for non-supported designs."""
    return PowerCalculation(
        outcome=outcome, method="unsupported",
        inputs=inputs or {},
        method_not_supported=True,
        message=reason,
    )


# ── Composer helper ─────────────────────────────────────────────────


def build_for_answer(answer: object) -> tuple[PowerCalculation, ...]:
    """Extract sample-size estimates for an Answer's claims.

    Each claim is examined for effect-size language; the deterministic
    extractor is intentionally conservative — it returns
    ``method_not_supported`` when it cannot extract clean numbers,
    rather than guessing.
    """
    import re

    claims = tuple(getattr(answer, "claims", ()) or ())
    if not claims:
        return (
            calc_unsupported(
                outcome="overall",
                reason=(
                    "no claims attached — specify expected effect size "
                    "(mean difference + SD, or proportion + comparator)"
                ),
            ),
        )

    out: list[PowerCalculation] = []
    md_re = re.compile(
        r"(?:mean difference|MD)\s*(?:of)?\s*[−-]?\s*(\d+(?:\.\d+)?)\s*"
        r"(?:.*?SD\s*=?\s*(\d+(?:\.\d+)?))?",
        re.IGNORECASE,
    )
    or_re = re.compile(
        r"\bOR\s*=?\s*(\d+(?:\.\d+)?)\b(?:.*?baseline\s*(?:rate|p)\s*=?\s*(\d+(?:\.\d+)?))?",
        re.IGNORECASE,
    )
    prop_re = re.compile(
        r"(\d+(?:\.\d+)?)\s*%\s*vs\.?\s*(\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    )

    for c in claims[:5]:  # cap per-answer to keep brief readable
        text = getattr(c, "text", "") or ""
        outcome = text.split(".")[0][:80]
        m = md_re.search(text)
        if m:
            mean_diff = float(m.group(1))
            sd = float(m.group(2)) if m.group(2) else 0.0
            if sd > 0:
                out.append(
                    calc_continuous_two_arm(
                        outcome=outcome, mean_diff=mean_diff, sd=sd,
                    )
                )
                continue
        m = prop_re.search(text)
        if m:
            p1 = float(m.group(1)) / 100.0
            p2 = float(m.group(2)) / 100.0
            if 0.0 < p1 < 1.0 and 0.0 < p2 < 1.0 and p1 != p2:
                out.append(
                    calc_proportion_two_arm(
                        outcome=outcome, p1=p1, p2=p2,
                    )
                )
                continue
        m = or_re.search(text)
        if m and m.group(2):
            odds_ratio = float(m.group(1))
            baseline_p = float(m.group(2))
            if 0.0 < baseline_p < 1.0 and odds_ratio > 0.0 and odds_ratio != 1.0:
                out.append(
                    calc_odds_ratio_two_arm(
                        outcome=outcome,
                        odds_ratio=odds_ratio,
                        baseline_p=baseline_p,
                    )
                )
                continue
        # Nothing extractable from this claim — be honest.
        out.append(
            calc_unsupported(
                outcome=outcome,
                reason=(
                    "insufficient effect-size data in cited claim — "
                    "specify mean difference + SD, or proportions, or "
                    "OR + baseline rate"
                ),
            )
        )
    return tuple(out)


# ── Renderer ────────────────────────────────────────────────────────


def render_markdown(estimates: tuple[PowerCalculation, ...]) -> str:
    """Insertable Markdown block — appended to the brief by ``answer.py``."""
    if not estimates:
        return ""
    lines: list[str] = []
    lines.append("## Power calculation (deterministic; α = 0.05, β = 0.20)")
    lines.append("")
    lines.append("| Outcome | Method | n per arm | n total | Notes |")
    lines.append("|---|---|---|---|---|")
    for e in estimates:
        if e.method_not_supported:
            n_per = "—"
            n_total = "—"
            notes = e.message
        else:
            n_per = str(e.n_per_arm)
            n_total = str(e.n_total)
            notes = "; ".join(e.notes) if e.notes else ""
        outcome = e.outcome.replace("|", "\\|")
        if len(outcome) > 60:
            outcome = outcome[:57] + "…"
        lines.append(f"| {outcome} | `{e.method}` | {n_per} | {n_total} | {notes} |")
    lines.append("")
    lines.append(
        "_Stdlib power calculator — Cohen 1988 (continuous) / "
        "Fleiss 1981 (proportion). Non-inferiority and adaptive "
        "designs report `method_not_supported` rather than guess._"
    )
    return "\n".join(lines)
