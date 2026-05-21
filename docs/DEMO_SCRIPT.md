# Cannavec Science — five-minute client demo

The MVP is built around four golden flows. Each one is a single CLI
command. The whole demo runs in under five minutes on a laptop with
network access.

## Flow 1 — Research brief on a real question (1.5 min)

```bash
python3 -m cannavec_science answer "What is the evidence for CBD in Dravet syndrome?"
```

What the client sees:

- A PICO-shaped brief on a real cannabis-research question.
- Five GRADE-graded claims, each cited with a PubMed ID and the GRADE
  level annotated inline at the citation site.
- An evidence summary block: highest grade (Level A), claim count,
  primary-source count.
- Cautions surfaced by the safety layer.
- A bibliography list ready to drop into Zotero / Mendeley / EndNote.

What the client should notice:

- **Every claim cites a real PMID.** No marketing copy, no
  "studies show," no anonymous attribution.
- **The grade is honest.** When a single-source row caps at Level B,
  the answer surfaces both the curator's anchor grade AND the
  deterministic decay, with the reason ("single primary study").
- **The wording matches the grade.** Level B does not get
  Level A verbs.

## Flow 2 — Live discovery across three sources (1.5 min)

```bash
python3 -m cannavec_science discover "CBD PTSD" --since 2024-01-01 --max 5
```

What the client sees:

- Live rows from PubMed, ChEMBL, and ClinicalTrials.gov, each tagged
  with its source (`live_pubmed`, `live_chembl`, `live_ctgov`).
- A cross-source synthesis verdict at the bottom
  (STRONG / MIXED / WEAK / NONE convergence) plus the first detected
  disagreement between sources, if any.

What the client should notice:

- **The plugin keeps up with the literature.** A 2025 trial PMID is
  the proof that this is not a stale snapshot.
- **Live rows are visually distinct.** They carry a `live_*` provenance
  tag and a "provisional, live-search" grade suffix. They never
  pretend to be curated.
- **A refused query fires no network call.** Try
  `python3 -m cannavec_science discover "indica cures PTSD"` — it
  refuses on banned-pattern grounds before any HTTP request.

## Flow 3 — Bibliography export (30 sec)

```bash
python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" \
    --bibliography bibtex --out /tmp/dravet.bib
```

What the client sees:

- A standard BibTeX `.bib` file with one `@article{...}` entry per
  cited PMID/DOI.
- GRADE level annotated inline in the `note` field of each entry.
- Same shape for `--bibliography ris` and `--bibliography csljson`.

What the client should notice:

- **The output is citable.** Drop it straight into Zotero. No
  re-keying.
- **The GRADE level travels with the citation.** A reader of the
  bibliography knows whether Cannavec Science was confident in the
  evidence or hedging.

## Flow 4 — Rigor audit on arbitrary text (30 sec)

```bash
python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC and the dose was 10 mg"
```

What the client sees:

- Three flagged violations:
  - **isomer_collapse**: bare "THC" in pharmacology context.
  - **dose_without_route**: "10 mg" with no oral/inhaled/sublingual.
  - **thca_vs_thc_conflation**: "22% THC by HPLC" needs THCA
    disambiguation.
- Each violation carries the matched span and a resolution hint.

What the client should notice:

- **The detectors are deterministic.** They fire the same way every
  time on the same text — no LLM variance.
- **They are conservative.** False positives are preferred to false
  negatives when a researcher's credibility is at stake.
- **The resolution hint is concrete.** "Disambiguate THCA (raw /
  pre-decarb) from Δ⁹-THC (decarboxylated); e.g.,
  '22% THCA (~19.3% Δ⁹-THC equiv post-decarb)'."

## Bonus — show the constitution (1 min)

```bash
cat .specify/memory/constitution.md | head -50
```

What the client sees:

- A short, principled charter that governs what the MVP does and
  what it explicitly will NOT do.
- Out-of-scope list: 14 audience surfaces the parent plugin has and
  this MVP does not.

What the client should notice:

- **The plugin is honest about its scope.** "Researcher audience only,
  v0.x. v0.2 may add others behind a constitutional amendment."
- **The honesty is a feature.** A demo that promises "everything"
  ends with the client doubting the parts that worked. A demo that
  promises one thing well builds trust in the parts that ship.

## When the demo goes well — close with this

> "This is one audience surface, one composer, one CLI, ~6,000 lines
> of stdlib Python. The larger parent plugin has fourteen more
> audiences, a KB flywheel, signed artifacts, multi-jurisdiction
> compliance, and the rest. We built this MVP first because we wanted
> to prove one thing exceptionally well before showing you everything.
> Where would you like to go next — clinician audience, lab QC,
> compliance, or somewhere else?"

That question reframes the conversation from "is this real?" to
"where do you want to deploy this?" — which is the conversation a
working MVP earns.
