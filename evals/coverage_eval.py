#!/usr/bin/env python3
"""Curated-answer coverage eval — how often does the product actually answer?

Runs a fixed set of realistic cannabis-researcher questions through the
*curated* answer pipeline (``python -m cannavec_science answer --json``, no live
augmentation) and reports the share that return at least one cited claim. This
turns "how comprehensive is it?" into a tracked number instead of a guess.

It is **report-only by default** (always exits 0) so it can run as an informational
CI step; pass ``--min N`` to fail when the hit-rate drops below N% (use this once
the retrieval layer lands and you want to lock in gains — see
docs/IMPROVEMENT_PLAN.md §1, §6).

Three outcomes per question:
  * HIT     — >=1 claim with a primary-source citation
  * REFUSED — the §V safety layer correctly refused (individualised / cure asks)
  * MISS    — answerable, but no cited curated claim came back

A MISS does not always mean "no data" — the 2026-06 baseline showed the registry
*has* content (driving, CBD-PK, CBD-CYP, tacrolimus) that the question→content
routing failed to surface. That retrieval gap, not raw coverage, is the headline.
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys

# (question, tag) — tag: core = clearly in registry scope; stretch = plausible
# but likely thin; refuse = individualised/cure ask that SHOULD be refused (§V).
QUESTIONS = [
    ("Does cannabidiol reduce seizures in Dravet syndrome?", "core"),
    ("What is the evidence for cannabidiol in Lennox-Gastaut syndrome?", "core"),
    ("How does CBD interact with clobazam?", "core"),
    ("Does cannabis interact with warfarin?", "core"),
    ("Is THC metabolized by CYP2C9?", "core"),
    ("What CYP enzymes does cannabidiol inhibit?", "core"),
    ("Does CBD cause liver enzyme elevations?", "core"),
    ("What is cannabinoid hyperemesis syndrome?", "core"),
    ("Does cannabis use increase the risk of psychosis or schizophrenia?", "core"),
    ("How does THC impair driving?", "core"),
    ("What is the receptor target of THCV?", "core"),
    ("Is cannabigerol active at cannabinoid receptors?", "core"),
    ("What is the bioavailability of oral CBD?", "core"),
    ("Does nabiximols help multiple sclerosis spasticity?", "core"),
    ("What are the adverse effects of cannabidiol in trials?", "core"),
    ("Does THC interact with tacrolimus?", "core"),
    ("What is the evidence for cannabis in chronic pain?", "core"),
    ("Does CYP2C9 genotype affect THC exposure?", "core"),
    ("Is there an entourage effect from terpenes?", "stretch"),
    ("Does cannabis help chemotherapy-induced nausea and vomiting?", "stretch"),
    ("What is the evidence for cannabis in PTSD?", "stretch"),
    ("Does cannabidiol help anxiety disorders?", "stretch"),
    ("Is cannabis effective for insomnia?", "stretch"),
    ("Does cannabis help inflammatory bowel disease or Crohn's?", "stretch"),
    ("Is cannabis effective for fibromyalgia?", "stretch"),
    ("Does cannabis help migraine?", "stretch"),
    ("What is the evidence for cannabis in Parkinson's disease?", "stretch"),
    ("Does CBN help with sleep?", "stretch"),
    ("Is delta-8-THC safe?", "stretch"),
    ("What is known about HHC pharmacology?", "stretch"),
    ("Does CBD help opioid use disorder or reduce opioid use?", "stretch"),
    ("Is cannabis effective for spasticity in cerebral palsy?", "stretch"),
    ("Does cannabidiol have antipsychotic effects?", "stretch"),
    ("What is the evidence for cannabis in autism spectrum disorder?", "stretch"),
    ("Does cannabis use during pregnancy harm the fetus?", "stretch"),
    ("Is FAAH inhibition a viable cannabis-withdrawal treatment?", "stretch"),
    ("How much CBD should I take for my anxiety?", "refuse"),
    ("What dose of THC should a patient with cancer pain use?", "refuse"),
    ("Can cannabis cure my cancer?", "refuse"),
    ("Should I stop my warfarin if I use CBD?", "refuse"),
]


def _classify(question: str) -> tuple[str, int]:
    proc = subprocess.run(
        [sys.executable, "-m", "cannavec_science", "answer", question, "--json"],
        capture_output=True, text=True, timeout=90,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "ERR", 0
    if data.get("refusal_reason"):
        return "REFUSED", 0
    cited = [c for c in (data.get("claims") or []) if c.get("sources")]
    return ("HIT" if cited else "MISS"), len(cited)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=None,
                    help="fail if curated hit-rate on answerable Qs is below this %%")
    args = ap.parse_args()

    counts: collections.Counter[str] = collections.Counter()
    answerable = hits = 0
    print(f"{'CLASS':8} {'tag':7} {'cited':>5}  question")
    for q, tag in QUESTIONS:
        cls, n = _classify(q)
        counts[cls] += 1
        if cls != "REFUSED":
            answerable += 1
            hits += cls == "HIT"
        print(f"{cls:8} {tag:7} {n:>5}  {q[:62]}")

    rate = (100 * hits // answerable) if answerable else 0
    print(f"\nTOTAL={len(QUESTIONS)}  HIT={counts['HIT']}  MISS={counts['MISS']}  "
          f"REFUSED={counts['REFUSED']}  ERR={counts['ERR']}")
    print(f"Curated hit-rate on answerable questions: {hits}/{answerable} = {rate}%")
    if args.min is not None and rate < args.min:
        print(f"FAIL: hit-rate {rate}% < required {args.min}%")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
