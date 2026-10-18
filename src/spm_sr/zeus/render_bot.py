"""Respuestas del bot (Radamantis) en HTML de Telegram. Cada respuesta indica la fuente de los datos."""
from __future__ import annotations

from html import escape
from typing import Any

from .render import ICON, LIMIT

MENU_BUTTONS = [["1️⃣ Total de proyectos", "2️⃣ Por categoría"],
                ["3️⃣ Por región", "4️⃣ Por programa"],
                ["5️⃣ Por portafolio", "6️⃣ Calidad de datos"],
                ["7️⃣ Estatus por ID (proyecto / programa / portafolio)"]]
COMMANDS = [("total", "Total de proyectos"), ("categorias", "Proyectos por categoría (estado)"),
            ("regiones", "Proyectos por región"), ("programas", "Proyectos por programa"),
            ("portafolios", "Proyectos por portafolio"), ("calidad", "Proyectos con problemas de calidad de datos"),
            ("estatus", "KPIs de un proyecto, programa o portafolio (ej. /estatus PRG0002)"),
            ("menu", "Mostrar el menú")]


def keyboard() -> dict:
    return {"keyboard": [[{"text": b} for b in row] for row in MENU_BUTTONS], "resize_keyboard": True,
            "is_persistent": True}


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "—"


def _foot(res: dict, when: str) -> str:
    return f"\n<i>Fuente: {escape(res.get('source_field', ''))} · datos leídos {escape(when)}</i>"


def _split(lines: list[str]) -> list[str]:
    msgs, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > LIMIT:
            msgs.append(cur)
            cur = ln
        else:
            cur = f"{cur}\n{ln}" if cur else ln
    msgs.append(cur)
    return [f"{m}\n<i>({i}/{len(msgs)})</i>" for i, m in enumerate(msgs, 1)] if len(msgs) > 1 else msgs


def welcome(name: str | None) -> list[str]:
    return [f"Hola {escape(name or '')} 👋 Soy <b>Radamantis</b>, el ejecutor del SR de proyectos.\n\n"
            "Elige una opción del menú o escribe un comando:\n"
            + "\n".join(f"/{c} — {escape(d)}" for c, d in COMMANDS[:-1])
            + "\n\nO escribe directamente un ID: <code>PRJ1001002</code>, <code>PRG0002</code>, <code>PFL0001</code>."
            + "\n\nLos datos se leen en tiempo real de la base (son <b>datos sintéticos</b> de demostración)."]


def not_understood() -> list[str]:
    return ["No entendí la petición. Usa el menú o /menu para ver las opciones."]


def unauthorized(chat_id: Any) -> list[str]:
    return [f"⛔ Este chat no está autorizado.\nComparte este chat_id con el administrador: <code>{escape(str(chat_id))}</code>"]


def error(code: str, detail: str) -> list[str]:
    return [f"⚠️ No pude obtener los datos ({escape(code)}).\n{escape(detail[:300])}\nEl administrador recibió el detalle."]


def render(res: dict, when: str) -> list[str]:
    k = res["kind"]
    if k == "total":
        ov = res["overall"]
        lines = ["<b>1. Total de proyectos</b>",
                 f"Total en la base: <b>{res['total']}</b>",
                 f"Activos: {res['activos']} · Cerrados/cancelados: {res['cerrados_cancelados']}",
                 f"Analizados por Thanatos: {res['analizados']} (excluidos por calidad: {res['excluidos_dq']})",
                 "Salud calculada (activos analizados): "
                 + " ".join(f"{ov.get(c, 0)}{ICON[c]}" for c in ("Verde", "Amarillo", "Rojo", "DATO_FALTANTE"))]
    elif k == "categorias":
        lines = ["<b>2. Proyectos por categoría</b>", f"Total: {res['total']}"]
        for r in res["rows"]:
            det = ", ".join(f"{escape(s)} {n}" for s, n in sorted(r["estados"].items(), key=lambda x: -x[1]))
            lines.append(f"• <b>{escape(r['categoria'])}</b>: {r['n']} ({_pct(r['n'], res['total'])}) — {det}")
    elif k == "regiones":
        lines = ["<b>3. Proyectos por región</b>"]
        if not res["available"]:
            lines.append("El campo de región (u_region) no existe en la base.")
        else:
            lines.append(f"Total: {res['total']}")
            lines += [f"• <b>{escape(r['region'])}</b>: {r['n']} ({_pct(r['n'], res['total'])}) · activos {r['activos']}"
                      for r in res["rows"]]
    elif k in ("programas", "portafolios"):
        title = "4. Proyectos por programa" if k == "programas" else "5. Proyectos por portafolio"
        lines = [f"<b>{title}</b>",
                 f"{res['con_proyectos']} con proyectos · {res['sin_proyectos']} sin proyectos · total proyectos {res['total']}",
                 "<i>Formato: proyectos (activos) · salud de activos 🟢🟡🔴</i>"]
        for r in res["rows"]:
            name = f" {escape(r['name'])}" if r.get("name") else ""
            lines.append(f"• <b>{escape(str(r['number']))}</b>{name}: {r['n']} ({r['activos']}) · "
                         f"{r['verde']}🟢 {r['amarillo']}🟡 {r['rojo']}🔴")
    elif k == "calidad":
        lines = ["<b>6. Proyectos con problemas de calidad de datos</b>",
                 f"Afectados: <b>{res['proyectos_afectados']}</b> de {res['evaluados']} evaluados",
                 f"<i>{escape(res['nota'])}</i>"]
        for r in res["rows"]:
            flag = " · <b>excluido del análisis</b>" if r["excluded"] else ""
            lines.append(f"\n<b>{escape(r['rule'])} {escape(r['label'])}</b> ({escape(r['severity'])}){flag}: {r['n']}")
            projs = r["projects"]
            lines.append(", ".join(escape(p) for p in projs[:40]) + (f" … (+{len(projs) - 40})" if len(projs) > 40 else ""))
        if not res["rows"]:
            lines.append("Sin hallazgos ✅")
    else:
        return not_understood()
    lines.append(_foot(res, when))
    return _split(lines)


