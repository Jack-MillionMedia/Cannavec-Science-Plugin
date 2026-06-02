#!/usr/bin/env python3
"""Audit every PMID shipped by the curated registries against live PubMed.

For each ``pmid="..."`` literal in ``cannavec_science/*.py`` this fetches the
real PubMed record (NCBI E-utilities ``esummary``) and flags any where **none
of the paper's authors** is named next to the citation in the source — i.e.
the identifier points at a different paper than the registry claims (the
failure mode that shipped a rat breast-implant study as "Hjorthoj 2023").

Matching against *all* listed authors (not just the first) avoids false
positives when a row cites a senior/last author (e.g. "Edery & Mechoulam").

Why this exists: the unit suite is offline (injected fetchers), so a
well-formed-but-wrong PMID passes every test. This is the online check that
the curated identifiers actually resolve to the claimed papers. Stdlib only;
needs network to NCBI. Synthetic retraction seeds (99000xxx) are skipped.

Set ``NCBI_API_KEY`` to lift the rate limit to 10 req/s (retries on 429).
PMIDs listed in ``evals/audit_allowlist.txt`` (one per line, ``#`` comments
allowed) are skipped — for confirmed-correct citations the surname heuristic
cannot see (e.g. an author cited by initials only).

Run from anywhere inside the repo:

    python3 evals/audit_pmids.py
    NCBI_API_KEY=xxxx python3 evals/audit_pmids.py

Exit code is non-zero when any (non-allowlisted) suspect is found, so it is
CI-gateable.
"""
from __future__ import annotations

import glob
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request

_PKG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cannavec_science",
)
_PMID_RE = re.compile(r'pmid\s*=\s*["\'](\d{4,9})["\']')
_API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
_SLEEP = 0.11 if _API_KEY else 0.34
_ALLOWLIST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "audit_allowlist.txt"
)


def _load_allowlist() -> set[str]:
    """PMIDs confirmed-correct but flagged by the surname heuristic.

    One PMID per line; ``#`` comments allowed. Used for citations the heuristic
    cannot confirm (e.g. an author cited only by initials, or a registry that
    names a study by group rather than by any indexed author surname).
    """
    out: set[str] = set()
    try:
        with open(_ALLOWLIST_PATH, encoding="utf-8") as fh:
            for line in fh:
                tok = line.split("#", 1)[0].strip()
                if tok.isdigit():
                    out.add(tok)
    except FileNotFoundError:
        pass
    return out


def _norm(s: str) -> str:
    """Diacritic-fold + lowercase + strip to letters/spaces for matching."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]+", " ", s.lower())


def collect_claimed_pmids() -> dict[str, tuple[str, int, str]]:
    """Map each registry PMID -> (filename, line, nearby source context)."""
    claims: dict[str, tuple[str, int, str]] = {}
    for path in sorted(glob.glob(os.path.join(_PKG, "*.py"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            for m in _PMID_RE.finditer(line):
                pmid = m.group(1)
                if pmid.startswith("99000"):  # documented synthetic seeds
                    continue
                # Tight window: capture this citation's own label without
                # bleeding into a neighbouring citation (avoids false negatives).
                ctx = " ".join(lines[max(0, i - 6):i + 1])
                claims.setdefault(pmid, (os.path.basename(path), i + 1, ctx))
    return claims


def _esummary(ids: list[str]) -> dict:
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
        "db=pubmed&retmode=json&id=" + ",".join(ids)
    )
    if _API_KEY:
        url += "&api_key=" + _API_KEY
    req = urllib.request.Request(url, headers={"User-Agent": "cannavec-audit/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("result", {})
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    return {}


def _author_tokens(authors: list) -> set[str]:
    """Normalised surname-ish tokens (len>=4) across *all* listed authors."""
    toks: set[str] = set()
    for a in authors:
        for t in _norm(a.get("name", "")).split():
            if len(t) >= 4:
                toks.add(t)
    return toks


def find_suspects(claims: dict[str, tuple[str, int, str]]) -> list[tuple]:
    allow = _load_allowlist()
    pmids = sorted(claims)
    print(f"Auditing {len(pmids)} registry PMIDs against live PubMed"
          f"{' (NCBI_API_KEY set)' if _API_KEY else ''}"
          f"{f'; {len(allow)} allowlisted' if allow else ''}...\n")
    real: dict[str, tuple | None] = {}
    for k in range(0, len(pmids), 100):
        chunk = pmids[k:k + 100]
        try:
            data = _esummary(chunk)
        except (urllib.error.URLError, OSError) as e:
            print(f"  fetch error for chunk at {k}: {e}")
            continue
        for pid in chunk:
            rec = data.get(pid) or {}
            authors = rec.get("authors") or []
            if not rec or rec.get("error") or not rec.get("title"):
                real[pid] = None
            else:
                real[pid] = (
                    _author_tokens(authors),
                    authors[0]["name"] if authors else "?",
                    (rec.get("pubdate") or "")[:4],
                    rec.get("source", ""),
                    rec.get("title", ""),
                )
        time.sleep(_SLEEP)

    suspects: list[tuple] = []
    for pid in pmids:
        if pid in allow:
            continue
        fname, ln, ctx = claims[pid]
        info = real.get(pid)
        if info is None:
            suspects.append((pid, fname, ln, "NOT FOUND on PubMed", ""))
            continue
        tokens, first, yr, journal, title = info
        nctx = _norm(ctx)
        # Flag only when NONE of the paper's authors is named near the cite.
        if tokens and not any(t in nctx for t in tokens):
            suspects.append((
                pid, fname, ln,
                f"{first} et al. | {yr} {journal} | {title[:72]}",
                ctx.strip()[-92:],
            ))
    return suspects


def main() -> int:
    claims = collect_claimed_pmids()
    suspects = find_suspects(claims)
    print(f"===== {len(suspects)} SUSPECT / {len(claims)} audited =====\n")
    for pid, fname, ln, real_s, ctx in suspects:
        print(f"PMID {pid}  cannavec_science/{fname}:{ln}")
        print(f"   PubMed: {real_s}")
        if ctx:
            print(f"   code  : ...{ctx}")
        print()
    return 1 if suspects else 0


if __name__ == "__main__":
    raise SystemExit(main())
