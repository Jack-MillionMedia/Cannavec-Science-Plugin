# Spec 035 — GRADE-Certainty Grading + Expert Credibility (system-wide, Phase 1)

**Status**: Draft — design approved 2026-06-08, pending spec review
**Created**: 2026-06-08
**Constitutional gates**: §I (Primary-Source Or Refuse), §II (Deterministic
Verification), §III (Test-First), §VII (GRADE Honesty), §XI (Citable, Presentable,
Traceable Output); M1, M3, M5.

---

## North Star (read first)

Make **every** Cannavec output surface — the Markdown brief, the typed JSON, the
CLI, `/cv:cite`, and `/cv:pdf` — read as an **expert-grade, credibility-first
evidence artifact** an expert can distribute unedited. Two shifts:

1. **Elite-accurate, transparent grading.** Express evidence certainty in the
   recognized **GRADE** vocabulary (High / Moderate / Low / Very low /
   Insufficient), grade **each source individually**, and show the **rationale**
   behind every grade (study design, SR/RCT counts, pre-registration, power,
   imprecision, downgrades). The grade a user sees must be standards-aligned,
   individually justified, and **honest about what could and could not be
   assessed** — never false precision.
2. **No system language in output.** Strip every internal/constitutional framing
   (`§…`, `M5`, "scaffolding to reason over", "not the intelligence itself",
   "Verify each identifier before citing") from user-facing text. Those belong in
   code comments, not in an expert's PDF.

This is **Phase 1** (offline, system-wide). Phase 2 (live-retrieval breadth) is a
separate spec and renders through the grading/credibility layer built here.

## Goals

1. **GRADE-certainty wording, system-wide.** A single source of truth maps the
   internal `EvidenceLevel` to a certainty word; every surface leads with it, with
   the letter kept as a small **secondary** auditable tag — "High certainty
   (Level A)".
2. **Computed grade rationale.** Expose the determinants `best_supportable_grade`
   already computes (canonical-SR / confirmatory-RCT counts, pre-registration,
   power, single-study cap, missing-disclosure downgrades) **plus** the
   data-derivable GRADE factors (imprecision from a cited effect estimate's CI;
   large effect from the effect size) as a short, honest string — and mark
   un-assessable factors (indirectness, publication bias) explicitly "not
   assessed", never fabricated.
3. **Per-source grading + surface all curated evidence.** The references/evidence
   section becomes a per-study list: each curated citation rendered as a distinct
   entry with its **own** certainty, rationale, study type, year, and key result —
   not a flat link list — and nothing relevant omitted.
4. **Strip internal/system language** from all rendered output (Markdown + PDF +
   CLI + cite), replaced with factual expert copy.
5. **§XI gate keeps holding** under the new vocabulary — the citation-lossless +
   inflation gate (and its 10 reproduced-bypass regressions) must stay green.

## Non-goals (YAGNI / deferred)

- **Live retrieval / breadth** — Phase 2 (separate spec).
- **No new slash command** (the five are capped; `/cv:*` are skills).
- **No fabricated GRADE factors.** Indirectness and publication bias are not
  reliably computable from current data and are reported "not assessed", never
  invented — honesty over false precision (§VII).
- **No change to retrieval / claim composition** beyond rendering existing
  evidence more completely.

## Architecture (5 components)

### 1. Certainty vocabulary — single source of truth (`evidence.py`)
- `EvidenceLevel` gains `certainty` (`A→"High"`, `B→"Moderate"`, `C→"Low"`,
  `D→"Very low"`, `E→"Very low"`, `Unsupported→"Insufficient"`) and a
  `display(letter: bool = True)` → `"High certainty (Level A)"`.
- `.value` ("Level A") and `.rank` are **unchanged** — internal computation,
  ordering, JSON `grade` back-compat, and the gate's ranking all keep working.

