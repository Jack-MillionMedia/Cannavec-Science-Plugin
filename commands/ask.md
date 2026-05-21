---
name: ask
description: Fast Q&A for cannabis-science questions. Same composer pipeline as /cannavec-science:research but renders only the short-answer + claims + citations, skipping the full evidence-synthesis block. Use this for sub-15-second answers when you do not need the full brief.
argument-hint: '<question>'
allowed-tools: Bash
---

# Cannabis Science — Fast Q&A

The user asked:

**`$ARGUMENTS`**

## How to dispatch

Run the composer in JSON mode and surface the claims + citations:

```bash
python3 -m cannavec_science answer "$ARGUMENTS" --json
```

Parse the JSON. Render:

1. **Refusal** if `is_refusal` is true.
2. Otherwise: each claim's text + grade + inline citation, then a
   compact citation list at the bottom.

Do NOT render the full monograph sections, the trace, or the rigor
report. Use `/cannavec-science:research` for the full brief.

## Hard rules

Inherits every constitution principle from `/cannavec-science:research`:
primary-source-or-refuse, isomer specificity, GRADE wording match,
retraction enforcement, deterministic phytochemistry rigor.
