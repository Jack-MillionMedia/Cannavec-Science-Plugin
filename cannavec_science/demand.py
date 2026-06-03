"""Demand instrumentation — *log the misses, promote what users actually ask.*

The flywheel is only worth turning where there is real demand. This module is
the cheap, deterministic instrument: every answer can record one
:class:`DemandEvent` (the prompt, the topic it routed to, how much curated
coverage it found, and whether that coverage was *thin*). Aggregated, the log
ranks topics by **miss volume** — the holes users keep hitting — which is the
priority queue the flywheel's fan-out reads from.

This is the missing read-time half of Constitution §IX: write-time checking
(the gate) is necessary but blind to *what to gate next*. The demand log tells
the curator where the scarce approval budget pays off.

Stdlib only; the ledger is ``demand_log.jsonl`` via
:mod:`cannavec_science.curation_store`. ``classify_topic`` is a deterministic
keyword router (no model), so the same prompt always books to the same topic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from cannavec_science.curation_store import (
    DEMAND_FILE,
    append_jsonl,
    read_jsonl,
    utcnow,
)

__all__ = [
    "TOPICS",
    "DemandEvent",
    "TopicDemand",
    "classify_topic",
    "topic_covered",
    "topic_query",
    "record_demand",
    "instrument_answer",
    "aggregate",
    "demand_report",
    "priority_topics",
]

# Canonical demand topics. Ordered **most-specific first** so a fibromyalgia
# question books to ``fibromyalgia`` rather than the generic ``pain`` bucket.
# Each entry: (topic, compiled alternation of trigger terms). Extending the
# taxonomy is a one-line addition; the router stays deterministic.
_TOPIC_PATTERNS: tuple[tuple[str, str], ...] = (
    ("fibromyalgia", r"fibromyalg"),
    ("migraine", r"migrain|cluster headache"),
    ("ibd", r"inflammatory bowel|crohn|ulcerative colitis|\bibd\b|colitis"),
    ("epilepsy", r"epileps|seizure|dravet|lennox|gastaut|convuls"),
    ("cbd_pharmacokinetics",
     r"pharmacokinet|bioavailab|\bt[\s-]?max\b|\bc[\s-]?max\b|half[\s-]?life|"
     r"absorption|first[\s-]?pass|\bauc\b|\bpk\b|food effect|metabolite"),
    ("driving", r"driv|impair.*(?:car|vehicle|road)|on[\s-]?road|simulator|"
                r"roadside|\bduid\b|psychomotor"),
    ("terpenes", r"terpen|myrcene|limonene|pinene|linalool|caryophyllene|"
                 r"entourage|humulene|terpinolene"),
    ("sleep", r"\bsleep\b|insomnia|somnolen|sleep quality|sleep latency"),
    ("ptsd_anxiety", r"\bptsd\b|post[\s-]?traumatic|anxiet|panic|social anxiety"),
    ("psychosis", r"psychos|schizophren|first[\s-]?episode psychosis"),
    ("nausea_cinv", r"nausea|vomit|\bcinv\b|chemotherapy[\s-]?induced|hyperemesis|"
                    r"antiemetic"),
    ("drug_interactions",
     r"interaction|\bcyp\d|cytochrome|warfarin|clobazam|tacrolimus|p[\s-]?gp|"
     r"\bddi\b|enzyme induc|enzyme inhib"),
    ("pain", r"\bpain\b|neuropath|analgesi|nocicept|chronic pain|spasticit"),
    ("multiple_sclerosis", r"multiple sclerosis|\bms\b spasticit|nabiximols|sativex"),
    ("appetite_weight", r"appetite|cachexia|weight gain|anorexia|wasting"),
    ("cancer", r"\bcancer\b|tumou?r|oncolog|glioma|antineoplast|palliat"),
    ("cardiovascular", r"cardiovascul|blood pressure|hypertens|arrhythmia|"
                       r"myocard|\bheart\b|tachycard"),
    ("liver", r"\bliver\b|hepat|transaminas|\balt\b|\bast\b|cirrhos"),
    ("immune_autoimmune", r"immune|autoimmun|cytokine|inflammat|rheumatoid|lupus"),
    ("dermatology", r"\bskin\b|dermatit|psorias|eczema|acne|prurit"),
    ("pharmacogenomics", r"pharmacogenom|genotype|polymorphism|\bcyp2c9\b|allele"),
)
_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (topic, re.compile(pat, re.IGNORECASE)) for topic, pat in _TOPIC_PATTERNS
)

TOPICS: tuple[str, ...] = tuple(t for t, _ in _TOPIC_PATTERNS)

UNCLASSIFIED = "unclassified"


def classify_topic(text: str) -> str:
    """Route free text to a canonical demand topic (deterministic).

    Returns the first topic whose trigger terms appear, scanning most-specific
    first, or ``"unclassified"`` if nothing matches. Pure and stdlib — the same
    text always books to the same topic, which keeps the demand ledger stable.
    """
    if not text:
        return UNCLASSIFIED
    for topic, rx in _COMPILED:
        if rx.search(text):
            return topic
    return UNCLASSIFIED


def _topic_pattern(topic: str):
    """The compiled trigger pattern for a topic (or ``None`` if unknown)."""
    for t, rx in _COMPILED:
        if t == topic:
            return rx
    return None


def topic_covered(topic: str, claim_texts) -> bool:
    """Whether any claim text actually addresses ``topic``.

    The sharper miss signal: a fibromyalgia question answered only with generic
    pain-review rows that never mention fibromyalgia is a *topic-specific* miss,
    even though it is not "thin" (it returned claims). Returns ``True`` when the
    topic is unknown or there is no claim text to read (no false misses).
    """
    rx = _topic_pattern(topic)
    blob = " ".join(t for t in claim_texts if t)
    if rx is None or not blob:
        return True
    return bool(rx.search(blob))


# Good primary-source queries per topic — the fan-out target a demand hole maps
# to. Used by the flywheel's demand-driven sweep (``curate-sweep``).
_TOPIC_QUERY: dict[str, str] = {
    "fibromyalgia": "(cannabis OR cannabidiol OR cannabinoid OR nabilone) AND fibromyalgia",
    "migraine": "(cannabis OR cannabidiol OR cannabinoid) AND (migraine OR cluster headache)",
    "ibd": "(cannabidiol OR cannabis OR cannabinoid) AND (inflammatory bowel disease OR Crohn OR ulcerative colitis)",
    "epilepsy": "(cannabidiol OR cannabis) AND (epilepsy OR seizure OR Dravet OR Lennox-Gastaut)",
    "cbd_pharmacokinetics": "cannabidiol AND (pharmacokinetics OR bioavailability OR plasma concentration)",
    "driving": "(cannabis OR tetrahydrocannabinol) AND driving AND (impairment OR psychomotor)",
    "terpenes": "(cannabis terpene OR myrcene OR limonene OR linalool OR caryophyllene) AND (analgesic OR anti-inflammatory OR clinical)",
    "sleep": "(cannabis OR cannabidiol OR cannabinoid OR nabilone) AND (insomnia OR sleep quality)",
    "ptsd_anxiety": "(cannabis OR cannabidiol OR cannabinoid OR nabilone) AND (PTSD OR posttraumatic OR anxiety)",
    "psychosis": "(cannabis OR cannabidiol OR tetrahydrocannabinol) AND (psychosis OR schizophrenia)",
    "nausea_cinv": "(cannabis OR cannabinoid OR nabilone OR dronabinol) AND (nausea OR vomiting OR chemotherapy-induced)",
    "drug_interactions": "(cannabidiol OR cannabis) AND (drug interaction OR CYP OR cytochrome)",
    "pain": "(cannabis OR cannabidiol OR cannabinoid) AND (chronic pain OR neuropathic pain)",
    "multiple_sclerosis": "(cannabis OR nabiximols OR cannabinoid) AND multiple sclerosis AND spasticity",
    "appetite_weight": "(cannabis OR dronabinol OR cannabinoid) AND (appetite OR cachexia OR weight)",
    "cancer": "(cannabis OR cannabidiol OR cannabinoid) AND cancer AND (palliative OR symptom)",
    "cardiovascular": "(cannabis OR cannabidiol OR tetrahydrocannabinol) AND (cardiovascular OR blood pressure)",
    "liver": "(cannabidiol OR cannabis) AND (liver OR hepatotoxicity OR transaminase)",
    "immune_autoimmune": "(cannabis OR cannabidiol OR cannabinoid) AND (autoimmune OR rheumatoid OR inflammation)",
    "dermatology": "(cannabidiol OR cannabis OR cannabinoid) AND (skin OR dermatitis OR psoriasis OR eczema)",
    "pharmacogenomics": "(cannabidiol OR cannabis OR tetrahydrocannabinol) AND (pharmacogenomics OR CYP2C9 OR genotype)",
}


def topic_query(topic: str) -> str:
    """A good primary-source search query for a demand topic.

    Known topics map to a hand-tuned cannabinoid × condition query; an unknown
    (but classified) topic falls back to a generic cannabis query over the topic
    name. This is what the demand-driven sweep fans out on per hole.
    """
    if topic in _TOPIC_QUERY:
        return _TOPIC_QUERY[topic]
    if topic and topic != UNCLASSIFIED:
        return f"(cannabis OR cannabidiol OR cannabinoid) AND {topic.replace('_', ' ')}"
    return "cannabis OR cannabidiol OR cannabinoid"


@dataclass(frozen=True)
class DemandEvent:
    """One instrumented answer: what was asked, and how well we covered it."""

    ts: str
    prompt: str
    topic: str
    n_claims: int
    highest_grade: str | None
    thin: bool                     # zero curated claims, or best grade Unsupported
    refusal: bool
    topic_covered: bool = True     # did any claim actually address the topic?

    @property
    def miss(self) -> bool:
        """A promotable coverage hole: thin, or no claim addressed the topic.

        A refusal is never a miss (we correctly declined). This is the signal
        the flywheel prioritises by — the holes users keep hitting.
        """
        if self.refusal:
            return False
        return self.thin or not self.topic_covered

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "prompt": self.prompt,
            "topic": self.topic,
            "n_claims": self.n_claims,
            "highest_grade": self.highest_grade,
            "thin": self.thin,
            "refusal": self.refusal,
            "topic_covered": self.topic_covered,
            "miss": self.miss,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DemandEvent":
        return cls(
            ts=str(d.get("ts", "")),
            prompt=str(d.get("prompt", "")),
            topic=str(d.get("topic", UNCLASSIFIED)),
            n_claims=int(d.get("n_claims", 0) or 0),
            highest_grade=d.get("highest_grade"),
            thin=bool(d.get("thin", False)),
            refusal=bool(d.get("refusal", False)),
            topic_covered=bool(d.get("topic_covered", True)),
        )


def _is_thin(n_claims: int, highest_grade: str | None, refusal: bool) -> bool:
    """A coverage *miss*: not a refusal, but no real curated answer.

    Mirrors :func:`cannavec_science.live.is_thin` — zero curated claims, or the
    best grade we could muster was Unsupported. A refusal is never a miss (we
    *correctly* declined; that is not a coverage hole).
    """
    if refusal:
        return False
    if n_claims <= 0:
        return True
    if highest_grade is None:
        return True
    return "unsupported" in highest_grade.lower()


def record_demand(
    prompt: str,
    *,
    n_curated_claims: int,
    highest_grade: str | None = None,
    refusal: bool = False,
    thin: bool | None = None,
    topic_covered: bool = True,
    topic: str | None = None,
    store_dir: str | None = None,
) -> DemandEvent:
    """Append one demand event to the ledger and return it.

    ``thin`` is derived from coverage unless explicitly passed. ``topic_covered``
    defaults to ``True`` (no false miss when the caller cannot assess it).
    ``topic`` is routed from ``prompt`` unless explicitly passed. Stdlib
    append-only; safe to call on every answer.
    """
    topic = topic or classify_topic(prompt)
    if thin is None:
        thin = _is_thin(n_curated_claims, highest_grade, refusal)
    event = DemandEvent(
        ts=utcnow(),
        prompt=prompt,
        topic=topic,
        n_claims=int(n_curated_claims),
        highest_grade=highest_grade,
        thin=bool(thin),
        refusal=bool(refusal),
        topic_covered=bool(topic_covered),
    )
    append_jsonl(DEMAND_FILE, event.to_dict(), store_dir)
    return event


def instrument_answer(answer, *, store_dir: str | None = None) -> DemandEvent:
    """Derive and record a :class:`DemandEvent` from a composed ``Answer``.

    Reads the public surface of :class:`cannavec_science.answer.Answer`
    (``prompt``, ``claims``, ``evidence_summary.highest_grade``,
    ``is_refusal``) defensively, so it works against any answer-shaped object
    and never raises into the answer path.
    """
    prompt = str(getattr(answer, "prompt", "") or "")
    claims = getattr(answer, "claims", None) or ()
    n_claims = len(claims)
    refusal = bool(getattr(answer, "is_refusal", False))
    grade = None
    es = getattr(answer, "evidence_summary", None)
    hg = getattr(es, "highest_grade", None)
    if hg is not None:
        grade = getattr(hg, "value", None) or str(hg)
    topic = classify_topic(prompt)
    covered = topic_covered(topic, [getattr(c, "text", "") for c in claims])
    return record_demand(
        prompt,
        n_curated_claims=n_claims,
        highest_grade=grade,
        refusal=refusal,
        topic_covered=covered,
        topic=topic,
        store_dir=store_dir,
    )


@dataclass(frozen=True)
class TopicDemand:
    """Aggregated demand for one topic. ``priority`` drives the flywheel order."""

    topic: str
    asks: int
    misses: int
    thin_rate: float
    last_seen: str

    @property
    def priority(self) -> int:
        """Promotion priority = miss volume (the holes users keep hitting)."""
        return self.misses

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "asks": self.asks,
            "misses": self.misses,
            "thin_rate": round(self.thin_rate, 3),
            "priority": self.priority,
            "last_seen": self.last_seen,
        }


def aggregate(events: list[DemandEvent]) -> list[TopicDemand]:
    """Roll events up per topic, sorted by priority (misses) then ask volume.

    Refusals are counted as asks (real demand) but never as misses (a correct
    decline is not a coverage hole).
    """
    by_topic: dict[str, dict] = {}
    for ev in events:
        slot = by_topic.setdefault(
            ev.topic, {"asks": 0, "misses": 0, "last_seen": ""}
        )
        slot["asks"] += 1
        if ev.miss:
            slot["misses"] += 1
        if ev.ts > slot["last_seen"]:
            slot["last_seen"] = ev.ts
    out = [
        TopicDemand(
            topic=topic,
            asks=slot["asks"],
            misses=slot["misses"],
            thin_rate=(slot["misses"] / slot["asks"]) if slot["asks"] else 0.0,
            last_seen=slot["last_seen"],
        )
        for topic, slot in by_topic.items()
    ]
    out.sort(key=lambda t: (t.priority, t.asks, t.topic), reverse=True)
    return out


def demand_report(store_dir: str | None = None) -> list[TopicDemand]:
    """Aggregate the persisted demand ledger into a ranked topic report."""
    events = [DemandEvent.from_dict(d) for d in read_jsonl(DEMAND_FILE, store_dir)]
    return aggregate(events)


def priority_topics(
    n: int = 5, *, min_misses: int = 1, store_dir: str | None = None
) -> list[str]:
    """The top ``n`` topics by miss volume — the flywheel's fan-out targets.

    Filters out topics with fewer than ``min_misses`` misses and the
    ``"unclassified"`` bucket (not an actionable promotion target).
    """
    report = demand_report(store_dir)
    picks = [
        td.topic
        for td in report
        if td.misses >= min_misses and td.topic != UNCLASSIFIED
    ]
    return picks[:n]
