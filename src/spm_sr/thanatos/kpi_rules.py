"""Reglas deterministas de KPIs (docs/plan/05). Ningún número sale de un LLM."""
from __future__ import annotations

import datetime as dt
from typing import Any

from ..core.util import norm, parse_date, to_float

G, Y, R, DF = "Verde", "Amarillo", "Rojo", "DATO_FALTANTE"
RANK = {G: 0, Y: 1, R: 2}


def _r(v: float | None, n: int = 2) -> float | None:
    return None if v is None else round(v, n)


def schedule(p: dict, as_of: dt.date, th: dict) -> dict[str, Any]:
    ps, pe, pc = parse_date(p.get("planned_start")), parse_date(p.get("planned_end")), to_float(p.get("percent_complete"))
    src = "pm_project.start_date/end_date/percent_complete"
    if ps is None or pe is None or pc is None:
        return {"color": DF, "source_field": src, "note": "Fechas planeadas o % de avance faltantes"}
    dur = (pe - ps).days
    if dur <= 0:
        expected = 100.0 if as_of >= pe else 0.0
    else:
        expected = max(0.0, min(1.0, (as_of - ps).days / dur)) * 100
    gap = pc - expected
    overdue = as_of > pe and pc < 100
    if overdue or gap < th["red_gap_pp"]:
        color = R
    elif gap < th["yellow_gap_pp"]:
        color = Y
    else:
        color = G
    ae = parse_date(p.get("actual_end"))
    end_var = (ae - pe).days if ae else ((as_of - pe).days if overdue else None)
    return {"color": color, "source_field": src, "percent_complete": _r(pc, 1), "expected_pct": _r(expected, 1),
            "gap_pp": _r(gap, 1), "overdue": overdue, "end_variance_days": end_var,
            "note": "Avance esperado lineal (subestima curvas S)"}


def cost(p: dict, th: dict) -> dict[str, Any]:
    pcst, ac, pc = to_float(p.get("planned_cost")), to_float(p.get("actual_cost")), to_float(p.get("percent_complete"))
    src = "pm_project.cost/work_cost/percent_complete"
    if not pcst or ac is None or pc is None:
        return {"color": DF, "source_field": src, "note": "Costo planeado nulo/0 o costo real faltante"}
    ev = pcst * pc / 100
    consumption = ac / pcst
    cpi = ev / ac if ac > 0 else None
    note = None
    if consumption > th["max_consumption"]:
        color = R
    elif cpi is None:
        color, note = G, "Sin costo real registrado (CPI no calculable)"
    elif cpi < th["yellow_cpi"]:
        color = R
    elif cpi < th["green_cpi"]:
        color = Y
    else:
        color = G
    return {"color": color, "source_field": src, "planned_cost": pcst, "actual_cost": ac, "earned_value": _r(ev),
            "cpi": _r(cpi), "consumption_pct": _r(consumption * 100, 1), "cost_variance": _r(ev - ac), "note": note}


def resources(p: dict, alloc_rows: list[dict] | None, th: dict) -> dict[str, Any]:
    planned, actual, pc = to_float(p.get("planned_effort")), to_float(p.get("actual_effort")), to_float(p.get("percent_complete"))
    src = "pm_project.effort/work_effort"
    alloc = None
    if alloc_rows:
        a = sum(to_float(r.get("allocated_hours")) or 0 for r in alloc_rows)
        b = sum(to_float(r.get("actual_hours")) or 0 for r in alloc_rows)
        alloc = {"allocated_hours": _r(a, 1), "actual_hours": _r(b, 1), "ratio": _r(b / a) if a else None,
                 "source_field": "resource_allocation.allocated_hours/actual_hours"}
    if (not planned or actual is None) and alloc and alloc["ratio"] is not None:
        idx, src, note = alloc["ratio"], alloc["source_field"], "Índice con horas asignadas vs reales (sin esfuerzo planeado)"
    elif not planned or actual is None or pc is None:
        return {"color": DF, "source_field": src, "allocation": alloc, "note": "Esfuerzo planeado nulo/0 o real faltante"}
    elif pc == 0:
        color = G if actual == 0 else Y
        return {"color": color, "source_field": src, "effort_index": None, "planned_effort": planned,
                "actual_effort": actual, "allocation": alloc,
                "note": None if actual == 0 else "Esfuerzo consumido sin avance registrado"}
    else:
        idx, note = actual / (planned * pc / 100), None
    if th["green_low"] <= idx <= th["green_high"]:
        color = G
    elif th["yellow_low"] <= idx <= th["yellow_high"]:
        color = Y
    else:
        color = R
    return {"color": color, "source_field": src, "effort_index": _r(idx), "planned_effort": planned,
            "actual_effort": actual, "allocation": alloc, "note": note}


def scope(change_rows: list[dict] | None, available: bool, th: dict, pending_states: set[str]) -> dict[str, Any]:
    src = "project_change_request.state"
    if not available:
        return {"color": DF, "source_field": src, "note": "Tabla de solicitudes de cambio no disponible"}
    pending = sum(1 for r in (change_rows or []) if norm(r.get("state")) in pending_states)
    if pending >= th["red_pending"]:
        color = R
    elif pending >= th["yellow_pending"]:
        color = Y
    else:
        color = G
    return {"color": color, "source_field": src, "pending_changes": pending,
            "note": "Regla 'cambio aprobado sin re-línea base' no calculable con OOB"}


def overall(components: dict[str, str]) -> dict[str, Any]:
    known = {k: v for k, v in components.items() if v != DF}
    incomplete = len(known) < len(components)
    if not known:
        return {"color": DF, "incomplete_evidence": True}
    reds = [k for k, v in known.items() if v == R]
    if known.get("schedule") == R or known.get("cost") == R or len(reds) >= 2:
        color = R
    elif any(v in (Y, R) for v in known.values()):
        color = Y
    else:
        color = G
    return {"color": color, "incomplete_evidence": incomplete, "red_components": reds}


def compare(declared: str | None, calculated: str) -> str:
    if declared not in RANK or calculated not in RANK:
        return "No comparable"
    if RANK[declared] < RANK[calculated]:
        return "Optimismo"
    if RANK[declared] > RANK[calculated]:
        return "Conservador"
    return "Consistente"
