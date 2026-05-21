"""Cannavec Science CLI.

Unified entry point: ``python -m cannavec_science <subcommand>``.

Subcommands:

- ``answer "<question>"`` — researcher brief from curated registries.
- ``discover "<query>"`` — live multi-source fan-out
  (PubMed + ChEMBL + ClinicalTrials.gov).
- ``verify <PMID|DOI>`` — spot-check a single identifier.
- ``rigor "<text>"`` — run the six phytochemistry rigor detectors.
- ``bibliography <answer.json>`` — re-render a saved answer's
  bibliography in BibTeX / RIS / CSL-JSON.
- ``source-health`` — probe per-source liveness.

Every subcommand returns a non-zero exit code on refusal / error.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


def _cmd_answer(args: argparse.Namespace) -> int:
    from cannavec_science.answer import compose_answer
    from cannavec_science.bibliography import bibliography_from_answer, render

    a = compose_answer(
        args.question,
        retraction_policy=args.retraction_policy,
        include_registries=True,
        include_claims=True,
        include_rigor=True,
    )

    if args.json:
        out = json.dumps(a.to_dict(), indent=2, default=str)
        print(out)
    else:
        print(a.to_markdown())

    if args.bibliography:
        entries = bibliography_from_answer(a)
        body = render(entries, args.bibliography)
        if args.out:
            Path(args.out).write_text(body, encoding="utf-8")
            print(
                f"\n[bibliography] {len(entries)} entries written to {args.out}",
                file=sys.stderr,
            )
        else:
            print("\n" + body)

    return 1 if a.is_refusal else 0


def _cmd_discover(args: argparse.Namespace) -> int:
    from cannavec_science.discover_guard import DiscoverRefused, preflight
    from cannavec_science.synthesis import synthesize, render_markdown

    try:
        preflight(args.query)
    except DiscoverRefused as exc:
        print(f"[refused] {exc}", file=sys.stderr)
        return 2

    default_sources = "pubmed,chembl,ctgov"
    sources = {s.strip() for s in (args.sources or default_sources).split(",")}
    out_payload: dict = {"query": args.query, "sources": {}}

    for source_key in sorted(sources):
        runner = _DISCOVERER_REGISTRY.get(source_key)
        if runner is None:
            out_payload["sources"][source_key] = {
                "error": f"unknown source: {source_key!r}",
            }
            continue
        try:
            rows = runner(args)
            out_payload["sources"][source_key] = [r.to_dict() for r in rows]
        except Exception as exc:
            out_payload["sources"][source_key] = {"error": str(exc)}

    # Build synthesis block keyed by the synthesis _SOURCE_KEYS — the
    # same short keys the CLI uses, so cross-source clustering picks up
    # every live row that came back.
    synth_rows: dict = {}
    for src, val in out_payload["sources"].items():
        if isinstance(val, list):
            synth_rows[src] = val
    block = synthesize(args.query, synth_rows)

    if args.json:
        out_payload["synthesis"] = block.to_dict()
        print(json.dumps(out_payload, indent=2, default=str))
        return 0

    for src in sorted(out_payload["sources"]):
        val = out_payload["sources"][src]
        n = len(val) if isinstance(val, list) else 0
        print(f"\n## Live {src} ({n})")
        print("")
        if isinstance(val, dict) and "error" in val:
            print(f"_(live source unavailable: {val['error']})_")
            continue
        for r in val[: args.max]:
            ident = (
                r.get("pmid")
                or r.get("nct_id")
                or r.get("activity_id")
                or r.get("cid")
                or r.get("pdb_id")
                or r.get("accession_id")
                or r.get("ensembl_id")
                or r.get("monomer_id")
                or r.get("chembl_id")
                or "?"
            )
            yr = r.get("year") or r.get("start_year") or ""
            title = (
                r.get("title")
                or r.get("brief_title")
                or r.get("disease_name")
                or r.get("compound")
                or ""
            )
            print(f"- `{ident}` ({yr}) {title}".rstrip())
    print("\n## Cross-source synthesis")
    print("")
    print(render_markdown(block))
    return 0


def _run_pubmed(args):
    from cannavec_science.pubmed_search import PubMedSearcher
    return PubMedSearcher().search(
        args.query, since=args.since, max_results=args.max
    )


def _run_chembl(args):
    from cannavec_science.chembl_discover import ChEMBLSearcher
    return ChEMBLSearcher().search(args.query, max_results=args.max)


def _run_ctgov(args):
    from cannavec_science.ctgov_discover import CTGovSearcher
    return CTGovSearcher().search(args.query, max_results=args.max)


def _run_pubchem(args):
    from cannavec_science.pubchem_discover import PubChemSearcher
    return PubChemSearcher().search(args.query, max_results=args.max)


def _run_pharmgkb(args):
    from cannavec_science.pharmgkb_discover import PharmGKBSearcher
    return PharmGKBSearcher().search(args.query, max_results=args.max)


def _run_rcsb(args):
    from cannavec_science.rcsb_discover import RCSBSearcher
    return RCSBSearcher().search(args.query, max_results=args.max)


def _run_opentargets(args):
    from cannavec_science.opentargets_discover import OpenTargetsSearcher
    return OpenTargetsSearcher().search(args.query, max_results=args.max)


def _run_gwas(args):
    from cannavec_science.gwas_discover import GWASSearcher
    return GWASSearcher().search(args.query, max_results=args.max)


def _run_bindingdb(args):
    from cannavec_science.bindingdb_discover import BindingDBSearcher
    return BindingDBSearcher().search(args.query, max_results=args.max)


_DISCOVERER_REGISTRY = {
    "pubmed": _run_pubmed,
    "chembl": _run_chembl,
    "ctgov": _run_ctgov,
    "pubchem": _run_pubchem,
    "pharmgkb": _run_pharmgkb,
    "rcsb": _run_rcsb,
    "opentargets": _run_opentargets,
    "gwas": _run_gwas,
    "bindingdb": _run_bindingdb,
}


def _cmd_verify(args: argparse.Namespace) -> int:
    from cannavec_science.pubmed_verify import verify_pmid, verify_doi
    from cannavec_science.retraction import is_retracted

    ident = args.identifier.strip()
    if ident.isdigit():
        result = verify_pmid(ident)
        rec = is_retracted(pmid=ident)
        kind = "PMID"
    elif "/" in ident or ident.startswith("10."):
        result = verify_doi(ident)
        rec = is_retracted(doi=ident)
        kind = "DOI"
    else:
        print(f"[error] not a recognized identifier: {ident}", file=sys.stderr)
        return 2

    print(f"## Identifier verification — {kind} {ident}")
    print("")
    if not result:
        print(f"- **Status:** FAIL — identifier not resolvable upstream")
        return 1
    print(f"- **First author:** {getattr(result, 'first_author', None) or '?'}")
    print(f"- **Year:** {getattr(result, 'year', None) or '?'}")
    print(f"- **Journal:** {getattr(result, 'journal', None) or '?'}")
    if hasattr(result, "title") and result.title:
        print(f"- **Title:** {result.title}")
    retr_status = getattr(result, "retraction_status", "unknown")
    print(f"- **Retraction status:** {retr_status}")
    if rec is not None:
        print(f"- **Retraction registry:** **{rec.status.value}**"
              f" ({getattr(rec, 'date', '?')})")
        print(f"- **Verdict:** FAIL")
        return 1
    print(f"- **Verdict:** PASS")
    return 0


def _cmd_rigor(args: argparse.Namespace) -> int:
    from cannavec_science.rigor_checks import run_rigor_checks
    from cannavec_science.banned_patterns import detect_banned_patterns

    text = args.text
    report = run_rigor_checks(text)
    banned = detect_banned_patterns(text)

    n = (
        len(report.isomer_violations)
        + len(report.receptor_violations)
        + len(report.dose_route_violations)
        + len(report.thca_thc_violations)
        + len(report.matrix_unit_violations)
        + len(report.decarb_context_violations)
        + len(banned)
    )

    print("## Rigor & banned-pattern report")
    print("")
    print(f"- **Phytochemistry rigor violations:** "
          f"{n - len(banned)}")
    print(f"- **Banned-pattern hits:** {len(banned)}")
    print("")

    if report.isomer_violations:
        print("### Isomer collapse (bare cannabinoid in pharmacology context)")
        for v in report.isomer_violations:
            print(f"- `{v.matched_phrase}` — {v.context_hint}")
        print("")
    if report.receptor_violations:
        print("### Receptor without UniProt ID")
        for v in report.receptor_violations:
            print(f"- `{v.matched_phrase}` ({v.receptor})")
        print("")
    if report.dose_route_violations:
        print("### Dose without administration route")
        for v in report.dose_route_violations:
            print(f"- `{v.dose}` in: {v.sentence}")
        print("")
    if report.thca_thc_violations:
        print("### THCA-vs-THC conflation")
        for v in report.thca_thc_violations:
            print(f"- `{v.matched_phrase}` — disambiguate THCA vs Δ⁹-THC")
        print("")
    if report.matrix_unit_violations:
        print("### Matrix-unit confusion")
        for v in report.matrix_unit_violations:
            print(f"- `{v.unit_phrase}` — add matrix tag "
                  f"(plasma / urine / flower / extract)")
        print("")
    if report.decarb_context_violations:
        print("### Decarboxylation context missing")
        for v in report.decarb_context_violations:
            print(f"- `{v.claim_phrase}` — raw-extract pharmacology should "
                  f"cite acid cannabinoid (THCA/CBDA)")
        print("")
    if banned:
        print("### Banned-pattern hits")
        for hit in banned:
            print(f"- **{hit.pattern.id}**: `{hit.match}`")
            print(f"  - Why: {hit.pattern.why}")
        print("")

    if n == 0:
        print("**Clean.** No violations.")
        return 0
    return 1


def _cmd_bibliography(args: argparse.Namespace) -> int:
    from cannavec_science.bibliography import render, BibliographyEntry, _entry_from_citation
    from cannavec_science.answer import Answer, Citation
    from cannavec_science.evidence import EvidenceLevel

    payload = json.loads(Path(args.answer_json).read_text(encoding="utf-8"))
    citations = [
        Citation(
            label=c["label"],
            pmid=c.get("pmid"),
            doi=c.get("doi"),
            url=c.get("url"),
            year=c.get("year"),
            grade=EvidenceLevel(c["grade"]) if c.get("grade") else None,
        )
        for c in payload.get("citations", [])
    ]
    entries = [
        _entry_from_citation(c, payload.get("evidence_summary", {}).get("highest_grade"))
        for c in citations
    ]
    body = render(entries, args.format)
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"[bibliography] {len(entries)} entries → {args.out}",
              file=sys.stderr)
    else:
        print(body)
    return 0


def _cmd_source_health(args: argparse.Namespace) -> int:
    from cannavec_science.source_health import ping_all

    healths = ping_all()
    sources = {h.source: h for h in healths}
    requested = {s.strip() for s in (args.sources or "pubmed,chembl,ctgov").split(",")}

    print("## Source health probe")
    print("")
    any_down = False
    for src in sorted(requested):
        h = sources.get(src)
        if h is None:
            print(f"- **{src}**: not configured")
            any_down = True
            continue
        status = "ok" if h.ok else "FAIL"
        print(f"- **{src}**: {status} (rtt {h.rtt_ms:.0f}ms)")
        if not h.ok:
            any_down = True
            if h.error:
                print(f"  - error: {h.error}")
    return 1 if any_down else 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cannavec_science",
        description="Cannavec Science — cannabis-research primitives.",
    )
    sub = p.add_subparsers(dest="cmd")

    # answer
    a = sub.add_parser("answer", help="Compose a researcher brief.")
    a.add_argument("question")
    a.add_argument("--audience", default="researcher")
    a.add_argument("--retraction-policy", choices=["strict", "badge"],
                   default="strict")
    a.add_argument("--bibliography", choices=["bibtex", "ris", "csljson"],
                   default=None)
    a.add_argument("--out", help="Write bibliography to this file")
    a.add_argument("--json", action="store_true",
                   help="Emit typed Answer as JSON")
    a.set_defaults(func=_cmd_answer)

    # discover
    d = sub.add_parser(
        "discover",
        help=(
            "Live multi-source fan-out across primary scientific sources: "
            "pubmed, chembl, ctgov (default) plus optional cannabis-primary "
            "widening: pubchem, pharmgkb, rcsb, opentargets, gwas, bindingdb."
        ),
    )
    d.add_argument("query")
    d.add_argument("--since", default=None,
                   help="ISO date floor (e.g., 2024-01-01)")
    d.add_argument("--max", type=int, default=10)
    d.add_argument(
        "--sources",
        default="pubmed,chembl,ctgov",
        help=(
            "Comma-separated subset of: pubmed, chembl, ctgov, pubchem, "
            "pharmgkb, rcsb, opentargets, gwas, bindingdb."
        ),
    )
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_discover)

    # verify
    v = sub.add_parser("verify",
                       help="Spot-check a single PMID or DOI.")
    v.add_argument("identifier")
    v.set_defaults(func=_cmd_verify)

    # rigor
    r = sub.add_parser("rigor",
                       help="Run six phytochemistry rigor detectors on text.")
    r.add_argument("text")
    r.set_defaults(func=_cmd_rigor)

    # bibliography
    b = sub.add_parser("bibliography",
                       help="Re-render a saved Answer's bibliography.")
    b.add_argument("answer_json", help="Path to a JSON-dumped Answer")
    b.add_argument("--format", choices=["bibtex", "ris", "csljson"],
                   required=True)
    b.add_argument("--out", help="Write to file (else stdout)")
    b.set_defaults(func=_cmd_bibliography)

    # source-health
    sh = sub.add_parser("source-health",
                        help="Probe per-source liveness.")
    sh.add_argument("--sources", default="pubmed,chembl,ctgov")
    sh.set_defaults(func=_cmd_source_health)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
