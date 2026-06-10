"""Registry inventory surface (spec 003 US8 / FR-008).

Industry-expert discoverability: a researcher sitting down with Cannavec
Science for the first time wants to know "what's in your registry?"
without grepping the source tree. The :func:`build_inventory` function
walks every curated registry and emits a typed inventory of:

- Cannabinoid registries (major + minor): canonical names + aliases.
- Terpene registry: canonical names + class.
- Interaction registry: distinct partner drugs covered per cannabinoid.
- Adverse event registry: distinct event names per cannabinoid.
- Contraindication registry: distinct (compound, population) pairs.
- Population registry: trial-supported indication labels.
- Pharmacogenomics registry: enzyme × allele rows.
- eCBome registry: mediator / receptor / enzyme / transporter names.

The renderer ships both a Markdown and a JSON view; the CLI surfaces
both via ``python3 -m cannavec_science registries [--format json]``.

Read-only at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable


__all__ = [
    "RegistryInventory",
    "RegistryGroup",
    "all_registry_groups",
    "build_inventory",
    "render_markdown",
    "render_json",
]


@dataclass(frozen=True)
class RegistryGroup:
    """One registry's inventory row."""

    name: str           # canonical name, e.g. "major_cannabinoids"
    label: str          # human-readable, e.g. "Major cannabinoids"
    row_count: int
    entries: tuple[str, ...] = ()
    last_verified: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "row_count": self.row_count,
            "entries": list(self.entries),
            "last_verified": self.last_verified,
        }


@dataclass(frozen=True)
class RegistryInventory:
    """The full read-only inventory of every curated Cannavec registry."""

    groups: tuple[RegistryGroup, ...] = ()

    def to_dict(self) -> dict:
        return {
            "groups": [g.to_dict() for g in self.groups],
        }

    @property
    def total_rows(self) -> int:
        return sum(g.row_count for g in self.groups)


def all_registry_groups() -> tuple[str, ...]:
    """Names of every inventory group, in canonical render order."""
    return (
        "major_cannabinoids",
        "minor_cannabinoids",
        "terpenes",
        "interactions",
        "adverse_events",
        "populations",
        "contraindications",
        "pharmacogenomics",
        "ecbome",
        "analytical_chemistry",
        "cultivation_science",
        # Spec 005 — clinical-pharmacology depth additions.
        "pharmacokinetics",
        "use_disorder",
        "hyperemesis_syndrome",
        "ecbome_inhibitors",
        "biosynthesis",
        # Spec 006 — research-domain-breadth additions.
        "pain_medicine",
        "psychiatry",
        "driving_impairment",
        "ptsd_anxiety_sleep",
        # Spec 026 — cannabis-endocrinology additions.
        "endocrine",
    )


def _latest_last_verified(rows: Iterable[object]) -> str:
    """Return the most-recent ``last_verified`` across rows. Empty if
    no row carries one."""
    latest = ""
    for r in rows:
        lv = getattr(r, "last_verified", "") or ""
        if lv > latest:
            latest = lv
    return latest


# Curation dates for the registries whose row dataclasses predate the per-row
# ``last_verified`` field. Recovered from git — the date each registry was first
# curated and its citations checked (these eight were all authored 2026-05-21,
# the same day as their dated siblings ecbome / analytical_chemistry /
# cultivation_science). Conservative: these facts were verified no LATER than
# this date — never fabricated as "today". Newer registries carry the date on the
# row itself, so this map is the fallback, not the primary source.
_REGISTRY_CURATION_DATE: dict[str, str] = {
    "major_cannabinoids": "2026-05-21",
    "minor_cannabinoids": "2026-05-21",
    "terpenes": "2026-05-21",
    "interactions": "2026-05-21",
    "adverse_events": "2026-05-21",
    "populations": "2026-05-21",
    "contraindications": "2026-05-21",
    "pharmacogenomics": "2026-05-21",
}


def _with_freshness(groups: tuple["RegistryGroup", ...]) -> tuple["RegistryGroup", ...]:
    """Fill an empty ``last_verified`` from the curation-date fallback so every
    registry honestly reports when it was last checked."""
    return tuple(
        replace(g, last_verified=_REGISTRY_CURATION_DATE[g.name])
        if not g.last_verified and g.name in _REGISTRY_CURATION_DATE
        else g
        for g in groups
    )


