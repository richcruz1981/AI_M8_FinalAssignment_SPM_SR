"""Bot replies (Radamantis) in Telegram HTML, in English. Every reply states where the data comes from.

Internal values (Spanish keys from Cronos/Thanatos) are translated here through `i18n`; names stored in the
database (projects, regions, people) are shown as stored.
"""
from __future__ import annotations

from html import escape
from typing import Any

from . import i18n
from .render import ICON, LIMIT

MENU_BUTTONS = [["1️⃣ Total projects", "2️⃣ By category"],
                ["3️⃣ By region", "4️⃣ By program"],
                ["5️⃣ By portfolio", "6️⃣ Data quality"],
                ["7️⃣ Status by ID (project / program / portfolio)"]]
COMMANDS = [("total", "Total projects"), ("categories", "Projects by category (state)"),
            ("regions", "Projects by region"), ("programs", "Projects by program"),
            ("portfolios", "Projects by portfolio"), ("dataquality", "Projects with data-quality issues"),
            ("status", "KPIs for a project, program or portfolio (e.g. /status PRG0002)"),
            ("menu", "Show the menu")]


def keyboard() -> dict:
    return {"keyboard": [[{"text": b} for b in row] for row in MENU_BUTTONS], "resize_keyboard": True,
            "is_persistent": True}


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "—"


def _foot(res: dict, when: str) -> str:
    return f"\n<i>Source: {escape(i18n.source(res.get('source_field', '')))} · data read {escape(when)}</i>"


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
    hi = f"Hi {escape(name)} 👋" if name else "Hi 👋"
    return [f"{hi} I'm <b>Radamantis</b>, the executor of the project status-report system.\n\n"
            "Pick an option from the menu or type a command:\n"
            + "\n".join(f"/{c} — {escape(d)}" for c, d in COMMANDS[:-1])
            + "\n\nOr just type an ID: <code>PRJ1001002</code>, <code>PRG0002</code>, <code>PFL0001</code>."
            + "\n\nData is read live from the database (<b>synthetic demo data</b>)."]


def not_understood() -> list[str]:
    return ["Sorry, I didn't understand that request. Use the menu or /menu to see the options."]


def unauthorized(chat_id: Any) -> list[str]:
    return [f"⛔ This chat is not authorized.\nShare this chat_id with the administrator: <code>{escape(str(chat_id))}</code>"]


def blocked(quarantined: bool = False, minutes: int = 30) -> list[str]:
    msg = ("🛡️ Request blocked by the security policy (Cerbero). Please use the menu options or type an ID "
           "such as <code>PRJ1001002</code>.")
    if quarantined:
        msg += f"\nToo many blocked requests: this chat is paused for {minutes} minutes."
    return [msg]


def error(code: str, detail: str = "") -> list[str]:
    return [f"⚠️ I couldn't retrieve the data ({escape(code)}).\nPlease try again in a few minutes; "
            "the administrator has the technical details."]


def _hicons(ov: dict) -> str:
    return " · ".join(f"{ICON[c]} {i18n.h(c)} {ov.get(c, 0)}" for c in ("Verde", "Amarillo", "Rojo", "DATO_FALTANTE"))


