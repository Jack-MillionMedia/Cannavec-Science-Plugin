#!/usr/bin/env python3
"""Audit every UniProt accession shipped by the registries against live UniProt.

Constitution §I names the UniProt accession as one of the five primary-source
identifier shapes; §VI requires every receptor to carry its accession. A wrong
accession (a typo, or CB1's id pasted onto CB2) is the protein-world analogue of
a wrong PMID — and, like a wrong PMID, it passes every offline test because the
string is well-formed. This is the online check.

For each accession literal in ``cannavec_science/*.py`` that is written as a
deliberate identifier (next to "UniProt" or "HGNC"), this resolves the real
record via :mod:`cannavec_science.uniprot_verify` and flags any where **neither
the real gene symbol nor the real protein name** appears next to the accession
in the source — i.e. the accession points at a different protein than the code
claims. This mirrors ``evals/audit_pmids.py`` (author-or-title match), and is
likewise network-resilient: an accession that cannot be fetched is reported
*inconclusive*, never a false suspect, so a flaky network does not fail the gate.

Stdlib only; needs network to UniProt. Run from anywhere in the repo:

    python3 evals/audit_uniprot.py
"""
from __future__ import annotations

import glob
import os
import re
import sys
import unicodedata
import urllib.error

# Allow running as a script (python3 evals/audit_uniprot.py) — the script's dir
# is evals/, so put the repo root on the path before importing the package.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cannavec_science.uniprot_verify import is_uniprot_accession, verify_uniprot

_PKG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cannavec_science",
)
# Strict UniProt accession shape (Swiss-Prot/TrEMBL), matched as a whole token.
_ACC_RE = re.compile(
    r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b"
)
# Only audit accessions written as deliberate identifiers — i.e. with one of
# these markers in their neighbourhood — so a random 6-char token is not chased.
_MARKERS = ("uniprot", "hgnc")
_GENERIC = frozenset(
    "the of and a an receptor protein human gene via at to in on for is are "
    "uniprot hgnc accession isoform subtype type".split()
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def collect_accessions() -> dict[str, tuple[str, int, str]]:
    """Map accession -> (file, line, context) for deliberately-cited accessions.

    The context is the union of ±3-line windows around every occurrence, so a
    gene symbol mentioned at any use-site counts as "named near the accession".
    """
    occ: dict[str, list[tuple[str, int]]] = {}
    text_by_file: dict[str, list[str]] = {}
    for path in sorted(glob.glob(os.path.join(_PKG, "*.py"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        text_by_file[path] = lines
        for i, line in enumerate(lines):
            for m in _ACC_RE.finditer(line):
                acc = m.group(0)
                if is_uniprot_accession(acc):
                    occ.setdefault(acc, []).append((path, i))

    claims: dict[str, tuple[str, int, str]] = {}
    for acc, sites in occ.items():
        ctx_parts: list[str] = []
        for path, i in sites:
            lines = text_by_file[path]
            ctx_parts.append(" ".join(lines[max(0, i - 3):i + 4]))
        ctx = " ".join(ctx_parts)
        if not any(mk in ctx.lower() for mk in _MARKERS):
            continue  # not written as a deliberate identifier — skip
        first_path, first_line = sites[0]
        claims[acc] = (os.path.basename(first_path), first_line + 1, ctx)
    return claims


def find_suspects(claims: dict[str, tuple[str, int, str]]) -> tuple[list[tuple], int]:
    """Return (suspects, inconclusive_count). A suspect resolves to a protein
    whose gene symbol and name are both absent from the accession's context."""
    suspects: list[tuple] = []
    inconclusive = 0
    for acc in sorted(claims):
        fname, ln, ctx = claims[acc]
        words = set(_norm(ctx).split())
        try:
            rec = verify_uniprot(acc)
        except (urllib.error.URLError, OSError) as exc:
            inconclusive += 1
            print(f"  fetch error for {acc}: {exc}")
            continue
        if rec is None:
            suspects.append((acc, fname, ln, "NOT FOUND on UniProt", ctx.strip()[:90]))
            continue
        gene = _norm(rec.gene_symbol or "")
        gene_hit = bool(gene) and all(t in words for t in gene.split())
        name_tokens = {t for t in _norm(rec.protein_name).split()
                       if len(t) >= 4 and t not in _GENERIC}
        name_hit = bool(name_tokens) and bool(name_tokens & words)
        if not gene_hit and not name_hit:
            suspects.append((
                acc, fname, ln,
                f"{rec.gene_symbol or '?'} | {rec.protein_name[:60]}",
                "",
            ))
    return suspects, inconclusive


def main() -> int:
    claims = collect_accessions()
    print(f"Auditing {len(claims)} UniProt accessions against live UniProt...\n")
    suspects, inconclusive = find_suspects(claims)
    tail = f"; {inconclusive} inconclusive (fetch error)" if inconclusive else ""
    print(f"===== {len(suspects)} SUSPECT / {len(claims)} audited{tail} =====\n")
    for acc, fname, ln, real_s, ctx in suspects:
        print(f"{acc}  cannavec_science/{fname}:{ln}")
        print(f"   UniProt: {real_s}")
        if ctx:
            print(f"   code   : {ctx}")
        print()
    if suspects:
        return 1
    if inconclusive:
        print(f"NOTE: {inconclusive} accession(s) could not be fetched; audit "
              f"inconclusive for those. Not failing the build on a network gap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
