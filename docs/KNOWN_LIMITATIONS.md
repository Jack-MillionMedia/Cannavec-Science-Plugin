# Known limitations — what to expect (and what not to trust yet)

Cannavec Science is an **early build**. The verification spine is solid and
well-tested, but coverage is deliberately narrow and a few rough edges remain.
This page tells you, as an early tester, what is **intentional behaviour** (not a
bug) and what is a **genuine rough edge** worth reporting. Please read it before
filing — and please *do* report anything in the "report these" list.

## What it is genuinely good at

- **Verifying citations.** A fabricated PMID/DOI returns `FAIL`; a retracted one
  is blocked; an unreachable one returns `UNVERIFIED` (never a false `PASS`).
- **Refusing rather than confabulating.** For most questions it has no curated
  evidence for, it says so honestly ("No curated efficacy evidence for X")
  instead of inventing an answer.
- **Catching unscientific language** (cure claims, isomer confusion,
  dose-without-route) deterministically and offline.

## Intentional behaviour — *not* a bug

- **Narrow curated coverage.** The curated corpus covers roughly **7–8 efficacy
  indications** (paediatric epilepsy/Dravet/LGS/TSC, MS spasticity, chronic
  neuropathic pain, CINV, cachexia) plus pharmacology/safety registries. For
  anything outside that, the tool **grounds via live retrieval** (PubMed, Europe
  PMC, ClinicalTrials.gov, ChEMBL, …) or honestly refuses. Hitting "no curated
  evidence" for an off-list disease is **expected**, not a failure.
- **`UNVERIFIED` offline.** Without network, `verify` can't confirm a citation
  upstream, so it returns `UNVERIFIED` (exit code 3) rather than guessing `PASS`.
- **Safety refusals are sovereign.** Individualized dosing ("how much should I
  take") and personal medical-advice questions are refused by design. This is a
  research-evidence tool, not a clinical-advice tool.
- **No legal / regulatory / dosing / cultivation advice surfaces.**

### The KB-improvement flywheel (`audit-mcp` / `route-gaps` / `kb-health`)

- **It flags, it never authors.** The flywheel *detects* weak, missing, outdated,
  incorrect, or misleading chunks and *routes* them to a research backlog for
  human review. It never writes clinical content, never sets or upgrades an
  evidence grade, and never touches a curated `RESEARCH_BACKLOG.md` — by design
  (the knowledge-base Agent Boundary Rule). Resolution is always a human step.
- **The Cannavec MCP returns rich chunk prose to your interactive Claude session**
  (not just the counts you may see in a raw tool log). That prose — with whatever
  citations it carries — is what the model forwards to `audit-mcp --chunks` for
  the flywheel to evaluate. The richness of the audit depends on those chunks
  actually carrying per-claim PMIDs/DOIs.
- **`--rigorous` corpus-contradiction is deliberately conservative.** Labelling a
  chunk **misleading** because the broader literature contradicts it requires a
  *strong majority* of credible sources to contradict it, over a *minimum sample*.
  This is intentional: a false `misleading` on a *correct* chunk is the worst
  error, so the bar is set high. The cost is that some wrong-direction claims on
  compound/negated sentences are not caught by the corpus tier alone — they are
  still caught by the other checks (uncited/weakly-cited, cross-chunk coherence,
  prose rigor) and routed to model/human review rather than asserted. An optional
  model-adjudicator seam exists (`review_claim(backend=…)`, identifier-free,
  grade-free, quote-gated) to sharpen this later; it is **off by default** so the
  deterministic core needs no API key or network to run.

## Genuine rough edges — please report if they bite you

- **Off-list disease (general skepticism).** The common phrasings — *"I have
  &lt;disease&gt;, can cannabis help me"*, *"diagnosed with X"*, *"I suffer from X"*,
  and *"&lt;cannabinoid&gt; for / to treat / help with X"* — now **refuse honestly**
  ("No curated efficacy evidence for X") for any disease outside the ~8 curated
  indications. The standing guidance still holds, though: **don't trust a
  confident or graded answer for a disease that isn't in the curated set** — an
  unusual phrasing could still slip a tangential row through. Check the citation,
  and report any that do.
- **Mechanism/receptor questions may over-refuse.** A pure binding/mechanism
  question naming a target (e.g. *"binding affinity of THC for CB1"*) may be
  wrongly answered with "No curated efficacy evidence for CB1." That's an
  over-refusal, not a real "no evidence" claim — the data may exist via
  `discover`.
- **Live retrieval reliability.** Key-less NCBI/PubMed can rate-limit or `403`
  from shared/cloud IPs; the tool falls back to **Europe PMC**, but for fast,
  reliable live results add your own free NCBI key: `python3 -m cannavec_science
  setup` (stored on your machine only — NCBI requires each user to use their own
  key, so none ships in this repo).
- **Web/API surface is early scaffolding.** The Vercel handlers (`api/`) work but
  default `CANNAVEC_ALLOWED_ORIGIN` to `*` and have no rate limiting — fine for a
  local/trusted try, not yet hardened for a public deployment. **Compliance note:**
  NCBI prohibits pooling many users' traffic through one key, so a *hosted*
  deployment must not route all visitors through a single `NCBI_API_KEY` — keep it
  operator-only, lean on the key-less Europe PMC lane, or have each user supply
  their own key. The per-user model above is for the plugin / CLI, where each
  person runs it with their own key.

## How to read a verdict

| Verdict | Means |
|---|---|
| `PASS` | Citation resolves upstream and is not retracted. |
| `FAIL` | Does not resolve, is retracted/flagged, or metadata mismatches. |
| `UNVERIFIED` | Could not confirm (offline / network error) — **never** treated as PASS. |
| "No curated efficacy evidence for X" | Honest refusal — the curated set has nothing for X. Try `discover` for the live frontier. |

## Reporting

- A **wrong or fabricated citation**, a **confident answer for an off-list
  disease**, a **crash/hang/stack trace** → file a
  [bug report](https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin/issues/new?template=bug_report.md).
- How a real research task went, especially the **trust** of the output → file
  [early-user feedback](https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin/issues/new?template=early_user_feedback.md).
