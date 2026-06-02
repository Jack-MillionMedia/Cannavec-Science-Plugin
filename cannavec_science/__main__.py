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
- ``meta <studies.json>`` — pool per-study effect sizes into a
  fixed/random-effects meta-analysis with heterogeneity (Q, I², τ²) and
  a GRADE inconsistency verdict (spec 011); ``--diagnostics`` adds Egger /
  leave-one-out / subgroup / trim-and-fill (specs 012-014) and
  ``--baseline-risk`` adds the GRADE Summary-of-Findings absolute effect +
  NNT (spec 015) and ``--certainty`` adds the GRADE ⊕ certainty rating that
  completes the SoF table (spec 016).

Every subcommand returns a non-zero exit code on refusal / error.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from cannavec_science._log import get_logger


_log = get_logger("cli")


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

    # v0.2 scaffolders — opt-in via flags. Each one is deterministic.
    scaffolder_blocks: list[str] = []
    scaffolders_dict: dict = {}
    pico_block = None
    if getattr(args, "pico", False) or getattr(args, "protocol_skeleton", False):
        from cannavec_science.pico import build_pico, render_markdown as render_pico
        pico_block = build_pico(a)
        if getattr(args, "pico", False):
            scaffolder_blocks.append(render_pico(pico_block))
            scaffolders_dict["pico"] = pico_block.to_dict()
    if getattr(args, "power_calc", False):
        from cannavec_science.power_calc import build_for_answer, render_markdown as render_power
        estimates = build_for_answer(a)
        scaffolder_blocks.append(render_power(estimates))
        scaffolders_dict["power_calc"] = [e.to_dict() for e in estimates]
    if getattr(args, "grade_profile", False):
        from cannavec_science.grade_profile import (
            build_profile, render_csv, render_markdown as render_gp,
        )
        profile = build_profile(a)
        fmt = getattr(args, "grade_profile_format", "markdown") or "markdown"
        if fmt == "csv":
            scaffolder_blocks.append("## GRADE evidence-profile (CSV)\n\n```\n" + render_csv(profile) + "```\n")
        else:
            scaffolder_blocks.append(render_gp(profile))
        scaffolders_dict["grade_profile"] = profile.to_dict()
    if getattr(args, "protocol_skeleton", False):
        from cannavec_science.protocol_skeleton import (
            build_skeleton, render_markdown as render_proto,
        )
        skeleton = build_skeleton(a, pico=pico_block)
        scaffolder_blocks.append(render_proto(skeleton))
        scaffolders_dict["protocol_skeleton"] = skeleton.to_dict()
    if getattr(args, "regulatory_feasibility", None):
        from cannavec_science.regulatory_feasibility import (
            assess_feasibility, render_markdown as render_regfeas,
        )
        from cannavec_science.pico import build_pico
        if pico_block is None:
            pico_block = build_pico(a)
        compound = pico_block.intervention or "Δ⁹-THC"
        advisory = assess_feasibility(compound, args.regulatory_feasibility)
        scaffolder_blocks.append(render_regfeas(advisory))
        scaffolders_dict["regulatory_feasibility"] = advisory.to_dict()

    # Summary-of-Findings weave (spec 017) — pool §I-anchored studies per
    # outcome and carry certainty + relative + absolute + NNT into the brief.
    if getattr(args, "sof", None) and not a.is_refusal:
        from cannavec_science.sof import (
            SoFError, build_sof, render_markdown as render_sof,
        )
        try:
            sof_spec = json.loads(Path(args.sof).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"[error] cannot read SoF sidecar {args.sof!r}: {exc}",
                  file=sys.stderr)
            return 2
        try:
            sof_obj = build_sof(sof_spec)
        except SoFError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        scaffolder_blocks.append(render_sof(sof_obj))
        scaffolders_dict["summary_of_findings"] = sof_obj.to_dict()

    if getattr(args, "augment_live", False):
        _augment_with_live(a, args)

    if args.json:
        payload = a.to_dict()
        if scaffolders_dict:
            payload["scaffolders"] = scaffolders_dict
        out = json.dumps(payload, indent=2, default=str)
        print(out)
    else:
        print(a.to_markdown())
        for block in scaffolder_blocks:
            print()
            print(block)

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


def _augment_with_live(a, args) -> None:
    """Flag-gated live-evidence weave (Constitution §IX).

    Re-uses the prompt as a discovery query, fans out to the requested live
    lanes, and attaches provisional, provenance-tagged findings to the
    Answer. Network only; a refusal or any lane failure degrades gracefully
    — the curated brief still stands. Never promotes a live row to curated.
    """
    from types import SimpleNamespace
    from cannavec_science.answer import live_finding_from_row
    from cannavec_science.discover_guard import DiscoverRefused, preflight

    if a.is_refusal:
        return
    try:
        preflight(a.prompt)
    except DiscoverRefused:
        return
    per_lane = max(1, int(getattr(args, "augment_max", 5) or 5))
    q = SimpleNamespace(
        query=a.prompt, since=getattr(args, "since", None), max=per_lane
    )
    sources = [
        s.strip()
        for s in (getattr(args, "augment_sources", None) or "pubmed,ctgov").split(",")
        if s.strip()
    ]
    for src in sources:
        runner = _DISCOVERER_REGISTRY.get(src)
        if runner is None:
            continue
        try:
            rows = runner(q)
        except Exception as exc:  # noqa: BLE001 — degrade; curated answer stands
            _log.warning("answer --augment-live lane %s failed: %s", src, exc)
            continue
        for r in rows[:per_lane]:
            finding = live_finding_from_row(src, r.to_dict())
            if finding:
                a.add_live_finding(**finding)


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
    # Spec 005 US6 — opt-in Europe PMC complement to PubMed.
    if getattr(args, "include_europepmc", False):
        sources.add("europepmc")
    # Spec 006 US6 — opt-in OpenAlex open scholarly citation graph.
    if getattr(args, "include_openalex", False):
        sources.add("openalex")
    out_payload: dict = {"query": args.query, "sources": {}}

    sorted_sources = sorted(sources)
    parallel = max(1, int(getattr(args, "parallel", 1) or 1))

    def _run_one(source_key: str):
        runner = _DISCOVERER_REGISTRY.get(source_key)
        if runner is None:
            return source_key, {"error": f"unknown source: {source_key!r}"}
        try:
            rows = runner(args)
            return source_key, [r.to_dict() for r in rows]
        except Exception as exc:  # noqa: BLE001 — surface to JSON, don't crash fan-out
            _log.warning("discover lane %s failed: %s", source_key, exc)
            return source_key, {"error": str(exc)}

    if parallel <= 1 or len(sorted_sources) <= 1:
        for source_key in sorted_sources:
            key, payload = _run_one(source_key)
            out_payload["sources"][key] = payload
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {pool.submit(_run_one, s): s for s in sorted_sources}
            results: dict = {}
            for fut in as_completed(futures):
                key, payload = fut.result()
                results[key] = payload
            # Preserve canonical (alphabetical) ordering in the output so
            # JSON / Markdown are deterministic regardless of completion order.
            for source_key in sorted_sources:
                out_payload["sources"][source_key] = results[source_key]

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
    # Per-source relevance gate: CT.gov free-text matching is broad, so a
    # cannabis-science query must not surface unrelated trials.
    return CTGovSearcher().search(
        args.query, max_results=args.max, cannabis_relevant_only=True
    )


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


