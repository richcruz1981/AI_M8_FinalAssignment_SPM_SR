"""Gráficas PNG para las respuestas del bot (Zeus). Una por opción, elegida según el trabajo del dato.

| Opción | Pregunta que responde | Forma |
|---|---|---|
| 1 Total | ¿Cómo está la salud del portafolio activo? | Barras horizontales por estado de salud |
| 2 Categoría | ¿Cuántos proyectos hay en cada estado? | Barras horizontales ordenadas (magnitud, 1 tono) |
| 3 Región | ¿Dónde están y cuántos siguen activos? | Barras apiladas activos / cerrados (1 tono, 2 pasos) |
| 4-5 Programa / Portafolio | ¿Quién concentra proyectos y riesgo? | Barras apiladas por salud (top N) |
| 6 Calidad | ¿Qué falta en la base y qué tan grave es? | Barras por regla, color = severidad |
| 7 Proyecto | ¿Cómo va contra lo esperado? | Matriz de salud calculado vs declarado + barras de % |
| 7 Programa / Portafolio | ¿Cómo se distribuye cada KPI de salud? | Barras 100 % apiladas por KPI |

Colores: paleta de estado fija (bueno/advertencia/crítico) + gris neutro para "sin dato"; la identidad
nunca depende solo del color: cada gráfica lleva leyenda y el valor escrito en cada barra.
Si matplotlib no está disponible, devuelve None y el bot responde solo con texto.
"""
from __future__ import annotations

import io
from typing import Any

from . import i18n

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
STATUS = {"Verde": "#0ca30c", "Amarillo": "#fab219", "Rojo": "#d03b3b", "DATO_FALTANTE": "#b7b6b0"}
STATUS_LBL = {"Verde": "Green", "Amarillo": "Amber", "Rojo": "Red", "DATO_FALTANTE": "No data"}
SEVERITY = {"Alta": "#d03b3b", "Media": "#ec835a", "Baja": "#fab219"}
SEV_LBL = {"Alta": "High", "Media": "Medium", "Baja": "Low"}
BLUE, BLUE_LIGHT = "#2a78d6", "#86b6ef"
HEALTH_KEYS = (("overall", "Overall"), ("schedule", "Schedule"), ("cost", "Cost"),
               ("resources", "Resources"), ("scope", "Scope"))


def _plt():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except Exception:  # noqa: BLE001
        return None


def _fig(plt, h: float, w: float = 7.2):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def _title(fig, title: str, subtitle: str | None = None):
    h = fig.get_figheight()
    fig.text(0.02, 1 - 0.12 / h, title, fontsize=12, fontweight="bold", color=INK, va="top")
    if subtitle:
        fig.text(0.02, 1 - 0.42 / h, subtitle, fontsize=8.5, color=INK2, va="top")


def _png(fig, plt, header_in: float = 0.75) -> bytes:
    """header_in: pulgadas reservadas arriba para título/subtítulo (+ leyenda)."""
    fig.tight_layout(rect=(0, 0, 1, 1 - header_in / fig.get_figheight()))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=SURFACE)
    plt.close(fig)
    return buf.getvalue()


def _hbars(plt, labels, values, colors, title, subtitle, total=None, xlabel="Projects", legend=None):
    h = max(2.4, 0.42 * len(labels) + 1.4)
    fig, ax = _fig(plt, h)
    y = list(range(len(labels)))[::-1]
    ax.barh(y, values, color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    ax.set_yticks(y, labels, color=INK, fontsize=9.5)
    top = max(values) if values else 1
    for yi, v in zip(y, values):
        txt = f"{v}" + (f"  ({100 * v / total:.0f}%)" if total else "")
        ax.text(v + top * 0.015, yi, txt, va="center", fontsize=9, color=INK)
    ax.set_xlim(0, top * 1.22 + 0.5)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    if legend:
        from matplotlib.patches import Patch

        ax.legend(handles=[Patch(color=c, label=n) for n, c in legend], loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  ncol=len(legend), frameon=False, fontsize=8.5, labelcolor=INK2, handlelength=1.2)
    _title(fig, title, subtitle)
    return _png(fig, plt, 0.62 if legend else 0.75)


def _stacked(plt, labels, series: list[tuple[str, str, list[int]]], title, subtitle, pct=False, xlabel="Projects"):
    h = max(2.6, 0.42 * len(labels) + 1.8)
    fig, ax = _fig(plt, h)
    y = list(range(len(labels)))[::-1]
    left = [0.0] * len(labels)
    totals = [sum(s[2][i] for s in series) for i in range(len(labels))]
    for name, color, vals in series:
        widths = [(100 * v / t if t else 0) if pct else v for v, t in zip(vals, totals)]
        ax.barh(y, widths, left=left, color=color, height=0.62, edgecolor=SURFACE, linewidth=2, label=name)
        for yi, l0, wv, v in zip(y, left, widths, vals):
            span = 100 if pct else max(totals or [1])
            if v and wv >= span * 0.06:
                ax.text(l0 + wv / 2, yi, str(v), ha="center", va="center", fontsize=8.5,
                        color=INK if color in (STATUS["Amarillo"], STATUS["DATO_FALTANTE"], BLUE_LIGHT) else "white")
        left = [a + b for a, b in zip(left, widths)]
    if not pct:
        top = max(totals) if totals else 1
        for yi, t in zip(y, totals):
            ax.text(t + top * 0.015, yi, str(t), va="center", fontsize=9, color=INK, fontweight="bold")
        ax.set_xlim(0, top * 1.15 + 0.5)
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    else:
        ax.set_xlim(0, 100)
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_yticks(y, labels, color=INK, fontsize=9.5)
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(series), frameon=False, fontsize=8.5,
              labelcolor=INK2, handlelength=1.2)
    _title(fig, title, subtitle)
    return _png(fig, plt, 0.62)


