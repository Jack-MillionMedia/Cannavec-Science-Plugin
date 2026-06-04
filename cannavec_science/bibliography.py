"""Bibliography exporter (spec 004 US4).

A research-grade tool whose output is not citable into the researcher's
existing toolchain is not actually research-grade for daily use. This
module turns a Cannavec :class:`~cannavec.answer.Answer`'s citation
list into a Zotero / Mendeley / EndNote-importable file in one of three
canonical formats:

- **BibTeX** — the de-facto LaTeX standard; one ``@article{...}`` per
  citation with a deterministic cite-key (``cannavec_<pmid>`` or
  ``cannavec_doi_<short-hash>``).
- **RIS** — the Reference Manager interchange format read by every
  major reference manager. One record per citation, terminated by
  ``ER  - ``.
- **CSL-JSON** — the Citation Style Language JSON schema used by Zotero
  / Pandoc / Mendeley. One list-of-objects payload.

Design rules (match the rest of Cannavec's deterministic backbone):

- Stdlib-only — ``json``, ``re``, ``hashlib``.
- Pure functions — no IO inside the renderers.
- Deterministic — sorted by PMID then DOI then URL; same input, same
  bytes out.
- Sanitization — no profile data, no filesystem paths, no env-var
  contents.
- Empty input → empty but valid output (zero entries, valid file
  header).

Public surface:

- :class:`BibliographyEntry` — typed per-citation row.
- :func:`bibliography_from_answer` — build the list from an Answer.
- :func:`render_bibtex` / :func:`render_ris` / :func:`render_csljson` —
  format renderers.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from cannavec_science.answer import Answer, Citation
    from cannavec_science.evidence import EvidenceLevel


_BIBTEX_KEY_SAFE = re.compile(r"[^A-Za-z0-9_]+")


@dataclass(frozen=True)
class BibliographyEntry:
    """A typed bibliography row derived from a Cannavec :class:`Citation`.

    Carries the minimum fields required for a Zotero / Mendeley round-trip:
    ``title`` (the citation label), ``authors`` (parsed best-effort from
    the label — Cannavec's label convention is ``"<Surname> <year> — <title>"``),
    ``year``, ``journal`` (when extractable), ``pmid``, ``doi``, ``url``,
    plus the Cannavec-specific ``evidence_level`` annotation.
    """

    cite_key: str
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    evidence_level: str | None = None  # "A" / "B" / "C" / "D" / "E" / "Unsupported"
    note: str = ""

    def to_csljson(self) -> dict:
        """Render this entry as a CSL-JSON object.

        Schema reference: https://github.com/citation-style-language/schema/blob/master/csl-data.json
        Only the canonical fields are emitted; consumers (Zotero,
        Pandoc) tolerate missing optional fields.
        """
        out: dict = {
            "id": self.cite_key,
            "type": "article-journal",
            "title": self.title,
        }
        if self.authors:
            # CSL-JSON author shape is structured: family + given.
            out["author"] = [
                _parse_author_to_csl(name) for name in self.authors
            ]
        if self.year is not None:
            out["issued"] = {"date-parts": [[self.year]]}
        if self.journal:
            out["container-title"] = self.journal
        if self.volume:
            out["volume"] = self.volume
        if self.issue:
            out["issue"] = self.issue
        if self.pages:
            out["page"] = self.pages
        if self.pmid:
            out["PMID"] = self.pmid
        if self.doi:
            out["DOI"] = self.doi
        if self.url:
            out["URL"] = self.url
        if self.evidence_level:
            # Cannavec extension — surfaces inline GRADE level. Most
            # CSL processors will ignore unknown keys; we use the
            # `note` field as the canonical surface for GRADE so the
            # information is preserved in citation managers that strip
            # non-standard keys.
            out["note"] = f"Cannavec GRADE: {self.evidence_level}"
            if self.note:
                out["note"] = self.note + " | " + out["note"]
        elif self.note:
            out["note"] = self.note
        return out


_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
# A token like "RG", "MF", "PF", "AS" — author initials in the
# "Surname INITIALS" convention used by Cannavec labels.
_INITIALS_RE = re.compile(r"^[A-Z]{1,4}$")
# "et al." / "et al" markers that are NOT author names.
_ETAL_RE = re.compile(r"\bet\s+al\.?", re.IGNORECASE)


def _parse_author_to_csl(name: str) -> dict:
    """Parse one author display string into CSL ``{family, given}`` shape.

    Handles the conventions that actually appear in Cannavec labels:

    - ``"Pertwee RG"`` → family ``Pertwee``, given ``RG`` (Surname INITIALS).
    - ``"de Wit H"``   → family ``de Wit``, given ``H`` (particled surname).
    - ``"Devinsky"``   → family ``Devinsky`` (surname only).
    - ``"Smith, J."``  → family ``Smith``, given ``J.`` (comma convention).
    """
    name = _ETAL_RE.sub("", name).strip().strip(",").strip()
    if not name:
        return {"literal": ""}
    if "," in name:
        family, _, given = name.partition(",")
        return {"family": family.strip(), "given": given.strip()}
    parts = name.split()
    if len(parts) == 1:
        return {"family": parts[0]}
    # Cannavec convention is "Surname [particle] INITIALS": the trailing
    # all-caps token is the initials (the *given* field); everything
    # before it is the (possibly particled) family name. If the last
    # token is NOT initials, fall back to Western "given ... family".
    last = parts[-1]
    if _INITIALS_RE.match(last) and len(parts) >= 2:
        return {"family": " ".join(parts[:-1]), "given": last}
    return {"family": last, "given": " ".join(parts[:-1])}


def _split_author_segment(segment: str) -> list[str]:
    """Split one author *block* into individual authors.

    A block may join people with ``&`` or ``and`` (``"Gaoni Y &
    Mechoulam R"``, ``"Lutz JA & de Wit H"``). Parenthetical asides
    (``"Ofek O et al. (Bab I, Zimmer A)"``) and ``et al.`` markers are
    dropped — they are not citable author names.
    """
    segment = re.sub(r"\([^)]*\)", "", segment)         # drop parentheticals
    segment = _ETAL_RE.sub("", segment).strip().strip(",").strip()
    if not segment:
        return []
    out: list[str] = []
    for piece in re.split(r"\s*(?:&|\band\b)\s*", segment):
        piece = piece.strip().strip(",").strip()
        if piece:
            out.append(piece)
    return out


def _parse_label(label: str) -> tuple[tuple[str, ...], str]:
    """Derive ``(authors, journal)`` from a Cannavec citation label.

    Cannavec labels follow two dominant conventions:

    1. **Comma form** — ``"<Authors>, <Journal> <Year>[, <title>]"``
       (e.g. ``"Pertwee RG, Br J Pharmacol 2008, ligand-binding ..."``).
       The journal lives in the comma-segment that carries the 4-digit
       year; everything before it is authors; everything after is title.

    2. **Inline-year form** — ``"<Authors> <Year> [<Journal>] — <Title>
       (<Journal>)"`` (e.g. ``"Devinsky 2017 — CBD in Dravet (NEJM)"`` or
       ``"Bansal et al. 2022 Drug Metab Dispos — ..."``).

    The cardinal rule (Constitution §I citation integrity, §XI Zotero
    promise): a journal name or title fragment must NEVER be emitted as an
    author. When the structure is ambiguous we prefer *fewer* authors over
    fabricated ones.
    """
    label = label.strip()
    if not label:
        return (), ""

    segments = [s.strip() for s in label.split(",")]
    # Comma form: locate the first segment that carries a year — that is
    # the "<Journal> <Year>" segment. Authors precede it.
    if len(segments) >= 2:
        for idx, seg in enumerate(segments):
            if idx == 0:
                # The leading segment is the author block; a bare year in
                # it (rare) does not make it the journal segment.
                continue
            if _YEAR_RE.search(seg):
                journal = _YEAR_RE.sub("", seg)
                journal = re.sub(r"\([^)]*\)", "", journal)
                # The journal name lives before any title separator; an
                # em-dash / colon introduces the title, which must NOT leak
                # into the journal field (mirrors _extract_inline_journal).
                journal = re.split(r"\s*(?:—|--|–|:)\s*", journal, maxsplit=1)[0]
                journal = re.sub(r"\s{2,}", " ", journal).strip()
                authors: list[str] = []
                for auth_seg in segments[:idx]:
                    authors.extend(_split_author_segment(auth_seg))
                return tuple(authors), journal

    # Inline-year form (or no comma at all). Split on the first year.
    m = _YEAR_RE.search(label)
    if not m:
        # No year and no journal-bearing comma segment → this is not an
        # author-bearing citation label (e.g. a section/monograph title
        # like "Adverse events", or an FDA-label stub). Emit no authors.
        return (), ""
    head = label[: m.start()].strip()
    tail = label[m.end():].strip()
    authors = _split_author_segment(head.rstrip("(").strip())
    journal = _extract_inline_journal(tail)
    return tuple(authors), journal


def _extract_inline_journal(tail: str) -> str:
    """Extract the journal from the post-year tail of an inline-year label.

    Two placements occur:
    - between the year and the em-dash: ``"... 2022 Drug Metab Dispos — t"``
    - in a trailing parenthesis: ``"... — CBD in Dravet syndrome (NEJM)"``
    """
    tail = tail.lstrip(") ").strip()
    # Trailing parenthesis wins when present (the canonical journal slot).
    parens = re.findall(r"\(([^)]*)\)", tail)
    if parens:
        cand = parens[-1].split(",")[0].strip()
        if cand:
            return cand
    # Otherwise the run between the year and the em-dash/colon is the
    # journal hint — but only if it is short (a journal abbreviation),
    # not a sentence (which would be the title).
    before_dash = re.split(r"\s*(?:—|--|–|:)\s*", tail, maxsplit=1)[0].strip()
    before_dash = before_dash.rstrip(".")
    if before_dash and len(before_dash.split()) <= 6 and before_dash[:1].isupper():
        return before_dash
    return ""


def _extract_year_from_label(label: str) -> int | None:
    m = _YEAR_RE.search(label)
    if m:
        return int(m.group(1))
    return None


def _bibtex_cite_key(citation: "Citation") -> str:
    """Deterministic stable BibTeX cite-key.

    - PMID-bearing → ``cannavec_pmid_<pmid>``
    - DOI-only → ``cannavec_doi_<8-char-hash>``
    - URL-only → ``cannavec_url_<8-char-hash>``

    The keys are deterministic and decoupled from author/year so two
    independent renders of the same citation produce the same key.
    """
    if citation.pmid:
        return f"cannavec_pmid_{citation.pmid}"
    if citation.doi:
        h = hashlib.sha256(citation.doi.encode("utf-8")).hexdigest()[:8]
        return f"cannavec_doi_{h}"
    if citation.url:
        h = hashlib.sha256(citation.url.encode("utf-8")).hexdigest()[:8]
        return f"cannavec_url_{h}"
    # Should be unreachable — Citation.__post_init__ enforces at least one.
    return f"cannavec_anon_{hashlib.sha256(citation.label.encode('utf-8')).hexdigest()[:8]}"


def _evidence_level_for_citation(answer: "Answer | None",
                                 citation: "Citation") -> str | None:
    """Look up the best-supportable evidence grade for this citation.

    The lookup walks ``answer.claims`` and returns the highest grade of
    any claim whose source list contains a Source matching this
    citation's PMID/DOI/URL. Returns ``None`` if no Answer is supplied
    or no matching claim is found.
    """
    if answer is None:
        return None
    try:
        from cannavec_science.evidence import EvidenceLevel as _EL
    except ImportError:
        return None
    best: "_EL | None" = None
    for claim in answer.claims:
        for s in claim.sources:
            same = (
                (citation.pmid and s.pmid == citation.pmid)
                or (citation.doi and s.doi == citation.doi)
                or (citation.url and s.url == citation.url)
            )
            if not same:
                continue
            try:
                g = claim.best_supportable_grade()
            except Exception:
                g = None
            if g is None:
                continue
            if best is None or g.rank > best.rank:
                best = g
    if best is None:
        return None
    return best.value


def bibliography_from_answer(answer: "Answer") -> tuple[BibliographyEntry, ...]:
    """Build a deterministic list of :class:`BibliographyEntry` from an
    :class:`Answer`.

    Citations are sorted by (PMID asc, DOI asc, URL asc, label asc) so
    two equivalent answers produce byte-identical bibliographies.
    """
    rows: list[BibliographyEntry] = []
    for c in answer.citations:
        rows.append(_entry_from_citation(c, answer=answer))
    rows.sort(key=lambda r: (
        r.pmid or "~",          # tilde sorts after digits so PMID-less last
        r.doi or "~",
        r.url or "~",
        r.title,
    ))
    return tuple(rows)


def _entry_from_citation(citation: "Citation",
                         *, answer: "Answer | None" = None) -> BibliographyEntry:
    """Build a single BibliographyEntry from a Citation.

    Author and journal are derived from the label's *structure* (never by
    naive comma tokenization) so the export drops cleanly into Zotero /
    Mendeley with real surnames and the real journal — see
    :func:`_parse_label`. Volume / issue / pages are emitted only when the
    Citation carries them (the curated data model does not, so they are
    left empty rather than fabricated).
    """
    authors, journal = _parse_label(citation.label)
    return BibliographyEntry(
        cite_key=_bibtex_cite_key(citation),
        title=citation.label,
        authors=authors,
        year=citation.year or _extract_year_from_label(citation.label),
        journal=journal,
        volume=str(getattr(citation, "volume", "") or ""),
        issue=str(getattr(citation, "issue", "") or ""),
        pages=str(getattr(citation, "pages", "") or ""),
        pmid=citation.pmid,
        doi=citation.doi,
        url=citation.url,
        evidence_level=_evidence_level_for_citation(answer, citation),
        note=citation.note or "",
    )


# ── Renderers ──────────────────────────────────────────────────────────


def _split_pages(pages: str) -> tuple[str, str]:
    """Split a page range ``"2011-2020"`` into ``("2011", "2020")``.

    Accepts hyphen, en-dash, or em-dash separators. A single page (no
    separator) returns ``(page, "")`` so the RIS ``EP`` line is omitted.
    """
    m = re.match(r"\s*([0-9A-Za-z]+)\s*[-–—]\s*([0-9A-Za-z]+)\s*$", pages)
    if m:
        return m.group(1), m.group(2)
    return pages.strip(), ""


def _bibtex_escape(s: str) -> str:
    r"""Escape BibTeX metacharacters in field values.

    Conservative: BibTeX treats ``{`` / ``}`` / ``%`` / ``\`` /
    ``#`` specially. We wrap the whole field in braces so most
    characters pass through; the special chars are still escaped.
    """
    return (
        s.replace("\\", r"\\")
         .replace("{", r"\{")
         .replace("}", r"\}")
         .replace("%", r"\%")
         .replace("#", r"\#")
         .replace("&", r"\&")
    )


def render_bibtex(entries: Iterable[BibliographyEntry]) -> str:
    """Render a sequence of :class:`BibliographyEntry` as a BibTeX file.

    Each entry is one ``@article{...}`` record with the fields
    ``title``, ``author``, ``year``, ``journal``, ``volume``,
    ``number``, ``pages``, ``pmid``, ``doi``, ``url``, ``note``. Empty
    fields are omitted.
    """
    lines: list[str] = []
    lines.append("% Cannavec Science bibliography — BibTeX export")
    lines.append("% See https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin")
    lines.append("")
    for e in entries:
        lines.append(f"@article{{{e.cite_key},")
        lines.append(f"  title   = {{{_bibtex_escape(e.title)}}},")
        if e.authors:
            lines.append(
                f"  author  = {{{_bibtex_escape(' and '.join(e.authors))}}},"
            )
        if e.year is not None:
            lines.append(f"  year    = {{{e.year}}},")
        if e.journal:
            lines.append(f"  journal = {{{_bibtex_escape(e.journal)}}},")
        if e.volume:
            lines.append(f"  volume  = {{{_bibtex_escape(e.volume)}}},")
        if e.issue:
            lines.append(f"  number  = {{{_bibtex_escape(e.issue)}}},")
        if e.pages:
            lines.append(f"  pages   = {{{_bibtex_escape(e.pages)}}},")
        if e.pmid:
            lines.append(f"  pmid    = {{{_bibtex_escape(e.pmid)}}},")
        if e.doi:
            lines.append(f"  doi     = {{{_bibtex_escape(e.doi)}}},")
        if e.url:
            lines.append(f"  url     = {{{_bibtex_escape(e.url)}}},")
        note = e.note
        if e.evidence_level:
            grade_note = f"Cannavec GRADE: {e.evidence_level}"
            note = (note + " | " + grade_note) if note else grade_note
        if note:
            lines.append(f"  note    = {{{_bibtex_escape(note)}}},")
        lines.append("}")
        lines.append("")
    # Drop the trailing blank line for byte-stable output.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def render_ris(entries: Iterable[BibliographyEntry]) -> str:
    """Render a sequence of :class:`BibliographyEntry` as a RIS file.

    Each record:
    ``TY  - JOUR``
    ``TI  - <title>``
    ``AU  - <author>`` (one per line)
    ``PY  - <year>``
    ``JO  - <journal>``
    ``VL  - <volume>``
    ``IS  - <issue>``
    ``SP  - <start page>`` / ``EP  - <end page>``
    ``M2  - PMID:<pmid>`` (the de-facto PMID line in Zotero RIS exports)
    ``DO  - <doi>``
    ``UR  - <url>``
    ``N1  - <note>``
    ``ER  -``
    """
    lines: list[str] = []
    for e in entries:
        lines.append("TY  - JOUR")
        lines.append(f"TI  - {e.title}")
        for author in e.authors:
            lines.append(f"AU  - {author}")
        if e.year is not None:
            lines.append(f"PY  - {e.year}")
        if e.journal:
            lines.append(f"JO  - {e.journal}")
        if e.volume:
            lines.append(f"VL  - {e.volume}")
        if e.issue:
            lines.append(f"IS  - {e.issue}")
        if e.pages:
            start, end = _split_pages(e.pages)
            lines.append(f"SP  - {start}")
            if end:
                lines.append(f"EP  - {end}")
        if e.pmid:
            lines.append(f"M2  - PMID:{e.pmid}")
        if e.doi:
            lines.append(f"DO  - {e.doi}")
        if e.url:
            lines.append(f"UR  - {e.url}")
        note = e.note
        if e.evidence_level:
            grade_note = f"Cannavec GRADE: {e.evidence_level}"
            note = (note + " | " + grade_note) if note else grade_note
        if note:
            lines.append(f"N1  - {note}")
        lines.append("ER  - ")
        lines.append("")
    # Drop the trailing blank for byte-stable output.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def render_csljson(entries: Iterable[BibliographyEntry]) -> str:
    """Render a sequence of :class:`BibliographyEntry` as CSL-JSON.

    The output is a list of CSL-JSON objects (one per entry). Indented
    with two spaces and sorted keys so the output is byte-deterministic.
    """
    return json.dumps(
        [e.to_csljson() for e in entries],
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def render(entries: Iterable[BibliographyEntry], format: str) -> str:
    """Dispatch to the per-format renderer.

    Supported formats: ``"bibtex"``, ``"ris"``, ``"csljson"`` (case
    insensitive, hyphens optional).
    """
    f = format.strip().lower().replace("-", "")
    if f == "bibtex":
        return render_bibtex(entries)
    if f == "ris":
        return render_ris(entries)
    if f in {"csljson", "json", "csl"}:
        return render_csljson(entries)
    raise ValueError(
        f"Unknown bibliography format: {format!r}. "
        f"Expected one of: bibtex, ris, csljson."
    )


__all__ = [
    "BibliographyEntry",
    "bibliography_from_answer",
    "render_bibtex",
    "render_ris",
    "render_csljson",
    "render",
]
