"""Render verdicts to a human report (markdown) + a machine queue (JSON)."""
from __future__ import annotations

import json
from dataclasses import asdict


def render(verdicts) -> tuple[str, str]:
    ordered = sorted(verdicts, key=lambda v: (v.priority, -v.credibility["open_findings"], v.path))
    counts = {"PASS": 0, "READY": 0, "IMPROVE": 0}
    for v in ordered:
        counts[v.routing] = counts.get(v.routing, 0) + 1

    lines = ["# KB Credibility Audit", "",
             f"- Files audited: **{len(ordered)}**",
             f"- READY (quick wins): **{counts['READY']}** · "
             f"IMPROVE (route to agent): **{counts['IMPROVE']}** · PASS: **{counts['PASS']}**", ""]
    for v in ordered:
        if v.routing == "PASS":
            continue
        lines.append(f"## [{v.routing}/{v.status}] {v.path}")
        for f in v.findings:
            lines.append(f"- **{f.gate}/{f.verdict}** — {f.issue}")
            lines.append(f"  - evidence: {f.evidence}")
            lines.append(f"  - action ({f.route}): {f.recommended_action}")
        lines.append("")

    payload = {
        "summary": {"files": len(ordered), **counts},
        "files": [
            {"path": v.path, "routing": v.routing, "status": v.status, "priority": v.priority,
             "credibility": v.credibility,
             "findings": [asdict(f) for f in v.findings]}
            for v in ordered
        ],
    }
    return "\n".join(lines), json.dumps(payload, indent=2)
