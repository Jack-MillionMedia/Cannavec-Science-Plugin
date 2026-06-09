"""Cannavec Science CLI.

Unified entry point: ``python -m cannavec_science <subcommand>``.

The deterministic grounding-and-verification backbone for an AI reasoner —
it retrieves, verifies, grades, and rigor-checks; the model does the reasoning
over the verified evidence (Constitution M1 / §II).

Subcommands:

- ``answer "<question>"`` — assemble a citation-bound brief; curated registry
  content is labelled offline reference, not the answer itself.
- ``discover "<query>"`` — live multi-source primary-source fan-out
  (PubMed + ChEMBL + ClinicalTrials.gov, plus opt-in lanes).
- ``verify <PMID|DOI|NCT|ChEMBL|UniProt>`` — spot-check one identifier:
  real? not retracted? (the anti-hallucination gate).
- ``rigor "<text>"`` — run the phytochemistry + reporting-rigor +
  banned-pattern detectors on arbitrary text.
- ``bibliography <answer.json>`` — re-render a saved answer's
  bibliography in BibTeX / RIS / CSL-JSON.
- ``registries`` — inventory the curated reference registries.
- ``kb-audit <path>`` — operator-only, read-only credibility audit of a
  knowledge-base directory (citation integrity + claim support + GRADE
  honesty); triages each file into READY / IMPROVE / PASS. Not a slash command.

Every subcommand returns a non-zero exit code on refusal / error.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Sequence

from cannavec_science import live as _live_lanes
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
        retrieval=getattr(args, "retrieval", "fallback"),
    )

    if getattr(args, "augment_live", False):
        _augment_with_live(a, args)

    if args.json:
        print(json.dumps(a.to_dict(), indent=2, default=str))
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


def _augment_with_live(a, args) -> None:
    """Flag-gated live-evidence weave — the blended brief (Constitution §IX).

    Re-uses the prompt as a discovery query, fans out to the requested live
    lanes, and weaves the result onto the curated Answer via the shared
    :func:`cannavec_science.live.weave_live_findings`: reranked, retraction-
    checked, provenance-tagged findings PLUS the cross-source synthesis verdict
    (STRONG / MIXED / WEAK), so the CLI brief carries the same one-answer blend
    as the web surface. Network only; a refusal or any lane failure degrades
    gracefully — the curated brief still stands. Never promotes a live row.
    """
    from types import SimpleNamespace
    from cannavec_science import live as _live
    from cannavec_science.discover_guard import DiscoverRefused, preflight
    from cannavec_science.synthesis import synthesize

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
    per_source_rows: dict = {}
    for src in sources:
        runner = _DISCOVERER_REGISTRY.get(src)
        if runner is None:
            continue
        try:
            rows = runner(q)
        except Exception as exc:  # noqa: BLE001 — degrade; curated answer stands
            _log.warning("answer --augment-live lane %s failed: %s", src, exc)
            continue
        per_source_rows[src] = [r.to_dict() for r in rows[:per_lane]]
    if not per_source_rows:
        return
    result = {
        "query": a.prompt,
        "sources": per_source_rows,
        "synthesis": synthesize(a.prompt, per_source_rows).to_dict(),
    }
    _live.weave_live_findings(a, result, query=a.prompt)


# Default model for the opt-in LLM rerank step. Sonnet 4.6 is accuracy-
# equivalent to Opus for a bounded rerank against an explicit rubric, at ~half
# the cost; the confidence short-circuit already keeps calls rare. Override per
# run with ``--rerank-model``.
_DEFAULT_RERANK_MODEL = "claude-sonnet-4-6"


def _maybe_rank(args: argparse.Namespace, out_payload: dict):
    """Rank the fanned-out candidates across sources, or return ``None``.

    Deterministic ranking is on by default (free, offline, additive — it never
    removes the per-source view). ``--rerank-llm`` adds the optional LLM lift,
    which fires only on a genuine top-of-list near-tie (the cost short-circuit)
    and degrades silently to the deterministic floor if the model, API key, or
    network is unavailable — the per-source results always stand.
    """
    if not getattr(args, "rank", True):
        return None
    from cannavec_science.ranker import (
        candidates_from_discovery,
        rank_candidates,
    )

    cands = candidates_from_discovery(out_payload)
    if not cands:
        return None

    backend = None
    if getattr(args, "rerank_llm", False):
        from cannavec_science.ranker_llm import LLMReranker

        backend = LLMReranker(
            model=getattr(args, "rerank_model", _DEFAULT_RERANK_MODEL)
        )

    return rank_candidates(
        args.query,
        cands,
        backend=backend,
        top_k=max(1, int(getattr(args, "max", 10) or 10)),
    )


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

    # Reliability backfill: a failed/empty PubMed lane is backed up by Europe
    # PMC (different host, same MEDLINE). Same policy as live.run_discovery so
    # the CLI and web-API paths behave identically. Fires only when PubMed
    # produced nothing and Europe PMC was not already requested with rows.
    if _live_lanes.needs_pubmed_fallback(out_payload["sources"]):
        fb_key = _live_lanes.PUBMED_FALLBACK_SOURCE
        _key, fb_payload = _run_one(fb_key)
        if isinstance(fb_payload, list) and fb_payload:
            out_payload["sources"][fb_key] = fb_payload
            out_payload["pubmed_fallback"] = fb_key

    # Operator hint (stderr — never pollutes the JSON / Markdown artifact):
    # a key-less NCBI request is on the shared 3 req/s limit and is the root
    # cause of the transient 500s / read-timeouts. Fire only when PubMed
    # actually came back empty, so it is actionable, not noise.
    from cannavec_science._http import ncbi_api_key as _ncbi_api_key

    _pm = out_payload["sources"].get("pubmed")
    _pubmed_troubled = isinstance(_pm, dict) or (isinstance(_pm, list) and not _pm)
    if _pubmed_troubled and _ncbi_api_key() is None:
        print(
            "[hint] PubMed returned no rows. Set NCBI_API_KEY to raise the "
            "E-utilities rate limit (3→10 req/s) and cut the transient "
            "500s / read-timeouts that empty the lane.",
            file=sys.stderr,
        )

    # Write-through to the verified-source flywheel (M2): cache every verified,
    # non-retracted live row before any cache-fallback injection, so the offline
    # KB grows from real fetches only. Degrades silently.
    from cannavec_science import live_cache as _live_cache

    try:
        _live_cache.record_discovery(args.query, out_payload["sources"])
    except Exception:  # noqa: BLE001 — a cache write never breaks discovery
        pass

    # Build synthesis block keyed by the synthesis _SOURCE_KEYS — the
    # same short keys the CLI uses, so cross-source clustering picks up
    # every LIVE row that came back (cache-fallback rows are added after and
    # deliberately excluded from the fresh-convergence verdict).
    synth_rows: dict = {}
    for src, val in out_payload["sources"].items():
        if isinstance(val, list):
            synth_rows[src] = val
    block = synthesize(args.query, synth_rows)

    # Read-fallback (offline resilience): when the entire live fan-out came back
    # empty — every upstream down — serve previously-verified sources from the
    # offline cache, retraction RE-CHECKED on read (§VIII). Kept under a
    # distinct ``live_cache`` key + flag so the reader knows these are not a
    # fresh fetch, and they never manufacture a fresh-convergence verdict.
    live_total = sum(len(v) for v in synth_rows.values())
    if live_total == 0:
        try:
            cached_rows = _live_cache.fetch_for_query(
                args.query, max_results=args.max
            )
        except Exception:  # noqa: BLE001
            cached_rows = []
        if cached_rows:
            out_payload["sources"]["live_cache"] = cached_rows
            out_payload["served_from_cache"] = True

    rank_result = _maybe_rank(args, out_payload)

    if args.json:
        out_payload["synthesis"] = block.to_dict()
        if rank_result is not None:
            out_payload["ranking"] = rank_result.to_dict()
        print(json.dumps(out_payload, indent=2, default=str))
        return 0

    if rank_result is not None:
        from cannavec_science.ranker import render_markdown as _render_rank_md

        print(_render_rank_md(rank_result))

    for src in sorted(out_payload["sources"]):
        val = out_payload["sources"][src]
        n = len(val) if isinstance(val, list) else 0
        print(f"\n## Live {src} ({n})")
        print("")
        if isinstance(val, dict) and "error" in val:
            print(f"_(live source unavailable: {val['error']})_")
            continue
        for r in val[: args.max]:
            # Display headline: prefer each lane's native structured id (a
            # pathway/ontology row reads better as R-HSA-… / GO:… / CHEBI:… /
            # EFO:… than as its supplementary PMID). Ranking, cross-source
            # dedup, and citation still resolve PMID-first elsewhere.
            ident = (
                r.get("chebi_id")
                or r.get("go_id")
                or r.get("pathway_id")
                or r.get("efo_id")
                or r.get("pmid")
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
                or r.get("chebi_name")
                or r.get("go_name")
                or r.get("display_name")
                or r.get("label")
                or ""
            )
            print(f"- `{ident}` ({yr}) {title}".rstrip())
    if out_payload.get("pubmed_fallback"):
        print(
            f"\n_PubMed was unavailable; Europe PMC backfilled the same MEDLINE "
            f"literature from a different host._"
        )
    if out_payload.get("served_from_cache"):
        n_cached = len(out_payload["sources"].get("live_cache", []))
        print(
            f"\n_All live upstreams were unavailable. Served {n_cached} "
            f"previously-verified source(s) from the offline cache "
            f"(retraction re-checked; not a fresh fetch)._"
        )
    print("\n## Cross-source synthesis")
    print("")
    print(render_markdown(block))
    return 0


# The CLI ``discover`` registry derives from the ONE canonical lane→runner map
# in ``live.ALL_LANE_RUNNERS`` — the single source of truth shared with the
# web-API blended path. (These were two hand-maintained copies of ~25
# near-identical wrappers that drifted; that duplication is now gone.) The
# canonical runners take ``(query, since, n)``; the CLI calls a runner with an
# argparse / ``SimpleNamespace`` object, so adapt the signature here. Kept as a
# module-level dict so tests can ``patch.dict`` it to inject offline fakes.
def _lane_from_args(runner: "Callable") -> "Callable":
    def _run(args):
        return runner(args.query, getattr(args, "since", None), args.max)
    return _run


_DISCOVERER_REGISTRY = {
    src: _lane_from_args(runner)
    for src, runner in _live_lanes.ALL_LANE_RUNNERS.items()
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
    from cannavec_science.pubmed_verify import verify_doi, VerificationVerdict
    from cannavec_science.retraction import is_retracted

    result = verify_doi(ident)
    rec = is_retracted(doi=ident)

    # Map the typed verdict to a CLI verdict + exit code, failing CLOSED —
    # identical discipline to _verify_pmid_render (Constitution §I / M2: a
    # citation is trustworthy only once the upstream record is confirmed).
    # verify_doi ALWAYS returns a (truthy) VerificationResult, so a bare
    # `if not result` guard is dead code — the verdict MUST be inspected, or a
    # NOT_FOUND/NETWORK_ERROR DOI renders a false PASS. Crossref never surfaces
    # RETRACTED, so a retraction can only come from the local registry (`rec`),
    # which is definitive even when the upstream fetch failed.
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
            "kind": "DOI",
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
        print(json.dumps(out, indent=2, default=str))
        return exit_code

    print(f"## Identifier verification — DOI {ident}")
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
        print("- **Status:** UNVERIFIED — could not reach Crossref (network error)")
        for note in result.notes:
            print(f"  - {note}")
        print("- **Verdict:** UNVERIFIED")
        return exit_code
    if verdict == VerificationVerdict.NOT_FOUND:
        print("- **Status:** FAIL — DOI not found in Crossref")
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
    return exit_code


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
    from cannavec_science.retraction import scan_text_for_retracted_pmids

    text = args.text
    report = run_rigor_checks(text)
    banned = detect_banned_patterns(text)
    # §VIII — a pasted citation that matches the retraction registry is a
    # rigor violation on every surface (mirrors /api/rigor and compose-time).
    retracted = list(scan_text_for_retracted_pmids(text))

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
    print(f"- **Retracted citations:** {len(retracted)}")
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
    if retracted:
        print("### Retracted / flagged citations (§VIII — do not cite)")
        for h in retracted:
            rec = h.record
            print(f"- **{h.matched_kind.upper()} {h.matched_identifier}** "
                  f"({rec.status.value}): {rec.title}")
            if rec.reason_summary:
                print(f"  - Why: {rec.reason_summary}")
        print("")

    if n == 0 and not retracted:
        print("**Clean.** No violations.")
        return 0
    return 1


def _cmd_kb_audit(args: argparse.Namespace) -> int:
    from cannavec_science.kb_audit.run import audit_path
    from cannavec_science.kb_audit.report import render
    from cannavec_science.kb_audit.scope import DEFAULT_INCLUDE

    include = tuple(args.include) if getattr(args, "include", None) else DEFAULT_INCLUDE
    exclude = tuple(args.exclude) if getattr(args, "exclude", None) else ()
    verdicts = audit_path(args.path, include=include, exclude=exclude)
    markdown, js = render(verdicts)
    body = js if args.json else markdown
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"[kb-audit] report written to {args.out}", file=sys.stderr)
    else:
        print(body)
    return 1 if any(v.status == "FAIL" for v in verdicts) else 0


def _cmd_bibliography(args: argparse.Namespace) -> int:
    from cannavec_science.bibliography import render, BibliographyEntry, _entry_from_citation
    from cannavec_science.answer import Answer, Citation
    from cannavec_science.evidence import EvidenceLevel

    try:
        payload = json.loads(Path(args.answer_json).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[error] cannot read answer JSON {args.answer_json!r}: {exc}",
              file=sys.stderr)
        return 2
    try:
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
    except (KeyError, TypeError, ValueError) as exc:
        print(f"[error] malformed citation in {args.answer_json!r}: {exc}",
              file=sys.stderr)
        return 2
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


_CITE_FORMATS = ("bibtex", "ris", "csljson")
_CITE_EXT = {"bibtex": "bib", "ris": "ris", "csljson": "json"}
_CITE_HEADER = {"bibtex": "BibTeX", "ris": "RIS", "csljson": "CSL-JSON"}


def _cmd_cite(args: argparse.Namespace) -> int:
    """Spec 033 — citation-lossless reference export (the surface behind
    /cv:cite).

    Composes the offline curated Answer and emits its verified citations as a
    reference export — all three formats by default, or a single ``--format``.
    Every format is independently gated by ``export.render_citation_export``; if
    ANY requested format is not citation-lossless (or the Answer is a refusal /
    has no graded evidence), the command emits nothing and exits non-zero — it
    never fabricates or partially-emits a reference set (§I / §XI / M5).
    """
    from cannavec_science.answer import compose_answer
    from cannavec_science.export import render_citation_export

    fmts = [args.format] if getattr(args, "format", None) else list(_CITE_FORMATS)
    answer = compose_answer(args.question)

    rendered: dict[str, str] = {}
    for fmt in fmts:
        body = render_citation_export(answer, fmt)
        if body is None:
            if answer.is_refusal:
                reason = "refusal"
            elif not answer.claims:
                reason = "no verified citations"
            else:
                reason = f"not citation-lossless ({fmt})"
            print(f"[cite] no citable answer: {reason}", file=sys.stderr)
            return 2
        rendered[fmt] = body

    if getattr(args, "out", None):
        written: list[str] = []
        for fmt in fmts:
            path = f"{args.out}.{_CITE_EXT[fmt]}"
            Path(path).write_text(rendered[fmt], encoding="utf-8")
            written.append(path)
        print(f"[cite] {len(written)} format(s) → {', '.join(written)}",
              file=sys.stderr)
        return 0

    if len(fmts) == 1:
        print(rendered[fmts[0]], end="")
    else:
        blocks = [f"=== {_CITE_HEADER[f]} ===\n{rendered[f]}" for f in fmts]
        print("\n".join(blocks), end="")
    return 0


def _pdf_slug(question: str) -> str:
    """A safe, short filename stem from a question (for the default --out)."""
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    return ("cannavec-" + (slug[:48].rstrip("-") or "brief"))


def _cmd_pdf(args: argparse.Namespace) -> int:
    """Render the composed answer as a polished, citation-lossless evidence brief
    (the surface behind /cv:pdf).

    Composes the offline curated Answer and renders it to a self-contained HTML
    evidence brief (clinical-journal style), then to PDF via the best available
    backend (headless Chrome → reportlab → HTML-only). Every primary-source
    identifier and GRADE label is preserved and none is inflated — the §XI gate is
    enforced in ``pdf_export`` and the command refuses (non-zero) rather than emit
    a lossy or inflated transform. Refusal and uncurated-indication answers render
    an honest brief (no evidence fabricated); only a gate failure or write error
    is non-zero.
    """
    from cannavec_science.answer import compose_answer
    from cannavec_science import pdf_export

    answer = compose_answer(args.question)

    # /cv:pdf packs the brief with on-topic, conservatively-graded live evidence
    # by DEFAULT (spec 036 Task 7) — the curated core, widened with the live
    # primary-source frontier via the ``BRIEF_SOURCES`` literature-breadth set,
    # gated on-topic and clamped to provisional grades (≤ Low, never curated).
    # ``--no-live`` opts out entirely (offline / curated-only).
    #
    # CRITICAL: the live tier must NEVER crash OR refuse the PDF. Two guards:
    #   1. a network failure / unreachable lane degrades silently inside
    #      ``augment_answer``; we also wrap it so no exception can propagate.
    #   2. the §XI render gate (enforced in ``export_pdf``) is a HARD guarantee
    #      for the curated surface and must not be weakened — but a provisional
    #      live finding must never be able to make the whole brief refuse. So we
    #      pre-check the augmented render: if weaving the live tier would trip the
    #      faithfulness gate, we fall back to the curated-only answer (which always
    #      renders) rather than refuse. The curated brief always stands.
    if not getattr(args, "no_live", False) and not answer.is_refusal:
        from cannavec_science import live as _live
        try:
            augmented = compose_answer(args.question)
            _live.augment_answer(augmented, sources=_live.BRIEF_SOURCES)
            if augmented.live_findings:
                pdf_export.assert_render_faithful(
                    augmented, pdf_export.render_html(augmented)
                )
                answer = augmented
            elif augmented.live_sources_searched:
                # Lanes WERE reachable but nothing on-topic survived the gate —
                # say so in the brief (transparency), not just on stderr.
                answer.live_retrieval_note = (
                    "Live retrieval found no additional on-topic primary "
                    "sources for this question."
                )
            else:
                # No lane was reachable (offline / firewall): ``augment_answer``
                # degrades silently rather than raising, so distinguish "offline"
                # from "nothing on-topic" by whether any lane returned at all.
                answer.live_retrieval_note = (
                    "Live literature retrieval was unavailable — showing curated "
                    "evidence only. Re-run on an open network to include the live "
                    "primary-source frontier."
                )
        except pdf_export.FaithfulnessError as exc:
            print(f"[pdf] live tier dropped (curated-only): render gate — {exc}",
                  file=sys.stderr)
            answer.live_retrieval_note = (
                "Live evidence was retrieved but could not be safely "
                "rendered; showing curated evidence only."
            )
        except Exception as exc:  # noqa: BLE001 — PDF never crashes on live
            print(f"[pdf] live augmentation skipped (curated-only): {exc}",
                  file=sys.stderr)
            answer.live_retrieval_note = (
                "Live literature retrieval was unavailable — showing curated "
                "evidence only. Re-run on an open network to include the live "
                "primary-source frontier."
            )

    out_prefix = args.out or _pdf_slug(args.question)
    try:
        result = pdf_export.export_pdf(
            answer, out_prefix, html_only=getattr(args, "html_only", False)
        )
    except pdf_export.FaithfulnessError as exc:
        print(f"[pdf] refused — render not citation-lossless: {exc}",
              file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"[pdf] write error: {exc}", file=sys.stderr)
        return 2
    print(f"[pdf] {result.summary()}", file=sys.stderr)
    print(result.pdf_path or result.html_path)
    return 0


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
    # Cross-registry BM25 retrieval recovery (Improvement Plan §1). Offline +
    # deterministic; recovers curated rows the brittle keyword detectors miss
    # (e.g. "how does THC impair driving"). ``fallback`` (default) fires only
    # when the detectors produced no claim; ``augment`` makes retrieval the
    # primary path; ``off`` restores pre-§1 detector-only routing.
    a.add_argument("--retrieval", choices=["fallback", "augment", "off"],
                   default="fallback",
                   help=("Curated-row retrieval recovery for thin/no-claim "
                         "answers (default: fallback)."))
    a.set_defaults(func=_cmd_answer)

    # discover
    d = sub.add_parser(
        "discover",
        help=(
            "Live multi-source fan-out across primary scientific sources: "
            "pubmed, chembl, ctgov (default) plus optional cannabis-primary "
            "widening: pubchem, pharmgkb, rcsb, opentargets, gwas, bindingdb, "
            "v0.2 preprint lanes biorxiv, medrxiv, v0.5 europepmc, v0.6 "
            "openalex, and v0.7 chebi (chemical ontology), quickgo (receptor "
            "GO function), reactome (receptor pathways), efo (indication "
            "normalization)."
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
            "europepmc, openalex, chebi, quickgo, reactome, efo."
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
    d.add_argument(
        "--no-rank", action="store_false", dest="rank", default=True,
        help=(
            "Disable the cross-source candidate ranking section (it is on by "
            "default: a free, offline, deterministic re-ordering of the "
            "fanned-out hits by relevance + study design + recency, with "
            "retracted papers sunk to the bottom)."
        ),
    )
    d.add_argument(
        "--rerank-llm", action="store_true", default=False,
        help=(
            "Add the optional LLM rerank lift on top of the deterministic "
            "ranking. Fires only on a genuine top-of-list near-tie (the cost "
            "short-circuit), ranks indices only (never a source of citations), "
            "and degrades to the deterministic order if the model / API key / "
            "network is unavailable. Requires ANTHROPIC_API_KEY."
        ),
    )
    d.add_argument(
        "--rerank-model", default=_DEFAULT_RERANK_MODEL,
        help=(
            f"Model for --rerank-llm (default: {_DEFAULT_RERANK_MODEL}). "
            "Sonnet 4.6 is accuracy-equivalent to Opus for a bounded rerank at "
            "lower cost; pass claude-opus-4-8 for the maximum ceiling."
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

    # cite (spec 033) — citation-lossless reference export behind /cv:cite
    ct = sub.add_parser(
        "cite",
        help=(
            "Export the verified citations behind a composed answer as a "
            "citation-lossless reference set (BibTeX + RIS + CSL-JSON by "
            "default). Refuses to emit anything it cannot preserve losslessly."
        ),
    )
    ct.add_argument("question")
    ct.add_argument(
        "--format", choices=list(_CITE_FORMATS), default=None,
        help="Emit a single format (default: all three).",
    )
    ct.add_argument(
        "--out",
        help="Write one file per format to <PREFIX>.bib/.ris/.json (else stdout).",
    )
    ct.set_defaults(func=_cmd_cite)

    # pdf (spec 034) — polished, citation-lossless evidence brief behind /cv:pdf
    pf = sub.add_parser(
        "pdf",
        help=(
            "Render the composed answer as a polished, citation-lossless PDF "
            "evidence brief (HTML → headless Chrome → reportlab, gracefully "
            "degrading). Refuses to emit anything it cannot preserve losslessly."
        ),
    )
    pf.add_argument("question")
    pf.add_argument(
        "--out",
        help="Output path prefix → <PREFIX>.html (+ <PREFIX>.pdf). "
             "Default: cannavec-<slug> in the current directory.",
    )
    pf.add_argument(
        "--html-only", action="store_true",
        help="Emit only the self-contained HTML (skip PDF rendering).",
    )
    pf.add_argument(
        "--no-live", action="store_true",
        help=("Skip live primary-source augmentation; render the curated-only "
              "brief (offline / deterministic). Default: pack the brief with "
              "on-topic, conservatively-graded live evidence."),
    )
    pf.set_defaults(func=_cmd_pdf)

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

    # kb-audit (spec 032) — read-only operator tool, not a research surface
    ka = sub.add_parser(
        "kb-audit",
        help=("Read-only credibility audit of a knowledge-base directory "
              "(citation integrity + claim support + GRADE honesty). Operator tool."),
    )
    ka.add_argument("path", help="Path to the knowledge-base repo or a subfolder")
    ka.add_argument("--include", action="append", default=None,
                    help=("Path substring to audit (repeatable). Default: the "
                          "science folders 5 (Medical) + 6 (Evidence)."))
    ka.add_argument("--exclude", action="append", default=None,
                    help="Path substring to skip (repeatable).")
    ka.add_argument("--json", action="store_true", help="Emit the corpus verdict as JSON.")
    ka.add_argument("--out", help="Write the report to this file instead of stdout.")
    ka.set_defaults(func=_cmd_kb_audit)

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
