"""Single source of truth for the cross-cutting scientific-identifier patterns
(§I PMID / DOI / NCT).

Before this module these patterns were defined independently in
``pubmed_verify``, ``retraction``, ``ctgov_discover``, ``__main__`` and
``kb_audit.extract``; the ``NCT\\d{8}`` core appeared in four places and a future
edit to one could silently diverge from the others. They now live here, compiled
once, so a change is reviewed against every sibling.

TWO deliberate scan variants exist for PMID and DOI. They are NOT drift — do not
"unify" them:

* **PMID.** The bulk verifier scans only *prefixed* tokens (``PMID_PREFIXED_SCAN``)
  so it never spends a verify API call on a bare year or count. The §VIII
  retraction sweep must catch a retracted PMID even when written as a *bare*
  number (``PMID_BARE_SCAN``) — and is bounded to ``\\d{6,9}`` precisely so a
  4-digit year ("2017") is never mistaken for a PMID. The prefixed scan is safe
  at ``{4,9}`` *only because* it requires the literal "PMID" prefix; widening the
  bare scan to ``{4,9}`` would reintroduce the year false-positive.
* **DOI.** ``DOI_SCAN`` (verifier) accepts the broad trailing class DOIs
  legitimately use ( ``():;<>`` ). ``DOI_RETRACTION_SCAN`` (§VIII sweep) keeps the
  historically narrower trailing class so its registry match set is unchanged.

Lane-specific parsers that match a *particular upstream format* — quickgo's
``PMID:1234`` GO-annotation refs, bioRxiv DOIs, UniProt accessions, and
``evidence``'s multi-registry (NCT/ISRCTN/EudraCT/ACTRN) pre-registration
detector — intentionally stay in their own modules. They are not the general
identifier and must not be folded in here.

Stdlib-only; imports nothing from the package, so it is safe to import anywhere.
"""

from __future__ import annotations

import re

# ── Shared core (the duplicated magic number, defined once) ──────────────────
NCT_CORE = r"NCT\d{8}"  # ClinicalTrials.gov registry id

# ── NCT ──────────────────────────────────────────────────────────────────────
# Exact-match one id. The CLI verify classifier accepts either case; the ctgov
# lane validates case-sensitively (its input is already an upper-case NCT id).
NCT_EXACT_CI = re.compile(rf"^{NCT_CORE}$", re.IGNORECASE)
NCT_EXACT = re.compile(rf"^{NCT_CORE}$")
# Find NCT ids within free text (kb-audit citation extraction).
NCT_SCAN_CI = re.compile(NCT_CORE, re.IGNORECASE)

# ── PMID ─────────────────────────────────────────────────────────────────────
# Validate a single bare PMID argument (the verify CLI).
PMID_EXACT = re.compile(r"^\d{4,9}$")
# Scan PREFIXED PMIDs only — the bulk verifier never follows a bare number.
PMID_PREFIXED_SCAN = re.compile(r"\bPMID[:\s#]*([0-9]{4,9})\b", re.IGNORECASE)
# Scan BARE PMIDs for the §VIII retraction sweep; >= 6 digits so a year is not
# mistaken for a PMID. (See module docstring — do not widen to {4,9}.)
PMID_BARE_SCAN = re.compile(r"\b(?:PMID:?\s*)?(\d{6,9})\b", re.IGNORECASE)

# ── DOI ──────────────────────────────────────────────────────────────────────
# Verifier scan — broad trailing class (DOIs legitimately contain ():;<> ).
DOI_SCAN = re.compile(
    r"\b(?:doi[:\s]*)?(?P<doi>10\.[0-9]{4,9}/[\w\.\-/:();<>]+)",
    re.IGNORECASE,
)
# §VIII retraction sweep — narrower historical trailing class, kept verbatim so
# the registry match set is unchanged.
DOI_RETRACTION_SCAN = re.compile(
    r"\b(?:doi:?\s*)?(10\.\d{4,9}/[\w\.\-/]+)",
    re.IGNORECASE,
)
