"""Polished, citation-lossless PDF/HTML rendering of a verified Answer (`/cv:pdf`).

The flagship output transform (§XI): turn the canonical verified
:class:`~cannavec_science.answer.Answer` into a clean, professional
*evidence brief* a researcher can hand to a colleague or a regulator — every
primary-source identifier and every GRADE label preserved, none inflated. It is a
**transform of already-verified evidence, never an author of it** (M5 / §II): it
renders exactly what the backbone graded, and refuses to emit anything it cannot
preserve losslessly.

Two layers, cleanly separated so the offline core never depends on the renderer
(Constitution §X):

  * ``render_html(answer)`` — pure, stdlib-only, deterministic. Builds a
    self-contained, print-optimized HTML evidence brief (clinical-journal style)
    from the Answer model. This is the canonical artifact and the surface the
    citation-lossless + grade gates run on. It ALWAYS works, on any machine.
  * ``export_pdf(...)`` — writes the HTML, then renders it to PDF via the best
    available backend (headless Chrome, else a pure-Python reportlab fallback),
    and gracefully degrades to "open the HTML and print to PDF" when neither is
    present. The optional backends are imported lazily, so importing this module
    needs nothing but the stdlib.

The gate (the line between a value-adding transform and noise) is enforced in
code, not prose: ``assert_render_faithful`` runs the §XI identifier floor over
the whole document and the strict per-citation grade-equality checks
(``grade_adjacency_failures`` + ``grade_inflation_failures``) over the *evidence
surface* — the BLUF, graded claims, and reference list, where citations are
presented as the answer's evidence. The curated-background monograph sections are
explicitly "verify before citing" reference material; they are covered by the
identifier floor, and their registry-internal grade labels are not read as the
citations' grades.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from cannavec_science._pdf_style import CLINICAL_BRIEF_CSS
from cannavec_science.export import (
    assert_citation_lossless,
    export_provenance,
    grade_adjacency_failures,
    grade_inflation_failures,
)

if TYPE_CHECKING:
    from cannavec_science.answer import Answer


__all__ = [
    "FaithfulnessError",
    "RenderResult",
    "render_html",
    "assert_render_faithful",
    "export_pdf",
]


# GRADE → restrained, accessible badge colour (white text on each). Data-viz as
# part of the design system: a single calm scale, strongest → weakest.
_GRADE_COLOR = {
    "Level A": "#0b6b3a",  # deep green
    "Level B": "#15607a",  # deep teal
    "Level C": "#9a5b00",  # amber
    "Level D": "#5b6470",  # slate
    "Level E": "#717784",  # light slate
    "Unsupported": "#8a8f98",
}
_GRADE_CLASS = {
    "Level A": "ga", "Level B": "gb", "Level C": "gc",
    "Level D": "gd", "Level E": "ge", "Unsupported": "gu",
}

# Chrome's print-to-pdf produces the best-looking output; resolved once per call.
_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome-stable",
    "google-chrome",
    "chromium-browser",
    "chromium",
)


class FaithfulnessError(RuntimeError):
    """A rendered transform failed the §XI gate (dropped/softened/inflated a
    citation or GRADE). The renderer refuses to emit rather than ship noise."""


@dataclass(frozen=True)
class RenderResult:
    """Outcome of an :func:`export_pdf` call."""

    html_path: str
    pdf_path: "str | None"
    backend: str  # "chrome" | "reportlab" | "none"
    state: str    # "brief" | "no_evidence" | "refusal"
    n_citations: int = 0
    notes: tuple = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return True

    def summary(self) -> str:
        where = self.pdf_path or self.html_path
        how = {
            "chrome": "rendered to PDF via headless Chrome",
            "reportlab": "rendered to PDF via reportlab",
            "none": "no PDF backend found — open the HTML and Print → Save as PDF",
        }[self.backend]
        state = {
            "brief": f"evidence brief ({self.n_citations} verified citations)",
            "no_evidence": "honest 'no curated efficacy evidence' brief",
            "refusal": "refusal brief (no evidence woven)",
        }[self.state]
        return f"{state}: {how} → {where}"


# --------------------------------------------------------------------------- #
# Inline / block content helpers (a tiny, safe Markdown-ish → HTML transform). #
# Content originates from our own registries, but is escaped regardless        #
# (correctness + defence-in-depth). Only **bold**, `code`, and bullet/quote    #
# block structure are interpreted; everything else is literal text.            #
# --------------------------------------------------------------------------- #

def _inline(text: str) -> str:
    out = html.escape(text or "")
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def _block(text: str) -> str:
    """Render a free-text block (a section body) preserving bullets, blockquotes,
    headings, and paragraphs — faithful to the Markdown the brief already shows."""
    lines = (text or "").split("\n")
    html_parts: list[str] = []
    bullets: list[str] = []

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{b}</li>" for b in bullets)
            html_parts.append(f"<ul>{items}</ul>")
            bullets.clear()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_bullets()
            continue
        m_bullet = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m_bullet:
            indent = len(m_bullet.group(1))
            cls = ' class="sub"' if indent >= 2 else ""
            bullets.append(f'<span{cls}>{_inline(m_bullet.group(2))}</span>')
            continue
        flush_bullets()
        if stripped.startswith("### "):
            html_parts.append(f"<h4>{_inline(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h4>{_inline(stripped[3:])}</h4>")
        elif stripped.startswith("> "):
            html_parts.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
        else:
            html_parts.append(f"<p>{_inline(stripped)}</p>")
    flush_bullets()
    return "\n".join(html_parts)


def _grade_badge(grade: "str | None") -> str:
    if not grade:
        return ""
    cls = _GRADE_CLASS.get(grade, "gu")
    return f'<span class="grade {cls}">{html.escape(grade)}</span>'


# HTML-comment markers (invisible in any rendered output) fence the EVIDENCE
# SURFACE — the regions where citations are presented as the answer's evidence
# (BLUF prose, graded claims, the reference list). The strict per-citation grade
# checks run over exactly these regions, extracted from the ACTUAL rendered HTML
# (so tampering is caught), and skip the document-level top-grade summary and the
# curated-background sections (covered by the whole-document identifier floor).
_EV_OPEN = "<!--CV:EV-->"
_EV_CLOSE = "<!--/CV:EV-->"


def _ev(fragment: str) -> str:
    return f"{_EV_OPEN}{fragment}{_EV_CLOSE}"


# A baked-in inline citation in composed prose — exactly the `Citation.inline`
# shapes "(PMID 123, Level B)", "(doi:10.x, Level A)", "(https://…)". Rendered as
# a clean chip so the identifier + GRADE stay visible (grounding) and adjacent
# (the gate reads them as a unit) while the prose loses the raw-parenthesis
# clutter. Other parentheticals (dose ranges, "(adults)", "(FDA)") never match.
_CITE_TOKEN_RE = re.compile(
    r"\((PMID\s\d+|doi:[^\s,)]+|https?://[^\s,)]+)(,\sLevel\s[A-E])?\)"
)


def _chipify_cites(escaped_html: str) -> str:
    """Turn baked-in inline citation parentheticals in already-escaped prose into
    styled citation chips. A non-matching parenthetical is left untouched, so no
    identifier or GRADE can be lost — worst case a citation stays a raw paren."""
    return _CITE_TOKEN_RE.sub(
        lambda m: f'<span class="cite">{m.group(1)}{m.group(2) or ""}</span>',
        escaped_html,
    )


def _cite_chip(label: str) -> str:
    """One citation chip (``label`` already safe), e.g. ``PMID 28538134, Level B``."""
    return f'<span class="cite">{label}</span>'


# --------------------------------------------------------------------------- #
# Fragment builders. Returned separately so the strict per-citation grade gate #
# can run over the EVIDENCE SURFACE (bluf + claims + references) only.          #
# --------------------------------------------------------------------------- #

def _masthead(answer: "Answer") -> str:
    es = answer.evidence_summary
    grade = es.highest_grade.value if es else None
    meta = [f'<span class="meta-k">Audience</span> {html.escape(answer.audience)}']
    if answer.generated_at:
        meta.append(
            f'<span class="meta-k">Generated</span> '
            f'{html.escape(answer.generated_at)}'
        )
    if grade and grade != "Unsupported":
        meta.append(
            f'<span class="meta-k">Top grade</span> {_grade_badge(grade)}'
        )
    return (
        '<header class="masthead">'
        '<div class="brand">CANNAVEC SCIENCE</div>'
        '<div class="eyebrow">Evidence Brief</div>'
        f'<h1>{_inline(answer.prompt)}</h1>'
        f'<div class="meta">{" &middot; ".join(meta)}</div>'
        "</header>"
    )


def _bluf(answer: "Answer") -> str:
    if not answer.short_answer:
        return ""
    es = answer.evidence_summary
    grade = es.highest_grade.value if es else None
    badge = _grade_badge(grade) if grade and grade != "Unsupported" else ""
    return (
        '<section class="bluf">'
        '<div class="bluf-head"><span class="eyebrow">Bottom line</span>'
        f"{badge}</div>"
        f'<div class="bluf-body">{_ev(_chipify_cites(_inline(answer.short_answer)))}</div>'
        "</section>"
    )


def _summary(answer: "Answer") -> str:
    es = answer.evidence_summary
    if es is None:
        return ""
    stats = [
        ("Highest grade", es.highest_grade.value),
        ("Claims", str(es.n_claims)),
        ("With primary source", str(es.n_with_primary_source)),
    ]
    if es.n_missing_required_disclosures:
        stats.append(("Missing disclosures", str(es.n_missing_required_disclosures)))
    if es.n_retracted_citations:
        stats.append(("Suppressed (retracted)", str(es.n_retracted_citations)))
    cells = "".join(
        f'<div class="stat"><div class="stat-v">{html.escape(v)}</div>'
        f'<div class="stat-k">{html.escape(k)}</div></div>'
        for k, v in stats
    )
    notes = "".join(f"<li>{_inline(n)}</li>" for n in es.notes)
    notes_html = f'<ul class="summary-notes">{notes}</ul>' if notes else ""
    return f'<section class="summary"><div class="stats">{cells}</div>{notes_html}</section>'


def _claims(answer: "Answer") -> str:
    if not answer.claims:
        return ""
    from cannavec_science.answer import Citation, _effect_estimates_for_claim

    rows: list[str] = []
    for claim in answer.claims:
        grade = claim.best_supportable_grade()
        # Citations as a chip-row beneath the claim (not inline in the sentence):
        # identifier + GRADE stay visible and adjacent (the gate reads the chip as
        # a unit), but the prose is no longer broken up by raw "(PMID …)" parens.
        chips = "".join(
            _cite_chip(_inline(Citation.from_source(s, grade=grade).inline[1:-1]))
            for s in claim.sources
        )
        cite_html = f'<div class="cite-row">{chips}</div>' if chips else ""
        est_html = ""
        ests = _effect_estimates_for_claim(claim)
        if ests:
            blocks = []
            for e in ests:
                dl = [f'<dt>Effect (PMID {html.escape(str(e.pmid))})</dt>']
                pairs = [
                    ("n", e.n), ("Comparator", e.comparator),
                    ("Primary outcome", e.primary_outcome),
                    ("Effect size", e.effect_size),
                    ("95% CI / P", e.confidence_interval),
                    ("NNT", e.nnt),
                ]
                for label, val in pairs:
                    if val not in (None, ""):
                        dl.append(
                            f"<dd><span class='ek'>{label}:</span> "
                            f"{_inline(str(val))}</dd>"
                        )
                if e.nnt_caveat:
                    dl.append(
                        f"<dd class='caveat'><span class='ek'>&#9888; NNT caveat:</span> "
                        f"{_inline(str(e.nnt_caveat))}.</dd>"
                    )
                blocks.append(f"<dl class='effect'>{''.join(dl)}</dl>")
            est_html = "".join(blocks)
        rows.append(
            '<div class="claim">'
            f'<div class="claim-grade">{_grade_badge(grade.value)}</div>'
            f'<div class="claim-body">{_inline(claim.text)}{cite_html}{est_html}</div>'
            "</div>"
        )
    return (
        '<section class="claims"><h2>Graded claims</h2>'
        + _ev("".join(rows))
        + "</section>"
    )


def _references(answer: "Answer") -> str:
    """Numbered reference list. The GRADE badge is placed IMMEDIATELY after each
    identifier so the grade is tightly bound to its citation (the gate reads them
    as a unit); an ungraded reference-context citation carries NO badge."""
    if not answer.citations:
        return ""
    from cannavec_science.answer import _lookup_citation_grade

    grade_map = answer._citation_grade_map()
    items: list[str] = []
    for c in answer.citations:
        grade = _lookup_citation_grade(grade_map, c)
        year = f" ({html.escape(str(c.year))})" if c.year else ""
        if c.pmid:
            id_text = f"PMID {html.escape(c.pmid)}"
        elif c.doi:
            id_text = f"doi:{html.escape(c.doi)}"
        else:
            id_text = html.escape(c.url or "")
        url = html.escape(c.resolvable_url)
        badge = f" {_grade_badge(grade)}" if grade else ""
        items.append(
            "<li>"
            f'<span class="ref-label">{_inline(c.label)}</span>{year}. '
            f'<a href="{url}">{id_text}</a>{badge}'
            "</li>"
        )
    return (
        '<section class="references"><h2>References</h2>'
        + _ev(f"<ol>{''.join(items)}</ol>")
        + "</section>"
    )


def _sections(answer: "Answer") -> str:
    if not answer.sections:
        return ""
    blocks = [
        '<section class="background"><div class="bg-notice">'
        "<strong>Curated reference (background).</strong> Graded background from "
        "the curated registries — scaffolding to reason over, <em>not</em> a "
        "live-verified answer and not the intelligence itself. Verify each "
        "identifier before citing (Constitution &sect;I / M5)."
        "</div>"
    ]
    for heading, body in answer.sections:
        blocks.append(f"<h3>{_inline(heading)}</h3>{_block(body)}")
    blocks.append("</section>")
    return "".join(blocks)


def _findings(answer: "Answer") -> str:
    from cannavec_science.answer import _LIVE_FLAGGED_STATUSES

    out: list[str] = []
    if answer.verified_findings:
        rows = []
        for f in answer.verified_findings:
            yr = f" ({html.escape(str(f['year']))})" if f.get("year") else ""
            grade = f.get("grade") or "verified"
            status = f.get("retraction_status", "clean")
            badge = " &#9888; " + html.escape(status.upper()) if status in _LIVE_FLAGGED_STATUSES else ""
            quote = f"<blockquote>&ldquo;{_inline(f['quote'])}&rdquo;</blockquote>" if f.get("quote") else ""
            by = f" — approved by {_inline(f['approver'])}" if f.get("approver") else ""
            url = f' — <a href="{html.escape(f["url"])}">{html.escape(f["url"])}</a>' if f.get("url") else ""
            rows.append(
                f'<li><span class="tag">{html.escape(f["source_tag"])} &middot; '
                f'{html.escape(grade)}</span>{badge} <code>{html.escape(f["identifier"])}</code>{yr} '
                f"{_inline(f.get('label', ''))}{by}{url}{quote}</li>"
            )
        out.append(
            '<section class="verified"><h2>Verified breadth — gate-passed, human-approved</h2>'
            "<p class='note'>Primary sources that cleared the same admission gate as a "
            "curated claim and were promoted by a named curator (&sect;IX). Each carries a "
            "conservative single-source GRADE and never re-grades the core.</p>"
            f"<ul>{''.join(rows)}</ul></section>"
        )
    if answer.live_findings or answer.live_synthesis:
        head = []
        if answer.live_synthesis:
            conv = answer.live_synthesis.get("convergence", "NONE")
            counts = answer.live_synthesis.get("per_source_counts", {}) or {}
            present = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()) if v) or "no live rows returned"
            head.append(f"<p><strong>Cross-source synthesis: {html.escape(str(conv))}</strong> — "
                        f"convergence across the live primary-source tier ({html.escape(present)}).</p>")
        rows = []
        for f in answer.live_findings:
            yr = f" ({html.escape(str(f['year']))})" if f.get("year") else ""
            status = f.get("retraction_status", "clean")
            badge = " &#9888; " + html.escape(status.upper()) if status in _LIVE_FLAGGED_STATUSES else ""
            url = f' — <a href="{html.escape(f["url"])}">{html.escape(f["url"])}</a>' if f.get("url") else ""
            rows.append(
                f'<li><span class="tag">{html.escape(f["source_tag"])}</span>{badge} '
                f'<code>{html.escape(f["identifier"])}</code>{yr} {_inline(f.get("label",""))} '
                f"— provisional grade: {_inline(f['provisional_grade'])}{url}</li>"
            )
        out.append(
            '<section class="live"><h2>Live discovery — provisional, not curated</h2>'
            "<p class='note'>Live-source breadth woven onto the verified curated core "
            "(&sect;IX). Provenance-tagged, reranked, retraction-checked, but carrying NO "
            "curated grade — verify each identifier before citing.</p>"
            + "".join(head) + f"<ul>{''.join(rows)}</ul></section>"
        )
    return "".join(out)


def _cautions(answer: "Answer") -> str:
    blocks: list[str] = []
    if answer.cautions:
        items = "".join(f"<li>{_inline(c)}</li>" for c in answer.cautions)
        blocks.append(f'<section class="cautions"><h2>Cautions</h2><ul>{items}</ul></section>')
    if answer.notes:
        items = "".join(f"<li>{_inline(n)}</li>" for n in answer.notes)
        blocks.append(f'<section class="notes"><h2>Notes</h2><ul>{items}</ul></section>')
    if answer.rigor_violations:
        items = []
        for v in answer.rigor_violations:
            res = f"<br><span class='ek'>Resolution:</span> {_inline(v['resolution'])}" if v.get("resolution") else ""
            items.append(f"<li><strong>{_inline(v['detector'])}</strong>: {_inline(v.get('match',''))}{res}</li>")
        blocks.append(f'<section class="rigor"><h2>Rigor violations (prompt)</h2><ul>{"".join(items)}</ul></section>')
    return "".join(blocks)


def _refusal_body(answer: "Answer") -> str:
    reason = answer.refusal_reason or "Cannavec Science cannot answer this prompt as posed."
    return (
        '<section class="refusal"><div class="refusal-head">'
        '<span class="eyebrow">Refusal</span></div>'
        f'<div class="refusal-body">{_block(reason)}</div>'
        "<p class='note'>This is the system declining to fabricate an answer — a "
        "credibility feature, not a failure. No evidence is woven for a refused "
        "prompt (Constitution &sect;V).</p></section>"
    )


def _footer(answer: "Answer") -> str:
    return (
        '<footer class="docfoot">'
        "<p>Generated by <strong>Cannavec&nbsp;Science</strong> — a research-grounding "
        "and verification layer. Every identifier above was confirmed real and not "
        "retracted, and every GRADE label is the level the deterministic backbone "
        "assigned; this document is a citation-lossless transform of the verified "
        "answer (Constitution &sect;XI). It is research grounding, not medical advice.</p>"
        "</footer>"
    )




def render_html(answer: "Answer") -> str:
    """Render ``answer`` as a self-contained, print-optimized clinical-journal
    evidence brief (HTML). Pure, deterministic, stdlib-only.

    Three honest states, all citation-lossless:
      * refusal — a clearly-marked refusal page, no evidence woven;
      * no curated evidence (0 claims) — an honest "no efficacy evidence" page
        with the compound background framed as NOT indication-specific evidence;
      * full evidence brief.
    """
    if answer.is_refusal:
        state_body = _refusal_body(answer)
    elif not answer.claims:
        banner = (
            '<section class="bluf"><div class="bluf-head">'
            '<span class="eyebrow">No curated efficacy evidence</span></div>'
            '<div class="bluf-body">Cannavec Science has <strong>no curated '
            "efficacy evidence</strong> for this question. The material below is "
            "general compound background, <strong>not</strong> indication-specific "
            "evidence — and the references are not evidence for the asked question. "
            "For the live frontier, use <code>/cv:discover</code> or "
            "<code>/cv:research</code>.</div></section>"
        )
        state_body = (
            banner + _sections(answer) + _findings(answer)
            + _cautions(answer) + _references(answer)
        )
    else:
        state_body = (
            _bluf(answer) + _summary(answer) + _claims(answer) + _sections(answer)
            + _findings(answer) + _cautions(answer) + _references(answer)
        )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(answer.prompt)} — Cannavec Science</title>"
        f"<style>{CLINICAL_BRIEF_CSS}</style></head><body><main class='page'>"
        + _masthead(answer) + state_body + _footer(answer)
        + "</main></body></html>"
    )


def _evidence_surface(full_html: str) -> str:
    """Concatenate the EVIDENCE-SURFACE regions (BLUF prose, graded claims,
    reference list) extracted from the ACTUAL rendered HTML — the regions where
    citations stand as the answer's evidence. Strict per-citation grade checks run
    here; the curated-background sections and the document-level top-grade summary
    are deliberately outside it (the whole-document identifier floor covers the
    former; the latter is a summary, not a citation's grade)."""
    return "".join(
        re.findall(
            re.escape(_EV_OPEN) + "(.*?)" + re.escape(_EV_CLOSE),
            full_html,
            flags=re.S,
        )
    )


# Inline styles that hide content — forbidden in the evidence surface so a render
# cannot show a fake citation while keeping the real identifier present-but-hidden
# to satisfy the floor. The renderer never inlines styles, so this only ever trips
# on tampering.
_HIDE_STYLE_RE = re.compile(
    r"(display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?![.\d])"
    r"|font-size\s*:\s*0(?![.\d])|aria-hidden\s*=\s*[\"']true)",
    re.IGNORECASE,
)


def assert_render_faithful(answer: "Answer", rendered_html: str) -> None:
    """Raise :class:`FaithfulnessError` unless ``rendered_html`` preserved every
    identifier + GRADE label (§XI) and inflated none of them (§VII).

    The identifier + GRADE-presence floor runs over the whole document. The strict
    per-citation checks run over the EVIDENCE SURFACE (BLUF prose, graded claims,
    references) — exactly where citations stand as the answer's evidence and where
    a grade beside an ungraded citation can only be an overclaim, never background:

    - anti-softening (``grade_adjacency_failures``): the true grade sits by its id;
    - anti-overclaim (``grade_inflation_failures(flag_ungraded=True)``): no grade
      label outranks its citation's verified grade, and NO grade is attached to an
      ungraded, reference-context citation (the bind is by bare identifier, so a
      non-canonical URL cannot dodge it, and homoglyph grades are folded/flagged);
    - no hidden content: the surface may not carry content-hiding inline styles
      that would let a real identifier satisfy the floor while a fake is shown.

    The inflation scan reads NORMALIZED VISIBLE TEXT (entities decoded, tags/
    comments stripped, enclosed-letterform + NFKD + script-confusable folded), and
    the grade slot after a ``Level``/``Grade`` anchor is recognised DENY-BY-DEFAULT
    (ASCII A–E, or a tier digit / Roman numeral / homoglyph → flagged), so an
    entity/tag split, a homoglyph, an enclosed symbol (🅰), or a "Level 1"/"Level I"
    tier cannot slip a fake grade past an ASCII allowlist.

    Honest boundary: this guards the ``Level``/``Grade`` + A–E lexeme relative to
    the verified Answer. It does NOT treat ``Class A`` as a grade (it is legitimate
    domain vocabulary here — CB1/CB2 are Class-A GPCRs), nor does it police a
    free-prose certainty claim an author might invent ("definitive evidence"). Both
    are acceptable: the renderer never authors prose or alternate grade schemes
    (M5), and ``export_pdf`` gates ``render_html``'s own output with no untrusted
    post-render step — this adversarial-tamper hardening is defense-in-depth for
    future output skills, not a guard against the current renderer.
    """
    report = assert_citation_lossless(answer, rendered_html)
    if not report:
        raise FaithfulnessError(report.summary())
    surface = _evidence_surface(rendered_html)
    soft = grade_adjacency_failures(answer, surface)
    if soft:
        raise FaithfulnessError(
            "GRADE softened/dropped beside: "
            + ", ".join(a.identifier for a in soft)
        )
    inflated = grade_inflation_failures(answer, surface, flag_ungraded=True)
    if inflated:
        raise FaithfulnessError(
            "GRADE inflated beside: " + ", ".join(a.identifier for a in inflated)
        )
    if _HIDE_STYLE_RE.search(surface):
        raise FaithfulnessError(
            "evidence surface contains content-hiding markup (a real identifier "
            "could be hidden while a fake is shown)"
        )


# --------------------------------------------------------------------------- #
# PDF backends (lazy, gracefully degrading).                                    #
# --------------------------------------------------------------------------- #

def _find_chrome() -> "str | None":
    override = os.environ.get("CANNAVEC_CHROME")
    if override and (Path(override).exists() or shutil.which(override)):
        return override
    for cand in _CHROME_CANDIDATES:
        if Path(cand).exists() or shutil.which(cand):
            return cand if Path(cand).exists() else shutil.which(cand)
    return None


_CHROME_QUIET = (
    "--disable-gpu", "--no-sandbox", "--no-first-run",
    "--no-default-browser-check", "--disable-extensions",
    "--disable-background-networking", "--disable-sync",
    "--disable-default-apps", "--disable-breakpad",
    "--disable-crash-reporter", "--disable-features=Translate",
    "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
    "--virtual-time-budget=5000",
)


def _chrome_pdf(chrome: str, html_path: str, pdf_path: str) -> bool:
    """Render ``html_path`` to ``pdf_path`` via headless Chrome. Each attempt uses
    a FRESH, isolated profile dir (so a process-singleton/profile race on a cold
    start cannot corrupt a shared profile); ``--headless=new`` is tried first with
    a fallback to the classic flag for older builds. Returns True only when a
    non-empty PDF actually lands."""
    src = Path(html_path).resolve()
    target = Path(pdf_path)
    if target.exists():
        target.unlink()
    for headless in ("--headless=new", "--headless"):
        with tempfile.TemporaryDirectory(prefix="cannavec-chrome-") as profile:
            cmd = [
                chrome, headless, f"--user-data-dir={profile}",
                *_CHROME_QUIET, f"--print-to-pdf={pdf_path}", src.as_uri(),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=90, check=False)
            except (OSError, subprocess.TimeoutExpired):
                continue
        if target.exists() and target.stat().st_size > 0:
            return True
    return target.exists() and target.stat().st_size > 0


def _reportlab_pdf(answer: "Answer", pdf_path: str) -> bool:
    """Pure-Python fallback: transcribe the canonical (gate-proven) Markdown brief
    into a clean reportlab PDF. Returns False if reportlab is not installed."""
    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
        )
    except Exception:
        return False

    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="Times-Roman",
                          fontSize=9.5, leading=13, alignment=TA_LEFT)
    h1 = ParagraphStyle("h1", parent=base["Title"], fontName="Helvetica-Bold",
                        fontSize=17, leading=20, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                        fontSize=11, textColor="#15607a", spaceBefore=12, spaceAfter=4)
    bullet = ParagraphStyle("bul", parent=body, leftIndent=10)

    def md_inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        for label, color in _GRADE_COLOR.items():
            s = re.sub(rf"(?<![A-Za-z]){re.escape(label)}(?![A-Za-z])",
                       f'<font color="{color}"><b>{label}</b></font>', s)
        return s

    story: list = []
    for raw in answer.to_markdown().split("\n"):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            story.append(Spacer(1, 4))
            continue
        if s.startswith("## "):
            story.append(Paragraph(md_inline(s[3:]), h2))
        elif s.startswith("### "):
            story.append(Paragraph("<b>" + md_inline(s[4:]) + "</b>", body))
        elif re.match(r"^\s*[-*]\s+", line):
            indent = len(line) - len(line.lstrip())
            st = ParagraphStyle("b%d" % indent, parent=bullet, leftIndent=10 + indent * 6)
            story.append(Paragraph("&bull; " + md_inline(re.sub(r"^\s*[-*]\s+", "", line)), st))
        elif s.startswith("**Q:**"):
            story.append(Paragraph(md_inline(s.replace("**Q:**", "").strip()), h1))
        elif s.startswith("> "):
            story.append(Paragraph("<i>" + md_inline(s[2:]) + "</i>", bullet))
        else:
            story.append(Paragraph(md_inline(s), body))

    try:
        SimpleDocTemplate(
            pdf_path, pagesize=letter,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=16 * mm, bottomMargin=16 * mm,
            title=answer.prompt[:120],
        ).build(story)
    except Exception:
        return False
    return Path(pdf_path).exists() and Path(pdf_path).stat().st_size > 0


