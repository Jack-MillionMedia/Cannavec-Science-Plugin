"""Internal-diagnostic logger.

User-facing CLI output (the ``[error]``, ``[refused]``, ``[bibliography]``
lines that tests pin) stays as direct ``print()`` to ``stderr``. This
module is for internal diagnostics — retry attempts, slow lanes,
swallowed exceptions — that operators want to surface on demand via the
``CANNAVEC_LOG_LEVEL`` environment variable (default ``WARNING``).

Usage::

    from cannavec_science._log import get_logger
    log = get_logger("discover")
    log.info("ChEMBL fetch retried after %ds", delay)

The logger writes to ``stderr`` and does not propagate to root, so it
will not pollute the JSON / Markdown CLI output streams.
"""

from __future__ import annotations

import logging
import os
import sys

__all__ = ["get_logger"]


_DEFAULT_LEVEL = "WARNING"
_NAMESPACE = "cannavec_science"
_INITIALISED = False


def _init_root() -> None:
    """One-time setup of the namespaced logger."""
    global _INITIALISED
    if _INITIALISED:
        return
    level_name = os.environ.get("CANNAVEC_LOG_LEVEL", _DEFAULT_LEVEL).upper()
    level = getattr(logging, level_name, logging.WARNING)
    root = logging.getLogger(_NAMESPACE)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    _INITIALISED = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``cannavec_science`` namespace."""
    _init_root()
    if name.startswith(_NAMESPACE):
        return logging.getLogger(name)
    return logging.getLogger(f"{_NAMESPACE}.{name}")