def render(res: dict, when: str) -> list[str]:
    k = res["kind"]
    if k == "total":
        lines = ["<b>1. Total projects</b>",
                 f"Total in the database: <b>{res['total']}</b>",
                 f"Active: {res['activos']} · Closed/cancelled: {res['cerrados_cancelados']}",
                 f"Analyzed by Thanatos: {res['analizados']} (excluded by data quality: {res['excluidos_dq']})",
                 "Calculated health (active, analyzed): " + _hicons(res["overall"])]
    elif k == "categorias":
        lines = ["<b>2. Projects by category</b>", f"Total: {res['total']}"]
        for r in res["rows"]:
            det = ", ".join(f"{escape(i18n.ph(s))} {n}" for s, n in sorted(r["estados"].items(), key=lambda x: -x[1]))
            lines.append(f"• <b>{escape(i18n.cat(r['categoria']))}</b>: {r['n']} ({_pct(r['n'], res['total'])}) — {det}")
    elif k == "regiones":
        lines = ["<b>3. Projects by region</b>"]
        if not res["available"]:
            lines.append("The region field (u_region) does not exist in the database.")
        else:
            lines.append(f"Total: {res['total']}")
            lines += [f"• <b>{escape(i18n.ph(r['region']))}</b>: {r['n']} ({_pct(r['n'], res['total'])}) · "
                      f"active {r['activos']}" for r in res["rows"]]
    elif k in ("programas", "portafolios"):
        title = "4. Projects by program" if k == "programas" else "5. Projects by portfolio"
        noun = "programs" if k == "programas" else "portfolios"
        lines = [f"<b>{title}</b>",
                 f"{res['con_proyectos']} {noun} with projects · {res['sin_proyectos']} without projects · "
                 f"{res['total']} projects in total",
                 "<i>Format: projects (active) · health of active projects 🟢 Green 🟡 Amber 🔴 Red</i>"]
        for r in res["rows"]:
            name = f" {escape(r['name'])}" if r.get("name") else ""
            lines.append(f"• <b>{escape(i18n.ph(r['number']))}</b>{name}: {r['n']} ({r['activos']}) · "
                         f"{r['verde']}🟢 {r['amarillo']}🟡 {r['rojo']}🔴")
    elif k == "calidad":
        lines = ["<b>6. Projects with data-quality issues</b>",
                 f"Affected: <b>{res['proyectos_afectados']}</b> of {res['evaluados']} evaluated",
                 "<i>Only active projects are evaluated (not closed or cancelled).</i>"]
        for r in res["rows"]:
            flag = " · <b>excluded from analysis</b>" if r["excluded"] else ""
            lines.append(f"\n<b>{escape(r['rule'])} {escape(i18n.dq(r['rule'], r['label']))}</b> "
                         f"({escape(i18n.sev(r['severity']))} severity){flag}: {r['n']}")
            projs = r["projects"]
            lines.append(", ".join(escape(p) for p in projs[:40]) + (f" … (+{len(projs) - 40})" if len(projs) > 40 else ""))
        if not res["rows"]:
            lines.append("No findings ✅")
    else:
        return not_understood()
    lines.append(_foot(res, when))
    return _split(lines)


# ---------------------------------------------------------------------------------- option 7: status by ID
LBL = (("overall", "1 Overall"), ("schedule", "2 Schedule"), ("cost", "3 Cost"), ("resources", "4 Resources"),
       ("scope", "5 Scope"))


def _m(v: Any) -> str:
    return "—" if v is None else f"${v:,.0f}"


def _n(v: Any, suf: str = "") -> str:
    if v is None:
        return "—"
    return (f"{v:,.0f}" if isinstance(v, float) and abs(v) >= 1000 else f"{v:g}" if isinstance(v, float) else str(v)) + suf


def _ci(v: str | None) -> str:
    return f"{ICON.get(v or 'DATO_FALTANTE', '⚪')} {i18n.h(v or 'DATO_FALTANTE')}"


def ask_id() -> list[str]:
    return ["<b>7. Status by ID</b>\nType the ID you want to look up, for example:\n"
            "• Project: <code>PRJ1001002</code>\n• Program: <code>PRG0002</code>\n• Portfolio: <code>PFL0001</code>\n\n"
            "<code>/status PRG0002</code> also works."]


def _dq_lines(dq: list[dict]) -> list[str]:
    return ["\n<b>Data quality</b>"] + (
        [f"• {escape(d['rule'])} {escape(i18n.dq(d['rule'], d['label']))} ({escape(i18n.sev(d['severity']))})"
         + (" · excluded" if d["excluded"] else "") for d in dq] or ["• No findings ✅"])