def export_pdf(
    answer: "Answer",
    out_prefix: str,
    *,
    html_only: bool = False,
) -> RenderResult:
    """Render ``answer`` to ``<out_prefix>.html`` (+ ``.pdf`` when a backend is
    available), gated citation-lossless. Raises :class:`FaithfulnessError` if the
    render would drop, soften, or inflate a citation/GRADE — never emits noise.

    State is computed from the Answer (refusal / no-evidence / brief); every state
    is an honest artifact. PDF backend preference: headless Chrome → reportlab →
    none (HTML only, with a 'print to PDF' note).
    """
    doc = render_html(answer)
    assert_render_faithful(answer, doc)

    state = (
        "refusal" if answer.is_refusal
        else "no_evidence" if not answer.claims
        else "brief"
    )
    n_citations = 0 if answer.is_refusal else len(export_provenance(answer))

    html_path = f"{out_prefix}.html"
    Path(html_path).write_text(doc, encoding="utf-8")

    if html_only:
        return RenderResult(html_path, None, "none", state, n_citations)

    pdf_path = f"{out_prefix}.pdf"
    chrome = _find_chrome()
    if chrome and _chrome_pdf(chrome, html_path, pdf_path):
        return RenderResult(html_path, pdf_path, "chrome", state, n_citations)
    if _reportlab_pdf(answer, pdf_path):
        return RenderResult(html_path, pdf_path, "reportlab", state, n_citations)
    return RenderResult(html_path, None, "none", state, n_citations)
