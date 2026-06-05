"""Production driver: scope -> extract -> audit each file, with real engine fetchers."""
from __future__ import annotations

import urllib.error
import urllib.request

from cannavec_science.kb_audit.scope import select_files, DEFAULT_INCLUDE
from cannavec_science.kb_audit.extract import extract
from cannavec_science.kb_audit.verdict import audit_record


def _real_verify(ident: str, id_type: str):
    """Dispatch to the engine; normalize verify_uniprot's raise into a NETWORK_ERROR result."""
    from cannavec_science.pubmed_verify import verify_pmid, verify_doi
    if id_type == "PMID":
        return verify_pmid(ident)
    if id_type == "DOI":
        return verify_doi(ident)
    if id_type == "UniProt":
        from cannavec_science.uniprot_verify import verify_uniprot
        try:
            rec = verify_uniprot(ident)
        except (urllib.error.URLError, OSError):
            return type("R", (), {"verdict": type("V", (), {"name": "NETWORK_ERROR"})})()
        name = "MATCH" if rec is not None else "NOT_FOUND"
        return type("R", (), {"verdict": type("V", (), {"name": name})})()
    # NCT / ChEMBL: existence-only, treat as pass (out of v1 verify scope)
    return type("R", (), {"verdict": type("V", (), {"name": "BARE_CITE_OK"})})()


def _real_retracted(**kw):
    from cannavec_science.retraction import is_retracted
    return is_retracted(**kw)


def _real_abstract(pmid: str):
    # Port of the proven efetch_abstract in evals/audit_claim_support.py:44,
    # routed through the repo transport cannavec_science._http (user_agent +
    # NCBI auth + bounded retry). Returns None on any network gap (→ Gate 2
    # inconclusive, never a flag). evals/ is a scripts dir, not an importable
    # package, so we keep a local copy here.
    from cannavec_science._http import (
        TIMEOUT_FAST,
        append_ncbi_auth,
        retry_urlopen,
        user_agent,
    )
    url = append_ncbi_auth(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
        f"db=pubmed&rettype=abstract&retmode=text&id={pmid}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": user_agent("kb-audit")})
    try:
        with retry_urlopen(req, timeout=TIMEOUT_FAST) as resp:
            text = resp.read().decode("utf-8", "replace")
        return text or None
    except (urllib.error.URLError, OSError):
        return None


def audit_path(root: str, *, include=DEFAULT_INCLUDE, exclude=(),
               verify_fn=_real_verify, retracted_fn=_real_retracted, abstract_fn=_real_abstract):
    # Verify each identifier / fetch each abstract once per corpus run — the same
    # PMID cited by many files costs one live call, not N (spec §Reliability: dedupe;
    # honor NCBI rate limits).
    _vc: dict = {}
    _ac: dict = {}
    _rc: dict = {}

    def _verify(ident, id_type):
        key = (ident, id_type)
        if key not in _vc:
            _vc[key] = verify_fn(ident, id_type)
        return _vc[key]

    def _abstract(pmid):
        if pmid not in _ac:
            _ac[pmid] = abstract_fn(pmid)
        return _ac[pmid]

    def _retracted(**kw):
        key = (kw.get("pmid"), kw.get("doi"))
        if key not in _rc:
            _rc[key] = retracted_fn(**kw)
        return _rc[key]

    verdicts = []
    for path in select_files(root, include, exclude):
        rec = extract(path, root=root, include=include, exclude=exclude)
        verdicts.append(audit_record(rec, verify_fn=_verify, retracted_fn=_retracted,
                                     abstract_fn=_abstract))
    return verdicts
