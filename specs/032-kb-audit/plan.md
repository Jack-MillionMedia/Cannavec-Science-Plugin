# KB Credibility Audit (spec 032) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, operator-only CLI (`python3 -m cannavec_science kb-audit <path>`) that audits the science files of `mc-knowledge-base`, verifying every citation is real + not retracted, checking claims against their cited source, and flagging inflated evidence grades — emitting a per-file verdict + ranked corpus report that triages each file into `READY` / `IMPROVE` / `PASS` for human review before upsert.

**Architecture:** A new `cannavec_science/kb_audit/` package of small pure units (`model` → `frontmatter` → `scope` → `extract` → `checks` → `verdict` → `report`) plus one argparse subcommand in `__main__.py`. It **reuses the existing engine** for all verification (`pubmed_verify`, `retraction`, `uniprot_verify`, `claim_support`, `evidence`) and follows the repo's offline convention: every network call goes through an **injectable fetcher** so the whole suite runs offline (Constitution §X). Nothing is ever written back to the KB (Phase 1 is read-only; M5).

**Tech Stack:** Python ≥ 3.9, stdlib only (zero pip). `unittest` (`python3 -m unittest discover -s tests`). Reuses `cannavec_science.{pubmed_verify,retraction,uniprot_verify,claim_support,evidence,_markdown_skip}`.

---

## Shared contract (read before any task)

These types are defined once in Task 1 (`kb_audit/model.py`) and used **verbatim** by every later task. Do not rename fields.

```python
@dataclass(frozen=True)
class Citation:
    identifier: str            # "28538134" / "10.1056/NEJMoa1611618" / "NCT05076903"
    id_type: str               # "PMID" | "DOI" | "NCT" | "ChEMBL" | "UniProt" | "unknown"
    claim: str                 # nearest preceding sentence (the claim this cite backs)

@dataclass(frozen=True)
class FileRecord:
    path: str
    in_scope: bool
    declared_grade: str | None # raw frontmatter value, e.g. "Level B" (None if absent)
    study_counts: dict         # {"systematic_reviews": 1, "observational_cohort": 1, ...}
    citations: tuple           # tuple[Citation, ...]
    parse_error: str | None = None

@dataclass(frozen=True)
class Finding:
    gate: str                  # "citation" | "claim" | "grade"
    issue: str                 # one-line description
    evidence: str              # the verified fact behind it
    verdict: str               # fabricated|retracted|contradiction|unverified|inflated|inconclusive
    recommended_action: str
    route: str                 # "quick_fix" | "improve_agent" | "deeper_research"

@dataclass(frozen=True)
class FileVerdict:
    path: str
    in_scope: bool
    routing: str               # "READY" | "IMPROVE" | "PASS"
    status: str                # "PASS" | "FLAG" | "FAIL"
    priority: int              # sort key, ascending = act sooner (0 READY .. 3 PASS)
    credibility: dict          # {"citations_clean": int, "citations_total": int, "open_findings": int}
    findings: tuple            # tuple[Finding, ...]
```

**Routing rule (the Phase-3 seam — keep it in one place, `verdict.py`):**

| finding verdict | route | status contribution |
|---|---|---|
| `retracted` | `improve_agent` ("find the superseding study") | FAIL |
| `fabricated` / `not_found` / `mismatch` | `improve_agent` ("replace with a verified primary source") | FAIL |
| `contradiction` | `improve_agent` ("cited source contradicts the claim — rework") | FAIL |
| `unverified` | `deeper_research` ("find a supporting primary source or hedge to true grade") | FLAG |
| `inflated` | `quick_fix` ("downgrade declared evidence_grade to the supportable ceiling, or add stronger evidence") | FLAG |
| `inconclusive` | (no finding emitted; counted only) | — |

`routing`: any `improve_agent`/`deeper_research` finding → **IMPROVE**; only `quick_fix` findings → **READY**; no findings → **PASS**. `status`: any FAIL-contributing finding → **FAIL**; else any finding → **FLAG**; else **PASS**. `priority`: `READY`→0, `IMPROVE`+FAIL→1, `IMPROVE`+FLAG-only→2, `PASS`→3.

---

## File structure

| File | Responsibility |
|---|---|
| `cannavec_science/kb_audit/__init__.py` | package marker + `audit_file` / `audit_path` top-level entry re-exports |
| `cannavec_science/kb_audit/model.py` | the five frozen dataclasses above (no logic) |
| `cannavec_science/kb_audit/frontmatter.py` | `parse_frontmatter(text) -> dict` — tiny stdlib reader for the fields we need |
| `cannavec_science/kb_audit/scope.py` | `select_files(root, include, exclude) -> list[str]`; `is_in_scope(path)` |
| `cannavec_science/kb_audit/extract.py` | `extract(path) -> FileRecord` (frontmatter + citations + nearest-claim) |
| `cannavec_science/kb_audit/checks.py` | the three gates over a `FileRecord`, network injected |
| `cannavec_science/kb_audit/verdict.py` | assemble `Finding`s → `FileVerdict` (routing rule) |
| `cannavec_science/kb_audit/report.py` | `render(verdicts) -> (markdown, json_str)` ordered by `priority` |
| `cannavec_science/__main__.py` | add `kb-audit` subparser + `_cmd_kb_audit` handler |
| `tests/test_kb_audit_*.py` | one test file per unit + an end-to-end fixture test |
| `tests/fixtures/kb_audit/` | the mini-KB fixtures |

---

### Task 1: Shared model

**Files:**
- Create: `cannavec_science/kb_audit/__init__.py` (empty for now)
- Create: `cannavec_science/kb_audit/model.py`
- Test: `tests/test_kb_audit_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_model.py
import unittest
from cannavec_science.kb_audit.model import Citation, FileRecord, Finding, FileVerdict


class ModelTests(unittest.TestCase):
    def test_citation_is_frozen_and_typed(self):
        c = Citation(identifier="28538134", id_type="PMID", claim="CBD reduces seizures.")
        self.assertEqual(c.identifier, "28538134")
        with self.assertRaises(Exception):
            c.identifier = "x"  # frozen

    def test_verdict_carries_routing_and_findings(self):
        f = Finding(gate="citation", issue="retracted", evidence="local registry",
                    verdict="retracted", recommended_action="find superseder",
                    route="improve_agent")
        v = FileVerdict(path="a.md", in_scope=True, routing="IMPROVE", status="FAIL",
                        priority=1, credibility={"citations_clean": 0, "citations_total": 1,
                        "open_findings": 1}, findings=(f,))
        self.assertEqual(v.findings[0].route, "improve_agent")
        self.assertEqual(v.routing, "IMPROVE")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_model -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cannavec_science.kb_audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# cannavec_science/kb_audit/__init__.py
"""Read-only credibility audit of knowledge-base markdown files (spec 032)."""
```

