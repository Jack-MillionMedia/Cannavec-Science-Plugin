---
name: cannabis-evidence-synthesis
description: Quantitative evidence-synthesis & robustness playbook for cannabis research. Auto-activate when pooling studies, computing or interpreting a meta-analysis, judging heterogeneity, rating GRADE certainty of a pooled body, or appraising whether a single trial's "significant" result is robust. Routes the question to the right deterministic `python3 -m cannavec_science` subcommand (meta / fragility) — every tool named here is implemented in `cannavec_science/` and unit-tested; none is LLM judgement.
version: 1.0.0
---

# Cannabis Evidence Synthesis

Apply this skill when a researcher moves from *finding* studies to *combining and
appraising* them quantitatively. The product ships a deterministic biostatistics
backbone (`cannavec_science.meta_analysis` and `cannavec_science.fragility`);
this skill is the map from a question to the command that answers it. **Never
hand-compute or estimate these quantities in prose — run the tool.** Every
number below comes from `math`-only stdlib code with a unit test, so two
identical inputs give byte-identical output (§II Deterministic-Backbone).

## The one rule that governs all of it

**With few studies, refuse to overstate precision.** Cannabis trials are small,
few, and often underpowered. The backbone encodes four independent guards
against a falsely confident synthesis — reach for them, and report what they
say honestly even when it weakens the headline:

| Guard | What it catches | Flag |
|---|---|---|
| **Prediction interval** (spec 013) | Where a *new* study's effect could land — not just the mean | wide PI under high I² |
| **Optimal Information Size** (spec 018) | A pool below a single adequately powered trial — imprecise even with a tight CI | `--certainty` imprecision = "below OIS" |
| **HKSJ interval** (spec 021) | The too-narrow DerSimonian–Laird CI when k is small | `--knha` |
| **Fragility Index** (spec 022) | A single trial whose significance hangs on 1–2 patients | `fragility` |

If a result survives all four, it is genuinely robust. If it does not, say so.

## Routing: question → command

### "Combine these comparative studies into one effect."

Two-arm studies (treatment vs control). Pick the measure:

- Binary outcome, ratio of odds/risk → `--measure OR` or `--measure RR`
- Continuous outcome, same scale → `--measure MD`; different scales → `--measure SMD`

```bash
python3 -m cannavec_science meta studies.json --measure RR --certainty --baseline-risk 0.40
```

Each study record needs a §I identifier (`pmid`/`doi`/`nct`/`chembl`/`uniprot`)
and either a 2×2 table (`events_t/n_t/events_c/n_c`) or arm summaries
(`mean_t/sd_t/n_t/...`). The output carries the fixed + random estimate,
heterogeneity (Q, I², τ²), the prediction interval, and a GRADE inconsistency
verdict. A study without an identifier refuses the whole pool.

### "Pool a single-arm rate — incidence or prevalence."

Adverse-event incidence across treatment arms, or prevalence across cohorts.
**Not** a comparative effect — there is no comparator. Use the Freeman–Tukey
double-arcsine (valid even at 0 % and 100 %):

```bash
python3 -m cannavec_science meta rates.json --measure prop
```

Records are single-arm `{events, n, pmid}`. Report the pooled rate as a rate,
never as an efficacy claim — the footnote says so for you.

### "Why is the heterogeneity so high?"

- A **categorical** moderator (chemotype, route, blinding) → `--diagnostics`
  runs subgroup analysis (Cochrane Q_between) alongside Egger / leave-one-out /
  trim-and-fill.
- A **continuous** moderator (THC dose, study year, baseline severity) →
  `--moderator-key dose` runs a meta-regression: slope, R² (variance explained),
  residual heterogeneity. Add `--knha` for the Knapp–Hartung t.

```bash
python3 -m cannavec_science meta studies.json --measure SMD --moderator-key dose --knha
```

Under ~10 studies per covariate the regression self-labels `CAUTION … treat as
exploratory`. Respect it.

### "How certain is the pooled estimate?"

```bash
python3 -m cannavec_science meta studies.json --measure RR --certainty --baseline-risk 0.40
```

`--certainty` rates the body on the GRADE ⊕-scale across five domains. Three are
computed (inconsistency from I²; imprecision from **both** the CI-vs-null check
**and** the OIS; publication bias from Egger under `--diagnostics`); risk of bias
and indirectness are *your* reviewer inputs (`--risk-of-bias`, `--indirectness`)
and are tagged as such. With `--baseline-risk` you also get the absolute effect
and NNT — the full GRADE Summary-of-Findings row. To weave that row into a prose
brief, use `answer "<question>" --sof sidecar.json`.

### "Is this single trial's significant result actually robust?"

```bash
python3 -m cannavec_science fragility --events-t 8 --n-t 100 --events-c 20 --n-c 100
```

Returns the Fragility Index (how many patient outcomes would have to flip to lose
significance) and the fragility quotient (FI / N). A small FI on a headline trial
is a finding in itself — surface it. A non-significant input is reported as such,
not coerced into a number.

## Interpretation discipline

- **Match the verb to the certainty.** A `⊕⊕⊝⊝ Low` pool does not "demonstrate";
  it "may suggest". The uncertainty checker enforces this — do not launder
  confidence in prose.
- **A tight CI is not the same as strong evidence.** Check the OIS (`--certainty`)
  and the HKSJ interval (`--knha`) before calling a few-study pool precise.
- **High I² is not a footnote.** Lead with the prediction interval and try to
  explain the heterogeneity (subgroup / meta-regression) before pooling blindly.
- **Live-discovery rows are never pooled as curated facts.** Effect sizes fed to
  `meta` come from the researcher's own §I-anchored extraction, not auto-promoted
  `live_*` rows (§IX).
