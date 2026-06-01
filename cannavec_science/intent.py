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
