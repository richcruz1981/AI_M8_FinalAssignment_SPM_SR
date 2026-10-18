"""Plantillas de Telegram del SR (HTML de Telegram), en inglés. El color siempre va acompañado de texto.

El canal de correo se retiró el 2026-10-18 (sin servidor SMTP disponible): Telegram lleva el detalle completo.
"""
from __future__ import annotations

import datetime as dt
from html import escape
from typing import Any

ICON = {"Verde": "🟢", "Amarillo": "🟡", "Rojo": "🔴", "DATO_FALTANTE": "⚪"}
SHORT = {"schedule": "Schedule", "cost": "Cost", "resources": "Resources", "scope": "Scope"}
EN = {"Verde": "Green", "Amarillo": "Amber", "Rojo": "Red", "DATO_FALTANTE": "No data",
      "Programa": "Program", "Portafolio": "Portfolio", "Escalamiento": "Escalation"}
LIMIT = 3900  # límite de Telegram: 4096 caracteres por mensaje


def _c(v: str | None) -> str:
    v = v or "DATO_FALTANTE"
    return f"{ICON.get(v, '')} {EN.get(v, v)}"


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:g}"
    return str(v)


def _project_block(r: dict, include_costs: bool) -> list[str]:
    h, perf, ctl = r["health"], r["performance"], r["control"]
    s, c = perf["schedule"], perf["cost"]
    sem = " · ".join(f"{SHORT[k]} {ICON.get(h[k]['calculated'], '⚪')}" for k in SHORT)
    lines = [f"\n<b>{escape(r['number'])}</b> {escape(r.get('name') or '')}",
             f"Overall {_c(h['overall']['calculated'])} (PM declared: {escape(EN.get(h['overall']['declared'] or 'DATO_FALTANTE', h['overall']['declared']))})",
             sem]
    if s.get("percent_complete") is not None:
        lines.append(f"Progress {_fmt(s['percent_complete'])}% vs {_fmt(s.get('expected_pct'))}% expected "
                     f"({_fmt(s.get('gap_pp'))} pp)")
    if include_costs and c.get("cpi") is not None:
        lines.append(f"CPI {c['cpi']} · budget used {_fmt(c.get('consumption_pct'))}%")
    ms, rk = ctl.get("milestones"), ctl.get("risks")
    ctl_bits = []
    if isinstance(ms, dict):
        ctl_bits.append(f"Milestones {ms['completed']}/{ms['total']} ({ms['overdue']} overdue)")
    if isinstance(rk, dict):
        ctl_bits.append(f"Open risks {rk['open']} ({rk['open_high']} high)")
    if ctl_bits:
        lines.append(" · ".join(ctl_bits))
    if r.get("sr_missing"):
        lines.append("⚠️ No status report")
    elif r.get("sr_stale"):
        lines.append(f"⚠️ Stale status report ({escape(_fmt(r.get('sr_as_on')))})")
    lines += [f"• {escape(a)}" for a in r["alerts"][:3]]
    return lines


def _rollup_block(ru: dict) -> list[str]:
    if not ru.get("distribution"):
        return [f"\n<b>{escape(EN.get(ru['level'], ru['level']))} {escape(str(ru.get('number')))}</b>: no valid projects"]
    d = ru["distribution"]["overall"]
    out = [f"\n<b>{escape(EN.get(ru['level'], ru['level']))} {escape(str(ru.get('number')))}</b> {escape(ru.get('name') or '')}",
           f"{ru['n_projects']} projects: {d['Verde']['n']}🟢 {d['Amarillo']['n']}🟡 {d['Rojo']['n']}🔴 "
           f"{d['DATO_FALTANTE']['n']}⚪ · worst case {_c(ru['worst_overall'])}"]
    if ru.get("budget_in_red_pct") is not None:
        out.append(f"Budget in Red projects: {ru['budget_in_red_pct']}%")
    if ru.get("optimism_discrepancies"):
        out.append(f"Optimistic reports (PM vs calculated): {ru['optimism_discrepancies']}")
    reds = [x["number"] for x in ru.get("red_projects", [])][:8]
    if reds:
        out.append("Red: " + ", ".join(escape(x) for x in reds) + (" …" if len(ru.get("red_projects", [])) > 8 else ""))
    out.append(escape(ru["narrative"]["text"]))
    return out


def telegram(recipient: dict, reports: list[dict], rollups: list[dict], escalated: list[dict], run_date: dt.date,
             include_costs: bool, partial_note: str | None, redirected: bool = False) -> list[str]:
    """Devuelve uno o más mensajes (se dividen por bloques si exceden el límite de Telegram)."""
    head = [f"<b>Status report {run_date.isoformat()}</b> · {escape('/'.join(recipient['roles']) or 'Escalation')}"]
    if redirected:
        head.append(f"📨 Original recipient: {escape(recipient.get('name') or recipient.get('user_id', ''))}")
    if partial_note:
        head.append(f"⚠️ Incomplete evidence: {escape(partial_note)}")
    blocks: list[list[str]] = [_rollup_block(ru) for ru in rollups]
    blocks += [_project_block(r, include_costs) for r in reports]
    if escalated:
        blocks.append(["\n<b>Escalated (projects without a reachable PM)</b>"])
        blocks += [_project_block(r, include_costs) for r in escalated]
    blocks.append(["\n<i>Health calculated with configurable thresholds (assumption); expected progress is linear.</i>"])
    msgs, cur = [], "\n".join(head)
    for b in blocks:
        txt = "\n".join(b)
        if len(cur) + len(txt) + 1 > LIMIT:
            msgs.append(cur)
            cur = txt.lstrip("\n")
        else:
            cur += "\n" + txt
    msgs.append(cur)
    if len(msgs) > 1:
        msgs = [f"{m}\n\n<i>({i}/{len(msgs)})</i>" for i, m in enumerate(msgs, start=1)]
    return msgs


def failure_text(report_md: str) -> str:
    return "Status report · RUN FAILURE\n\n" + report_md
