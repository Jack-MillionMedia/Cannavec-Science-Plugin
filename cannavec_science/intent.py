"""User-intent classification.

A focused, keyword-driven classifier that picks the intent most likely
to apply to the user's prompt. The output is informational — surfaces
use it to pick an output template and to decide whether to ask a
clarifying question (e.g. asking for jurisdiction when intent is
LEGAL_STATUS).

If the classifier is unsure, it returns ``Intent.OPEN_QUESTION`` and
the surface should use a general template.
"""

from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    DEFINITION = "definition"
    COMPARISON = "comparison"
    DOSING = "dosing"
    INTERACTION = "interaction"
    MECHANISM = "mechanism"
    EFFICACY = "efficacy"
    SAFETY_RISK = "safety_risk"
    LEGAL_STATUS = "legal_status"
    HOW_TO_PROCEDURAL = "how_to_procedural"
    RECOMMENDATION = "recommendation"
    LITERATURE_REVIEW = "literature_review"
    PRODUCT_CLAIM_CHECK = "product_claim_check"
    OPEN_QUESTION = "open_question"


# Pattern order matters: more specific intents are tried first.
# DEFINITION is intentionally LAST among the strong matchers because
# "what is the dose" / "what is the mechanism" / "what are the risks"
# are dose / mechanism / safety questions, not definition questions.
_PATTERNS: tuple[tuple[Intent, re.Pattern[str]], ...] = (
    (Intent.COMPARISON, re.compile(
        r"\b(?:vs\.?|versus|compare|comparison|difference between|"
        r"which is better|how does .* compare)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.DOSING, re.compile(
        r"\b(?:dose|dosage|dosing|how much|how many mg|titrat\w*|"
        r"starting dose|maintenance dose)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.INTERACTION, re.compile(
        r"\b(?:drug interaction|interact\w*|interfer\w*|"
        r"warfarin|coumadin|cyp\d|metaboli\w*)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.MECHANISM, re.compile(
        # ``receptor\w*`` so the plural "receptors" matches too — "how does
        # X act on its receptors" is a textbook mechanism question.
        r"\b(?:mechanism|how does .* work|how does .* act|receptor\w*|"
        r"agoni\w*|antagoni\w*|binding|affinity|pathway|signal\w*)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.SAFETY_RISK, re.compile(
        r"\b(?:safe|safety|risk|risky|side effects?|adverse|"
        r"dangerous|harmful|contraindicat\w*)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.EFFICACY, re.compile(
        # "evidence for/in <condition>" is the canonical way a researcher
        # asks an efficacy question ("CBD evidence in Dravet"). Anchored to
        # for/in/base so it does not steal LITERATURE_REVIEW's "state of the
        # evidence" / "review the evidence".
        r"\b(?:does it work|is it effective|effective for|"
        r"efficacy|works for|help with|good for|"
        r"evidence\s+(?:for|in|base))\b",
        flags=re.IGNORECASE,
    )),
    (Intent.LEGAL_STATUS, re.compile(
        # Scope "schedule" / "controlled" to the controlled-substances
        # senses only — bare "schedule" false-positively matched cultivation
        # questions like "Cannabis cultivation light schedule flower stage"
        # in v2.6. "scheduled" alone (past-tense verb) is also too loose,
        # so we require either the controlled-substances roman numerals,
        # the "scheduled drug/substance/I/II..." compound, or the
        # explicit "rescheduling" / "schedule of" phrasing.
        r"\b(?:legal|illegal|legaliz\w*|legalis\w*|"
        r"schedule\s+(?:i{1,3}v?|iv|v|of\s+(?:cannabis|marijuana|"
        r"controlled))|"
        r"rescheduling|reschedul\w*|"
        r"scheduled\s+(?:drug|substance|narcotic)|"
        r"controlled\s+substance|controlled\s+drug|"
        r"jurisdiction|federally|state\s+law|"
        r"is\s+it\s+legal|prescription)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.LITERATURE_REVIEW, re.compile(
        r"\b(?:review the literature|systematic review|"
        r"meta-analysis|state of the evidence|"
        r"latest research|recent studies|bibliography)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.PRODUCT_CLAIM_CHECK, re.compile(
        r"\b(?:is it true that|fact check|verify|true or false)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.HOW_TO_PROCEDURAL, re.compile(
        r"\b(?:how (?:to|do i|do you|do we)|steps to|procedure for|"
        r"how can I|what's the best way to)\b",
        flags=re.IGNORECASE,
    )),
    (Intent.RECOMMENDATION, re.compile(
        r"\b(?:should I|recommend|recommendation|suggest|"
        r"best (?:strain|product|cultivar|method))\b",
        flags=re.IGNORECASE,
    )),
    (Intent.DEFINITION, re.compile(
        r"\b(?:what is|what are|what's|what does|what do|"
        r"define|definition of|explain|tell me about|describe)\b",
        flags=re.IGNORECASE,
    )),
)


