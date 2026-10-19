"""PDF "Ecosystem description" built from docs/architecture/ARCHITECTURE_FOR_LLMS.md + the infographic.

Uso: python scripts/build_architecture_pdf.py
     -> docs/architecture/SPM_SR_Ecosystem_Description.html (fuente) y .pdf (Chromium/Playwright, A4).
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "architecture"

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
@page :first { margin: 0; }
* { box-sizing: border-box; }
body { font-family: Inter, system-ui, sans-serif; color: #14213D; font-size: 10.2pt; line-height: 1.5; margin: 0; }
.cover { width: 210mm; height: 297mm; background: linear-gradient(150deg, #28458E 0%, #1F3A7D 55%, #0B6FAE 100%);
  color: #fff; padding: 26mm 20mm 18mm; position: relative; page-break-after: always; display: flex; flex-direction: column; }
.cover .eyebrow { font-size: 10pt; letter-spacing: .2em; text-transform: uppercase; color: #BFE6FA; font-weight: 700; }
.cover h1 { font-size: 34pt; line-height: 1.05; margin: 8mm 0 4mm; font-weight: 800; letter-spacing: -.02em; }
.cover .lead { font-size: 13pt; color: #DCE6F5; max-width: 150mm; }
.cover .bar { width: 28mm; height: 3mm; background: #EB7B30; border-radius: 2mm; margin: 8mm 0; }
.cover img { width: 100%; border-radius: 3mm; margin-top: auto; box-shadow: 0 3mm 8mm rgba(0,0,0,.25); }
.cover .meta { display: grid; grid-template-columns: auto 1fr; gap: 1mm 5mm; font-size: 9.5pt; color: #DCE6F5; margin-top: 6mm; }
.cover .meta b { color: #fff; }
h2 { font-size: 15pt; color: #28458E; margin: 7mm 0 3mm; padding-bottom: 1.5mm; border-bottom: 2px solid #E1E6EE;
  page-break-after: avoid; display: flex; align-items: center; gap: 3mm; }
h2::before { content: ""; width: 2.2mm; height: 6mm; background: #EB7B30; border-radius: 1mm; flex: none; }
h1.doc { display: none; }
p { margin: 0 0 3mm; }
ul { margin: 0 0 3mm; padding-left: 5mm; } li { margin: .6mm 0; }
table { width: 100%; border-collapse: collapse; margin: 1mm 0 4mm; font-size: 8.8pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #28458E; color: #fff; text-align: left; padding: 1.8mm 2.2mm; font-weight: 700; }
td { padding: 1.6mm 2.2mm; border-bottom: 1px solid #E1E6EE; vertical-align: top; }
tr:nth-child(even) td { background: #F6F8FC; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 8.4pt; background: #EEF2F9; color: #1F3A7D; padding: .2mm 1mm; border-radius: 1mm; }
blockquote { margin: 0 0 4mm; padding: 3mm 4mm; background: #FFF6EF; border-left: 3px solid #EB7B30; border-radius: 1.5mm; color: #3A2A1E; }
.fig { break-before: page; break-after: page; height: 258mm; position: relative; margin: 0; }
.fig .rot { position: absolute; left: 0; top: 0; width: 255mm; height: 178mm; transform-origin: top left; transform: translate(179mm, 0) rotate(90deg); }
.fig .figtitle { font-size: 15pt; font-weight: 700; color: #28458E; margin: 0 0 3mm; border-left: 2.2mm solid #EB7B30; padding-left: 3mm; }
.fig img { display: block; width: 240mm; height: 160mm; margin: 0 auto; border: 1px solid #E1E6EE; border-radius: 2mm; }
.fig h3 { font-size: 13pt; color: #28458E; margin: 0 0 3mm; }
.fig .cap { font-size: 8.5pt; color: #5B6475; margin-top: 1.5mm; }
.kv { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; margin: 2mm 0 5mm; }
.kv div { border: 1px solid #E1E6EE; border-top: 1.2mm solid #28458E; border-radius: 2mm; padding: 2.5mm 3mm; }
.kv b { display: block; font-size: 18pt; line-height: 1.1; }
.kv span { font-size: 8.3pt; color: #5B6475; }
"""


