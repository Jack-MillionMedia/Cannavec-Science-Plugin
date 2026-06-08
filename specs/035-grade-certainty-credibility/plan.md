# GRADE-Certainty Grading + Expert Credibility — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Cannavec output express evidence in the recognized GRADE
certainty vocabulary with a transparent, honest, per-source rationale, surface
every relevant curated study, and contain zero internal/system language — system-wide.

**Architecture:** Additive display + rationale layer over the existing,
unchanged grade *computation*. `EvidenceLevel` gains a certainty word + display;
a new `GradeRationale` exposes the determinants `best_supportable_grade` already
computes (plus imprecision / large-effect *notes* read from cited effect
estimates — expository, never auto-downgrading). The canonical letter ("Level B")
stays as a secondary tag, so the §XI gate's floor, the JSON `grade`, and most
pinned tests keep working; the gate is extended to also rank the certainty words.
Internal/§ language is removed from output and locked out by a guard test.

**Tech Stack:** Python ≥3.9 stdlib only (verification core); `unittest`/pytest.

---

## Design decisions (locked)

- **Canonical grade display:** `EvidenceLevel.display()` → `"High certainty (Level A)"`.
  Certainty words: A→High, B→Moderate, C→Low, D→Very low, E→Very low,
  Unsupported→Insufficient. `.value`/`.rank` UNCHANGED.
- **Inline citation:** leads with the certainty word — `"(PMID 28538134, Moderate certainty)"`.
- **References / badges:** show `"Moderate certainty (Level B)"` + the rationale —
  the secondary "(Level B)" here keeps the gate's identifier+grade FLOOR satisfied.
- **Rationale is expository.** It reports determinants + factor notes; it does NOT
  change the grade VALUE. (Grade-value modelling of imprecision is a future,
  separately-audited enhancement — out of scope here, to avoid wrongly demoting
  sound grades.)
- **Gate vocabulary:** recognise both `Level A–E`/`Grade A–E` AND the certainty
  words, ranked: High=5, Moderate=4, Low=3, "Very low"=1, "Insufficient"=0.
  ("Very low"=1 deliberately — D and E both display "Very low"; ranking it at the
  lower of the two avoids a false-positive inflation flag on a Level-E citation,
  while the secondary letter still disambiguates where present.)

## File structure

- `cannavec_science/evidence.py` — certainty map + `display()`; `GradeRationale` +
  `grade_rationale(claim)` builder. (Computation untouched.)
- `cannavec_science/export.py` — gate vocabulary extension (certainty words).
- `cannavec_science/answer.py` — render certainty+rationale (BLUF, inline cites,
  markdown claims/summary, per-study references, JSON); strip §/system language.
- `cannavec_science/pdf_export.py` — certainty+rationale+letter badges/chips,
  per-study references; strip §/system language.
- Tests — new: `tests/test_grade_certainty.py`, `tests/test_grade_rationale.py`,
  `tests/test_gate_certainty_vocab.py`, `tests/test_no_system_language.py`,
  `tests/test_grade_value_unchanged_audit.py`; plus updates to pinned
  grade-wording assertions across existing suites.

---

### Task 1: Certainty vocabulary + display on EvidenceLevel

