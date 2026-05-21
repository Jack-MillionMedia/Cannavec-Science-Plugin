# Cannavec Science v0.2 — elite-tier client demo

The v0.2 build is structured around **nine** golden flows. Each one is
a single CLI command. The whole demo runs in under nine minutes on a
laptop with network access; the four v0.1 flows can be cut for a
five-minute version.

## Flow 1 — Research brief on a real question (1 min)

```bash
python3 -m cannavec_science answer "What is the evidence for CBD in Dravet syndrome?"
```

What the client sees:

- A research brief on a real cannabis-research question.
- GRADE-graded claims, each cited with a PubMed ID and the GRADE
  level annotated inline at the citation site.
- An evidence summary block: highest grade (Level A), claim count,
  primary-source count.
- Cautions surfaced by the safety layer.
- A bibliography list ready to drop into Zotero / Mendeley / EndNote.

What the client should notice:

- **Every claim cites a real PMID.** No marketing copy, no
  "studies show," no anonymous attribution.
- **The grade is honest.** When a single-source row caps at Level B,
  the answer surfaces the deterministic decay reason.
- **The wording matches the grade.** Level B does not get
  Level A verbs.

## Flow 2 — Researcher-workflow scaffolders (1.5 min) — NEW in v0.2

```bash
python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" \
    --pico --power-calc --grade-profile --protocol-skeleton
```

What the client sees:

- The same brief as Flow 1, plus four deterministic scaffolds:
  - A **PICO frame** with confidence label (`high` when both
    population and intervention resolve from the registry hits).
  - A **sample-size estimate** table per outcome (α = 0.05,
    β = 0.20). Cohen 1988 continuous formula or Fleiss 1981
    proportion with Tytun-Ury continuity correction. Honest
    `method_not_supported` when effect-size data are absent.
  - A **GRADE evidence-profile table** matching what journals ask
    for (#studies × design × bias × inconsistency × indirectness ×
    imprecision × publication bias × effect × certainty).
  - A **9-section IRB protocol skeleton** with the `Auto-generated
    skeleton — PI must review and supplement.` watermark on line 1.

What the client should notice:

- **Stdlib-only.** The power calculator uses `math.erf` for the
  normal CDF. No scipy / numpy / R required.
- **The protocol skeleton is honest.** Every PI-decision-required
  field is bracketed `[PI to specify ...]`. The tool does not
  pretend to be the protocol author.
- **Non-supported designs refuse explicitly.** Non-inferiority,
  adaptive, cluster-randomised, single-arm without historical
  control all return `method_not_supported` rather than guessing.

## Flow 3 — Preprint discovery (1 min) — NEW in v0.2

```bash
python3 -m cannavec_science discover "CB2 microglia" --sources biorxiv,medrxiv --max 5
```

What the client sees:

- Live rows from bioRxiv and medRxiv tagged `live_biorxiv` /
  `live_medrxiv`, with `posted_date`, `revision_number`,
  `version_history`, and the suggested Level D ceiling.
- Cross-source synthesis verdict counting bioRxiv + medRxiv as
  distinct sources.
- When a preprint has been peer-published, the Crossref-resolved
  `published_version_doi` is surfaced so the composer prefers the
  peer-reviewed version.

What the client should notice:

- **The plugin keeps up with the frontier.** Preprints are where
  half of recent cannabinoid-mechanism work lives in 2026.
- **Preprints are explicitly capped at Level D.** No matter the grade
  hint from the preprint server, the GRADE adapter applies the cap.
- **Refused queries fire no network calls.** Try the same command
  with `"indica cures cancer"` — it refuses at the preflight before
  any HTTP request.

## Flow 4 — Live discovery across eleven sources (1 min)

```bash
python3 -m cannavec_science discover "CBD PTSD" --since 2024-01-01 --max 5 \
    --sources pubmed,chembl,ctgov,pubchem,pharmgkb,rcsb,opentargets,gwas,bindingdb,biorxiv,medrxiv
```

What the client sees:

- Live rows from up to eleven primary sources, each tagged with its
  provenance.
- A cross-source synthesis verdict (STRONG / MIXED / WEAK / NONE
  convergence) plus the first detected disagreement.

What the client should notice:

- **Live rows are visually distinct.** Each carries a `live_*`
  provenance tag and a "provisional, live-search" grade suffix.
  They never auto-promote to the curated tier.
- **The synthesis verdict is deterministic.** Same inputs → same
  output. No LLM judging.

## Flow 5 — Verify with citation network (1 min) — NEW in v0.2

