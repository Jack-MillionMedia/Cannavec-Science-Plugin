# Cannavec Science — Vercel API

Stdlib-only Python serverless functions that expose the `cannavec_science`
engine over HTTP. Each `*.py` file is a Vercel function at `/api/<name>`,
using the `BaseHTTPRequestHandler` pattern (zero dependencies).

## Endpoints

| Route | Method | Network | Purpose |
|---|---|---|---|
| `/api/health` | GET | none | Liveness + capability probe (reports `live_discovery`). |
| `/api/answer` | GET/POST | none¹ | Curated, GRADE-honest research brief (`Answer.to_dict()` JSON, or `?format=markdown`). |
| `/api/discover` | GET/POST | **live** | Multi-source primary-source fan-out + synthesis verdict (Phase 2). |
| `/api/rigor` | GET/POST | none | Phytochemistry + banned-pattern audit of arbitrary text. |
| `/api/registries` | GET | none | Curated-registry inventory (`?format=markdown`). |

¹ `/api/answer` **auto-falls-back** to live discovery when curated coverage is
thin (no curated claim, or best grade Unsupported) — a novel question returns
a cited, provisionally-graded brief from live primary sources with no flag.
Force it with `augment=true`; disable it with `fallback=false`. Always
best-effort: it degrades to the curated brief if discovery is unavailable, and
live findings are never promoted to curated facts (§IX).

## Parameters

- `/api/answer` — `question` (required), `format=json|markdown`,
  `retraction_policy=strict|badge`, `augment=true|false` (force/skip live),
  `fallback=true|false` (default true — auto-fallback when thin). Response adds
  `augmented` (live findings attached) and `fallback_used`.
- `/api/discover` — `query` (required), `sources=pubmed,ctgov,chembl,europepmc`
  (default `pubmed,ctgov`), `max=<int>` (≤25), `since=YYYY-MM-DD`,
  `format=json|markdown`. The CT.gov lane is relevance-gated to cannabinoid
  trials so a broad free-text query can't surface unrelated studies.
  **Ranking:** `rank=true|false` (default `true`) adds a cross-source **Ranked
  candidates** block — a free, offline, deterministic re-ordering by relevance
  + study design + recency, with retracted papers sunk to the bottom.
  `rerank=true` (default `false`) adds the optional LLM lift, which fires only
  when the deterministic order is genuinely uncertain and degrades silently to
  the deterministic order if `anthropic`/`ANTHROPIC_API_KEY` is absent;
  `rerank=force` bypasses the confidence short-circuit and always calls the
  model (for testing the LLM path on demand); `rerank_model` (default
  `claude-sonnet-4-6`) selects the model. The ranking
  block carries `escalation_reason` (`top near-tie` | `design inversion` |
  `weak lexical signal` | `forced`) so you can see *why* the LLM was consulted.

## Environment variables

| Var | Required | Effect |
|---|---|---|
| `CANNAVEC_ALLOWED_ORIGIN` | recommended | CORS allow-origin (default `*` — set to your site before public launch). |
| `NCBI_API_KEY` | for live | Authenticates NCBI E-utilities (raises rate limit 3→10 req/s, fixes shared-IP `403`). Live discovery degrades gracefully without it. |
| `NCBI_EMAIL` | optional | NCBI etiquette contact, sent alongside the key. |
| `ANTHROPIC_API_KEY` | for `rerank=true` | Enables the optional LLM rerank lift. The `anthropic` package is bundled (`requirements.txt`), so this key is the only thing to set. Without it, `rerank=true` degrades silently to deterministic ranking — at zero cost. |

> **Enabling the LLM rerank on Vercel:** set `ANTHROPIC_API_KEY` in the Vercel
> project env and redeploy — that's it (the `anthropic` package is already in
> `requirements.txt`). Verify with `GET /api/health` → `"llm_rerank": true`.
> The Cannavec **core** stays stdlib-only (Constitution §X): `anthropic` is
> imported lazily by `ranker_llm` only, exclusively when `rerank=true` and the
> key is present. Deterministic ranking (the default) needs none of this.

## Notes

- `vercel.json` force-bundles `cannavec_science/**` into every function via
  `includeFiles` (the engine's lazily-imported registries would otherwise be
  missed by static import tracing) and sets `maxDuration: 30`.
- Curated responses are deterministic and edge-cached 24 h; live responses
  are cached 1 h.
- All behaviour is covered by offline tests (`tests/test_api_handlers.py`,
  `tests/test_live_discovery.py`, `tests/test_http_ncbi_auth.py`) — network
  calls use injected fetchers, so the suite never hits the wire.
