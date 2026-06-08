---
name: cv-cite
description: Export the verified citations behind a cannabis-science answer as a citation-lossless reference set (BibTeX + RIS + CSL-JSON). Auto-activate when the user asks to cite, export references/citations, build a bibliography, or produce BibTeX / RIS / CSL-JSON / Zotero / Mendeley / EndNote output for a cannabis, cannabinoid, terpene, or endocannabinoid-system research question. This is a deterministic, citation-lossless TRANSFORM of verified evidence — it never authors or invents citations, and it emits nothing when there is nothing verified to cite.
version: 1.0.0
---

# Cannavec Science — Citation Export (`/cv:cite`)

Turn a verified cannabis-science answer into a ready-to-paste reference export a
researcher can drop straight into Zotero / Mendeley / EndNote with zero
re-keying. This is the **output layer over the verification backbone** — every
reference it emits is a primary-source identifier the backbone already confirmed
is real and not retracted, with its GRADE preserved. It is a **citation-lossless
transform of verified evidence, never a citation generator** (Constitution §XI /
M5): you do not write, infer, or "fill in" any reference here. The deterministic
code decides what is citable; you present what it returns.

## How to run it

Run the `cite` subcommand for the user's research question. From the plugin root:

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science cite "$ARGUMENTS"
```

- **Default** emits all three formats (BibTeX, RIS, CSL-JSON), each delimited by
  a header — maximum reference-manager compatibility.
- Add `--format bibtex|ris|csljson` to emit a single format (e.g. for piping).
- Add `--out PREFIX` to write `PREFIX.bib`, `PREFIX.ris`, `PREFIX.json` to disk.

## What the exit code means (do not override it)

The command enforces the credibility guarantee in code; honour its result:

- **Exit 0** — it printed a citation-lossless reference export. Present it to the
  user as-is (or summarise the count and offer the raw block). Every identifier
  and GRADE label is guaranteed present.
- **Non-zero exit** with `no citable answer: <reason>` on stderr — there is
  nothing verified to cite. Surface the honest reason and **stop**. Do NOT invent
  references, fall back to your own memory, or paste citations from anywhere
  else. The reasons:
  - `refusal` — the question hit a safety/individualized refusal (§V).
  - `no verified citations` — the answer has no graded evidence for this
    indication (e.g. an uncurated indication the backbone honestly refuses). Tell
    the user there is no curated efficacy evidence to cite, and point them at
    `/cv:discover` (live primary-source search) or `/cv:research` for the frontier.
  - `not citation-lossless (<fmt>)` — a render dropped an identifier or GRADE;
    the export was refused rather than ship a lossy reference set.

## Scope (be honest about it)

`cite` composes the **offline curated** answer, so it cites cleanly for the
curated core (paediatric seizures, chronic pain, PTSD, sleep, anxiety, CINV, MS
spasticity, and the other curated indications) and **emits nothing for everything
else** — it refuses rather than fabricate. For the broader frontier, the
citations come from live retrieval (`/cv:discover` → verify), not from this skill.
Never present this as a "cite anything about cannabis" tool; its value is that
every reference it emits is verified, and it stays silent when it cannot be.
