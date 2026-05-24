"""Cannavec Science — research-grade cannabis-science primitives.

v0.5 industry-expert-clinical-depth build for the working researcher.
Inherits the full v0.4 industry-expert-depth surface and adds **five
new curated registries** plus a **twelfth primary-source live lane**:

- **Clinical pharmacokinetics** (≥ 8 rows): THC inhaled / oral PK,
  CBD oral PK + food effect (Birnbaum 2019), 11-OH-Δ⁹-THC active
  metabolite (Wall 1983), nabiximols oromucosal (Karschner 2011),
  plasma distribution (Garrett 1977), urine detection window
  (Huestis 1996).
- **Cannabis use disorder & withdrawal** (≥ 6 rows): DSM-5 CUD
  framework (Hasin 2013), CUDIT-R (Adamson 2010), Cannabis Withdrawal
  Scale (Allsop 2011), NESARC-III prevalence (Hasin 2015),
  heritability (Verweij 2010), adolescent-onset telescoping
  (Chen 2009 / Hall & Degenhardt 2009).
- **Cannabinoid hyperemesis syndrome** (≥ 4 rows): Sorensen 2017 SR
  + Allen 2004 + Simonetto 2012 case series, Rome IV framework
  (Venkatesan 2019), capsaicin acute-phase treatment (Dezieck 2017),
  post-legalization ED epidemiology (Kim 2018).
- **eCBome inhibitor pharmacology** (≥ 5 rows): PF-04457845 cannabis-
  withdrawal Phase 2a (D'Souza 2019) + OA-pain Phase 2 (Huggins 2012),
  BIA 10-2474 Rennes disaster (Kerbrat 2016) WITH explicit
  off-target-serine-hydrolase disambiguation (van Esbroeck 2017),
  MAGL inhibitor ABX-1431 (Cisar 2018), dual FAAH/MAGL JZL195
  (Long 2009).
- **Cannabinoid biosynthesis pathway** (≥ 5 rows): OLS + OAC
  polyketide entry (Taura 2009 + Gagne 2012), CBGAS prenyltransferase
  (Page 2011), THCA synthase (Sirikantaramas 2004), CBDA synthase
  (Taura 1996), yeast heterologous expression (Luo 2019 Nature).
- **Europe PMC** twelfth primary-source live-discovery lane — complement
  to PubMed; indexes PubMed + PMC full-text + European
  non-MEDLINE-indexed journals.

Backbone unchanged: GRADE evidence-grading, banned-pattern detection,
safety preflight, seven phytochemistry rigor checks (incl. entourage-
overclaim detector), PubMed/Crossref citation verification with forward-
citation network analysis, retraction enforcement at composition time,
**sixteen** science registries with ``last_verified`` + ``watch_pmids``
freshness fields, live discovery across **twelve** primary scientific
sources (PubMed, ChEMBL, CT.gov, PubChem, PharmGKB, RCSB, Open Targets,
GWAS, BindingDB, bioRxiv, medRxiv, Europe PMC), researcher-workflow
scaffolders (PICO, power calculation, GRADE evidence-profile table,
IRB protocol skeleton), regulatory-feasibility advisory (US / EU /
Canada / UK), BibTeX/RIS/CSL-JSON bibliography export with inline
GRADE annotation, and the v0.4 ``Answer.notes`` render closure.

Stdlib-only. Researcher audience only. Five slash commands.
"""

__version__ = "0.5.0"

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
