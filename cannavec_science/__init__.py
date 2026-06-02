"""Cannavec Science — research-grade cannabis-science primitives.

v0.6 research-domain-breadth build for the working researcher.
Inherits the full v0.5 industry-expert-clinical-depth surface and adds
**four new curated registries** plus a **reporting-rigor module** and
a **thirteenth primary-source live lane**:

- **Pain medicine** (≥ 7 rows): NASEM 2017 chapter-4 chronic-pain
  conclusive-evidence finding anchored to Whiting 2015 JAMA SR (PMID
  26103030), Stockings 2018 PAIN SR (PMID 29847469), Mücke 2018
  Cochrane neuropathic (PMID 29513392), Boehnke 2019 J Pain MMJ
  prospective cohort (PMID 31237829), Andreae 2015 IPD meta-analysis
  (PMID 26362106), de Vita 2018 experimental-pain SR (PMID 30422266).
- **Cannabis-and-psychosis psychiatry** (≥ 6 rows): Di Forti 2019
  EU-GEI Lancet Psychiatry (PMID 30902669), Marconi 2016 Schizophr
  Bull dose-response SR (PMID 26884547), Vaucher 2018 Mendelian
  randomization Mol Psychiatry (PMID 28115737), Bhattacharyya 2009
  acute-THC fMRI Arch Gen Psychiatry (PMID 19349314), Hjorthøj 2023
  Danish national-register cohort (PMID 37140715), Murray 2017
  Lancet Psychiatry narrative review.
- **Driving-impairment science** (≥ 5 rows): Compton 2017 NHTSA
  Virginia Beach case-control crash-risk (DOT HS 812 411), Hartman
  2015 Clin Chem plasma-THC dose-response (PMID 25371545), Marcotte
  2022 JAMA Psychiatry driving-simulator RCT (PMID 35080588),
  Brubacher 2022 NEJM BC post-legalization cohort (PMID 35020985),
  Bondallaz 2016 Forensic Sci Int SR (PMID 27701009). The SCIENCE,
  not the LAW — per-se law surfaces remain in the parent plugin.
- **PTSD / anxiety / sleep** (≥ 5 rows): Bonn-Miller 2021 PLOS One
  PTSD smoked-cannabis cross-over RCT (PMID 33730032) with the
  largely-negative primary endpoint honestly stated; Crippa 2011
  J Psychopharmacol CBD-SAD SPECT acute challenge (PMID 20829306);
  Bergamaschi 2011 Neuropsychopharm CBD-SAD public-speaking (PMID
  21307846); Bedi 2010 Drug Alcohol Depend biphasic acute Δ⁹-THC
  anxiety dose-response (PMID 19897322); Walsh 2017 Sleep Med Rev
  cannabinoids-and-sleep systematic review (PMID 28392485).
- **Reporting-rigor module**: six deterministic EQUATOR-network +
  risk-of-bias detectors — CONSORT-2010 for RCTs (Schulz 2010 BMJ
  PMID 20335313), PRISMA-2020 for SRs (Page 2021 BMJ PMID 33781993),
  STROBE for observational studies (von Elm 2007 PMID 17938396),
  ROB-2 for RCT bias (Sterne 2019 BMJ PMID 31462531), ROBINS-I for
  non-randomized intervention studies (Sterne 2016 BMJ PMID
  27733354), AMSTAR-2 for SR quality (Shea 2017 BMJ PMID 28935701).
  Detectors integrate into ``RigorCheckReport`` and surface in the
  ``rigor`` subcommand output.
- **OpenAlex** thirteenth primary-source live-discovery lane —
  open scholarly citation graph (PubMed + preprints + conference
  proceedings + open citation network).

Backbone unchanged: GRADE evidence-grading, banned-pattern detection,
safety preflight, seven phytochemistry rigor checks (incl. entourage-
overclaim detector), PubMed/Crossref citation verification with forward-
citation network analysis, retraction enforcement at composition time,
**twenty** science registries with ``last_verified`` + ``watch_pmids``
freshness fields, live discovery across **thirteen** primary scientific
sources (PubMed, ChEMBL, CT.gov, PubChem, PharmGKB, RCSB, Open Targets,
GWAS, BindingDB, bioRxiv, medRxiv, Europe PMC, OpenAlex), researcher-
workflow scaffolders (PICO, power calculation, GRADE evidence-profile
table, IRB protocol skeleton), regulatory-feasibility advisory (US /
EU / Canada / UK), BibTeX/RIS/CSL-JSON bibliography export with inline
GRADE annotation, and the v0.4 ``Answer.notes`` render closure.

Stdlib-only. Researcher audience only. Five slash commands.
"""

__version__ = "0.6.0"

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
