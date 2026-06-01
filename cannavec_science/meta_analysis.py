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
    "effects_from_records",
    "meta_analyze",
    "grade_inconsistency",
    "render_markdown",
    "EggerResult",
    "egger_test",
    "grade_publication_bias",
    "LeaveOneOutRow",
    "leave_one_out",
    "render_egger",
    "render_leave_one_out",
    "SubgroupRow",
    "SubgroupResult",
    "subgroup_analysis",
    "render_subgroups",
    "ImputedStudy",
    "TrimFillResult",
    "trim_and_fill",
    "render_trim_fill",
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
    subgroup: str | None = None    # moderator label (spec 014)

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
            "subgroup": self.subgroup,
        }


def _collect_ids(ids: dict) -> dict:
    """Filter a kwargs blob down to the §I identifier fields + subgroup."""
    keep = ("pmid", "doi", "nct", "chembl", "uniprot", "url", "subgroup")
    return {k: ids[k] for k in keep if ids.get(k)}


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


def effects_from_records(records, *, measure: str = "generic") -> list:
    """Build :class:`EffectSize` objects from a list of dict study records.

    The shared parser behind ``meta`` (CLI) and the Summary-of-Findings
    composer. Each record is a binary 2×2 table (``events_t/n_t/events_c/n_c``
    for OR/RR), a continuous arm pair (``mean_t/sd_t/n_t/mean_c/sd_c/n_c`` for
    MD/SMD), or a precomputed generic effect (``yi/vi``), plus §I identifier
    fields and an optional ``subgroup`` label. Raises ``KeyError`` on a missing
    required field and :class:`MetaAnalysisError` on invalid data.
    """
    m = (measure or "generic").upper() if isinstance(measure, str) else "GENERIC"
    id_keys = ("pmid", "doi", "nct", "chembl", "uniprot", "url", "subgroup")
    effects: list = []
    for idx, st in enumerate(records):
        sid = st.get("study_id") or st.get("id") or f"study {idx + 1}"
        ids = {k: st[k] for k in id_keys if st.get(k)}
        if m in ("OR", "RR"):
            es = binary_effect(
                sid, events_t=st["events_t"], n_t=st["n_t"],
                events_c=st["events_c"], n_c=st["n_c"], measure=m, **ids,
            )
        elif m in ("MD", "SMD"):
            es = continuous_effect(
                sid, mean_t=st["mean_t"], sd_t=st["sd_t"], n_t=st["n_t"],
                mean_c=st["mean_c"], sd_c=st["sd_c"], n_c=st["n_c"],
                measure=m, **ids,
            )
        else:
            es = EffectSize(
                study_id=sid, yi=float(st["yi"]), vi=float(st["vi"]),
                n=st.get("n"), **ids,
            )
        effects.append(es)
    return effects


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
    # 95% prediction interval for a new study's true effect (spec 013);
    # None when k < 3 (undefined).
    prediction_interval: tuple[float, float] | None = None

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
    def prediction_interval_display(self) -> tuple[float, float] | None:
        if self.prediction_interval is None:
            return None
        lo, hi = self.prediction_interval
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
                "prediction_interval": (
                    list(self.prediction_interval)
                    if self.prediction_interval is not None else None
                ),
                "prediction_interval_display": (
                    list(self.prediction_interval_display)
                    if self.prediction_interval_display is not None else None
                ),
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

    # 95% prediction interval for a new study's true effect (spec 013).
    # Higgins, Thompson & Spiegelhalter 2009 / IntHout 2016: mu ±
    # t_{k-2} * sqrt(tau^2 + Var(mu)). Undefined for k < 3.
    prediction_interval: tuple[float, float] | None = None
    if k >= 3:
        t_pi = _t_critical(confidence, k - 2)
        pi_half = t_pi * math.sqrt(tau_squared + random_var)
        prediction_interval = (random - pi_half, random + pi_half)

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
        prediction_interval=prediction_interval,
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
    pid = result.prediction_interval_display
    if pid is not None:
        lines.append("")
        lines.append(
            f"**95% prediction interval:** [{fmt(pid[0])}, {fmt(pid[1])}]  "
            f"_(plausible true effect of a new study; widens the CI by τ²)_"
        )
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


