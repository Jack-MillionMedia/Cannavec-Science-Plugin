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

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cannavec_science.answer import _lookup_citation_grade

if TYPE_CHECKING:
    from cannavec_science.answer import Answer


__all__ = [
    "CitationAtom",
    "LosslessReport",
    "export_provenance",
    "assert_citation_lossless",
    "grade_adjacency_failures",
]


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
    missing_grades = tuple(sorted(g for g in required_grades if g not in text))
    return LosslessReport(
        ok=not missing_ids and not missing_grades,
        missing_identifiers=missing_ids,
        missing_grades=missing_grades,
    )


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
