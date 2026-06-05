# Spec 032 — Knowledge-Base Credibility Audit (Phase 1 of the KB grounding flywheel)

**Status**: Draft — design approved 2026-06-05, pending spec review
**Created**: 2026-06-05
**Constitutional gates**: §I (Primary-Source Or Refuse), §II (Deterministic Verification),
§III (Test-First), §VII (GRADE Honesty), §VIII (Retraction Enforcement); M2, M4, M7.

---

## North Star (the guiding objective — read first)

The long-term goal is to make the **science side of `mc-knowledge-base` the most
credible, accurately-audited, and comprehensive cannabis-science knowledge base
ever assembled.** The Cannavec Science verification engine is the **immune system
and growth engine** for that knowledge base: it audits what is already there,
corrects or routes what is wrong, and gates what gets added — so that every fact
the KB feeds into Pinecone (and therefore into every downstream AI answer) is
real, not retracted, claim-supported, and GRADE-honest.

This is **not** the registry-growth flywheel retired in the MVP teardown (which
grew a static answer-store — the M5 anti-pattern). The KB is a **grounding corpus
the model reasons over, gated by verification**, which is exactly what M7 calls
for: structured knowledge, high-quality retrieval, expert feedback loops, and
workflows that measurably improve over time.

Spec 032 is **Phase 1**: the read-only audit that establishes the credibility
baseline everything else builds on.

## The flywheel and roadmap (where Phase 1 fits)

The user already runs this flywheel **by hand** — KB merge logs show
*"Merged from: Cannavec plugin research … Merged by: Claude / Neil Cartwright"*
following `00_meta_layer/workflow_guide.md`. The programme below systematizes the
verification half of that loop, sequenced **read → answer → write → outputs**
(prove the pipeline is trustworthy before letting it mutate the KB):

| Phase | Capability | Risk | Spec |
|---|---|---|---|
| **1 (this)** | **Audit** — read-only credibility report over science files | none (read) | 032 |
| 1.5 | **Pre-upsert CI gate** — the same audit as a GitHub Action on the KB repo, blocking merge on confirmed-bad citations / grade violations | none (read) | future |
| 2 | **Grounded Q&A** — ask → semantic-search KB + live `discover` → verify → cited answer | low (read) | future |
| 3a | **Write-back** — stamp per-file verdicts (`needs_review`, verification status) onto KB files | medium (mutates) | future |
| 3b | **Expand** — when strong evidence is missing, verify it and add it to the KB | high (mutates) | future |
| 3c | **Correct / triage** — flag and route weak, outdated, or wrong content for review | high (mutates) | future |
| 4 | **Outputs** — reports / PDFs / decks / decision-support from verified evidence | low | future |

Each later phase reuses Phase 1's **per-file verdict schema** unchanged.

## Problem

`mc-knowledge-base` is the **staging ground reviewed by a human before content is
upserted to Pinecone**. A fabricated PMID, a retracted source, a claim its
citation does not support, or an inflated evidence grade that slips through review
poisons the vector store and silently corrupts every AI answer grounded on it.
Today that review is manual and unaided. The KB is large (777 `.md` files, 711
with rich YAML frontmatter) and densely cited (folder 5 *Medical*: 78/83 files
cite sources; folder 6 *Evidence*: 40/86) — too large to re-verify by hand on
every change.

The KB is an **ideal audit target** because it already speaks the verification
language: inline citations in a parseable form (`(Devinsky 2017, *NEJM*,
PMID: 28538134)` plus reference tables with PMID columns), receptors tagged with
UniProt accessions (`CB1 (P21554)`), and frontmatter that declares
`evidence_grade` and a per-claim `evidence_grade_map`. The plugin's existing
audit scripts (`evals/audit_pmids.py`, `audit_dois.py`, `audit_chembl.py`,
`audit_uniprot.py`, `audit_claim_support.py`) already perform exactly these live
checks against the **curated registries** — Phase 1 generalizes that machinery to
take its identifier/claim set from **extracted KB-file citations** instead.

## Goal

Given a local clone of `mc-knowledge-base`, produce a **per-file verdict** and a
**ranked corpus report** that flags science files unsafe to upsert — fabricated or
retracted citations, claims the cited source does not support, and inflated
evidence grades — for the operator's human review. Read-only. Deterministic and
offline-testable; live verification when the network is available.

## Access control (standing principle for the whole programme)

**The KB audit, and every future KB-write/curate capability, is an OPERATOR tool —
never an end-user surface.** Only the owner, the owner's boss, and explicitly
granted operators may run it; end users of the research plugin must never be able
to edit, audit-to-write, or mutate the knowledge base.

