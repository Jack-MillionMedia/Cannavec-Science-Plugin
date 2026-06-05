"""Regulatory-feasibility advisory (spec 002 US6).

Given a research question + jurisdiction (US-federal / EU-EMA /
Canada / UK-MHRA), reports whether the proposed work touches a
controlled substance and what licensing path applies.

**ADVISORY ONLY.** Every output carries the explicit watermark
``This is not legal advice; consult your institutional research-
compliance office.`` The watermark is asserted by
``tests/test_regulatory_feasibility.py`` so it cannot be removed
silently.

Per-state US compliance is OUT OF SCOPE for v0.2 (Constitution
§"Out Of Scope For v0.2"). Per-state law lives in the parent
Cannavec plugin.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


__all__ = [
    "Jurisdiction",
    "Schedule",
    "RegulatoryFeasibilityAdvisory",
    "assess_feasibility",
    "render_markdown",
    "WATERMARK",
]


WATERMARK: str = (
    "**This is not legal advice; consult your institutional "
    "research-compliance office.**"
)


class Jurisdiction(str, Enum):
    US = "us"
    EU = "eu"
    CANADA = "ca"
    UK = "uk"


class Schedule(str, Enum):
    """Schedule classification across jurisdictions."""

    SCHEDULE_I = "schedule_i"          # US DEA Schedule I; CSA equivalent
    SCHEDULE_II = "schedule_ii"        # cannabinoid prescription drugs (Marinol etc.)
    SCHEDULE_III = "schedule_iii"      # Marinol (US — historical class)
    SCHEDULE_IV = "schedule_iv"        # nabilone US
    SCHEDULE_V = "schedule_v"          # Epidiolex US (descheduled 2020)
    DESCHEDULED = "descheduled"
    NOVEL_FOOD = "novel_food"          # EU; Δ⁸ / HHC gray zone
    GRAY_ZONE = "gray_zone"            # legally ambiguous
    UNCONTROLLED = "uncontrolled"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RegulatoryFeasibilityAdvisory:
    """One-jurisdiction × one-compound feasibility advisory."""

    compound: str
    jurisdiction: Jurisdiction
    schedule: Schedule
    licensing_path: str
    estimated_timeline: str = ""
    gray_zone_notes: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    watermark: str = WATERMARK

    def to_dict(self) -> dict:
        d = asdict(self)
        d["jurisdiction"] = self.jurisdiction.value
        d["schedule"] = self.schedule.value
        d["gray_zone_notes"] = list(self.gray_zone_notes)
        d["sources"] = list(self.sources)
        return d


# ── Per-jurisdiction × per-compound matrix ──────────────────────────


# Canonical compound names recognised by the matcher.
_COMPOUND_ALIASES: dict[str, str] = {
    "thc": "Δ⁹-THC",
    "delta-9 thc": "Δ⁹-THC",
    "delta-9-thc": "Δ⁹-THC",
    "δ⁹-thc": "Δ⁹-THC",
    "δ9-thc": "Δ⁹-THC",
    "tetrahydrocannabinol": "Δ⁹-THC",
    "dronabinol": "Δ⁹-THC",
    "marinol": "Δ⁹-THC",
    "delta-8 thc": "Δ⁸-THC",
    "delta-8-thc": "Δ⁸-THC",
    "δ⁸-thc": "Δ⁸-THC",
    "cbd": "CBD",
    "cannabidiol": "CBD",
    "epidiolex": "CBD",
    "hhc": "HHC",
    "thco": "THCO",
    "thcp": "THCP",
    "thca": "THCA",
    "cbn": "CBN",
    "cbg": "CBG",
    "thcv": "THCV",
    "cannabis": "cannabis (whole plant)",
    "marijuana": "cannabis (whole plant)",
}


def _canonicalise(compound: str) -> str:
    q = (compound or "").strip().lower()
    if not q:
        return ""
    if q in _COMPOUND_ALIASES:
        return _COMPOUND_ALIASES[q]
    # Substring match if the user said something like "Δ⁸-THC analgesia"
    for alias, canonical in _COMPOUND_ALIASES.items():
        if alias in q:
            return canonical
    return compound


def _assess_us(compound: str) -> RegulatoryFeasibilityAdvisory:
    """US-federal advisory matrix."""
    c = _canonicalise(compound)
    if c in ("Δ⁹-THC", "THCA", "cannabis (whole plant)"):
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.US,
            schedule=Schedule.SCHEDULE_I,
            licensing_path=(
                "DEA Schedule I Researcher Registration (21 CFR §1301.18). "
                "Steps: (1) IRB approval, (2) DEA Form 225 application, "
                "(3) DEA pre-approval site inspection, (4) NIDA Drug Supply "
                "Program for cannabis material (or DEA-licensed registrant). "
                "FDA IND required for human trials."
            ),
            estimated_timeline="6-18 months for the DEA registration alone",
            sources=(
                "21 USC §812 (Controlled Substances Act)",
                "21 CFR §1301.18 (researcher registration)",
                "21 USC §823(f) (DEA Form 225)",
                "NIDA Drug Supply Program (https://www.drugabuse.gov/drug-supply)",
            ),
        )
    if c == "Δ⁸-THC":
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.US,
            schedule=Schedule.GRAY_ZONE,
            licensing_path=(
                "Federally complicated: hemp-derived Δ⁸-THC sits in the "
                "2018 Farm Bill gray zone; DEA's August 2020 Interim "
                "Final Rule treats 'synthetically derived' "
                "tetrahydrocannabinols as Schedule I. The 9th Circuit "
                "AK Futures decision (May 2022) treated hemp-derived "
                "Δ⁸-THC as legal but is not nationally binding. For "
                "research-grade Δ⁸-THC: assume Schedule I treatment and "
                "follow the DEA Schedule I Researcher Registration path."
            ),
            estimated_timeline="6-18 months; assume Schedule I treatment",
            gray_zone_notes=(
                "9th Cir AK Futures v Boyd St (2022) holds hemp-derived "
                "Δ⁸-THC legal under the 2018 Farm Bill in that circuit only.",
                "DEA 2020 Interim Final Rule still pending finalisation.",
                "State-level law varies materially; coordinate with "
                "institutional compliance.",
            ),
            sources=(
                "21 USC §802(16)(B) (hemp definition)",
                "DEA Interim Final Rule (85 FR 51639, 2020-08-21)",
                "AK Futures LLC v Boyd Street Distro LLC (9th Cir 2022)",
            ),
        )
    if c in ("HHC", "THCO", "THCP"):
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.US,
            schedule=Schedule.GRAY_ZONE,
            licensing_path=(
                "Federal status genuinely ambiguous. Synthetic-conversion-"
                "derived novel cannabinoids likely fall under the Federal "
                "Analog Act (21 USC §813) when intended for human "
                "consumption. Plant-derived material (rare) may fall "
                "under the 2018 Farm Bill hemp definition if Δ⁹-THC < 0.3% "
                "by dry weight. For research-grade material: assume "
                "Schedule I treatment, file DEA Form 225, document source "
                "of starting material rigorously."
            ),
            estimated_timeline="6-18 months; document source chain carefully",
            gray_zone_notes=(
                "Federal Analog Act applies when 'intended for human "
                "consumption'.",
                "DEA letter to AHPA (2023) specifically called out "
                "synthetic-conversion cannabinoids as Schedule I.",
                "Document analytical chemistry of starting material + "
                "synthetic route in protocol.",
            ),
            sources=(
                "21 USC §813 (Federal Analog Act)",
                "21 USC §802(16)(B) (hemp definition)",
                "DEA letter to AHPA (February 2023)",
            ),
        )
    if c == "CBD":
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.US,
            schedule=Schedule.DESCHEDULED,
            licensing_path=(
                "FDA-approved Epidiolex is Schedule V (a single FDA-approved "
                "drug product). Synthetic CBD from non-Epidiolex sources is "
                "unscheduled federally if from hemp (Δ⁹-THC < 0.3%). For "
                "drug research: FDA IND under 21 CFR §312 (no DEA Schedule "
                "I registration required for hemp-derived CBD). For "
                "Epidiolex-formulated CBD: Schedule V researcher "
                "registration."
            ),
            estimated_timeline="3-9 months (IND process; faster if not formulated)",
            sources=(
                "21 CFR §312 (IND application)",
                "DEA notice of descheduling of Epidiolex (April 2020)",
                "2018 Farm Bill, 7 USC §1639o (hemp definition)",
            ),
        )
    return RegulatoryFeasibilityAdvisory(
        compound=c or compound,
        jurisdiction=Jurisdiction.US,
        schedule=Schedule.UNKNOWN,
        licensing_path=(
            "Compound not recognised by the v0.2 advisory matrix. "
            "Coordinate with the DEA Office of Diversion Control "
            "(202-307-1000) and institutional research-compliance."
        ),
        sources=("Cannavec Science v0.2 advisory matrix",),
    )


def _assess_eu(compound: str) -> RegulatoryFeasibilityAdvisory:
    c = _canonicalise(compound)
    if c in ("Δ⁹-THC", "cannabis (whole plant)"):
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.EU,
            schedule=Schedule.SCHEDULE_I,
            licensing_path=(
                "EU has no federal authority; controlled at member-state level "
                "under the 1961 Single Convention on Narcotic Drugs. "
                "Member-state controlled-drug licence required (e.g., German "
                "BfArM §3 BtMG, Dutch Office of Medicinal Cannabis). EMA "
                "Clinical Trial Application via the EU Portal under Regulation "
                "536/2014."
            ),
            estimated_timeline="6-12 months for member-state licence + EMA CTA",
            sources=(
                "Single Convention on Narcotic Drugs (1961)",
                "Regulation (EU) 536/2014 (Clinical Trials Regulation)",
                "German BfArM §3 BtMG (Betäubungsmittelgesetz)",
            ),
        )
    if c in ("Δ⁸-THC", "HHC", "THCO", "THCP"):
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.EU,
            schedule=Schedule.NOVEL_FOOD,
            licensing_path=(
                "EU classifies these as Novel Food per Regulation 2015/2283. "
                "EFSA dossier required for food / supplement sale (EFSA "
                "Novel Food Application). For research use only: EMA CTA "
                "still required when human subjects; member-state controlled-"
                "drug rules apply if scheduled at country level."
            ),
            estimated_timeline="9-24 months (EFSA NF dossier; CTA in parallel)",
            gray_zone_notes=(
                "Hungary, Estonia, Slovenia have explicitly banned HHC "
                "(2023-2024).",
                "France ANSM has classified HHC as a narcotic (June 2023).",
            ),
            sources=(
                "Regulation (EU) 2015/2283 (Novel Food)",
                "EFSA Novel Food Application Process",
                "Member-state controlled-substances rules (variable)",
            ),
        )
    if c == "CBD":
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.EU,
            schedule=Schedule.NOVEL_FOOD,
            licensing_path=(
                "CBD-as-Novel-Food authorisation under Regulation 2015/2283 "
                "is in progress (>200 dossiers pending EFSA review as of "
                "2024). For research use: EMA CTA under Regulation 536/2014; "
                "no controlled-drug licence required when isolated from "
                "EU-certified hemp (Δ⁹-THC < 0.2%). For Epidyolex (EU brand "
                "name): EMA-authorised as orphan drug for Dravet / LGS / TSC."
            ),
            estimated_timeline="3-9 months for CTA",
            sources=(
                "Regulation (EU) 2015/2283 (Novel Food)",
                "EMA Epidyolex EPAR (2019, updated 2021/2022)",
                "Regulation (EU) 536/2014",
            ),
        )
    return RegulatoryFeasibilityAdvisory(
        compound=c or compound,
        jurisdiction=Jurisdiction.EU,
        schedule=Schedule.UNKNOWN,
        licensing_path=(
            "Compound not recognised by the v0.2 advisory matrix. "
            "Coordinate with member-state regulator + EMA."
        ),
        sources=("Cannavec Science v0.2 advisory matrix",),
    )


def _assess_canada(compound: str) -> RegulatoryFeasibilityAdvisory:
    c = _canonicalise(compound)
    if c in ("Δ⁹-THC", "Δ⁸-THC", "THCA", "HHC", "THCO", "THCP",
             "cannabis (whole plant)", "CBD"):
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.CANADA,
            schedule=Schedule.SCHEDULE_II,
            licensing_path=(
                "Health Canada Cannabis Research Licence under the Cannabis "
                "Regulations (SOR/2018-144), Part 5. Alternatively §56 "
                "exemption from the Controlled Drugs and Substances Act "
                "(CDSA) for specific projects. Human clinical trials require "
                "Health Canada Clinical Trial Application (CTA) under "
                "Division 5 of the Food and Drug Regulations."
            ),
            estimated_timeline="2-9 months for research licence; 30-day CTA review",
            sources=(
                "Cannabis Act (SC 2018, c.16)",
                "Cannabis Regulations (SOR/2018-144)",
                "Food and Drug Regulations Part C, Division 5",
                "Controlled Drugs and Substances Act §56 exemption",
            ),
        )
    return RegulatoryFeasibilityAdvisory(
        compound=c or compound,
        jurisdiction=Jurisdiction.CANADA,
        schedule=Schedule.UNKNOWN,
        licensing_path=(
            "Compound not recognised by the v0.2 advisory matrix. "
            "Coordinate with Health Canada Cannabis Section."
        ),
        sources=("Cannavec Science v0.2 advisory matrix",),
    )


def _assess_uk(compound: str) -> RegulatoryFeasibilityAdvisory:
    c = _canonicalise(compound)
    if c in ("Δ⁹-THC", "THCA", "cannabis (whole plant)"):
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.UK,
            schedule=Schedule.SCHEDULE_I,
            licensing_path=(
                "Home Office Controlled Drugs Licence under Schedule 1 of the "
                "Misuse of Drugs Regulations 2001. MHRA Clinical Trial "
                "Authorisation (CTA) for human trials under the Medicines "
                "for Human Use (Clinical Trials) Regulations 2004 — note "
                "the post-Brexit MHRA Combined Review."
            ),
            estimated_timeline="3-6 months for Home Office licence",
            sources=(
                "Misuse of Drugs Act 1971",
                "Misuse of Drugs Regulations 2001 (SI 2001/3998)",
                "Medicines for Human Use (Clinical Trials) Regulations 2004",
            ),
        )
    if c in ("Δ⁸-THC", "HHC", "THCO", "THCP"):
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.UK,
            schedule=Schedule.SCHEDULE_I,
            licensing_path=(
                "UK Home Office classes all isomers of THC as Schedule 1 / "
                "Class B under the Misuse of Drugs Act 1971. Synthetic "
                "Δ⁸ / HHC / THCO / THCP variants fall under the same "
                "Schedule 1 framework. Home Office Controlled Drugs Licence "
                "required for research; MHRA CTA required for clinical "
                "trials."
            ),
            estimated_timeline="3-6 months",
            sources=(
                "Misuse of Drugs Act 1971 (Modification) Order 1977",
                "MHRA controlled-drug licensing guidance",
            ),
        )
    if c == "CBD":
        return RegulatoryFeasibilityAdvisory(
            compound=c,
            jurisdiction=Jurisdiction.UK,
            schedule=Schedule.UNCONTROLLED,
            licensing_path=(
                "CBD is not scheduled under the Misuse of Drugs Act 1971 "
                "(provided Δ⁹-THC content < 0.2%). MHRA CTA required for "
                "clinical trials; no Home Office controlled-drug licence "
                "required for CBD isolate research. Epidyolex is MHRA-"
                "authorised for Dravet / LGS / TSC."
            ),
            estimated_timeline="MHRA CTA review ~60 days",
            sources=(
                "Misuse of Drugs Act 1971",
                "MHRA Epidyolex SmPC (2019, updated)",
            ),
        )
    return RegulatoryFeasibilityAdvisory(
        compound=c or compound,
        jurisdiction=Jurisdiction.UK,
        schedule=Schedule.UNKNOWN,
        licensing_path=(
            "Compound not recognised by the v0.2 advisory matrix. "
            "Coordinate with Home Office Drugs Licensing & Compliance Unit."
        ),
        sources=("Cannavec Science v0.2 advisory matrix",),
    )


# ── Public entry point ──────────────────────────────────────────────


def assess_feasibility(
    compound: str,
    jurisdiction: str | Jurisdiction,
) -> RegulatoryFeasibilityAdvisory:
    """Assess regulatory feasibility for one compound × jurisdiction.

    Returns an honest "unsupported_jurisdiction" advisory if the
    jurisdiction is outside the v0.2 matrix (per the spec edge case).
    """
    if isinstance(jurisdiction, str):
        try:
            jurisdiction = Jurisdiction(jurisdiction.lower().strip())
        except ValueError:
            return RegulatoryFeasibilityAdvisory(
                compound=compound,
                jurisdiction=Jurisdiction.US,  # default placeholder
                schedule=Schedule.UNKNOWN,
                licensing_path=(
                    f"Jurisdiction {jurisdiction!r} not supported by the "
                    f"v0.2 advisory matrix. Supported: US (federal), "
                    f"EU (member-state framework), Canada (Health Canada), "
                    f"UK (Home Office / MHRA). Per-state US compliance "
                    f"and country-by-country EU detail lives in the parent "
                    f"Cannavec plugin."
                ),
                sources=("Cannavec Science v0.2 advisory matrix",),
            )
    if jurisdiction == Jurisdiction.US:
        return _assess_us(compound)
    if jurisdiction == Jurisdiction.EU:
        return _assess_eu(compound)
    if jurisdiction == Jurisdiction.CANADA:
        return _assess_canada(compound)
    if jurisdiction == Jurisdiction.UK:
        return _assess_uk(compound)
    return RegulatoryFeasibilityAdvisory(
        compound=compound,
        jurisdiction=jurisdiction,
        schedule=Schedule.UNKNOWN,
        licensing_path="Jurisdiction recognised but no matrix entry.",
        sources=("Cannavec Science v0.2 advisory matrix",),
    )


# ── Renderer ────────────────────────────────────────────────────────


def render_markdown(advisory: RegulatoryFeasibilityAdvisory) -> str:
    """Render an advisory block — watermark on line 1."""
    lines: list[str] = []
    lines.append(advisory.watermark)
    lines.append("")
    lines.append(
        f"## Regulatory-feasibility advisory — {advisory.compound} "
        f"({advisory.jurisdiction.value.upper()})"
    )
    lines.append("")
    lines.append(f"- **Schedule / classification:** `{advisory.schedule.value}`")
    lines.append(f"- **Licensing path:** {advisory.licensing_path}")
    if advisory.estimated_timeline:
        lines.append(f"- **Estimated timeline:** {advisory.estimated_timeline}")
    if advisory.gray_zone_notes:
        lines.append("- **Gray-zone notes:**")
        for n in advisory.gray_zone_notes:
            lines.append(f"  - {n}")
    if advisory.sources:
        lines.append("- **Primary sources:**")
        for s in advisory.sources:
            lines.append(f"  - {s}")
    return "\n".join(lines)