# ── Robustness diagnostics (spec 012) ───────────────────────────────


@dataclass(frozen=True)
class EggerResult:
    """Egger's regression test for small-study effects / funnel asymmetry."""

    k: int
    intercept: float
    intercept_se: float
    t: float
    df: int
    p_value: float
    slope: float
    bias_label: str          # GRADE publication-bias verdict
    bias_serious: bool        # triggers a GRADE downgrade?
    rationale: str

    def to_dict(self) -> dict:
        return {
            "k": self.k,
            "intercept": self.intercept,
            "intercept_se": self.intercept_se,
            "t": self.t,
            "df": self.df,
            "p_value": self.p_value,
            "slope": self.slope,
            "publication_bias": {
                "verdict": self.bias_label,
                "serious": self.bias_serious,
                "rationale": self.rationale,
            },
        }


def _pubbias_verdict(p_value: float, k: int) -> tuple[str, bool, str]:
    """Map an Egger p-value + study count to a GRADE publication-bias verdict.

    Egger's test is underpowered below 10 studies (Sterne 2011, BMJ), so a
    positive test with 3 ≤ k < 10 is reported but does NOT trigger a GRADE
    downgrade. Only k ≥ 10 with p < 0.10 yields a "strongly suspected"
    downgrade.
    """
    if k < 3:
        return (
            "not assessable (< 3 studies)",
            False,
            "Egger's test cannot be computed with fewer than three studies.",
        )
    if p_value < 0.10:
        if k >= 10:
            return (
                "strongly suspected",
                True,
                f"Egger's test p = {p_value:.4f} (k = {k}) indicates funnel "
                "asymmetry; GRADE downgrades certainty one level for "
                "publication bias.",
            )
        return (
            "small-study effects detected (underpowered)",
            False,
            f"Egger's test p = {p_value:.4f} but only k = {k} studies; the "
            "test is underpowered below 10 studies (Sterne 2011), so no GRADE "
            "downgrade is applied — interpret with caution.",
        )
    return (
        "undetected",
        False,
        f"Egger's test p = {p_value:.4f} (k = {k}); no funnel asymmetry detected.",
    )


def egger_test(effects: Sequence[EffectSize] | Iterable[EffectSize]) -> EggerResult:
    """Egger's regression test for funnel-plot asymmetry.

    Regresses each study's standard-normal deviate (yᵢ/seᵢ) on its precision
    (1/seᵢ) by ordinary least squares; the intercept's two-sided t-test
    (df = k − 2) is the test for small-study effects. Requires k ≥ 3.
    """
    studies = tuple(effects)
    k = len(studies)
    if k < 3:
        raise MetaAnalysisError("Egger's test requires at least 3 studies")
    for s in studies:
        if not s.identifier:
            raise MetaAnalysisError(
                f"effect size {s.study_id!r} has no primary-source identifier (§I)"
            )

    xs = [1.0 / s.se for s in studies]          # precision
    ys = [s.yi / s.se for s in studies]         # standard normal deviate
    n = float(k)
    xbar = math.fsum(xs) / n
    ybar = math.fsum(ys) / n
    sxx = math.fsum((x - xbar) ** 2 for x in xs)
    if sxx <= 0:
        raise MetaAnalysisError("Egger's test undefined: studies share identical precision")
    sxy = math.fsum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    df = k - 2
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    sse = math.fsum(e * e for e in residuals)
    s2 = sse / df
    var_a = s2 * (1.0 / n + xbar * xbar / sxx)
    se_a = math.sqrt(var_a) if var_a > 0 else 0.0

    if se_a > 0:
        t = intercept / se_a
        p_value = _t_sf_two_sided(t, df)
    elif abs(intercept) < 1e-12:
        t, p_value = 0.0, 1.0
    else:
        t, p_value = math.copysign(math.inf, intercept), 0.0

    label, serious, rationale = _pubbias_verdict(p_value, k)
    return EggerResult(
        k=k, intercept=intercept, intercept_se=se_a, t=t, df=df,
        p_value=p_value, slope=slope, bias_label=label,
        bias_serious=serious, rationale=rationale,
    )


