#!/usr/bin/env python3
"""Stdlib-only eval runner for Cannavec Science.

Drives `canonical_research_questions.json` against the composer and
asserts each prompt's declared expectations. Exits non-zero on any
failure so CI / pre-push hooks can gate on the eval suite.

Run: `python3 evals/run_evals.py`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cannavec_science.answer import compose_answer
from cannavec_science.banned_patterns import detect_banned_patterns


def _eval_prompt(prompt: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    text = prompt["prompt"]
    expect = prompt.get("expect", {})

    a = compose_answer(text)

    if "is_refusal" in expect:
        if bool(a.is_refusal) != bool(expect["is_refusal"]):
            failures.append(
                f"is_refusal: expected {expect['is_refusal']}, got {a.is_refusal}"
            )

    if "min_claims" in expect:
        if len(a.claims) < int(expect["min_claims"]):
            failures.append(
                f"min_claims: expected ≥ {expect['min_claims']}, "
                f"got {len(a.claims)}"
            )

    if "min_grade" in expect and a.evidence_summary is not None:
        from cannavec_science.evidence import EvidenceLevel
        want = EvidenceLevel(f"Level {expect['min_grade']}")
        got = a.evidence_summary.highest_grade
        if got.rank < want.rank:
            failures.append(
                f"min_grade: expected ≥ {want.value}, got {got.value}"
            )

    if "must_include_pmid" in expect:
        cite_pmids = {c.pmid for c in a.citations if c.pmid}
        for pmid in expect["must_include_pmid"]:
            if pmid not in cite_pmids:
                failures.append(
                    f"must_include_pmid: missing {pmid} "
                    f"(have {sorted(cite_pmids)[:5]}…)"
                )

    if "must_include_pmid_any_of" in expect:
        cite_pmids = {c.pmid for c in a.citations if c.pmid}
        wanted = set(expect["must_include_pmid_any_of"])
        if not (cite_pmids & wanted):
            failures.append(
                f"must_include_pmid_any_of: none of {sorted(wanted)} "
                f"in citations ({sorted(cite_pmids)[:5]}…)"
            )

    if "must_not_banned" in expect:
        hits = detect_banned_patterns(text)
        for forbidden_id in expect["must_not_banned"]:
            for h in hits:
                if h.pattern.id == forbidden_id:
                    failures.append(
                        f"must_not_banned: pattern {forbidden_id} fired"
                    )

    if "rigor_detectors_fire" in expect or "rigor_violations_max" in expect:
        from cannavec_science.rigor_checks import run_rigor_checks
        report = run_rigor_checks(text)
        fired = set()
        if report.isomer_violations:
            fired.add("isomer_collapse")
        if report.receptor_violations:
            fired.add("receptor_without_id")
        if report.dose_route_violations:
            fired.add("dose_without_route")
        if report.thca_thc_violations:
            fired.add("thca_vs_thc_conflation")
        if report.matrix_unit_violations:
            fired.add("matrix_unit_confusion")
        if report.decarb_context_violations:
            fired.add("decarb_context_missing")
        total = sum(
            len(getattr(report, attr))
            for attr in (
                "isomer_violations",
                "receptor_violations",
                "dose_route_violations",
                "thca_thc_violations",
                "matrix_unit_violations",
                "decarb_context_violations",
            )
        )

        if "rigor_detectors_fire" in expect:
            for required in expect["rigor_detectors_fire"]:
                if required not in fired:
                    failures.append(
                        f"rigor_detectors_fire: {required} did not fire "
                        f"(fired={sorted(fired)})"
                    )

        if "rigor_violations_max" in expect:
            if total > int(expect["rigor_violations_max"]):
                failures.append(
                    f"rigor_violations_max: expected ≤ "
                    f"{expect['rigor_violations_max']}, got {total} "
                    f"(fired={sorted(fired)})"
                )

    if "banned_patterns_fire" in expect:
        hits = detect_banned_patterns(text)
        fired_ids = {h.pattern.id for h in hits}
        for required in expect["banned_patterns_fire"]:
            if required not in fired_ids:
                failures.append(
                    f"banned_patterns_fire: {required} did not fire "
                    f"(fired={sorted(fired_ids)})"
                )

    if "safety_flag_must_fire" in expect:
        from cannavec_science.safety import check_safety
        verdict = check_safety(text)
        fired = {f.flag.value for f in verdict.flags}
        if expect["safety_flag_must_fire"] not in fired:
            failures.append(
                f"safety_flag_must_fire: {expect['safety_flag_must_fire']} "
                f"did not fire (fired={sorted(fired)})"
            )

    return (not failures, failures)


def main() -> int:
    path = Path(__file__).parent / "canonical_research_questions.json"
    data = json.loads(path.read_text())

    total = len(data["prompts"])
    passed = 0
    by_category: dict[str, list[bool]] = {}
    print(f"Cannavec Science evals — {total} prompts\n")

    for prompt in data["prompts"]:
        ok, failures = _eval_prompt(prompt)
        marker = "[pass]" if ok else "[FAIL]"
        print(f"{marker} {prompt['id']}  ({prompt['category']})")
        if not ok:
            for f in failures:
                print(f"        - {f}")
        else:
            passed += 1
        by_category.setdefault(prompt["category"], []).append(ok)

    print(f"\nResult: {passed}/{total} passed")
    print("\nBy category:")
    for cat in sorted(by_category):
        results = by_category[cat]
        print(f"  {cat}: {sum(results)}/{len(results)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