# ------------------------------------------------------------------ por opción
def _total(plt, r):
    ov = r["overall"]
    keys = ["Verde", "Amarillo", "Rojo", "DATO_FALTANTE"]
    return _hbars(plt, [STATUS_LBL[k] for k in keys], [ov.get(k, 0) for k in keys], [STATUS[k] for k in keys],
                  f"Calculated health · {r['analizados']} active analyzed projects",
                  f"Total in database: {r['total']} · active {r['activos']} · closed/cancelled "
                  f"{r['cerrados_cancelados']} · excluded by data quality {r['excluidos_dq']}", total=r["analizados"])


def _categorias(plt, r):
    rows = sorted(r["rows"], key=lambda x: -x["n"])
    return _hbars(plt, [i18n.cat(x["categoria"]) for x in rows], [x["n"] for x in rows], [BLUE] * len(rows),
                  "Projects by state category", f"Total: {r['total']} projects", total=r["total"])


def _regiones(plt, r):
    if not r.get("available") or not r["rows"]:
        return None
    rows = r["rows"]
    return _stacked(plt, [i18n.ph(x["region"]) for x in rows],
                    [("Active", BLUE, [x["activos"] for x in rows]),
                     ("Closed / cancelled", BLUE_LIGHT, [x["n"] - x["activos"] for x in rows])],
                    "Projects by region", f"Total: {r['total']} · region = custom field u_region")


def _padres(plt, r, top_n=15):
    rows = [x for x in r["rows"] if x["n"]][:top_n]
    if not rows:
        return None
    lbl = "program" if r["kind"] == "programas" else "portfolio"
    other = [x["n"] - x["verde"] - x["amarillo"] - x["rojo"] for x in rows]
    return _stacked(plt, [i18n.ph(x["number"]) for x in rows],
                    [("Green", STATUS["Verde"], [x["verde"] for x in rows]),
                     ("Amber", STATUS["Amarillo"], [x["amarillo"] for x in rows]),
                     ("Red", STATUS["Rojo"], [x["rojo"] for x in rows]),
                     ("Closed / not analyzed", STATUS["DATO_FALTANTE"], other)],
                    f"Projects by {lbl} and calculated health",
                    f"Top {len(rows)} of {r['con_proyectos']} with projects (sorted by number of projects)")


def _calidad(plt, r):
    rows = sorted(r["rows"], key=lambda x: -x["n"])
    if not rows:
        return None
    fig_bytes = _hbars(plt, [f"{x['rule']} {i18n.dq(x['rule'], x['label'])}" for x in rows], [x["n"] for x in rows],
                       [SEVERITY.get(x["severity"], STATUS["DATO_FALTANTE"]) for x in rows],
                       "Projects with data-quality issues",
                       f"{r['proyectos_afectados']} affected of {r['evaluados']} active projects evaluated · color = severity",
                       legend=[(f"{SEV_LBL[k]} severity", v) for k, v in SEVERITY.items()])
    return fig_bytes


