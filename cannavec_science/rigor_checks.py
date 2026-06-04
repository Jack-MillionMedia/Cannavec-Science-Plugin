"""Cannabis-specific rigor checks the Evidence Philosophy declares as
hard rules but until now lived only in prose.

`docs/EVIDENCE_PHILOSOPHY.md § 7` ("Cannabis-specific traps") states:

- **Isomer collapse.** "THC" alone is rejected for pharmacology;
  Δ⁹-THC, Δ⁸-THC, THCA are pharmacologically distinct.
- **Receptor-without-ID.** Mechanism claims must name receptors with
  UniProt IDs so the reader can resolve the target without ambiguity.
- **Dose-without-route.** Every dose claim states route +
  bioavailability range. Oral and inhaled THC are different drugs.

Until now those rules were enforced only by reviewer judgement. This
module turns each into a deterministic check so Cannavec's *own*
output can be re-audited mechanically — the same enforcement
strategy used for `banned_patterns`, `safety`, and the wording-vs-
grade checker.

Each check has the same shape: a finder function returning a tuple of
typed violations + an explanatory message. Empty tuple means clean.

These checks are *opt-in* in the audit pipeline (see
`self_audit.audit_output`'s `require_*` flags). Audience templates
that need them (researcher, clinician, lab) enable them via
`templates.ResponseTemplate.must_*` fields.

Design rules:
- Standard library only.
- Deterministic — same input, same output.
- Conservative — false positives degrade trust faster than misses.
  Each detector documents the contexts that explicitly do NOT fire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


# ── Isomer-collapse detector ──────────────────────────────────────────

# Pharmacology context: words that, when adjacent to a bare "THC" /
# "CBD" mention, imply a pharmacological claim. Bare cannabinoid names
# in non-pharmacology contexts (legal status, product copy, lay summary)
# are NOT violations — only pharmacology-claim contexts are.
_PHARM_CONTEXT = (
    r"(?:bind\w*|affinity|receptor|agonist|antagonist|inverse agonist|"
    r"partial agonist|allosteric|activat\w*|inhibit\w*|modulat\w*|"
    r"potentiat\w*|desensitis\w*|desensitiz\w*|"
    r"metabolis\w*|metaboliz\w*|cyp\d|"
    r"pharmacokinet\w*|pharmacodynam\w*|"
    r"bioavailab\w*|half[- ]life|t\W?max|c\W?max|"
    r"clearance|distribution|absorption|excretion|"
    r"mechanism|pathway|signal\w*|ec50|ic50|ki\b|kd\b|"
    r"plasma concentration|brain penetration|protein binding|"
    r"phase i metab|phase ii metab|glucuronid|hydroxy\w*|"
    r"in vitro|in vivo|cell line|membrane prep|displacement|"
    # Clinical-pharmacology framing: a bare cannabinoid name paired
    # with a dose/route/endpoint term is pharmacology context too,
    # and was being missed (e.g. "THC activates CB1 to produce
    # analgesia at 20 mg/kg/day").
    r"analges\w*|antinocicept\w*|anxiolyt\w*|antiemet\w*|antispasm\w*|"
    r"\bdose\b|\bdosing\b|\bdosage\b|mg/kg|mg\W*kg|"
    r"oral(?:ly)?|inhal\w*|sublingual|oromucosal|intravenous|"
    r"subcutaneous|intraperitoneal)"
)

# The phytocannabinoid families whose isomers are pharmacologically
# distinct. Bare matches are only a violation when adjacent to
# pharmacology context AND not already disambiguated by an isomer
# prefix (Δ⁹, Δ⁸, delta-9, delta-8, THCA, THCV, etc.).
#
# Only THC is in the set; the philosophy explicitly calls out THC
# (Δ⁹-THC, Δ⁸-THC, THCA pharmacologically distinct). CBD's analogues
# (CBDA, CBDV, 7-OH-CBD) are not conventionally conflated in research
# writing — "CBD" is widely understood as cannabidiol the parent
# compound — so flagging bare "CBD" would produce false positives on
# legitimate clinician text. If a future audit shows real-world CBD
# isomer confusion, the family can be re-added here.
_ISOMER_FAMILIES = ("THC",)

# Isomer prefixes that disambiguate a cannabinoid mention.
_ISOMER_DISAMBIG = re.compile(
    r"(?:Δ[⁰¹²³⁴⁵⁶⁷⁸⁹0-9]|delta[-\s]?\d|d[89]\b|"
    r"\d+[-,]?\d?[-\s]?(?:hydroxy|carboxy|oh|carb)|"
    r"thca\b|thcv\b|thco\b|thcp\b|thcb\b|"
    r"cbda\b|cbdv\b|cbdp\b|cbdb\b|cbdo\b|"
    r"11[- ]?(?:oh|hydroxy)[- ]?thc|"
    r"7[- ]?(?:oh|hydroxy)[- ]?cbd)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IsomerViolation:
    """A bare-cannabinoid mention in pharmacology context."""

    cannabinoid: str
    matched_phrase: str
    span: tuple[int, int]
    context_hint: str

    @property
    def why(self) -> str:
        return (
            f"bare '{self.cannabinoid}' appears in pharmacology context "
            f"('{self.context_hint}') without an isomer prefix; isomers "
            f"are pharmacologically distinct (Δ⁹-{self.cannabinoid}, "
            f"Δ⁸-{self.cannabinoid}, {self.cannabinoid}A all behave "
            f"differently)"
        )


def _compile_bare_cannabinoid_pattern(name: str) -> Pattern[str]:
    """Build a regex that finds `<name>` co-occurring with pharmacology
    context within a small window, where `<name>` is NOT preceded by an
    isomer prefix.
    """
    # The pattern uses two strategies:
    # 1. Name then pharmacology context within 80 chars
    # 2. Pharmacology context then name within 80 chars
    # In both cases the name boundary is a word boundary on both sides
    # to avoid matching "THCV" or "CBDV" as if they were bare "THC"/"CBD".
    return re.compile(
        rf"\b{name}\b[^.\n]{{0,80}}{_PHARM_CONTEXT}"
        rf"|"
        rf"{_PHARM_CONTEXT}[^.\n]{{0,80}}\b{name}\b",
        re.IGNORECASE,
    )


_ISOMER_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = tuple(
    (name, _compile_bare_cannabinoid_pattern(name))
    for name in _ISOMER_FAMILIES
)


def _is_disambiguated(text: str, name_span: tuple[int, int]) -> bool:
    """True if the match window already contains an isomer-disambig token.

    Looks backward 20 chars and forward 20 chars from the match span
    for one of `_ISOMER_DISAMBIG`. This is the false-positive guard for
    answers that already say `Δ⁹-THC` or `delta-9 THC` etc.
    """
    start = max(0, name_span[0] - 20)
    end = min(len(text), name_span[1] + 20)
    window = text[start:end]
    return bool(_ISOMER_DISAMBIG.search(window))


def detect_isomer_collapse(text: str) -> tuple[IsomerViolation, ...]:
    """Return every bare-cannabinoid-in-pharmacology mention.

    A pharmacology mention of bare `THC` or `CBD` (without a Δ⁹ / Δ⁸ /
    THCA / 11-OH-THC / etc. prefix in a small window around it) is a
    violation. The detector is intentionally narrow: bare `THC` in a
    legal-status sentence (`"THC is Schedule I under the CSA"`) or a
    plain-language patient summary (`"THC is the intoxicating
    component"`) does NOT fire — pharmacology context is required.
    """
    out: list[IsomerViolation] = []
    for name, regex in _ISOMER_PATTERNS:
        for m in regex.finditer(text):
            # Identify the bare-name span within the match
            # so the disambiguation check looks in the right window.
            inner = re.search(rf"\b{name}\b", m.group(0), flags=re.IGNORECASE)
            if not inner:
                continue
            inner_start = m.start() + inner.start()
            inner_end = m.start() + inner.end()
            if _is_disambiguated(text, (inner_start, inner_end)):
                continue
            # Take a short context excerpt for the message.
            ctx = m.group(0).strip()
            if len(ctx) > 80:
                ctx = ctx[:77] + "..."
            out.append(IsomerViolation(
                cannabinoid=name,
                matched_phrase=m.group(0),
                span=m.span(),
                context_hint=ctx,
            ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── Receptor-without-ID detector ──────────────────────────────────────

# Receptors / channels / enzymes Cannavec answers commonly name in
# mechanism context. Each requires a UniProt ID (or equivalent
# canonical identifier — gene symbol via HGNC, ChEMBL target id) within
# the same sentence-ish window.
_RECEPTOR_NAMES: tuple[str, ...] = (
    "CB1", "CB2",
    "GPR55", "GPR119",
    "TRPV1", "TRPV2", "TRPV3", "TRPV4", "TRPA1", "TRPM8",
    "PPAR-?(?:α|alpha)", "PPAR-?(?:γ|gamma)",
    "5[-\\s]?HT1A", "5[-\\s]?HT2A", "5[-\\s]?HT3A",
    "FAAH", "MAGL", "DAGL(?:-?[αβ])?", "NAPE-?PLD",
    "ABHD6", "ABHD12",
    "μ[-\\s]?opioid", "mu[-\\s]?opioid", "MOR\\b",
    "δ[-\\s]?opioid", "delta[-\\s]?opioid", "DOR\\b",
    "κ[-\\s]?opioid", "kappa[-\\s]?opioid", "KOR\\b",
    "GABA-?A", "GABA-?B",
    "α7 nAChR", "alpha7 nAChR", "nicotinic acetylcholine",
    "NMDA receptor", "AMPA receptor", "kainate receptor",
    "T-?type (?:calcium|Ca)", "L-?type (?:calcium|Ca)",
    "voltage-?gated sodium",
)

# Identifier formats that count as "named with a resolvable ID":
# - UniProt accession (e.g. P21554, O00519, Q9NYW2)
# - HGNC gene symbol in caps (e.g. CNR1, CNR2, GPR55, FAAH, MGLL)
#   — accept when paired with "gene" or "UniProt" or in caps adjacent
# - ChEMBL target id (e.g. CHEMBL218)
_IDENTIFIER_TOKEN = re.compile(
    r"(?:UniProt\s*[:#]?\s*[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|UniProt[^\s.;]{0,5}[A-Z][0-9][A-Z0-9]{3}[0-9]"
    r"|\b[OPQ][0-9][A-Z0-9]{3}[0-9]\b"
    r"|CHEMBL\d{2,}"
    r"|\b(?:CNR1|CNR2|MGLL|FAAH|TRPV1|TRPV2|TRPV3|TRPV4|TRPA1|"
    r"GPR55|GPR119|PPARA|PPARG|HTR1A|HTR2A|HTR3A|"
    r"OPRM1|OPRD1|OPRK1|NAPEPLD|DAGLA|DAGLB|ABHD6|ABHD12|"
    r"CHRNA7|GABRA1|GRIN1|GRIA1|CACNA1[A-Z]|SCN1A)\b"
    r"|gene\s+symbol\s*[:#]?\s*[A-Z][A-Z0-9]{2,}"
    r"|HGNC\s*[:#]?\s*\d+)",
    re.IGNORECASE,
)

# Mechanism context — words that mark a sentence as a mechanism claim
# (where identifier discipline is required). The receptor check fires
# only in mechanism context.
_MECHANISM_CONTEXT = re.compile(
    r"\b(?:agonist|antagonist|partial agonist|inverse agonist|"
    r"allosteric|binds?|binding|affinity|ki\b|kd\b|ic50|ec50|"
    r"selective|potency|mediated by|via|through|"
    r"activates?|inhibits?|modulates?|signal\w*|"
    r"acts? (?:at|on|via|through)|act(?:ing|ion) (?:at|on|via|through)|"
    r"active (?:at|on)|"
    r"mechanism|pathway|receptor[- ]mediated|target)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReceptorViolation:
    """A receptor named in mechanism context without a resolvable ID."""

    receptor: str
    matched_phrase: str
    span: tuple[int, int]

    @property
    def why(self) -> str:
        return (
            f"receptor '{self.receptor}' named in mechanism context "
            f"without a UniProt / HGNC / ChEMBL identifier; mechanism "
            f"claims must let the reader resolve the target unambiguously"
        )


def _compile_receptor_pattern(name: str) -> Pattern[str]:
    return re.compile(rf"\b{name}\b", re.IGNORECASE)


_RECEPTOR_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = tuple(
    (re.sub(r"[\\\[\]\?\(\)\-\s]", "", name).upper() or name,
     _compile_receptor_pattern(name))
    for name in _RECEPTOR_NAMES
)


# A `.` that belongs to a dotted route abbreviation (p.o., i.v., s.c.,
# …) is NOT a sentence boundary. The dotted forms all have the shape
# `<letter>.<letter>.` — two single-letter segments each closed by a
# period. The period at index ``i`` can be EITHER the inner period
# (``p|.|o.``) or the trailing period (``p.o|.|``); we match both.
_ROUTE_ABBREV_HEAD = re.compile(r"^[a-z]\.[a-z]\.", re.IGNORECASE)
_ROUTE_ABBREV_TAIL = re.compile(r"[a-z]\.[a-z]\.$", re.IGNORECASE)


def _is_route_abbrev_period(text: str, i: int) -> bool:
    """True if ``text[i]`` is a period that is part of a dotted route
    abbreviation (``p.o.``, ``i.v.``, ``s.c.``, …) and therefore must
    NOT be treated as a sentence boundary.

    A dotted route abbreviation is exactly ``<letter>.<letter>.``. The
    period at ``i`` qualifies if it is the FIRST period (the 4-char run
    starting one char back is ``p.o.``) or the SECOND period (the 4-char
    run ending here is ``p.o.``).
    """
    if i >= len(text) or text[i] != ".":
        return False
    # i is the first period: text[i-1 : i+3] == "p.o."
    if _ROUTE_ABBREV_HEAD.match(text[max(0, i - 1):i + 3]):
        return True
    # i is the second period: text[i-3 : i+1] == "p.o."
    if _ROUTE_ABBREV_TAIL.search(text[max(0, i - 3):i + 1]):
        return True
    return False


def _sentence_window_bounds(text: str, span: tuple[int, int],
                            radius: int = 140,
                            abbrev_safe: bool = False) -> tuple[int, int]:
    """Return the (start, end) bounds of the sentence-window around ``span``.

    Walks outward from ``span`` until either a sentence-boundary
    character (``.`` or newline) is reached or ``radius`` characters
    have been consumed. The returned bounds are absolute offsets into
    ``text`` — callers that need the slice should call
    :func:`_sentence_window` (a thin wrapper that returns ``text[start:end]``).

    When ``abbrev_safe`` is True, periods that belong to a dotted route
    abbreviation (``p.o.``, ``i.v.``, …) are stepped over rather than
    treated as boundaries. This keeps the dose-route detector from
    chopping "1-2 mg p.o." mid-abbreviation while leaving the receptor /
    entourage detectors' strict per-sentence isolation unchanged.
    """
    start = span[0]
    end = span[1]

    def _is_boundary(idx: int) -> bool:
        ch = text[idx]
        if ch == "\n":
            return True
        if ch == ".":
            if abbrev_safe and _is_route_abbrev_period(text, idx):
                return False
            return True
        return False

    # Walk back to a sentence boundary or `radius` chars.
    left = start
    while left > 0 and left > start - radius and not _is_boundary(left - 1):
        left -= 1
    right = end
    while (right < len(text) and right < end + radius
           and not _is_boundary(right)):
        right += 1
    return left, right


def _sentence_window(text: str, span: tuple[int, int],
                     radius: int = 140,
                     abbrev_safe: bool = False) -> str:
    """Return the surrounding text within `radius` chars (or to a period/
    newline boundary, whichever is closer). Used to ask whether an
    identifier appears alongside the receptor mention.

    ``abbrev_safe`` is forwarded to :func:`_sentence_window_bounds`.
    """
    left, right = _sentence_window_bounds(text, span, radius, abbrev_safe)
    return text[left:right]


def _identifier_in_window_outside_span(
    text: str, window_start: int, window_end: int,
    exclude_start: int, exclude_end: int,
) -> bool:
    """True if an identifier token appears in `text[window_start:window_end]`
    *outside* the receptor's own match span.

    This prevents a receptor name that happens to match a gene-symbol
    pattern (e.g. `TRPV1`, `FAAH`, `GPR55` — same name as receptor and
    gene) from self-satisfying the identifier requirement. The author
    must supply an *additional* identifier (UniProt accession,
    "UniProt", "HGNC", a different gene symbol, or a CHEMBL id) for the
    mention to count as resolvable.
    """
    window = text[window_start:window_end]
    for m in _IDENTIFIER_TOKEN.finditer(window):
        abs_start = window_start + m.start()
        abs_end = window_start + m.end()
        if abs_end <= exclude_start or abs_start >= exclude_end:
            return True
    return False


def detect_missing_receptor_ids(text: str) -> tuple[ReceptorViolation, ...]:
    """Return every receptor mention in mechanism context that lacks a
    resolvable identifier in the same sentence-window.

    A mention is a violation iff:
      1. The receptor name matches one of `_RECEPTOR_NAMES`.
      2. The surrounding sentence contains a mechanism-context word.
      3. No UniProt / HGNC / ChEMBL token appears in the same window
         *outside* the receptor's own matched span. (The receptor
         name itself does not satisfy its own identifier requirement,
         even when name and gene symbol happen to be the same string.)

    Sentence boundaries are estimated by `.` or `\\n`.
    """
    out: list[ReceptorViolation] = []
    seen_spans: set[tuple[int, int]] = set()
    for canonical, regex in _RECEPTOR_PATTERNS:
        for m in regex.finditer(text):
            if m.span() in seen_spans:
                continue
            w_start, w_end = _sentence_window_bounds(text, m.span())
            window = text[w_start:w_end]
            if not _MECHANISM_CONTEXT.search(window):
                continue
            if _identifier_in_window_outside_span(
                text, w_start, w_end, m.start(), m.end()
            ):
                continue
            seen_spans.add(m.span())
            ctx = window.strip()
            if len(ctx) > 120:
                ctx = ctx[:117] + "..."
            out.append(ReceptorViolation(
                receptor=canonical,
                matched_phrase=ctx,
                span=m.span(),
            ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── Dose-without-route detector ───────────────────────────────────────

# Dose expressions Cannavec answers commonly emit. A dose claim
# without a route within the same sentence-window is a violation —
# oral and inhaled cannabinoids have different bioavailability ranges,
# different onsets, and different drug-interaction profiles.
_DOSE_EXPRESSION = re.compile(
    # `20 mg/kg/day`, `2.5 mg`, `400 µg`, `1-12 sprays/day`, `200 mg twice daily`
    r"\b(?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?)\s*"
    r"(?:mg|milligrams?|μg|µg|ug|micrograms?|g\b|grams?|"
    r"mcg|sprays?|puffs?|drops?|gummies|gummy|capsules?|"
    r"ml|millilitres?|milliliters?)"
    r"(?:/(?:kg|d|day|m2|mL|min|h|hr|hour))*"
    r"(?:\s*(?:per|/)\s*"
    r"(?:kg|day|dose|24\s*h|24\s*hours?))?",
    re.IGNORECASE,
)

# Route-of-administration tokens that satisfy the requirement.
#
# Three families, each with a distinct boundary strategy:
#
# 1. Spelled-out forms (oral, intranasal, intramuscular, …) — match
#    case-insensitively with word boundaries on both sides.
# 2. Dotted abbreviations (p.o., s.l., i.v., i.m., i.p., i.n., s.c.,
#    p.r., s.q.) — the literal trailing period IS the terminator, so we
#    require a leading word boundary but NOT a trailing `\b` (a `\b`
#    after a literal `.` can never match before whitespace — that bug
#    made every dotted form dead code). A negative lookahead `(?!\w)`
#    keeps "i.v." from matching inside "i.various".
# 3. Bare two-letter abbreviations (PO IV IM SC SL IN IP PR SQ IT) — the
#    canonical way clinical dosing tables write the route ("20 mg PO").
#    Matched CASE-SENSITIVELY (`(?-i:…)`) and as standalone tokens so
#    they do not collide with the English words "in", "im", "is", "it",
#    or substrings of "important"/"impact"/"amount". Uppercase-only is
#    the precision guard: real dosing notation capitalises these.
_ROUTE_TOKEN = re.compile(
    # 1. Spelled-out routes.
    r"\b(?:oral(?:ly)?|inhal(?:ed|ation)|smok(?:ed|ing)|"
    r"vape(?:d|s|r)?|vaping|vapor(?:ised|ized)|vaporis(?:ed|er)|"
    r"sublingual(?:ly)?|"
    r"topical(?:ly)?|transdermal(?:ly)?|"
    r"rectal(?:ly)?|"
    r"intra(?:venous|muscular|peritoneal|nasal|thecal)(?:ly)?|"
    r"subcutaneous(?:ly)?|subcut\b|"
    r"by\s+mouth|per\s+os|"
    r"buccal(?:ly)?|"
    r"mucosal|oromucosal|"
    r"capsule|softgel|"
    r"tincture|edible|gummy|"
    r"spray\b|"
    r"injection|injected|infused|infusion|"
    r"oil drops?|oil\s+capsule|"
    r"via the [a-z]+ route)\b"
    # 2. Dotted abbreviations — leading boundary, no trailing `\b`.
    r"|\b(?:p\.o\.|s\.l\.|i\.v\.|i\.m\.|i\.p\.|i\.n\.|"
    r"s\.c\.|p\.r\.|s\.q\.|i\.t\.)(?!\w)"
    # 3. Bare uppercase abbreviations — case-sensitive island.
    r"|\b(?-i:PO|IV|IM|SC|SL|IN|IP|PR|SQ|IT)\b",
    re.IGNORECASE,
)

# Contexts that ARE a dose mention but should not require a route:
# - Cultivation / agronomy doses (nutrient ppm, soil amendments)
# - Lab method statements (LOD/LOQ, calibration)
# - Cultivation IPM doses (pesticide MRL)
# - Cell-line / animal mechanism doses (in vitro nM / μM)
_NON_CLINICAL_DOSE_HINT = re.compile(
    r"\b(?:lod|loq|limit of (?:detection|quantif\w*)|"
    r"calibration|reference standard|"
    r"ppm\b|ppb\b|mrl\b|action limit|"
    r"in vitro|in-vitro|cell line|culture medium|"
    r"micromolar|μm\b|nanomolar|nm\b|"
    r"nutrient|fertilis(?:er|ation)|"
    r"per (?:plant|hectare|ha|m2|m²|acre)|"
    r"spray ml/L|spray rate|"
    r"per litre|/l\b|/L\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DoseRouteViolation:
    """A dose expression in clinical/dosing context without a route."""

    dose: str
    span: tuple[int, int]
    sentence: str

    @property
    def why(self) -> str:
        return (
            f"dose '{self.dose}' stated without a route of administration; "
            f"cannabinoid PK varies materially by route — oral, inhaled, "
            f"and sublingual bioavailabilities differ by 3-5×"
        )


def detect_missing_dose_route(text: str) -> tuple[DoseRouteViolation, ...]:
    """Return every dose expression that does not name a route nearby.

    A dose is a violation iff:
      1. It matches `_DOSE_EXPRESSION`.
      2. The sentence-window does NOT contain a `_ROUTE_TOKEN`.
      3. The sentence-window does NOT match a non-clinical-dose hint
         (LOD/LOQ, cultivation ppm, in vitro nM, etc.).

    The non-clinical hint is the false-positive guard. Cannavec
    answers about cultivation nutrients, lab methods, and in-vitro
    pharmacology mention numbers + units routinely and those are NOT
    clinical-dose claims.
    """
    out: list[DoseRouteViolation] = []
    for m in _DOSE_EXPRESSION.finditer(text):
        window = _sentence_window(text, m.span(), radius=140,
                                  abbrev_safe=True)
        if _NON_CLINICAL_DOSE_HINT.search(window):
            continue
        if _ROUTE_TOKEN.search(window):
            continue
        ctx = window.strip()
        if len(ctx) > 160:
            ctx = ctx[:157] + "..."
        out.append(DoseRouteViolation(
            dose=m.group(0).strip(),
            span=m.span(),
            sentence=ctx,
        ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── Isomer-equivalence detector ───────────────────────────────────────
#
# Catches the explicit error of asserting two pharmacologically DISTINCT
# cannabinoids are the same: "THC and THCA are the same",
# "delta-8 and delta-9 THC are identical", "THC and CBD are
# interchangeable". This is the inverse of `detect_isomer_collapse`
# (which catches a *bare* name in pharmacology context): here the author
# has named both members of a distinct pair and wrongly equated them.
#
# Conservative by construction — it fires ONLY on an explicit
# equivalence assertion ("are the same / identical / interchangeable /
# equivalent", or the transposed "X is the same as Y") joining two
# members of a CURATED distinct-pair set. Correct precursor/conversion
# language ("THCA is the precursor of THC; it decarboxylates to THC")
# and "are different" statements never fire.

# Canonicalise a matched cannabinoid token to a small set of identity
# keys so that, e.g., "Δ⁹-THC", "delta-9-THC" and "delta 9 thc" all map
# to the same key, distinct from "Δ⁸-THC". Order matters: the more
# specific patterns (acids, delta isomers) are tested before bare THC.
_EQUIV_CANNABINOID_KEYS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"\bthca\b", re.IGNORECASE), "THCA"),
    (re.compile(r"\bcbda\b", re.IGNORECASE), "CBDA"),
    (re.compile(r"(?:Δ|delta[-\s]?)8(?:[-\s]?thc)?\b", re.IGNORECASE), "D8THC"),
    (re.compile(r"(?:Δ|delta[-\s]?)9(?:[-\s]?thc)?\b", re.IGNORECASE), "D9THC"),
    (re.compile(r"\bthcv\b", re.IGNORECASE), "THCV"),
    (re.compile(r"\bcbdv\b", re.IGNORECASE), "CBDV"),
    (re.compile(r"\bcbn\b", re.IGNORECASE), "CBN"),
    (re.compile(r"\bcbg\b", re.IGNORECASE), "CBG"),
    (re.compile(r"\bcbd\b", re.IGNORECASE), "CBD"),
    (re.compile(r"\bthc\b", re.IGNORECASE), "THC"),
)

# Pairs of identity keys that are pharmacologically DISTINCT and must
# never be called identical. Stored as frozensets for order-independent
# membership testing.
_DISTINCT_PAIRS: frozenset[frozenset[str]] = frozenset({
    frozenset({"THC", "THCA"}),          # decarboxylation pair
    frozenset({"CBD", "CBDA"}),          # decarboxylation pair
    frozenset({"D8THC", "D9THC"}),       # double-bond positional isomers
    frozenset({"THC", "CBD"}),           # different compounds entirely
    frozenset({"THC", "THCV"}),          # homologues
    frozenset({"CBD", "CBDV"}),          # homologues
    frozenset({"THC", "CBN"}),           # oxidation product vs parent
    frozenset({"THC", "D8THC"}),         # bare THC (=Δ⁹) vs Δ⁸
    frozenset({"THC", "D9THC"}),
    frozenset({"CBD", "CBG"}),
})

# The equivalence assertion itself. Two shapes:
#   A) "<X> and <Y> are [the] same / identical / interchangeable / ..."
#   B) "<X> is the same as / identical to / interchangeable with <Y>"
# We capture the two cannabinoid operands as free text and resolve each
# to an identity key afterwards, so the detector stays readable.
_EQUIV_ASSERTION = re.compile(
    # A) X and Y are <equiv>
    r"([A-Za-zΔ0-9][\w\-Δ ]{0,18}?)\s+and\s+([A-Za-zΔ0-9][\w\-Δ ]{0,18}?)\s+"
    r"are\s+(?:the\s+|essentially\s+|basically\s+|functionally\s+|"
    r"chemically\s+)*"
    r"(?:same|identical|interchangeable|equivalent)\b"
    r"|"
    # B) X is the same as Y
    r"([A-Za-zΔ0-9][\w\-Δ ]{0,18}?)\s+is\s+"
    r"(?:the\s+|essentially\s+|basically\s+|functionally\s+|chemically\s+)*"
    r"(?:same\s+as|identical\s+to|interchangeable\s+with|equivalent\s+to)\s+"
    r"([A-Za-zΔ0-9][\w\-Δ ]{0,18}?)\b",
    re.IGNORECASE,
)


def _resolve_cannabinoid_key(fragment: str) -> str | None:
    """Map a captured operand fragment to a single canonical identity
    key, or None if it names no recognised cannabinoid. The fragment is
    scanned with the most-specific patterns first so that "Δ⁹-THC"
    resolves to ``D9THC`` rather than the bare ``THC``."""
    for pat, key in _EQUIV_CANNABINOID_KEYS:
        if pat.search(fragment):
            return key
    return None


@dataclass(frozen=True)
class IsomerEquivalenceViolation:
    """An explicit assertion that two distinct cannabinoids are the same."""

    left: str
    right: str
    matched_phrase: str
    span: tuple[int, int]

    @property
    def why(self) -> str:
        return (
            f"asserts '{self.matched_phrase.strip()}' — but {self.left} and "
            f"{self.right} are pharmacologically distinct (different "
            f"receptor pharmacology / potency / decarboxylation state); "
            f"they are not the same, identical, or interchangeable"
        )


def detect_isomer_equivalence(text: str) -> tuple[IsomerEquivalenceViolation, ...]:
    """Return every explicit assertion that two pharmacologically
    distinct cannabinoids are the same / identical / interchangeable.

    Conservative: fires ONLY when an explicit equivalence verb joins two
    operands that both resolve to recognised cannabinoid identity keys
    AND form one of the curated `_DISTINCT_PAIRS`. Correct precursor
    language ("THCA is the precursor of THC") and "are different"
    statements do not fire because they carry no equivalence verb.
    """
    out: list[IsomerEquivalenceViolation] = []
    seen: set[tuple[int, int]] = set()
    for m in _EQUIV_ASSERTION.finditer(text):
        groups = [g for g in m.groups() if g]
        if len(groups) < 2:
            continue
        left_key = _resolve_cannabinoid_key(groups[0])
        right_key = _resolve_cannabinoid_key(groups[1])
        if not left_key or not right_key or left_key == right_key:
            continue
        if frozenset({left_key, right_key}) not in _DISTINCT_PAIRS:
            continue
        if m.span() in seen:
            continue
        seen.add(m.span())
        out.append(IsomerEquivalenceViolation(
            left=left_key,
            right=right_key,
            matched_phrase=m.group(0),
            span=m.span(),
        ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── THCA-vs-THC conflation detector (spec 004 US2) ────────────────────
#
# Catches the most common cannabis-chemistry conflation: a bare "THC"
# (or "CBD") mention in a *flower-content / cultivar-potency / pre-decarb
# assay* context. Different from isomer-collapse: that one catches bare
# THC in *pharmacology* context. This one catches bare THC in *chemistry
# / assay* context where the assay almost certainly measured THCA, not
# decarboxylated Δ⁹-THC. "This cultivar tests at 22% THC by HPLC" is
# the canonical violation; the true measurement is THCA, the post-decarb
# Δ⁹-THC equivalent is ~22% × 0.877 ≈ 19.3%.

_ASSAY_CONTEXT = re.compile(
    r"\b(?:by\s+hplc|by\s+lc[-]?ms|hplc|lc[-]?ms|gc[-]?ms|"
    r"hplc-uv|hplc-dad|"
    r"total\s+(?:thc|cbd)|"
    r"(?:flower|bud|raw\s+plant|raw\s+extract|extract|tincture|"
    r"cultivar|plant|biomass|hemp\s+flower|cannabis\s+flower|"
    r"chemovar|chemotype)|"
    r"potency|potency\s+test|coa|certificate\s+of\s+analysis|"
    r"% ?w/w|%w/w|percent\s+w/w|"
    r"%\s+by\s+(?:dry\s+weight|wet\s+weight)|"
    r"compliance\s+test\w*|"
    r"high[- ]thc|high[- ]cbd|"
    r"cultivar(?:s)?\s+test|labelled\s+at)\b",
    re.IGNORECASE,
)

# Disambiguation tokens that explicitly resolve the THCA/THC ambiguity.
# If any of these appears within ±150 chars of the bare "THC" / "CBD"
# mention, the detector does NOT fire.
_THCA_DISAMBIG = re.compile(
    r"\b(?:thca|cbda|tetrahydrocannabinolic\s+acid|"
    r"cannabidiolic\s+acid|"
    r"acid\s+form|carboxylic\s+acid\s+form|"
    r"decarboxylat\w+|post[- ]decarb\w*|"
    r"after\s+(?:full\s+)?decarb\w*|"
    r"post[- ]decarboxylation|"
    r"thca\s*\+\s*thc|total\s+(?:thc|cbd)|"
    r"thca\s*\+\s*\(thc\s*[*x]\s*0\.877\)|"
    r"thc\s+equivalent|equivalent\s+to.*thc|"
    r"max[- ]?thc|"
    r"%\s*\(\s*thc\s*equivalent\s*\))",
    re.IGNORECASE,
)

# Bare cannabinoid mentions paired with a percentage in chemistry context
# — the canonical pattern: "22% THC" / "THC content of 22%" / "tests at
# 18.4% THC" / "labelled at 22% THC" / etc.
_BARE_THC_PCT = re.compile(
    r"(?:"
    r"(?:test\w*\s+(?:at|with))|labelled\s+at|labeled\s+at|"
    r"label\s+claim\s+of|contain\w*|with|of|"
    r"yields?|produces?|reads?|measures?|"
    r"profile\s+of|amount\s+of|level\s+of|"
    r"value\s+of|reading\s+of|content\s+of|"
    r"%\s+is|=|equals?)\s*"
    r"~?\s*(\d+(?:\.\d+)?)\s*%?\s*"
    r"\b(THC|CBD)\b"
    r"|"
    r"~?\s*(\d+(?:\.\d+)?)\s*%\s*"
    r"\b(THC|CBD)\b"
    r"|"
    r"\b(THC|CBD)\b\s*(?:content|level|amount|profile|value|reading|by\s+weight)?\s*"
    r"(?:is|of|at|=|approximately|approx\.?|~|about)?\s*"
    r"~?\s*(\d+(?:\.\d+)?)\s*%",
)


@dataclass(frozen=True)
class ThcaThcViolation:
    """A bare THC/CBD mention in a chemistry/assay/flower-content context
    without THCA/CBDA disambiguation."""

    cannabinoid: str
    matched_phrase: str
    span: tuple[int, int]
    assay_context: str

    @property
    def why(self) -> str:
        return (
            f"'{self.matched_phrase.strip()}' uses bare '{self.cannabinoid}' "
            f"in chemistry/assay context ('{self.assay_context}') without "
            f"THCA/CBDA disambiguation; flower assays measure the acid form "
            f"pre-decarboxylation. Use "
            f"'{self.cannabinoid}A (X% by HPLC; ≈ Y% Δ⁹-{self.cannabinoid} "
            f"after full decarboxylation)' or 'total {self.cannabinoid} = "
            f"{self.cannabinoid}A + {self.cannabinoid} × 0.877'."
        )


def detect_thca_vs_thc_conflation(text: str) -> tuple[ThcaThcViolation, ...]:
    """Return every bare-THC / bare-CBD mention in a flower-assay /
    cultivar-content / pre-decarb chemistry context that lacks the
    THCA/CBDA disambiguation.

    The detector fires only when BOTH conditions hold:
    1. A bare ``THC`` or ``CBD`` mention paired with a percentage value
       OR a chemistry/assay context phrase in a ±200-char window.
    2. No disambiguation token (``THCA``, ``CBDA``, ``decarboxylated``,
       ``post-decarb``, ``THC equivalent``, etc.) within ±150 chars.

    A pharmacology-context bare ``THC`` (e.g. ``"THC binds CB1"``) is
    handled by :func:`detect_isomer_collapse`, not here.
    """
    out: list[ThcaThcViolation] = []
    seen_spans: set[tuple[int, int]] = set()
    for m in _BARE_THC_PCT.finditer(text):
        cannabinoid = None
        for g in m.groups():
            if g and g.upper() in ("THC", "CBD"):
                cannabinoid = g.upper()
                break
        if not cannabinoid:
            continue
        # Bare-name span within the match
        inner_pat = re.compile(rf"\b{cannabinoid}\b", re.IGNORECASE)
        inner = inner_pat.search(text, m.start(), m.end())
        if not inner:
            continue
        inner_span = inner.span()
        if inner_span in seen_spans:
            continue
        # Disambig window
        d_start = max(0, inner_span[0] - 150)
        d_end = min(len(text), inner_span[1] + 150)
        if _THCA_DISAMBIG.search(text[d_start:d_end]):
            continue
        # Also block if the bare name already has an isomer prefix
        # (Δ⁹-THC, delta-9 THC, etc.) — that disambiguation is enough.
        pre_start = max(0, inner_span[0] - 30)
        pre = text[pre_start:inner_span[0]]
        if _ISOMER_DISAMBIG.search(pre + cannabinoid):
            continue
        ctx_start = max(0, inner_span[0] - 80)
        ctx_end = min(len(text), inner_span[1] + 80)
        ctx_window = text[ctx_start:ctx_end]
        assay = _ASSAY_CONTEXT.search(ctx_window)
        if not assay:
            # Without an explicit assay-context phrase nearby, a bare
            # "20% THC" might be a legitimate label-shorthand in
            # consumer copy. We only fire when assay context is
            # corroborating.
            # Exception: a `% w/w` or `by HPLC` or `flower` adjacent token
            # itself is already in _ASSAY_CONTEXT.
            continue
        seen_spans.add(inner_span)
        out.append(ThcaThcViolation(
            cannabinoid=cannabinoid,
            matched_phrase=m.group(0).strip(),
            span=m.span(),
            assay_context=assay.group(0),
        ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── Matrix-unit-confusion detector (spec 004 US2) ─────────────────────
#
# Catches concentration values cited without a matrix tag — the second
# most common cannabis-chemistry conflation. "CBD level was 150 ng/mL
# after dosing" is ambiguous: 150 ng/mL of *what*? Plasma? Saliva?
# The pharmacology canon requires the matrix tag.

_CONC_UNIT = re.compile(
    r"(?<!\w)("
    r"\d+(?:\.\d+)?\s*"
    r"(?:ng\s*/\s*mL|ng/mL|ng\.mL\^-1|"
    r"µg\s*/\s*mL|ug\s*/\s*mL|µg/mL|ug/mL|"
    r"mg\s*/\s*mL|mg/mL|"
    r"pg\s*/\s*mL|pg/mL|"
    r"ng\s*/\s*g|ng/g|"
    r"µg\s*/\s*g|ug\s*/\s*g|µg/g|ug/g|"
    r"mg\s*/\s*g|mg/g|"
    r"%\s*w/w|%w/w|"
    r"(?<![a-z])nM\b|(?<![a-z])µM\b|(?<![a-z])uM\b|"
    r"(?<![a-z])mM\b|(?<![a-z])pM\b)"
    r")",
    re.IGNORECASE,
)

_MATRIX_TAG = re.compile(
    r"\b(?:plasma|serum|whole\s+blood|blood|urine|saliva|oral\s+fluid|"
    r"hair|sweat|csf|cerebrospinal\s+fluid|"
    r"flower|bud|raw\s+plant|extract|tincture|distillate|"
    r"isolate|edible|gummy|beverage|topical|cream|salve|"
    r"breast\s*milk|breastmilk|amniotic\s+fluid|"
    r"in\s+vitro|cell\s+(?:line|culture)|membrane\s+prep|"
    r"brain\s+tissue|liver\s+microsom\w+|microsomes?|"
    r"vapor\s+condensate|vape\s+aerosol|condensate|"
    r"buffer|assay\s+buffer|krebs)\b",
    re.IGNORECASE,
)

# Implicit-PK shorthand that conventionally implies plasma matrix:
# "Cmax 150 ng/mL", "AUC", "T-max", "C-max". These get a free pass.
_IMPLICIT_PK_MATRIX = re.compile(
    r"\b(?:c[-_\s]?max|t[-_\s]?max|auc|"
    r"cmax|tmax|"
    r"pharmacokinetic\w*|pk\s+parameter|"
    r"plasma\s+concentration|plasma\s+level)\b",
    re.IGNORECASE,
)

# Cannabinoid names that must be adjacent (within ±70 chars) for the
# detector to consider this a cannabinoid-concentration claim. Bare
# concentration units in non-cannabis context (e.g. "blood glucose 90
# mg/dL") do not concern us.
_CANNABINOID_NAMES = re.compile(
    r"\b(?:thc|cbd|thca|cbda|cbn|cbg|cbga|cbc|cbca|"
    r"thcv|thcva|cbdv|cbdva|cbnv|cbgv|"
    r"thcp|cbdp|hhc|thco|"
    r"cannabinoid\w*|cannabidiol|tetrahydrocannabinol|"
    r"cannabigerol|cannabinol|cannabichromene|"
    r"delta[- ]?\d|d8|d9|d10|"
    r"Δ\d|Δ\d)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MatrixUnitViolation:
    """A concentration value cited without a matrix tag."""

    unit_phrase: str
    span: tuple[int, int]
    cannabinoid_context: str

    @property
    def why(self) -> str:
        return (
            f"concentration '{self.unit_phrase.strip()}' cited near "
            f"'{self.cannabinoid_context}' without a matrix tag; the "
            f"pharmacology canon requires naming the matrix (plasma / "
            f"serum / urine / saliva / hair / flower / extract / edible / "
            f"in vitro buffer). 'CBD 150 ng/mL' is ambiguous; "
            f"'CBD plasma C-max 150 ng/mL (oral, fed, 750 mg)' is honest."
        )


def detect_matrix_unit_confusion(text: str) -> tuple[MatrixUnitViolation, ...]:
    """Return every concentration unit cited near a cannabinoid name
    without an explicit matrix tag.

    A unit + cannabinoid pairing fires UNLESS one of these holds:
    - A matrix tag (``plasma``, ``flower``, ``in vitro``, …) is within
      ±120 chars of the unit.
    - An implicit-PK-matrix token (``C-max``, ``AUC``, …) is within
      ±60 chars (these conventionally mean plasma).
    """
    out: list[MatrixUnitViolation] = []
    for m in _CONC_UNIT.finditer(text):
        unit_span = m.span()
        # Cannabinoid must be within ±70 chars
        cn_start = max(0, unit_span[0] - 70)
        cn_end = min(len(text), unit_span[1] + 70)
        cn = _CANNABINOID_NAMES.search(text[cn_start:cn_end])
        if not cn:
            continue
        # Matrix tag in ±120-char window?
        ma_start = max(0, unit_span[0] - 120)
        ma_end = min(len(text), unit_span[1] + 120)
        if _MATRIX_TAG.search(text[ma_start:ma_end]):
            continue
        # Implicit-PK shorthand in ±60-char window?
        pk_start = max(0, unit_span[0] - 60)
        pk_end = min(len(text), unit_span[1] + 60)
        if _IMPLICIT_PK_MATRIX.search(text[pk_start:pk_end]):
            continue
        out.append(MatrixUnitViolation(
            unit_phrase=m.group(0),
            span=unit_span,
            cannabinoid_context=cn.group(0),
        ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── Decarb-context-missing detector (spec 004 US2) ────────────────────
#
# Catches a pharmacology claim about THC or CBD sourced from a study
# that measured the acid form. "CBD inhibited cytokine release at 10 µM
# in raw extract" is the canonical violation: raw extract contains CBDA,
# not CBD. The pharmacology canon requires either decarboxylation
# applied, or naming the acid form measured.

_RAW_EXTRACT_CONTEXT = re.compile(
    r"\b(?:raw\s+extract|raw\s+plant|raw\s+material|raw\s+flower|"
    r"unheated|undecarbed|pre[- ]?decarb\w*|"
    r"non[- ]?decarbed|non[- ]?decarboxylat\w+|"
    r"undecarboxylat\w+|"
    r"acid[- ]?form|acid\s+cannabinoid\w*|"
    r"unheated\s+extract|"
    r"decarboxylation\s+not\s+applied|"
    r"no\s+decarboxylation|without\s+decarb\w*)\b",
    re.IGNORECASE,
)

_DECARB_APPLIED = re.compile(
    r"\b(?:decarboxylat\w+\s+(?:applied|completed|to\s+completion)|"
    r"post[- ]?decarb\w*|after\s+(?:full\s+)?decarb\w*|"
    r"heated\s+to\s+\d+\s*°?\s*[CF]|"
    r"thca\b|cbda\b|tetrahydrocannabinolic\s+acid|"
    r"cannabidiolic\s+acid|acid\s+form\s+measured)\b",
    re.IGNORECASE,
)

# Neutral-cannabinoid pharmacology claim: a sentence asserting THC or CBD
# (without an acid suffix) doing something pharmacologic.
_NEUTRAL_CB_CLAIM = re.compile(
    r"\b(?:thc|cbd)\b\s*"
    r"(?:.{0,80})?"
    r"\b(?:inhibit\w*|activat\w*|bind\w*|modulat\w*|"
    r"agonis\w+|antagonis\w+|"
    r"reduc\w+|increase\w+|decreas\w+|"
    r"suppress\w+|attenuat\w+|enhance\w+|potentiat\w+|"
    r"prevent\w+|block\w+|abolish\w+|abrogat\w+|"
    r"effect\w*\s+on|action\s+on|"
    r"pharmacolog\w+|mechanism\w*|"
    r"ec50|ic50|ki\b|kd\b|"
    r"selective\s+for|affinity\s+for)\b",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class DecarbContextViolation:
    """A neutral-cannabinoid (THC/CBD) pharmacology claim sourced from a
    raw-extract / undecarbed / acid-form context."""

    cannabinoid: str
    claim_phrase: str
    raw_context: str
    span: tuple[int, int]

    @property
    def why(self) -> str:
        return (
            f"pharmacology claim '{self.claim_phrase.strip()}' asserts a "
            f"neutral-form ('{self.cannabinoid}') effect but the "
            f"surrounding context names '{self.raw_context}'; raw / "
            f"undecarbed extracts contain {self.cannabinoid}A (acid form), "
            f"which has substantially different receptor pharmacology than "
            f"{self.cannabinoid}. Either restate as a {self.cannabinoid}A "
            f"claim, or document that decarboxylation was applied."
        )


def detect_decarb_context_missing(text: str) -> tuple[DecarbContextViolation, ...]:
    """Return every neutral-cannabinoid pharmacology claim adjacent to a
    raw-extract / undecarbed / acid-form context without a
    decarboxylation-applied disclaimer."""
    out: list[DecarbContextViolation] = []
    for m in _NEUTRAL_CB_CLAIM.finditer(text):
        # Identify the cannabinoid name within the match
        inner = re.search(r"\b(THC|CBD)\b", m.group(0), flags=re.IGNORECASE)
        if not inner:
            continue
        cannabinoid = inner.group(1).upper()
        # Block when the bare name has an isomer prefix already
        # (Δ⁹-THC, delta-9 THC, etc.) — that's the disambiguated form.
        absolute_start = m.start() + inner.start()
        absolute_end = m.start() + inner.end()
        pre_start = max(0, absolute_start - 30)
        if _ISOMER_DISAMBIG.search(text[pre_start:absolute_start] + cannabinoid):
            continue
        # Raw-extract context in ±200-char window?
        ctx_start = max(0, m.start() - 200)
        ctx_end = min(len(text), m.end() + 200)
        raw_ctx = _RAW_EXTRACT_CONTEXT.search(text[ctx_start:ctx_end])
        if not raw_ctx:
            continue
        # Decarb-applied disclaimer in ±200-char window?
        if _DECARB_APPLIED.search(text[ctx_start:ctx_end]):
            continue
        out.append(DecarbContextViolation(
            cannabinoid=cannabinoid,
            claim_phrase=m.group(0),
            raw_context=raw_ctx.group(0),
            span=m.span(),
        ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── Entourage-overclaim detector (spec 002 US6) ────────────────────────
#
# Catches the canonical cannabis-marketing claim — "myrcene potentiates
# THC", "limonene synergizes with CBD" — when the surrounding text fails
# to cite one of the small set of papers with measured terpene-cannabinoid
# interaction data. The entourage hypothesis is open-empirical with
# mixed evidence; the detector enforces citation-discipline on synergy
# claims, NOT the hypothesis itself. Discussion of the hypothesis is
# allowed; uncited claims OF synergy are not.
#
# Canonical citation set (the small body of papers with measured
# terpene-cannabinoid pharmacology data the field accepts):
#   - Russo EB 2011 (Br J Pharmacol; PMID 21749363) — entourage review
#   - Finlay DB 2020 (Front Pharmacol; PMID 32226370) — null reproduction
#   - Santiago M 2019 (Cannabis Cannabinoid Res; PMID 30728672) — null
#     reproduction
#   - LaVigne JE 2021 (Sci Rep; PMID 33888868) — myrcene/THC interaction
# Citing any of these explicitly clears the violation.

_TERPENE_NAMES = (
    "myrcene", "linalool", "limonene", "pinene", "α-pinene", "alpha-pinene",
    "β-pinene", "beta-pinene", "caryophyllene", "β-caryophyllene",
    "beta-caryophyllene", "humulene", "α-humulene", "alpha-humulene",
    "terpinolene", "ocimene", "bisabolol", "guaiol", "nerolidol",
    "eucalyptol", "geraniol", "cedrene", "phytol",
)
_TERPENE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in _TERPENE_NAMES) + r")\b",
    re.IGNORECASE,
)
_CANNABINOID_TOKEN_RE = re.compile(
    r"\b(?:thc|cbd|thca|cbda|cbn|cbg|cbc|thcv|cbdv|"
    r"Δ⁹-thc|delta-9 thc|delta-9-thc|Δ⁸-thc|delta-8 thc|hhc)\b",
    re.IGNORECASE,
)
_SYNERGY_VERB_RE = re.compile(
    r"\b(?:potentiate\w*|synerg\w+|enhance\w*|augment\w*|amplif\w+|"
    r"modulat\w*\s+(?:the\s+)?effect\w*\s+of|boost\w*|magnif\w+|"
    r"work[s]?\s+(?:together\s+)?with|"
    r"in\s+combination\s+with|combine\w*\s+(?:with|to)|"
    r"co-?administ\w+\s+(?:with|to)|"
    r"together\s+with|"
    r"entourage(?:\s+effect)?)\b",
    re.IGNORECASE,
)
_ENTOURAGE_CITATIONS_RE = re.compile(
    r"(?:russo\s+(?:eb\s+)?(?:2011|et\s+al)|pmid\s*[:#]?\s*21749363|"
    r"finlay\s+(?:db\s+)?(?:2020|et\s+al)|pmid\s*[:#]?\s*32226370|"
    r"santiago\s+(?:m\s+)?(?:2019|et\s+al)|pmid\s*[:#]?\s*30728672|"
    r"lavigne\s+(?:je\s+)?(?:2021|et\s+al)|pmid\s*[:#]?\s*33888868)",
    re.IGNORECASE,
)
_HYPOTHESIS_DISCUSSION_RE = re.compile(
    r"\b(?:hypothesis|hypothesise[d]?|propose\w*|theoreti\w*|"
    r"open\s+(?:question|empirical)|"
    r"is\s+(?:debated|contested|controversial)|"
    r"mixed\s+evidence|under\s+(?:debate|investigation)|"
    r"remains\s+(?:to\s+be\s+)?(?:established|tested|determined)|"
    r"would\s+(?:potentially\s+)?(?:potentiate|synerg)|"
    r"may\s+(?:in\s+theory\s+)?(?:potentiate|synerg)|"
    r"theoretically\s+(?:potentiate|synerg))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EntourageViolation:
    """A terpene-cannabinoid synergy claim without a canonical citation."""

    terpene: str
    cannabinoid: str
    matched_phrase: str
    span: tuple[int, int]

    @property
    def why(self) -> str:
        return (
            f"synergy claim pairing '{self.terpene}' with "
            f"'{self.cannabinoid}' (matched: "
            f"'{self.matched_phrase.strip()}') without citing one of the "
            f"canonical entourage-effect papers (Russo 2011 PMID 21749363, "
            f"Finlay 2020 PMID 32226370, Santiago 2019 PMID 30728672, "
            f"LaVigne 2021 PMID 33888868). The entourage hypothesis is "
            f"open-empirical with mixed evidence; synergy claims require "
            f"primary-source citation per Constitution §I."
        )


def detect_entourage_overclaim(text: str) -> tuple[EntourageViolation, ...]:
    """Return every uncited terpene-cannabinoid synergy claim.

    A sentence-level claim fires when ALL of these hold within a single
    sentence-window (±140 chars):
      1. A terpene name is mentioned.
      2. A cannabinoid name is mentioned.
      3. A synergy / entourage verb is present.
      4. NO canonical citation is present in the window.
      5. NO hypothesis-discussion language is present (false-positive
         guard for legitimate scientific discussion).

    The detector is conservative — it enforces citation discipline,
    not the hypothesis. A sentence discussing the entourage hypothesis
    as a debated research topic does NOT fire.
    """
    out: list[EntourageViolation] = []
    # Dedup key per spec 003 US10 / FR-010: a single (terpene,
    # cannabinoid, sentence-window) yields one violation even when
    # multiple synergy verbs fire inside that window.
    seen_keys: set[tuple[str, str, int, int]] = set()
    for m in _SYNERGY_VERB_RE.finditer(text):
        w_start, w_end = _sentence_window_bounds(text, m.span(), radius=200)
        window = text[w_start:w_end]
        terp = _TERPENE_RE.search(window)
        cann = _CANNABINOID_TOKEN_RE.search(window)
        if not (terp and cann):
            continue
        # False-positive guard: hypothesis discussion.
        if _HYPOTHESIS_DISCUSSION_RE.search(window):
            continue
        # False-positive guard: canonical citation in window.
        if _ENTOURAGE_CITATIONS_RE.search(window):
            continue
        terp_token = terp.group(0).lower()
        cann_token = cann.group(0).upper()
        key = (terp_token, cann_token, w_start, w_end)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(EntourageViolation(
            terpene=terp_token,
            cannabinoid=cann_token,
            matched_phrase=window.strip()[:160],
            span=m.span(),
        ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


# ── Combined audit helper ─────────────────────────────────────────────


@dataclass(frozen=True)
class RigorCheckReport:
    """Combined report from running all seven cannabis-specific checks
    (spec 001 isomer/receptor/dose-route + spec 004 THCA-vs-THC /
    matrix-unit / decarb-context + spec 002 US6 entourage-overclaim)
    plus the spec-006 reporting-guideline / risk-of-bias detectors."""

    isomer_violations: tuple[IsomerViolation, ...] = ()
    receptor_violations: tuple[ReceptorViolation, ...] = ()
    dose_route_violations: tuple[DoseRouteViolation, ...] = ()
    thca_thc_violations: tuple[ThcaThcViolation, ...] = ()
    matrix_unit_violations: tuple[MatrixUnitViolation, ...] = ()
    decarb_context_violations: tuple[DecarbContextViolation, ...] = ()
    entourage_violations: tuple[EntourageViolation, ...] = ()
    # Spec 006 US5 — reporting-guideline + risk-of-bias rigor.
    reporting_rigor_violations: tuple = ()
    # Explicit isomer / decarb equivalence errors ("THC and THCA are the
    # same"). Appended last so existing positional construction is safe.
    isomer_equivalence_violations: tuple[IsomerEquivalenceViolation, ...] = ()

    @property
    def clean(self) -> bool:
        return not (
            self.isomer_violations
            or self.receptor_violations
            or self.dose_route_violations
            or self.thca_thc_violations
            or self.matrix_unit_violations
            or self.decarb_context_violations
            or self.entourage_violations
            or self.reporting_rigor_violations
            or self.isomer_equivalence_violations
        )

    def summary(self) -> str:
        if self.clean:
            return (
                "Clean — no isomer / receptor-id / dose-route / "
                "THCA-vs-THC / matrix-unit / decarb-context / "
                "entourage-overclaim / reporting-rigor / "
                "isomer-equivalence violations."
            )
        lines: list[str] = []
        if self.isomer_violations:
            lines.append("## Isomer-collapse violations")
            for v in self.isomer_violations:
                lines.append(f"- {v.why}")
        if self.isomer_equivalence_violations:
            lines.append("## Isomer-equivalence violations")
            for v in self.isomer_equivalence_violations:
                lines.append(f"- {v.why}")
        if self.receptor_violations:
            lines.append("## Receptor-without-id violations")
            for v in self.receptor_violations:
                lines.append(f"- {v.why}")
        if self.dose_route_violations:
            lines.append("## Dose-without-route violations")
            for v in self.dose_route_violations:
                lines.append(f"- {v.why}")
        if self.thca_thc_violations:
            lines.append("## THCA-vs-THC conflation violations")
            for v in self.thca_thc_violations:
                lines.append(f"- {v.why}")
        if self.matrix_unit_violations:
            lines.append("## Matrix-unit-confusion violations")
            for v in self.matrix_unit_violations:
                lines.append(f"- {v.why}")
        if self.decarb_context_violations:
            lines.append("## Decarb-context-missing violations")
            for v in self.decarb_context_violations:
                lines.append(f"- {v.why}")
        if self.entourage_violations:
            lines.append("## Entourage-overclaim violations")
            for v in self.entourage_violations:
                lines.append(f"- {v.why}")
        if self.reporting_rigor_violations:
            lines.append("## Reporting-rigor violations")
            for v in self.reporting_rigor_violations:
                lines.append(
                    f"- [{v.kind.value}] {v.why} "
                    f"(anchor: {v.anchor_text!r})"
                )
        return "\n".join(lines)


def run_rigor_checks(text: str) -> RigorCheckReport:
    """Run all cannabis-specific rigor checks on `text`, plus the
    spec-006 reporting-guideline / risk-of-bias detectors."""
    from cannavec_science.reporting_rigor import (
        run_reporting_rigor_checks,
    )
    return RigorCheckReport(
        isomer_violations=detect_isomer_collapse(text),
        receptor_violations=detect_missing_receptor_ids(text),
        dose_route_violations=detect_missing_dose_route(text),
        thca_thc_violations=detect_thca_vs_thc_conflation(text),
        matrix_unit_violations=detect_matrix_unit_confusion(text),
        decarb_context_violations=detect_decarb_context_missing(text),
        entourage_violations=detect_entourage_overclaim(text),
        reporting_rigor_violations=run_reporting_rigor_checks(text),
        isomer_equivalence_violations=detect_isomer_equivalence(text),
    )
