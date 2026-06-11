"""Route captured live-retrieval gaps into the mc-knowledge-base research backlog.

Reads the operator improve-queue — the gaps the flywheel logged as the KB was
used, both the identifier tier (:mod:`cannavec_science.source_audit`) and the
chunk tier (:mod:`cannavec_science.chunk_audit`) — aggregates recurring gaps
(``occurrences`` = a real user-demand signal), maps each to one of the KB's 11
``cannabis/`` chapters / FAQ clusters, and writes, under the KB repo:

  ``cannabis/logs/live-gap/<area>.json``   — machine log, the repo's gap-audit
                                             schema + live fields (gitignored,
                                             like the other machine logs)
  ``RESEARCH_BACKLOG.live.md``             — a deterministic, regenerable backlog

It honours the KB repo's **Agent Boundary Rule**: it never authors a clinical
claim and never changes a grade. Every gap that needs a sourced clinical claim is
classified ``deep_research`` (the sourced-writing path); grade inflation is only
*flagged for downgrade review*. It **never** touches the hand-curated
``RESEARCH_BACKLOG.md``. Deterministic and offline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from cannavec_science import source_audit

__all__ = ["LiveGap", "RouteResult", "route_gaps", "default_kb_root", "area_for"]

# ── KB taxonomy (mirrors cannabis/logs/gap-audit/gen_backlog.py) ─────────────

AREA_LABEL = {
    "01-plant-botanical": "1. Plant & Botanical Identity",
    "02-cultivation-agronomy": "2. Cultivation & Agronomy",
    "03-phytochemistry": "3. Phytochemistry",
    "04-pharmacology-mechanisms": "4. Pharmacology & Mechanisms",
    "05-medical-therapeutic": "5. Medical & Therapeutic Use",
    "06-evidence-clinical": "6. Evidence & Clinical Validation",
    "07-products-formulations": "7. Products & Formulations",
    "08-hardware-accessories": "8. Hardware & Accessories",
    "09-regulation-law": "9. Regulation, Law & Compliance",
    "10-culture-history-industry": "10. Culture, History & Industry",
    "11-industry-actors-media": "11. Industry Actors, Institutions & Media",
    "news": "News / Signal Feed",
    "faq-clinical": "FAQ — Conditions & Safety",
    "faq-access": "FAQ — Prescriptions, Eligibility, Costs, Clinics",
    "faq-legal-products": "FAQ — Legal, Products, NHS, Irradiation",
    "unclassified": "Unclassified — needs triage",
}
CLINICAL = {"04-pharmacology-mechanisms", "05-medical-therapeutic",
            "06-evidence-clinical", "faq-clinical"}
EFFORT = {"missing_topic": "L", "thin_or_stub": "M", "quality_defect": "S",
          "missing_sources": "S", "structural_noncompliance": "S",
          "missing_faq_answer": "M", "outdated": "S", "broken_link": "S"}
SRC = {
    "04-pharmacology-mechanisms": "PubMed, ChEMBL, IUPHAR/BPS, DailyMed",
    "05-medical-therapeutic": "PubMed, ClinicalTrials.gov, Cochrane, NICE/BPNA guidance",
    "06-evidence-clinical": "PubMed (SRs/RCTs), ClinicalTrials.gov, Cochrane",
    "faq-clinical": "NHS, NICE, MHRA, PubMed, society guidance (BPNA, RCOG)",
    "faq-access": "NHS England, MHRA, clinic pricing, CQC",
    "faq-legal-products": "GOV.UK, Home Office, MHRA, DVLA, ACMD",
    "09-regulation-law": "GOV.UK, EU/MHRA, Home Office, registers, CPIC",
    "03-phytochemistry": "PubMed, ChEMBL, primary phytochemistry literature",
    "news": "Crossref, primary journals, GOV.UK, MHRA (verify before publishing)",
}

# 10 FAQ clusters → 3 backlog buckets (gen_backlog uses 3).
_FAQ_CLUSTER_AREA = {
    "cannabis_and_conditions": "faq-clinical",
    "safety_side_effects_and_risks": "faq-clinical",
    "costs_and_access": "faq-access",
    "eligibility_and_medical_records": "faq-access",
    "cannabis_clinics": "faq-access",
    "prescriptions_and_medication": "faq-access",
    "nhs_and_public_health": "faq-access",
    "legal_and_regulatory_issues": "faq-legal-products",
    "cannabis_products": "faq-legal-products",
    "irradiated_cannabis": "faq-legal-products",
}
_CHAPTER_NUM_AREA = {
    "1": "01-plant-botanical", "2": "02-cultivation-agronomy", "3": "03-phytochemistry",
    "4": "04-pharmacology-mechanisms", "5": "05-medical-therapeutic",
    "6": "06-evidence-clinical", "7": "07-products-formulations",
    "8": "08-hardware-accessories", "9": "09-regulation-law",
    "10": "10-culture-history-industry", "11": "11-industry-actors-media",
}

# Keyword → area fallback (ordered: first match wins). Used when no repo file
# resolves the doc — e.g. a missing-topic coverage gap. Deliberately small.
_KEYWORD_AREA: "list[tuple[re.Pattern, str]]" = [
    (re.compile(r"\b(price|cost|afford|clinic|eligib|prescri|refer|nhs access|"
                r"medical record|how to (get|access))\b", re.I), "faq-access"),
    (re.compile(r"\b(legal|schedul\w*|law|regulat\w*|licen[sc]e|import|export|"
                r"home office|irradiat\w*|driving|dvla)\b", re.I), "faq-legal-products"),
    (re.compile(r"\b(receptor|cb1|cb2|cyp\w*|pharmacokinetic|metabolis\w*|"
                r"mechanism|binding|agonist|antagonist|signal\w*)\b", re.I),
     "04-pharmacology-mechanisms"),
    (re.compile(r"\b(trial|rct|systematic review|meta-analys\w*|evidence|grade|"
                r"cochrane|efficacy data)\b", re.I), "06-evidence-clinical"),
    (re.compile(r"\b(treat\w*|therap\w*|indication|condition|seizure|epilep\w*|"
                r"pain|anxiety|ptsd|nausea|spasticit\w*|cancer|sleep|migraine|"
                r"symptom)\b", re.I), "faq-clinical"),
    (re.compile(r"\b(terpene|flavonoid|cannabinoid chemistr\w*|biosynthes\w*|"
                r"phytochem\w*|chemovar|chemotype)\b", re.I), "03-phytochemistry"),
    (re.compile(r"\b(cultivat\w*|grow\w*|agronom\w*|gacp|gmp|harvest|soil|"
                r"nutrient)\b", re.I), "02-cultivation-agronomy"),
    (re.compile(r"\b(vape|vaporiser|vaporizer|hardware|device|inhaler|cartridge)\b",
                re.I), "08-hardware-accessories"),
    (re.compile(r"\b(product|formulation|oil|tincture|edible|flower|extract|"
                r"sku)\b", re.I), "07-products-formulations"),
    (re.compile(r"\b(strain|cultivar|botanical|taxonom\w*|genetics?)\b", re.I),
     "01-plant-botanical"),
]

# A gap surfaced by ≥ this many user queries is real demand → bump priority one band.
DEMAND_BOOST_THRESHOLD = 3
_SEV_ORDER = ["low", "medium", "high"]
_PRIO_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def default_kb_root() -> Path:
    """KB repo root: ``$CANNAVEC_KB_ROOT`` if set, else ``~/mc-knowledge-base``."""
    import os
    env = os.environ.get("CANNAVEC_KB_ROOT", "").strip()
    return Path(env) if env else Path.home() / "mc-knowledge-base"


def _area_from_path(rel: str) -> Optional[str]:
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    for i, seg in enumerate(parts):
        if seg == "cannabis-faq" and i + 1 < len(parts):
            return _FAQ_CLUSTER_AREA.get(parts[i + 1])
        if seg == "cannabis" and i + 1 < len(parts):
            nxt = parts[i + 1]
            if nxt == "news":
                return "news"
            m = re.match(r"\s*(\d+)\.", nxt)
            if m:
                return _CHAPTER_NUM_AREA.get(m.group(1))
    return None


def _resolve_doc_area(doc_id: str, kb_root: Optional[Path]) -> Optional[str]:
    """Precise area from the actual repo file ``<doc_id>.md`` (the doc_id is the
    canonicalId == filename stem). None when the file does not exist (a coverage
    gap) or no kb_root is available."""
    if not doc_id or kb_root is None:
        return None
    stem = Path(doc_id).name
    if stem.endswith(".md"):
        stem = stem[:-3]
    for base in ("cannabis", "cannabis-faq"):
        root = kb_root / base
        if not root.is_dir():
            continue
        for hit in root.rglob(f"{stem}.md"):
            area = _area_from_path(str(hit.relative_to(kb_root)))
            if area:
                return area
    return None


def area_for(doc_id: str, query: str, *, kb_root: Optional[Path] = None) -> str:
    """Map a gap to a KB area: prefer the resolved repo file; else keyword-match
    the query; else ``unclassified`` (still logged — never silently dropped)."""
    resolved = _resolve_doc_area(doc_id, kb_root)
    if resolved:
        return resolved
    text = f"{doc_id} {query}"
    for pat, area in _KEYWORD_AREA:
        if pat.search(text):
            return area
    return "unclassified"


# ── gap model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LiveGap:
    area: str
    title: str
    kind: str
    location: str
    observation: str
    classification: str          # deep_research | small_fix
    severity: str                # high | medium | low
    proposed_action: str
    dimension: str               # retrieval|citation|accuracy|completeness|source
    queries: tuple               # the user queries that surfaced it
    occurrences: int
    route: str
    priority: Optional[str] = None   # P0..P3, assigned after demand boost (deep_research only)

    def to_dict(self) -> dict:
        return {
            "title": self.title, "kind": self.kind, "location": self.location,
            "observation": self.observation, "classification": self.classification,
            "severity": self.severity, "proposedAction": self.proposed_action,
            "mechanical": False,                  # always human-reviewed (source-verified)
            "dimension": self.dimension, "queries": list(self.queries),
            "occurrences": self.occurrences, "route": self.route,
            "priority": self.priority,
        }


# Map a raw flywheel issue → (kind, classification, base_severity, action, title).
# Conservative: anything needing a sourced clinical claim is deep_research; a
# verified-identifier correction or a metadata flag is small_fix.
def _shape_chunk(dimension: str, verdict: str, area: str, detail: str,
                 action: str) -> "tuple[str, str, str]":
    """Return (kind, classification, base_severity) for a chunk issue. Covers both
    the v1 chunk_audit verdicts and the rigorous chunk_eval verdicts."""
    clinical = area in CLINICAL
    # ── v1 chunk_audit ──
    if verdict == "thin_recall":
        return "missing_topic", "deep_research", ("high" if clinical else "medium")
    if verdict == "weak_relevance":
        return "quality_defect", "deep_research", "medium"
    if verdict == "false_citation":
        return "missing_sources", "small_fix", "high"
    if verdict == "uncited_claim":
        return "missing_sources", "deep_research", ("high" if clinical else "medium")
    if verdict == "contradiction":
        return "quality_defect", "deep_research", "high"
    if verdict == "unverified":
        return "quality_defect", "deep_research", "medium"
    if verdict == "thin_stub":
        return "thin_or_stub", "deep_research", ("medium" if clinical else "low")
    if verdict == "grade_inflation":
        return "quality_defect", "small_fix", "high"
    # ── rigorous chunk_eval: misleading (most severe) ──
    if verdict in ("corpus_contradiction", "rigor_violation", "banned_misleading",
                   "wording_overclaim", "reporting_gap", "coherence_conflict"):
        return "quality_defect", "deep_research", ("high" if clinical else "medium")
    # ── outdated ──
    if verdict in ("stale", "superseded"):
        return "outdated", "deep_research", ("high" if clinical else "medium")
    if verdict == "retracted_citation":
        return "missing_sources", "small_fix", "high"
    # ── weakly_cited ──
    if verdict in ("fabricated_citation", "misattributed_citation"):
        return "missing_sources", "small_fix", "high"
    if verdict == "under_cited":
        return "missing_sources", "deep_research", ("high" if clinical else "medium")
    # ── incomplete ──
    if verdict == "missing_evidence":
        return "missing_sources", "deep_research", "medium"
    return "quality_defect", "deep_research", "medium"


def _boost(severity: str, occurrences: int) -> str:
    if occurrences >= DEMAND_BOOST_THRESHOLD:
        i = min(_SEV_ORDER.index(severity) + 1, len(_SEV_ORDER) - 1)
        return _SEV_ORDER[i]
    return severity


def _priority(classification: str, severity: str, area: str) -> Optional[str]:
    if classification != "deep_research":
        return None
    if severity == "high":
        return "P0" if area in CLINICAL else "P1"
    if severity == "medium":
        return "P2"
    return "P3"


# ── queue → aggregated gaps ──────────────────────────────────────────────────

@dataclass
class _Agg:
    dimension: str
    verdict: str
    doc_id: str
    location: str
    detail: str
    action: str
    queries: set = field(default_factory=set)
    count: int = 0


def _iter_lines(path: Path) -> "Iterable[dict]":
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            yield obj


def _collect(path: Path) -> "dict[tuple, _Agg]":
    """Aggregate every queue line into dedup'd gaps with occurrence counts."""
    aggs: "dict[tuple, _Agg]" = {}

    def bump(key, *, dimension, verdict, doc_id, location, detail, action, query):
        a = aggs.get(key)
        if a is None:
            a = _Agg(dimension=dimension, verdict=verdict, doc_id=doc_id,
                     location=location, detail=detail, action=action)
            aggs[key] = a
        a.count += 1
        if query:
            a.queries.add(query)

    for obj in _iter_lines(path):
        query = str(obj.get("query", "") or "")
        # chunk tier
        for ci in obj.get("chunk_issues", []) or []:
            if not isinstance(ci, dict):
                continue
            verdict = str(ci.get("verdict", "") or "")
            dim = str(ci.get("dimension", "") or "")
            doc_id = str(ci.get("doc_id", "") or "")
            ck = str(ci.get("chunk_key", "") or "")
            loc = ck or doc_id or f"query:{query}"
            key = ("chunk", dim, verdict, loc)
            bump(key, dimension=dim, verdict=verdict, doc_id=doc_id, location=loc,
                 detail=str(ci.get("detail", "") or ""),
                 action=str(ci.get("recommended_action", "") or ""), query=query)
        # identifier tier — false sources the KB returned
        for f in obj.get("false_sources", []) or []:
            ident = str(f.get("identifier", "")).strip() if isinstance(f, dict) else str(f)
            if not ident:
                continue
            reason = str(f.get("reason", "") or "") if isinstance(f, dict) else ""
            key = ("source-false", ident)
            bump(key, dimension="source", verdict="false_source", doc_id="",
                 location=ident, detail=f"KB returned {ident} — {reason}",
                 action="remove/replace this source in the chunk(s) that cite it",
                 query=query)
        # identifier tier — primary sources the KB missed
        for m in obj.get("missing_sources", []) or []:
            ident = str(m).strip()
            if not ident:
                continue
            key = ("source-missing", ident)
            bump(key, dimension="source", verdict="missing_source", doc_id="",
                 location=ident,
                 detail=f"engine discovery found {ident}; the KB did not return it",
                 action="add this verified primary source to the relevant chunk/topic",
                 query=query)
    return aggs