```python
# cannavec_science/kb_audit/model.py
"""Shared frozen data model for the KB credibility audit (spec 032)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    identifier: str
    id_type: str
    claim: str


@dataclass(frozen=True)
class FileRecord:
    path: str
    in_scope: bool
    declared_grade: str | None
    study_counts: dict
    citations: tuple
    parse_error: str | None = None


@dataclass(frozen=True)
class Finding:
    gate: str
    issue: str
    evidence: str
    verdict: str
    recommended_action: str
    route: str


@dataclass(frozen=True)
class FileVerdict:
    path: str
    in_scope: bool
    routing: str
    status: str
    priority: int
    credibility: dict
    findings: tuple
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_model -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/__init__.py cannavec_science/kb_audit/model.py tests/test_kb_audit_model.py
git commit -m "feat(kb-audit): shared frozen data model (spec 032 task 1)"
```

---

### Task 2: Frontmatter parser (stdlib, focused)

The KB stores YAML frontmatter between `---` fences. We need only: top-level scalar keys (e.g. `evidence_grade: "Level B"`) and one flat nested int-map (`study_counts:` followed by indented `key: int` lines). PyYAML is forbidden (§X). Block scalars (`>`), lists, and deeper nesting are ignored — we do not need them.

**Files:**
- Create: `cannavec_science/kb_audit/frontmatter.py`
- Test: `tests/test_kb_audit_frontmatter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_frontmatter.py
import unittest
from cannavec_science.kb_audit.frontmatter import parse_frontmatter

_DOC = '''---
id: epilepsy
evidence_grade: "Level B"
evidence_grade_notes: >
  A long block scalar that should be ignored
  across multiple lines.
study_counts:
  total: 17
  systematic_reviews: 1
  observational_cohort: 1
tags:
  - epilepsy
  - CBD
needs_review: false
---
# Body starts here
Some text.
'''


class FrontmatterTests(unittest.TestCase):
    def test_extracts_scalar_grade(self):
        fm = parse_frontmatter(_DOC)
        self.assertEqual(fm["evidence_grade"], "Level B")  # quotes stripped

    def test_extracts_nested_int_map(self):
        fm = parse_frontmatter(_DOC)
        self.assertEqual(fm["study_counts"]["systematic_reviews"], 1)
        self.assertEqual(fm["study_counts"]["total"], 17)

    def test_block_scalar_and_lists_are_not_int_polluted(self):
        fm = parse_frontmatter(_DOC)
        self.assertNotIn("epilepsy", fm.get("study_counts", {}))

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(parse_frontmatter("# just a body\n"), {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_frontmatter -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# cannavec_science/kb_audit/frontmatter.py
"""Minimal, stdlib-only YAML-frontmatter reader (Constitution §X — no PyYAML).

Extracts exactly what the audit needs: top-level ``key: scalar`` pairs and one
level of indented ``key: int`` maps (e.g. ``study_counts``). Block scalars (``>``
/ ``|``) and list items (``- x``) are deliberately ignored — we never read them.
"""
from __future__ import annotations

import re

_FENCE = re.compile(r"^---\s*$", re.MULTILINE)
_TOP = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
_NEST = re.compile(r"^[ \t]+([A-Za-z0-9_]+):\s*(.*)$")


def _strip_scalar(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        v = v[1:-1]
    return v


def parse_frontmatter(text: str) -> dict:
    """Return the frontmatter as a dict, or ``{}`` if there is none."""
    if not text.startswith("---"):
        return {}
    parts = _FENCE.split(text, maxsplit=2)
    # parts == ['', '<frontmatter>', '<body>'] when a leading fence is present
    if len(parts) < 3:
        return {}
    block = parts[1]

    out: dict = {}
    current_map: str | None = None  # name of the nested map we are filling
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        nest = _NEST.match(raw)
        if nest and current_map is not None:
            key, val = nest.group(1), nest.group(2).strip()
            if re.fullmatch(r"-?\d+", val):
                out[current_map][key] = int(val)
            continue
        top = _TOP.match(raw)
        if not top:
            continue
        key, val = top.group(1), top.group(2)
        if val.strip() in (">", "|", ">-", "|-"):
            current_map = None            # block scalar — skip its lines
            continue
        if val.strip() == "":
            out[key] = {}                 # opens a nested map
            current_map = key
            continue
        out[key] = _strip_scalar(val)     # plain scalar
        current_map = None
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_frontmatter -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/frontmatter.py tests/test_kb_audit_frontmatter.py
git commit -m "feat(kb-audit): stdlib frontmatter parser (spec 032 task 2)"
```

---

### Task 3: Scope selection

In-scope (v1): `cannabis/5. Medical & Therapeutic Use/` and `cannabis/6. Evidence & Clinical Validation/`. Skip everything else, plus `README.md` and empty files. `include`/`exclude` are path-substring lists overriding the default.

