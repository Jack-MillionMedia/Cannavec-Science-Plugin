# Spec 034 — `/cv:pdf` Evidence-Brief PDF + the grade-INFLATION gate

**Status**: Implemented — 2026-06-08
**Constitutional gates**: §I (Primary-Source Or Refuse), §II (Deterministic
Verification, Not Deterministic Intelligence), §III (Test-First), §V (Safety
Sovereignty), §VII (GRADE Honesty), §X (Offline-Testable Core), §XI (Citable,
Presentable, Traceable Output); M1, M2, M5.

---

## North Star (read first)

`/cv:pdf` is the **flagship output skill** — it turns the canonical verified
`Answer` into a polished, professional **evidence brief** (clinical-journal
style) a researcher can hand to a colleague, attach to a grant, or show a
clinician. It is a **citation-lossless transform of verified evidence, never a
document generator** (§XI / M5): every identifier it prints was confirmed real
and not retracted, every GRADE label is the level the backbone assigned, and
**none is inflated**. It renders an honest artifact (or a refusal) for anything
the backbone has not verified, and refuses to emit anything it cannot preserve
losslessly.

Built on the spec 033 export foundation, this spec also closes the export.py
holes that foundation left open (documented in the v0.7.0 stress test): the
citation-lossless gate guarded GRADE *loss* but not GRADE *inflation*.

## Part A — the grade-INFLATION gate (`cannavec_science/export.py`)

The lossless gate (`assert_citation_lossless` + `grade_adjacency_failures`)
proved a transform never *drops* or *softens* a GRADE. It did not prove the
mirror — that a transform never *inflates* one. Rendering "Level A" beside a
Level-B citation passed every check as long as a "Level B" token survived
somewhere. Presenting evidence as more certain than the backbone graded it is the
exact M5/§VII overclaim this project exists to prevent, so it is now a
code-computed refusal.

1. **`grade_inflation_failures(answer, rendered, window=200)`** — the mirror of
   `grade_adjacency_failures`. Every GRADE-label occurrence is bound to the
   NEAREST identifier within `window`; the binding fails when the label outranks
   the grade the backbone assigned that identifier. The bound identifier must be
   a GRADED citation for a binding to fail — an ungraded reference-context
   citation legitimately appears inside a curated-background section that prints
   that source's own row grade, and flagging that would mis-read honest
   background (and would flag the canonical Markdown brief itself). The
   renderer-level "ungraded citation shows no grade" guarantee is asserted
   per-reference instead. Together adjacency + inflation enforce per-citation
   grade EQUALITY for inline formats.

2. **Token-boundary GRADE floor** — `assert_citation_lossless`'s GRADE-presence
   check was a naive substring `in` ("Level Below threshold" satisfied
   "Level B"). It is now boundary-scoped (`_grade_present`).

3. **`is_refusal` in `Answer.to_dict`** — a refusal still serializes its
   reference citations, so a JSON consumer could mistake it for a brief. The
   refusal state is now a first-class machine-readable field.

### Adversarial hardening (gate found unsound by red-team, then fixed)

A 20-agent adversarial workflow found **3 reproducible bypasses** in the first
cut of the gate — all in the dangerous *overclaim* direction, all while the gate
passed its own 37 tests. Each is now closed with a regression test
(`test_export_inflation.py`, `test_pdf_export.py::TestRefusesKnownBypasses`):

- **Ungraded short-circuit** — the inflation scan skipped a grade label bound to
  an ungraded citation, so "Level A" stamped on a reference-context citation
  passed. Fixed by `grade_inflation_failures(..., flag_ungraded=True)`: over a
  region holding only the answer's evidence (the evidence surface), a grade on an
  ungraded citation is an overclaim. The default stays lenient (background-section
  row grades, canonical Markdown) — the param is the difference between the two
  legitimate scopes.
- **Non-canonical-URL dodge** — the ungraded guard was keyed on the exact
  resolvable URL; swapping to an equivalent URL evaded it. Now the bind is by
  **bare identifier**, and the fragile URL-keyed helper is removed (superseded).
- **Homoglyph / source-vs-render** — a fake grade could read as "Level A" to a
  human while evading an ASCII source scan: Cyrillic/Greek/fullwidth homoglyphs of
  the grade letter *or the anchor word* ("Leveӏ A"), an HTML-entity or inline-tag
  split ("Level&nbsp;A", "Level <b>A</b>"), or the "Grade A" synonym. A second
  red-team round broke the first homoglyph fix here. Now the inflation scan runs
  over **normalized visible text** (`_normalize_visible`): decode HTML entities,
  strip tags/comments, NFKD-fold every compatibility look-alike (fullwidth / math /
  circled / Roman-numeral / ligature), drop combining marks, then fold the
  remaining script confusables — and detects both "Level" and "Grade" anchors, with
  a non-ASCII-letter backstop. This closes the bypass *class*, not instances.

Plus a `_HIDE_STYLE_RE` guard rejecting content-hiding inline styles
(`display:none` etc.) in the evidence surface (defends an unverified
real-hidden/fake-shown substitution vector). The strict checks run on the
evidence surface **extracted from the actual rendered HTML** (`<!--CV:EV-->`
markers), so tampering is caught, not designed around.

