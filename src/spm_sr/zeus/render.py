"""Plantillas de correo (HTML + texto) y Telegram. Color siempre acompañado de texto."""
from __future__ import annotations

import datetime as dt
from html import escape
from typing import Any

ICON = {"Verde": "🟢", "Amarillo": "🟡", "Rojo": "🔴", "DATO_FALTANTE": "⚪"}
CSS_COLOR = {"Verde": "#1e7d32", "Amarillo": "#b26a00", "Rojo": "#c62828", "DATO_FALTANTE": "#616161"}
HEALTH_LABELS = (("overall", "Overall"), ("schedule", "Cronograma"), ("cost", "Costo"),
                 ("resources", "Recursos"), ("scope", "Alcance"))


def _c(v: str | None) -> str:
    v = v or "DATO_FALTANTE"
    return f"{ICON.get(v, '')} {v}"


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}" if abs(v) >= 1000 else f"{v:g}"
    return str(v)


def _worst(items: list[str]) -> str:
    order = {"Rojo": 3, "Amarillo": 2, "Verde": 1, "DATO_FALTANTE": 0}
    return max(items, key=lambda x: order.get(x, 0)) if items else "DATO_FALTANTE"


def subject(recipient: dict, run_date: dt.date, worst: str) -> str:
    roles = "/".join(recipient["roles"]) or "Escalamiento"
    return f"SR diario · {roles} · {run_date.isoformat()} · Overall {worst}"


def _project_html(r: dict) -> str:
    h, perf, ctl = r["health"], r["performance"], r["control"]
    rows = "".join(
        f"<tr><td>{lbl}</td><td style='color:{CSS_COLOR.get(h[k]['calculated'], '#000')};font-weight:600'>"
        f"{escape(_c(h[k]['calculated']))}</td><td>{escape(_c(h[k]['declared']))}</td>"
        f"<td>{escape(h[k]['comparison'])}</td></tr>" for k, lbl in HEALTH_LABELS)
    s, c, rs = perf["schedule"], perf["cost"], perf["resources"]
    d = perf["dates"]
    perf_rows = [
        ("% Avance (KPI 6)", _fmt(s.get("percent_complete")), "pm_project.percent_complete"),
        ("% Esperado / brecha", f"{_fmt(s.get('expected_pct'))} / {_fmt(s.get('gap_pp'))} pp", "calculado"),
        ("Inicio plan / real (7, 9)", f"{_fmt(d['planned_start'])} / {_fmt(d['actual_start'])}", "pm_project.start_date/work_start"),
        ("Fin plan / real (8, 10)", f"{_fmt(d['planned_end'])} / {_fmt(d['actual_end'])}", "pm_project.end_date/work_end"),
        ("Variación de fin (días)", _fmt(s.get("end_variance_days")), "calculado"),
        ("Costo plan / real (11, 12)", f"{_fmt(c.get('planned_cost'))} / {_fmt(c.get('actual_cost'))}", "pm_project.cost/work_cost"),
        ("CPI / consumo", f"{_fmt(c.get('cpi'))} / {_fmt(c.get('consumption_pct'))}%", "calculado"),
        ("Esfuerzo plan / real (13)", f"{_fmt(rs.get('planned_effort'))} / {_fmt(rs.get('actual_effort'))} h", "pm_project.effort/work_effort"),
        ("Índice de esfuerzo", _fmt(rs.get("effort_index")), "calculado"),
    ]
    alloc = rs.get("allocation")
    if alloc:
        perf_rows.append(("Asignado vs real (13)", f"{_fmt(alloc['allocated_hours'])} / {_fmt(alloc['actual_hours'])} h",
                          alloc["source_field"]))
    prow = "".join(f"<tr><td>{a}</td><td>{escape(b)}</td><td style='color:#777'>{escape(src)}</td></tr>"
                   for a, b, src in perf_rows)

    def ctl_txt(key, fmt):
        v = ctl.get(key)
        return "DATO_FALTANTE" if not isinstance(v, dict) else fmt(v)

    crow = "".join(f"<tr><td>{a}</td><td>{escape(b)}</td></tr>" for a, b in [
        ("Hitos (14)", ctl_txt("milestones", lambda v: f"{v['completed']}/{v['total']} completados; {v['overdue']} vencidos")),
        ("Riesgos (15)", ctl_txt("risks", lambda v: f"{v['open']} abiertos; {v['open_high']} altos; {v['overdue']} vencidos")),
        ("Issues (16)", ctl_txt("issues", lambda v: f"{v['open']} abiertos; {v['no_owner']} sin responsable")),
        ("Decisiones (17)", ctl_txt("decisions", lambda v: f"{v['pending']} pendientes")),
        ("Acciones (18)", ctl_txt("actions", lambda v: f"{v['pending']} pendientes; {v['overdue']} vencidas")),
        ("Cambios (19)", ctl_txt("change_requests", lambda v: f"{v['pending']} pendientes; {v['pending_over_days']} > {v['threshold_days']} días")),
    ])
    warn = ""
    if r.get("sr_missing"):
        warn = "<p style='color:#c62828'>Sin Status Report: semáforos declarados no disponibles.</p>"
    elif r.get("sr_stale"):
        warn = f"<p style='color:#b26a00'>Status Report desactualizado (as_on {escape(_fmt(r.get('sr_as_on')))}).</p>"
    if h["overall"].get("incomplete_evidence"):
        warn += "<p style='color:#616161'>Overall con evidencia incompleta (algún componente sin dato).</p>"
    return (f"<h3>{escape(r['number'])} · {escape(r.get('name') or '')}</h3>{warn}"
            f"<p>{escape(r['narrative']['text'])}</p>"
            "<table border='1' cellpadding='4' cellspacing='0'><tr><th>Salud</th><th>Calculado</th><th>Declarado PM</th><th>Comparación</th></tr>"
            f"{rows}</table><br><table border='1' cellpadding='4' cellspacing='0'><tr><th>Desempeño</th><th>Valor</th><th>Origen</th></tr>{prow}</table>"
            f"<br><table border='1' cellpadding='4' cellspacing='0'><tr><th>Control</th><th>Estado</th></tr>{crow}</table>")


