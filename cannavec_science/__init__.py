"""Cannavec Science — research-grade cannabis-science primitives.

v0.4 industry-expert-depth build for the working researcher. Inherits the
full v0.3 routing-and-surfacing surface and adds two new registries —
**analytical chemistry** (decarboxylation kinetics, HPLC/GC-MS method
validation, chemovar classification, vapor pyrolysis byproducts; ≥ 8
rows) and **cultivation science** (UV-B effects, trichome biology,
THCA-/CBDA-synthase genetics, botanical taxonomy; ≥ 6 rows) — every
row anchored to a primary PubMed / DOI citation per Constitution §I.
Additional v0.4 closures: the ``Answer.notes`` rendering bug fixed so
0-claim classification messages now actually surface; a sibling banned
pattern catches the abstract framing of indica/sativa-as-pharmacology
while leaving research-grade botanical taxonomy untouched.

Backbone unchanged: GRADE evidence-grading, banned-pattern detection,
safety preflight, seven phytochemistry rigor checks (incl. entourage-
overclaim detector), PubMed/Crossref citation verification with forward-
citation network analysis, retraction enforcement at composition time,
eleven science registries (major / minor cannabinoids, terpenes, drug
interactions, adverse events, populations, contraindications,
pharmacogenomics, endocannabinoidome, analytical chemistry, cultivation
science) with ``last_verified`` + ``watch_pmids`` freshness fields, live
discovery across eleven primary scientific sources (PubMed, ChEMBL,
CT.gov, PubChem, PharmGKB, RCSB, Open Targets, GWAS, BindingDB +
bioRxiv + medRxiv preprint lanes), researcher-workflow scaffolders
(PICO, power calculation, GRADE evidence-profile table, IRB protocol
skeleton), regulatory-feasibility advisory (US / EU / Canada / UK),
and BibTeX/RIS/CSL-JSON bibliography export with inline GRADE
annotation.

Stdlib-only. Researcher audience only. Five slash commands.
"""

__version__ = "0.4.0"

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
