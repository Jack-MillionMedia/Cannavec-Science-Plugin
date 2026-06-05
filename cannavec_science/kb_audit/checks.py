"""The three audit gates over a FileRecord. All network is injected (offline-testable)."""
from __future__ import annotations

from cannavec_science.kb_audit.model import Citation, Finding

# verdict.name values from pubmed_verify.VerificationVerdict
_PASS = {"MATCH", "BARE_CITE_OK"}
_FABRICATED = {"NOT_FOUND", "MISMATCH"}


def check_citation(c: Citation, *, verify_fn, retracted_fn) -> Finding | None:
    """One citation → a Finding, or None if clean. Retraction is checked first
    and is definitive even offline. NETWORK_ERROR → inconclusive (never fabricated)."""
    kw = {"pmid": c.identifier} if c.id_type == "PMID" else (
        {"doi": c.identifier} if c.id_type == "DOI" else {})
    if kw and retracted_fn(**kw) is not None:
        return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} is retracted",
                       evidence="local retraction registry hit",
                       verdict="retracted",
                       recommended_action="find the superseding study and replace this citation",
                       route="improve_agent")

    name = verify_fn(c.identifier, c.id_type).verdict.name
    if name in _PASS:
        return None
    if name == "RETRACTED":
        return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} is retracted",
                       evidence="upstream record marks retraction", verdict="retracted",
                       recommended_action="find the superseding study and replace this citation",
                       route="improve_agent")
    if name == "NETWORK_ERROR":
        return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} not checkable now",
                       evidence="network unavailable", verdict="inconclusive",
                       recommended_action="re-run the audit with network access",
                       route="deeper_research")
    if name in _FABRICATED:
        return Finding(gate="citation",
                       issue=f"{c.id_type} {c.identifier} does not resolve to a real record",
                       evidence=f"verify verdict {name}", verdict="fabricated",
                       recommended_action="replace with a verified primary source",
                       route="improve_agent")
    return Finding(gate="citation", issue=f"{c.id_type} {c.identifier} unverifiable",
                   evidence=f"verify verdict {name}", verdict="inconclusive",
                   recommended_action="review manually", route="deeper_research")
