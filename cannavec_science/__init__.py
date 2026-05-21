"""Cannavec Science — research-grade cannabis-science primitives.

v0.2 elite-development build for the working researcher: GRADE evidence-
grading, banned-pattern detection, safety preflight, seven phytochemistry
rigor checks (incl. entourage-overclaim detector), PubMed/Crossref
citation verification with forward-citation network analysis, retraction
enforcement at composition time, eight science registries with
``last_verified`` + ``watch_pmids`` freshness fields, live discovery
across eleven primary scientific sources (PubMed, ChEMBL, CT.gov,
PubChem, PharmGKB, RCSB, Open Targets, GWAS, BindingDB + the v0.2
preprint lanes bioRxiv and medRxiv), researcher-workflow scaffolders
(PICO, power calculation, GRADE evidence-profile table, IRB protocol
skeleton), regulatory-feasibility advisory (US / EU / Canada / UK),
endocannabinoidome reference, and BibTeX/RIS/CSL-JSON bibliography
export with inline GRADE annotation.

Stdlib-only. Researcher audience only. Five slash commands.
"""

__version__ = "0.2.0"

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
