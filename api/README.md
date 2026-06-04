# Cannavec Science — Vercel API

Stdlib-only Python serverless functions that expose the `cannavec_science`
engine over HTTP. Each `*.py` file is a Vercel function at `/api/<name>`,
using the `BaseHTTPRequestHandler` pattern (zero dependencies).

## Endpoints

| Route | Method | Network | Purpose |
|---|---|---|---|
| `/api/health` | GET | none | Liveness + capability probe (reports `live_discovery`). |
| `/api/answer` | GET/POST | none¹ | **One blended brief** — curated core + live breadth + synthesis (`Answer.to_dict()` JSON, or `?format=markdown`). |
| `/api/discover` | GET/POST | **live** | Multi-source primary-source fan-out + synthesis verdict, raw frontier view on its own (Phase 2). |
| `/api/rigor` | GET/POST | none | Phytochemistry + reporting-rigor + banned-pattern + **retracted-citation** audit of arbitrary text (§VI / §VIII). |
| `/api/registries` | GET | none | Curated-registry inventory (`?format=markdown`). |

¹ **One answer, not two endpoints.** `blend=true` (alias `augment=true`) returns
the verified curated **core** (GRADE'd, retraction-checked) merged with
citation-checked live **breadth** (provenance-tagged `live_*`, reranked) and the
cross-source synthesis verdict — the two tiers kept visibly distinct, so a client
never has to also call `/api/discover` and merge by hand. Without the flag the
default is the offline curated core, which **auto-falls-back** to live discovery
only when curated coverage is thin (no curated claim, or best grade Unsupported);
disable that with `fallback=false`. Always best-effort: it degrades to the
curated brief if discovery is unavailable, the live tier never raises the curated
GRADE, and live findings are never promoted to curated facts (§IX). A retracted
live finding is badged (⚠) and pinned last, never silently cited (§VIII).

## Parameters

- `/api/answer` — `question` (required), `format=json|markdown`,
  `retraction_policy=strict|badge`, `blend=true|false` (alias `augment`; weave
  curated core + live breadth + synthesis), `fallback=true|false` (default true —
  auto-fallback when thin). Response adds `augmented` (live findings attached),
  `fallback_used`, `synthesis` (the cross-source convergence verdict, also
  inside `answer.live_synthesis`), and the nested `answer.is_refusal` mirror of
  the top-level `is_refusal`. The `answer` object also carries `sections` — the
  structured major/minor-cannabinoid monograph (chemistry, receptor activity,
  clinical / preclinical evidence, safety) when the question names a cannabinoid
  — so a JSON consumer receives the monograph the Markdown brief shows, not only
  the typed `claims`. A MECHANISM-intent query for a cannabinoid additionally
  surfaces its curated receptor pharmacology as typed Level-C `claims` (e.g.
  `cannabidiol (CBD) — agonist (in vitro) at 5-HT1A (UniProt P08908; HTR1A)`).
  `no_evidence: true` + a human `message` is set only when a non-refusal query
  yields no curated claim, no live finding AND no monograph section (so a
  CBG/CBC/CBN monograph is never masked) — an empty brief is never returned
  silently.
- `/api/discover` — `query` (required), `sources=pubmed,ctgov,chembl,europepmc`
  (default `pubmed,ctgov`), `max=<int>` (≤25), `since=YYYY-MM-DD`,
  `format=json|markdown`. The CT.gov lane is relevance-gated to cannabinoid
  trials so a broad free-text query can't surface unrelated studies. The Europe
  PMC lane uses the API's default relevance ranking; a retracted live finding is
  badged `⚠ RETRACTED` and pinned last in the Markdown (§VIII).
- `/api/rigor` — `text` (required). Response → `{ok, clean, counts,
  phytochemistry_violations, banned_pattern_hits, retracted_citations}`.
  `clean` is `false` (and `counts.retracted_citations > 0`) when the text cites
  a PMID/DOI in the retraction registry (§VIII), so a retracted citation can
  never be reported "clean".

## Environment variables

| Var | Required | Effect |
|---|---|---|
| `CANNAVEC_ALLOWED_ORIGIN` | recommended | CORS allow-origin (default `*` — set to your site before public launch). |
| `NCBI_API_KEY` | for live | Authenticates NCBI E-utilities (raises rate limit 3→10 req/s, fixes shared-IP `403`). Live discovery degrades gracefully without it. |
| `NCBI_EMAIL` | optional | NCBI etiquette contact, sent alongside the key. |

## Notes

- `vercel.json` force-bundles `cannavec_science/**` into every function via
  `includeFiles` (the engine's lazily-imported registries would otherwise be
  missed by static import tracing) and sets `maxDuration: 30`.
- Curated responses are deterministic and edge-cached 24 h; live responses
  are cached 1 h. The `format=markdown` brief echoes the question (`**Q:** …`),
  so it is served `Cache-Control: no-store`, never `public`.
- Every response sends `X-Content-Type-Options: nosniff`, and the echoed
  question is stripped of angle brackets at the boundary, so reflected input
  cannot be MIME-sniffed into executable HTML.
- All behaviour is covered by offline tests (`tests/test_api_handlers.py`,
  `tests/test_live_discovery.py`, `tests/test_http_ncbi_auth.py`) — network
  calls use injected fetchers, so the suite never hits the wire.
