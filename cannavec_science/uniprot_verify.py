"""UniProt accession verification (spec 003 US5 / FR-005).

Constitution §I names "PMID, DOI, ChEMBL ID, NCT ID, or UniProt
accession" as the five primary-source identifier shapes. This module
resolves a UniProt accession to a typed record by hitting the public
UniProt REST entry endpoint.

Design rules (matched to ``pubmed_verify`` and ``chembl_discover``):

- **Stdlib-only.** ``urllib`` transport, ``json`` parsing.
- **Network is opt-in.** The default fetcher only fires when the
  caller explicitly invokes :func:`verify_uniprot`. Tests inject a
  fixture fetcher so the offline suite still passes.
- **Conservative on failure.** Network / parse / not-found errors
  return ``None`` rather than swallowing the exception.

Endpoint: ``https://rest.uniprot.org/uniprotkb/{accession}.json``
(JSON returns the same payload as the legacy ``uniprot.org/uniprot/``
endpoint with a stable schema).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from cannavec_science._http import TIMEOUT_FAST, retry_urlopen, user_agent


__all__ = [
    "UniProtRecord",
    "Fetcher",
    "default_uniprot_fetcher",
    "fetch_uniprot_record",
    "verify_uniprot",
    "is_uniprot_accession",
]


# The canonical UniProt accession regex (Swiss-Prot + TrEMBL):
#   [OPQ][0-9][A-Z0-9]{3}[0-9]
#   [A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}
# Tightened to anchored full-string match.
_UNIPROT_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)


_UNIPROT_ENTRY_URL = "https://rest.uniprot.org/uniprotkb/{acc}.json"
_UNIPROT_PUBLIC_URL = "https://www.uniprot.org/uniprotkb/{acc}/entry"


def is_uniprot_accession(value: str) -> bool:
    """Strict shape check — does ``value`` look like a UniProt accession?"""
    if not value:
        return False
    return bool(_UNIPROT_RE.match(value.strip().upper()))


class Fetcher(Protocol):
    def __call__(self, url: str) -> str: ...


def default_uniprot_fetcher(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent("uniprot-verify"),
            "Accept": "application/json",
        },
    )
    with retry_urlopen(req, timeout=TIMEOUT_FAST) as resp:
        return resp.read().decode("utf-8")


@dataclass(frozen=True)
class UniProtRecord:
    """Minimal typed UniProt entry."""

    accession: str
    protein_name: str
    gene_symbol: Optional[str]
    organism: str
    organism_taxon_id: Optional[int]
    sequence_length: Optional[int]
    reviewed: bool
    url: str

    def to_dict(self) -> dict:
        return {
            "accession": self.accession,
            "protein_name": self.protein_name,
            "gene_symbol": self.gene_symbol,
            "organism": self.organism,
            "organism_taxon_id": self.organism_taxon_id,
            "sequence_length": self.sequence_length,
            "reviewed": self.reviewed,
            "url": self.url,
        }


def _parse_uniprot_response(accession: str, body: str) -> Optional[UniProtRecord]:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    # Protein description — prefer recommended name; fall back to submitted.
    descr = data.get("proteinDescription") or {}
    rec_name = (descr.get("recommendedName") or {}).get("fullName") or {}
    name = rec_name.get("value") if isinstance(rec_name, dict) else None
    if not name:
        for sub in descr.get("submissionNames") or []:
            sub_name = (sub or {}).get("fullName") or {}
            v = sub_name.get("value") if isinstance(sub_name, dict) else None
            if v:
                name = v
                break
    if not name:
        # Some entries store the name under alternative names.
        for alt in descr.get("alternativeNames") or []:
            alt_name = (alt or {}).get("fullName") or {}
            v = alt_name.get("value") if isinstance(alt_name, dict) else None
            if v:
                name = v
                break
    gene_symbol = None
    for g in data.get("genes") or []:
        gn = (g or {}).get("geneName") or {}
        v = gn.get("value") if isinstance(gn, dict) else None
        if v:
            gene_symbol = v
            break
    organism = ""
    organism_id: Optional[int] = None
    org = data.get("organism") or {}
    if isinstance(org, dict):
        sci = org.get("scientificName") or org.get("commonName")
        if sci:
            organism = sci
        tax = org.get("taxonId")
        if isinstance(tax, int):
            organism_id = tax
    seq_len = None
    seq = data.get("sequence") or {}
    if isinstance(seq, dict):
        ln = seq.get("length")
        if isinstance(ln, int):
            seq_len = ln
    reviewed = (data.get("entryType") or "").lower().startswith(
        "uniprotkb reviewed"
    )
    return UniProtRecord(
        accession=accession.upper(),
        protein_name=name or "",
        gene_symbol=gene_symbol,
        organism=organism,
        organism_taxon_id=organism_id,
        sequence_length=seq_len,
        reviewed=reviewed,
        url=_UNIPROT_PUBLIC_URL.format(acc=accession.upper()),
    )


def fetch_uniprot_record(
    accession: str,
    *,
    fetcher: Optional[Fetcher] = None,
) -> Optional[UniProtRecord]:
    """Fetch + parse a UniProt entry. Returns ``None`` on miss / parse error."""
    if not is_uniprot_accession(accession):
        return None
    f = fetcher or default_uniprot_fetcher
    url = _UNIPROT_ENTRY_URL.format(acc=accession.strip().upper())
    try:
        body = f(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return _parse_uniprot_response(accession.strip(), body)


def verify_uniprot(
    accession: str,
    *,
    fetcher: Optional[Fetcher] = None,
) -> Optional[UniProtRecord]:
    """Public verification entry point. Returns ``None`` on miss."""
    return fetch_uniprot_record(accession, fetcher=fetcher)