def grade_publication_bias(result: EggerResult) -> tuple[str, bool, str]:
    """Return the (verdict, serious, rationale) carried by an Egger result."""
    return (result.bias_label, result.bias_serious, result.rationale)


@dataclass(frozen=True)
class LeaveOneOutRow:
    """One row of a leave-one-out sensitivity analysis."""

    dropped_study_id: str
    dropped_identifier: str | None
    k_remaining: int
    estimate: float
    estimate_display: float
    ci: tuple[float, float]
    ci_display: tuple[float, float]
    i_squared: float
    influence: float          # |full pooled − leave-one-out pooled|, analysis scale

    def to_dict(self) -> dict:
        return {
            "dropped_study_id": self.dropped_study_id,
            "dropped_identifier": self.dropped_identifier,
            "k_remaining": self.k_remaining,
            "estimate": self.estimate,
            "estimate_display": self.estimate_display,
            "ci": list(self.ci),
            "ci_display": list(self.ci_display),
            "i_squared": self.i_squared,
            "influence": self.influence,
        }


def leave_one_out(
    effects: Sequence[EffectSize] | Iterable[EffectSize],
    *,
    measure: str | None = None,
    confidence: float = 0.95,
) -> tuple[LeaveOneOutRow, ...]:
    """Re-pool the evidence dropping each study in turn (requires k ≥ 2).

    Surfaces the influence of each trial — the study whose removal would most
    shift the random-effects estimate is the one a reviewer scrutinises first.
    """
    studies = tuple(effects)
    if len(studies) < 2:
        raise MetaAnalysisError("leave-one-out requires at least 2 studies")
    full = meta_analyze(studies, measure=measure, confidence=confidence)
    rows: list[LeaveOneOutRow] = []
    for i in range(len(studies)):
        subset = studies[:i] + studies[i + 1:]
        res = meta_analyze(subset, measure=measure, confidence=confidence)
        rows.append(LeaveOneOutRow(
            dropped_study_id=studies[i].study_id,
            dropped_identifier=studies[i].identifier,
            k_remaining=res.k,
            estimate=res.random_estimate,
            estimate_display=res.random_estimate_display,
            ci=res.random_ci,
            ci_display=res.random_ci_display,
            i_squared=res.i_squared,
            influence=abs(full.random_estimate - res.random_estimate),
        ))
    return tuple(rows)


def render_egger(result: EggerResult) -> str:
    """Markdown for an Egger small-study-effects test."""
    return "\n".join([
        "### Small-study effects — Egger's test",
        "",
        f"- **Intercept:** {result.intercept:.3f} "
        f"(SE {result.intercept_se:.3f})",
        f"- **t = {result.t:.3f}**, df = {result.df}, "
        f"two-sided p = {result.p_value:.4f}",
        f"- **Publication bias:** {result.bias_label} — {result.rationale}",
    ])


def render_leave_one_out(
    rows: Sequence[LeaveOneOutRow], *, log_scale: bool = False
) -> str:
    """Markdown table for a leave-one-out sensitivity analysis."""
    lines = [
        "### Leave-one-out sensitivity",
        "",
        "| Omitted study | k | Pooled (random) | I² | Influence |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.dropped_study_id} | {r.k_remaining} | "
            f"{r.estimate_display:.3f} [{r.ci_display[0]:.3f}, "
            f"{r.ci_display[1]:.3f}] | {r.i_squared:.0f}% | "
            f"{r.influence:.3f} |"
        )
    lines.append("")
    lines.append(
        "_Influence = absolute shift in the pooled (log-scale) estimate when "
        "that study is omitted; the largest-influence study drives the result._"
    )
    return "\n".join(lines)


# ── Subgroup analysis (spec 014) ────────────────────────────────────


@dataclass(frozen=True)
class SubgroupRow:
    """One subgroup's pooled summary."""

    label: str
    k: int
    estimate: float
    estimate_display: float
    ci: tuple[float, float]
    ci_display: tuple[float, float]
    i_squared: float
    tau_squared: float
    weight_percent: float

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "k": self.k,
            "estimate": self.estimate,
            "estimate_display": self.estimate_display,
            "ci": list(self.ci),
            "ci_display": list(self.ci_display),
            "i_squared": self.i_squared,
            "tau_squared": self.tau_squared,
            "weight_percent": self.weight_percent,
        }


