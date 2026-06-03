#!/usr/bin/env python3
"""Regression proof for the discovery RANKER (Improvement Plan / discovery-quality).

Pins the elite discovery behaviour against a battery of real queries so it can
never silently regress. Fully **offline + deterministic**: it ranks fixed
candidate sets — built from real PMIDs / titles seen in live discovery runs —
through :func:`cannavec_science.ranker.rank_candidates` and asserts the
invariants we built:

  * human trials lead (study-design prior),
  * animal / in-vitro work is demoted to preclinical,
  * cannabinoid synonyms match (THC == dronabinol, CBD == cannabidiol),
  * affix matching (permeability ⊂ hyperpermeability),
  * cross-source dedup collapses the same paper (shared PMID / DOI),
  * recency never beats study design,
  * a retracted paper sinks to the bottom.

No network: the live searchers are not called; the fixtures stand in for what
they return, so this runs in CI as a deterministic gate.

Run:  python3 evals/prove_ranking.py      # exit 0 = every invariant holds
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cannavec_science.ranker import (
    Candidate,
    candidates_from_discovery,
    rank_candidates,
)

_YEAR = 2026


def _C(ident, title, year, study_types=(), retraction="clean", doi=""):
    return Candidate(identifier=ident, title=title, abstract="", year=year,
                     study_types=tuple(study_types), retraction_status=retraction,
                     source="live_pubmed", doi=doi)


def _order(query, cands):
    return [rc.candidate.identifier
            for rc in rank_candidates(query, cands, now_year=_YEAR).ranked]


def _labels(query, cands):
    return {rc.candidate.identifier: rc.signals["design_label"]
            for rc in rank_candidates(query, cands, now_year=_YEAR).ranked}


# ── The battery (each check returns (name, ok, detail)) ────────────────────

def check_gut_permeability_human_first():
    # Real "cannabidiol gut permeability" result: the human RCT must lead and
    # the animal studies must sit below it (affix: permeability ⊂ Hyperpermeability).
    cands = [
        _C("31054246", "Palmitoylethanolamide and Cannabidiol Prevent Inflammation-induced "
           "Hyperpermeability of the Human Gut In Vitro and In Vivo - A Randomized, "
           "Placebo-controlled, Double-blind Controlled Trial", 2019,
           ("Randomized Controlled Trial",)),
        _C("41096585", "Cannabidiol Lipid Nanoparticles Stabilize Gut-Brain-Bone Axis "
           "Integrity in Stressed Rats", 2025),
        _C("39518951", "Cannabidiol in the Gut of Chickens Applied to Different Conditions", 2024),
        _C("41028669", "Effect of cannabidiol injection on intestine microbiome in a mouse model", 2025),
        _C("38928387", "Effects of Cannabinoids on Intestinal Motility, Barrier Permeability, "
           "and Therapeutic Potential in Gastrointestinal Diseases", 2024, ("Review",)),
    ]
    q = "cannabidiol gut permeability"
    order = _order(q, cands)
    labels = _labels(q, cands)
    if order[0] != "31054246":
        return ("gut: human RCT ranks #1", False, f"top={order[0]}")
    for animal in ("41096585", "39518951", "41028669"):
        if labels.get(animal) != "preclinical/animal":
            return ("gut: animal studies demoted", False, f"{animal}={labels.get(animal)}")
        if order.index("31054246") > order.index(animal):
            return ("gut: human RCT above animal", False, f"RCT below {animal}")
    return ("gut: human RCT #1, animal demoted below it", True, f"top={order[0]}")


def check_thc_dronabinol_synonym():
    # "THC" query must surface a "dronabinol" RCT (both → tetrahydrocannabinol).
    cands = [
        _C("D", "Dronabinol for chemotherapy-induced nausea and vomiting", 2007,
           ("Randomized Controlled Trial",)),
        _C("O", "Ondansetron for chemotherapy-induced nausea", 2010,
           ("Randomized Controlled Trial",)),
    ]
    order = _order("thc nausea", cands)
    return ("synonym: 'THC' query ranks a 'dronabinol' RCT first",
            order[0] == "D", f"order={order}")


def check_cbd_cannabidiol_synonym():
    cands = [
        _C("C", "Cannabidiol for drug-resistant seizures", 2017, ("Randomized Controlled Trial",)),
        _C("X", "Aspirin for headache", 2015, ("Randomized Controlled Trial",)),
    ]
    order = _order("cbd seizures", cands)
    return ("synonym: 'CBD' query ranks a 'cannabidiol' title first",
            order[0] == "C", f"order={order}")


def check_affix_permeability():
    # "permeability" must credit a "Hyperpermeability" title (affix match).
    cands = [
        _C("RCT", "Cannabidiol prevents intestinal hyperpermeability: a randomized controlled trial",
           2019, ("Randomized Controlled Trial",)),
        _C("REV", "Cannabidiol pharmacology: a narrative review", 2024, ("Review",)),
    ]
    order = _order("intestinal permeability", cands)
    return ("affix: 'permeability' matches 'hyperpermeability'",
            order[0] == "RCT", f"order={order}")


def check_recency_never_beats_design():
    cands = [
        _C("NEWCASE", "CBD sleep", 2026, ("Case Reports",)),
        _C("OLDSR", "CBD sleep", 2015, ("Systematic Review",)),
    ]
    order = _order("cbd sleep", cands)
    return ("recency: a 2026 case report does not outrank a 2015 systematic review",
            order[0] == "OLDSR", f"order={order}")


def check_retraction_sinks():
    cands = [
        _C("RET", "CBD epilepsy seizures meta-analysis", 2025, ("Meta-Analysis",),
           retraction="retracted"),
        _C("CLEAN", "CBD epilepsy seizures", 2018, ("Randomized Controlled Trial",)),
    ]
    order = _order("cbd epilepsy seizures", cands)
    return ("retraction: a retracted meta-analysis sinks below a clean RCT",
            order[-1] == "RET" and order[0] == "CLEAN", f"order={order}")


def check_cross_source_dedup():
    # The same paper from PubMed + Europe PMC (shared PMID) and a preprint +
    # Europe PMC (shared DOI) each collapse into ONE candidate.
    result = {"sources": {
        "pubmed": [{"pmid": "111", "title": "CBD gut RCT", "provenance": "live_pubmed"},
                   {"pmid": "222", "title": "CBD colitis", "provenance": "live_pubmed"}],
        "europepmc": [{"pmid": "111", "title": "CBD gut RCT (EPMC)", "provenance": "live_europepmc"},
                      {"doi": "10.1/x", "title": "CBD review", "provenance": "live_europepmc"}],
        "biorxiv": [{"doi": "https://doi.org/10.1/X", "title": "CBD review preprint",
                     "provenance": "live_biorxiv"}],
        "ctgov": [{"nct_id": "NCT07", "title": "trial", "provenance": "live_ctgov"}],
    }}
    cands = {c.identifier: c for c in candidates_from_discovery(result)}
    # 6 rows -> 4 unique works (111 merged, 10.1/x merged, 222, NCT07).
    ok = (len(cands) == 4
          and set(cands.get("111").provenances) == {"live_pubmed", "live_europepmc"}
          and "NCT07" in cands)
    return ("dedup: shared PMID + shared DOI collapse across sources",
            ok, f"{len(cands)} candidates from 6 rows")


_CHECKS = [
    check_gut_permeability_human_first,
    check_thc_dronabinol_synonym,
    check_cbd_cannabidiol_synonym,
    check_affix_permeability,
    check_recency_never_beats_design,
    check_retraction_sinks,
    check_cross_source_dedup,
]


def run_checks():
    """Run the battery; return ``[(name, ok, detail), ...]``."""
    out = []
    for fn in _CHECKS:
        try:
            out.append(fn())
        except Exception as exc:  # noqa: BLE001 — a crash is a failure
            out.append((fn.__name__, False, f"{type(exc).__name__}: {exc}"))
    return out


def main(argv=None) -> int:
    print("Discovery ranker regression proof\n" + "=" * 74)
    results = run_checks()
    failed = 0
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            failed += 1
            print(f"         ↳ {detail}")
    print("=" * 74)
    if failed:
        print(f"VERDICT: REGRESSED — {failed}/{len(results)} invariants broken")
        return 1
    print(f"VERDICT: PROVEN — all {len(results)} discovery invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