def _run_biorxiv(args):
    from cannavec_science.biorxiv_discover import BioRxivSearcher
    return BioRxivSearcher().search(
        args.query, since=args.since, max_results=args.max,
    )


def _run_medrxiv(args):
    from cannavec_science.medrxiv_discover import MedRxivSearcher
    return MedRxivSearcher().search(
        args.query, since=args.since, max_results=args.max,
    )


def _run_europepmc(args):
    from cannavec_science.europepmc_discover import EuropePMCSearcher
    return EuropePMCSearcher().search(
        args.query, since=args.since, max_results=args.max,
    )


def _run_openalex(args):
    from cannavec_science.openalex_discover import OpenAlexSearcher
    return OpenAlexSearcher().search(
        args.query, since=args.since, max_results=args.max,
    )


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
    # Spec 002 US1 — preprint lanes (Level D cap per FR-202).
    "biorxiv": _run_biorxiv,
    "medrxiv": _run_medrxiv,
    # Spec 005 US6 — Europe PMC twelfth primary-source live lane.
    "europepmc": _run_europepmc,
    # Spec 006 US6 — OpenAlex thirteenth primary-source live lane.
    "openalex": _run_openalex,
}


_NCT_RE = __import__("re").compile(r"^NCT\d{8}$", __import__("re").IGNORECASE)
_CHEMBL_RE = __import__("re").compile(r"^CHEMBL\d+$", __import__("re").IGNORECASE)


def _classify_identifier(ident: str) -> str:
    """Classify an identifier into one of the five §I shapes."""
    s = ident.strip()
    if not s:
        return "unknown"
    if s.isdigit():
        return "PMID"
    if _NCT_RE.match(s):
        return "NCT"
    if _CHEMBL_RE.match(s):
        return "ChEMBL"
    if "/" in s or s.startswith("10."):
        return "DOI"
    from cannavec_science.uniprot_verify import is_uniprot_accession
    if is_uniprot_accession(s):
        return "UniProt"
    return "unknown"


def _verify_pmid_render(ident: str, args: argparse.Namespace) -> int:
    from cannavec_science.pubmed_verify import verify_pmid, VerificationVerdict
    from cannavec_science.retraction import is_retracted

    result = verify_pmid(ident)
    rec = is_retracted(pmid=ident)

    citation_block = None
    if not getattr(args, "no_citation_network", False):
        from cannavec_science.citation_network import build_citation_network
        try:
            citation_block = build_citation_network(ident)
        except Exception as exc:
            from cannavec_science.citation_network import CitationNetworkBlock
            citation_block = CitationNetworkBlock(
                pmid=ident, count=0, error=str(exc),
            )

    # Map the typed verdict to a CLI verdict + exit code. Verification that
    # did not actually happen (transport/network failure) must FAIL CLOSED as
    # UNVERIFIED — never PASS (Constitution §I: a citation is only trustworthy
    # once the upstream record is confirmed). A locally-registered retraction
    # is an independent, definitive FAIL even when the upstream is unreachable.
    #   0 = PASS · 1 = FAIL (record bad/retracted/mismatch) · 3 = UNVERIFIED
    verdict = result.verdict
    if rec is not None:
        cli_verdict, exit_code = "FAIL", 1
    elif verdict == VerificationVerdict.NETWORK_ERROR:
        cli_verdict, exit_code = "UNVERIFIED", 3
    elif verdict in (
        VerificationVerdict.NOT_FOUND,
        VerificationVerdict.RETRACTED,
        VerificationVerdict.MISMATCH,
    ):
        cli_verdict, exit_code = "FAIL", 1
    else:  # MATCH / BARE_CITE_OK
        cli_verdict, exit_code = "PASS", 0

    if getattr(args, "json", False):
        out = {
            "identifier": ident,
            "kind": "PMID",
            "verdict": cli_verdict,
            "first_author": result.actual_first_author,
            "year": result.actual_year,
            "journal": result.journal,
            "title": result.title,
            "retraction_status": result.retraction_status,
        }
        if result.notes:
            out["notes"] = list(result.notes)
        if rec is not None:
            out["retraction_registry"] = {
                "status": rec.status.value,
                "date": getattr(rec, "date", None),
            }
        if citation_block is not None:
            out["citation_network"] = citation_block.to_dict()
        print(json.dumps(out, indent=2, default=str))
        return exit_code

    print(f"## Identifier verification — PMID {ident}")
    print("")
    # Locally-registered retraction is definitive even if the upstream fetch
    # failed — surface it first.
    if rec is not None:
        print(
            f"- **Retraction registry:** **{rec.status.value}**"
            f" ({getattr(rec, 'date', '?')})"
        )
        print("- **Verdict:** FAIL — citation is retracted")
        return exit_code
    if verdict == VerificationVerdict.NETWORK_ERROR:
        print("- **Status:** UNVERIFIED — could not reach PubMed (network error)")
        for note in result.notes:
            print(f"  - {note}")
        print("- **Verdict:** UNVERIFIED")
        return exit_code
    if verdict == VerificationVerdict.NOT_FOUND:
        print("- **Status:** FAIL — PMID not found in PubMed")
        print("- **Verdict:** FAIL")
        return exit_code
    print(f"- **First author:** {result.actual_first_author or '?'}")
    print(f"- **Year:** {result.actual_year or '?'}")
    print(f"- **Journal:** {result.journal or '?'}")
    if result.title:
        print(f"- **Title:** {result.title}")
    print(f"- **Retraction status:** {result.retraction_status}")
    if verdict == VerificationVerdict.RETRACTED:
        print("- **Verdict:** FAIL — record is retracted")
        return exit_code
    if verdict == VerificationVerdict.MISMATCH:
        print("- **Verdict:** FAIL — record does not match the cited claim")
        return exit_code
    print("- **Verdict:** PASS")
    if citation_block is not None and not citation_block.error:
        print("")
        from cannavec_science.citation_network import render_markdown as render_cn
        print(render_cn(citation_block))
    return exit_code