@dataclass(frozen=True)
class SubgroupResult:
    """Cochrane "test for subgroup differences" (Q_between)."""

    model: str
    measure: str
    log_scale: bool
    subgroups: tuple[SubgroupRow, ...]
    overall_estimate: float
    overall_estimate_display: float
    q_between: float
    q_between_df: int
    q_between_p: float
    i_squared_between: float
    significant: bool
    confidence: float
    rationale: str

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "measure": self.measure,
            "log_scale": self.log_scale,
            "overall_estimate": self.overall_estimate,
            "overall_estimate_display": self.overall_estimate_display,
            "q_between": self.q_between,
            "q_between_df": self.q_between_df,
            "q_between_p": self.q_between_p,
            "i_squared_between": self.i_squared_between,
            "significant": self.significant,
            "rationale": self.rationale,
            "subgroups": [s.to_dict() for s in self.subgroups],
        }


def subgroup_analysis(
    effects: Sequence[EffectSize] | Iterable[EffectSize],
    *,
    model: str = "random",
    measure: str | None = None,
    confidence: float = 0.95,
) -> SubgroupResult:
    """Partition ``effects`` by their ``subgroup`` label and test for
    differences between the subgroup-pooled estimates (Q_between).

    ``model`` is ``"fixed"`` or ``"random"`` (each subgroup pooled with its
    own DerSimonian–Laird τ² when random). Requires every study to carry a
    ``subgroup`` label and at least two distinct subgroups.
    """
    if model not in ("fixed", "random"):
        raise MetaAnalysisError(f"model must be 'fixed' or 'random', got {model!r}")
    studies = tuple(effects)
    if not studies:
        raise MetaAnalysisError("subgroup_analysis requires at least one study")
    for s in studies:
        if not s.identifier:
            raise MetaAnalysisError(
                f"effect size {s.study_id!r} has no primary-source identifier (§I)"
            )
        if not s.subgroup:
            raise MetaAnalysisError(
                f"effect size {s.study_id!r} has no subgroup label"
            )
    if measure is None:
        seen = {s.measure for s in studies}
        measure = seen.pop() if len(seen) == 1 else "generic"
    log_scale = measure in _LOG_SCALE_MEASURES

    # Deterministic subgroup order: sorted by label.
    labels = sorted({s.subgroup for s in studies})
    if len(labels) < 2:
        raise MetaAnalysisError(
            "subgroup_analysis requires at least two distinct subgroups"
        )

    z = _z_critical(confidence)

    # Pool each subgroup; capture estimate + variance under the chosen model.
    group_est: dict[str, float] = {}
    group_var: dict[str, float] = {}
    rows_tmp: list[tuple[str, MetaAnalysisResult]] = []
    for label in labels:
        members = [s for s in studies if s.subgroup == label]
        res = meta_analyze(members, measure=measure, confidence=confidence)
        if model == "fixed":
            est = res.fixed_estimate
            lo, hi = res.fixed_ci
        else:
            est = res.random_estimate
            lo, hi = res.random_ci
        var = ((hi - lo) / (2.0 * z)) ** 2
        group_est[label] = est
        group_var[label] = var
        rows_tmp.append((label, res))

    # Between-groups test: treat subgroup summaries as the units.
    w = {g: 1.0 / v if v > 0 else float("inf") for g, v in group_var.items()}
    sum_w = math.fsum(w[g] for g in labels)
    overall = math.fsum(w[g] * group_est[g] for g in labels) / sum_w
    q_between = math.fsum(w[g] * (group_est[g] - overall) ** 2 for g in labels)
    df = len(labels) - 1
    q_p = _chi2_sf(q_between, df)
    i2_between = max(0.0, (q_between - df) / q_between) * 100.0 if q_between > 0 else 0.0
    significant = q_p < 0.05

    rows: list[SubgroupRow] = []
    for label, res in rows_tmp:
        est = group_est[label]
        var = group_var[label]
        se = math.sqrt(var)
        ci = (est - z * se, est + z * se)
        disp = (lambda x: math.exp(x)) if log_scale else (lambda x: x)
        rows.append(SubgroupRow(
            label=label,
            k=res.k,
            estimate=est,
            estimate_display=disp(est),
            ci=ci,
            ci_display=(disp(ci[0]), disp(ci[1])),
            i_squared=res.i_squared,
            tau_squared=res.tau_squared,
            weight_percent=100.0 * w[label] / sum_w,
        ))

    rationale = (
        f"Q_between = {q_between:.3f} (df = {df}, p = {q_p:.4f}); "
        + ("the subgroups differ significantly (p < 0.05) — the moderator "
           "explains part of the heterogeneity."
           if significant else
           "no significant subgroup difference (p ≥ 0.05) — the moderator "
           "does not explain the heterogeneity.")
    )
    overall_disp = math.exp(overall) if log_scale else overall
    return SubgroupResult(
        model=model, measure=measure, log_scale=log_scale,
        subgroups=tuple(rows), overall_estimate=overall,
        overall_estimate_display=overall_disp, q_between=q_between,
        q_between_df=df, q_between_p=q_p, i_squared_between=i2_between,
        significant=significant, confidence=confidence, rationale=rationale,
    )


