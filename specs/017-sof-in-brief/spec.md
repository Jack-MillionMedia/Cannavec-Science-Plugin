# Spec 017 — Summary-of-Findings woven into the research brief

**Status**: Implemented, then archived (PR #41 MVP teardown — see archive/ARCHIVE_MANIFEST.md)

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §VII, §X.

## Why this priority

Specs 015–016 made `meta` emit a complete GRADE Summary-of-Findings (SoF) row:
certainty (⊕) → relative effect → absolute effect → NNT. But that row lives in
the standalone `meta` subcommand, away from the prose brief a researcher
actually delivers. A SoF table is most useful *inside* the brief, beside the
per-claim GRADE evidence profile. This spec weaves it in: `answer --sof FILE`
pools the §I-anchored studies for each named outcome and carries the full SoF
chain into the brief — end to end, deterministically.

It adds **no new statistics** — it is pure composition over the spec 011 / 015
/ 016 backbone — **no audience** (§IV), and **no slash command**.

## User stories

### P1 — `cannavec_science.sof.build_sof(spec)` composes per-outcome SoF rows

A sidecar maps `outcomes` → pooled study sets. For each outcome `build_sof`
pools the studies (`meta_analyze`), rates certainty (`certainty_from_meta`,
running Egger for the publication-bias domain when k ≥ 3), and — for a ratio
measure with a `baseline.risk` — computes the absolute effect + NNT
(`absolute_from_meta`). It returns a typed `SummaryOfFindings` /
`SummaryOfFindingsRow` set with `to_dict()`. A study lacking a primary-source
identifier refuses the whole section (§I) — a brief never carries an
unanchored pooled number.

### P2 — Shared `effects_from_records` parser

The per-study parsing that `meta` did inline is factored into
`meta_analysis.effects_from_records(records, measure=…)` and reused by both the
`meta` CLI and `build_sof`, so the two surfaces cannot drift (§II). A parity
test pins the helper against direct `binary_effect` construction.

### P3 — `answer --sof FILE` surfaces it

`answer --sof sidecar.json` appends a **Summary of Findings** section (one
block per outcome: relative line + certainty block + absolute block) to the
Markdown brief and a `scaffolders.summary_of_findings` object to `--json`. A
malformed sidecar or a §I-failing study exits non-zero with a clear message;
a refused brief skips the section.

## Sidecar shape

    {
      "outcomes": [
        {"outcome": "≥50% seizure reduction", "measure": "RR",
         "studies": [ {"study_id": …, "events_t": …, "pmid": …}, … ],
         "baseline": {"risk": 0.40, "label": "pooled placebo arms",
                      "pmid": "28538134"},
         "outcome_desirable": false,
         "evidence_base": "rct", "risk_of_bias": "not serious",
         "indirectness": "not serious"}
      ]
    }

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- A single RR outcome with a baseline yields a row with a computed certainty
  word and an NNTB absolute effect whose EER equals pooled-RR(display) × ACR.
- An outcome without a baseline (or a continuous measure) yields certainty but
  no absolute effect.
- `effects_from_records` matches direct `binary_effect` construction.
- A study missing its identifier refuses the section (`SoFError`).
- `answer --sof` renders "Summary of Findings" + a ⊕ glyph + NNTB in Markdown,
  and `scaffolders.summary_of_findings.rows` in `--json`; a bad sidecar exits
  non-zero.