def _verify_doi_render(ident: str, args: argparse.Namespace) -> int:
    from cannavec_science.pubmed_verify import verify_doi
    from cannavec_science.retraction import is_retracted

    result = verify_doi(ident)
    rec = is_retracted(doi=ident)

    if getattr(args, "json", False):
        out = {
            "identifier": ident,
            "kind": "DOI",
            "first_author": getattr(result, "first_author_surname", None)
                or getattr(result, "first_author", None),
            "year": getattr(result, "year", None),
            "journal": getattr(result, "journal", None),
            "title": getattr(result, "title", None),
            "retraction_status": getattr(result, "retraction_status", "unknown"),
        }
        if rec is not None:
            out["retraction_registry"] = {
                "status": rec.status.value,
                "date": getattr(rec, "date", None),
            }
        print(json.dumps(out, indent=2, default=str))
        return 1 if rec is not None or not result else 0

    print(f"## Identifier verification — DOI {ident}")
    print("")
    if not result:
        print("- **Status:** FAIL — identifier not resolvable upstream")
        return 1
    print(
        f"- **First author:** "
        f"{getattr(result, 'first_author_surname', None) or getattr(result, 'first_author', None) or '?'}"
    )
    print(f"- **Year:** {getattr(result, 'year', None) or '?'}")
    print(f"- **Journal:** {getattr(result, 'journal', None) or '?'}")
    if hasattr(result, "title") and result.title:
        print(f"- **Title:** {result.title}")
    retr_status = getattr(result, "retraction_status", "unknown")
    print(f"- **Retraction status:** {retr_status}")
    if rec is not None:
        print(
            f"- **Retraction registry:** **{rec.status.value}**"
            f" ({getattr(rec, 'date', '?')})"
        )
        print("- **Verdict:** FAIL")
        return 1
    print("- **Verdict:** PASS")
    return 0


def _verify_nct_render(ident: str, args: argparse.Namespace) -> int:
    """Resolve an NCT ID via CT.gov v2 (spec 003 US5 / FR-005)."""
    from cannavec_science.ctgov_discover import CTGovSearcher
    from cannavec_science.discover_guard import DiscoverRefused

    try:
        row = CTGovSearcher().fetch_trial(ident.upper())
    except DiscoverRefused as exc:
        print(f"[refused] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # NetworkError, ValueError, etc.
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        if row is None:
            out = {"identifier": ident, "kind": "NCT", "status": "not_found"}
            print(json.dumps(out, indent=2, default=str))
            return 1
        out = {"identifier": ident, "kind": "NCT", "trial": row.to_dict()}
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"## Identifier verification — NCT {ident}")
    print("")
    if row is None:
        print("- **Status:** FAIL — NCT not resolvable on ClinicalTrials.gov")
        return 1
    print(f"- **Title:** {row.title}")
    print(f"- **Phase:** {row.phase}")
    print(f"- **Status:** {row.status}")
    if row.sponsor:
        print(f"- **Sponsor:** {row.sponsor}")
    if row.pi_name:
        print(f"- **PI:** {row.pi_name}")
    if row.condition:
        print(f"- **Conditions:** {', '.join(row.condition)}")
    if row.intervention:
        print(f"- **Interventions:** {', '.join(row.intervention)}")
    if row.primary_endpoints:
        print(f"- **Primary endpoints:** {', '.join(row.primary_endpoints)}")
    if row.enrollment_count is not None:
        print(f"- **Enrolment:** {row.enrollment_count}")
    if row.start_date:
        print(f"- **Started:** {row.start_date}")
    print(f"- **URL:** {row.url}")
    print("- **Verdict:** PASS")
    return 0