def render_subgroups(result: SubgroupResult) -> str:
    """Markdown for a subgroup analysis."""
    fmt = (lambda x: f"{x:.3f}")
    lines = [
        f"### Subgroup analysis ({result.model} effects)",
        "",
        "| Subgroup | k | Estimate | 95% CI | I² | Weight |",
        "|---|---|---|---|---|---|",
    ]
    for r in result.subgroups:
        lines.append(
            f"| {r.label} | {r.k} | {fmt(r.estimate_display)} | "
            f"[{fmt(r.ci_display[0])}, {fmt(r.ci_display[1])}] | "
            f"{r.i_squared:.0f}% | {r.weight_percent:.1f}% |"
        )
    lines.append("")
    lines.append(
        f"**Test for subgroup differences:** Q = {fmt(result.q_between)} "
        f"(df = {result.q_between_df}, p = {result.q_between_p:.4f}), "
        f"I²_between = {result.i_squared_between:.0f}%"
    )
    lines.append("")
    lines.append(f"_{result.rationale}_")
    return "\n".join(lines)


# ── Trim-and-fill (Duval & Tweedie 2000) ────────────────────────────


@dataclass(frozen=True)
class ImputedStudy:
    """A hypothetical study imputed by trim-and-fill — NOT a cited source."""

    effect: float
    effect_display: float
    variance: float
    note: str = "imputed (trim-and-fill; hypothetical, not a primary source)"

    def to_dict(self) -> dict:
        return {
            "effect": self.effect,
            "effect_display": self.effect_display,
            "variance": self.variance,
            "note": self.note,
        }


@dataclass(frozen=True)
class TrimFillResult:
    """Publication-bias-adjusted estimate via Duval & Tweedie trim-and-fill."""

    model: str
    measure: str
    log_scale: bool
    k_observed: int
    k_imputed: int
    impute_side: str
    observed_estimate: float
    observed_estimate_display: float
    adjusted_estimate: float
    adjusted_estimate_display: float
    adjusted_ci: tuple[float, float]
    adjusted_ci_display: tuple[float, float]
    imputed_studies: tuple[ImputedStudy, ...]
    confidence: float
    rationale: str

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "measure": self.measure,
            "log_scale": self.log_scale,
            "k_observed": self.k_observed,
            "k_imputed": self.k_imputed,
            "impute_side": self.impute_side,
            "observed_estimate": self.observed_estimate,
            "observed_estimate_display": self.observed_estimate_display,
            "adjusted_estimate": self.adjusted_estimate,
            "adjusted_estimate_display": self.adjusted_estimate_display,
            "adjusted_ci": list(self.adjusted_ci),
            "adjusted_ci_display": list(self.adjusted_ci_display),
            "imputed_studies": [s.to_dict() for s in self.imputed_studies],
            "rationale": self.rationale,
        }