def _rollup_html(ru: dict) -> str:
    if not ru.get("distribution"):
        return f"<h3>{escape(ru['level'])} {escape(str(ru.get('number')))}</h3><p>Sin proyectos válidos.</p>"
    d = ru["distribution"]["overall"]
    reds = ", ".join(f"{x['number']}" for x in ru.get("red_projects", [])) or "ninguno"
    cpi = ru.get("cpi", {})
    return (f"<h3>{escape(ru['level'])} {escape(str(ru.get('number')))} · {escape(ru.get('name') or '')}</h3>"
            f"<p>{escape(ru['narrative']['text'])}</p><table border='1' cellpadding='4' cellspacing='0'>"
            f"<tr><td>Proyectos</td><td>{ru['n_projects']}</td></tr>"
            f"<tr><td>Overall V/A/R/sin dato</td><td>{d['Verde']['n']} / {d['Amarillo']['n']} / {d['Rojo']['n']} / {d['DATO_FALTANTE']['n']}</td></tr>"
            f"<tr><td>Peor caso</td><td>{escape(_c(ru['worst_overall']))}</td></tr>"
            f"<tr><td>Proyectos en Rojo</td><td>{escape(reds)}</td></tr>"
            f"<tr><td>% presupuesto en Rojo</td><td>{_fmt(ru.get('budget_in_red_pct'))}</td></tr>"
            f"<tr><td>CPI agregado (mediana; mín–máx; n)</td><td>{_fmt(cpi.get('aggregate'))} ({_fmt(cpi.get('median'))}; "
            f"{_fmt(cpi.get('min'))}–{_fmt(cpi.get('max'))}; {cpi.get('n')})</td></tr>"
            f"<tr><td>Discrepancias de optimismo</td><td>{ru.get('optimism_discrepancies')}</td></tr></table>")


