"""Deterministic detector for the ten banned patterns.

The ``cannabis-banned-patterns`` skill describes these in prose. This
module compiles them as regex so any output Cannavec produces can be
re-checked mechanically. The goal is not to police users — they may
quote any of these patterns when describing what *other* people say —
but to ensure Cannavec itself never adopts them as its own voice.

Each :class:`BannedPattern` carries:

- a short id
- a one-line title
- the pattern (compiled regex)
- a replacement template the surface should emit instead
- a note explaining *why* the pattern is banned

The detector returns a list of hits with the matching span so callers
can show the user where in their draft the pattern fires.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Pattern

from cannavec_science._markdown_skip import code_spans, is_in_code


@dataclass(frozen=True)
class BannedPattern:
    id: str
    title: str
    regex: Pattern[str]
    replacement: str
    why: str


@dataclass(frozen=True)
class BannedPatternHit:
    pattern: BannedPattern
    match: str
    span: tuple[int, int]


def _ci(pattern: str) -> Pattern[str]:
    return re.compile(pattern, flags=re.IGNORECASE | re.DOTALL)


BANNED_PATTERN_REGISTRY: tuple[BannedPattern, ...] = (
    BannedPattern(
        id="indica_sativa_as_pharmacology",
        title="Indica/sativa framed as pharmacology",
        # Match "indica/sativa" or "sativa/indica" or sentences where
        # indica/sativa is named alongside a pharmacological effect.
        regex=_ci(
            r"\b(?:indicas?|sativas?|hybrids?)\b[^.\n]{0,180}\b"
            r"(?:sleep|sleepy|sedat\w*|energ\w*|uplift\w*|relax\w*|alert\w*|"
            r"daytime|nighttime|night-time|focus|cerebral|body high|"
            r"calming|stimulat\w*|euphor\w*)\b"
        ),
        replacement=(
            "Describe by chemotype (Type I/II/III/IV/V) and named dominant "
            "cannabinoids + terpenes; indica/sativa is botanical/colloquial "
            "and does not correlate with effect."
        ),
        why=(
            "Indica/sativa/hybrid are not biochemically meaningful in "
            "modern hybridised cultivars; mapping them to subjective "
            "effects is a marketing convention, not pharmacology."
        ),
    ),
    # Spec 004 US4 / FR-005 — abstract-framing sibling of the indica/
    # sativa pattern. v0.3 only caught the prose form ("indica strains
    # are sedating"); a researcher asking the abstract meta question
    # ("indica vs sativa pharmacological differences") got silent
    # 0 claims. This sibling fires on indica/sativa + abstract framing
    # words. The negative lookbehinds let through botanical / taxonomy
    # framing because Cannabis sativa L. as a species name is research-
    # grade botany, not pharmacology framing.
    BannedPattern(
        id="indica_sativa_as_pharmacology_abstract",
        title="Indica/sativa framed as pharmacology (abstract framing)",
        regex=_ci(
            # Disallow contexts where the word is part of a binomial
            # ("Cannabis sativa", "Cannabis sativa L.", "C. sativa") OR
            # explicit taxonomic / botanical framing — these are research
            # questions about plant systematics, not pharmacology framing.
            r"(?<!cannabis\s)(?<!c\.\s)"
            r"\b(?:indicas?|sativas?|hybrids?)\b"
            r"(?![^.\n]*?\b(?:L\.|taxonom\w*|botan\w*|species\s+debate|"
            r"systemati\w*|biosystemati\w*|cronquist|hillig)\b)"
            r"[^.\n]{0,60}\b"
            r"(?:pharmacolog\w*|pharmaceut\w*|"
            r"effects?\b|differences?\b|"
            r"pharmacodynam\w*|pharmacokineti\w*|"
            r"mechanism\w*|receptor\s+activit\w*)"
        ),
        replacement=(
            "Describe by chemotype (Type I/II/III/IV/V) and named dominant "
            "cannabinoids + terpenes; indica/sativa as a pharmacology lens "
            "is a marketing convention. The botanical taxonomy debate "
            "(Small & Cronquist 1976 / Hillig & Mahlberg 2004 / McPartland "
            "2018) is a separate, research-grade question — phrase it in "
            "taxonomic / botanical terms if that is what you mean."
        ),
        why=(
            "Indica/sativa/hybrid do not correlate with pharmacological "
            "effects or pharmacokinetic profiles in modern hybridised "
            "cultivars; abstract framings of the question reinforce the "
            "same marketing convention as the prose form."
        ),
    ),
    BannedPattern(
        id="cultivar_as_effect",
        title="Cultivar-as-effect",
        # "OG Kush is for relaxation", "Blue Dream produces uplifting effects".
        # Case-sensitive — cultivar names are proper nouns. Using _ci() here
        # would make [A-Z] match any letter and produce false positives on
        # ordinary prose.
        #
        # The leading negative lookahead excludes English question/determiner
        # words and cannabinoid abbreviations so legitimate research prompts
        # ("What is the evidence for CBN as a sleep aid?", "Does THC help with
        # nausea?") do not get misclassified as cultivar-effect claims. See
        # specs/001-cannabis-insight-engine/spec.md US6 for the regression
        # cases.
        regex=re.compile(
            r"\b"
            r"(?!"
            r"(?:What|How|Where|When|Why|Which|Whose|Whom|"
            r"Does|Do|Did|Is|Are|Was|Were|Be|Been|Being|"
            r"Has|Have|Had|Can|Could|May|Might|Must|Shall|Should|"
            r"Will|Would|If|Whether|Maybe|Perhaps|"
            r"The|This|That|These|Those|"
            r"Cannabis|Hemp|Marijuana|"
            r"CBN|CBD|CBG|CBC|CBDV|CBDA|CBNA|CBCA|CBGA|"
            r"THCV|THC|THCA|HHC|CBL|CBT|"
            r"CB1|CB2|CYP|PPAR|TRPV1|GABA|"
            r"PMID|DOI|NCT|FDA|EMA|MHRA|DEA|EPA"
            r")\b)"
            r"([A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+){0,3})\s+"
            r"(?:is|are|provides|offers|delivers|produces|gives|brings|"
            r"causes|leads to)\s+"
            r"(?:[^.\n]{0,40})(?:relax\w*|sleep|sleepy|uplift\w*|energiz\w*|"
            r"creative|focus|calm\w*|euphor\w*|cerebral|body high|"
            r"sedat\w*|"
            # Effect-word expansion (cannabis-insight-engine spec 001 US6
            # false-negative fix): pain / insomnia / anxiety etc. are the
            # exact words cultivar marketing uses, and were missing from the
            # original alternation.
            r"pain|insomnia|anxiet\w*|stress|depress\w*|appetite|"
            r"nausea|PTSD|ADHD|migraine|inflammat\w*)",
            flags=re.DOTALL,
        ),
        replacement=(
            "Tie effects to chromatographically verified chemotype "
            "(cannabinoid + terpene profile) and clinical evidence, "
            "not the cultivar name."
        ),
        why=(
            "Cultivar names are colloquial labels. Two plants sold as "
            "the same cultivar in different markets are not guaranteed "
            "to be the same chemotype."
        ),
    ),
    BannedPattern(
        id="marketing_ratio",
        title="Marketing-derived CBD:THC ratios as pharmacology",
        # Match "1:1", "20:1", "4:1" alongside therapeutic claims.
        regex=_ci(
            r"\b\d{1,3}\s*:\s*\d{1,3}\b[^.\n]{0,120}\b"
            r"(?:balance\w*|daytime|nighttime|night-time|sleep|"
            r"therapeutic|effective|cure\w*|treat\w*|relax\w*|"
            r"calm\w*|wellness|harmony)\b"
        ),
        replacement=(
            "Cite the specific trial intervention arm with actual doses "
            "(mg CBD / mg THC), route, and population — not the ratio."
        ),
        why=(
            "Ratios in product marketing are not dose-response data. "
            "Therapeutic effect is dose- and indication-dependent."
        ),
    ),
    BannedPattern(
        id="natural_therefore_safe",
        title="“Natural therefore safe”",
        regex=_ci(
            r"\bnatural(?:ly)?\b[^.\n]{0,80}\b(?:safe|safer|gentle\w*|"
            r"non-toxic|harmless|less side effects|fewer side effects)\b"
            r"|"
            r"\b(?:plant|botanical|herbal)\b[^.\n]{0,60}\b"
            r"(?:safer|gentler|less harm|harmless)\b"
        ),
        replacement=(
            "Report specific safety / interaction data with citation. "
            "Plant origin grants no safety, efficacy, or interaction immunity."
        ),
        why=(
            "Many natural products are highly toxic; many synthetic "
            "drugs are extremely safe. Origin is a category error."
        ),
    ),
    BannedPattern(
        id="cure_claim",
        title="“Cure” claims",
        regex=_ci(
            r"\b(?:cures?|cured|curing|reverses?|reversal of|"
            r"eradicat\w*|eliminat\w*|heals?|healed|healing|"
            r"miracle\w*)\b[^.\n]{0,40}\b"
            r"(?:cancer|tumou?rs?|alzheimer\w*|parkinson\w*|"
            r"epileps\w*|seizures?|ptsd|depression|anxiet\w*|"
            r"autism|crohn\w*|ms|multiple sclerosis|aids|hiv|"
            r"diabetes|arthritis|fibromyalgi\w*)\b"
        ),
        replacement=(
            "State the quantified effect on a specific outcome (e.g. "
            "“reduces convulsive-seizure frequency by X% vs placebo "
            "(Devinsky 2017, NEJM)”) — not “cures”."
        ),
        why=(
            "Cannabinoids cure no condition under current evidence. "
            "Even the most evidence-supported cannabinoid medicines "
            "manage rather than cure."
        ),
    ),
    BannedPattern(
        id="cherry_picked",
        title="Cherry-picked sample sizes / studies",
        regex=_ci(
            r"\b(?:studies show|research shows|many studies|"
            r"countless studies|growing body of evidence|"
            r"overwhelming evidence)\b"
            r"(?![^.\n]{0,200}\b(?:meta-analysis|systematic review|"
            r"cochrane|grade)\b)"
        ),
        replacement=(
            "Cite the specific study or systematic review with effect "
            "size, n, and grade. Honest synthesis includes null and "
            "negative trials."
        ),
        why=(
            "Vague “studies show” framings without a specific citation "
            "are a cherry-pick tell. Pillar V requires honest synthesis."
        ),
    ),
    BannedPattern(
        id="mechanism_to_clinic",
        title="Mechanism-implies-clinic leap",
        regex=_ci(
            r"\b(?:CB1|CB2|TRPV1|GPR55|PPAR(?:γ|gamma)?|5-?HT1A)\b"
            r"[^.\n]{0,80}\btherefore\b[^.\n]{0,120}\b"
            r"(?:treat\w*|effective for|relieves?|cures?|"
            r"manages?)\b"
        ),
        replacement=(
            "Report the mechanism with primary database evidence "
            "(BindingDB / ChEMBL / UniProt) and state that bridging "
            "clinical trials are required for any clinical claim."
        ),
        why=(
            "A mechanism in vitro or in animals does not imply a "
            "clinical effect in humans. The leap requires bridging "
            "trial evidence."
        ),
    ),
    BannedPattern(
        id="brand_endorsement",
        title="Affiliate / brand / SKU endorsement",
        regex=_ci(
            r"\b(?:brand|company|dispensary|product|sku)\b[^.\n]{0,40}\b"
            r"(?:best|top|number one|#1|superior|most trusted|"
            r"recommended|premium)\b"
            r"|"
            r"\b(?:we recommend|i recommend|our pick)\b[^.\n]{0,40}\b"
            r"(?:product|brand|cultivar|strain)\b"
        ),
        replacement=(
            "Report only verifiable product facts: regulatory approvals "
            "(with date), recalls (with ID and date), formulation "
            "specifics, or contamination findings."
        ),
        why="Commercial neutrality is a Pillar V requirement.",
    ),
    BannedPattern(
        id="anecdote_as_evidence",
        title="Anecdote as evidence",
        regex=_ci(
            r"\b(?:patients?|users?|consumers?|people)\s+"
            r"(?:report|find|say|tell us|describe)\b[^.\n]{0,80}\b"
            r"(?:relief|helped|works|effective|amazing|"
            r"life[-\s]?changing)\b"
        ),
        replacement=(
            "Cite registry or survey data with sample, methodology, "
            "jurisdiction, and time period — framed as observational, "
            "not causal."
        ),
        why=(
            "Anecdotal framings substituted for trial evidence violate "
            "Pillar I (methodological rigor)."
        ),
    ),
    BannedPattern(
        id="untestable_wellness",
        title="Untestable wellness claims",
        regex=_ci(
            r"\b(?:strengthens?|supports?|boosts?|enhances?|"
            r"restores?|balances?|promotes?|optimi[sz]es?)\b"
            r"[^.\n]{0,40}\b"
            r"(?:immune system|wellness|harmony|natural balance|"
            r"endocannabinoid system|body|mind|wellbeing|well-being|"
            r"vitality|homeostasis)\b"
        ),
        replacement=(
            "Replace with a specific, measurable effect on a named "
            "biomarker or named clinical outcome in a named population."
        ),
        why=(
            "These claims have no operational definition and cannot be "
            "falsified. They are marketing language masquerading as "
            "scientific assertion."
        ),
    ),
    BannedPattern(
        id="endocannabinoid_deficiency_causal",
        title="Clinical Endocannabinoid Deficiency (CECD) as established causal explanation",
        # Match "endocannabinoid deficiency" used as a causal explanation for a named
        # condition without a qualifying 'hypothesis', 'proposed', or 'theory'.
        regex=_ci(
            r"\bendocannabinoid\s+deficiency\b[^.\n]{0,100}\b"
            r"(?:causes?|explains?|underlies?|responsible for|"
            r"leads? to|results? in|accounts? for)\b[^.\n]{0,60}\b"
            r"(?:migraine|fibromyalgi\w*|ibs|irritable bowel|ptsd|"
            r"depression|anxiet\w*|ms|multiple sclerosis|pain|insomnia)\b"
            r"|"
            r"\b(?:migraine|fibromyalgi\w*|ibs|irritable bowel|ptsd|"
            r"depression|anxiet\w*|ms|multiple sclerosis|pain|insomnia)\b"
            r"[^.\n]{0,60}\b"
            r"(?:caused? by|due to|result of|from)\b[^.\n]{0,60}\b"
            r"endocannabinoid\s+deficiency\b"
        ),
        replacement=(
            "Describe CECD as a theoretical hypothesis (proposed by Russo 2004 and "
            "updated 2016) with indirect supporting evidence (reduced endocannabinoid "
            "tone in some patient groups). State that no prospective human trial "
            "has confirmed it as a disease mechanism and that the evidence "
            "is classified Level D (observational signals, no established causation)."
        ),
        why=(
            "Clinical Endocannabinoid Deficiency is an unvalidated hypothesis, "
            "not an established pathophysiological mechanism. Presenting it as "
            "a confirmed cause of migraine, IBS, fibromyalgia, or similar "
            "conditions overclaims the evidence and may drive patients away "
            "from evidence-based treatments."
        ),
    ),
    BannedPattern(
        id="full_spectrum_superiority",
        title='"Full spectrum is better/superior/more effective than isolate" as universal claim',
        regex=_ci(
            r"\bfull[- ]?spectrum\b[^.\n]{0,80}\b"
            r"(?:better|superior|more effective|more potent|stronger|"
            r"outperforms?|beats?|preferred over|proven (?:better|superior))\b"
            r"[^.\n]{0,60}\b(?:isolates?|broad[- ]?spectrum|pure cbd|pure thc)\b"
            r"|"
            r"\b(?:isolates?|broad[- ]?spectrum)\b[^.\n]{0,60}\b"
            r"(?:inferior|less effective|weaker|not as (?:effective|potent|good))\b"
            r"[^.\n]{0,60}\bfull[- ]?spectrum\b"
        ),
        replacement=(
            "State the entourage-effect hypothesis is supported by preclinical "
            "evidence and limited human pharmacokinetic data (e.g. Gallily 2015 "
            "in mice; Pamplona 2018 observational in CBD epilepsy) but has not "
            "been demonstrated by a powered human RCT comparing full-spectrum "
            "to isolate at equivalent cannabinoid doses for any indication. "
            "Clinical superiority of full-spectrum over isolate is unproven."
        ),
        why=(
            "The entourage effect is a pharmacological hypothesis, not a "
            "clinically validated superiority claim. Asserting full-spectrum "
            "is categorically better than isolate without a supporting RCT "
            "at equivalent dose is a commercial claim masquerading as evidence."
        ),
    ),
    BannedPattern(
        id="non_psychoactive_cbd_misuse",
        title='"Non-psychoactive" applied to CBD implying freedom from CNS effects',
        regex=_ci(
            r"\bcbd\b[^.\n]{0,60}\b(?:non-psychoactive|non psychoactive|"
            r"not psychoactive|doesn'?t (?:affect|alter|change) (?:the )?mind|"
            r"won'?t get you high and (?:is|has|causes?)\b[^.\n]{0,40}\b"
            r"(?:safe|no side effects|no (?:adverse|bad|negative) effects))\b"
            r"|"
            r"\b(?:non-psychoactive|non psychoactive|not psychoactive)\b"
            r"[^.\n]{0,40}\bcbd\b[^.\n]{0,60}\b"
            r"(?:safe|no side effects|no (?:adverse|bad|negative) effects|"
            r"won'?t affect|doesn'?t affect)\b"
        ),
        replacement=(
            "Replace with 'non-intoxicating' or 'does not produce cannabis-like "
            "euphoria/intoxication'. CBD is not psychoactive in the colloquial "
            "sense but does have documented CNS activity including anxiolytic, "
            "anticonvulsant, and sedative effects. CBD also has documented "
            "adverse effects (somnolence, diarrhoea, elevated liver enzymes "
            "in the Epidiolex trial population at higher doses). "
            "Cite Devinsky 2017 (PMID 28538134) or the FDA Epidiolex label."
        ),
        why=(
            "Describing CBD as 'non-psychoactive' and therefore safe conflates "
            "two distinct claims. CBD lacks Δ⁹-THC-like euphoria, but it is "
            "not pharmacologically inert in the CNS. The 'non-psychoactive = "
            "safe' framing is factually incorrect and obscures real adverse "
            "effects documented in regulatory trials."
        ),
    ),
    BannedPattern(
        id="terpene_as_clinical_effect",
        title="Single terpene asserted as cause of a clinical effect from cannabis",
        # A terpene name + causal verb + sedation/anxiolysis/etc. without
        # qualifier ("in vitro", "rodent", "preclinical", "hypothesised").
        # The terpene-as-cause leap is the same error class as cultivar-
        # as-effect: in-vitro receptor activity at micromolar doses does
        # not translate to clinical effect at the nanomolar concentrations
        # inhaled cannabis actually delivers (see terpene registry).
        regex=_ci(
            r"\b(?:myrcene|linalool|limonene|pinene|α[-\s]?pinene|"
            r"β[-\s]?caryophyllene|caryophyllene|humulene|terpinolene|"
            r"ocimene|nerolidol|bisabolol|guaiol|eucalyptol|geraniol|"
            r"high[-\s]?(?:myrcene|linalool|limonene|pinene|caryophyllene))\b"
            r"(?:[- ](?:dominant|rich|heavy|cultivars?|strains?|chemotypes?))?"
            r"[^.\n]{0,80}\b"
            r"(?:causes?|produces?|provides?|delivers?|gives?|brings?|"
            r"results? in|leads? to|induces?|drives?|is responsible for|"
            r"makes? (?:you|users) (?:feel|become))\b[^.\n]{0,60}\b"
            r"(?:sedation|sedat\w*|sleep|sleepy|drowsiness|couch[-\s]?lock|"
            r"anxiolysis|anxiolyt\w*|relax\w*|calm\w*|uplift\w*|"
            r"energ\w*|focus|alertness|euphor\w*|"
            r"analges\w*|pain relief|anti[-\s]?inflammator\w*)\b"
        ),
        replacement=(
            "Frame terpene-effect claims by named pharmacology grade and "
            "concentration. Cannabis inhalation delivers nanomolar to sub-"
            "nanomolar terpene exposure at any receptor — typically below "
            "the micromolar concentrations at which in-vitro activity is "
            "observed. Cite the terpene registry and Russo 2011 (PMID 21749363) "
            "for the hypothesis; do not state effects as established."
        ),
        why=(
            "Single-terpene → clinical-effect claims overclaim what "
            "controlled human evidence supports. Receptor activity in vitro "
            "or in rodent models at concentrations not achieved by cannabis "
            "inhalation does not establish a clinical effect. The myrcene-"
            "couch-lock claim and the linalool-calming claim are marketing "
            "conventions, not pharmacology."
        ),
    ),
    BannedPattern(
        id="ecs_master_regulator",
        title="Endocannabinoid system framed as master regulator of all physiology",
        # The ECS is a meaningful homeostatic signalling system, but
        # framing it as the regulator of "all" / "every" body system or
        # disease is an over-reach that primes patients for over-broad
        # cannabinoid claims.
        regex=_ci(
            r"\b(?:the\s+)?(?:endocannabinoid\s+system|ecs)\b[^.\n]{0,80}\b"
            r"(?:regulates|controls|governs|orchestrates|"
            r"is (?:the |a )?master regulator (?:of|for)|"
            r"is responsible for|underlies|maintains homeostasis (?:of|in|across))"
            r"\b[^.\n]{0,80}\b"
            r"(?:all|every|the entire|the whole|"
            r"all (?:human )?(?:physiology|disease|body systems|organ systems)|"
            r"every (?:body|organ|cellular) system|"
            r"everything in (?:the body|human physiology))\b"
            r"|"
            r"\b(?:the\s+)?(?:endocannabinoid\s+system|ecs)\b[^.\n]{0,60}\b"
            r"(?:master regulator|grand regulator|central regulator of"
            r"\s+(?:all|every)|controls everything|regulates everything)\b"
        ),
        replacement=(
            "Describe the ECS as a homeostatic signalling system with "
            "documented roles in pain, mood, appetite, immune function, "
            "and reproduction (Pertwee 2015; Lu & Mackie 2016, PMID 26970271). "
            "It is not a master regulator of all physiology, and ECS "
            "involvement in a system does not imply cannabinoids modulate "
            "that system clinically."
        ),
        why=(
            "Master-regulator framing inflates the ECS beyond what its "
            "documented signalling roles support, and primes downstream "
            "claims that any cannabinoid intervention will affect any "
            "system. This is the conceptual gateway to over-broad clinical "
            "claims; the published ECS literature does not support it."
        ),
    ),
)


# Negation window: when a cure-verb match is preceded by a negation
# word within this many characters, the match is a false positive.
# Example: "does NOT cure cancer" — the factually correct rebuttal —
# should not fire the cure_claim pattern.
_NEGATION_WINDOW: int = 30

_NEGATION_PREFIX = re.compile(
    r"\b(?:not|no|never|cannot|can't|won't|doesn't|don't|"
    r"do not|will not|does not|are not|is not|isn't|aren't|"
    r"has not|have not|hasn't|haven't|"
    r"no evidence|not (?:a |an )?(?:cure|treatment|therapy|drug))\b",
    re.IGNORECASE,
)

# Patterns for which negation-prefix filtering is safe.  The cure_claim
# pattern is the only one currently needing this guard — the others
# (indica-as-pharmacology, marketing-ratio, etc.) are positive assertions
# that are unlikely to appear in negated form in legitimate answers.
_NEGATION_FILTERED_IDS: frozenset[str] = frozenset({"cure_claim"})


def _is_negated(text: str, match_start: int, pattern_id: str) -> bool:
    """True if the match at ``match_start`` is preceded by a negation phrase.

    Only applied for patterns in :data:`_NEGATION_FILTERED_IDS`.  Looks
    back up to :data:`_NEGATION_WINDOW` characters before the match for a
    negation word / phrase.
    """
    if pattern_id not in _NEGATION_FILTERED_IDS:
        return False
    window_start = max(0, match_start - _NEGATION_WINDOW)
    preceding = text[window_start:match_start]
    return bool(_NEGATION_PREFIX.search(preceding))


def detect_banned_patterns(text: str) -> list[BannedPatternHit]:
    """Return every banned-pattern hit in ``text`` with its span.

    Hits are returned in document order. Multiple patterns may match the
    same span. Callers are responsible for deciding whether to reject,
    rewrite, or surface to the user.

    Negated cure claims (e.g. "does NOT cure cancer", "cannabis is not a
    cure for cancer") are filtered out — they are factually correct
    rebuttals, not overclaims.

    Matches whose start position falls inside a markdown inline-code
    span (`` `cure` ``) or fenced code block are also filtered: an
    audit / discussion section that *names* a banned pattern in code
    formatting is not asserting the claim. This is the meta-language
    guard.
    """
    spans = code_spans(text)
    hits: list[BannedPatternHit] = []
    for pattern in BANNED_PATTERN_REGISTRY:
        for m in pattern.regex.finditer(text):
            if is_in_code(spans, m.start()):
                continue
            if _is_negated(text, m.start(), pattern.id):
                continue
            hits.append(BannedPatternHit(pattern=pattern, match=m.group(0), span=m.span()))
    hits.sort(key=lambda h: h.span[0])
    return hits


def format_hits(hits: Iterable[BannedPatternHit]) -> str:
    """Human-readable summary suitable for inclusion in a banned-pattern
    audit section of a research brief or audit response.
    """
    lines: list[str] = []
    for h in hits:
        lines.append(
            f"- **{h.pattern.title}** [{h.pattern.id}]\n"
            f"  - Match: `{h.match.strip()}`\n"
            f"  - Why: {h.pattern.why}\n"
            f"  - Suggested replacement: {h.pattern.replacement}"
        )
    return "\n".join(lines) if lines else "Clean — no banned patterns detected."
