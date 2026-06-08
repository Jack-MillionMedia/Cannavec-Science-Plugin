"""Citation-lossless export gate — the §XI guarantee made mechanical.

The canonical research artifact is the structured Markdown brief plus the typed
``--json`` :class:`~cannavec_science.answer.Answer`. The constitution (§XI)
permits rendering that artifact into presentable formats (PDF, slides,
reference-manager exports) ONLY as a **citation-lossless transform**: every
primary-source identifier and every inline GRADE label MUST survive into the
rendered output, or the transform "drops, softens, or de-anchors" evidence and
is forbidden.

This module turns that requirement into a single reusable check every ``/cv``
output skill calls on its rendered output, refusing to emit if it fails:

    from cannavec_science.export import assert_citation_lossless
    rendered = render_my_format(answer)            # transform only — never author
    report = assert_citation_lossless(answer, rendered)
    if not report:
        raise SystemExit(f"refusing to emit — dropped {report.missing_identifiers} "
                         f"{report.missing_grades}")

It is the line between a value-adding output skill (provably preserves the
verification) and noise (un-anchored, de-graded prose). Stdlib-only, pure,
deterministic, offline — same as the rest of the verification core (§II/§X).

GRADE resolution is the single source of truth shared with serialization and the
bibliography exporter: a citation's grade is the strongest grade across the
SURVIVING claims that cite it (so a dropped claim never orphans a grade — see
:meth:`Answer._citation_grade_map`).
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cannavec_science.answer import _lookup_citation_grade
from cannavec_science.evidence import EvidenceLevel

if TYPE_CHECKING:
    from cannavec_science.answer import Answer


__all__ = [
    "CitationAtom",
    "LosslessReport",
    "export_provenance",
    "assert_citation_lossless",
    "grade_adjacency_failures",
    "grade_inflation_failures",
    "render_citation_export",
]


# The discrete GRADE labels a render may carry, strongest first. "Unsupported"
# is excluded: it is never assigned to a citation (an ungraded atom is ``None``),
# and naming it beside a citation softens rather than inflates — the softening
# direction is already owned by :func:`grade_adjacency_failures`.
_GRADE_LABELS: "tuple[str, ...]" = tuple(
    lvl.value for lvl in EvidenceLevel if lvl is not EvidenceLevel.UNSUPPORTED
)


def _grade_present(label: str, text: str) -> bool:
    """Is GRADE ``label`` present in ``text`` as a DISCRETE token?

    A bare substring ``in`` check let a dropped grade be masked by an unrelated
    word that merely starts the same way — "Level Below threshold" satisfied
    "Level B". The boundary lookarounds make the floor honest: the label may not
    be glued to an adjacent letter on either side."""
    return (
        re.search(rf"(?<![A-Za-z]){re.escape(label)}(?![A-Za-z])", text) is not None
    )


def _grade_rank(label: "str | None") -> int:
    """Strength rank of a GRADE label (``"Level A"`` → 5 … ``"Level E"`` → 1),
    0 for ``None`` or any non-grade string. The single ordering the inflation
    gate compares against — reuses :class:`EvidenceLevel` so the two cannot drift."""
    if not label:
        return 0
    try:
        return EvidenceLevel(label).rank
    except ValueError:
        return 0


# Rank assigned to a grade whose LETTER is a non-ASCII homoglyph that normalisation
# did not fold: higher than any real grade, so it ALWAYS reads as inflation against
# any citation. A render must not slip a fake grade past the scan with a confusable.
_HOMOGLYPH_GRADE_RANK = 99

# Latin-look-alike Cyrillic / Greek letters (the cases NFKD does NOT fold, since
# they are distinct scripts, not compatibility variants) folded to ASCII so a GRADE
# label — or the anchor word "Level" / "Grade" itself — spelled with a confusable
# cannot evade the scan. Covers both the grade-letter slot and the anchor letters.
# NFKD already handles every compatibility look-alike (fullwidth, math, circled,
# Roman-numeral, ligature); this map is only the script-confusable remainder.
_GRADE_CONFUSABLES = {
    0x0410: "A", 0x0391: "A",                  # cyrillic / greek capital A
    0x0412: "B", 0x0392: "B",
    0x0421: "C", 0x03F9: "C",
    0x0415: "E", 0x0395: "E",
    0x0435: "e", 0x03B5: "e", 0x0454: "e",     # lowercase anchor letters
    0x03BD: "v", 0x0475: "v",
    0x04CF: "l", 0x0142: "l", 0x029F: "l",     # palochka / l-stroke / small-cap L
    0x04C0: "L", 0x0141: "L",
}

# Enclosed-alphanumeric letterforms (parenthesized / squared / negative-squared /
# negative-circled / circled A-Z) folded to their base letter BEFORE NFKD, because
# several (the negative forms 🅰/🅐) are Unicode Symbols that survive NFKD and would
# otherwise read as a grade letter the scan misses. Computed, covers all 26 letters.
_ENCLOSED_FOLD: "dict[int, str]" = {}
for _i in range(26):
    for _base in (0x1F110, 0x1F130, 0x1F150, 0x1F170):
        _ENCLOSED_FOLD[_base + _i] = chr(0x41 + _i)
    _ENCLOSED_FOLD[0x24B6 + _i] = chr(0x41 + _i)
    _ENCLOSED_FOLD[0x24D0 + _i] = chr(0x61 + _i)
del _i, _base

# Grade-label anchor: the word "Level"/"Grade" (ASCII after normalisation), then
# whitespace, then the grade slot. The slot is recognised DENY-BY-DEFAULT, not by a
# letter allowlist: a boundary-scoped ASCII A-E (our vocabulary), OR a single-digit
# / Roman-numeral tier (CEBM "Level 1"/"Level I" — a stronger-reading scheme that
# reuses our anchor), OR any non-ASCII glyph (homoglyph slot). "Level Below" / "Level
# of" / "Levels" cannot match (the A-E boundary fails and "B"/"o"/"s" is ASCII, not a
# tier digit, Roman numeral, or non-ASCII glyph).
_GRADE_LABEL_RE = re.compile(
    "(?<![A-Za-z])(?:Level|Grade)[  \t]+"
    "(?:([A-E])(?![A-Za-z])|([1-9])(?![0-9])|([IVX]+)(?![A-Za-z])|([^\\x00-\\x7F]))"
)
_TAG_OR_COMMENT_RE = re.compile(r"<!--.*?-->|<[^>]+>", re.S)


def _fold_grade_confusables(text: str) -> str:
    """Fold the script-confusable letters to ASCII (1:1 codepoint map)."""
    return text.translate(_GRADE_CONFUSABLES)


def _normalize_visible(text: str) -> str:
    """Approximate the text a human READS, so a grade claim cannot hide in the raw
    HTML source: decode HTML entities (``&nbsp;`` -> space, ``&#65;`` -> ``A``),
    strip tags and comments, fold enclosed letterforms, NFKD-fold every compatibility
    look-alike (fullwidth / math / circled / Roman-numeral / ligature), drop combining
    marks, then fold the remaining script confusables. This defeats the "scan source,
    not render" bypass class (``Level&nbsp;A``, ``Level <b>A</b>``, fullwidth /
    homoglyph / enclosed grades). Positions shift versus the source, but the inflation
    scan computes identifier AND label positions on this SAME normalised text, so
    binding stays consistent."""
    t = html.unescape(text or "")
    t = _TAG_OR_COMMENT_RE.sub(" ", t)
    t = t.translate(_ENCLOSED_FOLD)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return _fold_grade_confusables(t)


def _grade_label_positions(
    normalized: str, strict: bool = False
) -> "list[tuple[int, int]]":
    """``(position, rank)`` of every GRADE label in already-:func:`_normalize_visible`
    text. A boundary-scoped ASCII "Level A".."Level E" / "Grade A".."Grade E" carries
    its rank; a "Level "/"Grade " followed by a non-ASCII *letter* (a homoglyph the
    fold missed) carries :data:`_HOMOGLYPH_GRADE_RANK`. When ``strict`` (a region that
    holds ONLY our A-E vocabulary, e.g. a PDF evidence surface), a single-digit /
    Roman-numeral tier slot is ALSO max-rank — "Level 1"/"Level I" is not our grade
    and reads as a strong tier, so beside a citation it is an overclaim. ``strict`` is
    off for whole-document / Markdown use, where a tier scheme may be legitimate
    background."""
    hits: "list[tuple[int, int]]" = []
    for m in _GRADE_LABEL_RE.finditer(normalized):
        letter, digit, roman, homoglyph = m.group(1), m.group(2), m.group(3), m.group(4)
        if letter:
            hits.append((m.start(), _grade_rank("Level " + letter)))
        elif homoglyph and unicodedata.category(homoglyph).startswith("L"):
            hits.append((m.start(), _HOMOGLYPH_GRADE_RANK))
        elif (digit or roman) and strict:
            hits.append((m.start(), _HOMOGLYPH_GRADE_RANK))
    return hits


@dataclass(frozen=True)
class CitationAtom:
    """One primary-source identifier a rendered output MUST preserve.

    ``identifier`` is the typed canonical id (``"PMID:28538134"``,
    ``"DOI:10.1056/..."``, ``"URL:..."``). ``grade`` is the GRADE label that must
    survive alongside it (``"Level B"``), or ``None`` when no surviving claim
    grades the source (adjacent reference context — identifier still mandatory).
    """

    identifier: str
    grade: "str | None" = None

    @property
    def raw_id(self) -> str:
        """The bare identifier value (e.g. ``"28538134"``) — what a renderer
        actually prints, in a URL, a ``(PMID …)`` tag, or a bibliography field."""
        return self.identifier.split(":", 1)[1]


@dataclass(frozen=True)
class LosslessReport:
    """Result of a citation-lossless check. Falsy when the transform dropped
    anything, so ``if not report:`` reads as "refuse to emit"."""

    ok: bool
    missing_identifiers: tuple[str, ...] = ()
    missing_grades: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.ok

    def summary(self) -> str:
        if self.ok:
            return "citation-lossless: all identifiers and GRADE labels survived"
        parts = []
        if self.missing_identifiers:
            parts.append(f"dropped identifiers: {', '.join(self.missing_identifiers)}")
        if self.missing_grades:
            parts.append(f"dropped GRADE labels: {', '.join(self.missing_grades)}")
        return "NOT citation-lossless — " + "; ".join(parts)


def _id_present(raw_id: str, text: str) -> bool:
    """Is ``raw_id`` present in ``text`` as a DISCRETE identifier (not as a
    fragment of a longer token)?

    A false-OK in a correctness gate is worse than a false-FAIL, so the match is
    boundary-scoped: the id may not be glued to an adjacent alphanumeric, and may
    not be glued to a preceding ``.`` either. The leading-dot guard is what stops
    a DROPPED numeric PMID being masked by a SURVIVING DOI that embeds those
    digits (e.g. "10.1371/journal.pone.28538134"), and stops a short DOI being
    masked by a longer sibling ("10.1000/abc" inside "10.1000/abcdef"). A
    legitimately-rendered id is preceded by whitespace / ``(`` / ``:`` / ``/`` /
    ``_`` (a URL, a ``(PMID …)`` tag, or a bibtex key), none of which is excluded.
    """
    return (
        re.search(rf"(?<![0-9A-Za-z.]){re.escape(raw_id)}(?![0-9A-Za-z])", text)
        is not None
    )


def export_provenance(answer: "Answer") -> "tuple[CitationAtom, ...]":
    """The identifiers (+ their surviving-claim GRADE) a rendered transform of
    ``answer`` MUST preserve. One atom per citation, canonical id precedence
    PMID > DOI > URL. Empty for a refusal / no-citation answer."""
    # A refusal renders no citable brief (its citations are reference context,
    # not an exportable answer) — so there is nothing a transform must preserve.
    # Aligns with the empty-Answer case and the "skills skip refusals" contract.
    if answer.is_refusal:
        return ()
    grade_map = answer._citation_grade_map()
    atoms: list[CitationAtom] = []
    seen: set[str] = set()
    for c in answer.citations:
        if c.pmid:
            ident = f"PMID:{c.pmid}"
        elif c.doi:
            ident = f"DOI:{c.doi}"
        elif c.url:
            ident = f"URL:{c.url}"
        else:
            continue
        if ident in seen:
            continue
        seen.add(ident)
        atoms.append(
            CitationAtom(identifier=ident, grade=_lookup_citation_grade(grade_map, c))
        )
    return tuple(atoms)


def assert_citation_lossless(answer: "Answer", rendered: str) -> LosslessReport:
    """Check a rendered transform of ``answer`` preserved every identifier and
    every GRADE label (§XI).

    Identifier check is exact and per-citation (the §I non-negotiable): every
    citation's bare id must appear in ``rendered``. GRADE check is a floor: every
    distinct GRADE label present in the answer's provenance must appear in
    ``rendered`` — this catches a wholesale or per-tier GRADE strip (the
    "softening" failure mode). Per-citation GRADE *adjacency* is format-specific
    and left to the individual skill to assert more strictly if it wishes.
    """
    text = rendered or ""
    atoms = export_provenance(answer)
    missing_ids = tuple(a.identifier for a in atoms if not _id_present(a.raw_id, text))
    required_grades = {a.grade for a in atoms if a.grade}
    missing_grades = tuple(
        sorted(g for g in required_grades if not _grade_present(g, text))
    )
    return LosslessReport(
        ok=not missing_ids and not missing_grades,
        missing_identifiers=missing_ids,
        missing_grades=missing_grades,
    )


def render_citation_export(answer: "Answer", fmt: str) -> "str | None":
    """Render the verified citations behind ``answer`` as a reference export
    (``fmt`` ∈ ``{"bibtex", "ris", "csljson"}``), or ``None`` when there is
    nothing citation-lossless to emit (§XI / M5 — spec 033).

    The single deterministic primitive every ``/cv:cite`` output skill calls. It
    is a *transform* of verified evidence, never an author of citations:

    - Returns ``None`` for a refusal Answer, or one with **no graded claims** —
      an uncurated-indication "no curated efficacy" brief carries the compound
      monograph's cross-cutting citations, which are reference context, not
      evidence for the asked question; exporting them would be the
      citation→claim leak this project exists to prevent (§I / M2).
    - Otherwise renders the bibliography (each entry's GRADE preserved in the
      format's note field) and runs :func:`assert_citation_lossless`; returns the
      rendered string only if every identifier and GRADE label survived, else
      ``None`` (refuse to emit a lossy transform).

    Pure, deterministic, offline — same contract as the rest of the verification
    core (§II / §X). ``fmt`` is delegated to :func:`bibliography.render`, which
    raises ``ValueError`` on an unknown format.
    """
    from cannavec_science import bibliography

    if answer.is_refusal or not answer.claims:
        return None
    entries = bibliography.bibliography_from_answer(answer)
    if not entries:
        return None
    rendered = bibliography.render(entries, fmt)
    if not assert_citation_lossless(answer, rendered):
        return None
    return rendered


def grade_adjacency_failures(
    answer: "Answer", rendered: str, window: int = 300
) -> "tuple[CitationAtom, ...]":
    """Graded atoms whose GRADE label is NOT within ``window`` characters of
    their identifier in ``rendered``.

    The per-citation strictness ``assert_citation_lossless`` deliberately does
    NOT enforce (its GRADE check is a floor). Any **inline** multi-citation
    render — Markdown, a PDF text layer, a slide where the grade sits beside its
    citation — MUST be clean here, so a skill cannot keep one "Level B" label
    while silently softening another citation's grade. Skills whose format puts
    GRADE in a separate column legitimately skip this and assert their own
    column-level invariant. Empty tuple == all graded atoms are anchored.
    """
    text = rendered or ""
    failures: list[CitationAtom] = []
    for atom in export_provenance(answer):
        if not atom.grade:
            continue
        anchored = False
        for m in re.finditer(
            rf"(?<![0-9A-Za-z.]){re.escape(atom.raw_id)}(?![0-9A-Za-z])", text
        ):
            lo, hi = max(0, m.start() - window), m.end() + window
            if atom.grade in text[lo:hi]:
                anchored = True
                break
        if not anchored:
            failures.append(atom)
    return tuple(failures)


def grade_inflation_failures(
    answer: "Answer",
    rendered: str,
    window: int = 200,
    *,
    flag_ungraded: bool = False,
) -> "tuple[CitationAtom, ...]":
    """Atoms a render presents at a STRONGER grade than the backbone assigned —
    the mirror of :func:`grade_adjacency_failures` (which catches softening).

    Together they enforce per-citation grade EQUALITY for any inline format: a
    skill cannot quietly upgrade a Level-C source to "Level A" to make the
    evidence look more certain than it is (M5 / §VII / §XI). ``assert_citation_
    lossless`` cannot catch this — its GRADE check is a presence floor, so an
    upgraded label sails through as long as the true label survives elsewhere.

    Binding is by PROXIMITY, not document order: every GRADE-label occurrence is
    bound to the NEAREST identifier occurrence within ``window`` characters, and
    the binding fails when the label outranks the GRADE the backbone assigned that
    identifier. Nearest-binding keeps a legitimate "Level A" beside its own
    Level-A citation from being blamed on an adjacent weaker sibling. A label with
    no identifier inside ``window`` (a glossary / GRADE legend) is bound to nothing
    and is not inflation. GRADE-letter HOMOGLYPHS are folded to ASCII (and a
    "Level " followed by any other non-ASCII letter is treated as a max-rank
    grade), so a fake grade spelled with a confusable cannot evade the scan.

    ``flag_ungraded`` is the difference between the two legitimate scopes:

    - **False (default)** — a label bound to an UNGRADED citation is ignored. An
      ungraded, reference-context citation legitimately sits inside a
      curated-background section that prints that source's OWN row grade; flagging
      it would mis-read honest background as inflation and would flag the canonical
      Markdown brief itself. Use this whole-document, where background grades exist.
    - **True** — a label bound to an UNGRADED citation IS a failure (an ungraded
      citation must carry no grade). Use this over a region that holds ONLY the
      answer's evidence (e.g. /cv:pdf's evidence surface), where any grade beside
      an ungraded citation is an overclaim, not background.

    Empty tuple == no citation is rendered above its verified grade.
    """
    text = _normalize_visible(rendered or "")
    atoms = export_provenance(answer)
    if not atoms:
        return ()
    id_spans: "list[tuple[int, int, CitationAtom]]" = []
    for atom in atoms:
        for m in re.finditer(
            rf"(?<![0-9A-Za-z.]){re.escape(atom.raw_id)}(?![0-9A-Za-z])", text
        ):
            id_spans.append((m.start(), m.end(), atom))
    if not id_spans:
        return ()
    failures: list[CitationAtom] = []
    flagged: set[str] = set()
    for pos, label_rank in _grade_label_positions(text, strict=flag_ungraded):
        nearest: "CitationAtom | None" = None
        best = window + 1
        for s, e, atom in id_spans:
            dist = 0 if s <= pos <= e else min(abs(pos - s), abs(pos - e))
            if dist < best:
                best = dist
                nearest = atom
        if nearest is None or best > window:
            continue
        if nearest.grade:
            overclaim = label_rank > _grade_rank(nearest.grade)
        else:
            # No surviving claim grades this citation; in strict scope ANY grade
            # beside it is an overclaim, in lenient scope it is background.
            overclaim = flag_ungraded
        if overclaim and nearest.identifier not in flagged:
            failures.append(nearest)
            flagged.add(nearest.identifier)
    return tuple(failures)
