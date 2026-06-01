# Feature Specification: Research-Lead Orchestrator Agent (CANNA-RESEARCH-AGENT)

**Feature Branch**: `claude/compassionate-ptolemy-ehj2x`

**Created**: 2026-06-01

**Status**: Implemented (agent surface + surface-contract test ship in this branch)

**Input**: User request — adopt the supplied **CANNA-RESEARCH-AGENT**
persona as a shipping plugin surface. Product context (verbatim intent):
the persona is the research engine for a planned credible-research
feature on **cannavec.ai**, which today is a knowledge-base retrieval
(RAG) system. The feature should (a) find relevant research and retrieve
answers **not already in the existing knowledge base**, (b) hand the user
high-quality, credible research in a presentable, exportable format of
their choice (PDF, slideshow, …), and (c) seed a **flywheel** that
expands and improves the knowledge base over time.

## Background

Cannavec Science already ships two subagents (Constitution-governed,
deterministic-backbone-deferring):

- `cannabis-source-hunter` — live primary-literature discovery across the
  13 live lanes; wraps `python3 -m cannavec_science discover`.
- `cannabis-research-reviewer` — final review pass applying the Verity
  Test and the deterministic `rigor` pass.

What was missing is the **front-door orchestrator** that turns a single
research *objective* (not just a single query) into an end-to-end,
defensible brief — routing the question to the right primary sources,
composing from the curated registries, falling out to live discovery for
anything the registries do not cover, running the rigor + review gate,
verifying load-bearing identifiers, and exporting citable output. The
supplied CANNA-RESEARCH-AGENT persona is exactly that role.

This spec ships that persona as a third agent, **harmonized with the
Constitution**, named in house style.

### Why an agent and not a sixth slash command

