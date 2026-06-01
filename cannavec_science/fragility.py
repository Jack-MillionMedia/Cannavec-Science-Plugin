"""Fragility Index for a single 2×2 trial (spec 022).

The Fragility Index (Walsh et al. 2014, J Clin Epidemiol 67:622, PMID 24411409)
is the minimum number of patients in the smaller-event arm whose outcome would
have to change from a non-event to an event to turn a statistically significant
result (two-sided Fisher's exact p < α) into a non-significant one. A small FI
means a "significant" finding hangs on a handful of patients — the single most
legible robustness check a reviewer applies to a headline trial result.

Deterministic and stdlib-only (§X): exact two-sided Fisher via ``math.comb``;
no SciPy. The index is reported only for an already-significant result; a
non-significant input is surfaced honestly rather than coerced into a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb


__all__ = [
    "FragilityError",
    "FragilityResult",
    "fisher_exact_two_sided",
    "fragility_index",
    "render_fragility",
]


class FragilityError(ValueError):
    """Raised on a malformed 2×2 table."""


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher's exact p for the 2×2 table ``[[a, b], [c, d]]``.

    Sums the hypergeometric probabilities of every table (same margins) whose
    probability is ≤ that of the observed table — the standard two-sided
    convention. Exact integer binomials (``math.comb``); deterministic.
    """
    for name, v in (("a", a), ("b", b), ("c", c), ("d", d)):
        if v < 0:
            raise FragilityError(f"cell {name} must be ≥ 0; got {v}")
    r1, r2 = a + b, c + d
    c1, n = a + c, a + b + c + d
    if r1 == 0 or r2 == 0 or c1 == 0 or (b + d) == 0:
        return 1.0
    denom = comb(n, c1)
    p_obs = comb(r1, a) * comb(r2, c1 - a) / denom
    lo, hi = max(0, c1 - r2), min(r1, c1)
    tol = p_obs * (1.0 + 1e-9)
    total = 0.0
    for k in range(lo, hi + 1):
        pk = comb(r1, k) * comb(r2, c1 - k) / denom
        if pk <= tol:
            total += pk
    return min(1.0, total)


@dataclass(frozen=True)
class FragilityResult:
    """The Fragility Index of one 2×2 trial."""

    events_t: int
    n_t: int
    events_c: int
    n_c: int
    alpha: float
    p_value: float
    significant: bool
    fragility_index: int | None      # None when the result is not significant
    fragility_quotient: float | None  # FI / total N
    p_at_index: float | None         # p once it crosses α
    modified_arm: str | None         # which arm was altered
    rationale: str

    def to_dict(self) -> dict:
        return {
            "events_t": self.events_t,
            "n_t": self.n_t,
            "events_c": self.events_c,
            "n_c": self.n_c,
            "alpha": self.alpha,
            "p_value": self.p_value,
            "significant": self.significant,
            "fragility_index": self.fragility_index,
            "fragility_quotient": self.fragility_quotient,
            "p_at_index": self.p_at_index,
            "modified_arm": self.modified_arm,
            "rationale": self.rationale,
        }


def fragility_index(
    events_t: int, n_t: int, events_c: int, n_c: int, *, alpha: float = 0.05
) -> FragilityResult:
    """Compute the Fragility Index of a 2×2 trial (Walsh 2014).

    ``events_t`` of ``n_t`` in the treatment arm, ``events_c`` of ``n_c`` in the
    control arm. Convert non-events to events one at a time in the arm with the
    fewer events — the direction that moves the table toward the null — until
    two-sided Fisher's exact p ≥ ``alpha``; the FI is the number of conversions.
    Reported only for an already-significant result.
    """
    for label, ev, n in (("treatment", events_t, n_t), ("control", events_c, n_c)):
        if n <= 0:
            raise FragilityError(f"{label} arm size must be > 0")
        if ev < 0 or ev > n:
            raise FragilityError(
                f"{label} events ({ev}) out of range [0, {n}]"
            )
    if not 0.0 < alpha < 1.0:
        raise FragilityError(f"alpha must be in (0, 1); got {alpha}")

    a, b = events_t, n_t - events_t
    c, d = events_c, n_c - events_c
    p_obs = fisher_exact_two_sided(a, b, c, d)
    total_n = n_t + n_c

    if p_obs >= alpha:
        return FragilityResult(
            events_t=events_t, n_t=n_t, events_c=events_c, n_c=n_c,
            alpha=alpha, p_value=p_obs, significant=False,
            fragility_index=None, fragility_quotient=None, p_at_index=None,
            modified_arm=None,
            rationale=(
                f"The result is not statistically significant (two-sided "
                f"Fisher p = {p_obs:.4f} ≥ α = {alpha:g}); the Fragility Index "
                "is defined for significant results only."
            ),
        )

    # Modify the arm with the fewer events: non-event → event, toward the null.
    treat_fewer = a <= c
    arm = "treatment" if treat_fewer else "control"
    count = 0
    p_cur = p_obs
    while p_cur < alpha:
        if treat_fewer:
            if b <= 0:
                break
            a, b = a + 1, b - 1
        else:
            if d <= 0:
                break
            c, d = c + 1, d - 1
        count += 1
        p_cur = fisher_exact_two_sided(a, b, c, d)

    fq = count / total_n
    rationale = (
        f"Significant at p = {p_obs:.4f}; converting {count} non-event"
        f"{'s' if count != 1 else ''} to event{'s' if count != 1 else ''} in "
        f"the {arm} arm (the fewer-event arm) lifts p to {p_cur:.4f} ≥ "
        f"α = {alpha:g}. Fragility quotient {fq:.3f} (FI / {total_n}). "
        + ("A Fragility Index of 1 means a single patient's outcome carries "
           "the entire significance claim."
           if count == 1 else
           f"{count} patients carry the significance claim.")
    )
    return FragilityResult(
        events_t=events_t, n_t=n_t, events_c=events_c, n_c=n_c,
        alpha=alpha, p_value=p_obs, significant=True,
        fragility_index=count, fragility_quotient=fq, p_at_index=p_cur,
        modified_arm=arm, rationale=rationale,
    )


def render_fragility(result: FragilityResult) -> str:
    """Markdown for a Fragility Index result."""
    lines = [
        "## Fragility Index",
        "",
        f"- **Treatment:** {result.events_t} / {result.n_t} events",
        f"- **Control:** {result.events_c} / {result.n_c} events",
        f"- **Two-sided Fisher p:** {result.p_value:.4f} "
        f"(α = {result.alpha:g})",
    ]
    if result.significant:
        lines.append(f"- **Fragility Index:** {result.fragility_index}")
        lines.append(
            f"- **Fragility Quotient:** {result.fragility_quotient:.3f} "
            "(FI / total N)")
        lines.append(
            f"- **p at the index:** {result.p_at_index:.4f} "
            f"(just ≥ α, via the {result.modified_arm} arm)")
    else:
        lines.append("- **Fragility Index:** not applicable — result is not "
                     "significant")
    lines.append("")
    lines.append(f"_{result.rationale}_")
    return "\n".join(lines)
