#!/usr/bin/env python3
"""Live-retrieval quality eval — the mechanism-question gauntlet (M3).

``prove_retrieval.py`` proves the *curated* offline corpus is retrievable.
This is its live-frontier counterpart: it drives the **real** ``discover``
command (subprocess, exactly what ``/cv:research`` runs) over a fixed set of
hard cannabis-mechanism questions and scores what comes back —

- **coverage**   — did the query surface any primary-source rows at all?
- **relevance**  — are the top-ranked rows actually on the question's topic?
- **ranking**    — is the #1 row on-topic (the row a reader sees first)?
- **source mix** — which live lanes contributed.

Each question carries a hand-curated set of ``topic_terms`` (the gold on-topic
vocabulary) so relevance is judged against a human standard, not the engine's
own score. Run live; thresholds fail loudly so a coverage/ranking regression
can never pass silently.

Run:   python3 evals/eval_live_retrieval.py
       python3 evals/eval_live_retrieval.py --sources europepmc,ctgov,chembl
       python3 evals/eval_live_retrieval.py --max 8 --topk 3
Exit:  non-zero if any threshold is unmet.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# The eight mechanism/physiology questions — pharmacology a researcher asks,
# where the primary literature is rich and the answer is well-established.
QUERIES: tuple[dict, ...] = (
    {
        "q": "How does cannabis interaction with CB1 receptors alter short-term memory?",
        "topic_terms": ("memory", "cb1", "cannabinoid", "hippocamp", "cognit",
                        "working memory", "cnr1"),
    },
    {
        "q": "What is the neurological basis for cannabis reducing epileptic seizures?",
        "topic_terms": ("seizure", "epilep", "cannabidiol", "cbd", "anticonvuls",
                        "dravet", "lennox", "neuronal"),
    },
    {
        "q": "How does tetrahydrocannabinol THC temporarily impair motor coordination and balance?",
        "topic_terms": ("motor", "coordination", "balance", "cerebell", "thc",
                        "ataxia", "psychomotor", "impair"),
    },
    {
        "q": "How does smoking cannabis affect airway resistance compared to tobacco?",
        "topic_terms": ("airway", "respirat", "pulmonary", "lung", "bronch",
                        "smoking", "spirometr", "fev"),
    },
    {
        "q": "What causes the temporary increase in heart rate after consuming cannabis?",
        "topic_terms": ("heart rate", "tachycard", "cardiovascul", "cardiac",
                        "thc", "autonomic", "sympath", "hemodynam"),
    },
    {
        "q": "How does liver metabolism change THC into a stronger compound 11-hydroxy-THC when eaten?",
        "topic_terms": ("11-hydroxy", "11-oh-thc", "metaboli", "cyp", "hepatic",
                        "first-pass", "oral", "pharmacokinet"),
    },
    {
        "q": "Why do different ingestion methods vaping vs edibles change the onset time of cannabis?",
        "topic_terms": ("pharmacokinet", "bioavailab", "onset", "oral", "inhal",
                        "absorption", "plasma", "tmax", "edible", "vapor"),
    },
    {
        "q": "How does cannabidiol CBD counteract some of the anxiety caused by THC?",
        "topic_terms": ("anxiet", "anxiolytic", "cbd", "cannabidiol", "thc",
                        "5-ht", "amygdala", "fear"),
    },
)

DEFAULT_SOURCES = "europepmc,ctgov,chembl"


def _run_discover(query: str, sources: str, max_rows: int) -> dict:
    """Drive the real CLI ``discover`` command and return its JSON payload."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        # Ranking is on by default (disabled with --no-rank); --json emits the
        # structured payload including the cross-source ranking block.
        [sys.executable, "-m", "cannavec_science", "discover", query,
         "--sources", sources, "--max", str(max_rows), "--json"],
        cwd=root, capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"sources": {}, "ranking": {"ranked": []}, "_err": proc.stderr[-200:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"sources": {}, "ranking": {"ranked": []}, "_err": "non-JSON output"}


def _is_on_topic(title: str, topic_terms: tuple[str, ...]) -> bool:
    t = (title or "").lower()
    return any(term in t for term in topic_terms)


