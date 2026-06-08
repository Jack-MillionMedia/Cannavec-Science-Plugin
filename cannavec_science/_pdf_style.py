"""Clinical-journal stylesheet for the /cv:pdf evidence brief.

Isolated from :mod:`cannavec_science.pdf_export` so the renderer logic stays
focused. Pure data (a CSS string), stdlib-only, inlined into the self-contained
HTML so the artifact has zero external resources (offline / CSP-friendly).

Visual direction: a restrained, credible clinical-journal evidence brief — serif
body (Iowan/Palatino/Georgia) with a sans heading/label face, a single calm
accent, semantic GRADE badges, and print-optimized page geometry.
"""

CLINICAL_BRIEF_CSS = """
:root{
  --ink:#1a1c1e; --muted:#5b6470; --faint:#8a8f98; --rule:#d9dde2;
  --accent:#15607a; --paper:#ffffff; --bg-soft:#f6f7f9; --warn:#9a5b00;
}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{
  font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  color:var(--ink); background:var(--paper); line-height:1.5; font-size:10.5pt;
  margin:0; padding:0;
}
.page{max-width:760px;margin:0 auto;padding:8mm 4mm}
h1,h2,h3,h4,.brand,.eyebrow,.stat-k,.meta-k,.tag,.grade{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
}
.masthead{border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:20px}
.brand{font-size:9pt;letter-spacing:.22em;font-weight:700;color:var(--accent)}
.eyebrow{font-size:8pt;letter-spacing:.18em;text-transform:uppercase;color:var(--faint);font-weight:700}
.masthead h1{font-size:20pt;line-height:1.2;margin:8px 0 10px;font-weight:600}
.meta{font-size:9pt;color:var(--muted)}
.meta-k{color:var(--faint);text-transform:uppercase;letter-spacing:.08em;font-size:7.5pt;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin-right:3px}

.bluf{border-left:4px solid var(--accent);background:var(--bg-soft);
  padding:12px 16px;margin:0 0 18px;border-radius:0 6px 6px 0;page-break-inside:avoid}
.bluf-head{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.bluf-body{font-size:11.5pt;line-height:1.45}

.summary{margin:0 0 18px}
.stats{display:flex;flex-wrap:wrap;gap:10px;border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule);padding:10px 0}
.stat{flex:1 1 auto;min-width:120px}
.stat-v{font-size:14pt;font-weight:700;font-family:-apple-system,sans-serif}
.stat-k{font-size:7.5pt;text-transform:uppercase;letter-spacing:.08em;color:var(--faint)}
.summary-notes{font-size:9pt;color:var(--muted);margin:8px 0 0;padding-left:18px}

h2{font-size:11pt;text-transform:uppercase;letter-spacing:.1em;color:var(--accent);
  border-bottom:1px solid var(--rule);padding-bottom:4px;margin:22px 0 12px;break-after:avoid}
h3{font-size:12pt;margin:16px 0 6px;font-weight:600;break-after:avoid}
h4{font-size:10pt;margin:12px 0 4px;color:var(--muted);
  text-transform:none;letter-spacing:0;font-weight:700;break-after:avoid}

.claim{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--rule);
  page-break-inside:avoid;break-inside:avoid}
.claim:last-child{border-bottom:none}
.claim-grade{flex:0 0 auto;padding-top:2px}
.claim-body{flex:1 1 auto}
.cite-row{margin:7px 0 0;display:flex;flex-wrap:wrap;gap:5px}
.cite{display:inline-block;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:8pt;font-variant-numeric:tabular-nums;color:var(--accent);background:#eef3f5;
  border:1px solid #cfe0e6;padding:1px 7px;border-radius:4px;line-height:1.7;
  max-width:100%;overflow-wrap:anywhere}
.cite-row .cite{max-width:100%}
.bluf-body .cite{margin:0 1px;vertical-align:baseline}
.effect{margin:8px 0 0;padding:8px 12px;background:var(--bg-soft);border-radius:5px;
  font-size:9pt;break-inside:avoid;page-break-inside:avoid}
.effect dt{font-weight:700;font-family:-apple-system,sans-serif;font-size:8.5pt;
  text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:3px}
.effect dd{margin:0 0 2px}
.effect dd.caveat{color:var(--warn)}
.ek{color:var(--faint);font-weight:600}

.grade{display:inline-block;color:#fff;font-size:8pt;font-weight:700;
  padding:2px 8px;border-radius:10px;letter-spacing:.04em;white-space:nowrap;vertical-align:baseline}
.grade.ga{background:#0b6b3a}.grade.gb{background:#15607a}.grade.gc{background:#9a5b00}
.grade.gd{background:#5b6470}.grade.ge{background:#717784}.grade.gu{background:#8a8f98}

.references ol{padding-left:20px;margin:0}
.references li{margin:0 0 8px;font-size:9.5pt;line-height:1.4}
.ref-label{font-style:italic}
.references a{color:var(--accent);text-decoration:none;word-break:break-word}

.background{margin:22px 0;font-size:9pt;color:#33373b}
.bg-notice{background:#fbf3e3;border:1px solid #e8d6a8;border-radius:6px;
  padding:8px 12px;margin-bottom:12px;font-size:8.5pt;color:#5a4a1f}
.background ul{padding-left:18px}.background .sub{display:inline}
.background ul ul,.background li{margin:2px 0}
blockquote{border-left:3px solid var(--rule);margin:6px 0;padding:2px 12px;
  color:var(--muted);font-style:italic}

.verified,.live{font-size:9.5pt}
.note{font-size:8.5pt;color:var(--muted);margin:0 0 8px}
.tag{display:inline-block;background:#eef1f4;color:var(--muted);font-size:7.5pt;
  font-weight:700;padding:1px 7px;border-radius:8px;letter-spacing:.04em}
.verified ul,.live ul{padding-left:18px}
code{font-family:"SF Mono",Menlo,Consolas,monospace;font-size:8.5pt;background:#eef1f4;
  padding:1px 4px;border-radius:3px}

.cautions li,.notes li,.rigor li{margin:0 0 5px;font-size:9.5pt}
.rigor{color:var(--warn)}

.refusal{border-left:4px solid var(--warn);background:#fbf3e3;padding:14px 18px;
  border-radius:0 6px 6px 0}
.refusal-body{font-size:11pt;margin:6px 0}

.docfoot{margin-top:26px;border-top:1px solid var(--rule);padding-top:10px;
  font-size:8pt;color:var(--faint);line-height:1.45}

@page{size:Letter;margin:16mm 15mm 18mm}
@media print{.page{max-width:none;padding:0}body{font-size:10pt}}
"""
