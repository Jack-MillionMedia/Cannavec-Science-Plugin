#!/usr/bin/env python3
"""Propose correct PMIDs for misattributed registry citations.

Companion to ``audit_pmids.py``. For every citation whose PMID does not match
the paper named in its label, this searches PubMed (E-utilities ``esearch``)
for the paper the label *describes* — first-author surname + year + title
terms — re-fetches the candidate summaries, and proposes the best match.

The labels in the registries are accurate; only the identifiers drifted (the
signature of hallucinated PMIDs). So re-resolving from the label recovers the
intended paper. NOTHING is edited here: this prints a review sheet (and, with
``--json``, a machine-readable map) for a human to approve. Corrections are
applied separately and ``audit_pmids.py`` re-verifies, so a wrong proposal
cannot slip in silently.

Confidence:
  HIGH   — candidate first-author surname matches the claim AND year is within
           +/-1 AND >=1 title term overlaps. Safe to apply after a glance.
  REVIEW — a plausible candidate exists but one signal disagrees. Eyeball it.
  NONE   — no candidate matched; the row likely has no real source -> remove
           it (Constitution sec. I: a claim with no verifiable primary source
           is Unsupported / refused).

Stdlib only; needs network to NCBI. Run from anywhere in the repo:

    python3 evals/resolve_pmids.py
    python3 evals/resolve_pmids.py --json > proposals.json
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
_STOP = {
    "et", "al", "the", "and", "for", "with", "from", "study", "trial", "review",
    "analysis", "human", "vitro", "vivo", "data", "based", "using", "via",
    "effects", "effect", "role", "novel", "report", "case", "series", "label",
}


def _label_text(ctx: str) -> str:
    """Pull the citation's label string out of the source window."""
    m = re.search(r'label\s*=\s*\(?\s*"([^"]+)"', ctx)
    if m:
        return m.group(1)
    m = re.search(r'name\s*=\s*"([^"]+)"', ctx)
    return m.group(1) if m else ctx


def _claim_surname(label: str) -> str:
    """First plausible author surname in the label (handles diacritics)."""
    m = re.search(r"([A-ZÀ-ž][a-zÀ-ž'\-]{2,})", label)
    return m.group(1) if m else ""


def _claim_year(ctx: str, label: str) -> str:
    m = re.search(r"year\s*=\s*(\d{4})", ctx)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:19|20)\d{2}\b", label)
    return m.group(0) if m else ""


def _claim_terms(label: str, surname: str) -> list[str]:
    sn = _norm(surname)
    seen, terms = set(), []
    for w in re.findall(r"[A-Za-z][A-Za-z\-]{4,}", label):
        wn = _norm(w).strip()
        if wn and wn not in _STOP and wn != sn and wn not in seen:
            seen.add(wn)
            terms.append(w)
    return terms[:6]


def _esearch(term: str, retmax: int = 6) -> list[str]:
    url = (f"{_EUTILS}/esearch.fcgi?db=pubmed&retmode=json&retmax={retmax}"
           f"&term={urllib.parse.quote(term)}")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("esearchresult", {}).get("idlist", [])


def _esummary(ids: list[str]) -> dict:
    if not ids:
        return {}
    url = f"{_EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("result", {})


def _score(claim_sn: str, claim_yr: str, terms: list[str], rec: dict) -> int:
    authors = rec.get("authors") or []
    real_sn = _norm(authors[0]["name"]).split()[0] if authors else ""
    title = _norm(rec.get("title", ""))
    yr = (rec.get("pubdate") or "")[:4]
    s = 0
    if claim_sn and real_sn and _norm(claim_sn).split()[0] == real_sn:
        s += 3
    if claim_yr and yr and abs(int(yr) - int(claim_yr)) <= 1:
        s += 1
    s += sum(1 for t in terms if _norm(t).strip() in title)
    return s


def resolve_one(ctx: str) -> tuple[str, dict | None, str]:
    label = _label_text(ctx)
    surname = _claim_surname(label)
    year = _claim_year(ctx, label)
    terms = _claim_terms(label, surname)
    queries = []
    if surname and year:
        queries.append(f"{surname}[Author] AND {year}[pdat]")
    if terms and year:
        queries.append(f'{" ".join(terms[:4])} AND {year}[pdat]')
    if terms:
        queries.append(" ".join(terms[:5]))
    candidates: list[str] = []
    for q in queries:
        try:
            candidates = _esearch(q)
        except (urllib.error.URLError, OSError):
            candidates = []
        if candidates:
            break
        time.sleep(0.34)
    recs = _esummary(candidates)
    best, best_score = None, 0
    for pid in candidates:
        rec = recs.get(pid) or {}
        if not rec.get("title"):
            continue
        sc = _score(surname, year, terms, rec)
        if sc > best_score:
            best, best_score = pid, sc
    if best is None:
        return label, None, "NONE"
    rec = recs[best]
    authors = rec.get("authors") or []
    real_sn = _norm(authors[0]["name"]).split()[0] if authors else ""
    yr = (rec.get("pubdate") or "")[:4]
    conf = "HIGH" if (best_score >= 4 and _norm(surname).split()[0:1] == [real_sn]
                      and yr and year and abs(int(yr) - int(year)) <= 1) else "REVIEW"
    return label, {"pmid": best, "title": rec.get("title", ""),
                   "author": authors[0]["name"] if authors else "?",
                   "year": yr, "journal": rec.get("source", "")}, conf


def main() -> int:
    as_json = "--json" in sys.argv
    suspects = find_suspects(collect_claimed_pmids())
    proposals: dict[str, dict] = {}
    if not as_json:
        print(f"\nResolving {len(suspects)} suspects against PubMed...\n")
    for old_pmid, fname, ln, _real, ctx in suspects:
        label, match, conf = resolve_one(ctx)
        time.sleep(0.34)  # polite to NCBI
        entry = {"file": f"cannavec_science/{fname}", "line": ln,
                 "old": old_pmid, "confidence": conf, "claim": label[:90],
                 "new": (match or {}).get("pmid"),
                 "matched": None if not match else
                 f"{match['author']} {match['year']} {match['journal']} | {match['title'][:70]}"}
        proposals[old_pmid] = entry
        if not as_json:
            arrow = entry["new"] or "—"
            print(f"[{conf:6}] cannavec_science/{fname}:{ln}  {old_pmid} -> {arrow}")
            print(f"   claim : {label[:90]}")
            print(f"   match : {entry['matched'] or '(no confident candidate — consider removing the row)'}\n")
    if as_json:
        print(json.dumps(proposals, indent=2, ensure_ascii=False))
    else:
        n_high = sum(1 for e in proposals.values() if e["confidence"] == "HIGH")
        n_none = sum(1 for e in proposals.values() if e["confidence"] == "NONE")
        print(f"===== {len(proposals)} proposals: {n_high} HIGH, "
              f"{len(proposals) - n_high - n_none} REVIEW, {n_none} NONE =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
