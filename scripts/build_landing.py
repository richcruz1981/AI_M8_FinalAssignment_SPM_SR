"""Portada del sitio: la página original de hatchvps con paleta PepsiCo y la sección "Proyecto Final Edgar Cruz".

Entrada: site/original_index.html (copia de la portada original). Salida: HTML listo para /www/index.html.
Uso: python scripts/build_landing.py --out build/index.html
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://hatchvps.com/iaang01/edgarcruz"

# Paleta PepsiCo (Coloropedia, fuente secundaria): navy #28458E, electric blue #0096D6, tangelo #EB7B30.
# Tema oscuro navy: fondo profundo, acento electric blue, tangelo solo para avisos.
PALETTE = """  :root{
    --verde:#0096D6; --verde-claro:#5CC6F2; --verde-osc:#28458E;
    --negro:#0B1630; --negro-2:#0F1E40; --panel:#15284F; --panel-2:#1B325F;
    --texto:#EEF3FA; --muted:#A3B1C9; --linea:#26406F;
    --navy:#28458E; --tangelo:#EB7B30;
    --font:"Montserrat",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
    --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  }"""

COLOR_SWAPS = [
    ("rgba(118,188,33,", "rgba(0,150,214,"),     # verde hatch translúcido -> electric blue
    ("#b9ef86", "#9FDCF7"),                       # texto de <code>
    ("#cfe0bd", "#CFE4F5"),                       # texto de .nota
    ("background:#000;", "background:#081126;"),  # bloques negros -> navy profundo
    ("rgba(231,180,87,.10)", "rgba(235,123,48,.12)"),  # aviso -> tangelo
    ("border:1px solid #b8862f", "border:1px solid #EB7B30"),
    ("color:#f0d9a8", "color:#F8D9C2"),
    (".aviso b{color:#ffd98a}", ".aviso b{color:#FFB98A}"),
]

SECTION_CSS = """
  .pf{background:linear-gradient(115deg,#28458E 0%,#1F3A7D 55%,#0B6FAE 100%);border-bottom:4px solid var(--tangelo)}
  .pf .in{max-width:760px;margin:0 auto;padding:clamp(1.6rem,5vw,2.6rem) clamp(1rem,4vw,1.75rem)}
  .pf .eyebrow{color:#BFE6FA}
  .pf h2{margin:0 0 .4rem;font-size:clamp(1.5rem,5vw,2.1rem);font-weight:800;color:#fff}
  .pf h2::before{background:var(--tangelo)}
  .pf .lead{color:#DCE6F5;max-width:58ch;margin-bottom:1.3rem}
  .pf .links{display:grid;gap:.9rem;grid-template-columns:1fr}
  @media(min-width:600px){.pf .links{grid-template-columns:1fr 1fr}}
  .pf a.lk{display:flex;flex-direction:column;gap:.35rem;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.22);
    border-radius:.9rem;padding:1.1rem 1.2rem;text-decoration:none;color:#fff;transition:background .15s,transform .15s,border-color .15s}
  .pf a.lk:hover,.pf a.lk:focus-visible{background:rgba(255,255,255,.15);border-color:#5CC6F2;transform:translateY(-2px);outline:none}
  .pf .lk .k{font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:#BFE6FA;font-weight:700}
  .pf .lk .t{font-size:1.12rem;font-weight:700}
  .pf .lk .d{font-size:.9rem;color:#DCE6F5}
  .pf .lk .go{margin-top:.3rem;font-size:.85rem;font-weight:700;color:#FFB98A}
"""

SECTION_HTML = f"""  <section class="pf" id="proyecto-final" aria-labelledby="pf-title">
    <div class="in">
      <p class="eyebrow">ServiceNow SPM · Status Reports con agentes de IA</p>
      <h2 id="pf-title">Proyecto Final Edgar Cruz</h2>
      <p class="lead">Cronos lee la base, Thanatos calcula los 19 KPIs del Status Report y Zeus comunica por Telegram;
        Radamantis atiende las consultas del bot en tiempo real y Cerbero, el agente de seguridad, revisa cada acción
        (bloquea inyecciones, neutraliza datos maliciosos y detiene a cualquier agente comprometido) y deja un log
        de auditoría.</p>
      <div class="links">
        <a class="lk" href="{SITE}/app/">
          <span class="k">Bot de Telegram</span>
          <span class="t">Dashboard de uso del bot</span>
          <span class="d">Estado de Radamantis, peticiones atendidas, resumen de las consultas y log de auditoría de Cerbero.</span>
          <span class="go">Abrir →</span>
        </a>
        <a class="lk" href="{SITE}/dashboard/">
          <span class="k">KPIs del portafolio</span>
          <span class="t">Portfolio Health Dashboard</span>
          <span class="d">Los 19 KPIs en gráficas, con filtros, cambio de tipo de gráfica y descarga en PDF.</span>
          <span class="go">Abrir →</span>
        </a>
      </div>
    </div>
  </section>
"""


def build(src: str) -> str:
    html = re.sub(r"  :root\{.*?\n  \}", PALETTE, src, count=1, flags=re.S)
    for a, b in COLOR_SWAPS:
        html = html.replace(a, b)
    html = html.replace("</style>", SECTION_CSS + "</style>", 1)
    html = html.replace("<title>Edgar · hatch co.</title>", "<title>Proyecto Final Edgar Cruz · hatch co.</title>", 1)
    html = re.sub(r"<body>\s*", "<body>\n" + SECTION_HTML + "\n  ", html, count=1)
    assert "Proyecto Final Edgar Cruz" in html and "#0096D6" in html, "no se aplicaron los cambios"
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "site" / "original_index.html"))
    ap.add_argument("--out", default=str(ROOT / "build" / "index.html"))
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(Path(a.src).read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Portada -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