def email(recipient: dict, reports: list[dict], rollups: list[dict], escalated: list[dict], run_date: dt.date,
          partial_note: str | None) -> tuple[str, str, str]:
    worst = _worst([r["health"]["overall"]["calculated"] for r in reports + escalated] +
                   [ru["worst_overall"] for ru in rollups])
    parts = [f"<p>Hola {escape(recipient.get('name') or '')}, este es el Status Report del {run_date.isoformat()}.</p>"]
    if partial_note:
        parts.append(f"<p style='background:#fff3e0;padding:6px'><b>Reporte con evidencia incompleta:</b> {escape(partial_note)}</p>")
    for ru in rollups:
        parts.append(_rollup_html(ru))
    if reports:
        parts.append("<h2>Mis proyectos</h2>" + "".join(_project_html(r) for r in reports))
    if escalated:
        parts.append("<h2>Escalados (proyectos sin PM válido)</h2>" + "".join(_project_html(r) for r in escalated))
    parts.append("<hr><p style='color:#777;font-size:12px'>Semáforos calculados con umbrales configurables "
                 "(config/thresholds.yaml, SUPUESTO pendiente de validar con la PMO). Avance esperado lineal. "
                 "Generado por Cronos → Thanatos → Zeus.</p>")
    html_body = "<html><body style='font-family:Arial,sans-serif'>" + "".join(parts) + "</body></html>"
    text_lines = [f"SR {run_date.isoformat()} · Overall {worst}"]
    if partial_note:
        text_lines.append(f"Evidencia incompleta: {partial_note}")
    text_lines += [ru["narrative"]["text"] for ru in rollups]
    text_lines += [r["narrative"]["text"] for r in reports + escalated]
    return subject(recipient, run_date, worst), html_body, "\n\n".join(text_lines)


def telegram(recipient: dict, reports: list[dict], rollups: list[dict], escalated: list[dict], run_date: dt.date,
             include_costs: bool, partial_note: str | None) -> str:
    lines = [f"<b>SR diario {run_date.isoformat()}</b> · {escape('/'.join(recipient['roles']) or 'Escalamiento')}"]
    if partial_note:
        lines.append(f"⚠️ Evidencia incompleta: {escape(partial_note)}")
    for ru in rollups:
        if ru.get("distribution"):
            d = ru["distribution"]["overall"]
            lines.append(f"\n<b>{escape(ru['level'])} {escape(str(ru.get('number')))}</b>: {d['Verde']['n']}🟢 "
                         f"{d['Amarillo']['n']}🟡 {d['Rojo']['n']}🔴 {d['DATO_FALTANTE']['n']}⚪ · peor {_c(ru['worst_overall'])}")
    for r in reports + escalated:
        h = r["health"]
        short = {"schedule": "Crono", "cost": "Costo", "resources": "Recursos", "scope": "Alcance"}
        sem = " · ".join(f"{short[k]} {ICON.get(h[k]['calculated'], '⚪')}" for k, _ in HEALTH_LABELS[1:])
        lines.append(f"\n<b>{escape(r['number'])}</b> Overall {_c(h['overall']['calculated'])}\n{sem}")
        if include_costs and r["performance"]["cost"].get("cpi") is not None:
            lines.append(f"CPI {r['performance']['cost']['cpi']}")
        for a in r["alerts"][:3]:
            lines.append(f"• {escape(a)}")
    lines.append("\nDetalle completo en su correo.")
    msg = "\n".join(lines)
    return msg if len(msg) <= 4000 else msg[:3950] + "\n… (ver correo)"


def failure_text(report_md: str) -> tuple[str, str]:
    return "SR diario · FALLA en la corrida", report_md
