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

from dataclasses import dataclass, field
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
        return RegistryInventory(groups=groups)
    if registry not in _BUILDERS:
        raise ValueError(
            f"unknown registry: {registry!r}; expected one of "
            f"{tuple(_BUILDERS)} or 'all'"
        )
    return RegistryInventory(groups=(_BUILDERS[registry](),))


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
