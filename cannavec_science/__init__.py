"""Cannavec Science — research-grade cannabis-science primitives.

MVP for the working researcher: GRADE evidence-grading, banned-pattern
detection, safety preflight, six phytochemistry rigor checks,
PubMed/Crossref citation verification, retraction enforcement, eight
science registries, live discovery (PubMed + ChEMBL + ClinicalTrials.gov),
BibTeX/RIS/CSL-JSON bibliography export.

Stdlib-only. Researcher audience only. Five slash commands.
"""

__version__ = "0.1.0"

from cannavec_science.evidence import (
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
    grade_from_source,
    source_authority_weight,
)
from cannavec_science.uncertainty import grade_wording_consistency
from cannavec_science.adverse_events import build_claim as build_claim_for_adverse_event
from cannavec_science.contraindications import build_claim as build_claim_for_contraindication
from cannavec_science.interactions import build_claim as build_claim_for_interaction
from cannavec_science.populations import build_claim as build_claim_for_population
from cannavec_science.answer import compose_answer

__all__ = [
    "__version__",
    "Claim",
    "ClaimType",
    "EvidenceLevel",
    "Source",
    "SourceTier",
    "grade_from_source",
    "source_authority_weight",
    "grade_wording_consistency",
    "build_claim_for_adverse_event",
    "build_claim_for_contraindication",
    "build_claim_for_interaction",
    "build_claim_for_population",
    "compose_answer",
]