```bash
python3 -m cannavec_science verify 28538134
```

What the client sees:

- The verified Devinsky-2017 PubMed record (PMID 28538134).
- A `Forward-citation network` block reporting the forward-cite
  count, the per-cite sentiment counts (supports / refutes /
  neutral), the aggregate (`support_heavy` / `mixed` / `refute_heavy`
  / `neutral` / `insufficient`), and the replication status.
- If pushback is `refute_heavy`, the brief flags the deterministic
  GRADE downgrade (`inconsistency_serious=True` → one level lower).

What the client should notice:

- **The pushback signal is reproducible.** It uses the same
  rule-based `pubmed_sentiment` classifier the cross-source synthesis
  layer uses — not LLM-judged.
- **The GRADE downgrade is deterministic, not advisory.** When the
  signal flips, the composer-side grade drops by one level for any
  claim citing that PMID. Same inputs → same grade.

## Flow 6 — Registry freshness probe (1 min) — NEW in v0.2

```bash
python3 -m cannavec_science freshness --registry interactions
```

What the client sees:

- A per-row status table for the 35-row interaction registry.
- Per-row classification: `clean` / `retraction_detected` /
  `eoc_detected` / `last_verified_stale` / `network_error` /
  `no_watch_pmids`.
- Summary counts at the top.

What the client should notice:

- **No mutation.** The probe surfaces the gap; the curator updates
  the row. Mirror of Constitution §IX's "curated rows never
  auto-promote" → "curated rows never auto-invalidate."
- **Offline by default.** The local retraction registry is consulted
  first; `--network` enables live PubMed verification.
- **Composition-time integration.** When a brief cites a registry
  row with `last_verified` > 365 days old, the rendered citation
  gets a `[freshness: stale (verified YYYY-MM-DD)]` suffix.

## Flow 7 — Regulatory-feasibility advisory (45 sec) — NEW in v0.2

```bash
python3 -m cannavec_science answer "Can I study Δ⁹-THC in rats?" \
    --regulatory-feasibility us
```

What the client sees:

- The standard research brief, plus a regulatory-feasibility block:
  - `This is not legal advice; consult your institutional
    research-compliance office.` watermark.
  - Schedule classification (`schedule_i` for Δ⁹-THC in the US).
  - Licensing path (DEA Schedule I Researcher Registration, NIDA
    Drug Supply Program, FDA IND).
  - Estimated timeline.
  - Primary regulatory sources (21 USC §812, 21 CFR §1301.18, etc.).

What the client should notice:

- **The watermark is non-removable.** It is asserted by the test
  suite (`tests/test_regulatory_feasibility.py::WatermarkTests`).
  No silent removal possible.
- **Gray zones are flagged honestly.** Try with
  `"Can I study Δ⁸-THC?"` — the advisory names the AK Futures 9th
  Circuit case AND the DEA 2020 IFR position. No fake certainty.
- **Per-state US is out of scope.** The v0.2 advisory is US-federal
  only.

## Flow 8 — Rigor audit on arbitrary text (45 sec)

```bash
python3 -m cannavec_science rigor "myrcene potentiates THC's sedative effect at 10 mg"
```

What the client sees:

- Multiple flagged violations:
  - **isomer_collapse**: bare "THC" in pharmacology context.
  - **dose_without_route**: "10 mg" without oral/inhaled/sublingual.
  - **entourage_overclaim**: terpene-cannabinoid synergy claim
    without one of the canonical citations (Russo 2011, Finlay 2020,
    Santiago 2019, LaVigne 2021).
- Each violation carries the matched span and a resolution hint.

What the client should notice:

- **The detectors are deterministic.** They fire the same way every
  time — no LLM variance.
- **They are conservative.** False positives are preferred to false
  negatives. Discussion of the entourage hypothesis as a research
  topic does NOT fire (the detector enforces citation discipline,
  not the hypothesis itself).
- **Citations clear violations.** `myrcene potentiates THC (Russo
  2011)` does not fire.

## Flow 9 — Bibliography export (30 sec)

```bash
python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" \
    --bibliography bibtex --out /tmp/dravet.bib
```

What the client sees:

- A standard BibTeX `.bib` file with one `@article{...}` entry per
  cited PMID/DOI, GRADE level annotated inline.
- Same shape for `--bibliography ris` and `--bibliography csljson`.

## Bonus — show the constitution + version-boundary doc (30 sec)

```bash
cat .specify/memory/constitution.md | head -50
cat specs/002-elite-development/spec.md | head -30
```

