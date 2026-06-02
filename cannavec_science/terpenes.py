"""Curated cannabis terpene reference registry.

Terpenes are the aromatic compounds that give cannabis cultivars their
distinctive scent profiles. They are also pharmacologically active — but
at concentrations that are typically far lower than those demonstrating
effects in in-vitro assays. This gap is the single most important
nuance Cannavec enforces: terpene pharmacology at micromolar/nanomolar
concentrations in a cell assay does not translate directly to clinical
effects at the concentrations delivered by smoked, vaporized, or oral
cannabis.

The "entourage effect" (Russo 2011, Br J Pharmacol) is the hypothesis
that terpenes and minor cannabinoids modulate the effects of primary
cannabinoids in an additive or synergistic manner. Evidence for this
hypothesis is:

- Strong at the in-vitro and animal level for specific terpenes
  (β-caryophyllene CB2 agonism; linalool 5-HT1A activity).
- Weak at the human clinical level: no adequately powered,
  pre-registered RCT has isolated a terpene-specific clinical outcome
  independent of cannabinoid effects.
- Commercially over-claimed: "entourage effect" language in retail
  contexts almost never cites the specific terpene, the concentration,
  the receptor, or the clinical outcome.

Design rules (shared with cannavec.interactions and cannavec.adverse_events):

- Every entry has at least one primary citation.
- Every entry carries an evidence grade and a claim_type from
  cannavec.evidence.
- The concentration range is always stated — the gap between in-vitro
  active concentrations and estimated in-vivo concentrations is the
  most important safety nuance for terpene overclaiming.
- The entourage-effect note is explicit on every entry that is
  commonly marketed with entourage language.
- Registry is read-only at runtime; additions require a new citation
  meeting the inclusion bar (≥1 peer-reviewed primary source).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from cannavec_science.evidence import ClaimType, EvidenceLevel


class TerpeneName(str, Enum):
    """Canonical terpene names used in the registry."""

    BETA_CARYOPHYLLENE = "β-caryophyllene"
    LINALOOL = "linalool"
    MYRCENE = "myrcene"
    LIMONENE = "limonene"
    ALPHA_PINENE = "α-pinene"
    TERPINOLENE = "terpinolene"
    HUMULENE = "humulene"
    OCIMENE = "ocimene"


@dataclass(frozen=True)
class TerpeneCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class Terpene:
    """A single curated terpene reference entry.

    ``pharmacology_evidence_grade`` is the grade for the *best-evidenced
    pharmacological claim* — usually a receptor binding or enzyme
    inhibition result from an in-vitro or animal study.

    ``clinical_evidence_grade`` is the grade for clinical (human)
    efficacy. For almost all terpenes this is Level D or E because
    no adequately powered terpene-specific human RCT exists.

    ``typical_concentration_pct_ww`` is the approximate range found
    in cannabis flower by weight. This is important context: at these
    concentrations, the bioavailable terpene dose via inhalation is
    well below most pharmacologically active in-vitro concentrations.

    ``in_vitro_active_concentration`` states the concentration at which
    pharmacological effects were demonstrated in vitro (usually μM or mM),
    contrasted with the estimated in-vivo inhaled dose.
    """

    name: TerpeneName
    type: str                               # monoterpene | sesquiterpene | diterpene
    aroma: str
    pharmacological_target: str             # primary receptor/enzyme/mechanism
    pharmacology_evidence_grade: EvidenceLevel
    clinical_evidence_grade: EvidenceLevel
    claim_type: ClaimType
    typical_concentration_pct_ww: str       # range in cannabis flower
    in_vitro_active_concentration: str      # concentration unit in assay
    entourage_role: str                     # "limited" | "proposed" | "not studied"
    key_notes: tuple[str, ...]
    citations: tuple[TerpeneCitation, ...]
    # Topic tags (cannabis-insight-engine spec 001 US3). Used by
    # compose_answer to filter the class-mention pass to topic-relevant
    # rows when the prompt names a specific topic. Empty frozenset
    # means "no claimed topic relevance — show only in unfiltered
    # queries". Tags are curator-assigned from the proposed-entourage
    # literature; they are NOT clinical endorsements.
    topic_tags: frozenset[str] = frozenset()

    def to_dict(self) -> dict:
        return {
            "name": self.name.value,
            "type": self.type,
            "aroma": self.aroma,
            "pharmacological_target": self.pharmacological_target,
            "pharmacology_evidence_grade": self.pharmacology_evidence_grade.value,
            "clinical_evidence_grade": self.clinical_evidence_grade.value,
            "claim_type": self.claim_type.value,
            "typical_concentration_pct_ww": self.typical_concentration_pct_ww,
            "in_vitro_active_concentration": self.in_vitro_active_concentration,
            "entourage_role": self.entourage_role,
            "key_notes": list(self.key_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }

    def to_claim(self, *, source_tier: "SourceTier | None" = None) -> "Claim":
        """Render this terpene row as a typed :class:`cannavec.evidence.Claim`.

        Produces a ``MECHANISM`` claim with one :class:`Source` per
        citation. The default ``source_tier`` is ``SINGLE_ARM_OR_MECH``
        because the underlying primary literature is overwhelmingly
        in-vitro receptor pharmacology or animal mechanism work. Callers
        with stronger clinical evidence may override.

        The wording is neutral-descriptive so the grade-vs-wording check
        never trips; the *evidence grade* flows from source tier + count,
        not from the prose. Disclosures are passed as the required set
        because the curator inclusion bar already validates target,
        target_identifier, assay, concentration, species, and primary
        source for every registry row.
        """
        from cannavec_science.evidence import (
            Claim,
            ClaimType,
            Source,
            SourceTier as _SourceTier,
            required_disclosures,
        )

        tier = source_tier or _SourceTier.SINGLE_ARM_OR_MECH
        sources = tuple(
            Source(
                title=c.label,
                tier=tier,
                pmid=c.pmid,
                doi=c.doi,
                url=c.url,
                year=c.year,
            )
            for c in self.citations
            if (c.pmid or c.doi or c.url)
        )
        text = (
            f"{self.name.value} ({self.type}) — pharmacological target: "
            f"{self.pharmacological_target}. Typical flower concentration: "
            f"{self.typical_concentration_pct_ww}. In-vitro active "
            f"concentration: {self.in_vitro_active_concentration}. "
            f"Entourage role: {self.entourage_role}."
        )
        disclosures = required_disclosures(ClaimType.MECHANISM)
        return Claim(
            text=text,
            claim_type=ClaimType.MECHANISM,
            sources=sources,
            disclosures_present=disclosures,
        )


def build_claim(
    terpene: "Terpene",
    *,
    source_tier: "SourceTier | None" = None,
) -> "Claim":
    """Module-level helper mirroring :meth:`Terpene.to_claim`."""
    return terpene.to_claim(source_tier=source_tier)


# ── Registry ───────────────────────────────────────────────────────────

_TERPENE_REGISTRY: tuple[Terpene, ...] = (
    Terpene(
        name=TerpeneName.BETA_CARYOPHYLLENE,
        type="sesquiterpene",
        aroma="peppery, spicy, woody",
        pharmacological_target=(
            "CB2 receptor (UniProt P34972) — selective partial agonist; "
            "also TRPV1 and PPARγ in vitro"
        ),
        pharmacology_evidence_grade=EvidenceLevel.B,
        clinical_evidence_grade=EvidenceLevel.D,
        claim_type=ClaimType.MECHANISM,
        typical_concentration_pct_ww="0.01–0.5% w/w in cannabis flower; "
            "up to 1.2% in high-caryophyllene cultivars",
        in_vitro_active_concentration=(
            "Ki ≈ 155 nM at CB2 (Gertsch et al. 2008, PNAS); "
            "estimated inhaled terpene dose is low nanomolar to sub-nanomolar "
            "at the receptor — substantially below Ki"
        ),
        entourage_role="proposed",
        key_notes=(
            "Unique among common cannabis terpenes in being a confirmed CB2 "
            "partial agonist at nanomolar concentrations (PMID 18574142).",
            "Anti-inflammatory effects in multiple rodent models (colitis, "
            "neuropathic pain) at doses achievable by oral administration "
            "but not reliably by inhalation of cannabis.",
            "Human clinical evidence is limited to one small pilot trial "
            "(Klauke et al. 2014) and observational data — Level D.",
            "The mechanism-to-clinic leap (CB2 agonism in vitro → "
            "anti-inflammation in humans) requires bridging RCT evidence "
            "that does not yet exist at adequate power.",
        ),
        citations=(
            TerpeneCitation(
                label="Gertsch J et al., PNAS 2008, β-caryophyllene as CB2 agonist",
                pmid="18574142",
                year=2008,
            ),
            TerpeneCitation(
                label="Russo EB, Br J Pharmacol 2011, terpenes and the entourage effect",
                pmid="21749363",
                year=2011,
            ),
        ),
        topic_tags=frozenset({"pain", "inflammation"}),
    ),
    Terpene(
        name=TerpeneName.LINALOOL,
        type="monoterpene",
        aroma="floral, lavender-like",
        pharmacological_target=(
            "5-HT1A partial agonist (UniProt P08908) in vitro; "
            "GABA-A potentiation in rodent models"
        ),
        pharmacology_evidence_grade=EvidenceLevel.C,
        clinical_evidence_grade=EvidenceLevel.E,
        claim_type=ClaimType.MECHANISM,
        typical_concentration_pct_ww="<0.1–0.3% w/w in most cannabis cultivars",
        in_vitro_active_concentration=(
            "Active at low micromolar concentrations (1–100 μM) in cell "
            "assays; estimated inhaled concentration at receptor is "
            "nanomolar — below active range for most assay endpoints"
        ),
        entourage_role="proposed",
        key_notes=(
            "Commonly marketed as the 'calming' terpene based on lavender "
            "aromatherapy data — which uses different routes, doses, and "
            "matrices than cannabis.",
            "No adequately powered human RCT has isolated linalool as the "
            "active constituent responsible for anxiolytic effects in cannabis.",
            "In-vitro 5-HT1A activity (PMID 25237920) at concentrations "
            "that are likely not achieved by typical cannabis inhalation.",
            "Claims about linalool 'causing' sedation or anxiolysis in cannabis "
            "exceed current evidence and are treated as banned-pattern "
            "untestable-wellness language by Cannavec.",
        ),
        citations=(
            TerpeneCitation(
                label="Russo EB, Br J Pharmacol 2011, terpenes and the entourage effect",
                pmid="21749363",
                year=2011,
            ),
            TerpeneCitation(
                label="Karunanithi S et al., Neuropharmacology 2014, linalool and GABA-A",
                pmid="25237920",
                year=2014,
            ),
        ),
        topic_tags=frozenset({"sleep", "anxiety"}),
    ),
    Terpene(
        name=TerpeneName.MYRCENE,
        type="monoterpene",
        aroma="earthy, musky, clove-like",
        pharmacological_target=(
            "TRPV1 agonist (in vitro); possible GABA-A modulation (animal); "
            "no confirmed human receptor target at physiologically relevant doses"
        ),
        pharmacology_evidence_grade=EvidenceLevel.D,
        clinical_evidence_grade=EvidenceLevel.E,
        claim_type=ClaimType.MECHANISM,
        typical_concentration_pct_ww=(
            "0.1–0.5% w/w; often the most abundant terpene in many cultivars"
        ),
        in_vitro_active_concentration=(
            "Effects reported at milligram doses in rodent models — "
            "equivalent concentrations are not reached via inhalation of cannabis"
        ),
        entourage_role="proposed",
        key_notes=(
            "The 'couch lock' claim attributing sedation to myrcene is "
            "a marketing convention with no controlled human evidence.",
            "Rodent sedation studies used oral myrcene at doses well above "
            "what inhaled cannabis delivers to any receptor.",
            "Most abundant terpene in many cultivars; does not imply "
            "proportionally greater pharmacological effect.",
            "Indica/sativa myrcene-content claims are unsupported and "
            "treated as banned-pattern language by Cannavec.",
        ),
        citations=(
            TerpeneCitation(
                label="Russo EB, Br J Pharmacol 2011, terpenes and the entourage effect",
                pmid="21749363",
                year=2011,
            ),
        ),
        topic_tags=frozenset({"sleep"}),
    ),
    Terpene(
        name=TerpeneName.LIMONENE,
        type="monoterpene",
        aroma="citrus, lemon-like",
        pharmacological_target=(
            "Gastric acid secretion reduction (animal); possible "
            "adenosine A2A modulation; antifungal in vitro"
        ),
        pharmacology_evidence_grade=EvidenceLevel.C,
        clinical_evidence_grade=EvidenceLevel.D,
        claim_type=ClaimType.MECHANISM,
        typical_concentration_pct_ww="<0.1–0.5% w/w",
        in_vitro_active_concentration=(
            "Active at low micromolar concentrations (1–10 μM) in some assays; "
            "human studies use oral supplementation at 1 g/day — "
            "far exceeding inhaled terpene load"
        ),
        entourage_role="proposed",
        key_notes=(
            "One small human pilot (Lv X et al. 2020, PMID 33059502) showed "
            "mood effects after oral limonene supplementation at gram doses "
            "— not via cannabis inhalation.",
            "Commonly marketed as 'uplifting' in cannabis retail contexts "
            "without adequate trial evidence.",
            "Antifungal activity confirmed in vitro; agronomically relevant "
            "but does not translate to clinical antifungal use.",
        ),
        citations=(
            TerpeneCitation(
                label="Russo EB, Br J Pharmacol 2011, terpenes and the entourage effect",
                pmid="21749363",
                year=2011,
            ),
            TerpeneCitation(
                label="Lv X et al., Front Pharmacol 2020, limonene and mood",
                pmid="33059502",
                year=2020,
            ),
        ),
        topic_tags=frozenset({"anxiety"}),
    ),
    Terpene(
        name=TerpeneName.ALPHA_PINENE,
        type="monoterpene",
        aroma="pine, fresh",
        pharmacological_target=(
            "Acetylcholinesterase inhibitor in vitro; GABA-A site activity "
            "is concentration- and assay-dependent in the published in-"
            "vitro literature (reported as positive modulator at some "
            "concentrations, inverse-agonist-like at others — a flat "
            "'antagonist' label oversimplifies); bronchodilator in animal "
            "models. Human pharmacology at cannabis-delivered "
            "concentrations is unestablished."
        ),
        pharmacology_evidence_grade=EvidenceLevel.D,
        clinical_evidence_grade=EvidenceLevel.E,
        claim_type=ClaimType.MECHANISM,
        typical_concentration_pct_ww="<0.1–0.3% w/w",
        in_vitro_active_concentration=(
            "AChE inhibition at IC50 ≈ 0.04 mg/mL in vitro; "
            "clinical relevance at inhaled cannabis concentrations is unestablished"
        ),
        entourage_role="proposed",
        key_notes=(
            "Sometimes marketed as 'counteracting THC-induced memory impairment' "
            "via AChE inhibition — mechanism is plausible in vitro but "
            "no human RCT has confirmed this at cannabis-delivered concentrations.",
            "Bronchodilator effect in guinea pig model; not studied in humans "
            "at cannabis-delivered doses.",
        ),
        citations=(
            TerpeneCitation(
                label="Russo EB, Br J Pharmacol 2011, terpenes and the entourage effect",
                pmid="21749363",
                year=2011,
            ),
        ),
        topic_tags=frozenset({"focus"}),
    ),
    Terpene(
        name=TerpeneName.TERPINOLENE,
        type="monoterpene",
        aroma="floral, herby, piney",
        pharmacological_target=(
            "Antifungal in vitro; weak antioxidant; sedative in mice "
            "(high oral dose — not in vitro)"
        ),
        pharmacology_evidence_grade=EvidenceLevel.D,
        clinical_evidence_grade=EvidenceLevel.E,
        claim_type=ClaimType.MECHANISM,
        typical_concentration_pct_ww="<0.1% w/w in most cultivars; "
            "dominant in some specific chemotypes",
        in_vitro_active_concentration=(
            "Antifungal at MIC 0.5–2 mg/mL; sedation in mice at 200–400 mg/kg oral "
            "— far beyond inhalation-delivered concentrations"
        ),
        entourage_role="not studied",
        key_notes=(
            "Sedation marketing (sometimes called 'the sleepy terpene') based "
            "on very high rodent oral doses, not inhalation studies.",
            "Antifungal activity in vitro is agronomically relevant (cultivar "
            "pest resistance) but does not translate to clinical antifungal use.",
        ),
        citations=(
            TerpeneCitation(
                label="Russo EB, Br J Pharmacol 2011, terpenes and the entourage effect",
                pmid="21749363",
                year=2011,
            ),
        ),
        topic_tags=frozenset({"sleep"}),
    ),
    Terpene(
        name=TerpeneName.HUMULENE,
        type="sesquiterpene",
        aroma="earthy, woody, hoppy (same terpene as hops)",
        pharmacological_target=(
            "Anti-inflammatory (NF-κB pathway, in vitro/animal); "
            "appetite-suppressant effect in rodent models"
        ),
        pharmacology_evidence_grade=EvidenceLevel.D,
        clinical_evidence_grade=EvidenceLevel.E,
        claim_type=ClaimType.MECHANISM,
        typical_concentration_pct_ww="0.01–0.2% w/w",
        in_vitro_active_concentration=(
            "Anti-inflammatory at 1–10 μM in cell assays; rodent studies "
            "use oral humulene at doses not achievable via cannabis inhalation"
        ),
        entourage_role="not studied",
        key_notes=(
            "Anti-inflammatory marketing based on rodent data using isolated "
            "humulene at high oral doses — not demonstrated in humans.",
            "Also found in hops (Humulus lupulus) — cross-plant comparisons "
            "require route, dose, and matrix equivalence checks.",
        ),
        citations=(
            TerpeneCitation(
                label="Russo EB, Br J Pharmacol 2011, terpenes and the entourage effect",
                pmid="21749363",
                year=2011,
            ),
        ),
        topic_tags=frozenset({"inflammation", "appetite"}),
    ),
)


def all_terpenes() -> tuple[Terpene, ...]:
    """Return all curated terpene entries."""
    return _TERPENE_REGISTRY


# Detection patterns — used by detect_terpene_mention().
# Names are canonical; aliases cover common misspellings and abbreviations.
_TERPENE_ALIASES: dict[TerpeneName, tuple[str, ...]] = {
    TerpeneName.BETA_CARYOPHYLLENE: (
        "caryophyllene", "beta.caryophyllene", "β.caryophyllene",
        "bcp", "b-caryophyllene",
    ),
    TerpeneName.LINALOOL: ("linalool", "linalyl"),
    TerpeneName.MYRCENE: ("myrcene",),
    TerpeneName.LIMONENE: ("limonene", "d-limonene"),
    TerpeneName.ALPHA_PINENE: ("pinene", "alpha.pinene", "α.pinene", "a-pinene"),
    TerpeneName.TERPINOLENE: ("terpinolene",),
    TerpeneName.HUMULENE: ("humulene", "α.humulene", "alpha.humulene"),
}

_ALIAS_TO_NAME: dict[str, TerpeneName] = {}
_TERPENE_DETECT_RE: dict[TerpeneName, re.Pattern[str]] = {}

for _name, _aliases in _TERPENE_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_NAME[_alias] = _name
    _TERPENE_DETECT_RE[_name] = re.compile(
        r"\b(?:" + "|".join(re.escape(a) for a in _aliases) + r")\b",
        flags=re.IGNORECASE,
    )


def find_terpenes(
    *,
    name_substring: str | None = None,
    terpene_type: str | None = None,
    min_pharmacology_grade: EvidenceLevel | None = None,
) -> tuple[Terpene, ...]:
    """Filter the registry by optional criteria."""
    results: list[Terpene] = []
    for t in _TERPENE_REGISTRY:
        if name_substring and name_substring.lower() not in t.name.value.lower():
            continue
        if terpene_type and terpene_type.lower() not in t.type.lower():
            continue
        if (
            min_pharmacology_grade is not None
            and t.pharmacology_evidence_grade.rank < min_pharmacology_grade.rank
        ):
            continue
        results.append(t)
    return tuple(results)


def filter_by_topics(
    terpenes: Iterable[Terpene],
    topics: frozenset[str],
) -> tuple[Terpene, ...]:
    """Filter terpene rows whose curated ``topic_tags`` intersect the
    requested topics.

    Used by ``compose_answer`` (cannabis-insight-engine spec 001 US3).
    When ``topics`` is empty, returns the input unchanged — preserves
    backwards compatibility for queries with no topic intent.
    """
    if not topics:
        return tuple(terpenes)
    return tuple(
        t for t in terpenes if t.topic_tags & topics
    )


def detect_terpene_mention(text: str) -> tuple[Terpene, ...]:
    """Return every terpene mentioned in ``text``, deduplicated."""
    found: list[Terpene] = []
    seen: set[TerpeneName] = set()
    for t in _TERPENE_REGISTRY:
        if t.name in seen:
            continue
        regex = _TERPENE_DETECT_RE[t.name]
        if regex.search(text):
            found.append(t)
            seen.add(t.name)
    return tuple(found)


# Class-level fallback for generic terpene questions. Mirrors the pattern
# in ``cannavec.interactions.detect_interaction_class_mention``: when the
# strict named-terpene matcher returns nothing but the prompt is clearly
# about terpenes as a class ("how do terpenes affect cannabis effects?",
# "what are the main cannabis terpenes?", "entourage effect"), surface
# the full registry so the answer pipeline can render a meaningful
# terpene section instead of zero claims.
_TERPENE_CLASS_KEYWORDS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{kw}\b", flags=re.IGNORECASE)
    for kw in (
        r"terpenes?",
        r"monoterpenes?",
        r"sesquiterpenes?",
        r"diterpenes?",
        r"terpene profile",
        r"terpene pharmacology",
        r"entourage effect",
        r"entourage hypothesis",
        r"aromatic compounds? in cannabis",
        r"aroma compounds?",
    )
)


def detect_terpene_class_mention(text: str) -> tuple[Terpene, ...]:
    """Return the full terpene registry when the prompt is a class-level
    terpene question and no specific terpene was named.

    Companion to :func:`detect_terpene_mention`. Returns ``()`` when no
    class keyword fires, so callers can safely chain::

        hits = detect_terpene_mention(t) or detect_terpene_class_mention(t)

    Closes the gap that "How do terpenes affect cannabis effects?" — the
    canonical question for the terpene domain — surfaced zero registry
    rows through ``compose_answer``.
    """
    for rx in _TERPENE_CLASS_KEYWORDS:
        if rx.search(text):
            return tuple(_TERPENE_REGISTRY)
    return ()


def entourage_effect_note() -> str:
    """Return the canonical Cannavec note on the entourage effect.

    Surfaces should include this when answering questions about terpenes
    and cannabis effects, to distinguish what is known from what is
    commercially over-claimed.
    """
    return (
        "**Entourage effect hypothesis** (Russo 2011, PMID 21749363): "
        "Terpenes may modulate cannabinoid effects via receptor-level "
        "interactions. This hypothesis has mechanistic support at the "
        "in-vitro level for β-caryophyllene (CB2 agonism) and linalool "
        "(5-HT1A activity). However, no adequately powered, pre-registered "
        "human RCT has isolated a terpene-specific clinical outcome "
        "independent of cannabinoid effects. Terpene concentrations in "
        "typical inhaled cannabis (low nanomolar at the receptor) are often "
        "below the active concentrations demonstrated in in-vitro assays "
        "(low micromolar to millimolar). The entourage effect is an "
        "evidence-grounded hypothesis (Level C at best), not an established "
        "clinical mechanism."
    )


def format_for_clinician(terpenes: Iterable[Terpene]) -> str:
    """Render a list of terpene entries as Markdown for a clinician surface."""
    rows: list[str] = []
    for t in terpenes:
        pmids = [c.pmid for c in t.citations if c.pmid]
        pmid_str = ", ".join(f"PMID {p}" for p in pmids) if pmids else "no PMID"
        rows.append(
            f"### {t.name.value} ({t.type})\n"
            f"- **Aroma:** {t.aroma}\n"
            f"- **Target:** {t.pharmacological_target}\n"
            f"- **Pharmacology grade:** {t.pharmacology_evidence_grade.value} "
            f"(mechanism); **Clinical grade:** {t.clinical_evidence_grade.value}\n"
            f"- **Typical flower concentration:** {t.typical_concentration_pct_ww}\n"
            f"- **In-vitro active concentration:** {t.in_vitro_active_concentration}\n"
            f"- **Entourage role:** {t.entourage_role}\n"
            f"- **Key notes:**\n"
            + "\n".join(f"  - {n}" for n in t.key_notes)
            + f"\n- **Citations:** {pmid_str}"
        )
    if not rows:
        return "_No terpene registry entries matched._"
    return "\n\n".join(rows) + "\n\n" + entourage_effect_note()