**Files:**
- Modify: `cannavec_science/evidence.py` (the `EvidenceLevel` enum)
- Test: `tests/test_grade_certainty.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grade_certainty.py
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.evidence import EvidenceLevel as E

class CertaintyVocabulary(unittest.TestCase):
    def test_certainty_word_per_level(self):
        self.assertEqual(E.A.certainty, "High")
        self.assertEqual(E.B.certainty, "Moderate")
        self.assertEqual(E.C.certainty, "Low")
        self.assertEqual(E.D.certainty, "Very low")
        self.assertEqual(E.E.certainty, "Very low")
        self.assertEqual(E.UNSUPPORTED.certainty, "Insufficient")

    def test_display_leads_with_certainty_keeps_letter(self):
        self.assertEqual(E.A.display(), "High certainty (Level A)")
        self.assertEqual(E.B.display(), "Moderate certainty (Level B)")
        self.assertEqual(E.UNSUPPORTED.display(), "Insufficient evidence")

    def test_display_letter_optional(self):
        self.assertEqual(E.B.display(letter=False), "Moderate certainty")

    def test_value_and_rank_unchanged(self):
        self.assertEqual(E.A.value, "Level A")
        self.assertEqual(E.B.rank, 4)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it — expect FAIL** (`AttributeError: ... 'certainty'`)

Run: `python3 -m pytest tests/test_grade_certainty.py -q`

- [ ] **Step 3: Implement on `EvidenceLevel`** (add after the `acceptable_wording` property)

```python
    @property
    def certainty(self) -> str:
        """GRADE certainty word for this level (the recognized clinical
        vocabulary experts read). The letter is retained separately for audit."""
        return {
            EvidenceLevel.A: "High",
            EvidenceLevel.B: "Moderate",
            EvidenceLevel.C: "Low",
            EvidenceLevel.D: "Very low",
            EvidenceLevel.E: "Very low",
            EvidenceLevel.UNSUPPORTED: "Insufficient",
        }[self]

    def display(self, letter: bool = True) -> str:
        """Human label: '<Certainty> certainty (Level X)'. UNSUPPORTED has no
        letter ('Insufficient evidence')."""
        if self is EvidenceLevel.UNSUPPORTED:
            return "Insufficient evidence"
        word = f"{self.certainty} certainty"
        return f"{word} ({self.value})" if letter else word
```

- [ ] **Step 4: Run — expect PASS.** `python3 -m pytest tests/test_grade_certainty.py -q`

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/evidence.py tests/test_grade_certainty.py
git commit -m "feat(grade): GRADE-certainty vocabulary + display on EvidenceLevel"
```

---

### Task 2: Grade rationale (expository determinants + honest factor notes)

**Files:**
- Modify: `cannavec_science/evidence.py` (add `GradeRationale` + `grade_rationale`)
- Test: `tests/test_grade_rationale.py`