# ---------------------------------------------------------------------------------- opción 7: estatus por ID
LBL = (("overall", "1 Overall"), ("schedule", "2 Cronograma"), ("cost", "3 Costo"), ("resources", "4 Recursos"),
       ("scope", "5 Alcance"))


def _m(v: Any) -> str:
    return "—" if v is None else f"${v:,.0f}"


def _n(v: Any, suf: str = "") -> str:
    if v is None:
        return "—"
    return (f"{v:,.0f}" if isinstance(v, float) and abs(v) >= 1000 else f"{v:g}" if isinstance(v, float) else str(v)) + suf


def _ci(v: str | None) -> str:
    return f"{ICON.get(v or 'DATO_FALTANTE', '⚪')} {v or 'sin dato'}"


def ask_id() -> list[str]:
    return ["<b>7. Estatus por ID</b>\nEscribe el ID que quieres consultar, por ejemplo:\n"
            "• Proyecto: <code>PRJ1001002</code>\n• Programa: <code>PRG0002</code>\n• Portafolio: <code>PFL0001</code>\n\n"
            "También funciona <code>/estatus PRG0002</code>."]


def _project(res: dict) -> list[str]:
    head = [f"📌 <b>{escape(res['code'])}</b> · {escape(res.get('name') or '')}",
            f"{escape(res['categoria'])} ({escape(str(res.get('state')))}) · Región: {escape(res.get('region') or 'sin región')}",
            f"PM: {escape(res.get('pm') or 'sin PM')} · Programa: {escape(res.get('programa') or '—')} · "
            f"Portafolio: {escape(res.get('portafolio') or '—')}"]
    dq = res.get("dq", [])
    dq_lines = ["\n<b>Calidad de datos</b>"] + ([f"• {escape(d['rule'])} {escape(d['label'])} ({escape(d['severity'])})"
                                                 + (" · excluido" if d["excluded"] else "") for d in dq] or ["• Sin hallazgos ✅"])
    if not res["analyzed"]:
        return head + [f"\n⚠️ Sin KPIs: proyecto {escape(res['why'])}."] + dq_lines
    r = res["report"]
    h, perf, ctl = r["health"], r["performance"], r["control"]
    s, c, rs, d = perf["schedule"], perf["cost"], perf["resources"], perf["dates"]
    sr = f"SR al {escape(_n(r.get('sr_as_on')))}" + (" ⚠️ desactualizado" if r.get("sr_stale") else "")
    lines = head + [("⚠️ Sin Status Report" if r.get("sr_missing") else sr), "\n<b>Salud</b> (calculado | PM declara | comparación)"]
    for k, lbl in LBL:
        lines.append(f"{lbl}: {_ci(h[k]['calculated'])} | {_ci(h[k]['declared'])} | {escape(h[k]['comparison'])}")
    if h["overall"].get("incomplete_evidence"):
        lines.append("<i>Overall con evidencia incompleta</i>")
    lines += ["\n<b>Desempeño</b>",
              f"6 Avance: {_n(s.get('percent_complete'), '%')} (esperado {_n(s.get('expected_pct'), '%')}, brecha {_n(s.get('gap_pp'))} pp)",
              f"7-8 Plan: {escape(_n(d.get('planned_start')))} → {escape(_n(d.get('planned_end')))}",
              f"9-10 Real: {escape(_n(d.get('actual_start')))} → {escape(_n(d.get('actual_end')))} · variación fin {_n(s.get('end_variance_days'))} días",
              f"11-12 Costo: plan {_m(c.get('planned_cost'))} · real {_m(c.get('actual_cost'))} · CPI {_n(c.get('cpi'))} · consumo {_n(c.get('consumption_pct'), '%')}",
              f"13 Esfuerzo: plan {_n(rs.get('planned_effort'))} h · real {_n(rs.get('actual_effort'))} h · índice {_n(rs.get('effort_index'))}"]
    if rs.get("allocation"):
        a = rs["allocation"]
        lines.append(f"    Asignado vs real: {_n(a['allocated_hours'])} h vs {_n(a['actual_hours'])} h")

    def cl(key, fmt):
        v = ctl.get(key)
        return "DATO_FALTANTE" if not isinstance(v, dict) else fmt(v)
    lines += ["\n<b>Control</b>",
              "14 Hitos: " + cl("milestones", lambda v: f"{v['completed']}/{v['total']} completados · {v['overdue']} vencidos"),
              "15 Riesgos: " + cl("risks", lambda v: f"{v['open']} abiertos · {v['open_high']} altos · {v['overdue']} vencidos · {v['no_owner']} sin responsable"),
              "16 Issues: " + cl("issues", lambda v: f"{v['open']} abiertos · {v['no_owner']} sin responsable"),
              "17 Decisiones: " + cl("decisions", lambda v: f"{v['pending']} pendientes · antigüedad máx {_n(v['max_age_days'])} días"),
              "18 Acciones: " + cl("actions", lambda v: f"{v['pending']} pendientes · {v['pending_approval']} por aprobar · {v['overdue']} vencidas"),
              "19 Cambios: " + cl("change_requests", lambda v: f"{v['pending']} pendientes · {v['pending_over_days']} con más de {v['threshold_days']} días")]
    lines += dq_lines
    if r.get("alerts"):
        lines += ["\n<b>Alertas</b>"] + [f"• {escape(a)}" for a in r["alerts"]]
    return lines


