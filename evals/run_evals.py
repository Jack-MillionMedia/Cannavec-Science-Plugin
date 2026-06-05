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
        if report.entourage_violations:
            fired.add("entourage_overclaim")
        # Spec 006 US5 — reporting-rigor detectors.
        for v in report.reporting_rigor_violations:
            kind = v.kind.value
            if kind == "CONSORT":
                fired.add("consort_missing")
            elif kind == "PRISMA":
                fired.add("prisma_missing")
            elif kind == "STROBE":
                fired.add("strobe_missing")
            elif kind == "ROB-2":
                fired.add("rob_2_missing")
            elif kind == "ROBINS-I":
                fired.add("robins_i_missing")
            elif kind == "AMSTAR-2":
                fired.add("amstar_2_missing")
        total = sum(
            len(getattr(report, attr))
            for attr in (
                "isomer_violations",
                "receptor_violations",
                "dose_route_violations",
                "thca_thc_violations",
                "matrix_unit_violations",
                "decarb_context_violations",
                "entourage_violations",
                "reporting_rigor_violations",
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

    # Spec 003 US1 / US7 — section-level routing assertions.
    if "must_include_section" in expect:
        titles = {t for t, _ in a.sections}
        for required in expect["must_include_section"]:
            if not any(required in t for t in titles):
                failures.append(
                    f"must_include_section: {required!r} not in "
                    f"section titles ({sorted(titles)})"
                )

    if "must_not_include_section" in expect:
        titles = {t for t, _ in a.sections}
        for forbidden in expect["must_not_include_section"]:
            if any(forbidden in t for t in titles):
                failures.append(
                    f"must_not_include_section: {forbidden!r} fired in "
                    f"section titles ({sorted(titles)})"
                )

    # Spec 003 US3 — answer-level highest_grade ceiling.
    if "max_grade" in expect and a.evidence_summary is not None:
        from cannavec_science.evidence import EvidenceLevel
        want = EvidenceLevel(f"Level {expect['max_grade']}")
        got = a.evidence_summary.highest_grade
        if got.rank > want.rank:
            failures.append(
                f"max_grade: expected ≤ {want.value}, got {got.value}"
            )

    # Spec 003 US3 — highest_grade must equal Unsupported.
    if expect.get("highest_grade_unsupported"):
        from cannavec_science.evidence import EvidenceLevel
        if a.evidence_summary is None:
            failures.append("highest_grade_unsupported: no evidence summary")
        elif a.evidence_summary.highest_grade != EvidenceLevel.UNSUPPORTED:
            failures.append(
                f"highest_grade_unsupported: got "
                f"{a.evidence_summary.highest_grade.value}"
            )

    # Spec 003 US2 — every emitted claim must mention an allowed
    # cannabinoid. (Empty list permits any.)
    if "claims_must_only_mention_cannabinoids" in expect:
        allowed = set(expect["claims_must_only_mention_cannabinoids"])
        for c in a.claims:
            # Spot-check the first part of the claim text — registry
            # claims begin with the cannabinoid name.
            head = c.text[:30].lower()
            if not any(name.lower() in head for name in allowed):
                # Also accept when the claim attributes generic
                # "cannabis" but the prompt allowed it.
                if "cannabis" not in head:
                    failures.append(
                        f"claims_must_only_mention_cannabinoids: claim "
                        f"begins {c.text[:60]!r}; allowed {sorted(allowed)}"
                    )

    return (not failures, failures)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Cannavec Science deterministic eval runner.",
    )
    parser.add_argument(
        "--include-live", action="store_true",
        help=(
            "Run prompts marked ``live: true`` (requires network). "
            "By default, live prompts are skipped so the runner works "
            "in offline CI."
        ),
    )
    parser.add_argument(
        "--strict-coverage", action="store_true",
        help="Exit non-zero if any category bucket is below its minimum.",
    )
    parser.add_argument(
        "--strict-all", action="store_true",
        help=(
            "Gate the exit code on EVERY prompt (legacy behaviour), not just "
            "the MVP-contract buckets. Use to track coverage progress."
        ),
    )
    args = parser.parse_args(argv)

    path = Path(__file__).parent / "canonical_research_questions.json"
    data = json.loads(path.read_text())

    all_prompts = data["prompts"]
    minimums: dict = data.get("category_minimums", {})
    # MVP contract buckets gate the exit code. Coverage buckets are tracked and
    # printed but non-gating — the MVP grounds via live retrieval, not curated
    # breadth recall (forcing the static registry to memorize PMIDs is the M5
    # anti-pattern). See the seed's _gating_comment.
    gating_categories: set = set(data.get("gating_categories", []))
    by_category_count: dict[str, int] = {}
    for p in all_prompts:
        by_category_count[p["category"]] = by_category_count.get(p["category"], 0) + 1

    # Bucket-minimum gating.
    coverage_failed = False
    for cat, m in minimums.items():
        actual = by_category_count.get(cat, 0)
        if actual < m:
            print(
                f"[COVERAGE FAIL] bucket {cat}: have {actual}, need ≥ {m}"
            )
            coverage_failed = True

    # Filter live prompts unless --include-live.
    prompts = [
        p for p in all_prompts
        if not p.get("live") or args.include_live
    ]

    total = len(prompts)
    passed = 0
    by_category: dict[str, list[bool]] = {}
    print(
        f"Cannavec Science evals — {total} prompts "
        f"(live skipped: {len(all_prompts) - total})\n"
    )

    for prompt in prompts:
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

    # Split the scorecard into the gating MVP contract and tracked coverage.
    gating_pass = gating_total = 0
    coverage_pass = coverage_total = 0
    print("\nBy category:")
    for cat in sorted(by_category):
        results = by_category[cat]
        total_in_bucket = by_category_count.get(cat, 0)
        minimum = minimums.get(cat, 0)
        is_gating = cat in gating_categories
        tag = "contract" if is_gating else "coverage"
        if is_gating:
            gating_pass += sum(results)
            gating_total += len(results)
        else:
            coverage_pass += sum(results)
            coverage_total += len(results)
        print(
            f"  [{tag}] {cat}: {sum(results)}/{len(results)} pass "
            f"(loaded {len(results)} of {total_in_bucket}; min {minimum})"
        )

    if gating_categories:
        print(
            f"\nContract (gating): {gating_pass}/{gating_total} — "
            "verification / rigor / refusal / routing / cross-cutting."
        )
        print(
            f"Coverage (tracked, non-gating): {coverage_pass}/{coverage_total} — "
            "curated breadth is the roadmap; the MVP grounds via live retrieval."
        )

    if args.strict_coverage and coverage_failed:
        return 2
    if args.strict_all or not gating_categories:
        return 0 if passed == total else 1
    # MVP gate: every contract-bucket prompt must pass.
    return 0 if gating_pass == gating_total else 1


if __name__ == "__main__":
    sys.exit(main())
