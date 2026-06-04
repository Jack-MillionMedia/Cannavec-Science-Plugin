"""Evidence grading primitives.

Encodes the GRADE-style levels and Source Authority Hierarchy that the
``cannabis-evidence-grading`` skill describes in prose. The skill is the
human-readable rationale; this module is the machine-readable form.

Design rules:

- Every claim wording must be *no stronger* than its evidence grade
  supports. Level inflation is the single most common safety hazard in
  cannabis content — it is enforced here, not left to prompt vibes.
- A single-primary-study claim caps at Level C unless pre-registered,
  adequately powered, in a major journal (then Level B max). Level A
  requires Cochrane/AHRQ/NICE OR ≥2 independent RCTs in alignment.
- Required disclosures are claim-type-specific. A missing disclosure
  forces a one-grade downgrade and surfaces to reviewer.
- Source weights are multiplicative and capped at 1.00.

This module is import-safe in any Python ≥3.8 environment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class CitationMissingError(ValueError):
    """Raised by :class:`Answer.add_claim` in strict-citation mode.

    Constitution §I (Primary-Source-Or-Refuse) requires every claim to
    cite a primary source (PMID / DOI / ChEMBL / NCT / UniProt). The
    constructor checks on :class:`Source` and :class:`Citation` already
    enforce this at object-construction time; this exception adds a
    compose-time refusal so a sourceless claim cannot land in an
    :class:`Answer` even if it would have been silently graded
    UNSUPPORTED.

    Opt-in via ``Answer(strict_citation_mandate=True)``. Default behaviour
    is unchanged (the claim is accepted and graded UNSUPPORTED) so the
    existing test suite is not perturbed.
    """


class EvidenceLevel(str, Enum):
    """GRADE-style evidence levels.

    Ordering encodes strength: A > B > C > D > E > UNSUPPORTED.
    UNSUPPORTED is reserved for claims with no admissible primary source.
    """

    A = "Level A"
    B = "Level B"
    C = "Level C"
    D = "Level D"
    E = "Level E"
    UNSUPPORTED = "Unsupported"

    @property
    def rank(self) -> int:
        return {
            EvidenceLevel.A: 5,
            EvidenceLevel.B: 4,
            EvidenceLevel.C: 3,
            EvidenceLevel.D: 2,
            EvidenceLevel.E: 1,
            EvidenceLevel.UNSUPPORTED: 0,
        }[self]

    @property
    def acceptable_wording(self) -> tuple[str, ...]:
        return {
            EvidenceLevel.A: ("established", "demonstrates", "is effective for"),
            EvidenceLevel.B: ("likely effective", "appears to reduce", "is associated with"),
            EvidenceLevel.C: ("may reduce", "suggests potential benefit", "preliminary evidence"),
            EvidenceLevel.D: ("anecdotal reports", "open-label observations"),
            EvidenceLevel.E: ("unverified report", "case report only"),
            EvidenceLevel.UNSUPPORTED: ("no admissible primary evidence",),
        }[self]


class SourceTier(int, Enum):
    """Source-Authority Hierarchy tier. Lower is stronger.

    Tiers 1-2 are RCT / SR / cohort level.
    Tier 3 covers single-arm, mechanism, animal.
    Tier 4 covers preprints and small case series.
    Tier 5 covers regulator / pharmacopoeia / consensus.
    Tier 6 covers industry whitepaper / conference.
    Tier 7 covers trade press / advocacy.
    Tier 8 covers anonymous / unsigned content.
    """

    SR_FLAGSHIP = 1   # Cochrane / AHRQ / NICE / IQWiG / WHO SR; NEJM/JAMA/Lancet RCT
    JOURNAL_RCT = 2   # Specialist-journal RCT, major-journal SR/cohort
    SINGLE_ARM_OR_MECH = 3
    PREPRINT_OR_SMALL = 4
    REGULATOR_OR_PHARMACOPOEIA = 5
    INDUSTRY_OR_CONFERENCE = 6
    TRADE_PRESS_OR_ADVOCACY = 7
    ANONYMOUS = 8


class ClaimType(str, Enum):
    """The kind of claim being made — determines required disclosures."""

    CLINICAL_EFFICACY = "clinical_efficacy"
    MECHANISM = "mechanism"
    PHARMACOKINETIC = "pharmacokinetic"
    DOSING = "dosing"
    DRUG_INTERACTION = "drug_interaction"
    SAFETY = "safety"
    PHYTOCHEMISTRY_QUANTITY = "phytochemistry_quantity"
    LEGAL_REGULATORY = "legal_regulatory"
    CULTIVATION_PARAMETER = "cultivation_parameter"
    MARKET_DATA = "market_data"
    EDUCATIONAL = "educational"
    OPINION = "opinion"


@dataclass(frozen=True)
class Source:
    """A primary source backing a claim.

    Fields are deliberately concrete: a Source without a URL is not a
    source. Either ``pmid`` or ``doi`` or ``url`` must be set.
    """

    title: str
    tier: SourceTier
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None
    authors: tuple[str, ...] = field(default_factory=tuple)
    study_design: str | None = None
    sample_size: int | None = None
    pre_registered: bool = False
    adequately_powered: bool = False
    coi_declared: bool = False
    coi_undeclared_surfaced: bool = False
    pay_to_publish: bool = False
    author_has_retraction: bool = False
    retraction_status: str = "clean"   # clean | expression_of_concern | under_correction | retracted

    def __post_init__(self) -> None:
        if not (self.pmid or self.doi or self.url):
            raise ValueError("Source must have at least one of pmid/doi/url")


# Base tier weights (Source-Authority Hierarchy from the skill).
_TIER_BASE_WEIGHT: dict[SourceTier, float] = {
    SourceTier.SR_FLAGSHIP: 1.00,
    SourceTier.JOURNAL_RCT: 0.85,
    SourceTier.SINGLE_ARM_OR_MECH: 0.70,
    SourceTier.PREPRINT_OR_SMALL: 0.50,
    SourceTier.REGULATOR_OR_PHARMACOPOEIA: 1.00,   # for the regulator's own claims
    SourceTier.INDUSTRY_OR_CONFERENCE: 0.35,
    SourceTier.TRADE_PRESS_OR_ADVOCACY: 0.20,
    SourceTier.ANONYMOUS: 0.05,
}


def source_authority_weight(source: Source) -> float:
    """Compute the multiplicative source-authority weight, capped at 1.0."""
    weight = _TIER_BASE_WEIGHT[source.tier]
    if source.pre_registered:
        weight *= 1.10
    if source.adequately_powered:
        weight *= 1.05
    if source.coi_undeclared_surfaced:
        weight *= 0.50
    elif source.coi_declared:
        weight *= 0.85
    if source.pay_to_publish:
        weight *= 0.50
    if source.author_has_retraction:
        weight *= 0.70
    if source.sample_size is not None and source.sample_size < 20:
        weight *= 0.60
    return min(weight, 1.00)


def grade_from_source(source: Source) -> EvidenceLevel:
    """Best evidence grade a single source can support (before downgrades).

    This is the *starting point*. GRADE downgrades (risk of bias,
    inconsistency, indirectness, imprecision, publication bias) and the
    required-disclosure penalty are applied via :func:`apply_grade_modifiers`.
    """
    if source.retraction_status == "retracted":
        return EvidenceLevel.UNSUPPORTED
    if source.tier == SourceTier.SR_FLAGSHIP:
        return EvidenceLevel.A
    if source.tier == SourceTier.REGULATOR_OR_PHARMACOPOEIA:
        # Regulator documents anchor regulatory/legal claims at Level A
        # for the regulator's own assertions about scheduling, approvals,
        # etc. They do not anchor clinical efficacy claims at Level A.
        return EvidenceLevel.A
    if source.tier == SourceTier.JOURNAL_RCT:
        if source.pre_registered and source.adequately_powered:
            return EvidenceLevel.B
        return EvidenceLevel.C
    if source.tier == SourceTier.SINGLE_ARM_OR_MECH:
        return EvidenceLevel.C
    if source.tier == SourceTier.PREPRINT_OR_SMALL:
        return EvidenceLevel.D
    if source.tier == SourceTier.INDUSTRY_OR_CONFERENCE:
        return EvidenceLevel.D
    if source.tier == SourceTier.TRADE_PRESS_OR_ADVOCACY:
        return EvidenceLevel.E
    return EvidenceLevel.UNSUPPORTED


# §VII — only a CANONICAL evidence-synthesis body (Cochrane / AHRQ / NICE /
# IQWiG / USPSTF) clears the Level-A floor on a SINGLE systematic review. A
# high-quality journal SR/MA (e.g. a JAMA or PAIN review) is strong evidence
# but, per the constitution, caps at Level B on its own — Level A then needs a
# canonical SR or ≥ 2 aligned confirmatory RCTs. Detection is by source title,
# so no per-registry annotation is required and a future SR is classified the
# moment its citation names the body.
_CANONICAL_SR_RE = re.compile(
    r"\b(cochrane|ahrq|agency for healthcare research|nice|"
    r"national institute for health and care excellence|iqwig|uspstf|"
    r"u\.?s\.? preventive services)\b",
    re.IGNORECASE,
)


def _is_canonical_sr(source: "Source") -> bool:
    """True when ``source`` is a canonical systematic-review body (§VII).

    Only a Cochrane / AHRQ / NICE / IQWiG / USPSTF review qualifies. A journal
    SR/MA at :class:`SourceTier.SR_FLAGSHIP` is strong but is not, on its own, a
    Level-A floor (see :meth:`Claim.best_supportable_grade`).
    """
    if getattr(source, "tier", None) != SourceTier.SR_FLAGSHIP:
        return False
    return bool(_CANONICAL_SR_RE.search(getattr(source, "title", "") or ""))


def _downgrade(level: EvidenceLevel, steps: int) -> EvidenceLevel:
    if level == EvidenceLevel.UNSUPPORTED or steps <= 0:
        return level
    order = [
        EvidenceLevel.A,
        EvidenceLevel.B,
        EvidenceLevel.C,
        EvidenceLevel.D,
        EvidenceLevel.E,
        EvidenceLevel.UNSUPPORTED,
    ]
    idx = order.index(level)
    return order[min(idx + steps, len(order) - 1)]


def apply_grade_modifiers(
    base_grade: EvidenceLevel,
    *,
    risk_of_bias_serious: bool = False,
    inconsistency_serious: bool = False,
    indirectness_serious: bool = False,
    imprecision_serious: bool = False,
    publication_bias_suspected: bool = False,
    methods_unverified: bool = False,
    missing_disclosure_count: int = 0,
    single_primary_study: bool = False,
    pre_registered_major_journal: bool = False,
) -> EvidenceLevel:
    """Apply GRADE downgrades plus Cannavec's additional penalty rules.

    Caller is responsible for assessing the GRADE domains. This function
    is the *aggregator* — it composes the penalties deterministically so
    the same inputs always produce the same grade.
    """
    grade = base_grade
    if grade == EvidenceLevel.UNSUPPORTED:
        return grade

    # GRADE downgrades — one level each.
    for trigger in (
        risk_of_bias_serious,
        inconsistency_serious,
        indirectness_serious,
        imprecision_serious,
        publication_bias_suspected,
    ):
        if trigger:
            grade = _downgrade(grade, 1)

    # Methods-section unread → cap at Level C.
    if methods_unverified and grade.rank > EvidenceLevel.C.rank:
        grade = EvidenceLevel.C

    # Single primary study → cap at Level C unless pre-reg + major journal
    # (then Level B max).
    if single_primary_study:
        if pre_registered_major_journal:
            if grade.rank > EvidenceLevel.B.rank:
                grade = EvidenceLevel.B
        else:
            if grade.rank > EvidenceLevel.C.rank:
                grade = EvidenceLevel.C

    # Missing required disclosures → one-grade penalty each.
    if missing_disclosure_count > 0:
        grade = _downgrade(grade, missing_disclosure_count)

    return grade


@dataclass(frozen=True)
class ProvenanceScore:
    link_liveness_factor: float          # 1.0 LIVE, 0.5 REDIRECT_OK, 0.0 DEAD/RETRACTED
    retraction_factor: float             # 1.0 CLEAN, 0.5 EOC, 0.3 UNDER_CORRECTION, 0.0 RETRACTED
    source_authority_weight: float       # per :func:`source_authority_weight`

    @property
    def score(self) -> float:
        return min(
            1.0,
            self.link_liveness_factor
            * self.retraction_factor
            * self.source_authority_weight,
        )

    @property
    def acceptable_use(self) -> str:
        s = self.score
        if s >= 0.80:
            return "Level A/B claim support"
        if s >= 0.60:
            return "Level C claim support with hedging"
        if s >= 0.40:
            return "Context only, not primary support"
        return "Reject; do not cite as primary"


# Required disclosures per claim type. A claim missing any of these is
# downgraded one grade and surfaced to the reviewer.
_REQUIRED_DISCLOSURES: dict[ClaimType, frozenset[str]] = {
    ClaimType.CLINICAL_EFFICACY: frozenset({
        "effect_size", "ci_95", "n", "comparator", "primary_outcome",
        "evidence_grade", "funding", "coi",
    }),
    ClaimType.MECHANISM: frozenset({
        "target", "target_identifier", "assay", "concentration_or_dose",
        "species", "primary_source",
    }),
    ClaimType.PHARMACOKINETIC: frozenset({
        "route", "bioavailability_range", "tmax", "cmax", "half_life",
        "primary_source", "study_population",
    }),
    ClaimType.DOSING: frozenset({
        "route", "dose_range", "titration_schedule", "dose_response_source",
        "population", "frequency", "max_dose",
    }),
    ClaimType.DRUG_INTERACTION: frozenset({
        "substrate", "modifier", "cyp_isoform_or_mechanism",
        "magnitude_cmax_auc", "source",
    }),
    ClaimType.SAFETY: frozenset({
        "event_type", "incidence_with_denominator", "severity",
        "reversibility", "study_type", "source",
    }),
    ClaimType.PHYTOCHEMISTRY_QUANTITY: frozenset({
        "compound_with_isomer", "value_with_units", "method", "lod",
        "sample_provenance",
    }),
    ClaimType.LEGAL_REGULATORY: frozenset({
        "jurisdiction", "statutory_citation", "effective_date",
        "scope", "source_url",
    }),
    ClaimType.CULTIVATION_PARAMETER: frozenset({
        "environment", "substrate", "light_spectrum", "photoperiod",
        "climate_zone", "source",
    }),
    ClaimType.MARKET_DATA: frozenset({
        "jurisdiction", "time_period", "methodology", "sample",
        "source_organisation", "data_vintage",
    }),
    ClaimType.EDUCATIONAL: frozenset(),
    ClaimType.OPINION: frozenset(),
}


def required_disclosures(claim_type: ClaimType) -> frozenset[str]:
    """Disclosures that must accompany a claim of this type."""
    return _REQUIRED_DISCLOSURES[claim_type]


def missing_disclosures(claim_type: ClaimType, present: Iterable[str]) -> frozenset[str]:
    """Subset of required disclosures that are missing from ``present``."""
    return required_disclosures(claim_type) - frozenset(present)


@dataclass
class Claim:
    """A cannabis claim with the metadata needed to evaluate it.

    A Claim is *not* a chunk. A chunk may contain several claims. Use
    :func:`Claim.from_text` (or build one directly) when you need the
    typed object — e.g. to score evidence, to run banned-pattern checks,
    or to enforce required disclosures.
    """

    text: str
    claim_type: ClaimType
    sources: tuple[Source, ...] = ()
    disclosures_present: frozenset[str] = field(default_factory=frozenset)
    population: str | None = None
    jurisdiction: str | None = None
    dose_range: str | None = None
    route: str | None = None
    chemotype: str | None = None

    def best_supportable_grade(self) -> EvidenceLevel:
        """The highest grade any of the sources can support, post-downgrades."""
        if not self.sources:
            return EvidenceLevel.UNSUPPORTED
        best = EvidenceLevel.UNSUPPORTED
        live_sources = [s for s in self.sources if s.retraction_status != "retracted"]
        if not live_sources:
            return EvidenceLevel.UNSUPPORTED
        missing_count = len(missing_disclosures(self.claim_type, self.disclosures_present))

        # §VII Level-A floor: "Level A requires a Cochrane/AHRQ/NICE systematic
        # review OR ≥ 2 independent high-quality RCTs in alignment." Gate the
        # single-primary-study cap on the *study design* of the evidence base,
        # NOT on a raw PMID count — otherwise any second co-citation (a
        # mechanism cite, an open-label PK study) would defeat the cap and lift
        # a single pivotal RCT to Level A.
        #
        # - canonical SR/MA: a Cochrane / AHRQ / NICE / IQWiG / USPSTF review
        #   (see :func:`_is_canonical_sr`). ONE is sufficient for the Level-A
        #   floor. A journal SR/MA carried at the same tier (e.g. a single
        #   JAMA / PAIN review) is NOT a Level-A floor on its own — it caps at
        #   Level B below, per the constitution's own §VII wording.
        # - confirmatory RCT: a pre-registered, adequately-powered RCT
        #   (tier-2 JOURNAL_RCT, or a NEJM/JAMA/Lancet RCT carried at tier-1).
        #   ≥ 2 in alignment clear the floor; a single one caps at Level B.
        canonical_srs = [s for s in live_sources if _is_canonical_sr(s)]
        confirmatory_rcts = [
            s for s in live_sources
            if s.tier in (SourceTier.SR_FLAGSHIP, SourceTier.JOURNAL_RCT)
            and s.pre_registered and s.adequately_powered
        ]
        meets_level_a_floor = (
            len(canonical_srs) >= 1 or len(confirmatory_rcts) >= 2
        )

        if meets_level_a_floor:
            # A qualifying body of evidence (≥ 1 SR/MA or ≥ 2 aligned
            # confirmatory RCTs) anchors the *body* at Level A, even when an
            # individual RCT's own base grade is only B. The
            # missing-disclosure penalty still applies so the output stays
            # honest about gaps.
            return _downgrade(EvidenceLevel.A, missing_count)

        # Otherwise the single-primary-study cap governs (§VII): a lone
        # pre-registered, adequately-powered RCT in a major journal — or a lone
        # journal SR/MA that did not clear the canonical-SR floor above — caps
        # at Level B; any other single source (observational, open-label, PK,
        # mechanism) caps at Level C.
        for s in live_sources:
            base = grade_from_source(s)
            grade = apply_grade_modifiers(
                base,
                missing_disclosure_count=missing_count,
                single_primary_study=True,
                pre_registered_major_journal=(
                    # a tier-1 journal SR/MA is major-journal synthesis → B cap
                    s.tier == SourceTier.SR_FLAGSHIP
                    # or a pre-registered, adequately-powered major-journal RCT
                    or (s.pre_registered and s.adequately_powered
                        and s.tier == SourceTier.JOURNAL_RCT)
                ),
            )
            if grade.rank > best.rank:
                best = grade
        return best

    @classmethod
    def from_text(
        cls,
        text: str,
        claim_type: ClaimType = ClaimType.EDUCATIONAL,
        *,
        sources: "tuple[Source, ...]" = (),
        population: "str | None" = None,
        jurisdiction: "str | None" = None,
    ) -> "Claim":
        """Build a minimal :class:`Claim` from a text string.

        Convenience constructor for callers who know the text and type
        but have not yet assembled the full source metadata. All
        optional fields default to empty/None. The caller should attach
        sources and disclosures before calling
        :meth:`best_supportable_grade` — a Claim with no sources
        returns :attr:`EvidenceLevel.UNSUPPORTED` regardless of the
        text wording.

        Example::

            claim = Claim.from_text(
                "CBD is effective for convulsive seizures in Dravet syndrome.",
                ClaimType.CLINICAL_EFFICACY,
                population="paediatric Dravet syndrome",
            )
        """
        return cls(
            text=text,
            claim_type=claim_type,
            sources=sources,
            population=population,
            jurisdiction=jurisdiction,
        )