**Files:**
- Create: `cannavec_science/kb_audit/scope.py`
- Test: `tests/test_kb_audit_scope.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_scope.py
import os
import tempfile
import unittest
from cannavec_science.kb_audit.scope import is_in_scope, select_files

_DEFAULT = ("cannabis/5. Medical & Therapeutic Use", "cannabis/6. Evidence & Clinical Validation")


class ScopeTests(unittest.TestCase):
    def test_medical_and_evidence_are_in_scope(self):
        self.assertTrue(is_in_scope("cannabis/5. Medical & Therapeutic Use/x.md", _DEFAULT, ()))
        self.assertTrue(is_in_scope("cannabis/6. Evidence & Clinical Validation/y.md", _DEFAULT, ()))

    def test_non_science_and_readme_out_of_scope(self):
        self.assertFalse(is_in_scope("cannabis-faq/conditions/x.md", _DEFAULT, ()))
        self.assertFalse(is_in_scope("cannabis/9. Regulation, Law & Compliance/x.md", _DEFAULT, ()))
        self.assertFalse(is_in_scope("cannabis/5. Medical & Therapeutic Use/README.md", _DEFAULT, ()))

    def test_exclude_overrides_include(self):
        self.assertFalse(is_in_scope("cannabis/5. Medical & Therapeutic Use/draft.md",
                                     _DEFAULT, ("draft",)))

    def test_select_files_skips_empty_and_nonmd(self, ):
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "cannabis", "5. Medical & Therapeutic Use")
            os.makedirs(base)
            open(os.path.join(base, "full.md"), "w").write("# x\nbody\n")
            open(os.path.join(base, "empty.md"), "w").write("")
            open(os.path.join(base, "notes.txt"), "w").write("nope")
            got = select_files(d, _DEFAULT, ())
            self.assertEqual([os.path.basename(p) for p in got], ["full.md"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_scope -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# cannavec_science/kb_audit/scope.py
"""Select the in-scope science files of a KB repo (spec 032 — v1: folders 5 + 6)."""
from __future__ import annotations

import os

DEFAULT_INCLUDE = (
    "cannabis/5. Medical & Therapeutic Use",
    "cannabis/6. Evidence & Clinical Validation",
)


def is_in_scope(rel_path: str, include, exclude) -> bool:
    p = rel_path.replace(os.sep, "/")
    if os.path.basename(p).lower() == "readme.md":
        return False
    if any(x and x in p for x in exclude):
        return False
    return any(inc in p for inc in include)


def select_files(root: str, include=DEFAULT_INCLUDE, exclude=()) -> list[str]:
    """Return absolute paths of in-scope, non-empty ``.md`` files under ``root``."""
    out: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if not is_in_scope(rel, include, exclude):
                continue
            try:
                if os.path.getsize(full) == 0:
                    continue
            except OSError:
                continue
            out.append(full)
    return sorted(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_scope -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/scope.py tests/test_kb_audit_scope.py
git commit -m "feat(kb-audit): science-file scope selection (spec 032 task 3)"
```

---

### Task 4: Extraction (frontmatter + citations + nearest claim)

Reuse `pubmed_verify.scan_pmids` / `scan_dois` for PMID/DOI; add an NCT regex; skip identifiers inside code spans via `_markdown_skip`. Each citation's `claim` is the sentence containing (or immediately preceding) the identifier.

**Files:**
- Create: `cannavec_science/kb_audit/extract.py`
- Test: `tests/test_kb_audit_extract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_extract.py
import os
import tempfile
import unittest
from cannavec_science.kb_audit.extract import extract

_FILE = '''---
evidence_grade: "Level B"
study_counts:
  systematic_reviews: 1
---
# Epilepsy

CBD reduced convulsive seizures in Dravet syndrome (Devinsky 2017, PMID: 28538134).
The REFRACT trial is ongoing (NCT05076903).
'''


class ExtractTests(unittest.TestCase):
    def _write(self, d, text):
        p = os.path.join(d, "epilepsy.md")
        open(p, "w", encoding="utf-8").write(text)
        return p

    def test_pulls_declared_grade_and_counts(self):
        with tempfile.TemporaryDirectory() as d:
            rec = extract(self._write(d, _FILE))
            self.assertEqual(rec.declared_grade, "Level B")
            self.assertEqual(rec.study_counts["systematic_reviews"], 1)

    def test_finds_pmid_and_nct_with_types(self):
        with tempfile.TemporaryDirectory() as d:
            rec = extract(self._write(d, _FILE))
            ids = {(c.identifier, c.id_type) for c in rec.citations}
            self.assertIn(("28538134", "PMID"), ids)
            self.assertIn(("NCT05076903", "NCT"), ids)

    def test_citation_carries_its_claim_sentence(self):
        with tempfile.TemporaryDirectory() as d:
            rec = extract(self._write(d, _FILE))
            pmid = [c for c in rec.citations if c.identifier == "28538134"][0]
            self.assertIn("Dravet", pmid.claim)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_extract -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# cannavec_science/kb_audit/extract.py
"""Extract a FileRecord (frontmatter + cited identifiers + nearest claim) from a KB file."""
from __future__ import annotations

import os
import re

from cannavec_science._markdown_skip import code_spans, is_in_code
from cannavec_science.pubmed_verify import scan_pmids, scan_dois
from cannavec_science.kb_audit.frontmatter import parse_frontmatter
from cannavec_science.kb_audit.model import Citation, FileRecord
from cannavec_science.kb_audit.scope import DEFAULT_INCLUDE, is_in_scope

_NCT_RE = re.compile(r"NCT\d{8}", re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _body(text: str) -> str:
    if text.startswith("---"):
        parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            return parts[2]
    return text


def _claim_for(body: str, ident: str) -> str:
    pos = body.find(ident)
    if pos < 0:
        return ""
    head = body[:pos]
    sentences = _SENT_SPLIT.split(head)
    return (sentences[-1] if sentences else "").strip()


def extract(path: str, root: str | None = None, include=DEFAULT_INCLUDE, exclude=()) -> FileRecord:
    rel = os.path.relpath(path, root) if root else path
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as exc:
        return FileRecord(path=path, in_scope=True, declared_grade=None,
                          study_counts={}, citations=(), parse_error=str(exc))

    fm = parse_frontmatter(text)
    body = _body(text)
    spans = code_spans(body)

    seen: set[str] = set()
    cites: list[Citation] = []
    for ident, id_type in (
        [(p, "PMID") for p in scan_pmids(body)]
        + [(d, "DOI") for d in scan_dois(body)]
        + [(m.group(0).upper(), "NCT") for m in _NCT_RE.finditer(body)
           if not is_in_code(spans, m.start())]
    ):
        if ident in seen:
            continue
        seen.add(ident)
        cites.append(Citation(identifier=ident, id_type=id_type, claim=_claim_for(body, ident)))

    grade = fm.get("evidence_grade")
    return FileRecord(
        path=path,
        in_scope=is_in_scope(rel, include, exclude),
        declared_grade=grade if isinstance(grade, str) else None,
        study_counts=fm.get("study_counts", {}) if isinstance(fm.get("study_counts"), dict) else {},
        citations=tuple(cites),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_extract -v`