def _project(res: dict) -> list[str]:
    head = [f"📌 <b>{escape(res['code'])}</b> · {escape(res.get('name') or '')}",
            f"{escape(i18n.cat(res['categoria']))} ({escape(str(res.get('state')))}) · "
            f"Region: {escape(res.get('region') or 'no region')}",
            f"PM: {escape(res.get('pm') or 'no PM')} · Program: {escape(res.get('programa') or '—')} · "
            f"Portfolio: {escape(res.get('portafolio') or '—')}"]
    dq_lines = _dq_lines(res.get("dq", []))
    if not res["analyzed"]:
        return head + [f"\n⚠️ No KPIs: project {escape(i18n.WHY.get(res['why'], res['why']))}."] + dq_lines
    r = res["report"]
    h, perf, ctl = r["health"], r["performance"], r["control"]
    s, c, rs, d = perf["schedule"], perf["cost"], perf["resources"], perf["dates"]
    sr = f"Status report as of {escape(_n(r.get('sr_as_on')))}" + (" ⚠️ stale" if r.get("sr_stale") else "")
    lines = head + [("⚠️ No status report" if r.get("sr_missing") else sr),
                    "\n<b>Health</b> (calculated | PM declared | comparison)"]
    for k, lbl in LBL:
        lines.append(f"{lbl}: {_ci(h[k]['calculated'])} | {_ci(h[k]['declared'])} | {escape(i18n.cmp(h[k]['comparison']))}")
    if h["overall"].get("incomplete_evidence"):
        lines.append("<i>Overall based on incomplete evidence</i>")
    lines += ["\n<b>Performance</b>",
              f"6 Progress: {_n(s.get('percent_complete'), '%')} (expected {_n(s.get('expected_pct'), '%')}, "
              f"gap {_n(s.get('gap_pp'))} pp)",
              f"7-8 Planned: {escape(_n(d.get('planned_start')))} → {escape(_n(d.get('planned_end')))}",
              f"9-10 Actual: {escape(_n(d.get('actual_start')))} → {escape(_n(d.get('actual_end')))} · "
              f"end variance {_n(s.get('end_variance_days'))} days",
              f"11-12 Cost: planned {_m(c.get('planned_cost'))} · actual {_m(c.get('actual_cost'))} · "
              f"CPI {_n(c.get('cpi'))} · budget used {_n(c.get('consumption_pct'), '%')}",
              f"13 Effort: planned {_n(rs.get('planned_effort'))} h · actual {_n(rs.get('actual_effort'))} h · "
              f"index {_n(rs.get('effort_index'))}"]
    if rs.get("allocation"):
        a = rs["allocation"]
        lines.append(f"    Allocated vs actual: {_n(a['allocated_hours'])} h vs {_n(a['actual_hours'])} h")

    def cl(key, fmt):
        v = ctl.get(key)
        return "No data" if not isinstance(v, dict) else fmt(v)
    lines += ["\n<b>Control</b>",
              "14 Milestones: " + cl("milestones", lambda v: f"{v['completed']}/{v['total']} completed · {v['overdue']} overdue"),
              "15 Risks: " + cl("risks", lambda v: f"{v['open']} open · {v['open_high']} high · {v['overdue']} overdue · "
                                                  f"{v['no_owner']} without owner"),
              "16 Issues: " + cl("issues", lambda v: f"{v['open']} open · {v['no_owner']} without owner"),
              "17 Decisions: " + cl("decisions", lambda v: f"{v['pending']} pending · oldest {_n(v['max_age_days'])} days"),
              "18 Actions: " + cl("actions", lambda v: f"{v['pending']} pending · {v['pending_approval']} awaiting approval · "
                                                      f"{v['overdue']} overdue"),
              "19 Change requests: " + cl("change_requests", lambda v: f"{v['pending']} pending · {v['pending_over_days']} "
                                                                      f"older than {v['threshold_days']} days")]
    lines += dq_lines
    al = i18n.alerts(r)
    if al:
        lines += ["\n<b>Alerts</b>"] + [f"• {escape(a)}" for a in al]
    return lines


