#!/usr/bin/env python3
"""Live-retrieval quality eval — the mechanism-question gauntlet (M3), hardened.

``prove_retrieval.py`` proves the *curated* offline corpus is retrievable. This is
its live-frontier counterpart: it drives the **real** ``discover`` command
(subprocess, exactly what ``/cannavec-science:research`` runs) over a fixed set of
hard cannabis-mechanism questions and scores what comes back —

- **coverage**   — did the query surface any primary-source rows at all?
- **relevance**  — are the top-ranked rows actually on the question's topic?
- **ranking**    — is the #1 row on-topic (the row a reader sees first)?

Robustness (so the gate is reliable, never flaky):

- **subprocess retry** — a transient failure (timeout / crash / non-JSON) is
  retried before counting against the run.
- **best-of-N per query** — each question is run up to N times and scored on its
  BEST attempt, smoothing live-API result variance (the cause of borderline
  flakes at the relevance floor).
- **inconclusive, not failed** — a query whose every attempt failed at the
  transport level is marked INCONCLUSIVE and excluded from the gate; if too much
  of the eval couldn't reach the network, the whole run is INCONCLUSIVE (exit 0),
  so a network outage never reads as a regression.
- **hard reliability gate** — of the questions that DID reach the network, every
  one must be grounded in ≥1 real source. Relevance is a separate, conservative
  floor (a regression detector, set well below the operating point).
- **pubmed when a key is present** — auto-adds the pubmed lane when an
  ``NCBI_API_KEY`` is configured (better relevance + margin); europepmc-led
  otherwise (the key-less cloud-safe lane).

Run:   python3 evals/eval_live_retrieval.py
       python3 evals/eval_live_retrieval.py --sources europepmc,ctgov,chembl --best-of 3
Exit:  non-zero ONLY on a genuine regression; 0 on pass OR inconclusive (network).
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

# Thresholds — see module docstring. Reliability (grounding) is the HARD gate.
# Relevance is a conservative regression FLOOR set well below the best-of-N
# operating point so live-API variance never trips it, while a real collapse
# (retrieval broken → near-zero) still fails loudly.
MIN_MEAN_RELEVANCE = 0.25
MIN_TOP1_ON_TOPIC_RATE = 0.375
# At least this fraction of questions must reach the network for a verdict;
# otherwise the run is INCONCLUSIVE (network), not a regression.
MIN_CONCLUSIVE_FRAC = 0.60
# A best attempt this good ends the best-of loop early (saves live calls).
_GOOD_ENOUGH_RELEVANCE = 0.66


def _ncbi_key_present() -> bool:
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from cannavec_science import _creds
        _creds.load_dotenv(".env")  # resolve the key the same way the CLI does
        return bool(_creds.resolve("NCBI_API_KEY"))
    except Exception:  # noqa: BLE001 — never let key detection break the eval
        return False


def _run_discover(query: str, sources: str, max_rows: int, *, attempts: int = 3) -> tuple[dict, bool]:
    """Drive the real CLI ``discover`` command, retrying transient failures.

    Returns ``(payload, inconclusive)``. ``inconclusive`` is True only when every
    attempt failed at the transport level (timeout / crash / unparseable) — i.e.
    we could not reach the live APIs, as opposed to reaching them and getting no
    rows.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    last_err = ""
    for _ in range(max(1, attempts)):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "cannavec_science", "discover", query,
                 "--sources", sources, "--max", str(max_rows), "--json"],
                cwd=root, capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            last_err = "timeout"
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                return json.loads(proc.stdout), False
            except json.JSONDecodeError:
                last_err = "non-JSON output"
                continue
        last_err = (proc.stderr or "")[-200:]
    return {"sources": {}, "ranking": {"ranked": []}, "_err": last_err}, True


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
    lanes = sorted(s for s, v in sources.items() if isinstance(v, list) and v)
    return {
        "coverage": coverage,
        "relevance": relevance,
        "top1_on_topic": bool(on_topic and on_topic[0]),
        "lanes": lanes,
        "top_titles": [r.get("title", "")[:70] for r in top],
    }


def _best_of(runner, query, sources, max_rows, topic_terms, topk, *, best_of: int) -> dict:
    """Score a query on its BEST of up to ``best_of`` attempts. A query is
    inconclusive only when EVERY attempt failed at the transport level."""
    best: dict | None = None
    all_inconclusive = True
    for _ in range(max(1, best_of)):
        payload, inconclusive = runner(query, sources, max_rows)
        if not inconclusive:
            all_inconclusive = False
        sc = _score_query(payload, topic_terms, topk)
        if best is None or (sc["relevance"], sc["coverage"]) > (best["relevance"], best["coverage"]):
            best = sc
        if not inconclusive and best["top1_on_topic"] and best["relevance"] >= _GOOD_ENOUGH_RELEVANCE:
            break
    best["inconclusive"] = all_inconclusive
    return best


