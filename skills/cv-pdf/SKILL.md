---
name: cv-pdf
description: Render a verified cannabis-science answer into a polished, professional PDF evidence brief (clinical-journal style) with accurate, citation-lossless references. Auto-activate when the user asks to make/export/produce a PDF, report, evidence brief, one-pager, handout, or printable/shareable document for a cannabis, cannabinoid, terpene, or endocannabinoid-system research question. This is a deterministic, citation-lossless TRANSFORM of verified evidence — it never authors, invents, or "fills in" findings or citations, never inflates a GRADE, and renders an honest artifact (or refusal) for anything the backbone has not verified.
version: 1.0.0
---

# Cannavec Science — Evidence-Brief PDF (`/cv:pdf`)

Turn a verified cannabis-science answer into a clean, professional **evidence
brief** — a PDF a researcher can hand to a colleague, attach to a grant, or show
a clinician, with every reference accurate and every GRADE honest. This is the
**flagship output layer over the verification backbone**: every identifier it
prints was confirmed real and not retracted, every GRADE label is the level the
deterministic backbone assigned, and none is inflated. It is a **citation-lossless
transform of verified evidence, never a document generator** (Constitution §XI /
M5): you do not write claims, invent citations, or upgrade a grade. The
deterministic code decides what is rendered and refuses to emit anything it
cannot preserve losslessly; you present what it returns.

## How to run it

Run the `pdf` subcommand for the user's research question. From the plugin root:

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science pdf "$ARGUMENTS"
```

- It always writes a **self-contained HTML** evidence brief (works on any
  machine), then renders it to **PDF** via the best available backend: headless
  Chrome (best looking) → a pure-Python reportlab fallback → HTML-only.
- `--out PREFIX` controls the output path (`PREFIX.html` + `PREFIX.pdf`). Default
  is `cannavec-<slug>` in the current directory.
- `--html-only` skips PDF rendering (emit just the HTML to print yourself).
- The command prints the produced path to **stdout** and a one-line status to
  **stderr**.

## What the result means (do not override it)

The credibility guarantee is enforced in code — honour the result:

- **Exit 0** — it produced an honest artifact. Tell the user where it is (the path
  on stdout) and what it is (the stderr summary distinguishes three states):
  - an **evidence brief** with N verified citations (the normal case);
  - a **refusal brief** — the question hit a safety/individualized refusal (§V);
    the PDF honestly records the refusal and weaves **no** evidence. Present it as
    the system correctly declining — a credibility feature, not a bug.
  - a **"no curated efficacy evidence" brief** — the backbone has no verified
    efficacy evidence for this indication. The PDF says so plainly and frames any
    compound background as **not** indication-specific evidence. Point the user at
    `/cv:discover` (live primary-source search) or `/cv:research` for the frontier.
- If the backend was **reportlab** or **HTML-only** (no Chrome found), say so and,
  for HTML-only, tell the user to open the HTML and **Print → Save as PDF**.
- **Non-zero exit** with `[pdf] refused — render not citation-lossless` on stderr
  — a render would have dropped, softened, or inflated an identifier/GRADE, so it
  was refused. This should not happen for a faithful answer; do **not** work
  around it by hand-writing a document. Report the honest reason and stop.

## Scope (be honest about it)

`pdf` renders the **offline curated** answer, so it produces a full evidence brief
for the curated core (paediatric seizures, chronic pain, PTSD, sleep, anxiety,
CINV, MS spasticity, and the other curated indications) and an **honest empty/
refusal brief for everything else** — it never fabricates findings or citations to
fill a page. Its content is exactly the content of the verified answer it
transforms; breadth is a retrieval problem (`/cv:discover` → verify, then semantic
retrieval), not a job for this skill. Never present it as a "make a PDF about any
cannabis topic" tool — its value is that every brief it emits is verified, honest
about its grade, and stays empty when it must.