def build_html() -> str:
    md = (ARCH / "ARCHITECTURE_FOR_LLMS.md").read_text(encoding="utf-8")
    md = re.sub(r"^---.*?---\n", "", md, count=1, flags=re.S)                    # front matter
    md = re.sub(r"^# .*\n", "", md, count=1, flags=re.M)                          # título (va en portada)
    md = md.replace("> Purpose of this file: a complete, self-contained description of the system that another LLM can read to answer\n"
                    "> questions, propose changes, or generate code without access to the repository. Facts are stated as implemented;\n"
                    "> anything not implemented is marked **Not implemented**.\n",
                    "> This document describes the system as implemented on 2026-10-18. Anything not implemented is listed in "
                    "section 13. Data shown in the system is synthetic demo data.\n")
    img_b64 = base64.b64encode((ARCH / "ecosystem_architecture.png").read_bytes()).decode()
    img = f"data:image/png;base64,{img_b64}"
    fig = (f'<div class="fig"><div class="rot"><div class="figtitle">3. Diagram · Figure 1 · Ecosystem architecture</div><img src="{img}" alt="Ecosystem architecture infographic">'
           '<div class="cap">Figure 1 · Ecosystem architecture: data &amp; orchestration, agent layer guarded by Cerbero, '
           'channels &amp; experience.</div></div></div>')
    md = re.sub(r"```mermaid.*?```", "FIGURE_PLACEHOLDER", md, flags=re.S)
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    body = body.replace("<h2>3. Diagram</h2>", "").replace("<p>FIGURE_PLACEHOLDER</p>", fig)
    stats = """<div class="kv"><div><b>5</b><span>AI agents</span></div><div><b>19</b><span>status-report KPIs</span></div>
      <div><b>7</b><span>chatbot options</span></div><div><b>5</b><span>security gates</span></div></div>"""
    body = body.replace("<h2>2. Components</h2>", stats + "<h2>2. Components</h2>", 1)
    cover = f"""<section class="cover">
      <div class="eyebrow">Proyecto Final Edgar Cruz · System description</div>
      <h1>SPM Status Report<br>AI Ecosystem</h1>
      <div class="lead">ServiceNow SPM replica → five cooperating AI agents → Telegram chatbot and web dashboards,
        delivering the 19 standard status-report KPIs with a security guardian on every action.</div>
      <div class="bar"></div>
      <img src="{img}" alt="Architecture">
      <div class="meta"><b>Site</b><span>hatchvps.com/iaang01/edgarcruz</span>
        <b>Repository</b><span>github.com/richcruz1981/AI_M8_FinalAssignment_SPM_SR</span><b>Date</b><span>2026-10-18</span></div>
    </section>"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
      <title>SPM Status Report AI Ecosystem — System description</title><style>{CSS}</style></head>
      <body>{cover}<main>{body}</main></body></html>"""




def rotate_figure_page(pdf_path: Path) -> int:
    """La figura se imprime girada 90° en una página vertical; se marca la página con /Rotate para verla horizontal."""
    from pypdf import PdfReader, PdfWriter

    r = PdfReader(str(pdf_path))
    w = PdfWriter()
    hit = -1
    for i, page in enumerate(r.pages):
        if hit < 0 and "Figure 1" in (page.extract_text() or "") and "Ecosystem architecture" in (page.extract_text() or ""):
            page.rotate(270)
            hit = i
        w.add_page(page)
    w.add_metadata(r.metadata or {})
    with open(pdf_path, "wb") as fh:
        w.write(fh)
    return hit


FOOTER = ('<div style="width:100%;font-family:Inter,sans-serif;font-size:7.5pt;color:#5B6475;padding:0 15mm;'
          'display:flex;justify-content:space-between"><span>SPM Status Report AI Ecosystem · System description</span>'
          '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.goto(html_path.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.pdf(path=str(pdf_path), format="A4", print_background=True, display_header_footer=True,
               header_template="<div></div>", footer_template=FOOTER, prefer_css_page_size=True,
               margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"})
        b.close()


if __name__ == "__main__":
    html = ARCH / "SPM_SR_Ecosystem_Description.html"
    pdf = ARCH / "SPM_SR_Ecosystem_Description.pdf"
    html.write_text(build_html(), encoding="utf-8")
    print_pdf(html, pdf)
    print(pdf, "· figure page:", rotate_figure_page(pdf) + 1)