def _estatus_proyecto(plt, r):
    if not r.get("analyzed"):
        return None
    rep = r["report"]
    h, perf = rep["health"], rep["performance"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 5.6), dpi=150, gridspec_kw={"height_ratios": [1, 1.25]})
    fig.patch.set_facecolor(SURFACE)
    # Panel 1: matriz de salud (calculado vs declarado)
    ax1.set_facecolor(SURFACE)
    ax1.set_xlim(0, 5)
    ax1.set_ylim(0, 2)
    ax1.axis("off")
    for i, (k, lbl) in enumerate(HEALTH_KEYS):
        for j, (src, name) in enumerate((("calculated", "Calculated"), ("declared", "PM declared"))):
            v = h[k][src] or "DATO_FALTANTE"
            ax1.add_patch(plt.Rectangle((i + 0.04, 1 - j + 0.06), 0.92, 0.84, color=STATUS.get(v, STATUS["DATO_FALTANTE"])))
            ax1.text(i + 0.5, 1 - j + 0.48, STATUS_LBL.get(v, "No data"), ha="center", va="center", fontsize=8.5,
                     color=INK if v in ("Amarillo", "DATO_FALTANTE") else "white", fontweight="bold")
        ax1.text(i + 0.5, 2.03, lbl, ha="center", va="bottom", fontsize=9, color=INK)
    ax1.text(-0.05, 1.48, "Calculated", ha="right", va="center", fontsize=8.5, color=INK2)
    ax1.text(-0.05, 0.48, "PM declared", ha="right", va="center", fontsize=8.5, color=INK2)
    # Panel 2: porcentajes comparables (misma unidad, un solo eje)
    s, c, rs = perf["schedule"], perf["cost"], perf["resources"]
    pe, ae = rs.get("planned_effort"), rs.get("actual_effort")
    items = [("Actual progress", s.get("percent_complete"), BLUE),
             ("Expected progress (linear)", s.get("expected_pct"), BLUE_LIGHT),
             ("Budget used", c.get("consumption_pct"), "#6250d6"),
             ("Effort used", round(100 * ae / pe, 1) if pe and ae is not None else None, "#1baf7a")]
    items = [x for x in items if x[1] is not None]
    for sp in ("top", "right", "left"):
        ax2.spines[sp].set_visible(False)
    ax2.set_facecolor(SURFACE)
    ax2.spines["bottom"].set_color(GRID)
    ax2.tick_params(colors=INK2, labelsize=9, length=0)
    ax2.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax2.set_axisbelow(True)
    y = list(range(len(items)))[::-1]
    ax2.barh(y, [x[1] for x in items], color=[x[2] for x in items], height=0.6, edgecolor=SURFACE, linewidth=2)
    for yi, (_, v, _) in zip(y, items):
        ax2.text(v + 1.5, yi, f"{v:g}%", va="center", fontsize=9, color=INK)
    ax2.set_yticks(y, [x[0] for x in items], color=INK, fontsize=9.5)
    ax2.set_xlim(0, max(110, max(x[1] for x in items) * 1.15))
    ax2.axvline(100, color=INK2, linewidth=0.8, linestyle=(0, (3, 3)))
    ax2.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    fig.text(0.02, 0.985, f"{r['code']} · health and progress", fontsize=12, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 0.945, f"CPI {c.get('cpi') if c.get('cpi') is not None else 'n/a'} · progress gap "
             f"{s.get('gap_pp')} pp · dashed line = 100%", fontsize=8.5, color=INK2, va="top")
    fig.tight_layout(rect=(0.06, 0, 1, 0.9))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=SURFACE)
    plt.close(fig)
    return buf.getvalue()


def _estatus_rollup(plt, r):
    ru = r["rollup"]
    if not ru.get("distribution"):
        return None
    d = ru["distribution"]
    labels = [lbl for _, lbl in HEALTH_KEYS]
    series = [(STATUS_LBL[s], STATUS[s], [d[k][s]["n"] for k, _ in HEALTH_KEYS])
              for s in ("Verde", "Amarillo", "Rojo", "DATO_FALTANTE")]
    return _stacked(plt, labels, series, f"{r['code']} · health by KPI ({r['analizados']} analyzed projects)",
                    f"Worst case: {STATUS_LBL.get(ru['worst_overall'], ru['worst_overall'])} · "
                    f"budget in Red: {ru.get('budget_in_red_pct')}%", pct=True, xlabel="% of projects")


def render_chart(res: dict[str, Any]) -> bytes | None:
    """PNG de la gráfica que acompaña la respuesta, o None si no aplica o no hay matplotlib."""
    plt = _plt()
    if plt is None:
        return None
    k = res.get("kind")
    try:
        if k == "total":
            return _total(plt, res)
        if k == "categorias":
            return _categorias(plt, res)
        if k == "regiones":
            return _regiones(plt, res)
        if k in ("programas", "portafolios"):
            return _padres(plt, res)
        if k == "calidad":
            return _calidad(plt, res)
        if k == "estatus" and res.get("found"):
            return _estatus_proyecto(plt, res) if res["level"] == "proyecto" else _estatus_rollup(plt, res)
    except Exception:  # noqa: BLE001 - una gráfica fallida no debe impedir la respuesta en texto
        import logging

        logging.getLogger("spm_sr.zeus.charts").exception("No se pudo generar la gráfica (%s)", k)
    return None
