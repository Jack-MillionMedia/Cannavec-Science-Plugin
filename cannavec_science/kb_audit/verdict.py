"""Assemble gate findings into a routed FileVerdict (spec 032 — routing rule)."""
from __future__ import annotations

from cannavec_science.kb_audit.model import FileRecord, FileVerdict
from cannavec_science.kb_audit import checks

_FAIL_VERDICTS = {"retracted", "fabricated", "contradiction"}


def audit_record(rec: FileRecord, *, verify_fn, retracted_fn, abstract_fn) -> FileVerdict:
    findings = []
    clean = 0
    for c in rec.citations:
        cf = checks.check_citation(c, verify_fn=verify_fn, retracted_fn=retracted_fn)
        if cf is None:
            clean += 1
        elif cf.verdict != "inconclusive":
            findings.append(cf)
        clf = checks.check_claim(c, abstract_fn=abstract_fn)
        if clf is not None:
            findings.append(clf)
    gf = checks.check_grade(rec.declared_grade, rec.study_counts)
    if gf is not None:
        findings.append(gf)

    has_fail = any(f.verdict in _FAIL_VERDICTS for f in findings)
    routes = {f.route for f in findings}
    if not findings:
        routing, status, priority = "PASS", "PASS", 3
    elif routes <= {"quick_fix"}:
        routing = "READY"
        status = "FAIL" if has_fail else "FLAG"
        priority = 0
    else:
        routing = "IMPROVE"
        status = "FAIL" if has_fail else "FLAG"
        priority = 1 if has_fail else 2

    return FileVerdict(
        path=rec.path, in_scope=rec.in_scope, routing=routing, status=status, priority=priority,
        credibility={"citations_clean": clean, "citations_total": len(rec.citations),
                     "open_findings": len(findings)},
        findings=tuple(findings),
    )
