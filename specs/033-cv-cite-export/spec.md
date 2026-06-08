# Spec 033 — `/cv:cite` Citation-Lossless Reference Export

**Status**: Draft — design approved 2026-06-07, pending spec review
**Created**: 2026-06-07
**Constitutional gates**: §I (Primary-Source Or Refuse), §II (Deterministic
Verification, Not Deterministic Intelligence), §III (Test-First), §VII (GRADE
Honesty), §VIII (Retraction Enforcement), §X (Offline-Testable Core), §XI
(Citable, Presentable, Traceable Output); M1, M2, M5.

---

## North Star (read first)

`/cv:cite` is the **first user-callable output skill** — the start of the output
layer that turns verified cannabis-science evidence into polished, high-value
artifacts researchers can paste straight into Zotero / Mendeley / EndNote with
zero re-keying (§XI). It is a **citation-lossless transform of the canonical
verified Answer, never a free-text citation generator** (M5/§II): it serializes
only identifiers the backbone already confirmed are real and not retracted, and
it refuses to emit anything it cannot preserve losslessly.

It is deliberately **not** a "cite anything about cannabis" engine. Its coverage
is exactly the coverage of the Answer it transforms — the curated core for the
offline MVP. For anything the backbone has not verified, it emits **nothing**
(an honest empty/refusal), never a plausible-looking fake. Breadth is a retrieval
problem (live tier, then semantic retrieval), not a job for this skill.

## Goals

- Given a research question, emit a **reference export** (BibTeX, RIS, or
  CSL-JSON) of the verified citations behind the composed Answer.
- Enforce the **citation-lossless guarantee in code** (§XI): every
  primary-source identifier and every GRADE label survives into the rendered
  output, or the export is refused. This is the credibility verdict computed by
  `cannavec_science/`, never asserted in prose.
- Emit **nothing** for a refusal Answer or a question with no verified citations
  (§I / §V), with a non-zero exit code so a pipeline can gate on it.
- Reuse the existing `bibliography.py` renderers and the `export.py` lossless
  gate — minimal new code.

## Non-goals (YAGNI)

- **No live retrieval in the MVP.** Offline curated composition only. The cite
  path is Answer-centric, so a later `--augment-live` flag widens coverage to
  verified live citations by changing only how the Answer is composed
  (`compose_answer(..., live=...)`) — reusing the entire render→gate path. Not
  built now.
- **No PDF / styled / formatted output** — that is `/cv:pdf`, a later skill.
- **No new slash command.** The five research commands are capped (§ scope lock);
  `/cv:cite` is a **skill** (separate surface), so no constitution amendment.
- **No CSL style processing** (author-date formatting); raw interchange formats
  only — downstream managers apply styles.

## Architecture (3 components)

### 1. Deterministic gated export — `cannavec_science/export.py`

```
render_citation_export(answer: Answer, fmt: str) -> str | None
```

- `fmt ∈ {"bibtex", "ris", "csljson"}`.
- Returns `None` when `answer.is_refusal` (refusals export to nothing — aligned
  with `export_provenance` returning `()`), or when the lossless gate fails.
- Otherwise: builds entries via `bibliography.bibliography_from_answer(answer)`,
  annotates each entry's GRADE in a format-native note field (BibTeX `note`, RIS
  `N1`, CSL-JSON `note`) so the label survives, renders via
  `bibliography.render(entries, fmt)`, then runs
  `assert_citation_lossless(answer, rendered)` and returns the rendered string
  only if it passes.
- GRADE per citation is sourced **in-process** from `export.export_provenance`
  (`answer._citation_grade_map()`), never from `citations[].grade` in `--json`
  (the documented null-grade gotcha).

### 2. `cite` CLI subcommand — `cannavec_science/__main__.py`

```
python3 -m cannavec_science cite "<question>" [--format bibtex|ris|csljson] [--out FILE]
```

- Composes the offline curated Answer (`compose_answer(question)`), calls
  `render_citation_export`.
- On a string result: print to stdout (or write `--out`), exit `0`.
- On `None`: print an honest one-line reason to **stderr** — `no citable answer:
  <refusal | no verified citations | not citation-lossless>` — and exit non-zero
  (so a pipeline / CI can gate). Never prints a partial or fabricated export.
- Default `--format bibtex`.
- Registered in `_build_parser`; README CLI line + `test_readme_claims` updated
  so the documented subcommand surface stays in lockstep with argparse.

### 3. `/cv:cite` skill — `skills/cv-cite/SKILL.md`

- Thin wrapper: frontmatter description triggers on "export/cite references,
  bibliography, BibTeX/RIS/Zotero for a cannabis-science question."
- Instructs the model to run the `cite` subcommand and present the output as a
  ready-to-paste, citation-lossless reference export — explicitly a **transform
  of verified evidence, never authored citations** (M5). On a non-zero exit, it
  surfaces the honest reason and does **not** invent references.

## Data flow

```
question
  → compose_answer(question)            # offline, verified, deterministic
  → bibliography_from_answer(answer)     # existing renderer
  → GRADE-annotate each entry            # note field, per format
  → render(entries, fmt)                 # existing BibTeX/RIS/CSL-JSON
  → assert_citation_lossless(answer, …)  # §XI gate (export.py)
  → emit  |  refuse (None → non-zero exit)
```

## Refusal / error handling (every decision is code-computed)

| Condition | Behaviour |
|---|---|
| `answer.is_refusal` (safety / individualized) | emit nothing, exit non-zero |
| no verified citations (uncurated indication → empty provenance) | emit nothing, exit non-zero |
| lossless gate fails (an id or GRADE label dropped) | emit nothing, exit non-zero |
| unknown `--format` | argparse usage error |
| `--out` unwritable | error to stderr, exit non-zero |

## Testing (§III — positive + negative per behaviour)

- **Lossless round-trip**: `cite "CBD for Dravet"` → every Answer PMID/DOI appears
  in the BibTeX/RIS/CSL-JSON output; GRADE label survives.
- **Refusal exports nothing**: an individualized-dosing question → `None` /
  non-zero exit, no output.
- **Uncurated indication exports nothing**: `cite "CBD for diabetes"` (now a
  refusal Answer) → `None` / non-zero exit.
- **Lossy render fails the gate**: a render with a PMID or GRADE stripped →
  `render_citation_export`-level guard returns `None` (unit test on the gate).
- **All three formats** preserve identifiers + GRADE.
- **CLI exit codes**: `0` on success, non-zero on every refusal/empty/lossy path.
- **Docs lockstep**: `test_readme_claims` CLI-line guard covers the new
  subcommand.

## Acceptance criteria

1. `cite "CBD for Dravet" --format bibtex|ris|csljson` emits a citation-lossless
   reference export containing the verified PMIDs/DOIs with GRADE preserved.
2. `cite` on a refusal or uncurated-indication question emits nothing and exits
   non-zero.
3. The lossless guarantee is enforced by `export.py`, asserted by tests, not by
   skill prose.
4. Full offline suite stays green; new positive + negative tests land with the
   code (§III).
5. `/cv:cite` skill presents the export as a verified transform and never invents
   citations.