- Phase 1 expresses this as **CLI-only**: no slash command, no API endpoint, no
  agent/skill entry point. (The five user-facing slash commands stay research-only;
  the constitution's "exactly five slash commands" rule is therefore untouched.)
- Future write phases (3a–3c) MUST keep KB mutation behind operator-only surfaces
  and an explicit human-approval gate. This principle is part of the spec contract,
  not an implementation detail.

## Scope

**In scope (v1 default):** `cannabis/5. Medical & Therapeutic Use/` and
`cannabis/6. Evidence & Clinical Validation/` — the clinical-evidence core where
citations concentrate and where a wrong citation does the most harm. Configurable
via `--include` / `--exclude` path globs.

**Out of scope (skipped):** `cannabis/` folders 1–4 and 7–11, `news/`, `Trash/`,
all of `cannabis-faq/`, `README.md` files, and empty files. Non-science content is
never audited (M3 / constitution §IV science-only scope). **Documented next scope
expansion:** folders 3 (*Phytochemistry*) and 4 (*Pharmacology & Mechanisms*),
which are also citation-dense (55/80 and 26/30).

**Not in this increment (YAGNI):** no write-back to files or Pinecone; no CI gate
(Phase 1.5); no model-in-the-loop judgement or auto-correction (Phase 2/3); no
phytochemistry-rigor or authoring-standard-compliance checks (a deliberately
deferred bundle — see Future work).

## What it checks — the three gates

For each in-scope file, after extracting its citations, claims, and declared
grades:

### Gate 1 — Citation integrity (reuses `verify` + `retraction`)
Every extracted identifier (PMID / DOI / NCT / ChEMBL / UniProt) is verified live:
does it resolve to a real record, and is that record retracted? Verdicts per
identifier: `clean` / **`fabricated`** (does not resolve) / **`retracted`**.

### Gate 2 — Claim support (reuses `claim_support`)
For each (claim, citation) pair, does the cited source's abstract actually support
the claim attached to it? Verdicts: `supported` / `unverified` (soft — review
queue, non-failing) / **`contradiction`** (the abstract asserts the opposite —
failing). Mirrors `evals/audit_claim_support.py`: only a direction contradiction
fails a file.

### Gate 3 — GRADE honesty (reuses the `evidence.py` grade ladder; conservative)
Derive the **supportable grade ceiling** from the file's declared study
composition (`study_counts`, `evidence_grade_map`) using the deterministic grade
ladder (e.g., no completed adequately-powered RCT → ceiling Level B; only
observational/case-series → ceiling Level C; mechanistic/in-vitro only → Level D).
Flag where the file's declared `evidence_grade` **exceeds** that ceiling
(inflation). **Conservative by design:** flags clear inflation **for review**;
never auto-fails on a grade judgement in v1. Deepening this is explicit future work.

## Architecture

Four small, independently testable units in a new `cannavec_science/kb_audit/`
package, plus one CLI verb. Each unit answers *what it does / how you use it /
what it depends on*:

1. **`scope.py`** — `select_files(repo_path, include, exclude) -> list[Path]`.
   Applies the taxonomy + frontmatter scope rules. Depends on: filesystem only.
2. **`extract.py`** — `extract(path) -> FileRecord`. Parses YAML frontmatter
   (`evidence_grade`, `evidence_grade_map`, `study_counts`) and pulls body
   citations (inline `PMID:`/`doi:`/`NCT…` + reference-table cells), each tied to
   the nearest claim sentence. Pure function. Depends on: stdlib + a YAML reader.
3. **`checks.py`** — `audit_record(record, fetchers) -> FileVerdict`. Runs the
   three gates, dispatching to the existing engine
   (`pubmed_verify`/`uniprot_verify`/`retraction`, `claim_support`, `evidence`).
   Live calls are **injected fetchers** (offline-testable, §III). Depends on: the
   verification engine.
4. **`report.py`** — `render(verdicts) -> (markdown, json)`. Aggregates and ranks
   by severity, with summary stats. Pure. Depends on: nothing.

**CLI:** `python3 -m cannavec_science kb-audit <repo_path> [--include G] [--exclude G]
[--changed-only] [--json] [--out FILE]`. (Operator CLI verb; deliberately *not* a
slash command — see Access control.)

**Data flow:** `repo_path → scope.select_files → [extract per file] → [checks per
record, deduping identifiers across the corpus → one live verify per unique id] →
report.render → markdown + JSON`.

## Verdict and report schema (reusable across all later phases)

```
FileVerdict:
  path: str
  in_scope: true
  status: "PASS" | "FLAG" | "FAIL"          # FAIL = ≥1 fabricated/retracted/contradiction
  citation_findings: [{ id, type, verdict, source_title?, note }]
  claim_findings:    [{ claim, id, verdict, note }]
  grade_finding:     { declared, ceiling, verdict: "ok"|"inflated"|"inconclusive", note }
  reasons: [str]                            # human-readable, severity-ordered
  audited_at: <stamped by caller, not the pure core>
```

`status` rules: **FAIL** if any citation is `fabricated`/`retracted` or any claim
is a `contradiction`; **FLAG** if only soft issues (grade inflation, `unverified`
claims, inconclusive fetches worth a look); **PASS** otherwise. The corpus report
lists FAILs first, then FLAGs, with counts. The same `FileVerdict` is what the CI
gate (1.5) thresholds on and what write-back (3a) stamps onto files — designed once.

## Reliability and determinism (inherits the engine's philosophy)

- **Unfetchable ≠ fabricated.** A network/down failure yields `inconclusive`, never
  a false `fabricated`/`retracted`. Only a *confirmed* bad record fails a file.
- **Unparseable file** → flagged in the report, never a crash; the run continues.
- **Deterministic + offline-testable.** All live calls are injected fetchers
  (§III); identical input → identical verdict. Live verification is an additive
  layer, exactly as the existing `evals/audit_*.py` scripts work.
- **Dedupe.** Identifiers are verified once per corpus run (one `PMID 28538134`
  check serves every file that cites it). Honor `NCBI_API_KEY` for rate limits.

## Testing (§III — every gate ships positive + negative)

A fixture mini-KB under `tests/fixtures/kb_audit/` with injected fetchers:
- a **clean** science file → `PASS`
- a **fabricated-PMID** file → `FAIL` (citation `fabricated`)
- a **retracted-PMID** file → `FAIL` (citation `retracted`)
- a **claim-contradiction** file → `FAIL` (claim `contradiction`)
- a **grade-inflated** file (declares Level A, only observational studies) → `FLAG`
- a **non-science** file (e.g. under `cannabis-faq/`) → skipped (not in verdicts)
- an **unfetchable** identifier under simulated network-down → `inconclusive`, file
  not failed on that basis

Plus unit tests per module (`scope`, `extract` parsing edge cases, `report`
ordering).

## Success criteria

1. `python3 -m unittest discover -s tests` stays green offline (the new tests run
   with injected fetchers; no network in CI).
2. Run against the real `mc-knowledge-base` (folders 5 + 6) with `NCBI_API_KEY`:
   produces a per-file + corpus credibility report in a single command.
3. The seeded fabricated, retracted, contradiction, and grade-inflated fixtures are
   each caught with the correct status; the clean and non-science fixtures are not
   mis-flagged.
4. Zero false `fabricated`/`retracted` verdicts on identifiers that merely could not
   be fetched.

## Future work (explicitly documented to inform the north star)

Toward *the most credible, audited, and comprehensive cannabis-science KB ever
assembled*:

- **Scope expansion:** add folders 3 (Phytochemistry) + 4 (Pharmacology), then the
  remaining science folders.
- **Check depth:** add the deferred bundle — phytochemistry rigor (isomer/dose/
  UniProt correctness via `rigor_checks`) and authoring-standard compliance
  (required frontmatter, locked-format rules from
  `00_meta_layer/cannabis-authoring-standard.md`).
- **GRADE honesty:** move from the conservative ceiling-inflation heuristic to a
  fuller re-grade of the file's body against the live evidence it cites.
- **Phase 1.5 — CI gate:** run the audit on changed science files in every KB-repo
  PR; block merge (→ upsert) on `FAIL`. Operator-reviewed `FLAG`s allowed.
- **Phase 2 — Grounded Q&A** over the audited KB (semantic search + live discover +
  verify); requires the Pinecone connector (currently unbuilt; API access also
  needs valid credentials — the key was rejected during design).
- **Phase 3 — Write-back / Expand / Correct:** stamp verdicts onto files
  (`needs_review`), add missing verified evidence, and route weak/outdated/wrong
  content for review — all operator-only, human-gated, reusing the FileVerdict
  schema.
- **Phase 4 — Outputs:** verified reports / PDFs / presentations / decision-support.
- **Governance note:** if a KB surface is ever wanted beyond the operator CLI, the
  constitution's "exactly five slash commands" rule must be revisited via amendment
  — it is intentionally untouched here.

## Open questions (to resolve during planning, not blocking)

- Exact YAML reader: a tiny stdlib-only frontmatter parser (preserves the zero-pip
  core, §X) vs. an optional dependency. Default: stdlib-only mini-parser for the
  fields we need.
- Claim↔citation association heuristic for inline citations (nearest-sentence vs.
  reference-table row): start with nearest-sentence + table-row, measure on the
  real corpus, refine.
- Report destination: stdout + `--out` file (default), with the JSON form ready for
  the CI gate to consume.