def _agg_to_gap(a: _Agg, *, kb_root: Optional[Path]) -> LiveGap:
    primary_query = sorted(a.queries)[0] if a.queries else ""
    area = area_for(a.doc_id, primary_query, kb_root=kb_root)
    if a.dimension == "source":
        if a.verdict == "false_source":
            kind, classification, base_sev = "missing_sources", "small_fix", "high"
            title = f"False source the KB returned: {a.location}"
        else:
            kind, classification, base_sev = "missing_sources", "small_fix", "medium"
            title = f"Missing primary source the KB lacked: {a.location}"
    else:
        kind, classification, base_sev = _shape_chunk(
            a.dimension, a.verdict, area, a.detail, a.action)
        loc = a.location if a.location else "(query-level)"
        title = f"{a.verdict.replace('_', ' ').title()} — {loc}"
    severity = _boost(base_sev, a.count)
    priority = _priority(classification, severity, area)
    return LiveGap(
        area=area, title=title, kind=kind, location=a.location,
        observation=a.detail, classification=classification, severity=severity,
        proposed_action=a.action, dimension=a.dimension,
        queries=tuple(sorted(a.queries)), occurrences=a.count, route="",
        priority=priority,
    )


# ── result + render ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RouteResult:
    gaps: tuple
    by_area: dict
    counts: dict
    files_written: tuple = ()
    backlog_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "by_area": {k: len(v) for k, v in self.by_area.items()},
            "files_written": list(self.files_written),
            "backlog_path": self.backlog_path,
            "gaps": [g.to_dict() | {"area": g.area} for g in self.gaps],
        }