def _build_major_cannabinoids() -> RegistryGroup:
    from cannavec_science.major_cannabinoids import all_major_cannabinoids
    rows = all_major_cannabinoids()
    entries = tuple(sorted({c.name for c in rows}))
    return RegistryGroup(
        name="major_cannabinoids",
        label="Major cannabinoids",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_minor_cannabinoids() -> RegistryGroup:
    from cannavec_science.minor_cannabinoids import all_minor_cannabinoids
    rows = all_minor_cannabinoids()
    entries = tuple(sorted({c.name for c in rows}))
    return RegistryGroup(
        name="minor_cannabinoids",
        label="Minor cannabinoids",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_terpenes() -> RegistryGroup:
    from cannavec_science.terpenes import all_terpenes
    rows = all_terpenes()
    entries = tuple(sorted({t.name.value for t in rows}))
    return RegistryGroup(
        name="terpenes",
        label="Terpenes",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_interactions() -> RegistryGroup:
    from cannavec_science.interactions import all_interactions
    rows = all_interactions()
    entries = tuple(sorted(
        {f"{r.cannabinoid} × {r.partner_drug}" for r in rows}
    ))
    return RegistryGroup(
        name="interactions",
        label="Drug interactions",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_adverse_events() -> RegistryGroup:
    from cannavec_science.adverse_events import all_adverse_events
    rows = all_adverse_events()
    entries = tuple(sorted(
        {f"{r.cannabinoid} → {r.event}" for r in rows}
    ))
    return RegistryGroup(
        name="adverse_events",
        label="Adverse events",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_populations() -> RegistryGroup:
    from cannavec_science.populations import all_populations
    rows = all_populations()
    entries = tuple(sorted({r.label for r in rows}))
    return RegistryGroup(
        name="populations",
        label="Trial-supported populations",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_contraindications() -> RegistryGroup:
    from cannavec_science.contraindications import all_contraindications
    rows = all_contraindications()
    entries = tuple(sorted(
        {f"{r.compound} × {r.population}" for r in rows}
    ))
    return RegistryGroup(
        name="contraindications",
        label="Contraindications",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_pharmacogenomics() -> RegistryGroup:
    from cannavec_science.pharmacogenomics import all_pgx_records
    rows = all_pgx_records()
    entries = tuple(sorted(
        {f"{r.cannabinoid} × {r.enzyme} {r.allele_or_variant}" for r in rows}
    ))
    return RegistryGroup(
        name="pharmacogenomics",
        label="Pharmacogenomics",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_ecbome() -> RegistryGroup:
    from cannavec_science.ecbome import all_ecbome_entries
    rows = all_ecbome_entries()
    entries = tuple(sorted({f"{e.name} ({e.role.value})" for e in rows}))
    return RegistryGroup(
        name="ecbome",
        label="Endocannabinoidome (eCBome)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_analytical_chemistry() -> RegistryGroup:
    from cannavec_science.analytical_chemistry import (
        all_analytical_chemistry_rows,
    )
    rows = all_analytical_chemistry_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="analytical_chemistry",
        label="Analytical chemistry (v0.4)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_cultivation_science() -> RegistryGroup:
    from cannavec_science.cultivation_science import (
        all_cultivation_science_rows,
    )
    rows = all_cultivation_science_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="cultivation_science",
        label="Cultivation science (v0.4)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_pharmacokinetics() -> RegistryGroup:
    from cannavec_science.pharmacokinetics import (
        all_pharmacokinetics_rows,
    )
    rows = all_pharmacokinetics_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="pharmacokinetics",
        label="Clinical pharmacokinetics (v0.5)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_use_disorder() -> RegistryGroup:
    from cannavec_science.use_disorder import all_use_disorder_rows
    rows = all_use_disorder_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="use_disorder",
        label="Cannabis use disorder & withdrawal (v0.5)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_hyperemesis_syndrome() -> RegistryGroup:
    from cannavec_science.hyperemesis_syndrome import (
        all_hyperemesis_syndrome_rows,
    )
    rows = all_hyperemesis_syndrome_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="hyperemesis_syndrome",
        label="Cannabinoid hyperemesis syndrome (v0.5)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_ecbome_inhibitors() -> RegistryGroup:
    from cannavec_science.ecbome_inhibitors import (
        all_ecbome_inhibitor_rows,
    )
    rows = all_ecbome_inhibitor_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="ecbome_inhibitors",
        label="eCBome inhibitor pharmacology (v0.5)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_biosynthesis() -> RegistryGroup:
    from cannavec_science.biosynthesis import all_biosynthesis_rows
    rows = all_biosynthesis_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="biosynthesis",
        label="Cannabinoid biosynthesis pathway (v0.5)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_pain_medicine() -> RegistryGroup:
    from cannavec_science.pain_medicine import all_pain_medicine_rows
    rows = all_pain_medicine_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="pain_medicine",
        label="Pain medicine (v0.6)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_psychiatry() -> RegistryGroup:
    from cannavec_science.psychiatry import all_psychiatry_rows
    rows = all_psychiatry_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="psychiatry",
        label="Psychiatry / cannabis-psychosis (v0.6)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_driving_impairment() -> RegistryGroup:
    from cannavec_science.driving_impairment import (
        all_driving_impairment_rows,
    )
    rows = all_driving_impairment_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="driving_impairment",
        label="Cannabis driving-impairment science (v0.6)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_ptsd_anxiety_sleep() -> RegistryGroup:
    from cannavec_science.ptsd_anxiety_sleep import (
        all_ptsd_anxiety_sleep_rows,
    )
    rows = all_ptsd_anxiety_sleep_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="ptsd_anxiety_sleep",
        label="PTSD / anxiety / sleep (v0.6)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


def _build_endocrine() -> RegistryGroup:
    from cannavec_science.endocrine import all_endocrine_rows
    rows = all_endocrine_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="endocrine",
        label="Cannabis endocrinology — metabolic/reproductive/HP-axes (v0.7)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )


_BUILDERS = {
    "major_cannabinoids": _build_major_cannabinoids,
    "minor_cannabinoids": _build_minor_cannabinoids,
    "terpenes": _build_terpenes,
    "interactions": _build_interactions,
    "adverse_events": _build_adverse_events,
    "populations": _build_populations,
    "contraindications": _build_contraindications,
    "pharmacogenomics": _build_pharmacogenomics,
    "ecbome": _build_ecbome,
    "analytical_chemistry": _build_analytical_chemistry,
    "cultivation_science": _build_cultivation_science,
    # Spec 005 — clinical-pharmacology depth additions.
    "pharmacokinetics": _build_pharmacokinetics,
    "use_disorder": _build_use_disorder,
    "hyperemesis_syndrome": _build_hyperemesis_syndrome,
    "ecbome_inhibitors": _build_ecbome_inhibitors,
    "biosynthesis": _build_biosynthesis,
    # Spec 006 — research-domain-breadth additions.
    "pain_medicine": _build_pain_medicine,
    "psychiatry": _build_psychiatry,
    "driving_impairment": _build_driving_impairment,
    "ptsd_anxiety_sleep": _build_ptsd_anxiety_sleep,
    "endocrine": _build_endocrine,
}


def build_inventory(
    registry: str = "all",
) -> RegistryInventory:
    """Return a :class:`RegistryInventory` for the named registry.

    ``registry="all"`` (default) walks every group in canonical order.
    A specific name returns a single-group inventory. Unknown names
    raise ``ValueError``.
    """
    if registry == "all":
        groups = tuple(b() for b in (_BUILDERS[n] for n in all_registry_groups()))
        return RegistryInventory(groups=_with_freshness(groups))
    if registry not in _BUILDERS:
        raise ValueError(
            f"unknown registry: {registry!r}; expected one of "
            f"{tuple(_BUILDERS)} or 'all'"
        )
    return RegistryInventory(groups=_with_freshness((_BUILDERS[registry](),)))


def render_markdown(inv: RegistryInventory) -> str:
    """Markdown render of the inventory."""
    if not inv.groups:
        return "_No registries to inventory._"
    lines: list[str] = []
    lines.append("## Cannavec Science — registry inventory")
    lines.append("")
    lines.append(
        f"**{inv.total_rows}** rows across **{len(inv.groups)}** "
        f"curated registries."
    )
    lines.append("")
    for g in inv.groups:
        suffix = (
            f" — last verified {g.last_verified}" if g.last_verified else ""
        )
        lines.append(f"### {g.label} ({g.row_count} rows{suffix})")
        lines.append("")
        if not g.entries:
            lines.append("- _(no entries)_")
        else:
            for e in g.entries:
                lines.append(f"- {e}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_json(inv: RegistryInventory) -> str:
    import json
    return json.dumps(inv.to_dict(), indent=2, default=str)