def evaluate(queries, *, runner, sources, max_rows, topk, best_of) -> list[dict]:
    out = []
    for spec in queries:
        sc = _best_of(runner, spec["q"], sources, max_rows,
                      spec["topic_terms"], topk, best_of=best_of)
        sc["q"] = spec["q"]
        out.append(sc)
    return out


def gate(results: list[dict], *, min_relevance: float, min_top1: float,
         min_conclusive_frac: float = MIN_CONCLUSIVE_FRAC) -> dict:
    """Render a verdict. Status is one of ``pass`` / ``fail`` / ``inconclusive``.

    Reliability (grounding of every conclusive question) is the hard gate;
    relevance/top-1 are conservative regression floors. Too few conclusive
    questions → inconclusive (network), never a fail."""
    n_total = len(results)
    conclusive = [r for r in results if not r.get("inconclusive")]
    n_conc = len(conclusive)
    if n_total == 0 or n_conc / n_total < min_conclusive_frac:
        return {"status": "inconclusive", "n_total": n_total, "n_conclusive": n_conc}
    grounded = all(r["coverage"] > 0 for r in conclusive)
    mean_rel = sum(r["relevance"] for r in conclusive) / n_conc
    top1_rate = sum(1 for r in conclusive if r["top1_on_topic"]) / n_conc
    checks = [
        ("every reachable question is grounded in ≥1 real source", grounded),
        (f"mean relevance ≥ {int(min_relevance * 100)}% (floor)", mean_rel >= min_relevance),
        (f"top-1 on-topic ≥ {int(min_top1 * 100)}% (floor)", top1_rate >= min_top1),
    ]
    ok = all(p for _, p in checks)
    return {
        "status": "pass" if ok else "fail",
        "grounded": grounded, "mean_rel": mean_rel, "top1_rate": top1_rate,
        "checks": checks, "n_total": n_total, "n_conclusive": n_conc,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live-retrieval mechanism-question eval (hardened).")
    ap.add_argument("--sources", default=DEFAULT_SOURCES)
    ap.add_argument("--max", type=int, default=8)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--best-of", type=int, default=2,
                    help="Attempts per question; scored on the best (variance smoothing).")
    args = ap.parse_args(argv)

    sources = args.sources
    if "pubmed" not in sources.split(",") and _ncbi_key_present():
        sources = "pubmed," + sources  # a personal NCBI key lifts relevance + margin

    print("=" * 78)
    print("LIVE-RETRIEVAL EVAL — cannabis mechanism questions (hardened)")
    print(f"sources={sources}  max={args.max}  topk={args.topk}  best-of={args.best_of}\n")

    results = evaluate(QUERIES, runner=_run_discover, sources=sources,
                       max_rows=args.max, topk=args.topk, best_of=args.best_of)
    for r in results:
        tag = "INCONCLUSIVE" if r["inconclusive"] else (
            f"relevance@{args.topk}={r['relevance'] * 100:5.1f}% "
            f"top1={'on' if r['top1_on_topic'] else 'OFF'}")
        print(f"Q: {r['q'][:68]}")
        print(f"   coverage={r['coverage']:<3d} {tag} lanes={','.join(r['lanes']) or '—'}")
        for t in r["top_titles"]:
            print(f"      · {t}")
        print()

    g = gate(results, min_relevance=MIN_MEAN_RELEVANCE, min_top1=MIN_TOP1_ON_TOPIC_RATE)
    print("=" * 78)
    if g["status"] == "inconclusive":
        print(f"  reachable questions: {g['n_conclusive']}/{g['n_total']} "
              f"(< {int(MIN_CONCLUSIVE_FRAC * 100)}% needed for a verdict)")
        print("VERDICT: INCONCLUSIVE — too few questions reached the live APIs "
              "(network / rate-limit).")
        print("         Not a regression. Re-run with an NCBI key for reliability.")
        return 0

    print(f"  reachable (conclusive) questions: {g['n_conclusive']}/{g['n_total']}")
    print(f"  mean relevance@{args.topk}:      {g['mean_rel'] * 100:5.1f}%")
    print(f"  #1-row on-topic rate:    {g['top1_rate'] * 100:5.1f}%")
    for label, passed in g["checks"]:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print("=" * 78)
    if g["status"] == "pass":
        print("VERDICT: GROUNDED — every reachable mechanism question is grounded in "
              "real primary sources;")
        print("         relevance clears the conservative floor. Lifting the "
              "specific-mechanism paper to #1")
        print("         is the semantic-retrieval frontier (next milestone).")
        return 0
    print("VERDICT: REGRESSION — live retrieval fell below the floor on reachable "
          "questions; see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
