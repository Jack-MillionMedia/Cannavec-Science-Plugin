"""Select the in-scope science files of a KB repo (spec 032 — v1: folders 5 + 6)."""
from __future__ import annotations

import os

DEFAULT_INCLUDE = (
    "cannabis/5. Medical & Therapeutic Use",
    "cannabis/6. Evidence & Clinical Validation",
)


def is_in_scope(rel_path: str, include, exclude) -> bool:
    p = rel_path.replace(os.sep, "/")
    if os.path.basename(p).lower() == "readme.md":
        return False
    if any(x and x in p for x in exclude):
        return False
    return any(inc in p for inc in include)


def select_files(root: str, include=DEFAULT_INCLUDE, exclude=()) -> list[str]:
    """Return absolute paths of in-scope, non-empty ``.md`` files under ``root``."""
    out: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if not is_in_scope(rel, include, exclude):
                continue
            try:
                if os.path.getsize(full) == 0:
                    continue
            except OSError:
                continue
            out.append(full)
    return sorted(out)