### 2. Grade rationale — the "why" (`evidence.py`)
- A frozen `GradeRationale` dataclass capturing the determinants + a `.summary()`
  human string (e.g. *"1 Cochrane SR + 2 aligned RCTs; large effect"*, *"single
  adequately-powered RCT; wide CI (imprecision)"*, *"observational; not assessed
  for indirectness"*).
- `Claim` / `Source` expose a rationale alongside the grade. `best_supportable_
  grade` is refactored to *also* return its reasoning (the canonical-SR /
  confirmatory-RCT counts and downgrades it already computes), plus:
  - **imprecision** — derived from a cited `EffectEstimate`'s `confidence_interval`
    (CI crossing the null / a flagged non-significant endpoint → an imprecision
    note, and a conservative one-level downgrade where it governs the body grade);
  - **large effect** — a noted up-factor from a large `effect_size` (rendered as a
    reason; an upgrade only where GRADE permits — observational bodies).
  Each enhancement ships with explicit before/after grade review so no grade
  silently changes incorrectly (§VII).

### 3. Render layer — certainty + rationale on every surface
- BLUF frame (`_GRADE_FRAME`) → *"High certainty — <rationale>."*
- Inline citations → *"(PMID 28538134, Moderate certainty)"*.
- Markdown claims / evidence summary / references; PDF badges, chips, references;
  JSON adds `certainty` + `grade_rationale` (keeps `grade`).
- References/evidence list → per-study entries (Component, Goal 3).

### 4. Export/inflation gate vocabulary (`export.py`)
- Extend `_GRADE_LABELS` / `_GRADE_LABEL_RE` / `_grade_rank` to recognise the
  certainty words (`High`/`Moderate`/`Low`/`Very low`/`Insufficient`) ranked from
  `EvidenceLevel`, alongside the existing `Level A–E` / `Grade A–E` (the secondary
  letter tag still appears). `export_provenance` atoms carry the certainty label.
- The inflation/adjacency/lossless checks and all 10 reproduced-bypass regression
  tests stay green under the new labels.

### 5. Internal-language removal (`answer.py`, `pdf_export.py`)
- Replace the user-facing `§…` strings (the to_markdown curated-reference notice,
  verified/live findings notes, §IV refusal/zero-claim messages; the PDF
  background notice / footer / refusal note / findings notes) with factual expert
  copy. Constitutional references remain only in code comments.

## Data flow

```
compose_answer
  → claims + per-source grades (EvidenceLevel + GradeRationale)
  → render layer: EvidenceLevel.display() certainty (+ letter) + rationale.summary()
  → §XI gate (extended certainty vocabulary)
  → emit: Markdown · JSON · CLI · /cv:cite · /cv:pdf   (identical grade semantics)
```

## Testing (§III — positive + negative per behaviour)

- **Certainty map / display** — each level → expected word + "(Level X)".
- **Grade rationale** — each determinant present; un-assessable factors say "not
  assessed"; imprecision/large-effect derive only from real effect-estimate data.
- **Grade-change audit** — a pinned table of (curated question → certainty) before
  vs after; every change is intentional and justified (§VII).
- **Gate vocabulary** — certainty words ranked correctly; inflation flagged when a
  citation shows a stronger certainty than assigned; all 10 bypass regressions +
  lossless tests green.
- **Per-study evidence list** — every curated citation appears as a distinctly
  graded, reasoned entry.
- **No-system-language guard** — a test asserts NO `§`, `Constitution`, `M5`,
  `scaffolding`, or `intelligence itself` appears in any rendered Markdown/PDF
  output (fails loudly if internal framing reappears).
- **Full offline suite green**; every grade-wording assertion across surfaces
  updated in lockstep.

## Acceptance criteria

1. Every surface leads with GRADE certainty + a transparent rationale (letter kept
   secondary); no `§`/internal/system language appears anywhere in output.
2. Each curated study is individually graded with an honest rationale in the
   evidence list; nothing relevant is omitted.
3. The rationale applies the computable GRADE factors and explicitly marks
   un-assessable ones "not assessed" — never fabricated (§VII).
4. The §XI citation-lossless + inflation gate and its 10 reproduced-bypass
   regressions hold under the new vocabulary; full suite green.
5. A guard test fails if internal/system language reappears in rendered output.