def classify_intent(text: str) -> Intent:
    """First-match wins.

    The order of :data:`_PATTERNS` matters: more specific intents come
    first. This is good enough for routing; a tied or ambiguous case
    falls through to :attr:`Intent.OPEN_QUESTION`.
    """
    for intent, regex in _PATTERNS:
        if regex.search(text):
            return intent
    return Intent.OPEN_QUESTION


# Topic keywords used by `compose_answer` to filter multi-row
# registries (terpenes, etc.) to topic-relevant rows. Added by
# cannabis-insight-engine spec 001 User Story 3. The set is
# intentionally small and stable — adding new topics is a registry
# decision, not an open-ended NLP problem.
_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("sleep", re.compile(
        r"\b(?:sleep|sleepy|insomnia|sedat\w*|sedation|hypnotic|"
        r"drowsy|drowsiness|sleeplessness)\b",
        flags=re.IGNORECASE,
    )),
    ("pain", re.compile(
        r"\b(?:pain|analges\w*|nociceptive|neuropathic|chronic pain)\b",
        flags=re.IGNORECASE,
    )),
    ("anxiety", re.compile(
        r"\b(?:anxiet\w*|anxious|panic|stress|stressful|stressed)\b",
        flags=re.IGNORECASE,
    )),
    ("nausea", re.compile(
        r"\b(?:nausea|nauseous|vomit\w*|emesis|antiemetic|cinv)\b",
        flags=re.IGNORECASE,
    )),
    ("appetite", re.compile(
        r"\b(?:appetite|cachexia|anorexia|hunger|orexigen\w*|"
        r"appetite stimulat\w*)\b",
        flags=re.IGNORECASE,
    )),
    ("inflammation", re.compile(
        r"\b(?:inflam\w*|anti.?inflammator\w*|arthrit\w*)\b",
        flags=re.IGNORECASE,
    )),
    ("focus", re.compile(
        r"\b(?:focus|attention|concentration|alertness|"
        r"cognitive performance)\b",
        flags=re.IGNORECASE,
    )),
)


def topic_keywords(text: str) -> frozenset[str]:
    """Return the set of topic tags relevant to a prompt.

    Used by registries that carry per-row topic tags (currently
    terpenes; extensible) to filter what gets rendered. When the set
    is empty, callers fall back to their existing unfiltered behaviour
    — this preserves backwards compatibility for neutral queries like
    "What is the entourage effect?".
    """
    tags: set[str] = set()
    for tag, regex in _TOPIC_PATTERNS:
        if regex.search(text):
            tags.add(tag)
    return frozenset(tags)


