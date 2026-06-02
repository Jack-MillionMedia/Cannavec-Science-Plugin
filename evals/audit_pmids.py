#!/usr/bin/env python3
"""Audit every PMID shipped by the curated registries against live PubMed.

For each ``pmid="..."`` literal in ``cannavec_science/*.py`` this fetches the
real PubMed record (NCBI E-utilities ``esummary``) and flags any whose real
first-author surname does **not** appear next to the citation in the source —
i.e. the identifier points at a different paper than the registry claims
(the failure mode that shipped a rat breast-implant study as "Hjorthoj 2023").

Why this exists: the unit suite is offline (injected fetchers), so a
well-formed-but-wrong PMID passes every test. This is the online check that
the curated identifiers actually resolve to the claimed papers. Stdlib only;
needs network to NCBI. Synthetic retraction seeds (99000xxx) are skipped.

Run from anywhere inside the repo:

    python3 evals/audit_pmids.py

Exit code is non-zero when any suspect is found, so it is CI-gateable.
Some flags are expected false positives (a row that names a non-first author,
or a diacritic spelling); confirm each against PubMed before editing data.
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
    req = urllib.request.Request(url, headers={"User-Agent": "cannavec-audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("result", {})


def find_suspects(claims: dict[str, tuple[str, int, str]]) -> list[tuple]:
    pmids = sorted(claims)
    print(f"Auditing {len(pmids)} registry PMIDs against live PubMed...\n")
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
                    authors[0]["name"] if authors else "",
                    (rec.get("pubdate") or "")[:4],
                    rec.get("source", ""),
                    rec.get("title", ""),
                )
        time.sleep(0.34)  # be polite to NCBI (~3 req/s without an API key)

    suspects: list[tuple] = []
    for pid in pmids:
        fname, ln, ctx = claims[pid]
        info = real.get(pid)
        if info is None:
            suspects.append((pid, fname, ln, "NOT FOUND on PubMed", ""))
            continue
        first, yr, journal, title = info
        surname = (_norm(first).split() or [""])[0]
        if surname and surname not in _norm(ctx):
            suspects.append((
                pid, fname, ln,
                f"{first} | {yr} {journal} | {title[:72]}",
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