def trim_and_fill(
    effects: Sequence[EffectSize] | Iterable[EffectSize],
    *,
    model: str = "random",
    measure: str | None = None,
    confidence: float = 0.95,
    side: str = "auto",
    max_iter: int = 100,
) -> TrimFillResult:
    """Duval & Tweedie (2000) trim-and-fill with the L0 estimator.

    Estimates the number of studies suppressed by publication bias, imputes
    their mirror images, and re-pools for a bias-adjusted estimate. The
    imputed studies are hypothetical and carry no §I identifier — they are a
    sensitivity device, never cited evidence.
    """
    if model not in ("fixed", "random"):
        raise MetaAnalysisError(f"model must be 'fixed' or 'random', got {model!r}")
    if side not in ("auto", "left", "right"):
        raise MetaAnalysisError(f"side must be 'auto', 'left' or 'right', got {side!r}")
    studies = tuple(effects)
    n = len(studies)
    if n < 3:
        raise MetaAnalysisError("trim-and-fill requires at least 3 studies")
    for s in studies:
        if not s.identifier:
            raise MetaAnalysisError(
                f"effect size {s.study_id!r} has no primary-source identifier (§I)"
            )
    if measure is None:
        seen = {s.measure for s in studies}
        measure = seen.pop() if len(seen) == 1 else "generic"
    log_scale = measure in _LOG_SCALE_MEASURES

    ys = [s.yi for s in studies]
    vs = [s.vi for s in studies]
    z = _z_critical(confidence)
    observed_est, _obs_var = _pool_estimate(ys, vs, model)

    # Choose the over-represented side. Work in a sign-flipped frame so the
    # over-represented side is always the right (impute on the left there).
    if side == "auto":
        devs0 = [y - observed_est for y in ys]
        ranks0 = _rankdata([abs(d) for d in devs0])
        sr = math.fsum(
            (1.0 if d > 0 else (-1.0 if d < 0 else 0.0)) * r
            for d, r in zip(devs0, ranks0)
        )
        flip = sr < 0
    else:
        flip = (side == "right")

    work = [-y for y in ys] if flip else list(ys)
    order = sorted(range(n), key=lambda i: work[i])   # ascending by work effect

    k0 = 0
    for _ in range(max_iter):
        keep = order[: n - k0]
        center = _pool_estimate([work[i] for i in keep], [vs[i] for i in keep], model)[0]
        devs = [w - center for w in work]
        ranks = _rankdata([abs(d) for d in devs])
        tn = math.fsum(r for d, r in zip(devs, ranks) if d > 0)
        l0 = (4.0 * tn - n * (n + 1)) / (2.0 * n - 1.0)
        new_k0 = max(0, int(math.floor(l0 + 0.5)))
        if new_k0 >= n:
            new_k0 = n - 1
        if new_k0 == k0:
            break
        k0 = new_k0

    keep = order[: n - k0]
    final_center = _pool_estimate(
        [work[i] for i in keep], [vs[i] for i in keep], model
    )[0]

    largest = order[n - k0:] if k0 > 0 else []
    imputed_work = [(2.0 * final_center - work[i], vs[i]) for i in largest]

    aug_y = work + [iy for iy, _ in imputed_work]
    aug_v = vs + [iv for _, iv in imputed_work]
    adj_work, adj_var = _pool_estimate(aug_y, aug_v, model)
    adjusted = -adj_work if flip else adj_work
    adj_se = math.sqrt(adj_var)
    adjusted_ci = (adjusted - z * adj_se, adjusted + z * adj_se)

    disp = (lambda x: math.exp(x)) if log_scale else (lambda x: x)
    imputed_studies = tuple(
        ImputedStudy(
            effect=(-iy if flip else iy),
            effect_display=disp(-iy if flip else iy),
            variance=iv,
        )
        for iy, iv in imputed_work
    )
    impute_side = "right" if flip else "left"

    if k0 == 0:
        rationale = (
            "Trim-and-fill imputed 0 studies — the funnel is symmetric; the "
            "estimate is unchanged by adjustment for small-study effects."
        )
    else:
        rationale = (
            f"Trim-and-fill imputed {k0} hypothetical "
            f"{'study' if k0 == 1 else 'studies'} on the {impute_side} to "
            f"symmetrise the funnel; the bias-adjusted estimate moves from "
            f"{disp(observed_est):.3f} to {disp(adjusted):.3f}. Imputed "
            "studies are a sensitivity device, not cited evidence."
        )

    return TrimFillResult(
        model=model, measure=measure, log_scale=log_scale,
        k_observed=n, k_imputed=k0, impute_side=impute_side,
        observed_estimate=observed_est,
        observed_estimate_display=disp(observed_est),
        adjusted_estimate=adjusted,
        adjusted_estimate_display=disp(adjusted),
        adjusted_ci=adjusted_ci,
        adjusted_ci_display=(disp(adjusted_ci[0]), disp(adjusted_ci[1])),
        imputed_studies=imputed_studies,
        confidence=confidence, rationale=rationale,
    )


