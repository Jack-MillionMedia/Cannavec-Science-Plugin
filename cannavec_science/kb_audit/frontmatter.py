"""Minimal, stdlib-only YAML-frontmatter reader (Constitution §X — no PyYAML).

Extracts exactly what the audit needs: top-level ``key: scalar`` pairs and one
level of indented ``key: int`` maps (e.g. ``study_counts``). Block scalars (``>``
/ ``|``) and list items (``- x``) are deliberately ignored — we never read them.
"""
from __future__ import annotations

import re

_FENCE = re.compile(r"^---\s*$", re.MULTILINE)
_TOP = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
_NEST = re.compile(r"^[ \t]+([A-Za-z0-9_]+):\s*(.*)$")


def _strip_scalar(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        v = v[1:-1]
    return v


def parse_frontmatter(text: str) -> dict:
    """Return the frontmatter as a dict, or ``{}`` if there is none."""
    if not text.startswith("---"):
        return {}
    parts = _FENCE.split(text, maxsplit=2)
    # parts == ['', '<frontmatter>', '<body>'] when a leading fence is present
    if len(parts) < 3:
        return {}
    block = parts[1]

    out: dict = {}
    current_map: str | None = None  # name of the nested map we are filling
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        nest = _NEST.match(raw)
        if nest and current_map is not None:
            key, val = nest.group(1), nest.group(2).strip()
            if re.fullmatch(r"-?\d+", val):
                out[current_map][key] = int(val)
            continue
        top = _TOP.match(raw)
        if not top:
            continue
        key, val = top.group(1), top.group(2)
        if val.strip() in (">", "|", ">-", "|-"):
            current_map = None            # block scalar — skip its lines
            continue
        if val.strip() == "":
            out[key] = {}                 # opens a nested map
            current_map = key
            continue
        out[key] = _strip_scalar(val)     # plain scalar
        current_map = None
    return out