# ── Indication / condition tags ─────────────────────────────────────────────
#
# A focused lexicon of the *named medical conditions* a researcher asks about,
# used to make claim selection indication-aware (Improvement: WP-RETRIEVAL #2).
# A condition word maps to one or more canonical tags; a *family* member also
# carries its family tag so a broad query and a specific row still overlap
# (e.g. "CBD for seizures" → {epilepsy} and the Dravet row → {epilepsy, dravet}
# overlap, while "CBD for Tourette" → {tourette} does not).
#
# The set is intentionally two-sided: it covers the curated indications (so an
# on-topic query's condition matches the curated row that answers it) AND the
# common OFF-knowledge-base indications a user is likely to probe (Tourette,
# Parkinson, glaucoma, autism, …). The latter are NOT curated, so naming one
# is precisely the signal that a recovered curated efficacy claim about a
# *different* condition must not be presented as the answer.
#
# This is a deliberately small, stable, high-precision list — a generic head
# noun alone ("syndrome", "disease", "disorder", "tremor", "tics") is NOT a
# condition tag, so it cannot make a wrong-indication row look on-topic.
_INDICATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ── curated indications (and their epilepsy family) ──
    ("epilepsy", re.compile(
        r"\b(?:epilep\w*|seizur\w*|convulsi\w*|"
        r"dravet|lennox.?gastaut|\bLGS\b|tuberous sclerosis|\bTSC\b|"
        r"drop.seizure\w*|epileptic encephalopath\w*)\b",
        flags=re.IGNORECASE,
    )),
    ("dravet", re.compile(r"\bdravet\b", flags=re.IGNORECASE)),
    ("lennox-gastaut", re.compile(
        r"\blennox.?gastaut\b|\bLGS\b", flags=re.IGNORECASE)),
    ("tsc", re.compile(
        r"\btuberous sclerosis\b|\bTSC\b", flags=re.IGNORECASE)),
    ("spasticity", re.compile(
        # Clinical term + spelled-out "multiple sclerosis" (each already tags
        # spasticity), PLUS lay phrasings gated on an MS cue so the lexicon
        # stays in lockstep with the populations detector (WS2). The MS
        # abbreviation is matched case-SENSITIVELY ((?-i:MS)) and the
        # hyphen/slash-glued forms (GC-MS, LC-MS/MS), the "ms" time unit, and
        # the "Ms" honorific are excluded; the lay cue requires a "muscle"/
        # "limb" qualifier — so a bare "spasm"/"rigidity" near a stray "ms"
        # cannot tag spasticity (precision).
        r"\bspasticit\w*|multiple sclerosis|"
        r"(?:(?<![\w/-])(?-i:MS)(?![\w/])).{0,40}\b(?:muscle stiffness|"
        r"muscle spasm\w*|muscle tightness|muscle rigidity|limb rigidity)\b|"
        r"\b(?:muscle stiffness|muscle spasm\w*|muscle tightness|"
        r"muscle rigidity|limb rigidity)\b.{0,40}"
        r"(?:(?<![\w/-])(?-i:MS)(?![\w/]))",
        flags=re.IGNORECASE,
    )),
    ("neuropathic_pain", re.compile(
        r"\bneuropath\w*|chronic\s+pain\b|nerve\s+pain|shooting\s+pain|"
        r"burning\s+pain|lancinating",
        flags=re.IGNORECASE)),
    ("nausea_vomiting", re.compile(
        r"\bnause\w*|vomit\w*|emesis|antiemetic|\bCINV\b|"
        r"chemo.?induced nausea\b",
        flags=re.IGNORECASE,
    )),
    ("cachexia_appetite", re.compile(
        r"\bcachexi\w*|wasting|appetite stimulat\w*|"
        r"anorexia.cachexia\b",
        flags=re.IGNORECASE,
    )),
    # ── common OFF-knowledge-base indications (named but not curated) ──
    ("tourette", re.compile(r"\btourett\w*\b", flags=re.IGNORECASE)),
    ("parkinson", re.compile(r"\bparkinson\w*\b", flags=re.IGNORECASE)),
    ("glaucoma", re.compile(r"\bglaucoma\b", flags=re.IGNORECASE)),
    ("autism", re.compile(
        r"\bautis\w*|\bASD\b|asperger\w*\b", flags=re.IGNORECASE)),
    ("fibromyalgia", re.compile(r"\bfibromyalgi\w*\b", flags=re.IGNORECASE)),
    ("als", re.compile(
        r"\bALS\b|amyotrophic lateral sclerosis|"
        r"motor neuron(?:e)? disease\b",
        flags=re.IGNORECASE,
    )),
    ("ibd", re.compile(
        r"\binflammatory bowel\b|\bIBD\b|ulcerative colitis\b",
        flags=re.IGNORECASE,
    )),
    ("crohn", re.compile(r"\bcrohn\w*\b", flags=re.IGNORECASE)),
    ("gvhd", re.compile(
        r"\bgraft.?versus.?host\b|\bGVHD\b", flags=re.IGNORECASE)),
    ("alzheimer", re.compile(
        r"\balzheimer\w*|dementia\b", flags=re.IGNORECASE)),
    ("migraine", re.compile(r"\bmigrain\w*\b", flags=re.IGNORECASE)),
    ("ptsd", re.compile(
        r"\bptsd\b|post.?traumatic stress\b", flags=re.IGNORECASE)),
    ("schizophrenia", re.compile(
        r"\bschizophreni\w*|psychosis\b", flags=re.IGNORECASE)),
    ("covid", re.compile(
        r"\bcovid\b|sars.?cov.?2|coronavirus\b", flags=re.IGNORECASE)),
)


def indication_terms(text: str) -> frozenset[str]:
    """Return the canonical condition tags named in ``text``.

    The tag set powers indication-aware claim selection (WP-RETRIEVAL #2):
    a recovered *clinical-efficacy* claim is on-topic only when its own
    condition tags overlap the prompt's. A query that names a condition the
    knowledge base does not curate (e.g. Tourette) yields a tag with no
    curated overlap, which is the signal to NOT present a curated claim about
    a different condition as the answer.

    Empty when the prompt names no recognised condition — callers then leave
    behaviour unchanged (the gate only fires on a *named* indication).
    """
    tags: set[str] = set()
    for tag, regex in _INDICATION_PATTERNS:
        if regex.search(text):
            tags.add(tag)
    return frozenset(tags)