def render_trim_fill(result: TrimFillResult) -> str:
    """Markdown for a trim-and-fill adjustment."""
    fmt = (lambda x: f"{x:.3f}")
    lines = [
        f"### Trim-and-fill ({result.model} effects)",
        "",
        f"- **Observed estimate:** {fmt(result.observed_estimate_display)} "
        f"({result.k_observed} studies)",
        f"- **Imputed (suppressed) studies:** {result.k_imputed} "
        f"on the {result.impute_side}",
        f"- **Bias-adjusted estimate:** {fmt(result.adjusted_estimate_display)} "
        f"[{fmt(result.adjusted_ci_display[0])}, "
        f"{fmt(result.adjusted_ci_display[1])}]",
        "",
        f"_{result.rationale}_",
    ]
    return "\n".join(lines)


# ── stdlib numerics (no NumPy / SciPy — Constitution §X) ─────────────


def _pool_estimate(
    ys: Sequence[float], vs: Sequence[float], model: str
) -> tuple[float, float]:
    """Pool effects → (estimate, variance) under a fixed or DL-random model.

    Lightweight numeric core shared by trim-and-fill and subgroup analysis;
    operates on raw (yi, vi) without constructing :class:`EffectSize` objects
    (the imputed studies have no §I identifier by design).
    """
    weights = [1.0 / v for v in vs]
    sum_w = math.fsum(weights)
    fixed = math.fsum(w * y for w, y in zip(weights, ys)) / sum_w
    if model == "fixed" or len(ys) < 2:
        return fixed, 1.0 / sum_w
    k = len(ys)
    q = math.fsum(w * (y - fixed) ** 2 for w, y in zip(weights, ys))
    df = k - 1
    sum_w2 = math.fsum(w * w for w in weights)
    c_const = sum_w - sum_w2 / sum_w
    tau2 = max(0.0, (q - df) / c_const) if c_const > 0 else 0.0
    re_w = [1.0 / (v + tau2) for v in vs]
    sum_rw = math.fsum(re_w)
    est = math.fsum(w * y for w, y in zip(re_w, ys)) / sum_rw
    return est, 1.0 / sum_rw


def _rankdata(values: Sequence[float]) -> list[float]:
    """Average (fractional) ranks, 1-based — ties share their mean rank."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


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


def _t_critical(confidence: float, df: int) -> float:
    """Two-sided Student's-t critical value for ``confidence`` and ``df``.

    Found by deterministic bisection on the monotone-decreasing survival
    function :func:`_t_sf_two_sided` — no SciPy. Falls back to the normal
    critical value for very large ``df``.
    """
    if not (0.0 < confidence < 1.0):
        raise MetaAnalysisError(f"confidence must be in (0, 1), got {confidence!r}")
    if df <= 0:
        return _z_critical(confidence)
    target = 1.0 - confidence            # two-sided tail mass
    lo, hi = 0.0, 1.0e6
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _t_sf_two_sided(mid, df) > target:
            lo = mid                      # tail too big → need larger t
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return 0.5 * (lo + hi)


def _t_sf_two_sided(t: float, df: int) -> float:
    """Two-sided Student's-t tail probability 2·P(T > |t|) for ``df`` d.o.f.

    Uses the identity P(|T| > t) = I_x(df/2, 1/2) with x = df/(df + t²),
    where I is the regularized incomplete beta. Stdlib ``math`` only.
    """
    if df <= 0:
        return 1.0
    if not math.isfinite(t):
        return 0.0
    x = df / (df + t * t)
    return _betai(df / 2.0, 0.5, x)


def _betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _betacf(a: float, b: float, x: float) -> float:
    """Continued-fraction core of the incomplete beta (modified Lentz)."""
    tiny = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h