A third red-team round then broke the letter-allowlist with **enclosed-alphanumeric
symbols** (🅰 U+1F170 — Unicode category `So`, NFKD-stable) and **tier notations
reusing the anchor** (`Level 1` / `Level I`, Oxford CEBM). The durable fix replaces
the allowlist with **deny-by-default in the grade slot**: enclosed letterforms are
folded to their base letter before NFKD, and after a `Level`/`Grade` anchor the slot
is flagged unless it is exactly ASCII A–E — a tier digit, Roman numeral, or any
non-ASCII glyph is treated as max-rank (in the strict evidence-surface scope, where
A–E is the only legitimate vocabulary; the whole-document/Markdown scope stays
lenient so a background tier scheme is not mis-flagged).

**Honest boundary (documented, in `assert_render_faithful`):** the gate guarantees
no GRADE TOKEN in the `Level`/`Grade` + A–E lexeme — including entity/tag-split,
homoglyph (letter or anchor word), compatibility/enclosed (🅰), and tier-notation
(`Level 1`) forms, over normalized visible text — is dropped, softened, or inflated
relative to the verified Answer. It deliberately does **not** treat `Class A` as a
grade (legitimate domain vocabulary — CB1/CB2 are Class-A GPCRs), nor police a
free-prose certainty claim an author might invent ("definitive evidence"). Both are
acceptable: the renderer never authors prose or alternate grade schemes (M5), and
`export_pdf` gates `render_html`'s own output with no untrusted post-render step —
the adversarial-tamper hardening is defense-in-depth for future output skills.

### Out of scope (documented, deferred)
- **Co-citation grade attribution** (`_citation_grade_map` stamps a claim's grade
  onto every co-cited source): defensible-as-designed (GRADE grades a body of
  evidence per outcome, not a single paper), documented as intentional, and a
  change here re-grades many pinned tests — an upstream grading-model decision,
  not part of this gate.
- **Wrong-indication BLUF for some off-core efficacy queries** (e.g. "cannabis
  for breast cancer" still leads with a chronic-pain SR): an upstream `answer.py`
  composition bug, the documented spine residual. `/cv:pdf` is a faithful
  transform downstream of the Answer; spine correctness is a separate workstream.

## Part B — `/cv:pdf` renderer (`cannavec_science/pdf_export.py`)

A two-layer design that keeps the offline core renderer-independent (§X):

1. **`render_html(answer)`** — pure, stdlib-only, deterministic. Builds a
   self-contained, print-optimized HTML evidence brief from the Answer model.
   Three honest states: full evidence brief; an honest "no curated efficacy
   evidence" brief (0 claims) framing compound background as NOT
   indication-specific; a refusal brief that weaves no evidence (§V).
2. **The §XI gate — `assert_render_faithful`** — the identifier + GRADE-presence
   floor runs over the whole document; the strict per-citation
   adjacency + inflation checks run over the EVIDENCE SURFACE (BLUF prose, graded
   claims, references) extracted from the actual rendered HTML, plus the
   per-reference "ungraded carries no grade" guarantee. Refuses (raises
   `FaithfulnessError`) on any drop / softening / inflation.
3. **`export_pdf(...)`** — writes the HTML, then renders PDF via the best
   available backend, lazily imported and gracefully degrading: headless Chrome
   → pure-Python reportlab → HTML-only ("Print → Save as PDF"). The optional
   backends never break the stdlib core.

## Part C — `pdf` CLI subcommand + `/cv:pdf` skill

- `python3 -m cannavec_science pdf "<question>" [--out PREFIX] [--html-only]`.
- Composes the offline curated Answer, renders, gates, and emits an honest
  artifact. Exit 0 for any honest artifact (brief / refusal / no-evidence);
  non-zero only on a gate failure (would-be lossy/inflated render) or write
  error.
- `skills/cv-pdf/SKILL.md` — thin wrapper: transform-not-author (M5), run the
  subcommand, present the produced path, honour the result, never invent.
- README CLI line + module count kept in lockstep with the guards.

## Testing (§III — positive + negative per behaviour)

- `tests/test_export_inflation.py` — inflation caught; faithful render not
  flagged; token-boundary floor; legend-not-inflation; nearest-binding.
- `tests/test_answer_is_refusal_json.py` — `is_refusal` in `to_dict`.
- `tests/test_pdf_export.py` — render lossless for the curated core; tampered
  (dropped / softened / inflated) renders refused; ungraded refs carry no grade;
  refusal/uncurated honest states; self-contained HTML; backend degradation;
  reportlab fallback emits a real PDF.
- `tests/test_cli_pdf.py` — curated → lossless HTML, exit 0; refusal/uncurated →
  honest artifact, exit 0; `pdf` is a registered subcommand.
- Robustness sweep across 23 diverse questions (curated core, monographs,
  mechanism/PK, safety, refusals, uncurated indications): all citation-lossless,
  non-inflating, honest. Real PDFs (Chrome + reportlab) verified to contain every
  identifier + GRADE in their extracted text layer.

## Acceptance criteria

1. `pdf "CBD evidence in Dravet syndrome"` writes a polished, citation-lossless
   evidence brief (HTML + PDF) with the verified PMIDs/DOIs and GRADE preserved.
2. A render that would drop, soften, or inflate an identifier/GRADE is refused.
3. Refusal and uncurated-indication questions render an honest artifact with no
   fabricated evidence.
4. The grade-inflation gate, token-boundary floor, and `is_refusal` contract
   land with positive + negative tests; the full offline suite stays green.
5. `/cv:pdf` presents the brief as a verified transform and never authors content.