What the client sees:

- A short, principled charter that governs what the build does and
  what it explicitly will NOT do.
- The v0.2 elite-development spec naming the six gaps the build
  closed.

What the client should notice:

- **The build is honest about its scope.** "Researcher audience only.
  Per-state US compliance lives in the parent plugin."
- **The v0.x → v0.2 boundary was crossed via the spec, not vibes.**
  The constitution's own v0.x qualifier defines the mechanism;
  no amendment required.

## v0.3 routing-and-surfacing flows (3 min)

The 2026-05-21 industry-expert review (spec 003) found four shipping
bugs and three confidence-laundering failure modes inside the v0.2
surface. v0.3 closes all of them — these are the proofs.

### Flow 10 — Δ⁸-THC no longer fires Δ⁹-THC monograph

```bash
python3 -m cannavec_science answer "Δ⁸-THC pharmacology and safety"
```

What the client sees: the Δ⁸-THC minor monograph (Pertwee 2008 CB1
binding, Abrahamov 1995 antiemetic, regulatory status). No Δ⁹-THC
major monograph. Span-aware `NamedCannabinoidSet` suppresses the
`\bTHC\b` match embedded inside `Δ⁸-THC`.

### Flow 11 — HHC safety returns 0 spurious AE claims

```bash
python3 -m cannavec_science answer "HHC safety profile"
```

What the client sees: the HHC monograph's narrative safety profile.
No 26-row dump of CBD / Δ⁹-THC AE rows mis-attributed to HHC. The
AE detector accepts `cannabinoid_filter` and `compose_answer` wires
it through.

### Flow 12 — Entourage-effect grade is Unsupported

```bash
python3 -m cannavec_science answer "What is the evidence that the entourage effect is real?"
```

What the client sees: `Highest evidence grade: Unsupported` with the
note "10 claim(s) rendered for context only — none topically relevant
to the question." The topical-relevance signal requires the canonical
entourage citations (Russo 2011 / Finlay 2020 / Santiago 2019 /
LaVigne 2021) to count as topical.

### Flow 13 — Five-shape `verify`

```bash
python3 -m cannavec_science verify NCT02224560     # CT.gov
python3 -m cannavec_science verify CHEMBL5803      # ChEMBL
python3 -m cannavec_science verify P21554          # UniProt CB1
```

What the client sees: each identifier resolves to its primary record
(trial title + status, compound + formula + SMILES, protein + gene
+ organism). Constitution §I's full five-shape menu now resolves.

### Flow 14 — `cannabis × tacrolimus` interaction expansion

```bash
python3 -m cannavec_science answer "cannabis interaction with tacrolimus transplant"
```

What the client sees: the CBD-tacrolimus interaction row (case-report
graded Level C, Leino 2019 / Hauser 2020). The literal noun "cannabis"
expands to {CBD, Δ⁹-THC, CBN, CBG, THCV} for partner-drug matching.

### Flow 15 — Registry inventory

```bash
python3 -m cannavec_science registries
```

What the client sees: every covered cannabinoid, terpene, interaction
partner, AE, contraindication, PGx allele, and eCBome entry — grouped
by registry — with row counts and last-verified dates. Industry-expert
discoverability without grepping the source tree.

### Flow 16 — `source-health` no longer crashes

```bash
python3 -m cannavec_science source-health --json
```

What the client sees: structured JSON with `source`, `status`,
`latency_ms`, `error_excerpt` per source. Pre-v0.3 this crashed with
`AttributeError: 'SourceHealth' object has no attribute 'ok'`.

## v0.4 industry-expert-depth flows

These flows demonstrate the v0.4 deliverables (spec 004): two new
curated registries that close the analytical-chemistry and
cultivation-science depth gaps an industry-expert review of v0.3
identified.

### Flow 17 — Analytical-chemistry registry (decarboxylation kinetics)

```bash
python3 -m cannavec_science answer "Decarboxylation kinetics of THCA at 110 degrees C"
```

What the client sees: three Level C claims with primary citations
(Veress 1990 PMID 2384545 for the kinetic framework; Wang 2016 for
modern matrix-controlled curves; Citti 2018 for analytical
considerations). The `## Analytical-chemistry registry` section
renders with explicit matrix + conditions metadata.

Pre-v0.4 this returned silent 0 claims. v0.4 surfaces curated
primary-cited claims for the formulation scientist asking about
edibles process-engineering.

### Flow 18 — Chemovar genetic basis (Hazekamp & Fischedick framework)