Expected: PASS (3 tests). (Note: `scan_pmids` already filters code spans for PMIDs/DOIs; we add the same guard for NCT.)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/extract.py tests/test_kb_audit_extract.py
git commit -m "feat(kb-audit): extract citations + claims + declared grade (spec 032 task 4)"
```

---

### Task 5: Gate 1 — citation integrity (verify + retraction, network injected)

Mirror `__main__._verify_pmid_render` precedence with the audit-script inconclusive discipline. Network is injected via a `verify_fn` so tests stay offline.

**Files:**
- Create: `cannavec_science/kb_audit/checks.py`
- Test: `tests/test_kb_audit_checks_citation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_checks_citation.py
import unittest
from cannavec_science.kb_audit.model import Citation
from cannavec_science.kb_audit import checks


def _fake_verify(verdict):
    # stand-in for an engine verify result: object with .verdict.name
    class _R:
        def __init__(self, name): self.verdict = type("V", (), {"name": name})
    return lambda ident, id_type: _R(verdict)


class CitationGateTests(unittest.TestCase):
    def test_clean_pmid_no_finding(self):
        c = Citation("28538134", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("MATCH"),
                                    retracted_fn=lambda **k: None)
        self.assertIsNone(out)

    def test_retracted_is_fail_finding(self):
        c = Citation("32060308", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("MATCH"),
                                    retracted_fn=lambda **k: object())  # registry hit
        self.assertEqual(out.verdict, "retracted")
        self.assertEqual(out.route, "improve_agent")

    def test_not_found_is_fabricated(self):
        c = Citation("99999999", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("NOT_FOUND"),
                                    retracted_fn=lambda **k: None)
        self.assertEqual(out.verdict, "fabricated")

    def test_network_error_is_inconclusive(self):
        c = Citation("28538134", "PMID", "claim")
        out = checks.check_citation(c, verify_fn=_fake_verify("NETWORK_ERROR"),
                                    retracted_fn=lambda **k: None)
        self.assertEqual(out.verdict, "inconclusive")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_checks_citation -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'check_citation'`

- [ ] **Step 3: Write minimal implementation**

```python
# cannavec_science/kb_audit/checks.py
"""The three audit gates over a FileRecord. All network is injected (offline-testable)."""
from __future__ import annotations

from cannavec_science.kb_audit.model import Citation, Finding

# verdict.name values from pubmed_verify.VerificationVerdict
_PASS = {"MATCH", "BARE_CITE_OK"}
_FABRICATED = {"NOT_FOUND", "MISMATCH"}


def check_citation(c: Citation, *, verify_fn, retracted_fn) -> Finding | None:
    """One citation → a Finding, or None if clean. Retraction is checked first
    and is definitive even offline. NETWORK_ERROR → inconclusive (never fabricated)."""
    kw = {"pmid": c.identifier} if c.id_type == "PMID" else (
        {"doi": c.identifier} if c.id_type == "DOI" else {})
    if kw and retracted_fn(**kw) is not None:
        return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} is retracted",
                       evidence="local retraction registry hit",
                       verdict="retracted",
                       recommended_action="find the superseding study and replace this citation",
                       route="improve_agent")

    name = verify_fn(c.identifier, c.id_type).verdict.name
    if name in _PASS:
        return None
    if name == "RETRACTED":
        return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} is retracted",
                       evidence="upstream record marks retraction", verdict="retracted",
                       recommended_action="find the superseding study and replace this citation",
                       route="improve_agent")
    if name == "NETWORK_ERROR":
        return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} not checkable now",
                       evidence="network unavailable", verdict="inconclusive",
                       recommended_action="re-run the audit with network access",
                       route="deeper_research")
    if name in _FABRICATED:
        return Finding(gate="citation",
                       issue=f"{c.id_type} {c.identifier} does not resolve to a real record",
                       evidence=f"verify verdict {name}", verdict="fabricated",
                       recommended_action="replace with a verified primary source",
                       route="improve_agent")
    return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} unverifiable",
                   evidence=f"verify verdict {name}", verdict="inconclusive",
                   recommended_action="review manually", route="deeper_research")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_checks_citation -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/checks.py tests/test_kb_audit_checks_citation.py
git commit -m "feat(kb-audit): gate 1 citation integrity, inconclusive!=fabricated (spec 032 task 5)"
```

> **Note for the worker:** the production `verify_fn` and `retracted_fn` are wired in Task 9 (`_cmd_kb_audit`) — `verify_fn` dispatches on `id_type` to `pubmed_verify.verify_pmid` / `verify_doi` (reading `.verdict`), wraps `uniprot_verify.verify_uniprot` in `try/except (urllib.error.URLError, OSError)` to map a raise → a `NETWORK_ERROR`-named result, and `retracted_fn` is `retraction.is_retracted`. The gate above is engine-agnostic by design.

---

### Task 6: Gate 2 — claim support (assess_support, abstract injected)

For each **PMID** citation, fetch its abstract (injected), run `claim_support.assess_support`, and surface only `CONTRADICTION` (FAIL) and `UNVERIFIED` (FLAG). `NO_TEXT`/missing abstract → inconclusive (no finding). This gate is a flagger, never a grader.

**Files:**
- Modify: `cannavec_science/kb_audit/checks.py`
- Test: `tests/test_kb_audit_checks_claim.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_checks_claim.py
import unittest
from cannavec_science.kb_audit.model import Citation
from cannavec_science.kb_audit import checks


