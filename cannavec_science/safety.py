"""Safety preflight for cannabis questions.

Cannabis sits in a region where wrong information has real cost:
adolescent psychosis risk, pregnancy / lactation exposure, paediatric
dosing, drug-drug interactions (warfarin, immunosuppressants),
suicide / self-harm escalation, cannabis hyperemesis syndrome (CHS),
cardiovascular events. The safety guardrails here are deterministic
checks that fire on the *user's prompt* before any answer is generated,
so the surface can refuse, reframe, or add the right caution language.

The guardrails are intentionally permissive about education — Cannavec
should answer "what does the evidence say about cannabis in pregnancy?"
at population level. They refuse only when the question is *about the
user's own care* in a way that requires a clinician's judgement.

The output of :func:`check_safety` is a :class:`SafetyVerdict` listing
every flag that fired, with a recommended action (PROCEED, ADD_CAUTION,
REFRAME_TO_POPULATION, REFUSE_INDIVIDUALIZED, REFUSE_HARMFUL). The
caller decides what to do with it; this module does not produce prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Pattern


class SafetyAction(str, Enum):
    PROCEED = "proceed"
    ADD_CAUTION = "add_caution"
    REFRAME_TO_POPULATION = "reframe_to_population"
    REFUSE_INDIVIDUALIZED = "refuse_individualized"
    REFUSE_HARMFUL = "refuse_harmful"


class SafetyFlag(str, Enum):
    INDIVIDUALIZED_MEDICAL = "individualized_medical"
    INDIVIDUALIZED_DOSING = "individualized_dosing"
    INDIVIDUALIZED_INTERACTION = "individualized_interaction"
    PREGNANCY_LACTATION = "pregnancy_lactation"
    PAEDIATRIC = "paediatric"
    ADOLESCENT_THC = "adolescent_thc"
    ELDERLY = "elderly"
    PSYCHIATRIC = "psychiatric"
    CARDIOVASCULAR = "cardiovascular"
    HYPEREMESIS = "hyperemesis"
    DRIVING = "driving"
    OCCUPATIONAL = "occupational"
    SUICIDE_SELF_HARM = "suicide_self_harm"
    OPERATING_EQUIPMENT = "operating_equipment"
    OVERDOSE_QUESTION = "overdose_question"
    EXTRACTION_HAZARD = "extraction_hazard"
    ILLEGAL_ACQUISITION = "illegal_acquisition"
    DETECTION_EVASION = "detection_evasion"
    SYNTHETIC_CANNABINOID = "synthetic_cannabinoid"
    SYNTHETIC_CANNABINOID_SYNTHESIS = "synthetic_cannabinoid_synthesis"
    DELTA8_LEGAL_GRAY = "delta8_legal_gray"


@dataclass(frozen=True)
class FiredFlag:
    flag: SafetyFlag
    matched_text: str
    why: str
    action: SafetyAction


@dataclass
class SafetyVerdict:
    proceed: bool
    flags: tuple[FiredFlag, ...] = ()
    required_cautions: tuple[str, ...] = ()
    recommended_action: SafetyAction = SafetyAction.PROCEED

    @property
    def refused(self) -> bool:
        return self.recommended_action in (
            SafetyAction.REFUSE_INDIVIDUALIZED,
            SafetyAction.REFUSE_HARMFUL,
        )


# ── Regex helpers ───────────────────────────────────────────────────────

def _ci(p: str) -> Pattern[str]:
    return re.compile(p, flags=re.IGNORECASE | re.DOTALL)


# Second-person framings that indicate "about a specific individual's care"
# (the user themselves, a family member, a named hypothetical patient, etc.).
_SECOND_PERSON = _ci(
    r"\b(?:i|i'm|im|i am|me|my|mine|myself|"
    r"should i|can i|may i|will i|"
    r"would i|could i|am i|is it safe for me|"
    r"is it ok for me|is it okay for me|"
    r"is it bad for me|do i need|"
    r"i (?:have|got|take|took|use|used|smoke|smoked|"
    r"vape|vaped|consume|consumed)|"
    r"my (?:dose|dosage|prescription|condition|"
    r"doctor|symptoms?|medication|meds|child|kid|son|daughter|"
    r"pregnan\w*|wife|husband|partner)|"
    r"a (?:patient|client|user)|"
    r"this (?:patient|client|person|user)|"
    r"should we|can we|may we|"
    r"give (?:them|him|her) cannabis|"
    r"give (?:to )?(?:a |the )?(?:patient|person))\b"
)

_DOSE_ASKING = _ci(
    # A dosing question is personal only when it combines a quantity ask
    # with a volitional modal ("should", "would", "can/may I", "to take").
    # Research questions ("how much was used in trial X", "what dose is
    # in Epidiolex") use factual/state verbs and do NOT match these
    # patterns. This prevents refusing legitimate research queries.
    r"\b(?:"
    # "how much … should/would/can I/to take" within 80 chars
    r"how much\b[^.\n]{0,80}\b(?:should|would|can i\b|may i\b|to take\b)\b"
    r"|"
    # "how many [units] … should/would/to take" within 40 chars
    r"how many (?:mg|milligrams|grams|hits|puffs|tokes|drops|gummies|edibles)"
    r"\b[^.\n]{0,40}\b(?:should|would|can i\b|may i\b|to take\b)\b"
    r"|"
    # "what dose/dosage/amount … should … [I/you/patient/beginner/person]"
    r"what (?:dose|dosage|amount)\b[^.\n]{0,40}\b(?:should|would)\b"
    r"[^.\n]{0,40}\b(?:i\b|you\b|we\b|a (?:patient|person|beginner|user|novice))\b"
    r"|"
    # Direct personal take request
    r"what should (?:i|my (?:child|kid|son|daughter)) take\b"
    r")"
)


# Imperative-form individualized-dosing detector. Closes the 2026-05-19
# Oracle Evaluator §4.8 finding that prompts like "Take 25 mg of THC
# for chronic pain" sailed through check_safety because the existing
# detectors required a second-person pronoun or a volitional modal.
# Imperative voice IS the instruction form — the prompt is functionally
# a personalised dose recommendation phrased as a command. Treat it
# as REFUSE_INDIVIDUALIZED.
_IMPERATIVE_DOSING = _ci(
    r"(?:^|[.!?]\s+)"
    r"(?:take|start(?:\s+with)?|use|inhale|vape|smoke|eat|swallow|"
    r"chew|dose|titrate|consume|drink|try)"
    r"\s+"
    r"(?:[0-9]+(?:\.[0-9]+)?|a\s+|one\s+|two\s+|three\s+|four\s+|five\s+)"
    r"[^.\n]{0,60}"
    r"\b(?:mg|g|grams?|milligrams?|ml|mL|µg|micrograms?|"
    r"hit|hits|puff|puffs|drop|drops|gummy|gummies|edible|edibles|"
    r"dose|doses|drag|drags|toke|tokes)\b"
)

# Carve out non-clinical lab / agronomy / culinary imperatives so
# legitimate professional prompts don't trip the imperative detector.
_IMPERATIVE_LAB_CARVEOUT = _ci(
    r"\b(?:take|start|use|run|read)\s+"
    r"(?:a\s+|an\s+|the\s+)?"
    r"(?:sample|aliquot|reading|measurement|chromatogram|cutting|"
    r"clone|cross|seedling|experiment|seed|seeds|cuttings|"
    r"hplc|gc|temperature|temp)"
)

_INTERACTION_ASKING = _ci(
    r"\b(?:i (?:take|am (?:on|taking)|use)|"
    r"i'm on)\b[^.\n]{0,80}\b"
    r"(?:warfarin|coumadin|ssri|fluoxetine|sertraline|"
    r"clobazam|valproate|tacrolimus|lithium|methadone|"
    r"oxycodone|hydrocodone|tramadol|benzodiazepines?|"
    r"xanax|valium|adderall|ritalin|metformin|insulin|"
    r"chemo\w*|blood thinner)\b"
    r"|"
    r"\b(?:can|may|will) (?:cannabis|weed|marijuana|cbd|thc)\b[^.\n]{0,60}\b"
    r"(?:interact|interfere)\b[^.\n]{0,60}\bmy\b"
)

_PREGNANCY_LACTATION = _ci(
    r"\b(?:pregnan\w*|expecting|gestat\w*|trimester|"
    r"breast[-\s]?feed\w*|nursing|lactat\w*|"
    r"trying to conceive|ttc|in vitro|ivf|fertility)\b"
)

_PAEDIATRIC = _ci(
    r"\b(?:child|kid|kids|infant|baby|babies|"
    r"toddler|paediatric|pediatric|paeds|peds|"
    r"under (?:18|21)|teen|teenager|adolescent|"
    r"my (?:son|daughter|child|kid)|"
    r"\d{1,2}[\s-]year[-\s]?old|"
    # Named paediatric epileptic encephalopathies — Dravet syndrome and
    # Lennox-Gastaut typically present in infancy/early childhood and
    # are the labelled paediatric indications for CBD (Epidiolex).
    r"dravet|lennox.gastaut|tuberous sclerosis|cdkl5|"
    r"infantile spasm|west syndrome|aicardi|sturge.weber)\b"
)

_ADOLESCENT_BRAIN_RISK = _ci(
    r"\b(?:teens?|teenagers?|adolescents?|youths?|young (?:person|adult)s?|"
    r"under (?:18|21|25))\b[^.\n]{0,120}\b"
    r"(?:thc|cannabis|weed|marijuana|smoke|smoking|vape|vaping)\b"
    r"|"
    r"\b(?:thc|cannabis|weed|marijuana)\b[^.\n]{0,120}\b"
    r"(?:teens?|teenagers?|adolescents?|youths?|under (?:18|21|25))\b"
)

_ELDERLY = _ci(
    r"\b(?:elderly|geriatric|older adult|senior(?:s)?|"
    r"my (?:mother|father|mom|dad|grandma|grandpa|"
    r"grandparent|parent)|"
    r"over (?:65|70|75|80))\b"
)

_PSYCHIATRIC = _ci(
    r"\b(?:schizophreni\w*|psychosis|psychotic|"
    r"bipolar|mania|manic|"
    r"severe depression|suicid\w*|self[-\s]?harm|"
    r"family history of (?:schizophrenia|psychosis|bipolar))\b"
)

_SUICIDE_SELF_HARM = _ci(
    r"\b(?:kill (?:myself|yourself|himself|herself|themselves)|"
    r"end (?:it|my life|things)|"
    r"suicid\w*|self[-\s]?harm|"
    r"don't want to (?:live|be alive)|"
    r"better off (?:dead|without me))\b"
)

_CARDIOVASCULAR = _ci(
    r"\b(?:heart (?:attack|disease|condition|failure)|"
    r"angina|arrhythmia|tachycardia|atrial fibrillation|"
    r"a[-\s]?fib|stroke|tia|hypertension|blood pressure|"
    r"coronary|cardiovascular)\b"
)

_HYPEREMESIS = _ci(
    r"\b(?:hyperemesis|chs|cannabis hyperemesis|"
    r"can't stop (?:throwing up|vomiting)|"
    r"cyclic vomiting)\b"
)

_DRIVING = _ci(
    # The driving flag is for cannabis-and-vehicle questions, not for
    # the verb "drive" used metaphorically (e.g. "tax rates drive
    # consumers to the illicit market"). The word "driving" appears
    # frequently in non-vehicle contexts ("factors driving market
    # growth", "policies driving demand"). We only match when a
    # vehicle/impairment/risk cue is present alongside the drive* form.
    #
    # Four branches:
    #   1. drive* preceded or followed by post-use framing ("after using")
    #   2. drive* co-occurring with impairment / risk / safety / ability
    #   3. drive* co-occurring with vehicle/DUI hardware cues
    #   4. Explicit impaired-driving idioms (DUI, behind the wheel, etc.)
    # Branch 1a: drive* then "after [use verb]"
    r"\bdriv\w*\b[^.\n]{0,80}\bafter (?:use|using|smoking|vaping|consuming|taking|eating)\b"
    r"|"
    # Branch 1b: "after [use verb]" then drive*
    r"\bafter (?:use|using|smoking|vaping|consuming|taking|eating)\b[^.\n]{0,60}\bdriv\w*\b"
    r"|"
    # Branch 1c: drive* then "after [cannabis substance]" (e.g. "drive after CBD oil")
    r"\bdriv\w*\b[^.\n]{0,50}\bafter\b[^.\n]{0,40}"
    r"\b(?:cannabis|weed|marijuana|cbd|thc|edible|gummy|tincture)\b"
    r"|"
    # Branch 2a: impairment/risk word then drive*
    r"\b(?:impair\w*|affect|influenc\w*|performance|ability|safe\w*|unsafe|risks?)\b"
    r"[^.\n]{0,60}\bdriv\w*\b"
    r"|"
    # Branch 2b: drive* then impairment/risk word
    r"\bdriv\w*\b[^.\n]{0,60}"
    r"\b(?:impair\w*|affect|influenc\w*|performance|ability|safe\w*|unsafe|risks?)\b"
    r"|"
    r"\bdriv\w*\b[^.\n]{0,60}\b(?:vehicle|car|truck|motorcycle|dui|duii|"
    r"under the influence|license|licence)\b"
    r"|"
    r"\b(?:behind the wheel|operating (?:a vehicle|machinery)|"
    r"dui|duii|impaired driving|driving under the influence)\b"
)

_OVERDOSE = _ci(
    r"\b(?:overdos\w*|too much|lethal dose|"
    r"can(?:'t| not)? handle|"
    r"green out|whitey|whitied|"
    r"how (?:much|many) (?:would|to) (?:kill|overdose|harm))\b"
)

# Flammable-solvent home extraction is a fire / explosion hazard
# (§V REFUSE_HARMFUL). The original pattern only gated a handful of
# product nouns ("hash oil|shatter|wax|live resin") and "butane
# (extraction|hash)", so DEFECT #9 — a solvent extraction framed around
# the everyday product noun "THC oil" / "cannabis oil" / "cannabis
# extract" — slipped through to live fan-out.
#
# The hazard is a *flammable solvent applied to cannabis to make a
# concentrate*. To stay high-precision (and not refuse benign chemistry
# prose like "propane prices are running high" or "the GC method was run
# with hexane"), the broadened branches require BOTH a flammable solvent
# AND a cannabis substrate / concentrate-product cue, joined by an
# extraction action OR adjacency. Pure solvent chemistry with no cannabis
# context proceeds.
_EXTRACTION_SOLVENT = (
    r"(?:bho|butane|propane|hexane|naphtha|"
    r"petroleum ether|pentane|isobutane|n-butane)"
)
# Things the solvent is applied to: the plant substrate or the concentrate
# product. This cannabis/product cue is what separates a home-extraction
# hazard from generic solvent chemistry.
_EXTRACTION_TARGET = (
    r"(?:hash oil|hashish oil|shatter|budder|crumble|"
    r"live resin|live rosin|thc oil|cannabis oil|cannabis extract|"
    r"weed oil|marijuana oil|concentrate|distillate|crude oil|"
    r"rso|rick simpson oil|dabs?|honey oil|"
    r"cannabis|marijuana|weed|flower|trim|bud|kief|plant material|"
    r"trichomes?)"
)
_EXTRACTION_ACTION = (
    r"(?:extract\w*|blast\w*|purg\w*|wash\w*|run\b|running\b|"
    r"soak\w*|strip\w*|dissolv\w*|process\w*|"
    r"make|making|produc\w*)"
)
# Concentrate *products* only (the output of a solvent extraction). A
# flammable solvent directly next to one of these names is the home-BHO
# hazard even without an explicit action verb. The bare plant ("cannabis",
# "weed", "flower") is deliberately excluded here so it can only fire via
# the action-verb branches above — this prevents an incidental
# solvent-mention + "cannabis" elsewhere in a sentence from refusing.
_EXTRACTION_CONCENTRATE = (
    r"(?:hash oil|hashish oil|shatter|budder|crumble|"
    r"live resin|live rosin|thc oil|cannabis oil|cannabis extract|"
    r"weed oil|marijuana oil|concentrate|distillate|"
    r"rso|rick simpson oil|dabs?|honey oil)"
)
_EXTRACTION_HAZARD = _ci(
    r"\b(?:bho|butane (?:extraction|hash)|blasting|"
    r"open[-\s]?blast|open blasting|"
    r"closed[-\s]?loop extractor|"
    r"how to (?:make|extract|process) (?:hash oil|shatter|wax|live resin))\b"
    r"|"
    # Branch A (DEFECT #9): flammable solvent + extraction action +
    # cannabis/product target, in any of the natural orders. Requiring
    # the target cue keeps benign solvent chemistry from refusing.
    rf"\b{_EXTRACTION_SOLVENT}\b[^.\n]{{0,40}}\b{_EXTRACTION_ACTION}\b[^.\n]{{0,40}}\b{_EXTRACTION_TARGET}\b"
    r"|"
    rf"\b{_EXTRACTION_ACTION}\b[^.\n]{{0,40}}\b{_EXTRACTION_TARGET}\b[^.\n]{{0,40}}\b{_EXTRACTION_SOLVENT}\b"
    r"|"
    rf"\b{_EXTRACTION_ACTION}\b[^.\n]{{0,40}}\b{_EXTRACTION_SOLVENT}\b[^.\n]{{0,40}}\b{_EXTRACTION_TARGET}\b"
    r"|"
    rf"\b{_EXTRACTION_TARGET}\b[^.\n]{{0,40}}\b{_EXTRACTION_ACTION}\b[^.\n]{{0,40}}\b{_EXTRACTION_SOLVENT}\b"
    r"|"
    # Branch B (DEFECT #9): flammable solvent directly adjacent to a
    # *concentrate product* noun (the "purge the butane out of my BHO
    # concentrate" / "THC oil with butane" shape) — the extraction action
    # is implicit in the solvent+concentrate pairing, so no action verb is
    # required. Restricted to concentrate products (NOT the bare plant) so
    # "boiling point of butane" + "cannabis" in separate clauses can't trip.
    rf"\b{_EXTRACTION_SOLVENT}\b[^.\n]{{0,40}}\b{_EXTRACTION_CONCENTRATE}\b"
    r"|"
    rf"\b{_EXTRACTION_CONCENTRATE}\b[^.\n]{{0,40}}\b{_EXTRACTION_SOLVENT}\b"
)

_ILLEGAL_ACQUISITION = _ci(
    r"\b(?:where (?:can|do) (?:i|we) (?:buy|get|find) (?:weed|cannabis|marijuana))\b"
    r"|"
    r"\b(?:how (?:to|do (?:i|you|we))\s+"
    r"(?:smuggle|traffic|illegally (?:buy|sell|grow|transport)))\b"
)

_DETECTION_EVASION = _ci(
    r"\bbeat (?:a |the )?(?:drug|piss|urine|hair|saliva)"
    r"(?:[\s-]+(?:drug|piss|urine|hair|saliva))?\s+test\b"
    r"|"
    r"\bpass (?:a |the )?(?:drug|piss|urine|hair|saliva)"
    r"(?:[\s-]+(?:drug|piss|urine|hair|saliva))?\s+test\b"
    r"|"
    r"\b(?:detox kits?|synthetic urine|"
    r"avoid detection|"
    r"hide (?:weed|cannabis|marijuana) (?:from|in))\b"
)

_OCCUPATIONAL = _ci(
    # Safety-sensitive occupations: any cannabis-use question framed
    # around a named safety-sensitive role, employer requirement, or
    # federally-mandated drug-testing programme.
    # Note: commercial driving / operating heavy machinery is also
    # captured by the DRIVING flag via "operating machinery".
    r"\b(?:pilots?|aviation|airline|fly(?:ing)? (?:a plane|an aircraft)|"
    r"train drivers?|train operators?|air traffic control|atc|"
    r"commercial drivers?|cdl\b|commercial driver(?:'s)? licen[sc]e|"
    r"dot(?:\s+drug)?\s+test|dot drug|department of transportation|fmcsa|"
    r"faa drug|aviation drug|"
    r"surgeons?|operating theatre|operating room|"
    r"nuclear plant|nuclear facility|nuclear operator|power plant operator|"
    r"armed forces|military (?:service|personnel)|"
    r"law enforcement officer|police officer|"
    r"federal contractor|federal employee cannabis|"
    r"security clearance|drug.?free workplace|"
    r"workplace(?:\s+(?:drug|cannabis))?\s+polic(?:y|ies)|"
    r"employer(?:'s)?\s+drug\s+polic|"
    r"safety.?sensitive (?:jobs?|occupations?|roles?|positions?|employment|work)|"
    r"zero.tolerance (?:jobs?|employers?|workplaces?|policy|policies)|"
    r"random drug test at work|workplace drug tests?)\b"
)

_OPERATING_EQUIPMENT = _ci(
    # Heavy machinery / industrial equipment contexts not already captured
    # by the DRIVING flag.
    r"\b(?:forklift|crane operator|heavy equipment operator|"
    r"excavator|bulldozer|dump truck|"
    r"construction site|"
    r"operating heavy (?:equipment|machinery)|"
    r"heavy plant operator)\b"
)

# Synthetic cannabinoid receptor agonists (K2, Spice, and related
# designer cannabinoids) are structurally and toxicologically distinct
# from plant-derived cannabinoids. Documented risks include severe
# psychosis, cardiovascular events, coagulopathy, and death. Evidence
# from cannabis research does not transfer.
_SYNTHETIC_CANNABINOID = _ci(
    r"\b(?:k2\b|spice\b|synthetic cannabinoid|synthetic cannabis|"
    r"synthetic marijuana|designer cannabinoid|"
    r"jwh[-\s]?\d+|am[-\s]?\d+|am-2201|"
    r"ab[-\s]?fubinaca|ab[-\s]?chminaca|ab-pinaca|"
    r"mdmb[-\s]?4en[-\s]?pinaca|5f[-\s]?mdmb[-\s]?2201|"
    r"5f-adb|5f-mdmb-pinaca|ur-144|xlt-11|pb-22|"
    r"fake weed|fake pot|legal high|bath salt|"
    r"herbal incense(?:\s+drug)?)\b"
)

# Synthesis / procurement intent paired with a synthetic cannabinoid
# name. Educational questions about K2/Spice/JWH risk profile stay at
# ADD_CAUTION (handled by _SYNTHETIC_CANNABINOID). Step-by-step
# synthesis or home-production intent — which has driven mass-casualty
# outbreaks — escalates to REFUSE_HARMFUL.
_SYNTH_VERB = (
    r"(?:synthesi[sz]e|synthesi[sz]ing|synthesis of|"
    r"make|making|produce|producing|production of|"
    r"manufactur\w*|cook(?:ing)?|brew(?:ing)?|"
    r"prepare|preparing|preparation of|"
    r"how to (?:get|obtain|buy|acquire|order|source)|"
    r"where (?:to|can i|do i) (?:get|buy|order|find|source))"
)
_SYNTH_CANN_NAMES = (
    r"(?:synthetic cannabinoids?|synthetic cannabis|"
    r"synthetic marijuana|designer cannabinoids?|"
    r"k2\b|spice\b|jwh[-\s]?\d+|am[-\s]?\d+|am-2201|"
    r"ab[-\s]?fubinaca|ab[-\s]?chminaca|ab-pinaca|"
    r"mdmb[-\s]?4en[-\s]?pinaca|5f[-\s]?mdmb[-\s]?2201|"
    r"5f-adb|5f-mdmb-pinaca|ur-144|xlt-11|pb-22|"
    r"fake weed|fake pot|herbal incense)"
)
# Noun-head framings of a synthesis route. The verb-only `_SYNTH_VERB`
# detector let prompts like "synthesis route for X", "reaction scheme
# for X", "synthetic route to X", "synthesis protocol for X" bypass the
# §V hard-refuse while routing into the live network. These noun heads
# carry the same instruction intent in declarative dress. Critically,
# the noun head is ALWAYS co-gated with `_SYNTH_CANN_NAMES` below, so a
# plant phytochemistry question ("biosynthesis of THCA", "reaction
# scheme for THCA decarboxylation") can never trip it — THCA/CBD/CBGA
# are not in the designer-cannabinoid name list. `synthesis` is
# matched with a leading boundary that a preceding "bio" defeats, as a
# second layer of defence for plant-biosynthesis prose.
_SYNTH_NOUN_HEAD = (
    r"(?:"
    r"(?<![a-z])synthesis(?:\s+(?:route|scheme|protocol|procedure|"
    r"pathway|method|recipe|steps?))?"
    r"|synthetic\s+(?:route|pathway|scheme|procedure|protocol)"
    r"|total\s+synthesis"
    r"|reaction\s+scheme"
    r"|lab(?:oratory)?\s+(?:protocol|procedure|scheme|recipe)"
    r")"
)
_SYNTHETIC_CANNABINOID_SYNTHESIS = _ci(
    # Branch 1: synthesis verb before the cannabinoid name.
    rf"\b{_SYNTH_VERB}\b[^.\n]{{0,80}}\b{_SYNTH_CANN_NAMES}\b"
    r"|"
    # Branch 2: cannabinoid name before a synthesis verb or
    # home-production marker.
    rf"\b{_SYNTH_CANN_NAMES}\b[^.\n]{{0,80}}\b(?:{_SYNTH_VERB}|at home|"
    r"in (?:my|a) (?:garage|basement|kitchen|lab)|home[-\s]?lab|"
    r"homemade|diy|step[-\s]?by[-\s]?step|recipe)\b"
    r"|"
    # Branch 3: home-production marker before the cannabinoid name
    # (e.g. "step-by-step JWH-018 production").
    r"\b(?:step[-\s]?by[-\s]?step|recipe (?:for|to)|diy|home[-\s]?lab|"
    r"homemade)\b"
    rf"[^.\n]{{0,80}}\b{_SYNTH_CANN_NAMES}\b"
    r"|"
    # Branch 4 (DEFECT #4): synthesis NOUN-HEAD before the cannabinoid
    # name (e.g. "synthesis route for AB-FUBINACA", "reaction scheme
    # for JWH-018", "total synthesis of 5F-MDMB-PINACA").
    rf"\b{_SYNTH_NOUN_HEAD}\b[^.\n]{{0,80}}\b{_SYNTH_CANN_NAMES}\b"
    r"|"
    # Branch 5 (DEFECT #4): cannabinoid name before the synthesis
    # noun-head (e.g. "JWH-018 synthesis route", "AB-FUBINACA scheme").
    rf"\b{_SYNTH_CANN_NAMES}\b[^.\n]{{0,80}}\b{_SYNTH_NOUN_HEAD}\b"
)

# Delta-8 / delta-10 THC and related semi-synthetic cannabinoids are a
# legal gray area in many jurisdictions. Their safety data are thinner
# than delta-9, and their legal status under the Farm Bill and state
# law is actively contested.
_DELTA8_GRAY_AREA = _ci(
    r"\b(?:delta[-\s]?8|delta[-\s]?10|d8\b|d10\b|"
    r"delta[-\s]?8[-\s]?thc|delta[-\s]?10[-\s]?thc|"
    r"delta8|delta10|thc[-\s]?o|thco|hhc\b|"
    r"hexahydrocannabinol)\b"
)


_FLAG_RULES: tuple[tuple[Pattern[str], SafetyFlag, str, SafetyAction], ...] = (
    # Refuse-harmful first (highest precedence).
    (_SUICIDE_SELF_HARM, SafetyFlag.SUICIDE_SELF_HARM,
     "Mentions of suicide or self-harm require an immediate crisis-resources "
     "response, not a cannabis answer.",
     SafetyAction.REFUSE_HARMFUL),
    (_EXTRACTION_HAZARD, SafetyFlag.EXTRACTION_HAZARD,
     "Solvent-based extraction (BHO, open-blasting) is a fire/explosion "
     "hazard. Cannavec does not provide step-by-step procedures.",
     SafetyAction.REFUSE_HARMFUL),
    (_DETECTION_EVASION, SafetyFlag.DETECTION_EVASION,
     "Cannavec does not help users evade workplace, court-ordered, or "
     "regulatory drug testing.",
     SafetyAction.REFUSE_HARMFUL),
    (_ILLEGAL_ACQUISITION, SafetyFlag.ILLEGAL_ACQUISITION,
     "Cannavec does not direct users to unlicensed, illegal, or "
     "untested sources of supply.",
     SafetyAction.REFUSE_HARMFUL),
    # Synthetic cannabinoid SYNTHESIS / home-production intent: hard
    # refusal. The K2/Spice family has driven mass-casualty outbreaks
    # (severe psychosis, coagulopathy, cardiotoxicity, fatalities).
    # Step-by-step synthesis instructions for these compounds are out
    # of scope under any framing. This rule precedes the educational
    # ADD_CAUTION rule below so synthesis-intent takes precedence.
    (_SYNTHETIC_CANNABINOID_SYNTHESIS, SafetyFlag.SYNTHETIC_CANNABINOID_SYNTHESIS,
     "Cannavec does not provide synthesis routes, home-production "
     "procedures, or sourcing pathways for synthetic cannabinoid "
     "receptor agonists (K2, Spice, JWH, AM, AB-FUBINACA, MDMB family, "
     "etc.). These compounds have caused mass-casualty outbreaks "
     "including severe psychosis, coagulopathy, and death. For acute "
     "exposure, contact Poison Control (US: 1-800-222-1222).",
     SafetyAction.REFUSE_HARMFUL),
    # Synthetic cannabinoids: caution, not refusal. They warrant
    # an explicit population-level harm clarification and a strong
    # warning that evidence from cannabis studies does not transfer to
    # synthetic cannabinoids. Cannavec can describe the risk profile at
    # population level and refer users to toxicology / poison-control.
    (_SYNTHETIC_CANNABINOID, SafetyFlag.SYNTHETIC_CANNABINOID,
     "Synthetic cannabinoids (K2, Spice, designer cannabinoids) are "
     "structurally and toxicologically distinct from plant-derived "
     "cannabis. Evidence from cannabis research does not transfer. "
     "Documented risks include severe psychosis, cardiovascular events, "
     "coagulopathy, and death. Refer to Poison Control (US: 1-800-222-1222) "
     "for acute exposure. Do not conflate with plant-derived cannabis.",
     SafetyAction.ADD_CAUTION),

    # Refuse-individualized: drug-interaction questions framed in first
    # person always require clinician review.
    # Refuse-individualized — patterns that are inherently first-person.
    # _DOSE_ASKING is intentionally ADD_CAUTION here, not REFUSE_INDIVIDUALIZED.
    # The escalation to REFUSE_INDIVIDUALIZED happens via
    # is_individualized_medical_question when second-person context is present.
    # Keeping it at ADD_CAUTION prevents false positives on population-level
    # research questions that contain "how much" or "what dose" without
    # self-referential framing (e.g., "What dose was used in the Dravet trial?").
    # Refuse-individualized — patterns that are inherently personal in framing.
    # _INTERACTION_ASKING requires "I take/am on" or "my" medication phrasing
    # so it is already second-person and warrants direct refusal.
    # Refuse-individualized — only patterns that are unambiguously personal.
    (_INTERACTION_ASKING, SafetyFlag.INDIVIDUALIZED_INTERACTION,
     "Drug-interaction questions about the user's own medications need "
     "a clinician with access to their full medication list.",
     SafetyAction.REFUSE_INDIVIDUALIZED),

    # Dose-asking: ADD_CAUTION at this layer.
    # Population-level dose questions ("how much edible THC should a beginner
    # take?") are legitimate educational questions — refusing them is a false
    # positive. The is_individualized_medical_question() check below promotes
    # dose questions to REFUSE_INDIVIDUALIZED when second-person framing is
    # present (e.g. "I'm new to edibles. How much should I take?").
    (_DOSE_ASKING, SafetyFlag.INDIVIDUALIZED_DOSING,
     "Individual dosing is a clinician decision. Cannavec reports "
     "trial-supported population dose ranges; it never recommends a "
     "personal dose. Refer all dosing decisions to a clinician.",
     SafetyAction.ADD_CAUTION),
    (_DELTA8_GRAY_AREA, SafetyFlag.DELTA8_LEGAL_GRAY,
     "Delta-8 THC, delta-10 THC, THCO, HHC and related semi-synthetic "
     "cannabinoids occupy a contested legal gray zone. Their Farm Bill "
     "status and state-level legality are actively disputed; safety data "
     "are much thinner than for delta-9 THC. Cannavec flags date-sensitivity "
     "and limited safety evidence whenever these compounds are mentioned.",
     SafetyAction.ADD_CAUTION),

    # Add-caution.
    (_OCCUPATIONAL, SafetyFlag.OCCUPATIONAL,
     "Occupational, professional licensing, and federal contexts (DOT, CDL, "
     "FAA, federal contractors) impose cannabis restrictions that may differ "
     "from state law; legal and employment-law counsel is appropriate for "
     "individual situations.",
     SafetyAction.ADD_CAUTION),
    (_PREGNANCY_LACTATION, SafetyFlag.PREGNANCY_LACTATION,
     "Cannabinoids cross the placenta and are excreted in breast milk; "
     "ACOG/RCOG/SOGC default is avoidance.",
     SafetyAction.ADD_CAUTION),
    (_PAEDIATRIC, SafetyFlag.PAEDIATRIC,
     "Paediatric cannabis exposure (medical or accidental) has its own "
     "dose ranges and risk profile and must be supervised by a paediatric "
     "neurologist / clinician.",
     SafetyAction.ADD_CAUTION),
    (_ADOLESCENT_BRAIN_RISK, SafetyFlag.ADOLESCENT_THC,
     "Adolescent THC exposure is associated with elevated risk of "
     "psychotic disorder, cognitive effects, and dependence; absolute "
     "magnitude is debated but the direction is consistent.",
     SafetyAction.ADD_CAUTION),
    (_ELDERLY, SafetyFlag.ELDERLY,
     "Elderly patients are more sensitive to THC-induced orthostatic "
     "effects, cognitive effects, and drug interactions.",
     SafetyAction.ADD_CAUTION),
    (_PSYCHIATRIC, SafetyFlag.PSYCHIATRIC,
     "Personal or family history of psychosis / bipolar is a recognised "
     "risk factor for THC-associated psychiatric events.",
     SafetyAction.ADD_CAUTION),
    (_CARDIOVASCULAR, SafetyFlag.CARDIOVASCULAR,
     "THC is associated with dose-dependent tachycardia and orthostatic "
     "hypotension; caution in unstable cardiovascular disease.",
     SafetyAction.ADD_CAUTION),
    (_HYPEREMESIS, SafetyFlag.HYPEREMESIS,
     "Cannabis hyperemesis syndrome is paradoxical and requires "
     "cessation, not adjustment of cannabis use.",
     SafetyAction.ADD_CAUTION),
    (_DRIVING, SafetyFlag.DRIVING,
     "Cannabis impairs driving for hours after use; legal thresholds "
     "vary by jurisdiction.",
     SafetyAction.ADD_CAUTION),
    (_OPERATING_EQUIPMENT, SafetyFlag.OPERATING_EQUIPMENT,
     "Operating heavy equipment (forklift, crane, excavator) while "
     "impaired by cannabis is an occupational and public safety hazard.",
     SafetyAction.ADD_CAUTION),
    (_OVERDOSE, SafetyFlag.OVERDOSE_QUESTION,
     "Acute cannabis intoxication is rarely lethal but can be severely "
     "distressing; provide non-judgemental harm-reduction context.",
     SafetyAction.ADD_CAUTION),
)


_INDIVIDUALIZED_HINT = (_SECOND_PERSON, _DOSE_ASKING, _INTERACTION_ASKING)


def is_individualized_medical_question(text: str) -> bool:
    """True if the question is about the user's own care.

    A second-person framing alone is not enough — "how should I cite
    this?" is not individualised medical. The check requires a
    second-person framing *plus* a medical-decision verb (take, dose,
    use, smoke, vape, etc.), or an explicit ask for dose / interaction
    / safety-for-me.
    """
    has_second_person = bool(_SECOND_PERSON.search(text))
    if not has_second_person:
        return False
    medical_verbs = _ci(
        r"\b(?:take|taking|took|use|using|used|smoke|smoking|smoked|"
        r"vape|vaping|vaped|consume|consuming|consumed|"
        r"start|starting|stop|stopping|"
        r"dose|dosing|microdose|microdosing|"
        r"safe|risky|risk|interact|interaction|"
        r"add|adding|added|combine|combining|combined|"
        r"mix|mixing|mixed|switch|switching|switched|"
        r"give|giving|gave|try|trying|tried|"
        r"continue|continuing|increase|increasing|"
        r"decrease|decreasing|reduce|reducing|"
        r"prescribe|prescribed|prescribing|recommend|recommended)\b"
    )
    if medical_verbs.search(text):
        return True
    if _DOSE_ASKING.search(text) or _INTERACTION_ASKING.search(text):
        return True
    return False


def check_safety(text: str) -> SafetyVerdict:
    """Run every safety check and return the aggregated verdict.

    Precedence: REFUSE_HARMFUL > REFUSE_INDIVIDUALIZED > ADD_CAUTION.
    The verdict's ``recommended_action`` is the highest-precedence
    action that fired. The verdict's ``flags`` lists every check that
    fired, in document order.
    """
    fired: list[FiredFlag] = []
    cautions: list[str] = []

    for regex, flag, why, action in _FLAG_RULES:
        m = regex.search(text)
        if not m:
            continue
        fired.append(FiredFlag(
            flag=flag,
            matched_text=m.group(0),
            why=why,
            action=action,
        ))
        if action == SafetyAction.ADD_CAUTION:
            cautions.append(why)

    # Imperative-form individualized dosing. Closes the 2026-05-19
    # Oracle Evaluator §4.8 finding that "Take 25 mg of THC for chronic
    # pain" sailed through because the second-person detector required
    # "I" / "my" / "should I" framing. Imperative voice IS the
    # instruction form — the prompt functionally tells a user to take
    # a specific dose, which Cannavec must refuse. Lab / agronomy /
    # culinary carve-outs preserve legitimate professional prompts.
    if (_IMPERATIVE_DOSING.search(text)
            and not _IMPERATIVE_LAB_CARVEOUT.search(text)):
        if not any(f.action == SafetyAction.REFUSE_INDIVIDUALIZED
                   for f in fired):
            fired.append(FiredFlag(
                flag=SafetyFlag.INDIVIDUALIZED_DOSING,
                matched_text=text[:120],
                why=(
                    "Prompt uses imperative-form dosing instruction "
                    "(e.g. 'Take 25 mg of THC for chronic pain') — "
                    "functionally a personalised dose recommendation "
                    "phrased as a command. Cannavec reports trial-"
                    "supported population dose ranges; it never "
                    "recommends a personal dose. Refer all dosing "
                    "decisions to a clinician."
                ),
                action=SafetyAction.REFUSE_INDIVIDUALIZED,
            ))

    # Promote dose / interaction questions to "individualized" only if
    # the prompt is in second person about the user's own care.
    if is_individualized_medical_question(text):
        if not any(f.action == SafetyAction.REFUSE_INDIVIDUALIZED for f in fired):
            fired.append(FiredFlag(
                flag=SafetyFlag.INDIVIDUALIZED_MEDICAL,
                matched_text=text[:120],
                why=(
                    "Question asks about the user's own care. Cannavec "
                    "gives information; a clinician familiar with the "
                    "user's history gives advice."
                ),
                action=SafetyAction.REFUSE_INDIVIDUALIZED,
            ))

    if not fired:
        return SafetyVerdict(proceed=True)

    # Pick highest-precedence action.
    precedence = {
        SafetyAction.REFUSE_HARMFUL: 4,
        SafetyAction.REFUSE_INDIVIDUALIZED: 3,
        SafetyAction.REFRAME_TO_POPULATION: 2,
        SafetyAction.ADD_CAUTION: 1,
        SafetyAction.PROCEED: 0,
    }
    chosen = max(fired, key=lambda f: precedence[f.action]).action

    return SafetyVerdict(
        proceed=(chosen not in (
            SafetyAction.REFUSE_HARMFUL,
            SafetyAction.REFUSE_INDIVIDUALIZED,
        )),
        flags=tuple(fired),
        required_cautions=tuple(dict.fromkeys(cautions)),   # de-dup, keep order
        recommended_action=chosen,
    )
