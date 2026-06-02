"""Receptor-binding affinity conversions (spec 024).

The pharmacologist's everyday problem: an ``IC50`` is assay-dependent — it shifts
with the radioligand concentration and the radioligand's own Kd — so two papers'
raw IC50 values for the same cannabinoid at CB1 are **not comparable**. The
Cheng-Prusoff equation (Cheng & Prusoff 1973, Biochem Pharmacol 22:3099)
converts an IC50 to ``Ki``, the assay-independent inhibition constant, so
affinities from different papers can finally be put on one axis:

    Ki = IC50 / (1 + [L]/Kd)          (competitive radioligand binding)
    Ki = IC50 / (1 + [S]/Km)          (competitive enzyme inhibition)

It also reports the medicinal-chemistry log scale (pKi = −log10 Ki in molar),
on which a one-unit gain is a tenfold-tighter binder. Deterministic and
stdlib-only (§X): exact arithmetic and ``math.log10``; no numeric libraries.
This is in-vitro binding pharmacology — never a dose, a regimen, or
individualized advice (§V).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


__all__ = [
    "BindingError",
    "BindingResult",
    "cheng_prusoff",
    "p_affinity",
    "affinity_from_p",
    "binding_affinity",
    "render_binding",
]


# Concentration unit → molar.
_UNIT_TO_M = {
    "M": 1.0, "mM": 1e-3, "uM": 1e-6, "µM": 1e-6, "nM": 1e-9, "pM": 1e-12,
}


class BindingError(ValueError):
    """Raised on an invalid affinity input."""


def cheng_prusoff(ic50: float, ligand_conc: float, kd: float) -> float:
    """Ki from IC50 via Cheng-Prusoff. ``Ki = IC50 / (1 + ligand_conc/kd)``.

    For competitive radioligand binding ``ligand_conc`` is the radioligand
    concentration [L] and ``kd`` its dissociation constant; for competitive
    enzyme inhibition they are the substrate concentration [S] and Km. Inputs
    must share one unit; Ki is returned in that unit.
    """
    if ic50 <= 0:
        raise BindingError(f"IC50 must be > 0; got {ic50}")
    if kd <= 0:
        raise BindingError(f"Kd/Km must be > 0; got {kd}")
    if ligand_conc < 0:
        raise BindingError(f"ligand/substrate concentration must be ≥ 0; got {ligand_conc}")
    return ic50 / (1.0 + ligand_conc / kd)


def p_affinity(value: float, unit: str = "nM") -> float:
    """The p-scale affinity ``−log10(value in molar)`` (pKi / pIC50)."""
    if unit not in _UNIT_TO_M:
        raise BindingError(
            f"unknown unit {unit!r}; use one of {sorted(_UNIT_TO_M)}")
    if value <= 0:
        raise BindingError(f"value must be > 0 for a p-scale; got {value}")
    return -math.log10(value * _UNIT_TO_M[unit])


def affinity_from_p(p: float, unit: str = "nM") -> float:
    """Inverse of :func:`p_affinity` — a p-value back to a concentration."""
    if unit not in _UNIT_TO_M:
        raise BindingError(
            f"unknown unit {unit!r}; use one of {sorted(_UNIT_TO_M)}")
    return (10.0 ** (-p)) / _UNIT_TO_M[unit]


@dataclass(frozen=True)
class BindingResult:
    """A Cheng-Prusoff IC50→Ki conversion with the log-scale affinities."""

    ic50: float
    ligand_conc: float
    kd: float
    unit: str
    mode: str
    ki: float
    correction_factor: float     # 1 + [L]/Kd
    p_ic50: float
    p_ki: float
    rationale: str

    def to_dict(self) -> dict:
        return {
            "ic50": self.ic50,
            "ligand_conc": self.ligand_conc,
            "kd": self.kd,
            "unit": self.unit,
            "mode": self.mode,
            "ki": self.ki,
            "correction_factor": self.correction_factor,
            "p_ic50": self.p_ic50,
            "p_ki": self.p_ki,
            "rationale": self.rationale,
        }


def binding_affinity(
    ic50: float, ligand_conc: float, kd: float, *,
    unit: str = "nM", mode: str = "radioligand",
) -> BindingResult:
    """Convert an IC50 to Ki + pKi (Cheng-Prusoff). See module docstring."""
    if unit not in _UNIT_TO_M:
        raise BindingError(
            f"unknown unit {unit!r}; use one of {sorted(_UNIT_TO_M)}")
    mode = mode.lower()
    if mode not in ("radioligand", "enzyme"):
        raise BindingError(f"mode must be 'radioligand' or 'enzyme'; got {mode!r}")

    ki = cheng_prusoff(ic50, ligand_conc, kd)
    correction = 1.0 + ligand_conc / kd
    p_ic50 = p_affinity(ic50, unit)
    p_ki = p_affinity(ki, unit)
    comp = ("[L]/Kd" if mode == "radioligand" else "[S]/Km")
    rationale = (
        f"Cheng-Prusoff ({mode}): Ki = IC50 / (1 + {comp}) = {ic50:g} / "
        f"{correction:.3g} = {ki:.4g} {unit} (pKi {p_ki:.2f}). The IC50 of "
        f"{ic50:g} {unit} (pIC50 {p_ic50:.2f}) is assay-specific; the Ki is "
        "the assay-independent affinity to compare across papers. A "
        f"correction factor of {correction:.2f} means the raw IC50 overstates "
        "binding affinity by that multiple under these assay conditions."
    )
    return BindingResult(
        ic50=ic50, ligand_conc=ligand_conc, kd=kd, unit=unit, mode=mode,
        ki=ki, correction_factor=correction, p_ic50=p_ic50, p_ki=p_ki,
        rationale=rationale,
    )


def render_binding(result: BindingResult) -> str:
    """Markdown for a binding-affinity conversion."""
    sub = "[L]" if result.mode == "radioligand" else "[S]"
    kd_lbl = "Kd" if result.mode == "radioligand" else "Km"
    return "\n".join([
        "## Binding affinity — Cheng-Prusoff IC50 → Ki",
        "",
        f"- **IC50:** {result.ic50:g} {result.unit} "
        f"(pIC50 {result.p_ic50:.2f}) — assay-dependent",
        f"- **{sub} / {kd_lbl}:** {result.ligand_conc:g} / {result.kd:g} "
        f"{result.unit}  →  correction 1 + {sub}/{kd_lbl} = "
        f"{result.correction_factor:.2f}",
        f"- **Ki:** {result.ki:.4g} {result.unit} "
        f"(**pKi {result.p_ki:.2f}**) — assay-independent",
        "",
        f"_{result.rationale}_",
    ])
