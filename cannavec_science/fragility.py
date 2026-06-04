"""Fragility Index for a single 2×2 trial (spec 022).

The Fragility Index (Walsh et al. 2014, J Clin Epidemiol 67:622, PMID 24411409)
is the minimum number of patients in the lower-event-*rate* arm whose outcome
would have to change from a non-event to an event to turn a statistically
significant result (two-sided Fisher's exact p < α) into a non-significant one.
A small FI means a "significant" finding hangs on a handful of patients — the
single most legible robustness check a reviewer applies to a headline result.

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
    control arm. Convert non-events to events one at a time in the lower-event-
    *rate* arm — the direction that shrinks the absolute risk difference and so
    moves the table toward the null — until two-sided Fisher's exact p ≥
    ``alpha``; the FI is the number of conversions. Reported only for an
    already-significant result.
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

    return _resolve_significant(
        a=a, b=b, c=c, d=d, alpha=alpha,
        events_t=events_t, n_t=n_t, events_c=events_c, n_c=n_c,
    )


def _resolve_significant(
    *, a: int, b: int, c: int, d: int, alpha: float,
    events_t: int, n_t: int, events_c: int, n_c: int,
) -> FragilityResult:
    """Compute the Fragility Index of an already-significant 2×2 table.

    The table is driven toward the null by converting non-events to events in
    the **lower-event-rate** arm — the direction that shrinks the absolute risk
    difference and so raises the two-sided Fisher p. Choosing by *rate* (not by
    raw event count) is what makes the index direction-correct when the arms
    are unequally sized: the smaller-count arm can be the higher-rate arm, and
    converting events there would push p *away* from α.

    If the chosen arm is exhausted before p reaches α, significance could not
    be broken by this operation; that is reported honestly — never as an index
    whose ``p_at_index`` is still below α.
    """
    p_obs = fisher_exact_two_sided(a, b, c, d)
    total_n = n_t + n_c

    # Lower-rate arm → toward the null. Ties favour treatment (deterministic).
    convert_treatment = (a / n_t) <= (c / n_c)
    arm = "treatment" if convert_treatment else "control"

    count = 0
    p_cur = p_obs
    while p_cur < alpha:
        if convert_treatment:
            if b <= 0:
                break
            a, b = a + 1, b - 1
        else:
            if d <= 0:
                break
            c, d = c + 1, d - 1
        count += 1
        p_cur = fisher_exact_two_sided(a, b, c, d)

    # Guard: the arm exhausted without lifting p to α. Significance is
    # unbreakable by this operation — say so plainly, emit no bogus index.
    if p_cur < alpha:
        return FragilityResult(
            events_t=events_t, n_t=n_t, events_c=events_c, n_c=n_c,
            alpha=alpha, p_value=p_obs, significant=True,
            fragility_index=None, fragility_quotient=None, p_at_index=None,
            modified_arm=arm,
            rationale=(
                f"Significant at two-sided Fisher p = {p_obs:.4f}; this "
                f"significance cannot be broken by converting non-events to "
                f"events in the {arm} arm (the lower-rate arm) — that arm is "
                f"exhausted while p is still {p_cur:.4f} < α = {alpha:g}. The "
                "Fragility Index is undefined for this operation here."
            ),
        )

    fq = count / total_n
    rationale = (
        f"Significant at p = {p_obs:.4f}; converting {count} non-event"
        f"{'s' if count != 1 else ''} to event{'s' if count != 1 else ''} in "
        f"the {arm} arm (the lower-rate arm) lifts p to {p_cur:.4f} ≥ "
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
    if result.significant and result.fragility_index is not None:
        lines.append(f"- **Fragility Index:** {result.fragility_index}")
        lines.append(
            f"- **Fragility Quotient:** {result.fragility_quotient:.3f} "
            "(FI / total N)")
        lines.append(
            f"- **p at the index:** {result.p_at_index:.4f} "
            f"(just ≥ α, via the {result.modified_arm} arm)")
    elif result.significant:
        lines.append("- **Fragility Index:** not applicable — significance "
                     "cannot be broken by this conversion")
    else:
        lines.append("- **Fragility Index:** not applicable — result is not "
                     "significant")
    lines.append("")
    lines.append(f"_{result.rationale}_")
    return "\n".join(lines)
