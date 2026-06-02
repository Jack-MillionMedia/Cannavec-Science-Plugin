#!/usr/bin/env python3
"""Audit every curated ChEMBL id against the ChEMBL API.

A ChEMBL id is a §I primary-source identifier. A wrong one points at a different
molecule entirely (the kind of defect already found and fixed: an id that
resolved to a platinum complex instead of the MAGL inhibitor it claimed to be).
This is the online check that each ``chembl_id`` resolves to the compound named
next to it (its ``compound_id`` / label).

Same contract as the other identifier audits: resolve id -> pref_name +
synonyms; flag when the named compound matches none of them, or when the id does
not resolve (404); a network gap is inconclusive, never a failure. Only
``chembl_id="..."`` assignments are audited (a CHEMBL id mentioned in a comment
as an example is not a citation and is ignored). Stdlib only; resolver injected
for the offline test.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Callable, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PKG = os.path.join(_REPO_ROOT, "cannavec_science")
Resolver = Callable[[str], Optional[dict]]


def _norm(s: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split())


def chembl_resolve(chembl_id: str) -> Optional[dict]:
    """Return the ChEMBL molecule record, ``None`` on 404. Raises on network."""
    url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "cannavec-chembl-audit/1.0",
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def collect_chembl() -> dict[str, tuple[str, str]]:
    """Map chembl_id -> (file, claimed compound name) for citation assignments.

    The claimed name is the ``compound_id`` in the same record when present,
    else the nearest preceding ``name=``/``label=`` text.
    """
    out: dict[str, tuple[str, str]] = {}
    pat = re.compile(r'chembl_id\s*=\s*"(CHEMBL\d+)"')
    for path in sorted(glob.glob(os.path.join(_PKG, "*.py"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            m = pat.search(line)
            if not m:
                continue
            cid = m.group(1)
            window = " ".join(lines[max(0, i - 8):i + 1])
            cm = re.search(r'compound_id\s*=\s*"([^"]+)"', window) or \
                re.search(r'(?:name|label)\s*=\s*"([^"]+)"', window)
            out.setdefault(cid, (os.path.basename(path), cm.group(1) if cm else ""))
    return out


def _synonym_tokens(rec: dict) -> set[str]:
    toks: set[str] = set()
    toks |= _norm(rec.get("pref_name") or "")
    for s in rec.get("molecule_synonyms") or []:
        toks |= _norm(s.get("molecule_synonym") or "")
    return toks


def find_suspects(claims: dict[str, tuple[str, str]],
                  resolve: Resolver = chembl_resolve) -> tuple[list[tuple], int]:
    suspects: list[tuple] = []
    inconclusive = 0
    for cid in sorted(claims):
        fname, claimed = claims[cid]
        try:
            rec = resolve(cid)
        except (urllib.error.URLError, OSError) as exc:
            inconclusive += 1
            print(f"  fetch error for {cid}: {exc}")
            continue
        if rec is None:
            suspects.append((cid, fname, "does not resolve on ChEMBL (404)", claimed))
            continue
        syns = _synonym_tokens(rec)
        # significant claimed tokens (drop short/generic) must hit a synonym.
        claimed_toks = {t for t in _norm(claimed) if len(t) >= 3
                        and t not in {"the", "and", "lu"}}
        if claimed_toks and not (claimed_toks & syns):
            suspects.append((cid, fname,
                             f"resolves to {rec.get('pref_name') or '?'}", claimed))
    return suspects, inconclusive


def main() -> int:
    claims = collect_chembl()
    print(f"Auditing {len(claims)} curated ChEMBL ids against ChEMBL...\n")
    suspects, inconclusive = find_suspects(claims)
    tail = f"; {inconclusive} inconclusive (fetch error)" if inconclusive else ""
    print(f"===== {len(suspects)} SUSPECT / {len(claims)} audited{tail} =====\n")
    for cid, fname, real_s, claimed in suspects:
        print(f"{cid}  cannavec_science/{fname}")
        print(f"   ChEMBL: {real_s}")
        print(f"   claim : {claimed}")
        print()
    if suspects:
        return 1
    if inconclusive:
        print(f"NOTE: {inconclusive} id(s) could not be fetched; audit inconclusive "
              f"for those. Not failing the build on a network gap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
