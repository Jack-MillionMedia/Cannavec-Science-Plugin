"""Pharmacovigilance disproportionality analysis (spec 023).

Signal-detection measures for a drug-event pair in a spontaneous-reporting
database (FAERS, VigiBase, EudraVigilance): the Proportional Reporting Ratio
(PRR; Evans 2001, Pharmacoepidemiol Drug Saf 10:483) and the Reporting Odds
Ratio (ROR; Rothman 2004, Pharmacoepidemiol Drug Saf 13:519), with the
MHRA/Evans signal criterion (PRR ≥ 2, χ² ≥ 4, a ≥ 3).

These are *hypothesis-generating* disproportionality measures, not measures of
risk or causation — a spontaneous-reporting signal is the start of an
investigation, not its conclusion. The tool says so. Deterministic and
stdlib-only (§X): a continuity correction handles zero cells; the χ² uses Yates'
correction on the raw counts.

The 2×2 is reports cross-classified by (this drug? this event?):

                 event E      other events
    drug D          a              b
    other drugs     c              d
"""

from __future__ import annotations

import math
from dataclasses import dataclass


__all__ = [
    "DisproportionalityError",
    "DisproportionalityResult",
    "disproportionality",
    "render_disproportionality",
]


class DisproportionalityError(ValueError):
    """Raised on a malformed 2×2 report table."""


@dataclass(frozen=True)
class DisproportionalityResult:
    """PRR / ROR disproportionality for one drug-event pair."""

    a: int
    b: int
    c: int
    d: int
    corrected: bool          # 0.5 continuity correction applied?
    prr: float
    prr_ci: tuple[float, float]
    ror: float
    ror_ci: tuple[float, float]
    chi_squared: float       # Yates-corrected, on raw counts
    signal: bool
    criterion: str
    rationale: str

    def to_dict(self) -> dict:
        return {
            "table": {"a": self.a, "b": self.b, "c": self.c, "d": self.d},
            "continuity_corrected": self.corrected,
            "prr": self.prr,
            "prr_ci": list(self.prr_ci),
            "ror": self.ror,
            "ror_ci": list(self.ror_ci),
            "chi_squared_yates": self.chi_squared,
            "signal": self.signal,
            "criterion": self.criterion,
            "rationale": self.rationale,
        }


def disproportionality(
    drug_event: int,
    drug_other: int,
    other_event: int,
    other_other: int,
    *,
    signal_prr: float = 2.0,
    signal_chi2: float = 4.0,
    signal_min_a: int = 3,
    confidence: float = 0.95,
) -> DisproportionalityResult:
    """PRR + ROR signal detection for a drug-event pair.

    The four cells are report counts: ``drug_event`` (a), ``drug_other`` (b),
    ``other_event`` (c), ``other_other`` (d). The MHRA/Evans signal fires when
    PRR ≥ ``signal_prr``, χ² ≥ ``signal_chi2`` (Yates), and a ≥ ``signal_min_a``.
    A 0.5 continuity correction is applied to the ratios and CIs when any cell
    is zero; the χ² and the a-count gate use the raw counts.
    """
    cells = {"drug_event": drug_event, "drug_other": drug_other,
             "other_event": other_event, "other_other": other_other}
    for name, v in cells.items():
        if not isinstance(v, int) or v < 0:
            raise DisproportionalityError(f"{name} must be a non-negative integer; got {v!r}")
    a0, b0, c0, d0 = drug_event, drug_other, other_event, other_other
    if (a0 + b0) == 0 or (c0 + d0) == 0 or (a0 + c0) == 0 or (b0 + d0) == 0:
        raise DisproportionalityError(
            "every margin must be > 0 (need reports on the drug, off the drug, "
            "of the event, and of other events)"
        )

    corrected = 0 in (a0, b0, c0, d0)
    a, b, c, d = (float(a0), float(b0), float(c0), float(d0))
    if corrected:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5

    z = _z_for(confidence)
    prr = (a / (a + b)) / (c / (c + d))
    se_prr = math.sqrt(1.0 / a - 1.0 / (a + b) + 1.0 / c - 1.0 / (c + d))
    prr_ci = (math.exp(math.log(prr) - z * se_prr),
              math.exp(math.log(prr) + z * se_prr))

    ror = (a * d) / (b * c)
    se_ror = math.sqrt(1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d)
    ror_ci = (math.exp(math.log(ror) - z * se_ror),
              math.exp(math.log(ror) + z * se_ror))

    # Yates χ² on the raw 2×2.
    n = a0 + b0 + c0 + d0
    r1, r2 = a0 + b0, c0 + d0
    k1, k2 = a0 + c0, b0 + d0
    chi = (n * max(0.0, abs(a0 * d0 - b0 * c0) - n / 2.0) ** 2
           / (r1 * r2 * k1 * k2))

    signal = (prr >= signal_prr and chi >= signal_chi2 and a0 >= signal_min_a)
    criterion = (f"PRR ≥ {signal_prr:g} and χ² ≥ {signal_chi2:g} and a ≥ "
                 f"{signal_min_a} (Evans 2001 / MHRA)")
    verdict = "a disproportionality signal" if signal else "no signal"
    fails = []
    if prr < signal_prr:
        fails.append(f"PRR {prr:.2f} < {signal_prr:g}")
    if chi < signal_chi2:
        fails.append(f"χ² {chi:.2f} < {signal_chi2:g}")
    if a0 < signal_min_a:
        fails.append(f"a = {a0} < {signal_min_a}")
    rationale = (
        f"PRR {prr:.2f} ({int(confidence*100)}% CI {prr_ci[0]:.2f}-{prr_ci[1]:.2f}), "
        f"ROR {ror:.2f} ({ror_ci[0]:.2f}-{ror_ci[1]:.2f}), χ² {chi:.2f} → {verdict}"
        + (f" ({'; '.join(fails)})" if fails else "")
        + ". Disproportionality is hypothesis-generating from spontaneous "
        "reports — it is not an incidence, a risk, or evidence of causation; "
        "confounding by indication and reporting bias are unadjusted."
        + (" (0.5 continuity correction applied for a zero cell.)"
           if corrected else "")
    )
    return DisproportionalityResult(
        a=a0, b=b0, c=c0, d=d0, corrected=corrected,
        prr=prr, prr_ci=prr_ci, ror=ror, ror_ci=ror_ci,
        chi_squared=chi, signal=signal, criterion=criterion, rationale=rationale,
    )


def render_disproportionality(result: DisproportionalityResult) -> str:
    """Markdown for a disproportionality result."""
    return "\n".join([
        "## Pharmacovigilance disproportionality",
        "",
        f"- **2×2 (drug×event):** a={result.a}, b={result.b}, "
        f"c={result.c}, d={result.d}",
        f"- **PRR:** {result.prr:.2f} "
        f"(95% CI {result.prr_ci[0]:.2f} to {result.prr_ci[1]:.2f})",
        f"- **ROR:** {result.ror:.2f} "
        f"(95% CI {result.ror_ci[0]:.2f} to {result.ror_ci[1]:.2f})",
        f"- **χ² (Yates):** {result.chi_squared:.2f}",
        f"- **Signal ({result.criterion}):** "
        f"{'YES' if result.signal else 'no'}",
        "",
        f"_{result.rationale}_",
    ])


def _z_for(confidence: float) -> float:
    """Two-sided normal quantile for a CI (reuses the meta-analysis helper)."""
    from cannavec_science.meta_analysis import _z_critical
    return _z_critical(confidence)