class ClaimGateTests(unittest.TestCase):
    def test_contradiction_is_fail(self):
        c = Citation("1", "PMID", "CBD increases seizure frequency in Dravet syndrome.")
        # abstract asserts the opposite direction
        abstract = "Cannabidiol reduced convulsive seizure frequency in Dravet syndrome."
        out = checks.check_claim(c, abstract_fn=lambda pmid: abstract)
        self.assertEqual(out.verdict, "contradiction")
        self.assertEqual(out.route, "improve_agent")

    def test_no_abstract_is_inconclusive_no_finding(self):
        c = Citation("1", "PMID", "Some claim.")
        out = checks.check_claim(c, abstract_fn=lambda pmid: None)
        self.assertIsNone(out)

    def test_non_pmid_citation_skipped(self):
        c = Citation("NCT05076903", "NCT", "A claim.")
        self.assertIsNone(checks.check_claim(c, abstract_fn=lambda pmid: "text"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_checks_claim -v`
Expected: FAIL — `AttributeError: ... 'check_claim'`

- [ ] **Step 3: Write minimal implementation (append to `checks.py`)**

```python
# cannavec_science/kb_audit/checks.py  (append)
from cannavec_science.claim_support import assess_support, Verdict


def check_claim(c: Citation, *, abstract_fn) -> Finding | None:
    """For a PMID citation, does its abstract support the claim sentence?
    Surfaces CONTRADICTION (fail) and UNVERIFIED (flag). Flagger, not grader."""
    if c.id_type != "PMID" or not c.claim:
        return None
    abstract = abstract_fn(c.identifier)
    if not abstract:
        return None  # inconclusive — no abstract available
    report = assess_support(c.claim, abstract)
    if report.verdict == Verdict.CONTRADICTION:
        return Finding(gate="claim",
                       issue=f"cited PMID {c.identifier} contradicts the claim",
                       evidence=report.note or "abstract asserts the opposite direction",
                       verdict="contradiction",
                       recommended_action="the cited source contradicts the claim — rework the claim or citation",
                       route="improve_agent")
    if report.verdict == Verdict.UNVERIFIED:
        miss = ", ".join(report.missing) if report.missing else "key entities"
        return Finding(gate="claim",
                       issue=f"claim not supported by cited PMID {c.identifier}",
                       evidence=f"abstract does not mention: {miss}",
                       verdict="unverified",
                       recommended_action="find a supporting primary source or hedge the claim to its true grade",
                       route="deeper_research")
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_checks_claim -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/checks.py tests/test_kb_audit_checks_claim.py
git commit -m "feat(kb-audit): gate 2 claim support via assess_support (spec 032 task 6)"
```

---

### Task 7: Gate 3 — GRADE honesty (conservative ceiling from study_counts)

Conservative v1: derive a ceiling from the frontmatter's own `study_counts` with an explicit rule table, parse the declared grade with `EvidenceLevel`, and flag when `declared.rank > ceiling.rank`. Reuses only `EvidenceLevel` (offline, no network).

**Files:**
- Modify: `cannavec_science/kb_audit/checks.py`
- Test: `tests/test_kb_audit_checks_grade.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_checks_grade.py
import unittest
from cannavec_science.kb_audit import checks


class GradeGateTests(unittest.TestCase):
    def test_level_a_with_only_observational_is_inflated(self):
        out = checks.check_grade("Level A", {"observational_cohort": 2, "case_series": 1})
        self.assertEqual(out.verdict, "inflated")
        self.assertEqual(out.route, "quick_fix")
        self.assertIn("Level C", out.recommended_action)  # the ceiling

    def test_level_b_with_rct_is_ok(self):
        self.assertIsNone(checks.check_grade("Level B", {"feasibility_rct": 1}))

    def test_canonical_sr_floor_allows_level_a(self):
        self.assertIsNone(checks.check_grade("Level A", {"systematic_reviews": 1}))

    def test_missing_grade_no_finding(self):
        self.assertIsNone(checks.check_grade(None, {"observational_cohort": 1}))

    def test_unparseable_grade_is_flagged(self):
        out = checks.check_grade("Strong", {"observational_cohort": 1})
        self.assertEqual(out.verdict, "inflated")
        self.assertIn("unparseable", out.issue.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_checks_grade -v`
Expected: FAIL — `AttributeError: ... 'check_grade'`

- [ ] **Step 3: Write minimal implementation (append to `checks.py`)**

```python
# cannavec_science/kb_audit/checks.py  (append)
from cannavec_science.evidence import EvidenceLevel

# Conservative §VII ceiling keyed on the frontmatter's own study_counts.
# (The fuller Claim.best_supportable_grade() synthesis is deferred — see spec Future work.)
def _ceiling(counts: dict) -> EvidenceLevel:
    g = lambda *keys: sum(int(counts.get(k, 0) or 0) for k in keys)
    if g("systematic_reviews", "national_guidelines") >= 1 or g("rct", "confirmatory_rct") >= 2:
        return EvidenceLevel.A
    if g("feasibility_rct", "rct", "confirmatory_rct", "scoping_reviews") >= 1:
        return EvidenceLevel.B
    if g("observational_cohort", "case_series", "app_based_observational") >= 1:
        return EvidenceLevel.C
    if g("animal_models", "in_vitro") >= 1:
        return EvidenceLevel.D
    return EvidenceLevel.UNSUPPORTED


def check_grade(declared: str | None, study_counts: dict) -> Finding | None:
    if not declared:
        return None
    try:
        declared_level = EvidenceLevel(declared.strip())
    except (KeyError, TypeError, ValueError):
        return Finding(gate="grade", issue=f"declared evidence_grade {declared!r} is unparseable",
                       evidence="not one of Level A..E / Unsupported", verdict="inflated",
                       recommended_action="set evidence_grade to a valid 'Level X' value",
                       route="quick_fix")
    ceiling = _ceiling(study_counts)
    if declared_level.rank > ceiling.rank:
        return Finding(gate="grade",
                       issue=f"declared {declared_level.value} exceeds supportable {ceiling.value}",
                       evidence=f"study_counts support at most {ceiling.value}",
                       verdict="inflated",
                       recommended_action=f"downgrade declared evidence_grade to {ceiling.value}, or add stronger evidence",
                       route="quick_fix")
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_checks_grade -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/checks.py tests/test_kb_audit_checks_grade.py
git commit -m "feat(kb-audit): gate 3 conservative GRADE-honesty ceiling (spec 032 task 7)"
```

---

### Task 8: Verdict assembly + routing

Combine a `FileRecord` + its findings into a `FileVerdict` (routing/status/priority/credibility), running all three gates with injected fetchers.

**Files:**
- Create: `cannavec_science/kb_audit/verdict.py`
- Test: `tests/test_kb_audit_verdict.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_verdict.py
import unittest
from cannavec_science.kb_audit.model import Citation, FileRecord
from cannavec_science.kb_audit.verdict import audit_record


def _verify(name):
    class _R:
        def __init__(self): self.verdict = type("V", (), {"name": name})
    return lambda ident, id_type: _R()


class VerdictTests(unittest.TestCase):
    def _rec(self, **kw):
        base = dict(path="f.md", in_scope=True, declared_grade=None, study_counts={}, citations=())
        base.update(kw); return FileRecord(**base)

    def test_clean_file_passes(self):
        rec = self._rec(citations=(Citation("28538134", "PMID", "c"),))
        v = audit_record(rec, verify_fn=_verify("MATCH"), retracted_fn=lambda **k: None,
                         abstract_fn=lambda p: None)
        self.assertEqual(v.routing, "PASS")
        self.assertEqual(v.status, "PASS")
        self.assertEqual(v.credibility["citations_clean"], 1)

    def test_retracted_file_is_improve_fail(self):
        rec = self._rec(citations=(Citation("32060308", "PMID", "c"),))
        v = audit_record(rec, verify_fn=_verify("MATCH"), retracted_fn=lambda **k: object(),
                         abstract_fn=lambda p: None)
        self.assertEqual(v.routing, "IMPROVE")
        self.assertEqual(v.status, "FAIL")
        self.assertEqual(v.priority, 1)

    def test_grade_only_inflation_is_ready_quickfix(self):
        rec = self._rec(declared_grade="Level A", study_counts={"observational_cohort": 1})
        v = audit_record(rec, verify_fn=_verify("MATCH"), retracted_fn=lambda **k: None,
                         abstract_fn=lambda p: None)
        self.assertEqual(v.routing, "READY")
        self.assertEqual(v.status, "FLAG")
        self.assertEqual(v.priority, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_verdict -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# cannavec_science/kb_audit/verdict.py
"""Assemble gate findings into a routed FileVerdict (spec 032 — routing rule)."""
from __future__ import annotations

from cannavec_science.kb_audit.model import FileRecord, FileVerdict
from cannavec_science.kb_audit import checks

_FAIL_VERDICTS = {"retracted", "fabricated", "contradiction"}


def audit_record(rec: FileRecord, *, verify_fn, retracted_fn, abstract_fn) -> FileVerdict:
    findings = []
    clean = 0
    for c in rec.citations:
        cf = checks.check_citation(c, verify_fn=verify_fn, retracted_fn=retracted_fn)
        if cf is None:
            clean += 1
        elif cf.verdict != "inconclusive":
            findings.append(cf)
        clf = checks.check_claim(c, abstract_fn=abstract_fn)
        if clf is not None:
            findings.append(clf)
    gf = checks.check_grade(rec.declared_grade, rec.study_counts)
    if gf is not None:
        findings.append(gf)

    has_fail = any(f.verdict in _FAIL_VERDICTS for f in findings)
    routes = {f.route for f in findings}
    if not findings:
        routing, status, priority = "PASS", "PASS", 3
    elif routes <= {"quick_fix"}:
        routing = "READY"
        status = "FAIL" if has_fail else "FLAG"
        priority = 0
    else:
        routing = "IMPROVE"
        status = "FAIL" if has_fail else "FLAG"
        priority = 1 if has_fail else 2

    return FileVerdict(
        path=rec.path, in_scope=rec.in_scope, routing=routing, status=status, priority=priority,
        credibility={"citations_clean": clean, "citations_total": len(rec.citations),
                     "open_findings": len(findings)},
        findings=tuple(findings),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_verdict -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/verdict.py tests/test_kb_audit_verdict.py
git commit -m "feat(kb-audit): verdict assembly + triage routing (spec 032 task 8)"
```

---

### Task 9: Report rendering (markdown + JSON, ordered by priority)

**Files:**
- Create: `cannavec_science/kb_audit/report.py`
- Test: `tests/test_kb_audit_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_report.py
import json
import unittest
from cannavec_science.kb_audit.model import Finding, FileVerdict
from cannavec_science.kb_audit.report import render


def _v(path, routing, status, priority, findings=()):
    return FileVerdict(path=path, in_scope=True, routing=routing, status=status,
                       priority=priority,
                       credibility={"citations_clean": 0, "citations_total": 0, "open_findings": len(findings)},
                       findings=findings)


class ReportTests(unittest.TestCase):
    def test_ready_quickwins_sorted_before_improve(self):
        verdicts = [_v("improve.md", "IMPROVE", "FAIL", 1),
                    _v("ready.md", "READY", "FLAG", 0)]
        md, _ = render(verdicts)
        self.assertLess(md.index("ready.md"), md.index("improve.md"))

    def test_json_is_machine_readable_queue(self):
        f = Finding("citation", "i", "e", "retracted", "fix", "improve_agent")
        _, js = render([_v("a.md", "IMPROVE", "FAIL", 1, (f,))])
        data = json.loads(js)
        self.assertEqual(data["files"][0]["findings"][0]["route"], "improve_agent")
        self.assertIn("summary", data)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_report -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# cannavec_science/kb_audit/report.py
"""Render verdicts to a human report (markdown) + a machine queue (JSON)."""
from __future__ import annotations

import json
from dataclasses import asdict


def render(verdicts) -> tuple[str, str]:
    ordered = sorted(verdicts, key=lambda v: (v.priority, -v.credibility["open_findings"], v.path))
    counts = {"PASS": 0, "READY": 0, "IMPROVE": 0}
    for v in ordered:
        counts[v.routing] = counts.get(v.routing, 0) + 1

    lines = ["# KB Credibility Audit", "",
             f"- Files audited: **{len(ordered)}**",
             f"- READY (quick wins): **{counts['READY']}** · "
             f"IMPROVE (route to agent): **{counts['IMPROVE']}** · PASS: **{counts['PASS']}**", ""]
    for v in ordered:
        if v.routing == "PASS":
            continue
        lines.append(f"## [{v.routing}/{v.status}] {v.path}")
        for f in v.findings:
            lines.append(f"- **{f.gate}/{f.verdict}** — {f.issue}")
            lines.append(f"  - evidence: {f.evidence}")
            lines.append(f"  - action ({f.route}): {f.recommended_action}")
        lines.append("")

    payload = {
        "summary": {"files": len(ordered), **counts},
        "files": [
            {"path": v.path, "routing": v.routing, "status": v.status, "priority": v.priority,
             "credibility": v.credibility,
             "findings": [asdict(f) for f in v.findings]}
            for v in ordered
        ],
    }
    return "\n".join(lines), json.dumps(payload, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_report -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add cannavec_science/kb_audit/report.py tests/test_kb_audit_report.py
git commit -m "feat(kb-audit): report + machine IMPROVE queue, actionability order (spec 032 task 9)"
```

---

### Task 10: CLI wiring + production fetchers + end-to-end fixture test

Wire `audit_path()` (the top-level driver with real engine fetchers) and the `kb-audit` subcommand, then prove the whole flow on a fixture mini-KB offline.

**Files:**
- Create: `cannavec_science/kb_audit/run.py` (the production driver + fetcher wiring)
- Modify: `cannavec_science/kb_audit/__init__.py` (re-export `audit_path`)
- Modify: `cannavec_science/__main__.py` (subcommand + handler)
- Create: `tests/fixtures/kb_audit/cannabis/5. Medical & Therapeutic Use/clean.md`, `fabricated.md`, `retracted.md`, `inflated.md`; `tests/fixtures/kb_audit/cannabis-faq/x.md`
- Test: `tests/test_kb_audit_e2e.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb_audit_e2e.py
import os
import unittest
from cannavec_science.kb_audit.run import audit_path

_FX = os.path.join(os.path.dirname(__file__), "fixtures", "kb_audit")


def _stub_verify(ident, id_type):
    # offline engine stand-in keyed on the fixture identifiers
    name = "NOT_FOUND" if ident == "99999999" else "MATCH"
    class _R: pass
    r = _R(); r.verdict = type("V", (), {"name": name}); return r


def _stub_retracted(**kw):
    return object() if kw.get("pmid") == "32060308" else None


class E2ETests(unittest.TestCase):
    def setUp(self):
        self.verdicts = {os.path.basename(v.path): v for v in
                         audit_path(_FX, verify_fn=_stub_verify, retracted_fn=_stub_retracted,
                                    abstract_fn=lambda p: None)}

    def test_clean_passes(self):
        self.assertEqual(self.verdicts["clean.md"].routing, "PASS")

    def test_fabricated_fails_to_improve(self):
        v = self.verdicts["fabricated.md"]
        self.assertEqual(v.status, "FAIL")
        self.assertEqual(v.routing, "IMPROVE")

    def test_retracted_fails(self):
        self.assertEqual(self.verdicts["retracted.md"].status, "FAIL")

    def test_inflated_is_ready_quickfix(self):
        self.assertEqual(self.verdicts["inflated.md"].routing, "READY")

    def test_non_science_skipped(self):
        self.assertNotIn("x.md", self.verdicts)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Create the fixtures**

```bash
mkdir -p "tests/fixtures/kb_audit/cannabis/5. Medical & Therapeutic Use" "tests/fixtures/kb_audit/cannabis-faq"
```

```markdown
<!-- clean.md -->
---
evidence_grade: "Level B"
study_counts:
  feasibility_rct: 1
---
# Clean
CBD reduced seizures in Dravet syndrome (Devinsky 2017, PMID: 28538134).
```
```markdown
<!-- fabricated.md -->
---
evidence_grade: "Level C"
study_counts:
  observational_cohort: 1
---
# Fabricated
An invented citation appears here (PMID: 99999999).
```
```markdown
<!-- retracted.md -->
---
evidence_grade: "Level C"
study_counts:
  observational_cohort: 1
---
# Retracted
A retracted paper is cited (PMID: 32060308).
```
```markdown
<!-- inflated.md -->
---
evidence_grade: "Level A"
study_counts:
  observational_cohort: 2
---
# Inflated
Claims top-tier evidence on observational data only (Smith 2024, PMID: 28538134).
```
```markdown
<!-- cannabis-faq/x.md -->
---
evidence_grade: "Level A"
---
# Non-science FAQ (must be skipped)
How much does cannabis cost?
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m unittest tests.test_kb_audit_e2e -v`
Expected: FAIL — `ModuleNotFoundError: cannavec_science.kb_audit.run`

- [ ] **Step 4: Write minimal implementation**

```python
# cannavec_science/kb_audit/run.py
"""Production driver: scope -> extract -> audit each file, with real engine fetchers."""
from __future__ import annotations

import urllib.error

from cannavec_science.kb_audit.scope import select_files, DEFAULT_INCLUDE
from cannavec_science.kb_audit.extract import extract
from cannavec_science.kb_audit.verdict import audit_record


def _real_verify(ident: str, id_type: str):
    """Dispatch to the engine; normalize verify_uniprot's raise into a NETWORK_ERROR result."""
    from cannavec_science.pubmed_verify import verify_pmid, verify_doi
    if id_type == "PMID":
        return verify_pmid(ident)
    if id_type == "DOI":
        return verify_doi(ident)
    if id_type == "UniProt":
        from cannavec_science.uniprot_verify import verify_uniprot
        try:
            rec = verify_uniprot(ident)
        except (urllib.error.URLError, OSError):
            return type("R", (), {"verdict": type("V", (), {"name": "NETWORK_ERROR"})})()
        name = "MATCH" if rec is not None else "NOT_FOUND"
        return type("R", (), {"verdict": type("V", (), {"name": name})})()
    # NCT / ChEMBL: existence-only, treat as pass (out of v1 verify scope)
    return type("R", (), {"verdict": type("V", (), {"name": "BARE_CITE_OK"})})()


def _real_retracted(**kw):
    from cannavec_science.retraction import is_retracted
    return is_retracted(**kw)


def _real_abstract(pmid: str):
    # Replicated from evals/audit_claim_support.py:44 efetch_abstract — None on
    # any network gap (→ Gate 2 inconclusive, never a flag). evals/ is a scripts
    # dir, not an importable package, so we keep a local copy here.
    from cannavec_science import _http
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
           f"db=pubmed&rettype=abstract&retmode=text&id={pmid}")
    try:
        text = _http.retry_urlopen(url)
        return text or None
    except (urllib.error.URLError, OSError):
        return None


def audit_path(root: str, *, include=DEFAULT_INCLUDE, exclude=(),
               verify_fn=_real_verify, retracted_fn=_real_retracted, abstract_fn=_real_abstract):
    verdicts = []
    for path in select_files(root, include, exclude):
        rec = extract(path, root=root, include=include, exclude=exclude)
        verdicts.append(audit_record(rec, verify_fn=verify_fn, retracted_fn=retracted_fn,
                                     abstract_fn=abstract_fn))
    return verdicts
```

> **Worker note:** `_real_abstract` is a verbatim port of the proven `efetch_abstract` in `evals/audit_claim_support.py:44`, using the repo transport `cannavec_science._http.retry_urlopen`. Confirm `retry_urlopen(url) -> str` is the correct name (it is the transport the default fetchers route through). Gate 2 stays fully offline in tests because `abstract_fn` is injected — the production fetcher is only exercised by a live run, never by the unit suite.

```python
# cannavec_science/kb_audit/__init__.py  (append)
from cannavec_science.kb_audit.run import audit_path  # noqa: E402,F401
```

```python
# cannavec_science/__main__.py  — register subcommand (in _build_parser, before `return p`)
    ka = sub.add_parser(
        "kb-audit",
        help=("Read-only credibility audit of a knowledge-base directory "
              "(citation integrity + claim support + GRADE honesty). Operator tool."),
    )
    ka.add_argument("path", help="Path to the knowledge-base repo or a subfolder")
    ka.add_argument("--json", action="store_true", help="Emit the corpus verdict as JSON.")
    ka.add_argument("--out", help="Write the report to this file instead of stdout.")
    ka.set_defaults(func=_cmd_kb_audit)
```

```python
# cannavec_science/__main__.py  — handler (place beside _cmd_rigor)
def _cmd_kb_audit(args: argparse.Namespace) -> int:
    from cannavec_science.kb_audit.run import audit_path
    from cannavec_science.kb_audit.report import render

    verdicts = audit_path(args.path)
    markdown, js = render(verdicts)
    body = js if args.json else markdown
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"[kb-audit] report written to {args.out}", file=sys.stderr)
    else:
        print(body)
    return 1 if any(v.status == "FAIL" for v in verdicts) else 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m unittest tests.test_kb_audit_e2e -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Full-suite regression + CLI smoke**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK` (skips allowed). Then:
Run: `python3 -m cannavec_science kb-audit "tests/fixtures/kb_audit" --json`
Expected: JSON with `fabricated.md` and `retracted.md` as `IMPROVE/FAIL`, `inflated.md` as `READY`, `clean.md` absent from findings, exit code 1.

- [ ] **Step 7: Commit**

```bash
git add cannavec_science/kb_audit/run.py cannavec_science/kb_audit/__init__.py cannavec_science/__main__.py tests/test_kb_audit_e2e.py tests/fixtures/kb_audit
git commit -m "feat(kb-audit): CLI subcommand + production driver + e2e fixtures (spec 032 task 10)"
```

---

### Task 11: Docs + README surface

**Files:**
- Modify: `README.md` (add `kb-audit` to the operator-tools note; keep the 5-command research surface unchanged)
- Modify: `cannavec_science/__main__.py` module docstring (list `kb-audit` as an operator subcommand)

- [ ] **Step 1:** Add a short "Operator tools" subsection to `README.md` documenting `kb-audit` as read-only, operator-only, and pointing at `specs/032-kb-audit/spec.md`. Do **not** add it to the five slash commands.
- [ ] **Step 2:** Update the `__main__.py` docstring subcommand list to include `kb-audit`.
- [ ] **Step 3:** Run `python3 -m unittest discover -s tests 2>&1 | tail -2` → `OK` (the README module-count / docs-consistency tests must still pass; update any asserted counts if the test enumerates modules).
- [ ] **Step 4: Commit**

```bash
git add README.md cannavec_science/__main__.py
git commit -m "docs(kb-audit): document the operator-only kb-audit tool (spec 032 task 11)"
```

---

## Self-Review

**Spec coverage:**
- Three gates → Tasks 5 (citation), 6 (claim-support), 7 (GRADE honesty). ✓
- Triage/routing + READY/IMPROVE/PASS + priority + credibility → Task 8 + the routing table. ✓
- Machine-readable IMPROVE queue (agent hand-off) → Task 9 JSON. ✓
- Scope folders 5+6, configurable, skip non-science/README/empty → Task 3. ✓
- `unfetchable ≠ fabricated` → Task 5 (`NETWORK_ERROR`→inconclusive) + Task 8 (inconclusive emits no finding). ✓
- Operator-only, CLI-only, no slash command → Task 10 (subcommand, not a command md). ✓
- Offline-testable via injected fetchers → every gate/test injects. ✓
- Re-run trend / measurable baseline → `credibility` in Task 8 (a fixed file drops `open_findings`, raises `citations_clean`). ✓
- Compounding-excellence (small verified deltas) → read-only audit; the routing actions are per-finding, one at a time. ✓

**Placeholder scan:** one explicit worker-note (`fetch_abstract`) flags a single confirm-or-add micro-task with its exact shape — not a vague placeholder. No "TBD"/"handle edge cases".

**Type consistency:** `FileVerdict`/`Finding`/`Citation`/`FileRecord` fields are identical across Tasks 1, 5–10. Gate functions are `check_citation` / `check_claim` / `check_grade` (consistent). `audit_record` (Task 8) and `audit_path` (Task 10) names are stable. `verify_fn(ident, id_type) -> obj.verdict.name`, `retracted_fn(**kw)`, `abstract_fn(pmid) -> str|None` signatures are used identically in tests and production.

---

## Execution Handoff

See the offer presented after this plan was saved.
