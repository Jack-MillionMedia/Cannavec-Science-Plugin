# Cannavec Science — Product Strategy (First Principles)

_Working note, 2026-06-02. Written after a citation-integrity audit of the
curated registries (see "What this session established"). Labels evidence vs.
assumption deliberately; the pricing and market claims here are **hypotheses to
test**, not facts._

---

## 0. Decision summary

**Proceed — but narrow the investment to the verified-evidence engine.** The
platform is already built and architecturally sound. The thing that makes it
worth significant money is not the LLM (a commodity) — it is **provable citation
integrity at scale**: the ability to answer any cannabis-science question and
have every claim resolve to a real, correctly-labelled, non-retracted primary
source. That is the moat, and — as this session proved — it is also the most
fragile thing in the product. Spend here first.

The single most important next action is non-technical: **convert that
capability into a paid promise** ("every citation in your brief is verified, or
we flag it") and put it in front of 3–5 buyers whose work makes a wrong citation
expensive.

---

## 1. The real objective

| | |
|---|---|
| **Objective** | Let one cannabis-science expert work with the speed of a team *and* the citation-defensibility of a peer reviewer — across any scientific topic in the field. |
| **Success metric** | A paying user can hand any generated brief to a regulator, IRB, journal, or court and **every citation holds**. Operationally: zero unverified/wrong identifiers emitted; measured time-to-defensible-brief. |
| **Failure condition** | A single fabricated or mislabelled citation in a paid deliverable. This is not hypothetical — see §"What this session established". |
| **Time horizon** | Demand signal within one quarter (paid pilots); not a multi-year platform bet before validation. |
| **Non-goals** | Being a general cannabis chatbot; individualized medical/legal/dosing advice (refused by the §V safety layer); operational surfaces (cultivation, lab-QC, compliance, retail) — out of scope by Constitution §IV. |

---

## 2. The moat — why anyone pays (from first principles)

Strip the product to its atoms. A user wants a true, sourced answer to a
scientific question. Three ways to get one:

1. **Ask a frontier chatbot.** Fast, free, fluent — and it *hallucinates
   citations*. For a researcher, a confidently wrong PMID is worse than no
   answer, because verifying it costs the time the tool was supposed to save.
2. **Do the literature work by hand.** Trustworthy, but slow and doesn't scale.
3. **Cannavec.** The structural insight is that the LLM here is *fenced off from
   being a source of truth*: it reranks an identifier-free shortlist and can only
   return indices (`ranker_llm.py`), so it cannot invent a citation or assign a
   grade. Underneath sit a deterministic grader, retraction enforcement, and —
   now — a continuous verification gate.

The moat is **(2)'s trustworthiness at (1)'s speed.** PubMed, Crossref, and
ChEMBL are free; the defensible asset is the *curation + verification + GRADE +
retraction* layer on top, kept continuously true. That layer is expensive to
build, expensive to keep correct, and therefore hard to copy — which is exactly
what makes it monetizable.

> **The willingness-to-pay sentence:** _"I can put this in front of a regulator
> / journal / court without re-checking the citations."_ A free chatbot will
> never be able to say that. The whole strategy is to make that sentence true
> and then sell it.

---

## 3. Who pays, and why now

**Assumption (need validation), ranked by willingness-to-pay × urgency:**

1. **Cannabinoid pharma / biotech R&D & regulatory affairs** — IND/NDA support,
   drug-interaction dossiers, safety write-ups. A wrong citation in a regulatory
   submission is legally and financially consequential → highest WTP.
2. **Medical-affairs / MSL teams** at cannabinoid companies — HCP evidence
   responses, where claims must be sourced and on-label.
3. **Litigation / expert witnesses / insurers** — defensible evidence on harms
   (driving impairment, cannabinoid hyperemesis, psychosis risk, drug
   interactions). Citations get cross-examined.
4. **Academic / contract-research / systematic-review teams** — speed on PICO,
   power, GRADE, meta-analysis (surfaces the platform already has).
5. **Regulators / policy bodies** — evidence synthesis at scale.

**Why now (evidence-backed):** cannabis-research volume is rising fast — this
session's live discovery pulled 2025/2026 primary papers — evidence is
fragmented across PubMed/CTgov/ChEMBL, and as the field professionalizes and
regulates, the cost of a wrong citation is going *up*. The buyers above are
forming exactly as that cost rises.

---

## 4. What to build / strengthen (cheapest-decisive first)

| Priority | Investment | Status |
|---|---|---|
| **P0** | **Verified-evidence gate** — citation integrity enforced continuously, in CI, on every change. | **Shipped this session** (offline denylist guard + online author-OR-title audit gating PRs). Remaining: extend the *online* check to DOI / ChEMBL / UniProt (defects were found in all three), and mark the CI check "required" in branch protection. |
| **P1** | **Claim-support verification** — verify the cited paper actually supports the *magnitude/direction* claimed (e.g. "AUC ×14.8", "CYP3A4 inhibition"), not just that the identifier resolves. LLM-as-flagger over the abstract → human review. This is the next tier of trust and the deferred 4th option. | Not started |
| **P2** | **Per-answer provenance/audit trail** — every claim → identifier → verification timestamp → GRADE, exportable. This is what makes a brief *defensible and reproducible*, and is the feature enterprise buyers will pay extra for. | Partially present (bibliography export, GRADE inline) |
| **P3** | **Coverage expansion** (more registries/sources) — only *after* the gate is bulletproof, or you scale the defect surface faster than the trust. | Ongoing; sequence behind P0/P1 |

The ordering is the point: trust is the product, so trust-enforcement precedes
reach. Expanding coverage before the gate is solid multiplies the very risk that
kills willingness-to-pay.

---

## 5. Pricing & packaging (hypotheses — to be tested, not asserted)

- **Seat-based SaaS** for experts, + usage-based metering for heavy live
  discovery; **enterprise tier** adds the audit trail, SSO, and private/internal
  corpora.
- **Anchor price to avoided cost, not to tokens.** The reference point is the
  cost of one wrong citation in a regulatory submission or an expert report —
  which dwarfs an annual subscription. Sell defensibility, not word count.
- **Do not** price as "another AI assistant" (commoditized, race-to-zero). Price
  as "verified evidence infrastructure."

These are explicitly unproven. The cheapest way to learn the real numbers is §6.

---

## 6. Fastest reality test (demand, not flattery)

- **Hypothesis:** a regulatory-affairs or medical-affairs lead will *pay* for
  citation-locked, defensible briefs.
- **Test:** 3–5 paid design-partner pilots, each producing one *real* deliverable
  the org actually needs (a drug-interaction dossier, a harms evidence summary).
- **Metric:** (a) time saved vs. their status quo; (b) whether every citation
  survives their internal QC unchanged.
- **Pass:** ≥2 convert to paid contracts **and** zero citation defects in
  delivered briefs.
- **Fail:** they still re-verify everything by hand (trust not transferred), or
  won't pay beyond a free pilot.
- **Cost/time:** weeks, not quarters. Reversible.

Do **not** count demo enthusiasm, signups, or model praise as demand — only a
real deliverable they'd otherwise have paid a person to produce.

---

## 7. Red-team (attack the recommendation)

- **"Frontier models + web search will be good enough, for free."** Partly true
  for casual use. Mitigation: compete on *defensibility and zero-hallucination
  citations*, which general models structurally do not guarantee — and make that
  difference legible (per-claim verification badges).
- **Liability of being an evidence source** in medical/regulatory contexts.
  Mitigation: the §V "what the evidence says, never what *you* should take" line
  is already load-bearing; keep individualized advice refused, and keep the
  audit trail so claims are traceable, not authored.
- **The moat is also the biggest operational liability.** Citation integrity
  decays continuously (this session found 11 wrong identifiers that had passed
  the offline suite). If verification ever lapses, the core promise breaks. This
  is why P0 is continuous and gated, not a one-off cleanup.
- **TAM risk:** is cannabis-specific demand large enough? The verification engine
  is **domain-agnostic** — the same architecture serves any regulated evidence
  vertical (rare disease, tox, supplements). Cannabis is the wedge, not
  necessarily the ceiling. (Constitution scope is cannabis today; generalizing is
  a deliberate future decision, not a default.)
- **Evidence that would reverse "proceed":** paid pilots fail to convert, or
  buyers demonstrably trust a free general model's citations enough not to pay
  for verification.

---

## 8. What this session established (evidence, not assumption)

- **Live discovery + reranker: sound.** All 8 identifiers from the live demo
  (6 PMIDs + 2 trials) verified real and on-topic against PubMed / CTgov; the
  reranker's ordering was defensible.
- **Curated registry: 11 wrong identifiers found and fixed** across PMIDs (4,
  one propagated to 8 sites in safety-critical registries), DOIs (3), and ChEMBL
  IDs (4) — out of ~150 PMIDs + 45 DOIs + 5 ChEMBL checked. All re-anchored to
  verified sources or removed where no verified source exists.
- **The gate that should have caught them couldn't run** in the deployment
  sandbox (network policy) and had a substring blind spot. Both are now fixed;
  an offline denylist guard runs everywhere, and the online audit (author-OR-
  title, network-resilient) gates PRs.
- **Not yet verified (honest gaps):** claim-support (does the paper support the
  *magnitude* claimed?); 24 UniProt accessions (no verification tool available
  in-session — canonical receptor IDs spot-checked by knowledge only); the
  ~7,500-row discovery index (uncurated candidates, re-verified at read time);
  one Stott DOI (`10.2217/fca.13.87`) that does not resolve and needs a curator.

---

## 9. Final call

**Proceed. The verified-evidence engine is the asset; protect and sell it.**
Immediate next step: make `citation-audit` a *required* status check, then run
3–5 paid design-partner pilots tied to real deliverables. Build claim-support
verification (P1) only once the identifier gate is required and green.
