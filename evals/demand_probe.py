#!/usr/bin/env python3
"""Instrument a representative demand profile — the read-time half of §IX.

Runs a spread of researcher-style questions through the *real* curated answer
pipeline (offline, zero network) and records one demand event per answer via
:func:`cannavec_science.demand.instrument_answer`. The aggregated ledger ranks
topics by miss volume — the holes the flywheel should fan out on next.

This makes the demand signal *real*: a question like "is cannabis effective for
fibromyalgia?" returns generic pain-review rows that never mention fibromyalgia,
so it books as a topic-specific miss — exactly the hole the eval surfaces.

Run:  python3 evals/demand_probe.py                 # writes demand_log.jsonl
      python3 evals/demand_probe.py --store-dir /tmp/d
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cannavec_science.answer import compose_answer
from cannavec_science.demand import aggregate, instrument_answer

# A plausible researcher/patient demand profile. Topics users actually ask about
# (per the eval) recur; the holes recur because demand concentrates there.
QUESTIONS: tuple[str, ...] = (
    # CBD pharmacokinetics (curated depth exists)
    "What is the oral bioavailability of cannabidiol?",
    "What is the Tmax and elimination half-life of oral CBD?",
    "How does a high-fat meal change CBD plasma exposure?",
    # Driving (curated depth exists)
    "Does Δ⁹-THC impair driving performance?",
    "What does the evidence say about cannabis and on-road driving?",
    # Pain / psychiatry (curated depth exists)
    "Is cannabis effective for chronic neuropathic pain?",
    "Does cannabis use increase the risk of psychosis?",
    # Terpenes (shallow clinical depth)
    "Do terpenes like myrcene and limonene have clinical effects?",
    "What is the evidence for the entourage effect?",
    # Sleep (modest depth)
    "Can cannabidiol improve sleep quality and insomnia?",
    "Does cannabis help with chronic insomnia?",
    # IBD (hole)
    "Is cannabis effective for Crohn's disease?",
    "Does cannabidiol help ulcerative colitis?",
    "Cannabinoids for inflammatory bowel disease",
    # Fibromyalgia (hole)
    "Is cannabis effective for fibromyalgia?",
    "Does nabilone help fibromyalgia symptoms?",
    "Cannabis oil for fibromyalgia pain and quality of life",
    # Migraine (hole)
    "Are cannabinoids effective for migraine prophylaxis?",
    "Cannabis for chronic migraine and headache",
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Instrument a demand profile.")
    ap.add_argument("--store-dir", default=None)
    args = ap.parse_args(argv)

    print(f"Instrumenting {len(QUESTIONS)} answers through the curated pipeline\n")
    for q in QUESTIONS:
        answer = compose_answer(q, retraction_policy="strict",
                                include_registries=True, include_claims=True,
                                include_rigor=True)
        ev = instrument_answer(answer, store_dir=args.store_dir)
        mark = "MISS" if ev.miss else "ok  "
        print(f"  [{mark}] {ev.topic:<22} claims={ev.n_claims:<2} "
              f"covered={str(ev.topic_covered):<5} {q[:46]}")

    from cannavec_science.demand import demand_report
    print("\nTop demand holes (promotion priority):")
    for t in demand_report(args.store_dir)[:8]:
        if t.misses:
            print(f"  {t.topic:<22} asks={t.asks} misses={t.misses} "
                  f"miss_rate={t.thin_rate:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
