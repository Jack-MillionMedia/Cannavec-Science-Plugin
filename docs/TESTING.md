# Testing the CLI and the API, rigorously

Five layers, fastest/most-hermetic first. Layers 1–4 run offline with zero
network and gate every push; layer 5 points at a real deployment.

| Layer | What | Command | Network |
|---|---|---|---|
| 1. Unit | Engine modules, injected fetchers | `python3 -m unittest discover -s tests` | none |
| 2. API contract | Each `api/*.py` in an in-process `HTTPServer` | `python3 -m unittest tests.test_api_handlers` | none |
| 3. API smoke (offline) | Full invariant harness vs. the local router | `python3 -m unittest tests.test_live_api_smoke` | loopback |
| 4. CLI subprocess | `python3 -m cannavec_science …` exit codes | `python3 -m unittest tests.test_cli_subprocess` | none |
| 5. Live deployment | The same harness vs. the real URL | `python3 evals/smoke_api.py https://…` | yes |

The whole offline gate is just `python3 -m unittest discover -s tests` — it
includes layers 1–4 (≈2,190 tests). Keep it green; it is the floor (§III).

## What "rigorous" means here

The smoke harness (`evals/smoke_api.py`) asserts **constitution invariants**, not
just `200 OK`:

- **§I primary-source** — `/api/answer "CBD evidence in Dravet syndrome"`
  returns ≥1 claim, ≥1 cited PMID, and specifically Devinsky 2017 (`28538134`).
- **§VI phytochemistry** — `/api/rigor "…22% THC by HPLC"` fires the
  THCA-vs-THC detector (`counts.thca_thc_violations ≥ 1`, `clean=false`).
- **registries present** — `/api/health` reports `curated_registries ≥ 21`.
- **error contract** — missing `question`/`text` → `400`; a refused discover →
  `422`; unknown CLI subcommand → exit `2`; a rigor violation → exit `1`.

The CLI exit-code contract is the parallel surface: `0` ok · `1` refusal /
violation · `2` bad input. `tests/test_cli_subprocess.py` pins it by spawning a
real process (the in-process `test_cli_*` suites cover `main(argv)` directly).

## Run the API locally (no Vercel)

Each `api/*.py` is a standalone Vercel function; `evals/serve_local.py` mounts
them all behind one port so you can exercise the API end to end offline:

```bash
python3 evals/serve_local.py 8000 &
python3 evals/smoke_api.py http://127.0.0.1:8000        # 7/7 invariant checks
curl -s "http://127.0.0.1:8000/api/answer?question=CBD%20in%20Dravet%20syndrome" | jq '.answer.citations[].pmid'
curl -s "http://127.0.0.1:8000/api/rigor?text=22%25%20THC%20by%20HPLC" | jq '.counts'
```

## Hitting the live deployment

```bash
python3 evals/smoke_api.py https://cannavec-science-plugin.vercel.app
# or
CANNAVEC_API_BASE=https://cannavec-science-plugin.vercel.app python3 -m unittest tests.test_live_api_smoke
```

`--live` (smoke) / `CANNAVEC_SMOKE_LIVE=1` (test) additionally probes
`/api/discover`, which needs live discovery configured (`NCBI_API_KEY`).

### If the deployment is gated (401/403 before your handler)

Two distinct causes return a 403 *before any handler runs*:

1. **Vercel Deployment Protection** (Authentication / Password). Create a
   *Protection Bypass for Automation* secret in the project settings and export
   it — the harness sends it as `x-vercel-protection-bypass`:
   ```bash
   export VERCEL_AUTOMATION_BYPASS_SECRET=xxxxxxxx
   ```
2. **A network egress allowlist on the client** (e.g. a sandboxed CI runner that
   only permits certain hosts) returns its own 403 — that is the *client's*
   firewall, not your app. Run the smoke test from a host that can reach Vercel.

A clean `health 200 + registries` is the signal you are actually reaching the
function.

## Citation integrity (periodic, network)

Beyond shape, prove the *citations are real* — the audits resolve every curated
identifier against the live registries and flag drift (run on a schedule, not in
the per-push gate):

```bash
python3 evals/audit_pmids.py      # every curated PMID resolves + author/title matches
python3 evals/audit_dois.py
python3 evals/audit_uniprot.py
python3 evals/audit_chembl.py
python3 evals/audit_claim_support.py   # the cited paper actually supports the claim
python3 evals/run_evals.py             # the canonical-question regression suite
```

## CI (already wired)

- **`.github/workflows/ci.yml`** — the `tests` job runs the offline gate
  (`unittest discover -s tests`, i.e. layers 1–4) on Python 3.11/3.12 for every
  push + PR, plus a retrieval proof; the `citation-audit` job runs the online
  `evals/audit_*.py` suite on PRs and weekly (catching upstream retractions /
  metadata drift off the per-push critical path).
- **`.github/workflows/smoke.yml`** — runs `evals/smoke_api.py` against the live
  deployment: on every Vercel deploy (`deployment_status` success → tests that
  exact preview/prod URL, offline-engine invariants only), nightly with `--live`,
  and on manual dispatch. Set the `VERCEL_AUTOMATION_BYPASS_SECRET` repo secret
  if you turn on Deployment Protection, and optionally the `CANNAVEC_API_BASE`
  repo variable to override the default URL. `deployment_status` / `schedule` /
  `workflow_dispatch` only fire from the default branch, so this activates once
  the workflow lands on `main`.
