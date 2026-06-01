"""Quantitative evidence synthesis — deterministic meta-analysis (spec 011).

This module is the backbone's biostatistician. It pools per-study effect
sizes into a fixed-effect and a DerSimonian-Laird random-effects estimate,
quantifies heterogeneity (Cochran's Q, I², τ²), and maps I² to a GRADE
*inconsistency* verdict that feeds
:func:`cannavec_science.evidence.apply_grade_modifiers` and the
:mod:`cannavec_science.grade_profile` table.

Constitutional gates:

- **§I (Primary-Source-Or-Refuse).** Every :class:`EffectSize` MUST carry a
  primary-source identifier (PMID / DOI / NCT / ChEMBL / UniProt / URL). An
  effect size without one is rejected at construction time — there is no way
  to pool an unanchored number.
- **§II / §VII (Deterministic GRADE honesty).** The inconsistency verdict is
  computed from I², not asserted by prose. Same input → byte-identical
  output.
- **§X (Stdlib-only).** Only :mod:`math` and :mod:`dataclasses` are used.
  No NumPy, no SciPy. The χ² p-value for Cochran's Q is computed from the
  regularized upper incomplete gamma function via ``math.lgamma``; normal
  tail probabilities use ``math.erfc``.

Effect measures supported:

- ``OR`` / ``RR`` — binary 2×2 tables, pooled on the log scale, displayed
  exponentiated (Haldane-Anscombe 0.5 continuity correction on zero cells).
- ``MD`` — raw mean difference between two arms.
- ``SMD`` — standardized mean difference (Hedges' g, small-sample corrected).
- ``generic`` — caller supplies precomputed (yᵢ, vᵢ) on whatever scale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence


__all__ = [
    "MetaAnalysisError",
    "EffectSize",
    "MetaAnalysisResult",
    "binary_effect",
    "continuous_effect",
    "meta_analyze",
    "grade_inconsistency",
    "render_markdown",
]


class MetaAnalysisError(ValueError):
    """Raised when a meta-analysis cannot be performed deterministically.

    Covers the §I refusal (an effect size without a primary-source
    identifier), an empty study set, and impossible inputs (non-positive
    variance, impossible 2×2 cell counts).
    """


# Ratio measures are pooled on the natural-log scale and reported back-
# transformed; difference measures are pooled on their native scale.
_LOG_SCALE_MEASURES = frozenset({"OR", "RR"})
_KNOWN_MEASURES = frozenset({"OR", "RR", "MD", "SMD", "generic"})

# Exact two-sided z critical values for the common confidence levels.
# Anything else is computed deterministically via :func:`_inv_norm_cdf`.
_Z_CRITICAL = {
    0.90: 1.6448536269514722,
    0.95: 1.959963984540054,
    0.99: 2.5758293035489004,
}


# ── §I anchor + per-study effect size ───────────────────────────────


@dataclass(frozen=True)
class EffectSize:
    """One study's effect estimate on the analysis scale.

    ``yi`` is the effect (e.g. log odds ratio, mean difference) and ``vi``
    its variance (> 0). The study MUST carry at least one primary-source
    identifier — Constitution §I has no exception for "just the numbers".
    """

    study_id: str
    yi: float
    vi: float
    pmid: str | None = None
    doi: str | None = None
    nct: str | None = None
    chembl: str | None = None
    uniprot: str | None = None
    url: str | None = None
    n: int | None = None          # total sample, for reporting only
    measure: str = "generic"
    corrected: bool = False        # continuity correction applied?

    def __post_init__(self) -> None:
        if not self.identifier:
            raise MetaAnalysisError(
                f"effect size {self.study_id!r} has no primary-source "
                "identifier (§I): set one of pmid/doi/nct/chembl/uniprot/url"
            )
        if not math.isfinite(self.yi):
            raise MetaAnalysisError(
                f"effect size {self.study_id!r} has non-finite yi"
            )
        if not (self.vi > 0 and math.isfinite(self.vi)):
            raise MetaAnalysisError(
                f"effect size {self.study_id!r} has non-positive variance "
                f"(vi={self.vi!r}); a zero-variance study cannot be pooled"
            )

    @property
    def identifier(self) -> str | None:
        """The first primary-source identifier present, tagged by scheme."""
        for scheme, value in (
            ("PMID", self.pmid),
            ("DOI", self.doi),
            ("NCT", self.nct),
            ("ChEMBL", self.chembl),
            ("UniProt", self.uniprot),
            ("URL", self.url),
        ):
            if value:
                return f"{scheme}:{value}"
        return None

    @property
    def se(self) -> float:
        return math.sqrt(self.vi)

    @property
    def weight_fixed(self) -> float:
        return 1.0 / self.vi

    def ci(self, z: float = 1.959963984540054) -> tuple[float, float]:
        half = z * self.se
        return (self.yi - half, self.yi + half)

    def to_dict(self) -> dict:
        lo, hi = self.ci()
        return {
            "study_id": self.study_id,
            "identifier": self.identifier,
            "yi": self.yi,
            "vi": self.vi,
            "se": self.se,
            "ci_95": [lo, hi],
            "weight_fixed": self.weight_fixed,
            "n": self.n,
            "measure": self.measure,
            "corrected": self.corrected,
        }


def _collect_ids(ids: dict) -> dict:
    """Filter a kwargs blob down to the recognised §I identifier fields."""
    return {
        k: ids[k]
        for k in ("pmid", "doi", "nct", "chembl", "uniprot", "url")
        if ids.get(k)
    }


def binary_effect(
    study_id: str,
    *,
    events_t: int,
    n_t: int,
    events_c: int,
    n_c: int,
    measure: str = "OR",
    **ids: object,
) -> EffectSize:
    """Build an :class:`EffectSize` from a binary 2×2 table.

    ``measure`` is ``"OR"`` (log odds ratio) or ``"RR"`` (log risk ratio).
    A Haldane-Anscombe 0.5 continuity correction is applied to every cell
    when any cell is zero.
    """
    measure = measure.upper()
    if measure not in ("OR", "RR"):
        raise MetaAnalysisError(f"binary measure must be OR or RR, got {measure!r}")
    for label, ev, n in (("treatment", events_t, n_t), ("control", events_c, n_c)):
        if n <= 0:
            raise MetaAnalysisError(f"{study_id!r}: {label} arm size must be > 0")
        if ev < 0 or ev > n:
            raise MetaAnalysisError(
                f"{study_id!r}: {label} events ({ev}) out of range [0, {n}]"
            )

    a = float(events_t)
    b = float(n_t - events_t)
    c = float(events_c)
    d = float(n_c - events_c)
    corrected = False
    if 0 in (a, b, c, d):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
        corrected = True

    if measure == "OR":
        yi = math.log((a * d) / (b * c))
        vi = 1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d
    else:  # RR
        risk_t = a / (a + b)
        risk_c = c / (c + d)
        yi = math.log(risk_t / risk_c)
        vi = 1.0 / a - 1.0 / (a + b) + 1.0 / c - 1.0 / (c + d)

    return EffectSize(
        study_id=study_id, yi=yi, vi=vi, n=n_t + n_c,
        measure=measure, corrected=corrected, **_collect_ids(ids),
    )


def continuous_effect(
    study_id: str,
    *,
    mean_t: float,
    sd_t: float,
    n_t: int,
    mean_c: float,
    sd_c: float,
    n_c: int,
    measure: str = "MD",
    **ids: object,
) -> EffectSize:
    """Build an :class:`EffectSize` from two continuous arm summaries.

    ``measure`` is ``"MD"`` (raw mean difference) or ``"SMD"`` (standardized
    mean difference, Hedges' g with the small-sample J correction).
    """
    measure = measure.upper()
    if measure not in ("MD", "SMD"):
        raise MetaAnalysisError(f"continuous measure must be MD or SMD, got {measure!r}")
    if n_t < 2 or n_c < 2:
        raise MetaAnalysisError(f"{study_id!r}: each arm needs n ≥ 2")
    if sd_t <= 0 or sd_c <= 0:
        raise MetaAnalysisError(f"{study_id!r}: standard deviations must be > 0")

    if measure == "MD":
        yi = mean_t - mean_c
        vi = sd_t ** 2 / n_t + sd_c ** 2 / n_c
    else:  # SMD — Hedges' g
        df = n_t + n_c - 2
        sp = math.sqrt(((n_t - 1) * sd_t ** 2 + (n_c - 1) * sd_c ** 2) / df)
        if sp <= 0:
            raise MetaAnalysisError(f"{study_id!r}: pooled SD is zero")
        d = (mean_t - mean_c) / sp
        j = 1.0 - 3.0 / (4.0 * (n_t + n_c) - 9.0)
        g = j * d
        var_d = (n_t + n_c) / (n_t * n_c) + d ** 2 / (2.0 * df)
        yi = g
        vi = j ** 2 * var_d

    return EffectSize(
        study_id=study_id, yi=yi, vi=vi, n=n_t + n_c,
        measure=measure, **_collect_ids(ids),
    )


# ── Pooled result ───────────────────────────────────────────────────


@dataclass(frozen=True)
class MetaAnalysisResult:
    """Deterministic output of :func:`meta_analyze`."""

    measure: str
    log_scale: bool
    k: int
    studies: tuple[EffectSize, ...]
    confidence: float

    fixed_estimate: float
    fixed_ci: tuple[float, float]
    fixed_p: float

    random_estimate: float
    random_ci: tuple[float, float]
    random_p: float

    q: float
    q_df: int
    q_p: float
    i_squared: float        # percent, 0-100
    tau_squared: float

    inconsistency: str           # GRADE verdict label
    inconsistency_serious: bool  # convenience for apply_grade_modifiers
    downgrade_steps: int         # 0 / 1 / 2
    rationale: str

    point_estimates_consistent_direction: bool = True
    all_cis_overlap_pooled: bool = True

    # ── display helpers (ratio measures shown exponentiated) ──

    def _disp(self, x: float) -> float:
        return math.exp(x) if self.log_scale else x

    @property
    def fixed_estimate_display(self) -> float:
        return self._disp(self.fixed_estimate)

    @property
    def fixed_ci_display(self) -> tuple[float, float]:
        lo, hi = self.fixed_ci
        return (self._disp(lo), self._disp(hi))

    @property
    def random_estimate_display(self) -> float:
        return self._disp(self.random_estimate)

    @property
    def random_ci_display(self) -> tuple[float, float]:
        lo, hi = self.random_ci
        return (self._disp(lo), self._disp(hi))

    @property
    def null_value_display(self) -> float:
        """The no-effect value on the display scale (1 for ratios, 0 else)."""
        return 1.0 if self.log_scale else 0.0

    def to_dict(self) -> dict:
        return {
            "measure": self.measure,
            "log_scale": self.log_scale,
            "k": self.k,
            "confidence": self.confidence,
            "fixed": {
                "estimate": self.fixed_estimate,
                "ci": list(self.fixed_ci),
                "estimate_display": self.fixed_estimate_display,
                "ci_display": list(self.fixed_ci_display),
                "p_value": self.fixed_p,
            },
            "random": {
                "estimate": self.random_estimate,
                "ci": list(self.random_ci),
                "estimate_display": self.random_estimate_display,
                "ci_display": list(self.random_ci_display),
                "p_value": self.random_p,
            },
            "heterogeneity": {
                "q": self.q,
                "df": self.q_df,
                "q_p_value": self.q_p,
                "i_squared": self.i_squared,
                "tau_squared": self.tau_squared,
                "point_estimates_consistent_direction":
                    self.point_estimates_consistent_direction,
                "all_cis_overlap_pooled": self.all_cis_overlap_pooled,
            },
            "grade_inconsistency": {
                "verdict": self.inconsistency,
                "serious": self.inconsistency_serious,
                "downgrade_steps": self.downgrade_steps,
                "rationale": self.rationale,
            },
            "studies": [s.to_dict() for s in self.studies],
        }


# ── GRADE inconsistency mapping ─────────────────────────────────────


def grade_inconsistency(
    i_squared: float, k: int
) -> tuple[str, bool, int, str]:
    """Map I² (and study count) to a GRADE inconsistency verdict.

    Returns ``(verdict, serious, downgrade_steps, rationale)``. Thresholds
    follow the Cochrane handbook / GRADE guidance:

    - k < 2 → inconsistency is not assessable from a single study.
    - I² < 40 % → *not serious*.
    - 40 ≤ I² < 75 % → *serious* (one GRADE downgrade).
    - I² ≥ 75 % → *very serious* (two GRADE downgrades).
    """
    if k < 2:
        return (
            "not assessable (single study)",
            False,
            0,
            "Inconsistency cannot be assessed with fewer than two studies.",
        )
    if i_squared < 40.0:
        return (
            "not serious",
            False,
            0,
            f"I² = {i_squared:.0f}% indicates low heterogeneity (< 40%).",
        )
    if i_squared < 75.0:
        return (
            "serious",
            True,
            1,
            f"I² = {i_squared:.0f}% indicates substantial heterogeneity "
            "(40–75%); GRADE downgrades certainty one level for inconsistency.",
        )
    return (
        "very serious",
        True,
        2,
        f"I² = {i_squared:.0f}% indicates considerable heterogeneity "
        "(≥ 75%); GRADE downgrades certainty two levels for inconsistency.",
    )


# ── Core pooling ────────────────────────────────────────────────────


def meta_analyze(
    effects: Sequence[EffectSize] | Iterable[EffectSize],
    *,
    measure: str | None = None,
    log_scale: bool | None = None,
    confidence: float = 0.95,
) -> MetaAnalysisResult:
    """Pool ``effects`` into fixed- and random-effects estimates.

    ``measure`` defaults to the measure carried by the supplied effect
    sizes (or ``"generic"``). ``log_scale`` defaults to ``True`` for the
    ratio measures (OR / RR) and ``False`` otherwise.
    """
    studies = tuple(effects)
    if not studies:
        raise MetaAnalysisError("meta_analyze requires at least one effect size")

    # §I — defensive re-check (EffectSize enforces this at construction, but
    # generic dicts decoded elsewhere could bypass that path).
    for s in studies:
        if not s.identifier:
            raise MetaAnalysisError(
                f"effect size {s.study_id!r} has no primary-source identifier (§I)"
            )

    if measure is None:
        seen = {s.measure for s in studies}
        measure = seen.pop() if len(seen) == 1 else "generic"
    if measure not in _KNOWN_MEASURES:
        raise MetaAnalysisError(
            f"unknown measure {measure!r}; expected one of {sorted(_KNOWN_MEASURES)}"
        )
    if log_scale is None:
        log_scale = measure in _LOG_SCALE_MEASURES

    z = _z_critical(confidence)
    k = len(studies)

    # Inverse-variance fixed effect.
    weights = [s.weight_fixed for s in studies]
    sum_w = math.fsum(weights)
    sum_wy = math.fsum(w * s.yi for w, s in zip(weights, studies))
    fixed = sum_wy / sum_w
    fixed_var = 1.0 / sum_w
    fixed_se = math.sqrt(fixed_var)
    fixed_ci = (fixed - z * fixed_se, fixed + z * fixed_se)
    fixed_p = _two_sided_p(fixed / fixed_se) if fixed_se > 0 else 0.0

    # Cochran's Q and heterogeneity.
    q = math.fsum(w * (s.yi - fixed) ** 2 for w, s in zip(weights, studies))
    df = k - 1
    if q <= 1e-12 or df <= 0:
        i_squared = 0.0
    else:
        i_squared = max(0.0, (q - df) / q) * 100.0
    if df >= 1:
        sum_w2 = math.fsum(w * w for w in weights)
        c_const = sum_w - sum_w2 / sum_w
        tau_squared = max(0.0, (q - df) / c_const) if c_const > 0 else 0.0
        q_p = _chi2_sf(q, df)
    else:
        tau_squared = 0.0
        q_p = 1.0

    # DerSimonian-Laird random effects.
    re_weights = [1.0 / (s.vi + tau_squared) for s in studies]
    sum_rw = math.fsum(re_weights)
    sum_rwy = math.fsum(w * s.yi for w, s in zip(re_weights, studies))
    random = sum_rwy / sum_rw
    random_var = 1.0 / sum_rw
    random_se = math.sqrt(random_var)
    random_ci = (random - z * random_se, random + z * random_se)
    random_p = _two_sided_p(random / random_se) if random_se > 0 else 0.0

    verdict, serious, steps, rationale = grade_inconsistency(i_squared, k)

    consistent_dir = (
        all(s.yi >= 0 for s in studies) or all(s.yi <= 0 for s in studies)
    )
    all_overlap = all(
        s.ci(z)[0] <= random <= s.ci(z)[1] for s in studies
    )

    return MetaAnalysisResult(
        measure=measure,
        log_scale=log_scale,
        k=k,
        studies=studies,
        confidence=confidence,
        fixed_estimate=fixed,
        fixed_ci=fixed_ci,
        fixed_p=fixed_p,
        random_estimate=random,
        random_ci=random_ci,
        random_p=random_p,
        q=q,
        q_df=df,
        q_p=q_p,
        i_squared=i_squared,
        tau_squared=tau_squared,
        inconsistency=verdict,
        inconsistency_serious=serious,
        downgrade_steps=steps,
        rationale=rationale,
        point_estimates_consistent_direction=consistent_dir,
        all_cis_overlap_pooled=all_overlap,
    )


# ── Renderer ────────────────────────────────────────────────────────


def render_markdown(result: MetaAnalysisResult) -> str:
    """Deterministic Markdown forest table + pooled summary."""
    pct = int(round(result.confidence * 100))
    is_ratio = result.log_scale
    null = result.null_value_display

    def fmt(x: float) -> str:
        return f"{x:.3f}"

    lines: list[str] = []
    lines.append(f"## Meta-analysis — {result.measure} ({result.k} studies)")
    lines.append("")
    lines.append(f"| Study | Identifier | Effect | {pct}% CI | Weight |")
    lines.append("|---|---|---|---|---|")
    sum_w = math.fsum(s.weight_fixed for s in result.studies)
    for s in result.studies:
        lo, hi = s.ci(_z_critical(result.confidence))
        if is_ratio:
            eff, lo, hi = math.exp(s.yi), math.exp(lo), math.exp(hi)
        else:
            eff = s.yi
        w_pct = 100.0 * s.weight_fixed / sum_w if sum_w else 0.0
        ident = s.identifier or "—"
        tag = " *(0.5 cc)*" if s.corrected else ""
        lines.append(
            f"| {s.study_id}{tag} | {ident} | {fmt(eff)} | "
            f"[{fmt(lo)}, {fmt(hi)}] | {w_pct:.1f}% |"
        )
    lines.append("")

    fe = result.fixed_estimate_display
    fl, fh = result.fixed_ci_display
    re = result.random_estimate_display
    rl, rh = result.random_ci_display
    lines.append(f"**Fixed effect:** {fmt(fe)} [{fmt(fl)}, {fmt(fh)}]  "
                 f"(p = {result.fixed_p:.4f})")
    lines.append("")
    lines.append(f"**Random effects (DerSimonian–Laird):** {fmt(re)} "
                 f"[{fmt(rl)}, {fmt(rh)}]  (p = {result.random_p:.4f})")
    lines.append("")
    lines.append(
        f"**Heterogeneity:** Q = {fmt(result.q)} "
        f"(df = {result.q_df}, p = {result.q_p:.4f}), "
        f"I² = {result.i_squared:.0f}%, τ² = {fmt(result.tau_squared)}"
    )
    lines.append("")
    lines.append(
        f"**GRADE inconsistency:** {result.inconsistency} — {result.rationale}"
    )
    lines.append("")
    lines.append(
        f"_No-effect line at {fmt(null)}. Effect sizes pooled by "
        f"inverse-variance weighting; certainty downgrades per GRADE "
        f"(Schünemann et al. 2013). Deterministic — no LLM in the path._"
    )
    return "\n".join(lines)


# ── stdlib numerics (no NumPy / SciPy — Constitution §X) ─────────────


def _z_critical(confidence: float) -> float:
    """Two-sided z critical value for ``confidence`` (e.g. 0.95 → 1.95996)."""
    if not (0.0 < confidence < 1.0):
        raise MetaAnalysisError(f"confidence must be in (0, 1), got {confidence!r}")
    if confidence in _Z_CRITICAL:
        return _Z_CRITICAL[confidence]
    return _inv_norm_cdf(1.0 - (1.0 - confidence) / 2.0)


def _two_sided_p(z: float) -> float:
    """Two-sided p-value for a standard-normal z statistic."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def _inv_norm_cdf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation).

    Deterministic, stdlib-only. Max absolute error ≈ 1.15e-9, refined here
    with one Halley step against ``math.erf`` for full double precision.
    """
    if not (0.0 < p < 1.0):
        raise MetaAnalysisError(f"probability must be in (0, 1), got {p!r}")
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    # One Halley refinement step.
    e = 0.5 * math.erfc(-x / math.sqrt(2.0)) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    x = x - u / (1.0 + x * u / 2.0)
    return x


def _chi2_sf(x: float, df: int) -> float:
    """χ² survival function P(X > x) for ``df`` degrees of freedom.

    Implemented via the regularized upper incomplete gamma Q(df/2, x/2),
    using ``math.lgamma`` (stdlib). Returns 1.0 for non-positive ``x``.
    """
    if df <= 0 or x <= 0:
        return 1.0
    return _gammq(df / 2.0, x / 2.0)


def _gammq(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) = 1 − P(a, x)."""
    if x < 0.0 or a <= 0.0:
        raise MetaAnalysisError("invalid arguments to incomplete gamma")
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gamma_series(a, x)
    return _gamma_cf(a, x)


def _gamma_series(a: float, x: float) -> float:
    """Series evaluation of the lower regularized incomplete gamma P(a, x)."""
    gln = math.lgamma(a)
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(1000):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-15:
            break
    return total * math.exp(-x + a * math.log(x) - gln)


def _gamma_cf(a: float, x: float) -> float:
    """Continued-fraction evaluation of Q(a, x) (modified Lentz)."""
    gln = math.lgamma(a)
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - gln) * h