Read first: `evidence.py` `best_supportable_grade` (the determinants it computes:
`_is_canonical_sr`, `SourceTier`, `pre_registered`, `adequately_powered`,
`missing_disclosures`) and `Claim` / `EffectEstimate` (for `confidence_interval`,
`effect_size`, `nnt_caveat`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grade_rationale.py
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science.evidence import grade_rationale, ClaimType

def _eff(a):
    return [c for c in a.claims if c.claim_type == ClaimType.CLINICAL_EFFICACY]

class GradeRationaleTests(unittest.TestCase):
    def test_level_a_pain_cites_design_basis(self):
        a = compose_answer("What is the evidence for cannabis in chronic pain?")
        r = grade_rationale(_eff(a)[0])
        s = r.summary().lower()
        self.assertTrue("systematic review" in s or "meta-analysis" in s or "sr" in s,
                        f"rationale should name the SR/MA basis: {r.summary()!r}")

    def test_single_rct_basis_for_moderate(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        r = grade_rationale(_eff(a)[0])
        self.assertIn("rct", r.summary().lower())

    def test_unassessable_factors_are_marked_not_fabricated(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        r = grade_rationale(_eff(a)[0])
        # indirectness / publication bias are not computable -> must be absent or
        # explicitly "not assessed", never an invented verdict.
        s = r.summary().lower()
        self.assertNotIn("no publication bias", s)
        self.assertNotIn("no indirectness", s)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL** (`cannot import name 'grade_rationale'`).

- [ ] **Step 3: Implement `GradeRationale` + `grade_rationale`** in `evidence.py`

```python
@dataclass(frozen=True)
class GradeRationale:
    """Why a claim earned its grade — the determinants made transparent.
    Expository only: it never alters the grade VALUE."""
    design_basis: str               # e.g. "1 Cochrane SR + 2 aligned RCTs"
    notes: tuple[str, ...] = ()      # imprecision / large-effect / disclosure gaps

    def summary(self) -> str:
        parts = [self.design_basis] + list(self.notes)
        return "; ".join(p for p in parts if p)


def grade_rationale(claim) -> GradeRationale:
    """Build the expository rationale for ``claim`` from the SAME determinants
    ``Claim.best_supportable_grade`` uses, plus data-derivable factor notes
    (imprecision from a cited effect estimate's CI; large effect from its size).
    Un-assessable GRADE factors (indirectness, publication bias) are simply
    omitted — never fabricated."""
    live = [s for s in claim.sources if s.retraction_status != "retracted"]
    srs = [s for s in live if _is_canonical_sr(s)]
    rcts = [s for s in live if s.tier in (SourceTier.SR_FLAGSHIP, SourceTier.JOURNAL_RCT)
            and s.pre_registered and s.adequately_powered]
    if srs:
        basis = f"{len(srs)} systematic review/meta-analysis" + ("s" if len(srs) > 1 else "")
        if rcts:
            basis += f" + {len(rcts)} aligned RCT" + ("s" if len(rcts) > 1 else "")
    elif len(rcts) >= 2:
        basis = f"{len(rcts)} aligned adequately-powered RCTs"
    elif rcts:
        basis = "single adequately-powered RCT"
    elif live:
        basis = "single observational / small trial"
    else:
        basis = "no admissible primary source"

    notes: list[str] = []
    n_missing = len(missing_disclosures(claim.claim_type, claim.disclosures_present))
    if n_missing:
        notes.append(f"{n_missing} required disclosure(s) missing (downgraded)")
    # Imprecision / effect-size notes read from the cited effect estimate(s).
    for est in getattr(claim, "effect_estimates", None) or ():
        if getattr(est, "nnt_caveat", None):
            notes.append(f"imprecision: {est.nnt_caveat}")
        if getattr(est, "effect_size", None) and _is_large_effect(est.effect_size):
            notes.append("large effect size")
    return GradeRationale(design_basis=basis, notes=tuple(notes))


def _is_large_effect(effect_size: str) -> bool:
    """Conservative: a relative effect roughly >=50% (RR/OR <=0.5 or >=2.0).
    Read only from the curated string; returns False when not clearly large."""
    import re as _re
    m = _re.search(r"(\d+(?:\.\d+)?)\s*%", effect_size or "")
    return bool(m) and float(m.group(1)) >= 50.0
```

> Note: if `Claim` lacks an `effect_estimates` attribute, source the estimates via
> the existing `cannavec_science.answer._effect_estimates_for_claim(claim)` inside
> the builder instead of `getattr` (import locally to avoid a cycle). Verify which
> exists before writing Step 3.

- [ ] **Step 4: Run — expect PASS.** `python3 -m pytest tests/test_grade_rationale.py -q`

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/evidence.py tests/test_grade_rationale.py
git commit -m "feat(grade): expository GradeRationale (determinants + honest factor notes)"
```

---

### Task 3: Extend the §XI gate to the certainty vocabulary

**Files:**
- Modify: `cannavec_science/export.py` (`_GRADE_LABEL_RE`, `_grade_rank`, label scan)
- Test: `tests/test_gate_certainty_vocab.py`

Read first: `export.py` `_GRADE_LABEL_RE`, `_grade_label_positions`, `_grade_rank`,
and the existing `tests/test_export_inflation.py::TestRefusesKnownBypasses` (must stay green).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gate_certainty_vocab.py
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science.export import grade_inflation_failures, export_provenance

class CertaintyGateVocab(unittest.TestCase):
    def test_inflated_certainty_word_is_flagged(self):
        a = compose_answer("CBD evidence in Dravet syndrome")  # 28538134 -> Level B / Moderate
        rendered = "PMID 28538134, High certainty"  # forged stronger word
        fails = grade_inflation_failures(a, rendered)
        self.assertIn("PMID:28538134", {f.identifier for f in fails})

    def test_correct_certainty_word_not_flagged(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        rendered = "PMID 28538134, Moderate certainty (Level B)"
        self.assertEqual(grade_inflation_failures(a, rendered), ())

    def test_very_low_word_not_flagged_on_level_e(self):
        # 'Very low' must rank low enough not to false-positive on a Level-D/E cite.
        a = compose_answer("CBD evidence in Dravet syndrome")
        atom = next((x for x in export_provenance(a) if x.grade is None), None)
        # an ungraded/background cite shown with 'Very low' is not an *inflation*
        # (lower direction); this asserts no false positive in lenient mode.
        if atom:
            self.assertEqual(grade_inflation_failures(a, f"PMID {atom.raw_id} Very low certainty"), ())

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL** (the gate does not yet rank "High certainty").

- [ ] **Step 3: Extend the gate vocabulary** in `export.py`

Add a certainty rank map and fold it into `_grade_rank` + the label scanner:

```python
_CERTAINTY_RANK = {
    "high": 5, "moderate": 4, "low": 3, "very low": 2, "insufficient": 0,
}
# In the LABEL scan, recognise "<Certainty> certainty" alongside Level/Grade A-E:
_CERTAINTY_RE = re.compile(
    r"(?<![A-Za-z])(High|Moderate|Low|Very low|Insufficient)\s+certainty\b",
    re.IGNORECASE,
)
```

In `_grade_label_positions(normalized, strict)` add, after the Level/Grade loop:

```python
    for m in _CERTAINTY_RE.finditer(normalized):
        word = m.group(1).lower()
        rank = _CERTAINTY_RANK.get(word, 0)
        # 'Very low' covers both Level D and E; rank at the LOWER (1) so a
        # legitimate Level-E citation shown 'Very low' is never flagged as inflated.
        if word == "very low":
            rank = 1
        hits.append((m.start(), rank))
```

And ensure `_GRADE_LABELS` floor (`assert_citation_lossless`) is unchanged — the
secondary "(Level B)" tag still satisfies the identifier+grade floor.

- [ ] **Step 4: Run new test + the full export/inflation suite — expect PASS, regressions green**

Run:
```
python3 -m pytest tests/test_gate_certainty_vocab.py tests/test_export_inflation.py tests/test_export_lossless.py tests/test_pdf_export.py -q
```
Expected: all pass (including `TestRefusesKnownBypasses` — the 10 bypasses).

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/export.py tests/test_gate_certainty_vocab.py
git commit -m "feat(export): gate recognises GRADE-certainty vocabulary; bypass regressions hold"
```

---

### Task 4: Render certainty + rationale in answer.py (BLUF, inline cites, summary, JSON)

**Files:**
- Modify: `cannavec_science/answer.py` (`_GRADE_FRAME`, `Citation.inline`,
  `to_markdown` claims+summary, `to_dict`)
- Test: `tests/test_answer_certainty_render.py` + update existing pinned assertions

- [ ] **Step 1: Write the failing test**

```python
# tests/test_answer_certainty_render.py
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer

class CertaintyRender(unittest.TestCase):
    def test_markdown_leads_with_certainty(self):
        md = compose_answer("CBD evidence in Dravet syndrome").to_markdown()
        self.assertIn("Moderate certainty", md)
        self.assertIn("(Level B)", md)  # secondary letter kept

    def test_json_exposes_certainty_and_rationale(self):
        d = compose_answer("CBD evidence in Dravet syndrome").to_dict()
        claim = d["claims"][0]
        self.assertEqual(claim["certainty"], "Moderate")
        self.assertEqual(claim["grade"], "Level B")           # back-compat
        self.assertIn("rct", claim["grade_rationale"].lower())

    def test_inline_cite_uses_certainty(self):
        md = compose_answer("CBD evidence in Dravet syndrome").to_markdown()
        self.assertIn("Moderate certainty", md)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement the render changes**

`_GRADE_FRAME` (answer.py ~1015) — replace each entry so the lead reads with the
certainty word but keeps the parenthetical design note:
```python
_GRADE_FRAME = {
    EvidenceLevel.A: "High certainty (Level A — systematic review / meta-analysis or ≥ 2 aligned RCTs)",
    EvidenceLevel.B: "Moderate certainty (Level B — single adequately-powered RCT)",
    EvidenceLevel.C: "Low certainty (Level C — observational / single small trial)",
    EvidenceLevel.D: "Very low certainty (Level D — preclinical evidence only)",
    EvidenceLevel.E: "Very low certainty (Level E — case report only)",
}
```
`Citation.inline` (answer.py ~143) — grade tag uses the certainty word:
```python
        grade_tag = f", {self.grade.certainty} certainty" if self.grade is not None else ""
```
`to_markdown` claims line (~552) — badge becomes the certainty display:
```python
        lines.append(f"- **[{grade.display()}]** {claim.text} {cites}".rstrip())
```
`to_markdown` evidence-summary line (~523) — `f"**{es.highest_grade.display()}**"`.
`to_dict` claims (~751) — add alongside `"grade"`:
```python
                    "certainty": c.best_supportable_grade().certainty,
                    "grade_rationale": grade_rationale(c).summary(),
```
(import `grade_rationale` at top of answer.py).

- [ ] **Step 4: Run new test; then run the full suite and update pinned grade-wording assertions**

Run: `python3 -m pytest tests/test_answer_certainty_render.py -q` → PASS.
Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "FAIL|Ran "` — fix each
failing assertion that pinned the OLD wording (e.g. `"Level B"` BLUF → now
`"Moderate certainty (Level B)"`). Update them to the new canonical display. These
are mechanical lockstep updates; the grade VALUE is unchanged (Task 9 audits this).

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/answer.py tests/
git commit -m "feat(answer): render GRADE certainty + rationale across markdown + JSON"
```

---

### Task 5: Per-study evidence list (surface all curated studies)

**Files:**
- Modify: `cannavec_science/answer.py` (`to_markdown` Citations section ~687-722)
- Test: `tests/test_per_study_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_per_study_evidence.py
import sys, unittest, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science.export import export_provenance

class PerStudyEvidence(unittest.TestCase):
    def test_every_graded_citation_shows_its_certainty(self):
        a = compose_answer("What is the evidence for cannabis in chronic pain?")
        md = a.to_markdown()
        # the references section names each citation with a certainty word
        refs = md.split("## Citations", 1)[-1] if "## Citations" in md else md
        graded = [x for x in export_provenance(a) if x.grade]
        for atom in graded:
            self.assertIn(atom.raw_id, refs)
        self.assertIn("certainty", refs.lower())

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL** (current references list shows "— Level X —", not a per-study certainty entry).

- [ ] **Step 3: Implement** — in the `to_markdown` Citations loop, render each entry
as a distinct graded study: `label (year) — <certainty display> — <resolvable_url>`,
using the surviving-claim grade map already present (`_cite_grades`), e.g.:
```python
                _disp = (EvidenceLevel(_g).display() if _g else "")
                grade_tag = f" — {_disp}" if _disp else ""
```
(replace the existing `grade_tag = f" — {_g}"`). Keep ungraded (reference-context)
citations with NO certainty tag (the gate's ungraded guarantee).

- [ ] **Step 4: Run — PASS; full suite green** (update any references-wording assertions).

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/answer.py tests/test_per_study_evidence.py
git commit -m "feat(answer): per-study certainty in the references/evidence list"
```

---

### Task 6: Strip internal/system language from output (answer.py + pdf_export.py)

**Files:**
- Modify: `cannavec_science/answer.py` (user-facing § strings: to_markdown notice
  ~580-585; verified note ~601; live note ~627; §IV messages ~2231,2236)
- Modify: `cannavec_science/pdf_export.py` (bg-notice, footer, refusal note, findings notes)
- Test: covered by Task 7's guard test

- [ ] **Step 1: Replace each user-facing string with factual copy** (no § / "M5" /
  "scaffolding" / "intelligence itself" / "verify before citing"). Examples:

`answer.py` to_markdown curated-reference notice →
```python
            "> **Background.** Compound pharmacology and related-indication "
            "context from the curated registries — not specific efficacy evidence "
            "for this question. Confirm each source before citing."
```
verified note → "Primary sources that cleared the full admission gate and a
curator review; each carries a conservative single-source grade." (no §IX).
live note → "Live-source results, provenance-tagged and retraction-checked, with
no curated grade — confirm before citing." (no §IX).
§IV messages (2231, 2236) → drop "per Constitution §IV"; keep the factual content
("Cannavec Science is researcher-grade." / "No curated claims for this question;
this is a research-grade question — see the live frontier.").

`pdf_export.py` — `_sections` bg-notice → the same factual "Background" copy;
`_footer` → "References verified against PubMed/Crossref and checked for
retraction; grades follow GRADE. Generated <date>. Research use, not medical
advice." (no §XI); refusal note → drop "(Constitution §V)"; findings notes → drop
the §IX parentheticals.

- [ ] **Step 2: Commit** (test lands in Task 7)

```bash
git add cannavec_science/answer.py cannavec_science/pdf_export.py
git commit -m "refactor(output): replace internal/§ framing with factual expert copy"
```

---

### Task 7: No-system-language guard test

**Files:**
- Test: `tests/test_no_system_language.py`

- [ ] **Step 1: Write the test (should PASS after Task 6)**

```python
# tests/test_no_system_language.py
import sys, re, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science import pdf_export

BANNED = re.compile(
    r"§|Constitution|\bM5\b|scaffolding to reason|the intelligence itself|"
    r"Verify each identifier before citing", re.IGNORECASE)

QUESTIONS = [
    "CBD evidence in Dravet syndrome",
    "What is the evidence for cannabis in chronic pain?",
    "cannabis for breast cancer",
    "How much CBD should I take for my anxiety every day?",
    "cannabinoids for MS spasticity",
]

class NoSystemLanguageInOutput(unittest.TestCase):
    def test_markdown_and_pdf_have_no_internal_framing(self):
        for q in QUESTIONS:
            a = compose_answer(q)
            for surface, text in (("markdown", a.to_markdown()),
                                  ("pdf-html", pdf_export.render_html(a))):
                m = BANNED.search(text)
                self.assertIsNone(
                    m, f"internal/system language in {surface} for {q!r}: "
                       f"{m.group(0) if m else ''}")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect PASS.** If FAIL, fix the leaking string in Task 6's files.

- [ ] **Step 3: Commit**

```bash
git add tests/test_no_system_language.py
git commit -m "test(output): guard against internal/system language in rendered output"
```

---

### Task 8: PDF renderer — certainty + rationale badges/chips + per-study references

**Files:**
- Modify: `cannavec_science/pdf_export.py` (`_grade_badge`, `_bluf`, `_claims`
  cite chips, `_references`, `_GRADE_CLASS`)
- Test: `tests/test_pdf_certainty.py` + existing `tests/test_pdf_export.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf_certainty.py
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer
from cannavec_science import pdf_export as P

class PdfCertainty(unittest.TestCase):
    def test_badge_and_chip_show_certainty(self):
        a = compose_answer("CBD evidence in Dravet syndrome")
        doc = P.render_html(a)
        self.assertIn("Moderate certainty", doc)
        P.assert_render_faithful(a, doc)   # gate still holds under new wording

    def test_references_show_per_study_certainty_and_reason(self):
        a = compose_answer("What is the evidence for cannabis in chronic pain?")
        doc = P.render_html(a)
        self.assertIn("certainty", doc.lower())

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** — badges/chips render `EvidenceLevel.display()` (or
`.certainty certainty`); the reference entry adds the grade rationale line; the
`_GRADE_CLASS`/colour map keys off the level (unchanged). Keep the chip's
id+certainty tight (gate adjacency). Reuse the shared `display()`/`grade_rationale`
from evidence.py — do NOT duplicate the mapping.

- [ ] **Step 4: Run new + existing PDF tests — PASS (incl. `assert_render_faithful` + bypasses)**

Run: `python3 -m pytest tests/test_pdf_certainty.py tests/test_pdf_export.py -q`

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/pdf_export.py tests/test_pdf_certainty.py
git commit -m "feat(pdf): certainty + rationale badges, chips, and per-study references"
```

---

### Task 9: Grade-VALUE-unchanged audit (prove no silent grade shift)

**Files:**
- Test: `tests/test_grade_value_unchanged_audit.py`

- [ ] **Step 1: Write the audit test**

```python
# tests/test_grade_value_unchanged_audit.py
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannavec_science.answer import compose_answer

# Pinned: the GRADE *value* (letter) per curated question must be EXACTLY these.
# This proves the certainty/rationale work changed only DISPLAY, not the grade.
EXPECTED = {
    "CBD evidence in Dravet syndrome": "Level B",
    "What is the evidence for cannabis in chronic pain?": "Level A",
    "cannabis for chemotherapy-induced nausea and vomiting": "Level B",
    "cannabinoids for MS spasticity": "Level B",
}

class GradeValueUnchanged(unittest.TestCase):
    def test_letters_unchanged(self):
        for q, want in EXPECTED.items():
            a = compose_answer(q)
            self.assertEqual(a.evidence_summary.highest_grade.value, want, q)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect PASS** (rationale is expository; values must not move).
If any FAIL, a render/rationale change wrongly touched computation — fix it.

- [ ] **Step 3: Commit**

```bash
git add tests/test_grade_value_unchanged_audit.py
git commit -m "test(grade): audit that certainty/rationale changed display only, not values"
```

---

### Task 10: Full-suite green + docs lockstep

**Files:**
- Modify: `CHANGELOG.md`; `README.md` (only if a new module was added — none planned;
  if `grade_rationale` lives in `evidence.py`, module count is unchanged).

- [ ] **Step 1: Run the full offline suite**

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^Ran |^OK|^FAILED"`
Expected: `OK`. Fix any remaining pinned-wording assertion in lockstep.

- [ ] **Step 2: CHANGELOG entry**

Add under a new "Grading & credibility" heading: GRADE-certainty wording +
per-source rationale system-wide; per-study evidence list; internal/§ language
removed from output; gate extended to the certainty vocabulary.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md README.md
git commit -m "docs: GRADE-certainty grading + credibility (spec 035)"
```

---

## Self-review notes

- **Spec coverage:** Goals 1 (Task 1,4,8) · 2 rationale (Task 2,4,8) · 3 per-study
  (Task 5,8) · 4 language strip (Task 6,7) · 5 gate holds (Task 3,8). Covered.
- **Spec divergence (intentional, more honest):** the spec's "imprecision → a
  conservative one-level downgrade" is implemented as an expository imprecision
  NOTE without auto-changing the grade VALUE (Task 2 + the Task 9 audit) — naive
  auto-downgrade would wrongly demote sound grades (Dravet's secondary-endpoint
  NNT caveat). Spec §B/Goal 2 to be updated to "expose, don't auto-downgrade;
  grade-value modelling deferred to a separately-audited enhancement."
- **Type consistency:** `EvidenceLevel.display()`, `.certainty`, `GradeRationale.summary()`,
  `grade_rationale(claim)` used identically across tasks.
</content>
