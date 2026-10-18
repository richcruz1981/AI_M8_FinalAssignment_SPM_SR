"""Plantillas de Telegram (HTML de Telegram). El color siempre va acompañado de texto.

El canal de correo se retiró el 2026-10-18 (sin servidor SMTP disponible): Telegram lleva el detalle completo.
"""
from __future__ import annotations

import datetime as dt
from html import escape
from typing import Any

ICON = {"Verde": "🟢", "Amarillo": "🟡", "Rojo": "🔴", "DATO_FALTANTE": "⚪"}
SHORT = {"schedule": "Crono", "cost": "Costo", "resources": "Recursos", "scope": "Alcance"}
LIMIT = 3900  # límite de Telegram: 4096 caracteres por mensaje


def _c(v: str | None) -> str:
    v = v or "DATO_FALTANTE"
    return f"{ICON.get(v, '')} {v}"


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
             f"Overall {_c(h['overall']['calculated'])} (PM declara: {escape(h['overall']['declared'] or 'sin dato')})",
             sem]
    if s.get("percent_complete") is not None:
        lines.append(f"Avance {_fmt(s['percent_complete'])}% vs {_fmt(s.get('expected_pct'))}% esperado "
                     f"({_fmt(s.get('gap_pp'))} pp)")
    if include_costs and c.get("cpi") is not None:
        lines.append(f"CPI {c['cpi']} · consumo {_fmt(c.get('consumption_pct'))}%")
    ms, rk = ctl.get("milestones"), ctl.get("risks")
    ctl_bits = []
    if isinstance(ms, dict):
        ctl_bits.append(f"Hitos {ms['completed']}/{ms['total']} ({ms['overdue']} vencidos)")
    if isinstance(rk, dict):
        ctl_bits.append(f"Riesgos abiertos {rk['open']} ({rk['open_high']} altos)")
    if ctl_bits:
        lines.append(" · ".join(ctl_bits))
    if r.get("sr_missing"):
        lines.append("⚠️ Sin Status Report")
    elif r.get("sr_stale"):
        lines.append(f"⚠️ SR desactualizado ({escape(_fmt(r.get('sr_as_on')))})")
    lines += [f"• {escape(a)}" for a in r["alerts"][:3]]
    return lines


def _rollup_block(ru: dict) -> list[str]:
    if not ru.get("distribution"):
        return [f"\n<b>{escape(ru['level'])} {escape(str(ru.get('number')))}</b>: sin proyectos válidos"]
    d = ru["distribution"]["overall"]
    out = [f"\n<b>{escape(ru['level'])} {escape(str(ru.get('number')))}</b> {escape(ru.get('name') or '')}",
           f"{ru['n_projects']} proyectos: {d['Verde']['n']}🟢 {d['Amarillo']['n']}🟡 {d['Rojo']['n']}🔴 "
           f"{d['DATO_FALTANTE']['n']}⚪ · peor caso {_c(ru['worst_overall'])}"]
    if ru.get("budget_in_red_pct") is not None:
        out.append(f"Presupuesto en proyectos Rojo: {ru['budget_in_red_pct']}%")
    if ru.get("optimism_discrepancies"):
        out.append(f"Discrepancias de optimismo (PM vs cálculo): {ru['optimism_discrepancies']}")
    reds = [x["number"] for x in ru.get("red_projects", [])][:8]
    if reds:
        out.append("En Rojo: " + ", ".join(escape(x) for x in reds) + (" …" if len(ru.get("red_projects", [])) > 8 else ""))
    out.append(escape(ru["narrative"]["text"]))
    return out


def telegram(recipient: dict, reports: list[dict], rollups: list[dict], escalated: list[dict], run_date: dt.date,
             include_costs: bool, partial_note: str | None, redirected: bool = False) -> list[str]:
    """Devuelve uno o más mensajes (se dividen por bloques si exceden el límite de Telegram)."""
    head = [f"<b>SR diario {run_date.isoformat()}</b> · {escape('/'.join(recipient['roles']) or 'Escalamiento')}"]
    if redirected:
        head.append(f"📨 Destinatario original: {escape(recipient.get('name') or recipient.get('user_id', ''))}")
    if partial_note:
        head.append(f"⚠️ Evidencia incompleta: {escape(partial_note)}")
    blocks: list[list[str]] = [_rollup_block(ru) for ru in rollups]
    blocks += [_project_block(r, include_costs) for r in reports]
    if escalated:
        blocks.append(["\n<b>Escalados (proyectos sin PM con contacto)</b>"])
        blocks += [_project_block(r, include_costs) for r in escalated]
    blocks.append(["\n<i>Semáforos calculados con umbrales configurables (SUPUESTO); avance esperado lineal.</i>"])
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
    return "SR diario · FALLA en la corrida\n\n" + report_md
