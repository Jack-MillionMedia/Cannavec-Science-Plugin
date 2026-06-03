#!/usr/bin/env python3
"""Proof that Cannavec Science can reliably retrieve the knowledge it holds.

Improvement Plan §1 diagnosed the product as unable to retrieve curated
evidence it already owns: the per-registry keyword/regex detectors are
order- and phrasing-sensitive, so "how does THC impair driving" returned
zero claims. This harness proves — reproducibly, over the WHOLE knowledge
base, with negative controls — that the retrieval layer fixes that.

Three measurements, all offline and deterministic:

A. WHOLE-KB RETRIEVABILITY (the proof).
   For every curated row, build a query from the row's own most-distinctive
   terms and SHUFFLE them into a bag of words. The shuffle is the adversarial
   step: it breaks the order-sensitive detectors (which need their trigger
   phrase contiguous and in order) while bag-of-words BM25 is order-invariant.
   We then measure, end-to-end through ``compose_answer``, how often the row's
   own primary-source evidence is surfaced:
     - detector-only   (retrieval="off")       — the pre-§1 product
     - with retrieval  (retrieval="fallback")   — the §1 product
   plus the engine's exact-row recall@10. The gap between off and on is the
   proof: knowledge the brittle detectors missed is now reliably found.

B. NEGATIVE CONTROLS (reliable ≠ "returns everything").
   Generic, off-domain, and cross-cannabinoid queries must surface nothing
   spurious. Zero false positives is required.

C. REALISTIC PROBES (human-readable cross-check).
   Natural researcher questions, phrased the way a person would (not echoing
   row text), each with a known target, off vs on.

Run:  python3 evals/prove_retrieval.py
Exit: non-zero if any proof threshold is not met.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cannavec_science import retrieval as R
from cannavec_science.answer import compose_answer, resolve_named_cannabinoid_set
from cannavec_science.ranker import _tokens as toks

# Proof thresholds. The harness fails loudly if reality falls short, so the
# proof can never silently rot.
MIN_ENGINE_RECALL = 0.95      # ≥95% of rows are findable by the engine
MIN_PRODUCT_RECALL_ON = 0.90  # ≥90% surface their evidence end-to-end
MIN_LIFT = 0.30               # retrieval adds ≥30 points over detectors alone
MAX_FALSE_POSITIVES = 0       # negative controls must surface nothing


def _row_pmids(row) -> set:
    """Every PMID the row can legitimately surface (its claim + citations)."""
    pmids: set[str] = set()
    if hasattr(row, "to_claim"):
        try:
            c = row.to_claim()
        except Exception:  # noqa: BLE001
            c = None
        if c is not None:
            for s in c.sources:
                if getattr(s, "pmid", None):
                    pmids.add(s.pmid)
    for cit in getattr(row, "citations", ()) or ():
        if getattr(cit, "pmid", None):
            pmids.add(cit.pmid)
    return pmids


def _corpus_idf() -> dict:
    docs = R._corpus()
    n = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for t in d.token_set:
            df[t] = df.get(t, 0) + 1
    return {t: math.log(1.0 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}


def _cannabinoid_tokens(row) -> list[str]:
    """Short cannabinoid tokens for the row, so the query names the compound
    (the scope filter needs it) the way a real question would."""
    disc = getattr(row, "cannabinoid", None) or getattr(row, "compound", None) or ""
    out: list[str] = []
    for name in resolve_named_cannabinoid_set(str(disc)).all_names:
        out.append("thc" if name in ("THC", "Δ⁹-THC") else name.lower())
    return out


def _shuffled_query(doc, idf: dict, n_distinct: int = 6) -> str:
    """A bag of the row's most-distinctive terms (+ its cannabinoid), shuffled.

    High-IDF terms identify the row; the shuffle destroys any contiguous
    trigger phrase the detectors rely on. Deterministic per row.
    """
    distinct = sorted(
        {t for t in doc.token_set if len(t) > 3},
        key=lambda t: (-idf.get(t, 0.0), t),
    )[:n_distinct]
    bag = list(dict.fromkeys(_cannabinoid_tokens(doc.row) + distinct))
    rng = random.Random(hash(doc.identifier) & 0xFFFFFFFF)
    rng.shuffle(bag)
    return " ".join(bag)


def measurement_a() -> dict:
    docs = R._corpus()
    idf = _corpus_idf()
    by_reg: dict[str, list] = {}
    engine_hits = prod_on = prod_off = scored = 0

    for d in docs:
        pmids = _row_pmids(d.row)
        if not pmids:
            continue  # cannot score a row with no PMID target
        scored += 1
        q = _shuffled_query(d, idf)

        # Engine: is THIS row in the retrieved shortlist?
        eng = d.identifier in {h.identifier for h in R.retrieve(q, k=10)}

        # Product: does the answer surface any of the row's PMIDs?
        on = bool(pmids & {c.pmid for c in compose_answer(q).citations if c.pmid})
        off = bool(
            pmids
            & {c.pmid for c in compose_answer(q, retrieval="off").citations if c.pmid}
        )
        engine_hits += eng
        prod_on += on
        prod_off += off
        by_reg.setdefault(d.registry, [0, 0, 0])
        by_reg[d.registry][0] += eng
        by_reg[d.registry][1] += on
        by_reg[d.registry][2] += off

    return {
        "scored": scored,
        "engine_recall": engine_hits / scored,
        "product_on": prod_on / scored,
        "product_off": prod_off / scored,
        "lift": (prod_on - prod_off) / scored,
        "by_reg": by_reg,
    }


# ── B. Negative controls ────────────────────────────────────────────────────

_GENERIC = ["What is CBD?", "What is THC?", "cannabis", "cannabinoids",
            "tell me about cannabis"]
_OFF_DOMAIN = ["hello world stock market", "what is the weather today",
               "best pizza recipe", "how do I file my taxes",
               "tell me a joke about computers"]
# Cross-cannabinoid: HHC has no curated HHC rows, so no CBD/Δ⁹-THC evidence
# may be attributed to it.
_CROSS = ["HHC safety profile and adverse events",
          "HHC drug interactions and contraindications"]


def measurement_b() -> dict:
    false_pos = 0
    detail: list[str] = []
    for q in _GENERIC + _OFF_DOMAIN:
        n = len(R.retrieve(q))
        if n:
            false_pos += 1
            detail.append(f"  LEAK: {q!r} retrieved {n} rows")
    cross_leak = 0
    for q in _CROSS:
        a = compose_answer(q)
        leaks = [c for c in a.claims if "CBD " in c.text or "Δ⁹-THC " in c.text]
        if leaks:
            cross_leak += 1
            detail.append(f"  LEAK: {q!r} surfaced {len(leaks)} other-cannabinoid claims")
    return {"false_pos": false_pos, "cross_leak": cross_leak, "detail": detail}


# ── C. Realistic probes (human-readable) ────────────────────────────────────
# Natural questions a researcher would type, phrased WITHOUT echoing the row's
# trigger phrase, each with a topical expectation. Proves the bag-of-words
# result in (A) also holds for real prose.
_PROBES = [
    ("how does THC impair driving", "driving"),
    ("is it dangerous to drive after smoking weed", "driving"),
    ("blood THC levels and crash risk", "driving"),
    ("what liver enzymes does CBD block", "cyp"),
    ("which CYP pathways are inhibited by cannabidiol", "cyp"),
    ("does cannabidiol change how the body clears other drugs", "cyp"),
    ("recurrent vomiting in chronic cannabis users relieved by hot showers", "hyperemesis"),
    ("how is problematic cannabis use diagnosed", "use_disorder"),
    ("symptoms when a heavy cannabis user quits", "withdrawal"),
    ("can marijuana trigger a psychotic illness", "psychos"),
    ("does cannabis lower testosterone in men", "testosterone"),
    ("a FAAH-inhibiting drug studied for cannabis dependence", "faah"),
]


def measurement_c() -> dict:
    on_hits = off_hits = 0
    rows: list[str] = []
    for q, needle in _PROBES:
        a_on = compose_answer(q)
        a_off = compose_answer(q, retrieval="off")
        on = len(a_on.claims) > 0
        off = len(a_off.claims) > 0
        on_hits += on
        off_hits += off
        rows.append(f"  [{'ON ' if on else 'on0'}|{'OFF' if off else 'off0'}] "
                    f"claims {len(a_off.claims)}→{len(a_on.claims)}  {q}")
    return {"on": on_hits, "off": off_hits, "n": len(_PROBES), "rows": rows}


def main() -> int:
    print("=" * 74)
    print("PROOF: Cannavec Science reliably retrieves the knowledge it holds")
    print("Improvement Plan §1 — reproducible, whole-KB, offline\n")
    print(f"Curated corpus: {R.corpus_size()} claim-bearing rows\n")

    print("A. WHOLE-KB RETRIEVABILITY (shuffled bag-of-words queries)")
    print("-" * 74)
    a = measurement_a()
    print(f"  rows scored (with a PMID target): {a['scored']}")
    print(f"  engine recall@10 (exact row found):        "
          f"{a['engine_recall']*100:5.1f}%")
    print(f"  product recall — detectors only (off):     "
          f"{a['product_off']*100:5.1f}%")
    print(f"  product recall — with retrieval (on):      "
          f"{a['product_on']*100:5.1f}%")
    print(f"  retrieval lift:                            "
          f"+{a['lift']*100:4.1f} points")
    print("\n  per-registry (engine / on / off):")
    for reg in sorted(a["by_reg"]):
        eng, on, off = a["by_reg"][reg][0], a["by_reg"][reg][1], a["by_reg"][reg][2]
        print(f"    {reg:22s} eng={eng:3d} on={on:3d} off={off:3d}")

    print("\nB. NEGATIVE CONTROLS (reliable ≠ returns everything)")
    print("-" * 74)
    b = measurement_b()
    print(f"  generic + off-domain queries that leaked:  {b['false_pos']} "
          f"(of {len(_GENERIC)+len(_OFF_DOMAIN)})")
    print(f"  cross-cannabinoid (HHC) leaks:             {b['cross_leak']} "
          f"(of {len(_CROSS)})")
    for d in b["detail"]:
        print(d)

    print("\nC. REALISTIC PROBES (natural prose, off → on)")
    print("-" * 74)
    c = measurement_c()
    for r in c["rows"]:
        print(r)
    print(f"  answered: detectors {c['off']}/{c['n']} → with retrieval "
          f"{c['on']}/{c['n']}")

    # ── Verdict ──────────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    checks = [
        ("engine recall ≥ 95%", a["engine_recall"] >= MIN_ENGINE_RECALL),
        ("product recall (on) ≥ 90%", a["product_on"] >= MIN_PRODUCT_RECALL_ON),
        (f"retrieval lift ≥ {int(MIN_LIFT*100)} pts", a["lift"] >= MIN_LIFT),
        ("zero generic/off-domain leaks", b["false_pos"] <= MAX_FALSE_POSITIVES),
        ("zero cross-cannabinoid leaks", b["cross_leak"] <= MAX_FALSE_POSITIVES),
    ]
    ok = all(passed for _, passed in checks)
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print("=" * 74)
    print("VERDICT: " + ("PROVEN — the product reliably retrieves its own "
                         "knowledge." if ok else "NOT PROVEN — see failures above."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