The slash-command surface is locked at exactly five (Constitution §IV;
`CLAUDE.md` "Slash commands: exactly five … Adding a sixth requires a
constitution amendment"). Agents are not capped. The persona is literally
framed as an agent ("You are CANNA-RESEARCH-AGENT"), so an agent file is
the correct, amendment-free vehicle.

### The constitutional hook the persona triggers

The persona advertises an `AGENT-DELEGATION` skill — "managing a team of
junior researchers" / "autonomous research team." Under the Constitution's
**Honest Surface Constraints**, "a slash command, agent file, or skill
that promises orchestration MUST be backed by deterministic code OR carry
an explicit honesty disclaimer in its frontmatter description." The
honest reality is that the "team" is **sequenced deterministic
subcommands plus two named delegate subagents** — not an autonomous
multi-agent swarm. The agent's frontmatter therefore carries an explicit
`HONESTY DISCLAIMER`, and US2 (below) makes that a CI-enforced invariant
for *any* orchestration-promising agent, not just this one.

## Design

**Agent name**: `cannabis-research-lead` (house style: lowercase-hyphenated,
`cannabis-` prefix, role-descriptive — sibling of `cannabis-research-reviewer`).
The persona's brand name **CANNA-RESEARCH-AGENT** is preserved in the agent
body so the cannavec.ai brand identity survives.

**Tools**: `Read, Bash` — identical to the two existing agents. The lead
runs the deterministic CLI itself; it does **not** claim to spawn
autonomous sub-agents (see honesty disclaimer).

### Persona module → deterministic surface mapping

The persona's four `[SKILL: …]` modules map onto real, already-tested
surfaces. No module introduces a new deterministic rule, so Constitution
§II ("every rule implemented in code with a unit test before any prose
surface mentions it") is satisfied by the existing backbone.

| Persona module | Deterministic surface(s) it dispatches to |
|---|---|
| `LIT-REVIEW` | `discover` (13 lanes) + `answer` (curated compose) + `evidence_synthesis` rollup; delegate: `cannabis-source-hunter` |
| `ECS-PATHWAY` | `major/minor_cannabinoids`, `terpenes`, `interactions`, `ecbome`, `ecbome_inhibitors` registries + `verify` (UniProt) + `discover --sources chembl,bindingdb,opentargets,rcsb`; skill: `cannabis-primary-source-routing` |
| `AGENT-DELEGATION` | sequenced CLI stages + hand-offs to the two existing subagents (the "execution blueprint"); **carries the honesty disclaimer** |
| `CLINICAL-TRANSLATION` | `populations`, `pharmacokinetics`, `psychiatry`, `pain_medicine`, `ptsd_anxiety_sleep`, `use_disorder` registries + `discover --sources pubmed,ctgov` + `--grade-profile`/`--pico`/`--power-calc` scaffolders |

## User Scenarios & Testing *(mandatory)*

### US1 — A constitution-compliant orchestrator agent ships (Priority: P1)

**As a** Cannavec Science operator wiring a credible-research feature,

**I want** a single front-door agent that decomposes a research objective
into the deterministic pipeline and relays the backbone's verdicts
verbatim,

**so that** I get an end-to-end defensible brief without any grade,
refusal, or citation being authored by prose.

**Independent Test:**

- `agents/cannabis-research-lead.md` exists with valid frontmatter whose
  `name:` equals the file stem and which carries a `description:`.
- The body operates under `.specify/memory/constitution.md` (cites it in
  an "Authority documents" section, matching the existing two agents).
- The body explicitly defers grading/refusal/citation/retraction/rigor to
  the Python backbone and never authors them in prose.

**Acceptance Scenarios:**

1. **Given** the repository at this branch, **When** the agent file is
   parsed, **Then** its frontmatter `name` is `cannabis-research-lead`
   and a non-empty `description` is present.
2. **Given** the agent body, **When** read, **Then** it references the
   Constitution and the two delegate agents
   (`cannabis-source-hunter`, `cannabis-research-reviewer`).

### US2 — Orchestration surfaces carry an honesty disclaimer (Priority: P1)

**As a** maintainer guarding the Constitution's Honest Surface Constraints,

**I want** any agent whose description promises orchestration / delegation
/ a "research team" / autonomy to also carry an explicit honesty
disclaimer in that description,

**so that** the §II "no marketing without a deterministic enforcer or a
disclaimer" rule is mechanically enforced, not merely documented.

**Independent Test:**

- `tests/test_surface_contracts.py` scans every `agents/*.md`; any agent
  whose frontmatter description matches `orchestrat|deleg|research team|
  autonomous` (case-insensitive) MUST also contain a disclaimer marker
  (`honesty disclaimer` / `not an autonomous` / `metaphor`).
- `cannabis-research-lead` triggers the rule and passes it.
- The two pre-existing agents do **not** trigger the rule (their
  descriptions promise discovery and review, not orchestration), so the
  test adds no retroactive burden.

**Acceptance Scenarios:**

1. **Given** `cannabis-research-lead.md`, **When** the test runs, **Then**
   its description contains both an orchestration trigger and a disclaimer
   marker.
2. **Given** a future agent that advertises delegation without a
   disclaimer, **When** the test runs, **Then** it FAILS (the guardrail
   bites).

### US3 — The slash-command surface stays locked at five (Priority: P2)

**As a** maintainer, **I want** a test that fails if the command count
ever drifts from five, **so that** Constitution §IV's amendment gate is
mechanical.

**Independent Test:**

- `tests/test_surface_contracts.py` asserts `commands/*.md` is exactly
  `{ask, discover, research, rigor, verify}`.

## Scope decisions for the cannavec.ai vision

This spec deliberately records how the broader product vision maps to the
Constitution, so the boundaries are explicit rather than implied.

- **Beyond-KB retrieval** — *in scope.* The agent drives the existing
  13-lane live `discover` fan-out for anything the curated registries do
  not cover. This is the core differentiator the website wants and it is
  already a shipping, tested surface (Constitution §IX).
- **Credible, exportable presentation** — *partially in scope.* The
  canonical artifact is the structured Markdown brief plus BibTeX / RIS /
  CSL-JSON export and the `--json` typed `Answer` (Constitution §XI). The
  Markdown brief is the **source-of-truth a downstream renderer converts**
  to PDF / slideshow. PDF/slideshow rendering inside the plugin is
  **deferred**: it needs a non-stdlib renderer and therefore a §X
  justification + fallback (or it lives in the website layer, outside this
  stdlib plugin). The agent MUST NOT claim to emit a format it cannot
  deterministically produce.
- **Knowledge-base flywheel** — *seam only, not autopilot.* Constitution
  §IX ("live rows NEVER auto-promote … requires a future manual `apply`
  flow which is explicitly out-of-MVP-scope") and the README "What does
  NOT ship" list ("KB flywheel, gap detection, proposal generation";
  "curator updates manually") forbid an automatic flywheel today. The
  agent's honest contribution is a clearly-labelled **"Curation
  candidates (human review required)"** block: a structured signal a human
  curator can later feed into a manual apply flow. The agent never mutates
  a registry and never promotes a `live_*` row.
- **Multi-audience website visitors** — *out of scope.* Constitution §IV
  locks the audience to researchers. Serving patients/clinicians/etc. on
  cannavec.ai is a separate product surface requiring a constitutional
  amendment; this agent refuses non-researcher framings.

## Out of Scope

- A sixth slash command (Constitution §IV — this ships as an agent).
- New deterministic rules, registries, or live lanes (the agent
  orchestrates existing, tested surfaces only).
- New runtime dependencies (Constitution §X — `pyproject.toml`
  `dependencies = []` unchanged).
- Automatic KB promotion / gap detection / proposal generation
  (Constitution §IX + out-of-scope list).
- In-plugin PDF / slideshow rendering (downstream / future, §X).
- Non-researcher audience surfaces (Constitution §IV).

## Risks & Mitigations

- **Risk:** A reader treats the "autonomous research team" framing as a
  literal capability. **Mitigation:** the honesty disclaimer is in the
  frontmatter description AND restated in the body's "Honest framing"
  section AND enforced by `tests/test_surface_contracts.py` (US2).
- **Risk:** The agent is tempted to author a grade/citation to fill a gap.
  **Mitigation:** the body's "What you do NOT do" forbids it and routes
  gaps to `discover` + the honest "Unsupported / not in curated KB" reply,
  mirroring `cannabis-research-reviewer`.
- **Risk:** Adding an agent silently breaks a meta-test. **Mitigation:**
  verified no test asserts an agent count; the new surface-contract test
  is additive and reads files only (no new imports, stdlib-only).

## Acceptance Gate

Before merging this branch, ALL of the following MUST hold:

- `python3 -m unittest discover -s tests` exits 0 (including the new
  `tests/test_surface_contracts.py`).
- `agents/cannabis-research-lead.md` exists, has valid frontmatter, cites
  the Constitution, and carries the honesty disclaimer.
- The slash-command count is exactly five (Constitution §IV unchanged).
- `pyproject.toml` `dependencies = []` unchanged (Constitution §X).
- The plugin remains researcher-only (Constitution §IV unchanged — no new
  audience surface).
