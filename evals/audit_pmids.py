#!/usr/bin/env python3
"""Audit every PMID shipped by the curated registries against live PubMed.

For each ``pmid="..."`` literal in ``cannavec_science/*.py`` this fetches the
real PubMed record (NCBI E-utilities ``esummary``) and flags any where the
paper matches **neither the author nor the title** named next to the citation
in the source — i.e. the identifier points at a different paper than the
registry claims (the failure mode that shipped an abdominal-infection case
report as "Gaston 2017", and a rat study as "Hjorthoj 2023").

The author-OR-title test is deliberate: a cite is sound if the real paper's
author is named near it (matched against *all* listed authors, whole-word, so
"Conti" does not match inside "discontinuation") OR if ≥30% of the real title's
content words appear there. Requiring both to fail before flagging clears the
false positive where a correct cite's first author has a <4-char surname
("Kim", "Luo") and the title carries the match instead.

Why this exists: the unit suite is offline (injected fetchers), so a
well-formed-but-wrong PMID passes every test. This is the online check that
the curated identifiers actually resolve to the claimed papers. Stdlib only;
needs network to NCBI. Synthetic retraction seeds (99000xxx) are skipped.

Set ``NCBI_API_KEY`` to lift the rate limit to 10 req/s (retries on 429).
PMIDs listed in ``evals/audit_allowlist.txt`` (one per line, ``#`` comments
allowed) are skipped — for confirmed-correct citations the heuristic cannot see.

Run from anywhere inside the repo:

    python3 evals/audit_pmids.py
    NCBI_API_KEY=xxxx python3 evals/audit_pmids.py

Exit code is non-zero when any (non-allowlisted) suspect is found, so it is
CI-gateable. A PMID that could not be fetched (network gap) is reported as
*inconclusive*, not a suspect, so a flaky network never false-fails the gate.
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


# Generic words that carry no identifying signal in a title — excluded from the
# title-overlap check so a cite is not "matched" by boilerplate alone.
_TITLE_STOP = frozenset(
    "a an and the of in on for to with from into versus vs study studies trial "
    "trials effect effects role human humans patient patients clinical review "
    "systematic analysis based using use new novel via case report series".split()
)


def _title_tokens(title: str) -> set[str]:
    """Significant (len>=4, non-stopword) tokens from a paper title."""
    return {t for t in _norm(title).split() if len(t) >= 4 and t not in _TITLE_STOP}


def find_suspects(claims: dict[str, tuple[str, int, str]]) -> tuple[list[tuple], int]:
    """Return (suspects, inconclusive_count).

    A PMID is a suspect when it resolves to a paper that matches neither the
    author nor the title named at the cite. PMIDs that could not be fetched
    (network gap) are *inconclusive*, not suspects — so the audit can gate a PR
    without false-failing on PubMed flakiness.
    """
    allow = _load_allowlist()
    pmids = sorted(claims)
    print(f"Auditing {len(pmids)} registry PMIDs against live PubMed"
          f"{' (NCBI_API_KEY set)' if _API_KEY else ''}"
          f"{f'; {len(allow)} allowlisted' if allow else ''}...\n")
    real: dict[str, tuple | None] = {}
    unfetched: set[str] = set()
    for k in range(0, len(pmids), 100):
        chunk = pmids[k:k + 100]
        try:
            data = _esummary(chunk)
        except (urllib.error.URLError, OSError) as e:
            print(f"  fetch error for chunk at {k}: {e}")
            unfetched.update(chunk)   # network gap — inconclusive, not a defect
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
        if pid in allow or pid in unfetched:
            continue                       # allowlisted, or could not be fetched
        fname, ln, ctx = claims[pid]
        info = real.get(pid)
        if info is None:
            suspects.append((pid, fname, ln, "NOT FOUND on PubMed", ""))
            continue
        tokens, first, yr, journal, title = info
        nctx_words = set(_norm(ctx).split())
        # A citation is sound if EITHER the paper's author is named near the
        # cite OR enough of the paper's title appears there. Flag only when
        # BOTH fail — that catches a wrong PMID (an unrelated paper) without
        # false-flagging a correct cite whose first author has a <4-char surname
        # or is cited by initials (the title carries the match instead).
        #
        # Word-boundary match, never substring: a surname must not count as
        # "named" because it sits inside an unrelated word (e.g. "Conti" within
        # "discontinuation" — the substring blind spot that once let a wrong
        # PMID pass this audit).
        author_hit = bool(tokens) and bool(tokens & nctx_words)
        ttokens = _title_tokens(title)
        title_overlap = (len(ttokens & nctx_words) / len(ttokens)) if ttokens else 0.0
        if not author_hit and title_overlap < 0.30:
            suspects.append((
                pid, fname, ln,
                f"{first} et al. | {yr} {journal} | {title[:72]}",
                ctx.strip()[-92:],
            ))
    return suspects, len(unfetched)


def main() -> int:
    claims = collect_claimed_pmids()
    suspects, inconclusive = find_suspects(claims)
    tail = f"; {inconclusive} inconclusive (fetch error)" if inconclusive else ""
    print(f"===== {len(suspects)} SUSPECT / {len(claims)} audited{tail} =====\n")
    for pid, fname, ln, real_s, ctx in suspects:
        print(f"PMID {pid}  cannavec_science/{fname}:{ln}")
        print(f"   PubMed: {real_s}")
        if ctx:
            print(f"   code  : ...{ctx}")
        print()
    if suspects:
        return 1
    if inconclusive:
        # Network gap, not a citation defect — do not fail the build on
        # infrastructure. The offline denylist guard (tests/) is the always-on
        # floor; this online audit is the best-effort gate when PubMed responds.
        print(f"NOTE: {inconclusive} PMID(s) could not be fetched; audit "
              f"inconclusive for those. Not failing the build on a network gap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
