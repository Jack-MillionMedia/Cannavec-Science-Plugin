#!/usr/bin/env python3
"""Claim-support audit: does each interaction's cited paper support the claim?

Runs :func:`cannavec_science.claim_support.assess_support` over every curated
drug-interaction row against the abstract of its primary citation. It is the
continuous review-queue generator for the "right paper, wrong claim" failure
mode that the identifier audits cannot see.

This is a **high-recall flagger**, deliberately advisory rather than a hard gate
for the soft verdicts: an abstract does not always restate a magnitude that
lives in the full text, so an ``UNVERIFIED``/``WEAK`` verdict means "a human
should glance at this", not "this is wrong". The one verdict treated as a build
failure is ``CONTRADICTION`` — the abstract asserts the *opposite* direction
(inhibition vs. induction), which is a genuine defect, not a recall artefact.

Network-resilient, like the identifier audits: a citation whose abstract cannot
be fetched is *inconclusive*, never a flag. Stdlib only; the abstract fetcher is
injected so the offline suite exercises the wiring with zero network.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from typing import Callable, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cannavec_science.claim_support import (
    Verdict,
    assess_support,
    gates_to_llm,
    review_claim,
)
from cannavec_science.interactions import all_interactions

_API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
AbstractFetcher = Callable[[str], Optional[str]]


def efetch_abstract(pmid: str) -> Optional[str]:
    """Default fetcher: PubMed efetch (text). Returns None on a network gap."""
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
        f"db=pubmed&rettype=abstract&retmode=text&id={pmid}"
    )
    if _API_KEY:
        url += "&api_key=" + _API_KEY
    req = urllib.request.Request(url, headers={"User-Agent": "cannavec-claim-support/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError):
        return None


def review_interactions(fetch: AbstractFetcher = efetch_abstract):
    """Return (flags, checked, inconclusive).

    ``flags`` is a list of (cannabinoid, partner_drug, pmid, SupportReport) for
    every row whose citation's abstract does not evidently support the claim.
    """
    cache: dict[str, Optional[str]] = {}
    flags = []
    checked = 0
    inconclusive = 0
    for row in all_interactions():
        pmid = next((c.pmid for c in row.citations if getattr(c, "pmid", None)), None)
        if not pmid:
            continue
        if pmid not in cache:
            cache[pmid] = fetch(pmid)
        abstract = cache[pmid]
        if not abstract:
            inconclusive += 1
            continue
        report = assess_support(
            row.magnitude_note or "",
            abstract,
            cannabinoid=row.cannabinoid,
            partner_drug=row.partner_drug,
            cyp_isoform=row.cyp_isoform,
            direction_hint=getattr(row.direction, "value", str(row.direction)),
        )
        checked += 1
        if report.needs_review:
            flags.append((row.cannabinoid, row.partner_drug, pmid, report))
    return flags, checked, inconclusive


def adjudicate_interactions(
    fetch: AbstractFetcher = efetch_abstract,
    *,
    adjudicator=None,
):
    """Deterministically flag, then optionally LLM-adjudicate, every row.

    Returns ``(reviews, checked, inconclusive)`` where ``reviews`` is a list of
    ``(cannabinoid, partner_drug, pmid, ClaimReview)`` for the rows the
    deterministic flagger (:func:`gates_to_llm`) sent for a closer read — the
    human review queue. That gate is the flagged minority (``WEAK`` /
    ``UNVERIFIED`` / ``CONTRADICTION``) **plus** an otherwise-confident
    ``SUPPORTED`` claim whose text asserts a quantitative magnitude
    (:func:`asserts_magnitude`), since the deterministic layer never reads the
    number itself.

    With no ``adjudicator`` the reviews carry the deterministic verdict only.
    Pass an injected :class:`cannavec_science.claim_support_llm.LLMAdjudicator`
    (or any duck-typed backend) and each flagged row also carries the model's
    identifier-free verdict (``supported`` / ``partial`` / ``unverified``) and
    the supporting sentence quoted — provenance-gated, so a fabricated quote is
    dropped, never surfaced. A human confirms the contested ones.

    Note the two verdict surfaces on each ``ClaimReview``: ``review.verdict`` is
    the surfaced :class:`~cannavec_science.claim_support.Support` (the model's
    read, or the deterministic mapping), while the hard CI signal — a direction
    *contradiction* — lives on the deterministic floor at
    ``review.report.verdict == Verdict.CONTRADICTION`` (and is always reflected
    in ``review.needs_human``). A caller gating CI on contradictions MUST read
    the floor, not the surfaced verdict, which maps a contradiction to the
    softer ``unverified``.

    Network-resilient like the deterministic audit: an un-fetchable abstract is
    inconclusive, never a flag. The fetcher is injected so the offline suite
    exercises the wiring with zero network.
    """
    cache: dict[str, Optional[str]] = {}
    reviews = []
    checked = 0
    inconclusive = 0
    for row in all_interactions():
        pmid = next((c.pmid for c in row.citations if getattr(c, "pmid", None)), None)
        if not pmid:
            continue
        if pmid not in cache:
            cache[pmid] = fetch(pmid)
        abstract = cache[pmid]
        if not abstract:
            inconclusive += 1
            continue
        claim = row.magnitude_note or ""
        review = review_claim(
            claim,
            abstract,
            backend=adjudicator,
            cannabinoid=row.cannabinoid,
            partner_drug=row.partner_drug,
            cyp_isoform=row.cyp_isoform,
            direction_hint=getattr(row.direction, "value", str(row.direction)),
        )
        checked += 1
        if gates_to_llm(review.report, claim_text=claim):
            reviews.append((row.cannabinoid, row.partner_drug, pmid, review))
    return reviews, checked, inconclusive


def main() -> int:
    flags, checked, inconclusive = review_interactions()
    contradictions = [f for f in flags if f[3].verdict == Verdict.CONTRADICTION]
    tail = f"; {inconclusive} inconclusive (fetch error)" if inconclusive else ""
    print(f"Claim-support audit: {checked} interaction claims checked{tail}\n")
    for cb, drug, pmid, rep in flags:
        print(f"[{rep.verdict.value.upper()}] {cb} x {drug}  (PMID {pmid})")
        print(f"   {rep.note}")
        if rep.missing:
            print(f"   missing from abstract: {', '.join(rep.missing)}")
        print()
    print(f"===== {len(flags)} need review "
          f"({len(contradictions)} contradiction) / {checked} checked =====")
    if contradictions:
        return 1   # a direction contradiction is a real defect, not recall noise
    if checked == 0 and inconclusive:
        print("NOTE: no abstracts could be fetched; audit inconclusive (network gap).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