def _score_query(payload: dict, topic_terms: tuple[str, ...], topk: int) -> dict:
    sources = payload.get("sources", {})
    coverage = sum(len(v) for v in sources.values() if isinstance(v, list))
    ranked = (payload.get("ranking") or {}).get("ranked", []) or []
    top = ranked[:topk]
    on_topic = [_is_on_topic(r.get("title", ""), topic_terms) for r in top]
    relevance = (sum(on_topic) / len(on_topic)) if on_topic else 0.0
    top1_on_topic = bool(on_topic and on_topic[0])
    lanes = sorted(s for s, v in sources.items() if isinstance(v, list) and v)
    return {
        "coverage": coverage,
        "relevance": relevance,
        "top1_on_topic": top1_on_topic,
        "lanes": lanes,
        "top_titles": [r.get("title", "")[:70] for r in top],
        "served_from_cache": bool(payload.get("served_from_cache")),
    }


# Thresholds — a regression FLOOR, not an aspirational ceiling. The headline
# guarantee M1+M2 deliver is COVERAGE: every mechanism question is grounded in a
# real, current, retraction-checked primary source even when NCBI is down (via
# the Europe PMC lane + the offline flywheel). Relevance is the deterministic
# floor: keyword retrieval over cannabis terms surfaces broad cannabis
# literature, and lifting the *specific* mechanism paper to #1 reliably is a
# semantic-retrieval problem (the next milestone), not a distillation one. These
# floors sit below the measured operating point (≈37% mean relevance / 50% top-1)
# so the eval fails loudly on a regression without flaking on live-API variance.
MIN_QUERIES_WITH_ROWS = 1.0       # HARD: every question must surface ≥1 source
MIN_MEAN_RELEVANCE = 0.30         # floor (operating point ≈0.37)
MIN_TOP1_ON_TOPIC_RATE = 0.40     # floor (operating point ≈0.50)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live-retrieval mechanism-question eval.")
    ap.add_argument("--sources", default=DEFAULT_SOURCES)
    ap.add_argument("--max", type=int, default=8)
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args(argv)

    print("=" * 78)
    print("LIVE-RETRIEVAL EVAL — cannabis mechanism questions")
    print(f"sources={args.sources}  max={args.max}  topk={args.topk}\n")

    rows: list[dict] = []
    for spec in QUERIES:
        payload = _run_discover(spec["q"], args.sources, args.max)
        sc = _score_query(payload, spec["topic_terms"], args.topk)
        rows.append(sc)
        cache = " (cache)" if sc["served_from_cache"] else ""
        print(f"Q: {spec['q'][:68]}")
        print(f"   coverage={sc['coverage']:<3d} relevance@{args.topk}={sc['relevance']*100:5.1f}% "
              f"top1={'on' if sc['top1_on_topic'] else 'OFF':<3} lanes={','.join(sc['lanes']) or '—'}{cache}")
        for t in sc["top_titles"]:
            print(f"      · {t}")
        print()

    n = len(rows)
    with_rows = sum(1 for r in rows if r["coverage"] > 0) / n
    mean_rel = sum(r["relevance"] for r in rows) / n
    top1_rate = sum(1 for r in rows if r["top1_on_topic"]) / n

    print("=" * 78)
    print(f"  questions with ≥1 row:   {with_rows*100:5.1f}%")
    print(f"  mean relevance@{args.topk}:      {mean_rel*100:5.1f}%")
    print(f"  #1-row on-topic rate:    {top1_rate*100:5.1f}%")
    checks = [
        ("every question surfaces a source (grounding)", with_rows >= MIN_QUERIES_WITH_ROWS),
        (f"mean relevance ≥ {int(MIN_MEAN_RELEVANCE*100)}% (floor)", mean_rel >= MIN_MEAN_RELEVANCE),
        (f"top-1 on-topic ≥ {int(MIN_TOP1_ON_TOPIC_RATE*100)}% (floor)", top1_rate >= MIN_TOP1_ON_TOPIC_RATE),
    ]
    ok = all(p for _, p in checks)
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print("=" * 78)
    if ok:
        print("VERDICT: GROUNDED — every mechanism question is reliably grounded "
              "in real primary sources;")
        print("         relevance meets the deterministic floor. Lifting the "
              "specific-mechanism paper to #1")
        print("         is the semantic-retrieval frontier (next milestone).")
    else:
        print("VERDICT: REGRESSION — live retrieval fell below the floor; see "
              "failures above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
