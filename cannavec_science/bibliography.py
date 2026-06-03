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


def _parse_author_to_csl(name: str) -> dict:
    """Best-effort author parsing into CSL ``{family, given}`` shape."""
    name = name.strip()
    if not name:
        return {"literal": ""}
    # If the label is "Surname YYYY" or "Surname et al.", take the first
    # token as the family name. If it's "Surname, F." use the comma split.
    if "," in name:
        family, _, given = name.partition(",")
        return {"family": family.strip(), "given": given.strip()}
    parts = name.split()
    if len(parts) == 1:
        return {"family": parts[0]}
    # Heuristic: last token is family in Western convention; "et al."
    # / "and colleagues" / year-only tokens get dropped from the given
    # field.
    drop = {"et", "al.", "al", "and", "colleagues", "co-authors"}
    given_parts = [p for p in parts[:-1] if p.lower() not in drop and not p.isdigit()]
    return {"family": parts[-1], "given": " ".join(given_parts)}


def _extract_authors_from_label(label: str) -> tuple[str, ...]:
    """Pull author strings out of a Cannavec citation label.

    The conventional label shape is ``"<Surname> <Year> — <Title>"`` or
    ``"<Surname> <Year>, <Title>"``. We extract the leading surname token
    and return it as the single-author list. Multi-author labels using
    ``"<S1> & <S2>"`` or ``"<S1>, <S2>, <S3>"`` are also handled.
    """
    # The leading chunk before the first separator (em-dash, colon, comma,
    # open-paren, or a 4-digit year) is the author segment; everything after is
    # title / journal. The comma needs no preceding space ("Pertwee RG,").
    head = re.split(
        r"\s*(?:—|--|–|:|,|\()\s*|\s+(?=(?:19|20)\d{2}\b)", label, maxsplit=1
    )[0]
    head = re.sub(r"\b(?:19|20)\d{2}\b", "", head).strip(" .,&")
    # Must look like a name (starts with an uppercase letter), else this label
    # is a free-text description (journal / title / keywords) with no parsable
    # author — return nothing rather than mangle it into fake authors.
    if not head or not head[0].isalpha() or not head[0].isupper():
        return ()
    # Multiple authors ONLY on a real word-boundary connector (" and " / " & "),
    # never the substring "and" inside a word (the "ligand" → "lig"+"and" bug).
    parts = re.split(r"\s+(?:and|&)\s+", head)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p.lower() not in {"et al.", "et al", "the", "for", "a"}:
            out.append(p)
    return tuple(out)


def _extract_year_from_label(label: str) -> int | None:
    m = re.search(r"\b(19\d{2}|20\d{2})\b", label)
    if m:
        return int(m.group(1))
    return None


def _extract_journal_from_label(label: str) -> str:
    """Pull a journal hint from the citation label.

    Cannavec labels often carry the journal name after the title
    em-dash, but the convention is irregular. We only return a hint when
    the label contains a recognizable journal abbreviation pattern.
    """
    # Conservative: if the label has " - <Journal>" or " (Journal Name)"
    # we extract the trailing capitalised phrase.
    m = re.search(r"[-—–]\s*([A-Z][A-Za-z][A-Za-z\s&]+(?:Journal|Med|"
                  r"Lancet|JAMA|NEJM|BMJ|Nature|Cell|Science|Pharm\w*|"
                  r"Cannabis\w*|Epilep\w*|Neuro\w*|Oncol\w*|Cardiol\w*|"
                  r"Psychiat\w*|Hepatol\w*))\b",
                  label)
    if m:
        return m.group(1).strip()
    return ""


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
    """Build a single BibliographyEntry from a Citation."""
    return BibliographyEntry(
        cite_key=_bibtex_cite_key(citation),
        title=citation.label,
        authors=_extract_authors_from_label(citation.label),
        year=citation.year or _extract_year_from_label(citation.label),
        journal=_extract_journal_from_label(citation.label),
        pmid=citation.pmid,
        doi=citation.doi,
        url=citation.url,
        evidence_level=_evidence_level_for_citation(answer, citation),
        note=citation.note or "",
    )


# ── Renderers ──────────────────────────────────────────────────────────


def _bibtex_escape(s: str) -> str:
    """Escape BibTeX metacharacters in field values.

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
    ``title``, ``author``, ``year``, ``journal``, ``pmid``, ``doi``,
    ``url``, ``note``. Empty fields are omitted.
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
    ``JF  - <journal>``
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
            lines.append(f"JF  - {e.journal}")
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
