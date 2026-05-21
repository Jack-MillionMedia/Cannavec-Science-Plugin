"""Shared safety + banned-pattern preflight for every live discoverer.

Spec 002 foundational layer. Centralises the FR-002 contract:

  "discover MUST run the safety preflight and the banned-pattern
   detector BEFORE any network call. A refuse verdict MUST emit the
   standard refusal message and MUST NOT touch any network endpoint."

Every per-source `*_discover.search()` entry point calls
:func:`preflight` as line one. Adding a new source therefore cannot
silently bypass the safety gate — a future maintainer who forgets
this loses the per-source test (`test_*_discover.py::*short_circuit`)
on the first commit.

Also owns the :class:`Provenance` enum (FR-017) so every discoverer
shares one source-of-truth for `provenance` tag values.
"""

from __future__ import annotations

from enum import Enum

from cannavec_science.banned_patterns import detect_banned_patterns
from cannavec_science.safety import check_safety


__all__ = [
    "DiscoverRefused",
    "Provenance",
    "preflight",
]


class Provenance(str, Enum):
    """Per-source provenance tag for any row emitted by a live discoverer.

    These values extend the existing curated-tier provenance set; they
    are never auto-promoted to the curated registry. The KB-flywheel
    guard (FR-018) refuses to auto-apply any row whose ``provenance``
    starts with ``live_``.
    """

    # Spec 002 — research-source live discoverers.
    LIVE_PUBMED = "live_pubmed"
    LIVE_CHEMBL = "live_chembl"
    LIVE_CTGOV = "live_ctgov"
    LIVE_PREPRINT = "live_preprint"
    LIVE_COURTLISTENER = "live_courtlistener"
    # Spec 003 — adverse-event signal feeds (US5).
    LIVE_FAERS = "live_faers"
    LIVE_MAUDE = "live_maude"
    LIVE_CAERS = "live_caers"
    LIVE_STATE_ARS_CA = "live_state_ars_ca"
    LIVE_STATE_ARS_CO = "live_state_ars_co"
    LIVE_STATE_ARS_OR = "live_state_ars_or"
    LIVE_STATE_ARS_NY = "live_state_ars_ny"
    # Spec 003 — patents + standards landscape (US6).
    LIVE_USPTO = "live_uspto"
    LIVE_ISO = "live_iso"
    LIVE_ASTM = "live_astm"
    LIVE_AOAC = "live_aoac"
    LIVE_CSA = "live_csa"


class DiscoverRefused(Exception):
    """Raised by :func:`preflight` when the prompt fails safety
    or banned-pattern checks.

    The caller (CLI / slash command / orchestrator) catches this and
    emits the standard refusal to the user. The exception's
    ``reason`` field carries a structured value the caller can route
    on:

    - ``"banned:<pattern_id>"`` for a banned-pattern hit
    - ``"safety:<flag_value>"`` for a safety refuse verdict

    ``detail`` is a free-text human-readable explanation, useful for
    the audit log but not required for refusal rendering.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def preflight(prompt: str) -> None:
    """Run safety + banned-pattern checks against the prompt.

    Returns ``None`` on PROCEED; raises :class:`DiscoverRefused` on
    refuse.

    Precedence rule: banned-pattern checks first. A
    ``cultivar_as_effect`` hit is a clearer signal than a
    ``pain_relief`` safety flag, and the refusal message is more
    actionable for the reader. The unit-test suite pins this.

    Note that only REFUSE_INDIVIDUALIZED and REFUSE_HARMFUL safety
    verdicts trigger refusal. ADD_CAUTION and REFRAME_TO_POPULATION
    do NOT block discovery — live-search results aren't
    recommendations, so the caution language belongs at render time,
    not preflight.
    """
    if not prompt or not prompt.strip():
        raise ValueError("preflight() requires a non-empty prompt")

    banned_hits = detect_banned_patterns(prompt)
    if banned_hits:
        hit = banned_hits[0]
        raise DiscoverRefused(
            reason=f"banned:{hit.pattern.id}",
            detail=f"matched: {hit.match!r}",
        )

    verdict = check_safety(prompt)
    if verdict.refused:
        flag_value = (
            verdict.flags[0].flag.value if verdict.flags else "unspecified"
        )
        raise DiscoverRefused(
            reason=f"safety:{flag_value}",
            detail=f"action={verdict.recommended_action.value}",
        )

    return None
