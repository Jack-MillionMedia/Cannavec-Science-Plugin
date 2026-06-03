#!/usr/bin/env python3
"""Audit every curated DOI against Crossref.

The PMID and UniProt audits cover those identifier shapes; this is the DOI
equivalent and the only audit that can verify the non-PubMed DOIs (old ACS/JACS
papers, JSTOR/Taxon, the NASEM report) — Crossref is the registry of record for
*all* DOIs, so a DOI that 404s there is fake, and one that resolves to a paper
matching neither the author nor the title named at the cite is mis-attributed.

Same contract as ``audit_pmids`` / ``audit_uniprot``:
  * resolve each DOI -> real (first-author family, title, year, journal);
  * flag when the cite names neither the author nor enough of the title
    (author-OR-title, whole-word), or when the DOI does not resolve (404);
  * network gap (cannot reach Crossref) is *inconclusive*, never a failure.

Crossref is queried from the polite pool (a descriptive User-Agent with a
contact); this works from CI. The synthetic seed DOI (10.99999/...) is skipped.
Stdlib only; the resolver is injected so the offline suite needs no network.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from typing import Callable, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PKG = os.path.join(_REPO_ROOT, "cannavec_science")

_CONTACT = os.environ.get("CROSSREF_MAILTO", "cannavec-science@example.org")
_UA = f"cannavec-doi-audit/1.0 (mailto:{_CONTACT})"
Resolver = Callable[[str], Optional[dict]]

_TITLE_STOP = frozenset(
    "a an and the of in on for to with from into versus vs study studies trial "
    "trials effect effects role human humans patient patients clinical review "
    "systematic analysis based using use new novel via case report series".split()
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def crossref_resolve(doi: str) -> Optional[dict]:
    """Return Crossref ``message`` for a DOI, ``None`` on 404. Raises on network."""
    url = "https://api.crossref.org/works/" + urllib.request.quote(doi)
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("message")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _blocks(text: str):
    for m in re.finditer(r"\b\w*(?:Citation|Source)\s*\(", text):
        start = text.index("(", m.start()); depth = 0; j = start
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield text[start:j + 1]


_FIELD = re.compile(r'\b(?:pmid|doi|url|year|role|first_author|authors?|'
                    r'compound_id|chembl_id|tier)\s*=')


def _extract_label(body: str) -> str:
    """Full label text, joining Python implicit string concatenation.

    Labels are often written as ``label=("a " "b")`` or split across lines, so a
    single ``label="..."`` match drops everything after the first segment — which
    silently hid an author (Blount) or a title (the NASEM report) from the match.
    This collects every quoted segment after ``label=`` up to the next field.
    """
    m = re.search(r'label\s*=\s*', body)
    if not m:
        return ""
    rest = body[m.end():]
    stop = _FIELD.search(rest)
    span = rest[:stop.start()] if stop else rest
    return " ".join(re.findall(r'"([^"]*)"', span)).strip()


def collect_dois() -> dict[str, tuple[str, str]]:
    """Map DOI -> (file, label) for every curated citation DOI (skips synthetic)."""
    out: dict[str, tuple[str, str]] = {}
    for path in sorted(glob.glob(os.path.join(_PKG, "*.py"))):
        text = open(path, encoding="utf-8").read()
        for body in _blocks(text):
            dm = re.search(r'doi\s*=\s*"([^"]+)"', body)
            if not dm:
                continue
            doi = dm.group(1)
            if doi.startswith("10.99999"):
                continue  # documented synthetic seed
            out.setdefault(doi, (os.path.basename(path), _extract_label(body)))
    return out


def find_suspects(claims: dict[str, tuple[str, str]],
                  resolve: Resolver = crossref_resolve) -> tuple[list[tuple], int]:
    suspects: list[tuple] = []
    inconclusive = 0
    for doi in sorted(claims):
        fname, label = claims[doi]
        words = set(_norm(label).split())
        try:
            msg = resolve(doi)
        except (urllib.error.URLError, OSError) as exc:
            inconclusive += 1
            print(f"  fetch error for {doi}: {exc}")
            continue
        if msg is None:
            suspects.append((doi, fname, "DOI does not resolve on Crossref (404)", label[:70]))
            continue
        authors = msg.get("author") or []
        # Match against ALL authors (and any org "name"), like audit_pmids: a
        # label may cite a senior/last author, not Crossref's first author, and
        # reports/books are org-authored (a "name", not a "family").
        author_toks: set[str] = set()
        for a in authors:
            for t in (_norm(a.get("family", "")) + " " + _norm(a.get("name", ""))).split():
                if len(t) >= 4:
                    author_toks.add(t)
        author_hit = bool(author_toks & words)
        title = _norm((msg.get("title") or [""])[0])
        ttoks = {t for t in title.split() if len(t) >= 4 and t not in _TITLE_STOP}
        overlap = (len(ttoks & words) / len(ttoks)) if ttoks else 0.0
        if not author_hit and overlap < 0.30:
            yr = ""
            try:
                yr = str(msg.get("issued", {}).get("date-parts", [[None]])[0][0] or "")
            except Exception:
                pass
            j = (msg.get("container-title") or [""])[0]
            suspects.append((doi, fname,
                             f"{authors[0].get('family','?') if authors else '?'} {yr} {j[:30]}".strip(),
                             label[:70]))
    return suspects, inconclusive


def main() -> int:
    claims = collect_dois()
    print(f"Auditing {len(claims)} curated DOIs against Crossref...\n")
    suspects, inconclusive = find_suspects(claims)
    tail = f"; {inconclusive} inconclusive (fetch error)" if inconclusive else ""
    print(f"===== {len(suspects)} SUSPECT / {len(claims)} audited{tail} =====\n")
    for doi, fname, real_s, label in suspects:
        print(f"{doi}  cannavec_science/{fname}")
        print(f"   Crossref: {real_s}")
        print(f"   label   : {label}")
        print()
    if suspects:
        return 1
    if inconclusive:
        print(f"NOTE: {inconclusive} DOI(s) could not be fetched; audit inconclusive "
              f"for those. Not failing the build on a network gap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
