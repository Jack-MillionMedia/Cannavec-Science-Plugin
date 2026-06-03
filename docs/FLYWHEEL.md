# The expert-gated curation flywheel (Constitution §IX)

> Grow the verified tier **through the gate, not around it** — without growing
> the defect surface.

Constitution §IX names a flywheel — *live discovery → identifier audit →
claim-support check → human approves → curated* — and forbids fully-automatic
promotion. Until now it was named but unbuilt. This is that pipeline, as
deterministic code, orchestrating the checks the codebase already ships.

It is an **orchestrator that chains three workflows**:

| Workflow | Stage | Code | Reuses |
|---|---|---|---|
| **Fan-out & synthesize** (retrieval) | `fanout()` | gather live + index candidates → dedup → rank | `live.run_discovery`, `ranker.rank_candidates`, `source_index` |
| **Generate & filter** (curate) | `gate()` | safety → identifier audit → retraction → claim-support (+ verbatim quote) → phytochemistry rigor → conservative GRADE | `pubmed_verify`, `retraction`, `claim_support`, `rigor_checks`, `safety`, `evidence` |
| **Classify & act** (index routing) | `classify()` / `stage()` | lane the candidate, route it to the staging queue | `curation_store` |

Nothing here re-implements a check. The flywheel is the wiring §IX was missing.

## Three tiers

1. **Candidate pool** — `data/primary_source_index.csv` (7,500 harvested
   identifiers). Ungated.
2. **Verified tier** — `data/verified_sources.jsonl` *(new)*. Gate-passed,
   quote-anchored, conservatively-graded, **human-approved** primary sources.
   This is the tier the flywheel grows. It is deliberately distinct from the
   candidate pool and from the hand-authored registry rows, so it never trips
   `test_source_index_integrity`.
3. **Curated registries** — the `*.py` registry modules (~199 identifiers).
   The richest tier; authoring one is a clinical-depth task (an expert
   *graduates* a verified source into a full registry row).

## Two lanes — the honesty mechanism for "no experts yet"

The gate reduces each promotion decision to a set of *mechanical facts*. What it
cannot reduce, it does not pretend to:

- **`BASIC_APPROVABLE`** — identifier network-verified, not retracted, claim
  **supported** with a verbatim abstract quote, phytochemistry-clean, and a
  conservative grade (≤ Level C, single source). These are facts a
  non-specialist curator can confirm. Safe to promote.
- **`NEEDS_EXPERT`** — mechanically sound, but the call hinges on clinical
  depth: grade ≥ B, an evidence-synthesis (SR / meta-analysis) design, weak or
  partial claim support, a contradiction risk, or an identifier we could not
  verify. Held until an expert exists. **Never auto-promoted, never faked.**
- **`REJECT`** — failed a mechanical gate (identifier doesn't resolve /
  retracted / claim unsupported or contradicted / rigor violation). Recorded
  with the reason so the **defect rate is measured, not hidden**.

This is how the verified tier grows *without* growing the defect surface: the
gate catches the ~8 % defect classes before a human sees them, and the
clinically-deep judgments are **deferred, not faked**.

The flywheel **never** assigns Level A — Level A requires a systematic-review /
≥2-aligned-RCT judgment, which is exactly the call it defers (`evidence.py`).

## The blended brief: three visibly-distinct tiers

A single answer can carry all three tiers, each clearly fenced (Constitution
§IX, "one blended brief"):

1. **Curated core** — registry claims, GRADE inline at each citation.
2. **Verified breadth** *(new)* — gate-passed, human-approved sources under
   `## Verified breadth — gate-passed, human-approved`, each with a conservative
   single-source grade (`[verified · Level C] PMID …`) and a verbatim quote.
3. **Live frontier** — provisional `live_*` hits, reranked + retraction-checked.

Verified breadth is woven by `weave_verified_findings()` (offline; reads the
local verified store), is reranked by relevance, **re-checks retraction at
composition time** (§VIII — a source retracted since promotion is badged and
pinned last), and **never changes the curated grade**. Opt-in:

```bash
python3 -m cannavec_science answer "Is cannabis effective for Crohn's disease?" --verified
```

## Demand instrumentation — promote what users actually ask

`cannavec_science.demand` is the read-time half: every answer can record one
event (topic, coverage, whether any claim actually addressed the topic). A
question like *"is cannabis effective for fibromyalgia?"* that comes back with
generic pain-review rows which never mention fibromyalgia books as a
**topic-specific miss** — the exact hole the eval surfaces. Aggregated, the
ledger ranks topics by miss volume, and that ranking is the flywheel's fan-out
priority.

## CLI

```bash
# read-time: where are the holes?
python3 -m cannavec_science demand-report

# stage 1-3: fan out a demand topic, gate it, route to the queue
python3 -m cannavec_science curate-scan "cannabidiol Crohn's disease" --network

# batch driver: work down the top demand holes, one gated turn each
python3 -m cannavec_science curate-sweep --holes 5            # dry preview (topics + queries)
python3 -m cannavec_science curate-sweep --holes 5 --network  # execute the live fan-out

# review the queue (default: pending)
python3 -m cannavec_science curate-queue --lane basic_approvable

# the human gate (§IX): promote / reject / revoke — requires a named approver
python3 -m cannavec_science curate-apply --id 33858011 --approver you@lab
python3 -m cannavec_science curate-apply --id 29538683 --approver expert@lab --expert-override
python3 -m cannavec_science curate-apply --id 33858011 --approver you@lab --reject --reason "off-topic"
python3 -m cannavec_science curate-apply --id 33858011 --approver you@lab --revoke --reason "bad read"

# health: verified-tier size, queue by lane, and the defect rate
python3 -m cannavec_science curate-stats
```

`curate-scan` is offline by default (a dry run that holds everything it cannot
network-verify as `NEEDS_EXPERT`). `--network` fans out live discovery and
verifies identifiers, so claim-supported sources can reach `BASIC_APPROVABLE`.

Stores are redirectable with `CANNAVEC_CURATION_DIR` (used by the test-suite to
stay hermetic).

## Reproducing the seeded first turn

```bash
python3 evals/demand_probe.py      # instrument a demand profile  → demand_log.jsonl
python3 evals/seed_flywheel.py     # one real gated turn for the holes → staging_queue.jsonl
```

The seeded queue (committed) holds 10 real, PubMed-confirmed, non-retracted RCTs
across IBD / gut, fibromyalgia, and sleep — 8 `BASIC_APPROVABLE`, 2
`NEEDS_EXPERT`, 0 defects. (An 11th candidate, PMID 30374683, was auto-excluded
because it is already a curated registry fact — the flywheel never re-proposes
what the registries already hold.) Nothing is promoted: the queue is `pending`
for a human to approve.

## The path to ~1,500

199 curated identifiers → 1,500 is ~1,300 promotions, reached **one
human-approved turn at a time**, demand-first. Each topic turn fans out ~25
live candidates, gates them, and stages the survivors by lane; the curator
clears the `BASIC_APPROVABLE` lane and parks `NEEDS_EXPERT` for when expert
review exists. The defect rate in `curate-stats` is the guard rail — if it
climbs, the gate (not the human) is doing the filtering, which is the point.