def _sort_key(g: LiveGap):
    p = _PRIO_ORDER.get(g.priority or "", 9)
    return (p, g.area, -g.occurrences, g.title)


def _src(area: str) -> str:
    return SRC.get(area, "PubMed, primary literature, authoritative guidance bodies")


def render_backlog_md(gaps: "list[LiveGap]", *, generated: str) -> str:
    deep = [g for g in gaps if g.classification == "deep_research"]
    small = [g for g in gaps if g.classification == "small_fix"]
    pcount = {p: sum(1 for g in deep if g.priority == p) for p in ("P0", "P1", "P2", "P3")}
    L: "list[str]" = []
    w = L.append
    w("# Cannabis KB — Live-Retrieval Gap Backlog")
    w("")
    w(f"> **Generated:** {generated} · **Source:** the Cannavec live-retrieval flywheel")
    w("> (gaps surfaced by real user questions, deterministically verified). This file is")
    w("> **machine-generated and regenerable** — do not hand-edit; it is regenerated from")
    w("> `cannabis/logs/live-gap/*.json` on every `route-gaps` run. It is **separate from**")
    w("> the hand-curated `RESEARCH_BACKLOG.md`, which it never touches.")
    w("")
    w("Per `AGENT_PROTOCOL.md`, nothing here is written to Pinecone/Sanity directly and no")
    w("clinical fact is invented: every gap needing a sourced clinical claim is")
    w("`deep_research` for the normal review path; grade changes are flagged for human")
    w("sign-off only. `occurrences` is how many distinct user queries surfaced the gap —")
    w("higher means more real demand.")
    w("")
    w("---")
    w("")
    w("## At a glance")
    w("")
    w(f"- **{len(gaps)} live gaps** — {len(deep)} deep-research · {len(small)} corrections/quick-fixes.")
    w(f"- Deep-research by priority: **P0 = {pcount['P0']}**, P1 = {pcount['P1']}, "
      f"P2 = {pcount['P2']}, P3 = {pcount['P3']}.")
    w("- Effort key: **S** ≈ <2h · **M** ≈ ½–1 day · **L** ≈ 1–3 days of sourced writing.")
    w("")
    w("---")
    w("")
    # corrections / quick fixes
    w("## Corrections & quick fixes (verified identifiers / metadata flags)")
    w("")
    if small:
        w("| Area | Item | Kind | Occurrences | Action |")
        w("|---|---|---|---|---|")
        for g in sorted(small, key=_sort_key):
            w(f"| {AREA_LABEL.get(g.area, g.area)} | {g.title} | {g.kind} | "
              f"{g.occurrences} | {g.proposed_action[:160]} |")
    else:
        w("_None logged._")
    w("")
    w("---")
    w("")
    w("## Deep-research backlog (prioritized)")
    w("")
    w("Each item is a sourced-writing / review task tied to the chunk that surfaced it.")
    w("`→` is the deliverable; **Sources** lists the databases/authorities to mine.")
    w("")
    TIER = {
        "P0": "### P0 — Clinical, urgent (high-severity in clinical/pharmacology/evidence/FAQ areas)",
        "P1": "### P1 — High-severity (non-clinical areas)",
        "P2": "### P2 — Medium priority",
        "P3": "### P3 — Lower priority / completeness",
    }
    for prio in ("P0", "P1", "P2", "P3"):
        items = sorted((g for g in deep if g.priority == prio), key=_sort_key)
        if not items:
            continue
        w(TIER[prio] + f"  ·  {len(items)} items")
        w("")
        cur = None
        for g in items:
            if g.area != cur:
                cur = g.area
                w(f"**{AREA_LABEL.get(cur, cur)}**")
                w("")
            eff = EFFORT.get(g.kind, "M")
            loc = f" · `{g.location}`" if g.location else ""
            demand = f" · {g.occurrences}× user demand" if g.occurrences > 1 else ""
            w(f"- **{g.title}** _(effort {eff}{demand})_{loc}")
            if g.observation:
                w(f"  - Gap: {g.observation}")
            if g.proposed_action:
                w(f"  - → {g.proposed_action}")
            if g.queries:
                w(f"  - Asked as: {'; '.join(g.queries[:3])}")
            w(f"  - Sources: {_src(g.area)}")
        w("")
    return "\n".join(L) + "\n"


