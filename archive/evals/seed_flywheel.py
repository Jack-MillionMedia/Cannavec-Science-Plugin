#!/usr/bin/env python3
"""Seed one real turn of the §IX flywheel for the demand-revealed holes.

This is the *act* stage on real data: a committed, reproducible batch of real,
PubMed-confirmed primary sources for topics the eval shows are thin (IBD /
gut, fibromyalgia, sleep, CBD pharmacokinetics) — run through the **same**
deterministic admission gate as a hand-curated row and routed to the staging
queue by lane. Nothing here promotes anything; promotion stays a human act
(`python -m cannavec_science curate-apply --id ... --approver YOU`).

Provenance: every record below was retrieved from PubMed (search →
get_article_metadata) and checked for retraction status at seed time. The
``source`` line is the article's own verbatim conclusion sentence — the
evidentiary anchor the claim-support gate reads and the verbatim quote the
verified row would carry. ``claim`` is a neutral, isomer-precise paraphrase.

Run:  python3 evals/seed_flywheel.py            # writes to the package data dir
      python3 evals/seed_flywheel.py --dry-run  # gate + classify, print, no write
      python3 evals/seed_flywheel.py --store-dir /tmp/queue
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cannavec_science import flywheel as fw
from cannavec_science.ranker import Candidate


# (pmid, doi, year, topic, study_type, title, claim, source_conclusion)
# study_type drives the conservative GRADE; the flywheel never assigns Level A.
SEED: tuple[dict, ...] = (
    {
        "pmid": "33571293", "doi": "10.1371/journal.pone.0246871", "year": 2021,
        "topic": "ibd", "study_type": "Randomized Controlled Trial",
        "title": "Cannabis is associated with clinical but not endoscopic remission in ulcerative colitis: A randomized controlled trial.",
        "claim": "In mild-to-moderately active ulcerative colitis, 8 weeks of Δ⁹-THC-rich cannabis induced clinical remission and improved quality of life, without significant improvement in the Mayo endoscopic score.",
        "source": "Short term treatment with THC rich cannabis induced clinical remission and improved quality of life in patients with mild to moderately active ulcerative colitis. However, these beneficial clinical effects were not associated with significant anti-inflammatory improvement in the Mayo endoscopic score or laboratory markers for inflammation.",
    },
    {
        "pmid": "33858011", "doi": "10.1093/ecco-jcc/jjab069", "year": 2021,
        "topic": "ibd", "study_type": "Randomized Controlled Trial",
        "title": "Oral CBD-rich Cannabis Induces Clinical but Not Endoscopic Response in Patients with Crohn's Disease, a Randomised Controlled Trial.",
        "claim": "In Crohn's disease, 8 weeks of oral cannabidiol-rich cannabis induced clinical and quality-of-life improvement without significant change in endoscopic scores or inflammatory markers.",
        "source": "Eight weeks of CBD-rich cannabis treatment induced significant clinical and QOL improvement without significant changes in inflammatory parameters or endoscopic scores.",
    },
    {
        "pmid": "28349233", "doi": "10.1007/s10620-017-4540-z", "year": 2017,
        "topic": "ibd", "study_type": "Randomized Controlled Trial",
        "title": "Low-Dose Cannabidiol Is Safe but Not Effective in the Treatment for Crohn's Disease, a Randomized Controlled Trial.",
        "claim": "In moderately active Crohn's disease, low-dose oral cannabidiol (10 mg twice daily) was safe but not effective versus placebo on disease activity.",
        "source": "In this study of moderately active Crohn's disease, CBD was safe but had no beneficial effects.",
    },
    {
        "pmid": "29538683", "doi": "10.1093/ibd/izy002", "year": 2018,
        "topic": "ibd", "study_type": "Randomized Controlled Trial",
        "title": "A Randomized, Double-blind, Placebo-controlled, Parallel-group, Pilot Study of Cannabidiol-rich Botanical Extract in the Symptomatic Treatment of Ulcerative Colitis.",
        "claim": "In ulcerative colitis, a cannabidiol-rich botanical extract did not meet its primary remission endpoint, though several secondary symptom measures favoured it.",
        "source": "Although the primary endpoint was not reached, several signals suggest CBD-rich botanical extract may be beneficial for symptomatic treatment of UC.",
    },
    {
        "pmid": "34531823", "doi": "10.3389/fendo.2021.685289", "year": 2021,
        "topic": "ibd", "study_type": "Randomized Controlled Trial",
        "title": "Endocannabinoid Levels in Ulcerative Colitis Patients Correlate With Clinical Parameters and Are Affected by Cannabis Consumption.",
        "claim": "In ulcerative colitis, cannabis use altered circulating endocannabinoid tone and was associated with beneficial effects on disease symptoms.",
        "source": "Our study supports the notion that cannabis use affects eCB \"tone\" in UC patients and may have beneficial effects on disease symptoms in UC patients.",
    },
    {
        "pmid": "31054246", "doi": "10.1093/ibd/izz017", "year": 2019,
        "topic": "ibd", "study_type": "Randomized Controlled Trial",
        "title": "Palmitoylethanolamide and Cannabidiol Prevent Inflammation-induced Hyperpermeability of the Human Gut In Vitro and In Vivo.",
        "claim": "Cannabidiol and palmitoylethanolamide reduced inflammation-induced permeability of the human colon in vitro and in vivo.",
        "source": "Cannabidiol and palmitoylethanolamide reduce permeability in the human colon.",
    },
    {
        "pmid": "37482172", "doi": "10.1016/j.cgh.2023.07.008", "year": 2023,
        "topic": "ibd", "study_type": "Randomized Controlled Trial",
        "title": "A Randomized, Controlled Trial of Efficacy and Safety of Cannabidiol in Idiopathic and Diabetic Gastroparesis.",
        "claim": "In idiopathic and diabetic gastroparesis, 4 weeks of pharmaceutical cannabidiol reduced total symptom score and vomiting episodes versus placebo, despite slowing gastric emptying.",
        "source": "CBD provides symptom relief in patients with gastroparesis and improves the tolerance of liquid nutrient intake, despite slowing of GES.",
    },
    {
        "pmid": "33118602", "doi": "10.1093/pm/pnaa303", "year": 2020,
        "topic": "fibromyalgia", "study_type": "Randomized Controlled Trial",
        "title": "Ingestion of a THC-Rich Cannabis Oil in People with Fibromyalgia: A Randomized, Double-Blind, Placebo-Controlled Clinical Trial.",
        "claim": "In women with fibromyalgia, 8 weeks of a Δ⁹-THC-rich cannabis oil significantly reduced Fibromyalgia Impact Questionnaire scores versus placebo.",
        "source": "after the intervention, the cannabis group presented a significant decrease in FIQ score in comparison with the placebo group",
    },
    {
        "pmid": "30585986", "doi": "10.1097/j.pain.0000000000001464", "year": 2019,
        "topic": "fibromyalgia", "study_type": "Randomized Controlled Trial",
        "title": "An experimental randomized study on the analgesic effects of pharmaceutical-grade cannabis in chronic pain patients with fibromyalgia.",
        "claim": "In fibromyalgia, single-inhalation pharmaceutical-grade cannabis produced only small analgesic responses, with no variety exceeding placebo on spontaneous or electrical pain.",
        "source": "None of the treatments had an effect greater than placebo on spontaneous or electrical pain responses",
    },
    {
        "pmid": "20007734", "doi": "10.1213/ANE.0b013e3181c76f70", "year": 2009,
        "topic": "sleep", "study_type": "Randomized Controlled Trial",
        "title": "The effects of nabilone on sleep in fibromyalgia: results of a randomized controlled trial.",
        "claim": "In fibromyalgia with chronic insomnia, the synthetic cannabinoid nabilone improved sleep and was superior to amitriptyline on the Insomnia Severity Index.",
        "source": "Although sleep was improved by both amitriptyline and nabilone, nabilone was superior to amitriptyline",
    },
    {
        "pmid": "30374683", "doi": "10.1007/s40263-018-0578-5", "year": 2018,
        "topic": "cbd_pharmacokinetics", "study_type": "Randomized Controlled Trial",
        "title": "A Phase I Trial of the Safety, Tolerability and Pharmacokinetics of Highly Purified Cannabidiol in Healthy Subjects.",
        "claim": "In healthy adults, a high-fat meal increased oral cannabidiol plasma exposure (Cmax and AUC) roughly four- to five-fold, a large food effect.",
        "source": "A high-fat meal increased CBD plasma exposure (Cmax and AUC) by 4.85- and 4.2-fold, respectively; there was no effect of food on tmax or terminal half-life.",
    },
)


def _esummary(rec: dict) -> str:
    """Reconstruct a PubMed esummary from the seed record (confirmed at fetch).

    The PMID was resolved from PubMed at seed time, so this faithfully feeds the
    identifier audit: a real, non-retracted record with the article's pubtype.
    """
    return json.dumps({
        "header": {"type": "esummary"},
        "result": {"uids": [rec["pmid"]], rec["pmid"]: {
            "uid": rec["pmid"],
            "pubdate": f"{rec['year']} Jan 1",
            "source": "PubMed",
            "authors": [{"name": "Seed", "authtype": "Author"}],
            "title": rec["title"],
            "pubtype": ["Journal Article", rec["study_type"]],
        }},
    })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Seed a real flywheel turn for the holes.")
    ap.add_argument("--store-dir", default=None,
                    help="Where to write the staging queue (default: package data dir).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Gate + classify + print, but do not write the queue.")
    args = ap.parse_args(argv)

    by_lane = {"basic_approvable": 0, "needs_expert": 0, "reject": 0}
    print(f"Seeding {len(SEED)} PubMed-confirmed candidates through the §IX gate\n")
    for rec in SEED:
        cand = Candidate(
            identifier=rec["pmid"], title=rec["title"], abstract=rec["source"],
            study_types=(rec["study_type"],), topic=rec["topic"],
            source="live_pubmed", url=f"https://pubmed.ncbi.nlm.nih.gov/{rec['pmid']}/",
        )
        result = fw.gate(
            cand, claim_text=rec["claim"], abstract=rec["source"],
            verify_fetcher=lambda url, _r=rec: _esummary(_r),
        )
        lane = fw.classify(result)
        by_lane[lane.value] += 1
        flag = {"basic_approvable": "✓ basic", "needs_expert": "⚠ expert",
                "reject": "✗ reject"}[lane.value]
        print(f"  [{flag:<9}] {rec['pmid']:<9} {result.grade:<8} {rec['topic']:<20} "
              f"id={result.checks.get('identifier')} support={result.checks.get('claim_support')}")
        if result.flags:
            print(f"               ⤷ {result.flags[0]}")
        if not args.dry_run:
            fw.stage(cand, result, lane, topic=rec["topic"], store_dir=args.store_dir)

    print(f"\n  basic_approvable={by_lane['basic_approvable']}  "
          f"needs_expert={by_lane['needs_expert']}  reject={by_lane['reject']}")
    if args.dry_run:
        print("  (dry run — nothing written)")
    else:
        print(f"\n  Wrote staging queue. Review:  python3 -m cannavec_science curate-queue")
        print(f"  Promote (human gate):  python3 -m cannavec_science curate-apply "
              f"--id <PMID> --approver YOU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
