# `/cv` output-skills foundation

This is the build-ready contract for user-callable **output skills** (`cv:cite`,
`cv:pdf`, `cv:evidence-table`, `cv:clear`, …) that turn verified research into
polished deliverables. It exists so those skills add **value** (provably
preserve the verification) and not **noise** (un-anchored, de-graded prose).

Read this before building any `/cv` feature. It is governed by the constitution
(`.specify/memory/constitution.md`) — §XI (citable/presentable/traceable),
§I (primary-source-or-refuse), §VII (GRADE honesty), §II/M5 (no static answer
generation).

## The one rule

> A `/cv` output skill **transforms an already-verified `Answer` artifact**. It
> never authors content, never re-fetches, never re-grades, and never accepts a
> free-text topic to "write about." Generating new claims is the M5/§II
> anti-pattern; transforming verified atoms is the whole job.

## The canonical artifact (your input)

Every skill starts from the typed `Answer`:

```bash
python3 -m cannavec_science answer "<question>" --json    # machine artifact
```

Its shape is **locked** by `tests/test_answer_json_contract.py` — build against
these fields; they change only deliberately:

- `short_answer` — the GRADE-honest BLUF (already worded to its grade).
- `refusal_reason` — **check this first**; if set (or `claims` is empty on a
  refusal), surface the refusal and **do not render**.
- `claims[]` — `text`, `claim_type`, `grade` (A–E / Unsupported), `population`,
  `sources[]` (`pmid`/`doi`/`url`/`year`/`tier`), and `effect_estimates[]`
  (`n`, `comparator`, `primary_outcome`, `effect_size`, `confidence_interval`,
  `nnt`, `nnt_caveat`) when the registry holds them.
- `citations[]` — `label`, `pmid`/`doi`/`url`, `year`, and `grade` (recomputed
  from the **surviving** claims, so it is never an orphaned grade — see below).

The Markdown brief (`answer.to_markdown()`) is the human-readable twin: it
carries the same identifiers and inline GRADE labels and is itself
citation-lossless against its own provenance.

### GRADE lives on the claim — not a stored snapshot

Per-citation grade is **derived from the surviving claims at serialization
time** (`Answer._citation_grade_map`). Never read a grade you cached before a
claim could be dropped — a dropped wrong-indication efficacy claim must not leave
a Level-A stamp on a "no curated evidence" bibliography. `to_dict`, the Markdown
`## Citations` section, and `bibliography._evidence_level_for_citation` all use
this one source and provably agree (`tests/test_citation_grade_roundtrip.py`).

## The mandatory gate (your output)

Every rendered output MUST pass the citation-lossless check before it is emitted
— this is §XI made mechanical:

```python
from cannavec_science.export import assert_citation_lossless

rendered = render_my_format(answer)          # transform only — never author
report = assert_citation_lossless(answer, rendered)
if not report:
    # refuse to emit — the transform dropped evidence
    raise SystemExit(report.summary())
```

`assert_citation_lossless` checks that **every** primary-source identifier
survives (exact, token-boundary-scoped — the §I non-negotiable) and that every
GRADE label survives (a *floor*: a wholesale or per-tier GRADE strip is caught,
but not a single softened citation).

**For any inline multi-citation render** (Markdown / PDF text / slides where the
grade sits beside its citation) you MUST also assert per-citation GRADE
adjacency — the floor alone would let a skill keep one "Level B" while softening
another:

```python
from cannavec_science.export import grade_adjacency_failures
loose = grade_adjacency_failures(answer, rendered)   # must be empty for inline formats
if loose:
    raise SystemExit(f"GRADE not anchored to: {[a.identifier for a in loose]}")
```

A skill whose format puts GRADE in a separate column skips the adjacency check
and asserts its own column-level invariant instead. `export_provenance(answer)`
gives you the atoms (`identifier`, `grade`) to build that.

## The build pattern

1. Run `answer --json` (or call `compose_answer`) → the verified `Answer`.
2. If `is_refusal` / `refusal_reason` → surface the refusal, stop.
3. **Transform** the artifact into your format (reuse `bibliography.py` for
   reference exports; `claims[].effect_estimates` for tables; `to_markdown()` as
   the source for PDF/slides). Copy verified atoms — do not write new prose.
4. `assert_citation_lossless(answer, rendered)` → refuse to emit on failure.
5. Optional renderers (PDF/PPTX libraries) live in the **optional layer** (§X):
   degrade gracefully to the Markdown brief when the renderer is absent; never
   break the stdlib offline core.

## Namespace: skills, not a sixth command

The five **research** slash commands (`research`, `ask`, `discover`, `verify`,
`rigor`) are capped by the constitution — adding a sixth needs an amendment.
Output capabilities are a **different surface**: ship them as **skills**
(`skills/<name>/SKILL.md`, invoked via the Skill tool), which the cap does not
restrict. Do **not** add `cv:pdf` as a `.claude/commands/cv/*.md` slash command
— that would be a sixth research command and a constitution violation.

## Recommended first skills (each names the primitive that backs it)

| Skill | Transforms | Backed by | Effort |
|---|---|---|---|
| `cv:cite` | `Answer` → BibTeX/RIS/CSL-JSON for Zotero, GRADE in note | `bibliography.py` (§XI-mandated) | S |
| `cv:clear` | manuscript / id list → per-citation PASS/FAIL-retracted table | `pubmed_verify` + `retraction` + `rigor` | M |
| `cv:pdf` | Markdown brief → cited PDF + embedded bibliography | `to_markdown()` + `bibliography.py` + the gate | M |
| `cv:evidence-table` | `claims[].effect_estimates` → summary-of-findings CSV/MD | `Answer.to_dict()` | M |
| `cv:presentation` | brief → slide deck (GRADE on every claim slide) | same as `cv:pdf`; **build after** the answer-relevance work | M–L |

## Anti-patterns (these make a skill noise)

- Accepting a free-text topic and "generating" a PDF/deck/answer (M5/§II).
- Reading a grade from a stored snapshot instead of the surviving-claims map.
- Rendering a refused answer.
- Dropping/softening an identifier or GRADE label (caught by the gate — never
  bypass it).
- Marketing the export as journal-ready: offline curated citations carry a
  Cannavec **label**, not the real article title (real-title backfill is a
  tracked follow-up on the live-verify path).