# ── public entry point ───────────────────────────────────────────────────────

def _utcnow_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def route_gaps(
    *,
    queue_path: "str | Path | None" = None,
    store_dir: "str | Path | None" = None,
    kb_root: "str | Path | None" = None,
    write: bool = True,
    generated: Optional[str] = None,
) -> RouteResult:
    """Fold the operator improve-queue into the KB research backlog.

    ``write=False`` (dry run / review) computes the full plan but touches nothing.
    Writing never modifies the hand-curated ``RESEARCH_BACKLOG.md``.
    """
    qpath = Path(queue_path) if queue_path else source_audit.improve_queue_path(store_dir)
    root = Path(kb_root) if kb_root else default_kb_root()
    gen = generated or _utcnow_date()

    aggs = _collect(qpath)
    gaps = [_agg_to_gap(a, kb_root=root if root.is_dir() else None)
            for a in aggs.values()]
    gaps.sort(key=_sort_key)

    by_area: "dict[str, list]" = {}
    for g in gaps:
        by_area.setdefault(g.area, []).append(g)

    counts = {
        "total": len(gaps),
        "deep_research": sum(1 for g in gaps if g.classification == "deep_research"),
        "small_fix": sum(1 for g in gaps if g.classification == "small_fix"),
        "P0": sum(1 for g in gaps if g.priority == "P0"),
        "P1": sum(1 for g in gaps if g.priority == "P1"),
        "P2": sum(1 for g in gaps if g.priority == "P2"),
        "P3": sum(1 for g in gaps if g.priority == "P3"),
    }

    files_written: "list[str]" = []
    backlog_path: Optional[str] = None
    if write and gaps:
        log_dir = root / "cannabis" / "logs" / "live-gap"
        log_dir.mkdir(parents=True, exist_ok=True)
        for area, items in sorted(by_area.items()):
            payload = {
                "area": area, "areaLabel": AREA_LABEL.get(area, area),
                "generated": gen, "source": "live-retrieval-flywheel",
                "gaps": [g.to_dict() for g in sorted(items, key=_sort_key)],
            }
            fp = log_dir / f"{area}.json"
            fp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
            files_written.append(str(fp))
        bp = root / "RESEARCH_BACKLOG.live.md"
        bp.write_text(render_backlog_md(gaps, generated=gen), encoding="utf-8")
        backlog_path = str(bp)

    return RouteResult(
        gaps=tuple(gaps), by_area=by_area, counts=counts,
        files_written=tuple(files_written), backlog_path=backlog_path,
    )