```bash
python3 -m cannavec_science answer "Type II chemovar genetic basis"
```

What the client sees: the Hazekamp & Fischedick 2012 (PMID 22362625)
Type I/II/III/IV/V framework AND the synthase-locus inheritance
explanation, both as Level C claims with primary citations.

Why this matters for an industry expert: the chemovar framing IS the
right modern lens (data, not marketing). The legacy indica / sativa /
hybrid framing is what the banned-pattern detector refuses. The two
surfaces are complementary.

### Flow 19 — HPLC vs GC-MS in-injector artefact

```bash
python3 -m cannavec_science answer "HPLC vs GC-MS cannabinoid quantitation"
```

What the client sees: the curated row surfacing "GC-MS produces
in-injector decarboxylation; the apparent Δ⁹-THC peak on a GC
chromatogram is the SUM of native Δ⁹-THC PLUS decarboxylated THCA"
— the SAME artefact the v0.3 THCA-vs-THC rigor detector catches in
prose. Registry teaches, rigor detector enforces.

### Flow 20 — Cultivation-science registry (UV-B + cannabinoid biosynthesis)

```bash
python3 -m cannavec_science answer "UV-B effect on cannabinoid biosynthesis"
```

What the client sees: the Lydon 1987 (PMID 3621052) canonical finding
that UV-B supplementation increases Δ⁹-THC content of glandular
trichomes in THC-chemotype plants, with the Magagnini 2018 follow-up.
Level C; cannabinoid biosynthesis is the topic, plant science is the
surface.

### Flow 21 — Botanical taxonomy honest debate

```bash
python3 -m cannavec_science answer "Is Cannabis sativa one species or three?"
```

What the client sees: ONE Level C claim that cites BOTH Small &
Cronquist 1976 (single-species framework) AND Hillig 2005
(multi-species view) AND McPartland 2018 (review). Cannavec Science
does NOT pick a winner — it surfaces the live scholarly debate.

Critically: this query does NOT fire the strengthened indica/sativa
banned pattern, because the botany framing is research-grade and
distinct from the pharmacology framing.

### Flow 22 — Strengthened indica/sativa refusal

```bash
python3 -m cannavec_science answer "indica vs sativa pharmacological differences"
```

What the client sees: a Refusal with the strengthened banned-pattern
hit (`indica_sativa_as_pharmacology_abstract`). Pre-v0.4 this returned
silent 0 claims because the abstract meta-framing did not satisfy the
sedative-keyword co-occurrence the v0.3 pattern required.

### Flow 23 — Rendered 0-claim hint

```bash
python3 -m cannavec_science answer "Bedrocan medical cannabis cultivars THC content"
```

What the client sees: under the standard answer block, a new
`## Notes` section with the v0.3 audience-classification message
("0 curated claims: this question targets a non-researcher audience
— see the parent Cannavec plugin"). Pre-v0.4 the classification was
set internally but never rendered; v0.4 closes the loop.

### Flow 24 — Two new inventory groups

```bash
python3 -m cannavec_science registries --registry analytical_chemistry
python3 -m cannavec_science registries --registry cultivation_science
```

What the client sees: each group renders its 8 / 6 rows grouped by
topic. Total inventory across all registries grows from 145 (v0.3) to
159 (v0.4) rows across 11 (was 9) registries.

## When the demo goes well — close with this

> "This is one audience surface, one composer, one CLI, ~26,500 lines
> of stdlib Python, 1,220+ unit tests, and 133 offline canonical eval
> prompts across eight buckets (curated, rigor-positive, rigor-negative,
> refusal, cross-cutting, routing-and-surfacing, analytical-cultivation,
> live). v0.4 took the v0.3 routing-and-surfacing build through a
> second-pass industry-expert review and (a) closed every new P1/P2/P3
> finding the second pass turned up, AND (b) shipped the analytical-
> chemistry + cultivation-science depth the first pass had scoped as
> the v0.4 horizon — all inside the existing constitutional gates,
> with no audience broadening. The larger parent plugin has fourteen
> more audiences, a KB flywheel, signed artifacts, multi-jurisdiction
> compliance, and the rest. We built v0.4 to prove that researcher-
> grade rigor + honest routing + analytical depth + cultivation-science
> coverage + live frontier discovery can ship at elite-tier quality
> before showing you everything else. Where would you like to go next
> — clinician audience, lab QC, compliance, or somewhere else?"

That question reframes the conversation from "is this real?" to
"where do you want to deploy this?" — which is the conversation a
working elite-tier build earns.
