#!/usr/bin/env python3
"""Gather correct-PMID candidates for misattributed registry citations.

Companion to ``audit_pmids.py``. For every citation whose PMID does not match
the paper its label names, this runs a PubMed relevance search built from the
label text and prints the top candidates *with their titles* — a dossier for a
human (or an LLM with domain knowledge) to pick the right identifier from.

Why a dossier, not an auto-pick: matching a label like "Huang SM, PNAS 2002,
NADA endocannabinoid" to the right PMID needs judgment. Surname+year alone is
useless (common surnames match thousands of papers) and the labels describe
*findings*, not *title words*, so keyword overlap misfires. So this gathers
real PubMed candidates; the correct one is chosen with judgment, the diff is
approved by a human, and ``audit_pmids.py`` re-verifies — no wrong PMID can
slip back in.

NCBI etiquette: set ``NCBI_API_KEY`` to lift the rate limit to 10 req/s
(otherwise ~3/s). Retries with backoff on HTTP 429. Stdlib only.

    NCBI_API_KEY=xxxx python3 evals/resolve_pmids.py | tee candidates.txt
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_pmids import collect_claimed_pmids, find_suspects, _norm  # noqa: E402

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_UA = {"User-Agent": "cannavec-resolve/1.0"}
_API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
_SLEEP = 0.11 if _API_KEY else 0.36
_DROP = {"label", "name", "pmid", "year", "doi", "the", "and", "for", "with",
         "et", "al", "from", "via"}


def _get(url: str) -> dict:
    """Resilient GET: append api_key, retry with backoff on 429 / transient."""
    if _API_KEY:
        url += ("&" if "?" in url else "?") + "api_key=" + _API_KEY
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, OSError):
            if attempt < 3:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    return {}


def _label_text(ctx: str) -> str:
    m = re.search(r'label\s*=\s*\(?\s*"([^"]+)"', ctx)
    if m:
        return m.group(1)
    m = re.search(r'name\s*=\s*"([^"]+)"', ctx)
    return m.group(1) if m else ctx


def _claim_year(ctx: str, label: str) -> str:
    m = re.search(r"year\s*=\s*(\d{4})", ctx)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:19|20)\d{2}\b", label)
    return m.group(0) if m else ""


def _query(label: str, year: str) -> str:
    words = [w for w in re.findall(r"[A-Za-zΔ′'\-]{3,}", label)
             if w.lower() not in _DROP]
    term = " ".join(words[:12])
    return f"{term} AND {year}[pdat]" if year else term


def _esearch(term: str, retmax: int = 8) -> list[str]:
    url = (f"{_EUTILS}/esearch.fcgi?db=pubmed&retmode=json&sort=relevance"
           f"&retmax={retmax}&term={urllib.parse.quote(term)}")
    return _get(url).get("esearchresult", {}).get("idlist", [])


def _esummary(ids: list[str]) -> dict:
    if not ids:
        return {}
    url = f"{_EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}"
    return _get(url).get("result", {})


def candidates_for(ctx: str):
    label = _label_text(ctx)
    year = _claim_year(ctx, label)
    try:
        ids = _esearch(_query(label, year))
    except (urllib.error.URLError, OSError):
        ids = []
    time.sleep(_SLEEP)
    recs = _esummary(ids) if ids else {}
    time.sleep(_SLEEP)
    out = []
    for pid in ids:
        r = recs.get(pid) or {}
        if not r.get("title"):
            continue
        authors = r.get("authors") or []
        out.append((
            pid,
            authors[0]["name"] if authors else "?",
            (r.get("pubdate") or "")[:4],
            r.get("source", ""),
            r.get("title", ""),
        ))
    return label, out[:5]


def main() -> int:
    suspects = find_suspects(collect_claimed_pmids())
    print(f"\nGathering candidates for {len(suspects)} suspects "
          f"({'with' if _API_KEY else 'no'} NCBI_API_KEY)...\n")
    for old_pmid, fname, ln, _real, ctx in suspects:
        label, cands = candidates_for(ctx)
        print(f"cannavec_science/{fname}:{ln}  OLD={old_pmid}")
        print(f"  claim: {label[:96]}")
        if not cands:
            print("  cands: (none found — search returned nothing)")
        for pid, au, yr, jr, ti in cands:
            print(f"    {pid} | {au[:18]:18} | {yr} | {jr[:24]:24} | {ti[:72]}")
        print()
    print(f"===== {len(suspects)} suspects; pick the correct PMID per block =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