def _rollup(res: dict) -> list[str]:
    ru, p, k = res["rollup"], res["perf"], res["ctl"]
    icon = "🗂" if res["level"] == "programa" else "🏢"
    lines = [f"{icon} <b>{escape(res['code'])}</b> · {escape(res.get('name') or '')}",
             f"Owner: {escape(res.get('manager') or 'unassigned')}",
             f"Projects: {res['total']} · active {res['activos']} · analyzed {res['analizados']}"]
    if not ru.get("distribution"):
        return lines + ["\nNo active analyzed projects: there are no KPIs to aggregate."]
    lines.append(f"\n<b>Health</b> (projects 🟢 Green 🟡 Amber 🔴 Red ⚪ No data) · worst case {_ci(ru['worst_overall'])}")
    for key, lbl in LBL:
        dd = ru["distribution"][key]
        lines.append(f"{lbl}: {dd['Verde']['n']}🟢 {dd['Amarillo']['n']}🟡 {dd['Rojo']['n']}🔴 {dd['DATO_FALTANTE']['n']}⚪")
    cpi = ru.get("cpi", {})
    lines += ["\n<b>Performance</b>",
              f"6 Budget-weighted progress: {_n(p['pc_ponderado'], '%')} (median {_n(p['pc_mediana'], '%')}; "
              f"min–max {_n(p['pc_min'], '%')}–{_n(p['pc_max'], '%')})",
              f"7-10 Projects past planned end: {p['vencidos']}",
              f"11-12 Cost: planned {_m(p['costo_plan'])} · actual {_m(p['costo_real'])}",
              f"    Aggregate CPI {_n(cpi.get('aggregate'))} (median {_n(cpi.get('median'))}; "
              f"min–max {_n(cpi.get('min'))}–{_n(cpi.get('max'))}; n={cpi.get('n')})",
              f"    Budget in Red projects: {_n(ru.get('budget_in_red_pct'), '%')}",
              f"13 Effort: planned {_n(float(p['esfuerzo_plan']))} h · actual {_n(float(p['esfuerzo_real']))} h",
              "\n<b>Control</b> (sum across projects)",
              f"14 Milestones: {_n(k['hitos_pendientes'])} pending · {_n(k['hitos_vencidos'])} overdue",
              f"15 Risks: {_n(k['riesgos_abiertos'])} open · {_n(k['riesgos_altos'])} high",
              f"16 Open issues: {_n(k['issues_abiertos'])}",
              f"17 Pending decisions: {_n(k['decisiones_pend'])}",
              f"18 Actions: {_n(k['acciones_pend'])} pending · {_n(k['acciones_vencidas'])} overdue",
              f"19 Pending change requests: {_n(k['cambios_pend'])}",
              f"\nOptimistic reports (PM vs calculated): {ru.get('optimism_discrepancies', 0)} · "
              f"Stale status reports: {ru.get('stale_reports', 0)}",
              "\n<b>Projects</b>"]
    lines += [f"• {escape(x['number'])} {_ci(x['overall']) if x['overall'] else '— not analyzed'} · "
              f"{escape(i18n.cat(x['categoria']))}" for x in res["projects"][:60]]
    if len(res["projects"]) > 60:
        lines.append(f"… and {len(res['projects']) - 60} more")
    return lines


def render_status(res: dict, when: str) -> list[str]:
    if not res.get("level"):
        return ask_id()
    if not res["found"]:
        return [f"I couldn't find {escape(i18n.LEVEL.get(res['level'], res['level']))} <b>{escape(res['code'])}</b>. "
                "Please check the ID (e.g. <code>PRJ1001002</code>, <code>PRG0002</code>, <code>PFL0001</code>)."]
    lines = _project(res) if res["level"] == "proyecto" else _rollup(res)
    lines.append(_foot(res, when))
    return _split(lines)