def _rollup(res: dict) -> list[str]:
    ru, p, k = res["rollup"], res["perf"], res["ctl"]
    icon = "🗂" if res["level"] == "programa" else "🏢"
    lines = [f"{icon} <b>{escape(res['code'])}</b> · {escape(res.get('name') or '')}",
             f"Responsable: {escape(res.get('manager') or 'sin asignar')}",
             f"Proyectos: {res['total']} · activos {res['activos']} · analizados {res['analizados']}"]
    if not ru.get("distribution"):
        return lines + ["\nSin proyectos activos analizados: no hay KPIs que agregar."]
    lines.append(f"\n<b>Salud</b> (proyectos 🟢 🟡 🔴 ⚪) · peor caso {_ci(ru['worst_overall'])}")
    for key, lbl in LBL:
        dd = ru["distribution"][key]
        lines.append(f"{lbl}: {dd['Verde']['n']}🟢 {dd['Amarillo']['n']}🟡 {dd['Rojo']['n']}🔴 {dd['DATO_FALTANTE']['n']}⚪")
    cpi = ru.get("cpi", {})
    lines += ["\n<b>Desempeño</b>",
              f"6 Avance ponderado por presupuesto: {_n(p['pc_ponderado'], '%')} (mediana {_n(p['pc_mediana'], '%')}; "
              f"mín–máx {_n(p['pc_min'], '%')}–{_n(p['pc_max'], '%')})",
              f"7-10 Proyectos con fin planeado vencido: {p['vencidos']}",
              f"11-12 Costo: plan {_m(p['costo_plan'])} · real {_m(p['costo_real'])}",
              f"    CPI agregado {_n(cpi.get('aggregate'))} (mediana {_n(cpi.get('median'))}; mín–máx {_n(cpi.get('min'))}–{_n(cpi.get('max'))}; n={cpi.get('n')})",
              f"    Presupuesto en proyectos Rojo: {_n(ru.get('budget_in_red_pct'), '%')}",
              f"13 Esfuerzo: plan {_n(float(p['esfuerzo_plan']))} h · real {_n(float(p['esfuerzo_real']))} h",
              "\n<b>Control</b> (suma de proyectos)",
              f"14 Hitos: {_n(k['hitos_pendientes'])} pendientes · {_n(k['hitos_vencidos'])} vencidos",
              f"15 Riesgos: {_n(k['riesgos_abiertos'])} abiertos · {_n(k['riesgos_altos'])} altos",
              f"16 Issues abiertos: {_n(k['issues_abiertos'])}",
              f"17 Decisiones pendientes: {_n(k['decisiones_pend'])}",
              f"18 Acciones: {_n(k['acciones_pend'])} pendientes · {_n(k['acciones_vencidas'])} vencidas",
              f"19 Cambios pendientes: {_n(k['cambios_pend'])}",
              f"\nDiscrepancias de optimismo (PM vs cálculo): {ru.get('optimism_discrepancies', 0)} · SR desactualizados: {ru.get('stale_reports', 0)}",
              "\n<b>Proyectos</b>"]
    lines += [f"• {escape(x['number'])} {ICON.get(x['overall'], '⚪') if x['overall'] else '—'} {escape(x['categoria'])}"
              for x in res["projects"][:60]]
    if len(res["projects"]) > 60:
        lines.append(f"… y {len(res['projects']) - 60} más")
    return lines


def render_status(res: dict, when: str) -> list[str]:
    if not res.get("level"):
        return ask_id()
    if not res["found"]:
        return [f"No encontré el {escape(res['level'])} <b>{escape(res['code'])}</b>. Revisa el ID (por ejemplo "
                "<code>PRJ1001002</code>, <code>PRG0002</code>, <code>PFL0001</code>)."]
    lines = _project(res) if res["level"] == "proyecto" else _rollup(res)
    lines.append(_foot(res, when))
    return _split(lines)
