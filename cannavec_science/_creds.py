"""Per-user credential resolution (NCBI keys, etc.).

NCBI requires every user to use their OWN personal API key — pooling user traffic
through a single shared key is prohibited. So a key NEVER lives in shipped source;
it is supplied per user and resolved at runtime, in precedence order:

  1. the process environment (CI, deployment, an explicit ``export``);
  2. the user's ``~/.cannavec/credentials`` file, written by
     ``python3 -m cannavec_science setup``.

The CLI additionally bootstraps a local ``.env`` (developer convenience) into the
environment before anything runs. Stdlib only; every function is fail-safe — a
missing or unreadable file degrades to "no credential", never an exception.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "credentials_path",
    "resolve",
    "load_dotenv",
    "save_credentials",
    "parse_env_text",
    "KNOWN_KEYS",
]

# Credentials this tool recognises in a credentials / .env file. NCBI_API_KEY and
# NCBI_EMAIL are the load-bearing ones for reliable live retrieval.
KNOWN_KEYS = (
    "NCBI_API_KEY",
    "NCBI_EMAIL",
    "CANNAVEC_CROSSREF_MAILTO",
    "ANTHROPIC_API_KEY",
)


def credentials_path() -> Path:
    """The per-user credentials file: ``$CANNAVEC_HOME/credentials`` if set, else
    ``~/.cannavec/credentials``."""
    home = os.environ.get("CANNAVEC_HOME", "").strip()
    base = Path(home) if home else Path.home() / ".cannavec"
    return base / "credentials"


def parse_env_text(text: str) -> dict:
    """Parse ``KEY=VALUE`` lines (dotenv-style). Tolerates ``export`` prefixes,
    single/double quotes, ``#`` comments, and blank lines. A malformed line (no
    ``=``) is skipped, never raised."""
    out: dict = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        out[key] = val
    return out


def _read_file(path: Path) -> dict:
    try:
        return parse_env_text(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}


def resolve(name: str, *, path: "Path | None" = None) -> "str | None":
    """Resolve a credential: process environment first, then the credentials
    file. Returns ``None`` when neither has a non-empty value."""
    val = os.environ.get(name, "").strip()
    if val:
        return val
    fileval = _read_file(path or credentials_path()).get(name, "").strip()
    return fileval or None


def load_dotenv(path) -> int:
    """Load ``KEY=VALUE`` pairs from ``path`` into ``os.environ`` WITHOUT
    overriding an already-set variable. Returns the count newly set; a missing or
    unreadable file is a clean no-op (0)."""
    p = Path(path)
    if not p.is_file():
        return 0
    n = 0
    for key, val in _read_file(p).items():
        if key and not os.environ.get(key):
            os.environ[key] = val
            n += 1
    return n


def save_credentials(values: dict, *, path: "Path | None" = None) -> Path:
    """Write ``values`` as ``KEY=VALUE`` to the credentials file with owner-only
    (0600) permissions, creating the parent directory. Empty values are skipped.
    Returns the path written."""
    p = path or credentials_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Cannavec Science credentials — YOUR OWN keys, on this machine only.",
        "# NCBI requires each user to use their own personal key (no sharing).",
    ]
    for k in sorted(values):
        v = str(values[k]).strip()
        if v:
            lines.append(f"{k}={v}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(p, 0o600)  # owner read/write only — a secret on disk
    except OSError:  # pragma: no cover — best-effort on exotic filesystems
        pass
    return p
