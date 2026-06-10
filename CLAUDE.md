# Cannavec Science — project guidelines

## Mission (read this first — it decides everything)

This project exists to **ground AI models in credible, verifiable,
non-hallucinated cannabis-science research so experts can become dramatically
more productive without sacrificing accuracy, trust, or scientific rigor.** The
goal is the world's best AI-powered cannabis research tool: an expert-grade
research *grounding* system that lets researchers, clinicians, analysts, and
scientists do extremely high-quality research at scale.

It is **not** a toy chatbot, **not** a static answer engine, and **not** a
generic automation script.

Judge every change — feature, agent, schema, retrieval method, eval, refactor —
against the **Mission Test**: *does this make the AI more grounded, more accurate,
more verifiable, more useful to experts, or more resistant to hallucination?* If
no, it is not a priority. Full text: `.specify/memory/constitution.md` (the Seven
Mission Mandates M1–M7 and operational principles §I–§XI govern this repo).

## What the deterministic code is FOR (and is NOT)

The Python in `cannavec_science/` is the **grounding + verification harness around
an AI reasoner — not the reasoner**. (Constitution §II, M1, M5.)

- **It IS for:** retrieval of primary sources, identifier verification, retraction
  enforcement, GRADE grading, phytochemistry/reporting rigor checks, safety
  preflight, citation export, evaluation, and orchestration. These stay
  deterministic and offline-testable because **credibility cannot be probabilistic**.
- **It is NOT for:** generating canned answers. Hard-coded answer logic, static
  response templates, registry-only output presented *as the intelligence*, and
  simplistic generators standing in for research reasoning are **anti-patterns**.
  Do not deepen them. `compose_answer()` is a grounding/verification primitive
  (assemble verified evidence → citation-lossless, machine-checkable artifact); it
  is **not** a substitute for model reasoning, and must not evolve into one.
- **Direction of travel:** toward *model-reasoning-grounded-by-retrieval-and-
  verification*. The model proposes; the deterministic layer disposes — every
  credibility verdict (real citation, not retracted, GRADE level, safety verdict)
  is computed and enforced by code before output reaches the user.

When you touch this code, the default question is "does this strengthen grounding,
retrieval, verification, or expert leverage?" — not "how do I make the static
generator output more strings?"

## Quick orientation

- **Target user / metric**: the **expert** (researcher, clinician, analyst,
  scientist) doing high-quality research at scale; success = expert productivity +
  grounding fidelity, not template coverage (Constitution §IV / M3). Research-grade
  science may reach any reader, but the evidence standard is invariant.
- **Evidence floor (never lower it)**: primary-source-or-refuse (§I), GRADE honesty
  (§VII), phytochemistry precision (§VI), retraction enforcement (§VIII), safety
  sovereignty (§V). Model-authored text is held to the *same* standard as curated
  rows.
- **Stack**: verification core is stdlib Python ≥ 3.9, offline-testable, zero
  `pip install` (Constitution §X). Retrieval / embeddings / semantic-vector search
  / model orchestration / rendering are first-class but live in their own
  justified, gracefully-degrading layer — they must not break the offline core.
- **Slash commands**: exactly five — `research`, `ask`, `discover`, `verify`,
  `rigor`. This five-command cap is a deliberate project invariant; adding a
  sixth is a significant scope decision, not a casual change.
- **CLI entry point**: `python3 -m cannavec_science <subcommand>`.
- **Tests**: `python3 -m unittest discover -s tests` runs offline and must stay
  green; every change ships a positive + negative test (Constitution §III).