def _verify_chembl_render(ident: str, args: argparse.Namespace) -> int:
    """Resolve a ChEMBL ID via the ChEMBL REST (spec 003 US5 / FR-005)."""
    from cannavec_science.chembl_discover import ChEMBLSearcher
    from cannavec_science.discover_guard import DiscoverRefused

    try:
        compound = ChEMBLSearcher().fetch_compound(ident.upper())
    except DiscoverRefused as exc:
        print(f"[refused] {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        if compound is None:
            out = {"identifier": ident, "kind": "ChEMBL", "status": "not_found"}
            print(json.dumps(out, indent=2, default=str))
            return 1
        out = {
            "identifier": ident,
            "kind": "ChEMBL",
            "compound": {
                "chembl_id": compound.get("molecule_chembl_id"),
                "pref_name": compound.get("pref_name"),
                "molecule_type": compound.get("molecule_type"),
                "molecular_formula": (
                    compound.get("molecule_properties") or {}
                ).get("full_molformula"),
                "smiles": (
                    compound.get("molecule_structures") or {}
                ).get("canonical_smiles"),
                "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/"
                       f"{compound.get('molecule_chembl_id')}/",
            },
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"## Identifier verification — ChEMBL {ident.upper()}")
    print("")
    if compound is None:
        print("- **Status:** FAIL — compound not resolvable on ChEMBL")
        return 1
    chembl_id = compound.get("molecule_chembl_id")
    pref_name = compound.get("pref_name") or "(unnamed)"
    mol_props = compound.get("molecule_properties") or {}
    structures = compound.get("molecule_structures") or {}
    print(f"- **ChEMBL ID:** {chembl_id}")
    print(f"- **Compound name:** {pref_name}")
    if compound.get("molecule_type"):
        print(f"- **Type:** {compound.get('molecule_type')}")
    if mol_props.get("full_molformula"):
        print(f"- **Formula:** {mol_props.get('full_molformula')}")
    if mol_props.get("full_mwt"):
        print(f"- **Molecular weight:** {mol_props.get('full_mwt')}")
    if structures.get("canonical_smiles"):
        print(f"- **SMILES:** `{structures.get('canonical_smiles')}`")
    if structures.get("standard_inchi_key"):
        print(f"- **InChI key:** {structures.get('standard_inchi_key')}")
    print(
        f"- **URL:** https://www.ebi.ac.uk/chembl/compound_report_card/"
        f"{chembl_id}/"
    )
    print("- **Verdict:** PASS")
    return 0


def _verify_uniprot_render(ident: str, args: argparse.Namespace) -> int:
    """Resolve a UniProt accession via the UniProt REST (spec 003 US5 / FR-005)."""
    from cannavec_science.uniprot_verify import verify_uniprot

    try:
        record = verify_uniprot(ident.upper())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        if record is None:
            out = {
                "identifier": ident,
                "kind": "UniProt",
                "status": "not_found",
            }
            print(json.dumps(out, indent=2, default=str))
            return 1
        out = {
            "identifier": ident,
            "kind": "UniProt",
            "protein": record.to_dict(),
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"## Identifier verification — UniProt {ident.upper()}")
    print("")
    if record is None:
        print("- **Status:** FAIL — accession not resolvable on UniProt")
        return 1
    print(f"- **Protein name:** {record.protein_name}")
    if record.gene_symbol:
        print(f"- **Gene symbol:** {record.gene_symbol}")
    if record.organism:
        organism = record.organism
        if record.organism_taxon_id is not None:
            organism = f"{organism} (taxon {record.organism_taxon_id})"
        print(f"- **Organism:** {organism}")
    if record.sequence_length is not None:
        print(f"- **Sequence length:** {record.sequence_length} aa")
    print(
        f"- **Review status:** "
        f"{'reviewed (Swiss-Prot)' if record.reviewed else 'unreviewed (TrEMBL)'}"
    )
    print(f"- **URL:** {record.url}")
    print("- **Verdict:** PASS")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Verify a single identifier (spec 003 US5 / FR-005).

    Accepts the five Constitution §I shapes: PMID, DOI, NCT, ChEMBL,
    UniProt. Unknown shapes return a descriptive error listing the
    accepted shapes so the user can re-key.
    """
    ident = args.identifier.strip()
    kind = _classify_identifier(ident)
    if kind == "PMID":
        return _verify_pmid_render(ident, args)
    if kind == "DOI":
        return _verify_doi_render(ident, args)
    if kind == "NCT":
        return _verify_nct_render(ident, args)
    if kind == "ChEMBL":
        return _verify_chembl_render(ident, args)
    if kind == "UniProt":
        return _verify_uniprot_render(ident, args)
    print(
        f"[error] not a recognized identifier: {ident}\n"
        f"  Accepted shapes (Constitution §I): "
        f"PMID (digits), DOI (10.*/...), NCT (NCT\\d{{8}}), "
        f"ChEMBL (CHEMBL\\d+), UniProt (e.g. P21554, Q8NER1).",
        file=sys.stderr,
    )
    return 2


def _cmd_rigor(args: argparse.Namespace) -> int:
    from cannavec_science.rigor_checks import run_rigor_checks
    from cannavec_science.banned_patterns import detect_banned_patterns

    text = args.text
    report = run_rigor_checks(text)
    banned = detect_banned_patterns(text)

    # Spec 003 US10 / FR-010 — dedup the rendered output by
    # (detector, span) so identical findings can never appear twice.
    def _dedup(items, span_fn):
        seen: set[tuple] = set()
        out = []
        for v in items:
            key = tuple(span_fn(v))
            if key in seen:
                continue
            seen.add(key)
            out.append(v)
        return out

    iso = _dedup(report.isomer_violations, lambda v: v.span)
    recv = _dedup(report.receptor_violations, lambda v: v.span)
    dose = _dedup(report.dose_route_violations, lambda v: v.span)
    thca = _dedup(report.thca_thc_violations, lambda v: v.span)
    matrix = _dedup(report.matrix_unit_violations, lambda v: v.span)
    decarb = _dedup(report.decarb_context_violations,
                    lambda v: (0, len(v.claim_phrase)))
    ent = _dedup(
        report.entourage_violations,
        lambda v: (v.terpene, v.cannabinoid, v.span),
    )
    # Spec 006 US5 — reporting-rigor violations (CONSORT, PRISMA,
    # STROBE, ROB-2, ROBINS-I, AMSTAR-2).
    reprig = _dedup(
        report.reporting_rigor_violations,
        lambda v: (v.kind.value, v.span),
    )

    n = (
        len(iso) + len(recv) + len(dose) + len(thca)
        + len(matrix) + len(decarb) + len(ent) + len(reprig) + len(banned)
    )

    print("## Rigor & banned-pattern report")
    print("")
    print(f"- **Phytochemistry rigor violations:** "
          f"{n - len(banned) - len(reprig)}")
    print(f"- **Reporting-rigor violations:** {len(reprig)}")
    print(f"- **Banned-pattern hits:** {len(banned)}")
    print("")

    if iso:
        print("### Isomer collapse (bare cannabinoid in pharmacology context)")
        for v in iso:
            print(f"- `{v.matched_phrase}` — {v.context_hint}")
        print("")
    if recv:
        print("### Receptor without UniProt ID")
        for v in recv:
            print(f"- `{v.matched_phrase}` ({v.receptor})")
        print("")
    if dose:
        print("### Dose without administration route")
        for v in dose:
            print(f"- `{v.dose}` in: {v.sentence}")
        print("")
    if thca:
        print("### THCA-vs-THC conflation")
        for v in thca:
            print(f"- `{v.matched_phrase}` — disambiguate THCA vs Δ⁹-THC")
        print("")
    if matrix:
        print("### Matrix-unit confusion")
        for v in matrix:
            print(f"- `{v.unit_phrase}` — add matrix tag "
                  f"(plasma / urine / flower / extract)")
        print("")
    if decarb:
        print("### Decarboxylation context missing")
        for v in decarb:
            print(f"- `{v.claim_phrase}` — raw-extract pharmacology should "
                  f"cite acid cannabinoid (THCA/CBDA)")
        print("")
    if ent:
        print("### Entourage-overclaim (synergy claim without canonical citation)")
        for v in ent:
            print(f"- `{v.terpene}` × `{v.cannabinoid}` — cite Russo 2011 / "
                  f"Finlay 2020 / Santiago 2019 / LaVigne 2021 or reframe "
                  f"as open hypothesis.")
        print("")
    if reprig:
        print("### Reporting-rigor violations (EQUATOR-network / risk-of-bias)")
        for v in reprig:
            print(
                f"- **{v.kind.value} missing** at `{v.anchor_text}` — "
                f"recommend Schulz/Page/von-Elm/Sterne/Shea PMID "
                f"{v.recommendation_pmid}"
            )
            print(f"  - Why: {v.why}")
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
    # _entry_from_citation accepts ``answer`` only as a keyword argument
    # (its evidence-level lookup uses Answer.claims). Re-rendering from a
    # saved Answer JSON does not reconstruct the Claim graph, so pass
    # ``answer=None`` and surface the per-citation grade (already
    # captured in the saved JSON) on the entry's evidence_level field.
    entries: list = []
    for c in citations:
        entry = _entry_from_citation(c, answer=None)
        if c.grade is not None:
            entry = entry.__class__(  # frozen dataclass — copy with override
                **{**entry.__dict__, "evidence_level": c.grade.value}
            )
        entries.append(entry)
    body = render(entries, args.format)
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"[bibliography] {len(entries)} entries → {args.out}",
              file=sys.stderr)
    else:
        print(body)
    return 0


def _cmd_freshness(args: argparse.Namespace) -> int:
    """Probe one or all registries' watch_pmids.

    Stdlib-only; the offline path uses the local retraction registry
    only (no network). ``--network`` enables PubMed verification with
    the default fetcher.
    """
    from cannavec_science.freshness import (
        FreshnessStatus,
        all_registry_names,
        probe_all,
        probe_registry,
        render_json,
        render_markdown,
    )

    fetcher = None
    if getattr(args, "network", False):
        from cannavec_science.pubmed_verify import default_pubmed_fetcher
        fetcher = default_pubmed_fetcher

    parallel = max(1, int(getattr(args, "parallel", 1) or 1))

    targets: tuple[str, ...]
    if args.registry:
        if args.registry == "all":
            targets = all_registry_names()
        else:
            if args.registry not in all_registry_names():
                print(
                    f"[error] unknown registry: {args.registry}; "
                    f"expected one of {all_registry_names()} or 'all'",
                    file=sys.stderr,
                )
                return 2
            targets = (args.registry,)
    else:
        targets = all_registry_names()

    reports = [
        probe_registry(t, fetcher=fetcher, parallel=parallel)
        for t in targets
    ]

    if args.json:
        payload = {"registries": [r.to_dict() for r in reports]}
        print(json.dumps(payload, indent=2, default=str))
    else:
        for rep in reports:
            print(render_markdown(rep))
            print("")

    # Exit codes: 0 if all clean, 1 if any retractions or EOCs detected.
    for rep in reports:
        if rep.n_retraction > 0 or rep.n_eoc > 0:
            return 1
    return 0


def _cmd_freshness_report(args: argparse.Namespace) -> int:
    """Curator-facing report — same as freshness but filtered by date."""
    return _cmd_freshness(args)


def _cmd_registries(args: argparse.Namespace) -> int:
    """Emit the curated-registry inventory (spec 003 US8 / FR-008).

    Industry-expert discoverability — every registry the plugin
    curates, with row counts, last-verified dates, and entry labels.
    """
    from cannavec_science.registries import (
        all_registry_groups,
        build_inventory,
        render_json,
        render_markdown,
    )

    registry = args.registry or "all"
    if registry != "all" and registry not in all_registry_groups():
        print(
            f"[error] unknown registry: {registry}; expected one of "
            f"{all_registry_groups()} or 'all'",
            file=sys.stderr,
        )
        return 2
    inv = build_inventory(registry)
    if getattr(args, "format", "markdown") == "json":
        print(render_json(inv))
    else:
        print(render_markdown(inv))
    return 0


def _cmd_source_health(args: argparse.Namespace) -> int:
    """Probe per-source liveness (spec 003 US4 / FR-004).

    Reads the actual ``SourceHealth`` dataclass fields (``status``,
    ``latency_ms``, ``error_excerpt``) — earlier prototypes used a
    deleted ``ok``/``rtt_ms``/``error`` shape and crashed.
    """
    from cannavec_science.source_health import HealthStatus, ping_all

    healths = ping_all()
    sources = {h.source: h for h in healths}
    requested = {s.strip() for s in (args.sources or "pubmed,chembl,ctgov").split(",")}

    if getattr(args, "json", False):
        payload = []
        any_down = False
        for src in sorted(requested):
            h = sources.get(src)
            if h is None:
                payload.append({
                    "source": src,
                    "status": "unknown",
                    "latency_ms": None,
                    "error_excerpt": "not configured",
                })
                any_down = True
                continue
            row = h.to_dict()
            payload.append(row)
            if h.status != HealthStatus.GREEN:
                any_down = True
        print(json.dumps({"sources": payload}, indent=2, default=str))
        return 1 if any_down else 0

    print("## Source health probe")
    print("")
    any_down = False
    for src in sorted(requested):
        h = sources.get(src)
        if h is None:
            print(f"- **{src}**: not configured")
            any_down = True
            continue
        rtt = f"{h.latency_ms}ms" if h.latency_ms is not None else "n/a"
        print(f"- **{src}**: {h.status.value} (rtt {rtt})")
        if h.status != HealthStatus.GREEN:
            any_down = True
            if h.error_excerpt:
                print(f"  - error: {h.error_excerpt}")
    return 1 if any_down else 0


def _cmd_fragility(args: argparse.Namespace) -> int:
    """Fragility Index of a single 2×2 trial (spec 022)."""
    from cannavec_science.fragility import (
        FragilityError, fragility_index, render_fragility,
    )
    try:
        result = fragility_index(
            args.events_t, args.n_t, args.events_c, args.n_c,
            alpha=getattr(args, "alpha", 0.05),
        )
    except FragilityError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(render_fragility(result))
    # A non-significant result is a clean, expected outcome — exit 0.
    return 0


def _cmd_signal(args: argparse.Namespace) -> int:
    """Pharmacovigilance disproportionality / signal detection (spec 023)."""
    from cannavec_science.disproportionality import (
        DisproportionalityError, disproportionality, render_disproportionality,
    )
    try:
        result = disproportionality(
            args.drug_event, args.drug_other,
            args.other_event, args.other_other,
        )
    except DisproportionalityError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(render_disproportionality(result))
    return 0


def _cmd_affinity(args: argparse.Namespace) -> int:
    """Cheng-Prusoff IC50→Ki binding-affinity conversion (spec 024)."""
    from cannavec_science.binding import (
        BindingError, binding_affinity, render_binding,
    )
    try:
        result = binding_affinity(
            args.ic50, args.ligand, args.kd,
            unit=getattr(args, "unit", "nM"),
            mode=getattr(args, "mode", "radioligand"),
        )
    except BindingError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(render_binding(result))
    return 0


def _cmd_meta(args: argparse.Namespace) -> int:
    """Pool per-study effect sizes into a meta-analysis (spec 011).

    Reads a JSON spec ``{"measure": ..., "studies": [...]}``. Each study
    is a binary 2×2 table (``events_t/n_t/events_c/n_c``), a continuous
    arm pair (``mean_t/sd_t/n_t/mean_c/sd_c/n_c``), or a precomputed
    generic effect (``yi/vi``). Every study MUST carry a primary-source
    identifier (§I); a study without one refuses with a non-zero exit.
    """
    from cannavec_science.meta_analysis import (
        MetaAnalysisError,
        effects_from_records,
        egger_test,
        leave_one_out,
        meta_analyze,
        render_egger,
        render_leave_one_out,
        render_markdown,
        render_subgroups,
        render_trim_fill,
        subgroup_analysis,
        trim_and_fill,
        proportion_meta_analyze,
        render_proportion,
        meta_regression,
        render_meta_regression,
        hksj_interval,
        render_hksj,
    )

    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[error] cannot read meta spec {args.spec!r}: {exc}", file=sys.stderr)
        return 2

    measure = (getattr(args, "measure", None) or spec.get("measure") or "generic")
    confidence = float(getattr(args, "confidence", 0.95) or 0.95)

    # Single-arm proportion meta-analysis (spec 019): a structurally different
    # surface — pooled rates carry no comparator — handled before the
    # comparative OR/RR/MD/SMD pipeline.
    if str(measure).strip().upper() in ("PFT", "PROP", "PROPORTION"):
        try:
            prop_effects = effects_from_records(
                spec.get("studies", []), measure="PFT")
            presult = proportion_meta_analyze(prop_effects, confidence=confidence)
        except KeyError as exc:
            print(f"[error] study missing required field: {exc}", file=sys.stderr)
            return 2
        except MetaAnalysisError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        p_egger = None
        if getattr(args, "diagnostics", False):
            try:
                p_egger = egger_test(prop_effects)
            except MetaAnalysisError:
                p_egger = None
        if getattr(args, "json", False):
            payload = presult.to_dict()
            if getattr(args, "diagnostics", False):
                payload["egger"] = (
                    p_egger.to_dict() if p_egger is not None
                    else {"note": "Egger's test requires at least 3 studies"}
                )
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(render_proportion(presult))
            if p_egger is not None:
                print("")
                print(render_egger(p_egger))
        return 0

    try:
        effects = effects_from_records(spec.get("studies", []), measure=measure)
        result = meta_analyze(
            effects,
            measure=(None if str(measure).lower() == "generic" else measure),
            confidence=confidence,
        )
    except KeyError as exc:
        print(f"[error] study missing required field: {exc}", file=sys.stderr)
        return 2
    except MetaAnalysisError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    # Optional robustness diagnostics: Egger + leave-one-out (spec 012),
    # trim-and-fill + subgroup analysis (spec 014).
    measure_arg = None if str(measure).lower() == "generic" else measure
    egger = loo = trimfill = subgroups = None
    if getattr(args, "diagnostics", False):
        try:
            loo = leave_one_out(effects, measure=measure_arg, confidence=confidence)
        except MetaAnalysisError:
            loo = None
        try:
            egger = egger_test(effects)
        except MetaAnalysisError:
            egger = None
        try:
            trimfill = trim_and_fill(effects, measure=measure_arg, confidence=confidence)
        except MetaAnalysisError:
            trimfill = None
        if any(e.subgroup for e in effects):
            try:
                subgroups = subgroup_analysis(
                    effects, measure=measure_arg, confidence=confidence)
            except MetaAnalysisError:
                subgroups = None

    # Hartung-Knapp-Sidik-Jonkman interval for the pooled estimate (spec 021).
    # --knha doubles as "use Hartung-Knapp throughout" — for the pool here and
    # for the meta-regression slope below.
    hksj = None
    if getattr(args, "knha", False):
        try:
            hksj = hksj_interval(result)
        except MetaAnalysisError:
            hksj = None

    # Meta-regression on a continuous moderator (spec 020). Each study record
    # must carry a numeric field named by --moderator-key.
    metareg = None
    mod_key = getattr(args, "moderator_key", None)
    if mod_key:
        records = spec.get("studies", [])
        try:
            mod_vals = [float(r[mod_key]) for r in records]
        except (KeyError, TypeError, ValueError):
            print(f"[error] meta-regression: every study needs a numeric "
                  f"{mod_key!r} field", file=sys.stderr)
            return 2
        try:
            metareg = meta_regression(
                effects, mod_vals, moderator_name=mod_key,
                confidence=confidence, knha=getattr(args, "knha", False))
        except MetaAnalysisError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2

    # Absolute effects & NNT (spec 015). CLI --baseline-risk overrides any
    # spec {"baseline": {...}} block. Ratio measures only — a continuous
    # mean difference has no risk difference and refuses with a non-zero exit.
    abs_effect = None
    spec_baseline = spec.get("baseline") if isinstance(spec.get("baseline"), dict) else {}
    baseline_risk = getattr(args, "baseline_risk", None)
    if baseline_risk is None and spec_baseline.get("risk") is not None:
        baseline_risk = float(spec_baseline["risk"])
    if baseline_risk is not None:
        from cannavec_science.absolute_effects import (
            AbsoluteEffectError,
            RiskProvenance,
            absolute_from_meta,
            render_markdown as render_absolute,
        )
        prov = RiskProvenance(
            label=(getattr(args, "baseline_source", None) or spec_baseline.get("label")
                   or "assumed baseline risk (unsourced)"),
            pmid=(getattr(args, "baseline_pmid", None) or spec_baseline.get("pmid")),
            doi=spec_baseline.get("doi"),
            nct=spec_baseline.get("nct"),
            url=spec_baseline.get("url"),
        )
        outcome = (getattr(args, "outcome", None) or spec_baseline.get("outcome")
                   or spec.get("outcome") or "the outcome")
        desirable = bool(getattr(args, "outcome_desirable", False)
                         or spec_baseline.get("outcome_desirable", False))
        try:
            abs_effect = absolute_from_meta(
                result, acr=baseline_risk, outcome=outcome,
                outcome_desirable=desirable, acr_provenance=prov,
                model=getattr(args, "absolute_model", "random"),
            )
        except AbsoluteEffectError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2

    # GRADE certainty rating (spec 016) — completes the SoF table. Uses the
    # --diagnostics Egger result for the publication-bias domain when present.
    certainty = None
    if getattr(args, "certainty", False):
        from cannavec_science.grade_profile import (
            certainty_from_meta,
            render_certainty,
        )
        certainty = certainty_from_meta(
            result,
            evidence_base=getattr(args, "evidence_base", "rct"),
            risk_of_bias=getattr(args, "risk_of_bias", "not-serious"),
            indirectness=getattr(args, "indirectness", "not-serious"),
            egger=egger,
            # One control rate, two GRADE uses: absolute effect + OIS
            # imprecision (spec 018).
            baseline_risk=baseline_risk,
            pooling_sd=getattr(args, "pooling_sd", None),
        )

    if getattr(args, "json", False):
        payload = result.to_dict()
        if getattr(args, "diagnostics", False):
            payload["egger"] = (
                egger.to_dict() if egger is not None
                else {"note": "Egger's test requires at least 3 studies"}
            )
            payload["leave_one_out"] = (
                [r.to_dict() for r in loo] if loo is not None
                else {"note": "leave-one-out requires at least 2 studies"}
            )
            payload["trim_and_fill"] = (
                trimfill.to_dict() if trimfill is not None
                else {"note": "trim-and-fill requires at least 3 studies"}
            )
            if subgroups is not None:
                payload["subgroup_analysis"] = subgroups.to_dict()
        if certainty is not None:
            payload["certainty"] = certainty.to_dict()
        if abs_effect is not None:
            payload["absolute_effect"] = abs_effect.to_dict()
        if hksj is not None:
            payload["hksj"] = hksj.to_dict()
        if metareg is not None:
            payload["meta_regression"] = metareg.to_dict()
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(render_markdown(result))
        if egger is not None:
            print("")
            print(render_egger(egger))
        if loo is not None:
            print("")
            print(render_leave_one_out(loo, log_scale=result.log_scale))
        if trimfill is not None:
            print("")
            print(render_trim_fill(trimfill))
        if subgroups is not None:
            print("")
            print(render_subgroups(subgroups))
        if certainty is not None:
            print("")
            print(render_certainty(certainty))
        if abs_effect is not None:
            print("")
            print(render_absolute(abs_effect))
        if hksj is not None:
            print("")
            print(render_hksj(hksj))
        if metareg is not None:
            print("")
            print(render_meta_regression(metareg))
    return 0


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
    # v0.2 scaffolders (spec 002 US2 + US6)
    a.add_argument("--pico", action="store_true",
                   help="Emit deterministic PICO frame for the brief.")
    a.add_argument("--power-calc", action="store_true",
                   help="Emit sample-size estimates per cited claim.")
    a.add_argument("--grade-profile", action="store_true",
                   help="Emit a GRADE evidence-profile table.")
    a.add_argument("--grade-profile-format", choices=["markdown", "csv"],
                   default="markdown",
                   help="GRADE table rendering format.")
    a.add_argument("--protocol-skeleton", action="store_true",
                   help="Emit a 9-section IRB protocol skeleton.")
    a.add_argument("--regulatory-feasibility",
                   choices=["us", "eu", "ca", "uk"],
                   default=None,
                   help="Emit a regulatory-feasibility advisory.")
    a.add_argument("--sof", default=None, metavar="FILE",
                   help=("Weave a GRADE Summary-of-Findings section into the "
                         "brief from a JSON sidecar of pooled outcomes "
                         "(certainty + relative + absolute effect + NNT). See "
                         "cannavec_science.sof for the sidecar shape (spec 017)."))
    # Weave in the live frontier (Constitution §IX). Off by default so the
    # brief stays offline + deterministic; when set, fan out to live lanes
    # and append a clearly-tagged, provisional, never-promoted section.
    a.add_argument("--augment-live", action="store_true",
                   help="Append clearly-tagged live-discovery hits to the brief.")
    a.add_argument("--augment-sources", default="pubmed,ctgov",
                   help="Comma-separated live lanes for --augment-live.")
    a.add_argument("--augment-max", type=int, default=5,
                   help="Max live findings per lane for --augment-live.")
    a.add_argument("--since", default=None,
                   help="Earliest date (YYYY-MM-DD) for --augment-live lanes.")
    a.set_defaults(func=_cmd_answer)

    # discover
    d = sub.add_parser(
        "discover",
        help=(
            "Live multi-source fan-out across primary scientific sources: "
            "pubmed, chembl, ctgov (default) plus optional cannabis-primary "
            "widening: pubchem, pharmgkb, rcsb, opentargets, gwas, bindingdb, "
            "v0.2 preprint lanes biorxiv, medrxiv, v0.5 europepmc, and v0.6 "
            "openalex."
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
            "pharmgkb, rcsb, opentargets, gwas, bindingdb, biorxiv, medrxiv, "
            "europepmc, openalex."
        ),
    )
    d.add_argument(
        "--include-europepmc", action="store_true",
        help=(
            "Spec 005 US6 — opt-in addition of the Europe PMC lane to "
            "whatever --sources is set (complement to PubMed for "
            "European-indexed and PMC full-text literature)."
        ),
    )
    d.add_argument(
        "--include-openalex", action="store_true",
        help=(
            "Spec 006 US6 — opt-in addition of the OpenAlex lane "
            "(open scholarly citation graph; PubMed + preprints + "
            "conference proceedings + open citation network)."
        ),
    )
    d.add_argument(
        "--parallel",
        type=int,
        default=1,
        help=(
            "Thread-pool size for concurrent per-source fan-out "
            "(default 1, serial; recommended <=4 for NCBI etiquette). "
            "Result ordering is deterministic regardless of completion "
            "order, so identical --parallel runs produce identical output."
        ),
    )
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_discover)

    # verify (v0.3: now accepts all five Constitution §I shapes)
    v = sub.add_parser(
        "verify",
        help=(
            "Spot-check a single primary-source identifier (PMID, DOI, "
            "NCT, ChEMBL, or UniProt accession)."
        ),
    )
    v.add_argument("identifier")
    v.add_argument("--no-citation-network", action="store_true",
                   help="Skip the forward-citation network probe (PMIDs).")
    v.add_argument("--json", action="store_true",
                   help="Emit verification result as JSON.")
    v.set_defaults(func=_cmd_verify)

    # rigor
    r = sub.add_parser(
        "rigor",
        help=(
            "Run the seven phytochemistry rigor detectors + six "
            "reporting-rigor detectors (CONSORT / PRISMA / STROBE / "
            "ROB-2 / ROBINS-I / AMSTAR-2) + the 16 banned-pattern "
            "detectors on arbitrary text."
        ),
    )
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

    # registries (spec 003 US8 / FR-008)
    rg = sub.add_parser(
        "registries",
        help=(
            "List every curated registry's row count, entries, and "
            "last-verified date. Industry-expert discoverability."
        ),
    )
    rg.add_argument(
        "--registry",
        default="all",
        help=(
            "Registry to inventory: 'all' (default) or one of "
            "major_cannabinoids, minor_cannabinoids, terpenes, "
            "interactions, adverse_events, populations, "
            "contraindications, pharmacogenomics, ecbome, "
            "analytical_chemistry, cultivation_science, "
            "pharmacokinetics, use_disorder, hyperemesis_syndrome, "
            "ecbome_inhibitors, biosynthesis."
        ),
    )
    rg.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown).",
    )
    rg.set_defaults(func=_cmd_registries)

    # source-health
    sh = sub.add_parser("source-health",
                        help="Probe per-source liveness.")
    sh.add_argument("--sources", default="pubmed,chembl,ctgov")
    sh.add_argument("--json", action="store_true",
                    help="Emit structured JSON instead of Markdown.")
    sh.set_defaults(func=_cmd_source_health)

    # freshness (spec 002 US5)
    fr = sub.add_parser(
        "freshness",
        help=(
            "Probe registry watch_pmids for retractions / EOCs / stale "
            "verification dates. Offline by default (local retraction "
            "registry only); --network enables PubMed verification."
        ),
    )
    fr.add_argument(
        "--registry",
        default="all",
        help=(
            "Registry to probe: 'all' (default) or one of "
            "major_cannabinoids, minor_cannabinoids, terpenes, "
            "interactions, adverse_events, populations, "
            "contraindications, pharmacogenomics."
        ),
    )
    fr.add_argument("--parallel", type=int, default=1,
                    help="Thread-pool size for parallel probes.")
    fr.add_argument("--network", action="store_true",
                    help="Enable live PubMed verification (slower).")
    fr.add_argument("--json", action="store_true")
    fr.set_defaults(func=_cmd_freshness)

    # meta (spec 011 — quantitative evidence synthesis)
    m = sub.add_parser(
        "meta",
        help=(
            "Pool per-study effect sizes into a fixed-effect + DerSimonian-"
            "Laird random-effects meta-analysis with heterogeneity (Q, I², "
            "τ²) and a GRADE inconsistency verdict — comparative (OR/RR/MD/SMD) "
            "or single-arm rates (--measure prop, Freeman-Tukey). "
            "Deterministic, stdlib-only."
        ),
    )
    m.add_argument(
        "spec",
        help=(
            'JSON file: {"measure": "OR|RR|MD|SMD|prop|generic", "studies": '
            '[...]}. Each study carries a primary-source identifier (pmid/doi/'
            "nct/chembl/uniprot/url) per §I and either a 2×2 table, continuous "
            "arm summaries, a single-arm {events, n} rate (prop), or "
            "precomputed yi/vi."
        ),
    )
    m.add_argument(
        "--measure", default=None,
        help=("Override the spec's measure: OR | RR | MD | SMD | prop | "
              "generic. 'prop' pools single-arm rates (Freeman-Tukey)."),
    )
    m.add_argument("--confidence", type=float, default=0.95,
                   help="Confidence level for CIs (default 0.95).")
    m.add_argument("--diagnostics", action="store_true",
                   help=("Append robustness diagnostics (spec 012): Egger's "
                         "small-study-effects test and a leave-one-out "
                         "sensitivity analysis."))
    m.add_argument("--moderator-key", default=None,
                   help=("Meta-regression (spec 020): the numeric study-record "
                         "field to regress the effect on (e.g. dose, year, "
                         "baseline severity). Reports slope, R², and residual "
                         "heterogeneity."))
    m.add_argument("--knha", action="store_true",
                   help=("Use Hartung-Knapp throughout (recommended for few "
                         "studies): a modified-HKSJ CI for the pooled estimate "
                         "(spec 021) and the Knapp-Hartung t-test for the "
                         "meta-regression slope (spec 020)."))
    # Absolute effects & NNT (spec 015) — ratio measures only.
    m.add_argument("--baseline-risk", type=float, default=None,
                   help=("Assumed comparator (control) risk in (0,1). When set "
                         "for an OR/RR pool, append the GRADE Summary-of-"
                         "Findings absolute effect + NNT. May also be given in "
                         'the spec under {"baseline": {"risk": ...}}.'))
    m.add_argument("--outcome", default=None,
                   help="Outcome label for the absolute-effect block.")
    m.add_argument("--outcome-desirable", action="store_true",
                   help=("Treat the outcome as desirable (response/remission) "
                         "so a risk increase is a benefit. Default: undesirable "
                         "(event/relapse), so a risk reduction is the benefit."))
    m.add_argument("--baseline-source", default=None,
                   help="Provenance label for the assumed comparator risk (§I).")
    m.add_argument("--baseline-pmid", default=None,
                   help="Anchor the assumed comparator risk to a PMID (§I).")
    m.add_argument("--absolute-model", choices=["random", "fixed"],
                   default="random",
                   help="Pooled estimate used for the absolute effect.")
    # GRADE certainty rating (spec 016) — completes the SoF table.
    m.add_argument("--certainty", action="store_true",
                   help=("Rate the certainty of the pooled evidence (GRADE "
                         "⊕ rating). Inconsistency, imprecision and (with "
                         "--diagnostics) publication bias are computed; risk "
                         "of bias and indirectness are reviewer inputs."))
    m.add_argument("--evidence-base", choices=["rct", "observational"],
                   default="rct",
                   help="Starting certainty: RCT body → High, observational → Low.")
    m.add_argument("--pooling-sd", type=float, default=None,
                   help=("Pooling SD for an MD pool, used only to size the "
                         "GRADE Optimal Information Size imprecision criterion "
                         "(spec 018). RR/OR pools use --baseline-risk; an SMD "
                         "pool needs neither."))
    m.add_argument("--risk-of-bias",
                   choices=["not-serious", "serious", "very-serious"],
                   default="not-serious",
                   help="Reviewer-assessed GRADE risk-of-bias domain.")
    m.add_argument("--indirectness",
                   choices=["not-serious", "serious", "very-serious"],
                   default="not-serious",
                   help="Reviewer-assessed GRADE indirectness domain.")
    m.add_argument("--json", action="store_true",
                   help="Emit structured JSON instead of Markdown.")
    m.set_defaults(func=_cmd_meta)

    # fragility (spec 022 — single-trial robustness)
    fg = sub.add_parser(
        "fragility",
        help=(
            "Fragility Index of one 2×2 trial: the minimum number of "
            "non-event→event flips in the fewer-event arm that turns a "
            "significant result (two-sided Fisher's exact) non-significant. "
            "Deterministic, stdlib-only."
        ),
    )
    fg.add_argument("--events-t", type=int, required=True,
                    help="Events in the treatment arm.")
    fg.add_argument("--n-t", type=int, required=True,
                    help="Treatment arm size.")
    fg.add_argument("--events-c", type=int, required=True,
                    help="Events in the control arm.")
    fg.add_argument("--n-c", type=int, required=True,
                    help="Control arm size.")
    fg.add_argument("--alpha", type=float, default=0.05,
                    help="Significance threshold (default 0.05).")
    fg.add_argument("--json", action="store_true",
                    help="Emit structured JSON instead of Markdown.")
    fg.set_defaults(func=_cmd_fragility)

    # signal (spec 023 — pharmacovigilance disproportionality)
    sg = sub.add_parser(
        "signal",
        help=(
            "Pharmacovigilance disproportionality for a drug-event pair: PRR + "
            "ROR (with CIs) and the MHRA/Evans signal criterion, from a 2×2 of "
            "spontaneous-report counts. Hypothesis-generating, not causal. "
            "Deterministic, stdlib-only."
        ),
    )
    sg.add_argument("--drug-event", type=int, required=True,
                    help="a: reports with this drug AND this event.")
    sg.add_argument("--drug-other", type=int, required=True,
                    help="b: reports with this drug AND other events.")
    sg.add_argument("--other-event", type=int, required=True,
                    help="c: reports with other drugs AND this event.")
    sg.add_argument("--other-other", type=int, required=True,
                    help="d: reports with other drugs AND other events.")
    sg.add_argument("--json", action="store_true",
                    help="Emit structured JSON instead of Markdown.")
    sg.set_defaults(func=_cmd_signal)

    # affinity (spec 024 — Cheng-Prusoff IC50 → Ki)
    af = sub.add_parser(
        "affinity",
        help=(
            "Cheng-Prusoff IC50 → Ki conversion: turn an assay-dependent IC50 "
            "into an assay-independent Ki + pKi so receptor affinities from "
            "different papers compare. Deterministic, stdlib-only."
        ),
    )
    af.add_argument("--ic50", type=float, required=True,
                    help="Measured IC50 (same unit as --ligand and --kd).")
    af.add_argument("--ligand", type=float, required=True,
                    help="Radioligand [L] (radioligand mode) or substrate [S] "
                         "(enzyme mode).")
    af.add_argument("--kd", type=float, required=True,
                    help="Radioligand Kd (radioligand mode) or Km (enzyme mode).")
    af.add_argument("--unit", default="nM",
                    help="Concentration unit: M / mM / uM / nM / pM (default nM).")
    af.add_argument("--mode", default="radioligand",
                    choices=["radioligand", "enzyme"],
                    help="Competitive binding (radioligand) or enzyme inhibition.")
    af.add_argument("--json", action="store_true",
                    help="Emit structured JSON instead of Markdown.")
    af.set_defaults(func=_cmd_affinity)

    # freshness-report
    fr2 = sub.add_parser(
        "freshness-report",
        help="Curator-facing freshness report (alias of freshness with date filter).",
    )
    fr2.add_argument("--registry", default="all")
    fr2.add_argument("--since", default=None,
                     help="Filter rows whose last_verified changed since this date.")
    fr2.add_argument("--parallel", type=int, default=1)
    fr2.add_argument("--network", action="store_true")
    fr2.add_argument("--json", action="store_true")
    fr2.set_defaults(func=_cmd_freshness_report)

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
