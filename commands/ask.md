---
name: ask
description: Fast, grounded Q&A for a cannabis-science question. You give a tight answer; the deterministic backbone verifies the citation behind it — every identifier you cite is confirmed real and not retracted before you present it. Use for a sub-15-second verified answer when you do not need the full /cannavec-science:research brief.
argument-hint: '<question>'
allowed-tools: Bash
---

# Cannabis Science — Fast, Verified Q&A

The user asked:

**`$ARGUMENTS`**

You give a short, expert answer — but you may only state a scientific claim that
sits behind a **verified** primary source. The backbone does the verifying.

## The fast grounded flow

### 1. Pull curated reference + any candidate citations

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science answer "$ARGUMENTS" --json
```

If `is_refusal` is true, surface the refusal and stop. Otherwise read the
graded claims and their identifiers — but treat them as **candidates to verify**,
not as the final answer.

### 2. Verify the identifier(s) behind your answer

For each PMID / DOI / NCT / ChEMBL / UniProt you will cite:

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science verify <identifier>
```

Cite it **only on PASS**. A FAIL means fabricated, not-found, or **retracted** —
drop it. If the curated layer has no claim for this question, run a quick
`cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science discover "$ARGUMENTS" --sources pubmed --max 3` and
verify a returned identifier instead.

### 3. Answer

Give a tight, GRADE-honest answer: the bottom line, worded to match the grade,
with the **verified** citation inline (`PMID 28538134, Level B`). Name
cannabinoids by isomer; no dose without route. If nothing verifies, say so —
"no primary source confirms this" is a valid, honest answer (§I).

## Hard rules

Inherits every constitution principle from `/cannavec-science:research`:
primary-source-or-refuse, no self-certification (the backbone verifies, not you),
retracted-never-cited, isomer specificity, GRADE-wording match, and no
individualized advice.
