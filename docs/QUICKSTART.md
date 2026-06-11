# Quickstart — testing Cannavec Science as a user

A 10-minute walkthrough to install the plugin and exercise everything end-to-end:
the **verification spine** (the anti-hallucination core) and the **KB-improvement
flywheel** (turning real usage into a research backlog). Copy-paste as you go.

> **Mental model.** The model does the reasoning; deterministic code does the
> *verifying*. Every credibility verdict (real citation? retracted? GRADE? safe?
> misleading?) is computed by code, not asserted by the model. The flywheel
> **flags** problems and routes them for review — it never authors clinical content.

---

## 1. Install (inside Claude Code)

```text
/plugin marketplace add Jack-MillionMedia/Cannavec-Science-Plugin
/plugin install cannavec-science@cannavec-science
```

Five commands now appear under the `cannavec-science:` namespace:
`/research`, `/ask`, `/discover`, `/verify`, `/rigor`.

There is **nothing to `pip install`** — the verification core is stdlib-only
Python ≥ 3.9. The plugin works immediately; keys (below) only make live retrieval
faster and unlock semantic KB recall.

## 2. (Recommended) Add keys

In a terminal, from the plugin directory (or anywhere the CLI is on PATH):

```bash
python3 -m cannavec_science setup        # walks you through an optional free NCBI key
python3 -m cannavec_science setup --show # confirm what's stored (machine-only)
```

- **NCBI key** — free; makes live PubMed retrieval faster and less rate-limited.
  Without it, the tool still runs (it leans on Europe PMC).
- **Cannavec key** — unlocks semantic/vector recall over the curated KB + the
  chunk flywheel. **Get your key + a copy-paste command from your dashboard:**
  <https://cannavec.ai/dashboard/mcp-setup>. To connect it in Claude Code,
  **export it in the same shell first** (otherwise the `Bearer` header is empty
  and the MCP returns 401):

  ```bash
  export CANNAVEC_API_KEY=<your-cannavec-key>
  claude mcp add --transport http cannavec https://cannavec.ai/api/mcp \
    --header "Authorization: Bearer ${CANNAVEC_API_KEY}"
  ```

  Full setup for Claude Code, Claude Desktop, and Claude.ai (web), plus
  troubleshooting, is in **[MCP_SETUP.md](MCP_SETUP.md)**.

## 3. The verification spine (90 seconds, no keys needed)

```bash
# Verify a real paper → PASS (read live from NCBI, retraction-checked)
python3 -m cannavec_science verify 28538134

# THE MONEY SHOT — refuse a retracted citation that looks legitimate
python3 -m cannavec_science verify 32060308          # → FAIL: retracted

# Refuse a fabricated citation — it will not invent a paper
python3 -m cannavec_science verify 99999999          # → FAIL: not found

# Catch unscientific language deterministically (offline, <0.2s)
python3 -m cannavec_science rigor "CBD is non-psychoactive and cures all seizures. We gave cannabis at 50mg."
#   → flags: cure_claim, non_psychoactive_cbd_misuse, dose-without-route
```

Every verdict is machine-readable with `--json`.

## 4. The slash commands (in Claude)

Type these in Claude Code and watch the model reason over *verified* evidence:

- `/cannavec-science:ask Does CBD interact with clobazam?`
- `/cannavec-science:research CBD for paediatric epilepsy`
- `/cannavec-science:discover cannabidiol Dravet syndrome seizure`
- `/cannavec-science:verify 26114620`
- `/cannavec-science:rigor <paste any paragraph of cannabis science>`

Expect honest refusals for indications outside the curated set — that is
**intentional** (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)), not a failure.

## 5. The KB-improvement flywheel (the new part)

The flywheel evaluates the chunks the KB returned and turns problems into a
research backlog. It's an **operator/terminal** feature (not a slash command). To
watch the *recursive* part (the `kb-health` trend across cycles), point
`CANNAVEC_HOME` at a writable dir and run an eval twice:

```bash
export CANNAVEC_HOME=~/cannavec-test     # a writable home so the ledger persists
```

Run it offline first (deterministic, no network):

```bash
# Forward a chunk the way the model would after a KB hit, and classify it
python3 -m cannavec_science audit-mcp --query "CBD for epilepsy" --rigorous --no-corpus \
  --chunks '[{"doc_id":"cbd_epilepsy","h2_anchor":"Efficacy","text":"CBD is a miracle cure that is 100% effective and completely safe for all seizures.","citations":[]}]'
#   → ✗ MISLEADING (high) · cbd_epilepsy#Efficacy [hash]
#       banned_misleading + uncited_claim + thin_stub …

# See the recursive-learning trend (status distribution + % correct over cycles)
python3 -m cannavec_science kb-health
```

Now the **live** version — drop `--no-corpus` to compare each claim against the
real literature (PubMed / Europe PMC / ClinicalTrials.gov) and GRADE-tier it:

```bash
python3 -m cannavec_science audit-mcp --query "Does CBD inhibit CYP3A4 and interact with clobazam?" --rigorous \
  --chunks '[{"doc_id":"cbd_clobazam","h2_anchor":"Mechanism","text":"Cannabidiol inhibits CYP3A4 and CYP2C19, raising plasma levels of norclobazam (the active metabolite of clobazam) and increasing sedation; monitor levels and consider a clobazam dose reduction.","citations":["26114620"]}]'
#   → corroboration tally from the live corpus + a verdict, recorded to the ledger
```

Route the findings into a knowledge-base repo's backlog (it **never** touches a
curated `RESEARCH_BACKLOG.md` — it writes a separate, regenerable file):

```bash
python3 -m cannavec_science route-gaps --kb-root /path/to/mc-knowledge-base --review   # dry preview
python3 -m cannavec_science route-gaps --kb-root /path/to/mc-knowledge-base            # write
```

If a flag is a false positive, suppress it so it stops being re-queued (it
re-arms automatically when the chunk's content changes):

```bash
python3 -m cannavec_science eval-feedback --chunk cbd_epilepsy#Efficacy --verdict banned_misleading --hash <hash-from-the-rigorous-output>
python3 -m cannavec_science eval-feedback --list
```

## 6. What to look for

| You see… | Meaning |
|---|---|
| `PASS` / `FAIL` / `UNVERIFIED` | Citation verified / refused / un-confirmable (never a false PASS) |
| "No curated efficacy evidence for X" | Honest refusal for an off-list indication — **intentional** |
| `correct / incomplete / outdated / weakly_cited / misleading` | The rigorous chunk verdict (most-severe-wins) |
| `resolved / regressed / reopened` | Recursive-learning ledger: a fix confirmed / a regression / new evidence appeared |

Read [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) before filing — it separates
**intentional behaviour** from **genuine rough edges**.

## 7. Report

- A wrong/fabricated citation, a confident answer for an off-list disease, or any
  crash → [bug report](https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin/issues/new?template=bug_report.md).
- How a real research task went, especially the **trust** of the output →
  [early-user feedback](https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin/issues/new?template=early_user_feedback.md).

Sanity check (any time): `python3 -m unittest discover -s tests` runs the full
offline suite — it should report `OK`.
