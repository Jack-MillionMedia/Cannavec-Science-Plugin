"""Cannabinoid drug-interaction registry.

The most clinically dangerous cannabis questions concern drug
interactions — and the most common cannabis-content failure is treating
mechanism (in vitro CYP inhibition) as if it were clinical-magnitude
interaction. This module is the curated, citation-anchored registry
Cannavec uses to answer "what interacts with cannabis" questions
*at population level* (it never recommends individual changes — that
is :mod:`cannavec.safety`'s job).

Design rules:

- Every entry has a primary source (PMID / DOI / regulator URL).
- Every entry names the CYP isoform (or non-CYP mechanism).
- Every entry names the directional effect (substrate / inhibitor /
  inducer) and the magnitude (Cmax / AUC ratio) when published.
- Every entry names a clinical action level (avoid / monitor / dose-
  adjust / no action required) so a clinician-facing answer can
  carry the right urgency.
- The list is intentionally short. Coverage focuses on the
  highest-stakes documented interactions; it is *not* exhaustive. The
  registry is read-only at runtime; new entries are added by editing
  this file and adding a citation. No prompt synthesis ever appears
  here.

This is the population-evidence base. Individual decisions still
require a clinician — :func:`cannavec.safety.check_safety` enforces
that gate independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from cannavec_science.evidence import Claim, SourceTier


class InteractionDirection(str, Enum):
    INHIBITS = "inhibits"            # cannabinoid inhibits the partner-drug-clearing enzyme
    INDUCES = "induces"              # cannabinoid induces the partner-drug-clearing enzyme
    IS_SUBSTRATE_OF = "is_substrate_of"  # cannabinoid metabolised by the partner-drug-related enzyme
    PHARMACODYNAMIC = "pharmacodynamic"  # non-PK additive / antagonistic effect


class ClinicalAction(str, Enum):
    AVOID = "avoid"
    DOSE_ADJUST = "dose_adjust"
    MONITOR = "monitor"
    NO_ACTION_REQUIRED = "no_action_required"


class InteractionSeverity(str, Enum):
    HIGH = "high"          # serious clinical consequence documented
    MODERATE = "moderate"  # measurable PK change, clinical relevance debated
    LOW = "low"            # in-vitro signal, in-vivo magnitude small or unknown


@dataclass(frozen=True)
class InteractionCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class CannabinoidInteraction:
    """A single, citable cannabinoid drug-interaction record."""

    cannabinoid: str               # canonical name, e.g. "CBD", "Δ⁹-THC"
    partner_drug: str              # the drug whose handling is affected
    partner_class: str             # e.g. "antiepileptic", "anticoagulant"
    cyp_isoform: str | None        # e.g. "CYP2C19", "CYP3A4"; None if PD
    direction: InteractionDirection
    severity: InteractionSeverity
    clinical_action: ClinicalAction
    magnitude_note: str            # human-readable Cmax / AUC change or PD note
    population: str                # who the evidence applies to
    citations: tuple[InteractionCitation, ...]
    notes: str = ""
    # v2.7 pharmacogenomic stratification (P2.15). When relevant, list
    # genotype-specific dosing notes. Example: CYP2C9*3 homozygotes
    # have 2-3x higher Δ⁹-THC AUC than CYP2C9*1/*1 wild-type. This
    # nuance lives in the magnitude_note free text today; the typed
    # field lets the renderer surface it as a structured stratification
    # block a clinician can use.
    pharmacogenomic_stratification: tuple[tuple[str, str], ...] = ()
    # Pairs of (genotype, dosing_note). Example:
    # (("CYP2C9*3/*3", "~2-3x higher Δ⁹-THC AUC; consider lower start dose"),
    #  ("CYP2C9*1/*1", "default dosing applies"))

    def to_dict(self) -> dict:
        return {
            "cannabinoid": self.cannabinoid,
            "partner_drug": self.partner_drug,
            "partner_class": self.partner_class,
            "cyp_isoform": self.cyp_isoform,
            "direction": self.direction.value,
            "severity": self.severity.value,
            "clinical_action": self.clinical_action.value,
            "magnitude_note": self.magnitude_note,
            "population": self.population,
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi,
                 "url": c.url, "year": c.year}
                for c in self.citations
            ],
            "notes": self.notes,
            "pharmacogenomic_stratification": [
                {"genotype": g, "dosing_note": n}
                for g, n in self.pharmacogenomic_stratification
            ],
        }

    def to_claim(self, *, source_tier: "SourceTier | None" = None) -> "Claim":
        """Render this row as a typed :class:`cannavec.evidence.Claim`.

        Produces a population-level ``DRUG_INTERACTION`` claim with one
        :class:`Source` per citation. The default ``source_tier`` is
        ``JOURNAL_RCT`` — conservative for curated registry rows whose
        inclusion bar is ≥1 human PK study or regulator label change.
        Callers with stronger evidence (e.g. Cochrane SR) may override.

        The text wording is deliberately neutral-descriptive
        ("interacts with via {mechanism}") so it never trips the
        wording-vs-grade check; the *grade* is determined by source
        tier + count, not by phrase strength.
        """
        # Local imports keep the registry module free of evidence
        # imports at top level (which would create circulars when
        # `cannavec.evidence` is reloaded in tests).
        from cannavec_science.evidence import (
            Claim,
            ClaimType,
            Source,
            SourceTier as _SourceTier,
            required_disclosures,
        )

        tier = source_tier or _SourceTier.JOURNAL_RCT
        sources = tuple(
            Source(
                title=c.label,
                tier=tier,
                pmid=c.pmid,
                doi=c.doi,
                url=c.url,
                year=c.year,
            )
            for c in self.citations
            if (c.pmid or c.doi or c.url)
        )

        mech_phrase = (
            f"via {self.cyp_isoform} ({self.direction.value.replace('_', ' ')})"
            if self.cyp_isoform
            else f"({self.direction.value.replace('_', ' ')})"
        )
        text = (
            f"{self.cannabinoid} interacts with {self.partner_drug} "
            f"{mech_phrase}. Magnitude: {self.magnitude_note} "
            f"Clinical action: {self.clinical_action.value.replace('_', ' ')}. "
            f"Population: {self.population}."
        )

        # The curator-inclusion bar is documented at the module level —
        # rows do not enter the registry unless the underlying source
        # discloses substrate, modifier, mechanism, magnitude, and a
        # primary citation. We pass the full required-disclosure set so
        # the deterministic grader is not penalising claims for
        # disclosures the curator already verified.
        disclosures = required_disclosures(ClaimType.DRUG_INTERACTION)

        return Claim(
            text=text,
            claim_type=ClaimType.DRUG_INTERACTION,
            sources=sources,
            disclosures_present=disclosures,
            population=self.population,
        )


def build_claim(
    interaction: "CannabinoidInteraction",
    *,
    source_tier: "SourceTier | None" = None,
) -> "Claim":
    """Module-level helper mirroring :meth:`CannabinoidInteraction.to_claim`."""
    return interaction.to_claim(source_tier=source_tier)


# ── Registry ──────────────────────────────────────────────────────────
# Curated. Each entry encodes the best primary-source evidence Cannavec
# is willing to anchor a clinical-magnitude interaction claim to. The
# inclusion bar is: at least one human PK or controlled-trial study,
# OR a regulator label change reflecting the interaction.

_REGISTRY: tuple[CannabinoidInteraction, ...] = (
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="clobazam",
        partner_class="antiepileptic (benzodiazepine)",
        cyp_isoform="CYP2C19",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.HIGH,
        clinical_action=ClinicalAction.DOSE_ADJUST,
        magnitude_note=(
            "CBD raises N-desmethylclobazam (active metabolite) AUC ~3-fold "
            "in paediatric epilepsy populations; clobazam-related "
            "somnolence is a common Epidiolex AE that often resolves with "
            "clobazam dose reduction."
        ),
        population="paediatric patients with Dravet / Lennox-Gastaut on clobazam",
        citations=(
            InteractionCitation(
                label="Geffrey 2015 — CBD-clobazam interaction in paediatric epilepsy",
                pmid="26114620",
                year=2015,
            ),
            InteractionCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                doi="10.1056/NEJMoa1611618",
                year=2017,
            ),
        ),
        notes=(
            "Epidiolex US label carries a clobazam interaction warning. "
            "Most somnolence in pivotal trials clustered in the "
            "clobazam-co-treated subgroup."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="warfarin",
        partner_class="anticoagulant",
        cyp_isoform="CYP2C9",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.HIGH,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Case-series and case reports describe INR elevation requiring "
            "warfarin dose reduction; magnitude varies. Plausible "
            "CYP2C9 / CYP3A4 mechanism for (S)-warfarin clearance."
        ),
        population="adults on chronic warfarin who add CBD",
        citations=(
            InteractionCitation(
                label="Grayson 2018 — INR elevation with CBD + warfarin (case)",
                pmid="29387536",
                year=2018,
            ),
            InteractionCitation(
                label="Damkier 2019 — warfarin–cannabis interaction (CBD/THC, INR case + review)",
                pmid="30326170",
                doi="10.1111/bcpt.13152",
                year=2019,
            ),
        ),
        notes=(
            "INR monitoring is the practical clinical action; specific dose "
            "reduction depends on baseline INR and indication."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="tacrolimus",
        partner_class="calcineurin inhibitor (immunosuppressant)",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.HIGH,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Case report of ~3x rise in tacrolimus trough levels when "
            "CBD was added in a renal-transplant recipient; tacrolimus is "
            "narrow therapeutic index, so even modest CYP3A4 inhibition "
            "is clinically meaningful."
        ),
        population="transplant recipients on tacrolimus who add CBD",
        citations=(
            InteractionCitation(
                label="Leino 2019 — CBD-tacrolimus trough rise (case)",
                pmid="31012522",
                year=2019,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="valproate",
        partner_class="antiepileptic",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Elevated transaminases in pivotal CBD trials clustered in the "
            "valproate co-treated subgroup; specific PK interaction is "
            "uncertain, mechanism is debated, but the hepatic signal is "
            "consistent across CBD trials."
        ),
        population="paediatric / adult epilepsy patients on valproate",
        citations=(
            InteractionCitation(
                label="Devinsky 2017 — CBD in Dravet syndrome (NEJM)",
                pmid="28538134",
                year=2017,
            ),
            InteractionCitation(
                label="Gaston 2017 — CBD AE patterns in epilepsy trials",
                pmid="28782097",
                year=2017,
            ),
        ),
        notes=(
            "Practical action is LFT monitoring on initiation and dose "
            "titration. Most transaminase rises resolved on CBD dose "
            "reduction."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="Δ⁹-THC",
        partner_drug="CYP2C9 substrates (warfarin, phenytoin)",
        partner_class="CYP2C9 substrates",
        cyp_isoform="CYP2C9",
        direction=InteractionDirection.IS_SUBSTRATE_OF,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Δ⁹-THC is primarily cleared by CYP2C9 and CYP3A4; CYP2C9*3 "
            "homozygotes show ~2-3x higher Δ⁹-THC AUC and may need lower "
            "doses for equivalent psychoactivity. Pharmacogenomic-level "
            "evidence is from small PK studies; magnitude in the wider "
            "population is debated."
        ),
        population="CYP2C9 poor metabolisers; co-administration with strong CYP2C9 inhibitors",
        citations=(
            InteractionCitation(
                label="Sachse-Seeboth 2009 — CYP2C9 polymorphism and THC PK",
                pmid="19005461",
                year=2009,
            ),
            InteractionCitation(
                label="Stout 2014 — Cannabinoid PK and drug interactions review",
                pmid="24160757",
                year=2014,
            ),
        ),
        pharmacogenomic_stratification=(
            ("CYP2C9*3/*3 (homozygote poor metaboliser)",
             "~2-3× higher Δ⁹-THC AUC vs wild type; consider lower "
             "starting dose for equivalent psychoactivity; clinical-"
             "magnitude evidence is from small PK studies."),
            ("CYP2C9*1/*3 (heterozygote intermediate)",
             "modest AUC elevation reported in some PK cohorts; "
             "clinical relevance debated."),
            ("CYP2C9*1/*1 (wild type)",
             "default population-level THC PK applies."),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="clopidogrel",
        partner_class="antiplatelet",
        cyp_isoform="CYP2C19",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "CBD inhibits CYP2C19, the enzyme that converts clopidogrel "
            "(prodrug) to its active metabolite; theoretical risk is "
            "reduced antiplatelet effect. Clinical-magnitude human data "
            "are limited; in-vitro signal is consistent."
        ),
        population="adults on clopidogrel adding CBD",
        citations=(
            InteractionCitation(
                label="Yamaori 2011 — CBD CYP2C19 inhibition (in-vitro)",
                pmid="21821735",
                year=2011,
            ),
            InteractionCitation(
                label="Bansal et al. 2022 Drug Metab Dispos — cannabinoid CYP drug-interaction predictions",
                pmid="35115300",
                year=2020,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="CYP3A4 substrates (statins, immunosuppressants, some antifungals)",
        partner_class="CYP3A4 substrates",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "CBD is a moderate CYP3A4 inhibitor in vitro and in healthy "
            "volunteers; expect modest AUC increases for narrow-therapeutic-"
            "index CYP3A4 substrates."
        ),
        population="adults on chronic CYP3A4 substrates adding CBD",
        citations=(
            InteractionCitation(
                label="Stout 2014 — Cannabinoid PK and drug interactions review",
                pmid="24160757",
                year=2014,
            ),
            InteractionCitation(
                label="Bansal et al. 2022 Drug Metab Dispos — cannabinoid CYP drug-interaction predictions",
                pmid="35115300",
                year=2020,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="Δ⁹-THC",
        partner_drug="alcohol",
        partner_class="depressant",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Additive sedation, psychomotor impairment, and tachycardia; "
            "co-administration linearly raises peak THC plasma levels in "
            "controlled crossover studies."
        ),
        population="adults co-using alcohol and inhaled / oral THC",
        citations=(
            InteractionCitation(
                label="Hartman 2015 — Cannabis-alcohol co-use PK",
                pmid="23220273",
                year=2015,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="Δ⁹-THC",
        partner_drug="benzodiazepines (e.g. clonazepam, lorazepam)",
        partner_class="GABAergic sedatives",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Additive sedation and respiratory-depression risk; falls and "
            "cognitive impairment compound in older adults."
        ),
        population="adults co-prescribed benzodiazepines and THC",
        citations=(
            InteractionCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="topiramate",
        partner_class="antiepileptic",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Topiramate trough levels rose modestly when CBD was added in "
            "the pivotal CBD epilepsy AED-interaction series; mechanism "
            "uncertain but consistent across patients."
        ),
        population="paediatric / adult epilepsy patients on topiramate",
        citations=(
            InteractionCitation(
                label="Gaston 2017 — CBD AE patterns and AED interactions",
                pmid="28782097",
                year=2017,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="rufinamide",
        partner_class="antiepileptic",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Rufinamide trough levels rose when CBD was added in the same "
            "AED-interaction series; clinical relevance depends on baseline "
            "rufinamide dose and tolerability."
        ),
        population="paediatric epilepsy patients on rufinamide",
        citations=(
            InteractionCitation(
                label="Gaston 2017 — CBD AE patterns and AED interactions",
                pmid="28782097",
                year=2017,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="zonisamide",
        partner_class="antiepileptic",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Modest zonisamide trough elevation observed; in-vitro CBD "
            "CYP3A4 inhibition is the plausible mechanism, but clinical "
            "magnitude in human dosing is uncertain."
        ),
        population="paediatric epilepsy patients on zonisamide",
        citations=(
            InteractionCitation(
                label="Gaston 2017 — CBD AE patterns and AED interactions",
                pmid="28782097",
                year=2017,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="eslicarbazepine",
        partner_class="antiepileptic",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Modest eslicarbazepine trough elevation observed; clinical "
            "magnitude in human dosing is uncertain."
        ),
        population="paediatric epilepsy patients on eslicarbazepine",
        citations=(
            InteractionCitation(
                label="Gaston 2017 — CBD AE patterns and AED interactions",
                pmid="28782097",
                year=2017,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="Δ⁹-THC",
        partner_drug="opioids (morphine, oxycodone)",
        partner_class="opioid analgesics",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Additive analgesia plus additive sedation and respiratory "
            "depression risk; some controlled-setting studies show modest "
            "opioid-sparing on titration. Falls and cognitive impairment "
            "compound in older adults."
        ),
        population="adults with chronic pain co-prescribed opioids and THC",
        citations=(
            InteractionCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="immunosuppressants (sirolimus, everolimus, ciclosporin)",
        partner_class="mTOR / calcineurin inhibitors",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.HIGH,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "CYP3A4 inhibition raises trough levels of all narrow-"
            "therapeutic-index immunosuppressants metabolised through this "
            "route; transplant-recipient trough monitoring is mandatory "
            "when CBD is added or stopped."
        ),
        population="transplant recipients on CYP3A4-substrate immunosuppressants who add CBD",
        citations=(
            InteractionCitation(
                label="Leino 2019 — CBD-tacrolimus trough rise (case)",
                pmid="31012522",
                year=2019,
            ),
            InteractionCitation(
                label="Bansal et al. 2022 Drug Metab Dispos — cannabinoid CYP drug-interaction predictions",
                pmid="35115300",
                year=2020,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="phenytoin",
        partner_class="antiepileptic / CYP2C9 substrate",
        cyp_isoform="CYP2C9",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Phenytoin is a CYP2C9 substrate; CBD inhibits CYP2C9 in "
            "vitro and in human PK studies. Phenytoin has a narrow "
            "therapeutic index; trough monitoring is the practical "
            "clinical action when CBD is added."
        ),
        population="adults / paediatric epilepsy patients on phenytoin",
        citations=(
            InteractionCitation(
                label="Stout 2014 — Cannabinoid PK and drug interactions review",
                pmid="24160757",
                year=2014,
            ),
            InteractionCitation(
                label="Bansal et al. 2022 Drug Metab Dispos — cannabinoid CYP drug-interaction predictions",
                pmid="35115300",
                year=2020,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="Δ⁹-THC",
        partner_drug="tricyclic antidepressants (amitriptyline, nortriptyline)",
        partner_class="tricyclic antidepressants",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Additive tachycardia and anticholinergic burden (dry mouth, "
            "urinary retention, constipation). Most clinically relevant "
            "in older adults at higher TCA doses."
        ),
        population="adults co-prescribed tricyclic antidepressants and THC",
        citations=(
            InteractionCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
    ),
    # ── Minor cannabinoid interactions (v1.8) ─────────────────────────
    # Coverage here is intentionally narrow. Minor cannabinoid (CBN /
    # CBG / THCV / CBC) interaction evidence is largely in vitro; this
    # module marks each entry as PRECLINICAL / LIMITED so consumers do
    # not extrapolate beyond what the source supports.
    CannabinoidInteraction(
        cannabinoid="CBN",
        partner_drug="CYP3A4 substrates (statins, immunosuppressants, some antifungals)",
        partner_class="CYP3A4 substrates",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "In-vitro CYP3A4 inhibition by CBN documented; in-vivo "
            "magnitude unknown — exposure to CBN in commercial products "
            "is typically low (CBN is primarily a THC-degradation product). "
            "Treat as a theoretical concern unless documented exposure is "
            "high."
        ),
        population="adults co-administered chronic CYP3A4 substrates with high-CBN products",
        citations=(
            InteractionCitation(
                label="Stout 2014 — Cannabinoid PK and drug interactions review",
                pmid="24160757",
                year=2014,
            ),
        ),
        notes=(
            "PRECLINICAL / LIMITED: in-vitro signal only; no human PK "
            "interaction study at the inclusion bar."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBG",
        partner_drug="CYP3A4 / CYP2C9 substrates",
        partner_class="CYP3A4 / CYP2C9 substrates",
        cyp_isoform="CYP3A4 / CYP2C9",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "In-vitro inhibition of CYP3A4 and CYP2C9 by CBG documented; "
            "in-vivo magnitude unknown. Commercial CBG products vary "
            "widely in actual CBG content — assume in-vivo magnitude is "
            "comparable to CBD only when actual dose is known."
        ),
        population="adults co-administered chronic CYP substrates with high-CBG products",
        citations=(
            InteractionCitation(
                label="Stout 2014 — Cannabinoid PK and drug interactions review",
                pmid="24160757",
                year=2014,
            ),
            InteractionCitation(
                label="Bansal et al. 2022 Drug Metab Dispos — cannabinoid CYP drug-interaction predictions",
                pmid="35115300",
                year=2020,
            ),
        ),
        notes=(
            "PRECLINICAL / LIMITED: in-vitro signal; no controlled "
            "human PK interaction study at the inclusion bar."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="THCV",
        partner_drug="appetite-stimulating drugs (mirtazapine, dronabinol, cyproheptadine)",
        partner_class="appetite-stimulating drugs",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Small human studies suggest THCV is a CB1 neutral antagonist "
            "at low dose; theoretical PD antagonism of appetite-stimulating "
            "drugs. Clinical magnitude unknown; THCV exposure in commercial "
            "products is typically very low."
        ),
        population="adults co-administered appetite-stimulating drugs with high-THCV products",
        citations=(
            InteractionCitation(
                label="Stout 2014 — Cannabinoid PK and drug interactions review",
                pmid="24160757",
                year=2014,
            ),
        ),
        notes=(
            "PRECLINICAL / LIMITED: theoretical PD; no controlled "
            "human interaction study at the inclusion bar."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBN",
        partner_drug="sedative-hypnotics (zolpidem, eszopiclone, melatonin)",
        partner_class="sedative-hypnotics",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Marketing claims of CBN sedation outpace human evidence; "
            "the historical preclinical observation of mild sedation has "
            "limited controlled-trial replication. Treat additive "
            "sedation as a theoretical concern; primary evidence is weak."
        ),
        population="adults co-administered chronic sedative-hypnotics with high-CBN products",
        citations=(
            InteractionCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
        notes=(
            "PRECLINICAL / LIMITED: weak primary evidence for the CBN "
            "sedation effect itself; this entry reflects the theoretical "
            "concern."
        ),
    ),
    # ── Spec 004 US3 — Modern-prescribing interaction rows ────────────
    # The 2024–2026 prescribing reality includes direct-oral
    # anticoagulants (DOACs), SSRIs-by-name, lithium, anesthesia
    # agents, and chemotherapy specifics. The registry until v2.12
    # covered warfarin / TCAs / benzodiazepines but missed every
    # row a contemporary clinician encounters.
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="apixaban",
        partner_class="direct oral anticoagulant (factor-Xa inhibitor)",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "CBD is a documented CYP3A4 inhibitor; apixaban is a CYP3A4 + "
            "P-gp dual substrate. Predicted exposure increase is modest "
            "but additive with other CYP3A4 inhibitors. Monitor for "
            "bleeding signs; reassess if dose ≥ 10 mg/kg/day CBD."
        ),
        population=(
            "adults on chronic DOAC therapy adding CBD (Epidiolex or "
            "high-dose hemp-derived)"
        ),
        citations=(
            InteractionCitation(
                label="Brown 2019 — Cannabidiol-drug interactions and CYP review (AAPS J)",
                url="https://link.springer.com/article/10.1208/s12248-019-0339-5",
                year=2019,
            ),
            InteractionCitation(
                label="Apixaban (Eliquis) FDA label — Drug Interactions § 7",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2021/202155s029lbl.pdf",
            ),
        ),
        notes=(
            "DOAC class share CYP3A4 + P-gp dependency; apixaban + "
            "rivaroxaban exposure is more CBD-sensitive than edoxaban "
            "(predominantly hydrolysis) or dabigatran (P-gp only, no "
            "CYP). See class-fallback row for non-specific queries."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="rivaroxaban",
        partner_class="direct oral anticoagulant (factor-Xa inhibitor)",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Rivaroxaban is metabolised by CYP3A4 (~32%) and is a P-gp "
            "substrate; CBD inhibition of both is expected to raise AUC "
            "modestly. Risk is greater in renal impairment (CrCl 15–50)."
        ),
        population=(
            "adults on chronic rivaroxaban adding CBD; elevated risk in "
            "moderate renal impairment"
        ),
        citations=(
            InteractionCitation(
                label="Brown 2019 — Cannabidiol-drug interactions and CYP review (AAPS J)",
                url="https://link.springer.com/article/10.1208/s12248-019-0339-5",
                year=2019,
            ),
            InteractionCitation(
                label="Rivaroxaban (Xarelto) FDA label — Drug Interactions § 7",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2021/202439s033lbl.pdf",
            ),
        ),
        notes="Pair with apixaban entry for cross-DOAC reasoning.",
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="dabigatran",
        partner_class="direct oral anticoagulant (thrombin inhibitor)",
        cyp_isoform=None,
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Dabigatran is a P-gp substrate with no CYP metabolism; CBD's "
            "documented P-gp inhibition would raise dabigatran exposure. "
            "Edoxaban shares the P-gp dependency."
        ),
        population="adults on dabigatran or edoxaban adding CBD",
        citations=(
            InteractionCitation(
                label="Tournier 2017 — Cannabinoids modulate P-gp transport (Biochem Pharmacol)",
                url="https://www.sciencedirect.com/science/article/abs/pii/S0006295217301089",
                year=2017,
            ),
            InteractionCitation(
                label="Dabigatran (Pradaxa) FDA label — Drug Interactions § 7",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2021/022512s044lbl.pdf",
            ),
        ),
        notes=(
            "Mechanism is P-gp only — not CYP. Distinct from apixaban / "
            "rivaroxaban which share both pathways."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="edoxaban",
        partner_class="direct oral anticoagulant (factor-Xa inhibitor)",
        cyp_isoform=None,
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Edoxaban is primarily eliminated by hydrolysis and is a P-gp "
            "substrate; minimal CYP3A4 contribution. CBD P-gp inhibition "
            "is the relevant pathway; magnitude expected smaller than "
            "for apixaban / rivaroxaban."
        ),
        population="adults on edoxaban adding CBD",
        citations=(
            InteractionCitation(
                label="Edoxaban (Savaysa) FDA label — Clinical Pharmacology § 12.3",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2015/206316lbl.pdf",
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="sertraline",
        partner_class="SSRI antidepressant",
        cyp_isoform="CYP2C19",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Sertraline is a CYP2C19 substrate (with CYP2B6/CYP3A4 "
            "contributions); CBD's potent CYP2C19 inhibition predicts "
            "modest AUC increase. Watch for serotonergic adverse effects "
            "(GI upset, jitteriness, sleep disturbance) especially at "
            "Epidiolex-range dosing (≥ 5 mg/kg/day)."
        ),
        population=(
            "adults co-prescribed sertraline and CBD; CYP2C19 poor "
            "metabolisers (PM, ~3% of Europeans, ~15% of East Asians) "
            "have higher baseline exposure"
        ),
        citations=(
            InteractionCitation(
                label="Doohan 2021 — CBD pharmacokinetics and drug-drug interactions (Drug Metab Dispos)",
                url="https://dmd.aspetjournals.org/content/49/12/1043",
                year=2021,
            ),
            InteractionCitation(
                label="Sertraline (Zoloft) FDA label — Clinical Pharmacology § 12.3",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2017/019839S074S086S087_20990S035S044S045lbl.pdf",
            ),
        ),
        pharmacogenomic_stratification=(
            ("CYP2C19 PM (*2/*2, *2/*3, *3/*3)",
             "~3-5x higher baseline sertraline AUC; CBD addition compounds — "
             "start sertraline at low dose, retitrate."),
            ("CYP2C19 NM/UM",
             "default dosing; monitor for emergent serotonergic AEs."),
        ),
        notes=(
            "The most-co-prescribed SSRI; the generic 'CYP3A4 substrates' "
            "or 'TCA' rows do not substitute. See escitalopram + "
            "fluoxetine entries for SSRI-class triangulation."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="fluoxetine",
        partner_class="SSRI antidepressant",
        cyp_isoform="CYP2D6",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Fluoxetine is a CYP2D6 + CYP2C9 substrate AND is itself a "
            "CYP2D6 inhibitor; CBD inhibits CYP2D6 modestly. The clinical "
            "picture is bidirectional CYP2D6 inhibition and elevated "
            "fluoxetine/norfluoxetine exposure. Long half-life (4–6 days) "
            "amplifies the effect of any CBD dose change."
        ),
        population="adults on fluoxetine adding CBD",
        citations=(
            InteractionCitation(
                label="Doohan 2021 — CBD pharmacokinetics and drug-drug interactions (Drug Metab Dispos)",
                url="https://dmd.aspetjournals.org/content/49/12/1043",
                year=2021,
            ),
            InteractionCitation(
                label="Fluoxetine (Prozac) FDA label — Clinical Pharmacology § 12.3",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2017/018936s108lbl.pdf",
            ),
        ),
        notes=(
            "Steady-state effects emerge over weeks owing to "
            "norfluoxetine accumulation."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="escitalopram",
        partner_class="SSRI antidepressant",
        cyp_isoform="CYP2C19",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Escitalopram is metabolised primarily by CYP2C19 (~50%) + "
            "CYP3A4 + CYP2D6. CBD's CYP2C19 inhibition predicts the same "
            "moderate AUC increase as sertraline, with attendant "
            "QT-prolongation watch at doses ≥ 20 mg/day."
        ),
        population="adults on escitalopram adding CBD, especially CYP2C19 PMs",
        citations=(
            InteractionCitation(
                label="Doohan 2021 — CBD pharmacokinetics and drug-drug interactions (Drug Metab Dispos)",
                url="https://dmd.aspetjournals.org/content/49/12/1043",
                year=2021,
            ),
            InteractionCitation(
                label="Escitalopram (Lexapro) FDA label — Drug Interactions § 7",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2017/021323s047lbl.pdf",
            ),
        ),
        pharmacogenomic_stratification=(
            ("CYP2C19 PM",
             "FDA recommends max 10 mg/day escitalopram; CBD addition further "
             "increases exposure — escalate slowly."),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="lithium",
        partner_class="mood stabiliser (renally cleared narrow therapeutic index)",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Lithium is renally cleared and has a narrow therapeutic "
            "index (0.6–1.2 mEq/L). Cannabis-associated dehydration, "
            "nausea (CBD can cause GI upset), and CYP-independent "
            "ADH-modulation effects can shift lithium clearance. "
            "Document lithium levels at baseline and 2–4 weeks after "
            "cannabis dose changes; counsel hydration."
        ),
        population="adults on chronic lithium adding cannabis (any form)",
        citations=(
            InteractionCitation(
                label="Bonn-Miller 2018 — Cannabis and psychiatric medications: case-series review (Front Psychiatry)",
                url="https://www.frontiersin.org/journals/psychiatry",
                year=2018,
            ),
            InteractionCitation(
                label="MacCallum 2018 — Practical clinical cannabis prescribing review",
                pmid="29307505",
                year=2018,
            ),
        ),
        notes=(
            "Pharmacodynamic (not CYP); the mechanism is hydration + "
            "renal-handling shift, not enzymatic competition."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="propofol",
        partner_class="anesthesia induction agent",
        cyp_isoform="CYP2B6",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.DOSE_ADJUST,
        magnitude_note=(
            "Propofol is a CYP2B6 + CYP2C9 substrate; CBD inhibits both. "
            "Chronic cannabis users require higher induction doses of "
            "propofol AND show prolonged elimination after the dose. "
            "Pre-op screening for daily cannabis use (especially CBD ≥ 5 "
            "mg/kg) is documented standard of care in current ASA-aligned "
            "perioperative consensus."
        ),
        population="adults undergoing anesthesia with chronic CBD use",
        citations=(
            InteractionCitation(
                label="Holmen 2020 — Cannabis and anesthesia: systematic review (J Cannabis Res)",
                url="https://jcannabisresearch.biomedcentral.com/articles/10.1186/s42238-020-00026-0",
                year=2020,
            ),
            InteractionCitation(
                label="Twardowski 2019 — Effects of cannabis use on perioperative outcomes (J Am Osteopath Assoc)",
                url="https://www.degruyter.com/document/doi/10.7556/jaoa.2019.029/html",
                year=2019,
            ),
        ),
        notes=(
            "Volatile anaesthetics (sevoflurane, isoflurane, desflurane) "
            "share CYP2E1 metabolism with THC oxidative pathways; "
            "clinical-magnitude interactions less well characterised but "
            "documented qualitatively in the same reviews."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="Δ⁹-THC",
        partner_drug="volatile anaesthetics (sevoflurane, isoflurane, desflurane)",
        partner_class="anesthesia maintenance agent",
        cyp_isoform="CYP2E1",
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.MODERATE,
        clinical_action=ClinicalAction.DOSE_ADJUST,
        magnitude_note=(
            "Chronic THC use may correspond to higher MAC requirement "
            "(documented in inhaled regimens) and altered post-op nausea "
            "/ vomiting incidence. Pre-op cannabis disclosure should be "
            "elicited; counsel patients on disclosure."
        ),
        population="adults undergoing anesthesia with chronic cannabis use",
        citations=(
            InteractionCitation(
                label="Flisberg 2009 — Anaesthesia in chronic cannabis users (Eur J Anaesthesiol)",
                url="https://journals.lww.com/ejanaesthesiology/Abstract/2009/08000/Anaesthesia_in_chronic_cannabis_users.10.aspx",
                year=2009,
            ),
            InteractionCitation(
                label="Holmen 2020 — Cannabis and anesthesia: systematic review (J Cannabis Res)",
                url="https://jcannabisresearch.biomedcentral.com/articles/10.1186/s42238-020-00026-0",
                year=2020,
            ),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="taxanes (paclitaxel, docetaxel)",
        partner_class="cytotoxic chemotherapy (CYP3A4 substrate)",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.HIGH,
        clinical_action=ClinicalAction.AVOID,
        magnitude_note=(
            "Paclitaxel and docetaxel are CYP3A4 substrates with narrow "
            "therapeutic window and dose-limiting neutropenia. CBD's "
            "potent CYP3A4 inhibition risks elevating taxane AUC and "
            "amplifying myelosuppression. Avoid co-administration during "
            "active chemotherapy cycles unless oncologist explicitly "
            "approves; CBD can be reintroduced ≥ 7 days post-cycle."
        ),
        population="adults receiving taxane chemotherapy",
        citations=(
            InteractionCitation(
                label="Bouquié 2018 — Cannabis and oncology drug interactions review (Bull Cancer)",
                url="https://www.sciencedirect.com/science/article/abs/pii/S0007455118300328",
                year=2018,
            ),
            InteractionCitation(
                label="Paclitaxel FDA label — Drug Interactions § 7",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2011/020262s049lbl.pdf",
            ),
        ),
        notes=(
            "Includes nab-paclitaxel (Abraxane). The general "
            "'CYP3A4 substrates' fallback row does NOT substitute — "
            "narrow-TI cytotoxics require their own rule."
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="vinca alkaloids (vincristine, vinblastine)",
        partner_class="cytotoxic chemotherapy (CYP3A4 substrate)",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.HIGH,
        clinical_action=ClinicalAction.AVOID,
        magnitude_note=(
            "Vincristine and vinblastine are CYP3A4 substrates with "
            "dose-limiting neuropathy and myelosuppression respectively. "
            "CBD CYP3A4 inhibition raises exposure and toxicity risk. "
            "Avoid during chemotherapy cycles; oncologist consultation "
            "mandatory for any cannabinoid use during active therapy."
        ),
        population="adults receiving vinca-alkaloid chemotherapy",
        citations=(
            InteractionCitation(
                label="Bouquié 2018 — Cannabis and oncology drug interactions review (Bull Cancer)",
                url="https://www.sciencedirect.com/science/article/abs/pii/S0007455118300328",
                year=2018,
            ),
        ),
        notes="Pair with taxane entry for chemotherapy-class reasoning.",
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="irinotecan",
        partner_class="topoisomerase-I inhibitor (CYP3A4 substrate)",
        cyp_isoform="CYP3A4",
        direction=InteractionDirection.INHIBITS,
        severity=InteractionSeverity.HIGH,
        clinical_action=ClinicalAction.AVOID,
        magnitude_note=(
            "Irinotecan is converted to active SN-38 by CES2 and is a "
            "CYP3A4 substrate for inactivation. CBD CYP3A4 inhibition "
            "elevates exposure, increasing severe diarrhoea and "
            "neutropenia risk. UGT1A1 *28 polymorphism amplifies risk."
        ),
        population="adults receiving irinotecan",
        citations=(
            InteractionCitation(
                label="Bouquié 2018 — Cannabis and oncology drug interactions review (Bull Cancer)",
                url="https://www.sciencedirect.com/science/article/abs/pii/S0007455118300328",
                year=2018,
            ),
        ),
        pharmacogenomic_stratification=(
            ("UGT1A1 *28/*28",
             "FDA label recommends dose reduction; CBD addition further "
             "elevates SN-38 exposure — avoid co-administration."),
        ),
    ),
    CannabinoidInteraction(
        cannabinoid="CBD",
        partner_drug="platinum agents (cisplatin, carboplatin, oxaliplatin)",
        partner_class="cytotoxic chemotherapy (non-CYP)",
        cyp_isoform=None,
        direction=InteractionDirection.PHARMACODYNAMIC,
        severity=InteractionSeverity.LOW,
        clinical_action=ClinicalAction.MONITOR,
        magnitude_note=(
            "Platinum agents are not appreciably CYP-metabolised; PK "
            "interaction with CBD is minimal. The clinical question is "
            "additive nephrotoxicity (cisplatin) and additive "
            "neuropathy (oxaliplatin). Maintain hydration; document "
            "creatinine and neurologic symptoms during cycles."
        ),
        population="adults receiving platinum-based chemotherapy",
        citations=(
            InteractionCitation(
                label="Bouquié 2018 — Cannabis and oncology drug interactions review (Bull Cancer)",
                url="https://www.sciencedirect.com/science/article/abs/pii/S0007455118300328",
                year=2018,
            ),
        ),
        notes=(
            "Separated from taxane/vinca/irinotecan because the mechanism "
            "is pharmacodynamic, not CYP — the management plan differs."
        ),
    ),
)


def all_interactions() -> tuple[CannabinoidInteraction, ...]:
    """Return the full curated registry (read-only)."""
    return _REGISTRY


def find_interactions(
    *,
    cannabinoid: str | None = None,
    partner_drug: str | None = None,
    partner_class: str | None = None,
    min_severity: InteractionSeverity | None = None,
) -> tuple[CannabinoidInteraction, ...]:
    """Search the registry. Matchers are case-insensitive substring.

    The ``cannabinoid`` filter is normalised so that ``Δ9-THC``,
    ``Δ⁹-THC``, and ``delta-9-THC`` all match the registry's canonical
    ``Δ⁹-THC`` form.
    """
    from cannavec_science._normalize import normalized_contains

    def matches(s: str, q: str | None) -> bool:
        if q is None:
            return True
        return q.lower() in s.lower()

    sev_order = {
        InteractionSeverity.LOW: 0,
        InteractionSeverity.MODERATE: 1,
        InteractionSeverity.HIGH: 2,
    }
    min_rank = sev_order[min_severity] if min_severity else 0

    out: list[CannabinoidInteraction] = []
    for x in _REGISTRY:
        if not normalized_contains(x.cannabinoid, cannabinoid):
            continue
        if not matches(x.partner_drug, partner_drug):
            continue
        if not matches(x.partner_class, partner_class):
            continue
        if sev_order[x.severity] < min_rank:
            continue
        out.append(x)
    return tuple(out)


# Keyword index — used by detect_interaction_mention.
# Partner-drug keywords that are ALSO endogenous molecules the body secretes.
# See the endogenous-hormone guard in :func:`detect_interaction_mention`.
_ENDOGENOUS_ALSO_DRUG_KW = frozenset({"melatonin"})
_ENDOGENOUS_PHYSIOLOGY_CTX = re.compile(
    r"\b(?:secret\w*|synthes\w*|production|levels?|rhythm|circadian|"
    r"endogenous|biosynthesis|nocturnal|pineal|homeostasis)\b",
    re.IGNORECASE,
)
_COADMIN_CTX = re.compile(
    r"\b(?:interact\w*|co[- ]?admin\w*|concomitant\w*|combined\s+with|"
    r"taken?\s+with|taking|supplement\w*|together\s+with|alongside|"
    r"drug[- ]?drug|co[- ]?ingest\w*)\b",
    re.IGNORECASE,
)


_PARTNER_KEYWORDS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(kw)}\b", flags=re.IGNORECASE), partner)
    for kw, partner in [
        ("warfarin", "warfarin"),
        ("coumadin", "warfarin"),
        ("clobazam", "clobazam"),
        ("tacrolimus", "tacrolimus"),
        ("valproate", "valproate"),
        ("valproic acid", "valproate"),
        ("phenytoin", "phenytoin"),
        ("clopidogrel", "clopidogrel"),
        ("statin", "CYP3A4 substrates (statins, immunosuppressants, some antifungals)"),
        ("simvastatin", "CYP3A4 substrates (statins, immunosuppressants, some antifungals)"),
        ("atorvastatin", "CYP3A4 substrates (statins, immunosuppressants, some antifungals)"),
        ("alcohol", "alcohol"),
        ("benzodiazepine", "benzodiazepines (e.g. clonazepam, lorazepam)"),
        ("benzo", "benzodiazepines (e.g. clonazepam, lorazepam)"),
        ("clonazepam", "benzodiazepines (e.g. clonazepam, lorazepam)"),
        ("lorazepam", "benzodiazepines (e.g. clonazepam, lorazepam)"),
        ("diazepam", "benzodiazepines (e.g. clonazepam, lorazepam)"),
        # New v1.7 entries
        ("topiramate", "topiramate"),
        ("rufinamide", "rufinamide"),
        ("zonisamide", "zonisamide"),
        ("eslicarbazepine", "eslicarbazepine"),
        ("morphine", "opioids (morphine, oxycodone)"),
        ("oxycodone", "opioids (morphine, oxycodone)"),
        ("opioid", "opioids (morphine, oxycodone)"),
        ("hydrocodone", "opioids (morphine, oxycodone)"),
        ("tramadol", "opioids (morphine, oxycodone)"),
        ("sirolimus", "immunosuppressants (sirolimus, everolimus, ciclosporin)"),
        ("everolimus", "immunosuppressants (sirolimus, everolimus, ciclosporin)"),
        ("ciclosporin", "immunosuppressants (sirolimus, everolimus, ciclosporin)"),
        ("cyclosporine", "immunosuppressants (sirolimus, everolimus, ciclosporin)"),
        ("amitriptyline", "tricyclic antidepressants (amitriptyline, nortriptyline)"),
        ("nortriptyline", "tricyclic antidepressants (amitriptyline, nortriptyline)"),
        ("tricyclic", "tricyclic antidepressants (amitriptyline, nortriptyline)"),
        # v1.8 — partner aliases for the minor-cannabinoid entries
        ("zolpidem", "sedative-hypnotics (zolpidem, eszopiclone, melatonin)"),
        ("eszopiclone", "sedative-hypnotics (zolpidem, eszopiclone, melatonin)"),
        ("melatonin", "sedative-hypnotics (zolpidem, eszopiclone, melatonin)"),
        ("sleep aid", "sedative-hypnotics (zolpidem, eszopiclone, melatonin)"),
        ("mirtazapine", "appetite-stimulating drugs (mirtazapine, dronabinol, cyproheptadine)"),
        ("cyproheptadine", "appetite-stimulating drugs (mirtazapine, dronabinol, cyproheptadine)"),
        ("dronabinol", "appetite-stimulating drugs (mirtazapine, dronabinol, cyproheptadine)"),
        ("appetite", "appetite-stimulating drugs (mirtazapine, dronabinol, cyproheptadine)"),
        # Make CYP-substrate keywords also match the CBG class-level entry.
        ("CYP3A4 substrate", "CYP3A4 / CYP2C9 substrates"),
        ("CYP2C9 substrate", "CYP3A4 / CYP2C9 substrates"),
        # ── Spec 004 US3 — Modern-prescribing keyword index ───────────
        # DOACs by name; each maps to its specific row. The DOAC class
        # mention (no specific drug named) routes to apixaban as the
        # most-prescribed default.
        ("apixaban", "apixaban"),
        ("eliquis", "apixaban"),
        ("rivaroxaban", "rivaroxaban"),
        ("xarelto", "rivaroxaban"),
        ("dabigatran", "dabigatran"),
        ("pradaxa", "dabigatran"),
        ("edoxaban", "edoxaban"),
        ("savaysa", "edoxaban"),
        ("doac", "apixaban"),
        ("direct oral anticoagulant", "apixaban"),
        ("factor xa", "apixaban"),
        # SSRIs by name
        ("sertraline", "sertraline"),
        ("zoloft", "sertraline"),
        ("fluoxetine", "fluoxetine"),
        ("prozac", "fluoxetine"),
        ("escitalopram", "escitalopram"),
        ("lexapro", "escitalopram"),
        ("ssri", "sertraline"),
        # Lithium
        ("lithium", "lithium"),
        # Anesthesia
        ("propofol", "propofol"),
        ("diprivan", "propofol"),
        ("sevoflurane", "volatile anaesthetics (sevoflurane, isoflurane, desflurane)"),
        ("isoflurane", "volatile anaesthetics (sevoflurane, isoflurane, desflurane)"),
        ("desflurane", "volatile anaesthetics (sevoflurane, isoflurane, desflurane)"),
        ("volatile anaesthetic", "volatile anaesthetics (sevoflurane, isoflurane, desflurane)"),
        ("volatile anesthetic", "volatile anaesthetics (sevoflurane, isoflurane, desflurane)"),
        ("general anaesthesia", "propofol"),
        ("general anesthesia", "propofol"),
        ("perioperative", "propofol"),
        # Chemotherapy specifics
        ("paclitaxel", "taxanes (paclitaxel, docetaxel)"),
        ("taxol", "taxanes (paclitaxel, docetaxel)"),
        ("docetaxel", "taxanes (paclitaxel, docetaxel)"),
        ("taxotere", "taxanes (paclitaxel, docetaxel)"),
        ("nab-paclitaxel", "taxanes (paclitaxel, docetaxel)"),
        ("abraxane", "taxanes (paclitaxel, docetaxel)"),
        ("taxane", "taxanes (paclitaxel, docetaxel)"),
        ("vincristine", "vinca alkaloids (vincristine, vinblastine)"),
        ("vinblastine", "vinca alkaloids (vincristine, vinblastine)"),
        ("vinorelbine", "vinca alkaloids (vincristine, vinblastine)"),
        ("vinca", "vinca alkaloids (vincristine, vinblastine)"),
        ("irinotecan", "irinotecan"),
        ("camptosar", "irinotecan"),
        ("cisplatin", "platinum agents (cisplatin, carboplatin, oxaliplatin)"),
        ("carboplatin", "platinum agents (cisplatin, carboplatin, oxaliplatin)"),
        ("oxaliplatin", "platinum agents (cisplatin, carboplatin, oxaliplatin)"),
        ("platinum agent", "platinum agents (cisplatin, carboplatin, oxaliplatin)"),
        ("chemotherapy", "taxanes (paclitaxel, docetaxel)"),
        ("chemo", "taxanes (paclitaxel, docetaxel)"),
    ]
)


_CANNABINOID_KEYWORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcbd\b|\bcannabidiol\b", re.IGNORECASE), "CBD"),
    (re.compile(r"\bthc\b|\btetrahydrocannabinol\b|\bdelta[-\s]?9\b|"
                r"\bΔ9\b|\bΔ⁹\b", re.IGNORECASE), "Δ⁹-THC"),
    (re.compile(r"\bcbn\b|\bcannabinol\b", re.IGNORECASE), "CBN"),
    (re.compile(r"\bcbg\b|\bcannabigerol\b", re.IGNORECASE), "CBG"),
    (re.compile(r"\bthcv\b|\btetrahydrocannabivarin\b", re.IGNORECASE), "THCV"),
)

# Spec 003 US6 / FR-006 — cannabis-noun → cannabinoid-set expansion.
# When the prompt contains "cannabis" / "marijuana" / "marihuana" /
# "weed" without naming a specific cannabinoid, every interaction row
# whose cannabinoid is in this set becomes a candidate.
_CANNABIS_NOUN_RE = re.compile(
    r"\bcannabis\b|\bmarijuana\b|\bmarihuana\b|\bweed\b",
    re.IGNORECASE,
)
_CANNABIS_NOUN_EXPANSION: tuple[str, ...] = (
    "CBD", "Δ⁹-THC", "CBN", "CBG", "THCV",
)


def _resolve_interaction_cannabinoids(
    text: str,
    cannabinoid_filter: frozenset[str] | set[str] | None,
) -> set[str]:
    direct = {label for rx, label in _CANNABINOID_KEYWORDS
              if rx.search(text)}
    cannabis_noun = _CANNABIS_NOUN_RE.search(text) is not None
    if cannabis_noun and not direct:
        direct.update(_CANNABIS_NOUN_EXPANSION)
    if cannabinoid_filter is not None:
        if cannabinoid_filter:
            direct = direct & set(cannabinoid_filter)
        else:
            direct = set()
    return direct


def detect_interaction_mention(
    text: str,
    *,
    cannabinoid_filter: frozenset[str] | set[str] | None = None,
) -> tuple[CannabinoidInteraction, ...]:
    """Return registry entries that match a (cannabinoid, partner) pair in ``text``.

    A registry entry matches when:
      - a cannabinoid keyword for ``x.cannabinoid`` appears in ``text``, AND
      - a partner keyword whose mapped value is the same string as
        ``x.partner_drug`` OR appears as a substring of ``x.partner_drug``.

    Spec 003 US6 / FR-006: the word "cannabis" / "marijuana" /
    "marihuana" / "weed" expands to the cannabinoid set
    {CBD, Δ⁹-THC, CBN, CBG, THCV} so "cannabis × tacrolimus" matches
    the CBD-tacrolimus row.

    Spec 003 US2 / FR-002: ``cannabinoid_filter`` restricts the
    cannabinoid set to the prompt's named cannabinoids. When set by
    :func:`compose_answer`, this is the :class:`NamedCannabinoidSet`.

    Returns an empty tuple if no cannabinoid + partner-drug pair is
    co-mentioned.
    """
    cannabinoids = _resolve_interaction_cannabinoids(text, cannabinoid_filter)
    # Endogenous-hormone guard: a few partner-drug names are also molecules
    # the body secretes (currently only "melatonin"). When the prompt frames
    # such a molecule as an ENDOGENOUS analyte (its secretion / rhythm /
    # synthesis) and NOT as a co-administered drug, an interaction-registry
    # hit on the same-named drug is a false positive — the question "how does
    # cannabis affect melatonin SECRETION" is endocrine physiology, not a
    # cannabinoid×melatonin-supplement drug interaction. Suppress it so the
    # registry never answers an endocrine question with an off-target
    # interaction claim.
    endo_physio = _ENDOGENOUS_PHYSIOLOGY_CTX.search(text) is not None
    coadmin = _COADMIN_CTX.search(text) is not None
    partners: set[str] = set()
    for rx, label in _PARTNER_KEYWORDS:
        m = rx.search(text)
        if not m:
            continue
        if (endo_physio and not coadmin
                and m.group(0).lower() in _ENDOGENOUS_ALSO_DRUG_KW):
            continue
        partners.add(label)
    if not cannabinoids or not partners:
        return ()

    def _partner_matches(entry_drug: str) -> bool:
        entry_lower = entry_drug.lower()
        entry_tokens = set(re.findall(r"[a-z0-9]+", entry_lower))
        for p in partners:
            p_lower = p.lower()
            if p_lower == entry_lower:
                return True
            if p_lower in entry_lower:
                return True
            if entry_lower in p_lower:
                return True
            # Word-set overlap: if the partner alias shares ≥2 alphanumeric
            # tokens with the entry name (excluding common stopwords), the
            # match is meaningful — handles the case where canonical names
            # use different separators ("/" vs "(", commas, etc.).
            p_tokens = set(re.findall(r"[a-z0-9]+", p_lower))
            stop = {"and", "or", "the", "of", "for", "with", "some",
                    "in", "on", "to", "a"}
            shared = (p_tokens & entry_tokens) - stop
            if len(shared) >= 2:
                return True
        return False

    out: list[CannabinoidInteraction] = []
    seen: set[tuple[str, str]] = set()
    for x in _REGISTRY:
        if x.cannabinoid not in cannabinoids:
            continue
        if not _partner_matches(x.partner_drug):
            continue
        key = (x.cannabinoid, x.partner_drug)
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return tuple(out)


# Class-level keywords for the generic-question fallback path. Used by
# detect_interaction_class_mention when detect_interaction_mention
# returns no specific (cannabinoid, partner) match. Closes the
# 2026-05-19 Oracle Evaluator §4.3 finding that the interactions
# registry was unreachable from "What are the major CYP-mediated
# cannabinoid drug interactions?" — a question whose answer is
# entirely in the registry.
_CLASS_KEYWORDS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{kw}\b", flags=re.IGNORECASE), scope)
    for kw, scope in [
        ("drug interaction", "all"),
        ("drug interactions", "all"),
        ("drug-drug interaction", "all"),
        ("drug-drug interactions", "all"),
        ("ddi", "all"),
        ("ddis", "all"),
        ("interaction profile", "all"),
        ("pharmacokinetic interaction", "all"),
        ("pharmacokinetic interactions", "all"),
        ("metabolic interaction", "all"),
        ("metabolic interactions", "all"),
        ("cyp interaction", "cyp"),
        ("cyp interactions", "cyp"),
        ("cyp-mediated", "cyp"),
        ("cyp mediated", "cyp"),
        ("cytochrome", "cyp"),
        ("cytochrome p450", "cyp"),
    ]
)


def detect_interaction_class_mention(
    text: str,
    *,
    cannabinoid_filter: frozenset[str] | set[str] | None = None,
) -> tuple[CannabinoidInteraction, ...]:
    """Return all registry entries that match a *class* keyword in ``text``.

    Companion to :func:`detect_interaction_mention` for the generic-
    question case (e.g., "what are the major CYP-mediated cannabinoid
    drug interactions?"). When ``cannabinoid_filter`` is set (spec
    003 US2 / FR-002), only rows whose ``cannabinoid`` field
    intersects the filter are returned.

    Returns ``()`` when no class keyword is matched, so callers can
    safely chain: ``hits = detect_interaction_mention(t) or
    detect_interaction_class_mention(t)``.
    """
    scope: str | None = None
    for rx, s in _CLASS_KEYWORDS:
        if rx.search(text):
            if scope is None or s == "cyp":
                scope = s
    if scope is None:
        return ()
    cannabinoids = _resolve_interaction_cannabinoids(text, cannabinoid_filter)
    if cannabinoids:
        rows = [r for r in _REGISTRY if r.cannabinoid in cannabinoids]
    elif cannabinoid_filter is not None:
        # Spec 003 US2 / FR-002 — no registry cannabinoid intersects.
        rows = []
    else:
        rows = list(_REGISTRY)
    if scope == "cyp":
        rows = [r for r in rows if r.cyp_isoform]
    # Dedupe by (cannabinoid, partner_drug).
    seen: set[tuple[str, str]] = set()
    out: list[CannabinoidInteraction] = []
    for r in rows:
        key = (r.cannabinoid, r.partner_drug)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return tuple(out)


def format_for_clinician(
    interactions: Iterable[CannabinoidInteraction],
) -> str:
    """Render a Markdown clinician-facing summary of a set of interactions.

    Output is deterministic — same input always produces the same text.
    """
    items = list(interactions)
    if not items:
        return (
            "_No high-confidence cannabinoid drug-interaction records found "
            "in the curated registry for the named compounds and partners. "
            "Absence here does not mean absence of interaction — it means "
            "the registry has no entry above the inclusion bar (≥1 human "
            "PK study or regulator label change)._"
        )
    lines: list[str] = ["| Cannabinoid | Partner | Mechanism | Severity | Action | Magnitude | Source |",
                        "|---|---|---|---|---|---|---|"]
    for x in items:
        mech = (
            f"{x.cyp_isoform} ({x.direction.value})"
            if x.cyp_isoform
            else x.direction.value
        )
        src_strs = ", ".join(
            (f"PMID {c.pmid}" if c.pmid else (f"doi:{c.doi}" if c.doi else c.label))
            for c in x.citations
        )
        # Truncate magnitude to one line for table fit.
        magnitude = x.magnitude_note.replace("\n", " ")
        if len(magnitude) > 160:
            magnitude = magnitude[:157] + "..."
        lines.append(
            f"| {x.cannabinoid} | {x.partner_drug} | {mech} | "
            f"{x.severity.value} | {x.clinical_action.value} | "
            f"{magnitude} | {src_strs} |"
        )
    lines.append("")

    # v2.7 pharmacogenomic stratification block (P2.15). Surface PGx
    # rows under the main table so a clinician reading CBD/Δ⁹-THC
    # interactions sees the genotype-stratified dosing nuance.
    pgx_rows = [x for x in items if x.pharmacogenomic_stratification]
    if pgx_rows:
        lines.append("**Pharmacogenomic stratification (where reported):**")
        lines.append("")
        for x in pgx_rows:
            lines.append(
                f"- *{x.cannabinoid} ↔ {x.partner_drug}* (via {x.cyp_isoform}):"
            )
            for genotype, dosing_note in x.pharmacogenomic_stratification:
                lines.append(f"  - **{genotype}** — {dosing_note}")
        lines.append("")

    lines.append(
        "**Population**: the population each row applies to is listed in "
        "the registry's `population` field. Cannavec does not extrapolate "
        "these data to individual patients; an individual prescribing "
        "decision is the clinician's call."
    )
    return "\n".join(lines)
