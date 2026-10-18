"""Consultas bajo demanda de Thanatos (usadas por Radamantis, el bot). Todo se calcula de los datos de Cronos.

Cada función recibe la salida de Cronos (C1) y, cuando aplica, la de Thanatos (C2), y devuelve un dict
estructurado que Zeus convierte en mensaje. Ninguna cifra sale de un LLM.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ..core.util import norm

STATE_CATEGORY = {
    "pending": "Abierto", "open": "Abierto", "new": "Abierto", "draft": "Abierto", "requested": "Abierto",
    "work_in_progress": "En progreso", "in_progress": "En progreso",
    "on_hold": "En pausa", "paused": "En pausa",
    "closed": "Cerrado", "closed_complete": "Cerrado", "closed_incomplete": "Cerrado", "closed_skipped": "Cerrado",
    "complete": "Cerrado", "completed": "Cerrado",
    "cancelled": "Cancelado", "canceled": "Cancelado",
}
CATEGORY_ORDER = ["Abierto", "En progreso", "En pausa", "Cerrado", "Cancelado", "Otro"]
DQ_LABELS = {
    "DQ-01": "Sin Status Report", "DQ-02": "Status Report desactualizado", "DQ-03": "% de avance inválido",
    "DQ-04": "Fechas planeadas inválidas o vacías", "DQ-05": "Avance sin fecha de inicio real",
    "DQ-06": "Costo o esfuerzo planeado faltante", "DQ-07": "Sin PM o PM sin correo",
    "DQ-08": "Semáforo declarado vacío", "DQ-09": "Registro duplicado", "DQ-10": "Sin región",
}
INTENTS = ("total", "categorias", "regiones", "programas", "portafolios", "calidad")


def category(state: Any) -> str:
    return STATE_CATEGORY.get(norm(state), "Otro")


def _active(p: dict) -> bool:
    return category(p.get("state")) not in ("Cerrado", "Cancelado")


def total(c: dict, t: dict | None) -> dict[str, Any]:
    inv = c.get("inventory", [])
    dq = c.get("data_quality", [])
    reps = (t or {}).get("project_reports", [])
    return {"kind": "total", "total": len(inv), "activos": sum(1 for p in inv if _active(p)),
            "cerrados_cancelados": sum(1 for p in inv if not _active(p)),
            "analizados": len(reps), "excluidos_dq": sum(1 for f in dq if f.get("excluded")),
            "overall": dict(Counter(r["health"]["overall"]["calculated"] for r in reps)),
            "source_field": "pm_project (todos los registros del alcance)"}


def by_category(c: dict, t: dict | None = None) -> dict[str, Any]:
    inv = c.get("inventory", [])
    cats = Counter(category(p.get("state")) for p in inv)
    raw = defaultdict(Counter)
    for p in inv:
        raw[category(p.get("state"))][str(p.get("state") or "(vacío)")] += 1
    rows = [{"categoria": k, "n": cats[k], "estados": dict(raw[k])} for k in CATEGORY_ORDER if cats.get(k)]
    return {"kind": "categorias", "total": len(inv), "rows": rows, "source_field": "pm_project.state"}


def by_region(c: dict, t: dict | None = None) -> dict[str, Any]:
    inv = c.get("inventory", [])
    if not c.get("region_available", False):
        return {"kind": "regiones", "total": len(inv), "rows": [], "available": False,
                "source_field": "pm_project.u_region (campo personalizado)"}
    cnt = Counter(p.get("region") or "(sin región)" for p in inv)
    act = Counter(p.get("region") or "(sin región)" for p in inv if _active(p))
    rows = [{"region": k, "n": n, "activos": act.get(k, 0)} for k, n in cnt.most_common()]
    return {"kind": "regiones", "total": len(inv), "rows": rows, "available": True,
            "source_field": "pm_project.u_region (campo personalizado)"}


def _by_parent(c: dict, t: dict | None, key: str, level: str, hier_key: str) -> dict[str, Any]:
    inv = c.get("inventory", [])
    ents = c.get("hierarchy", {}).get(hier_key, {})
    reps = {r["project_id"]: r for r in (t or {}).get("project_reports", [])}
    groups: dict[str, list] = defaultdict(list)
    for p in inv:
        groups[p.get(key) or "(sin asignar)"].append(p)
    rows = []
    for gid, ps in groups.items():
        e = ents.get(gid, {})
        colors = Counter(reps[p["id"]]["health"]["overall"]["calculated"] for p in ps if p["id"] in reps)
        rows.append({"id": gid, "number": e.get("number") or gid, "name": e.get("name"), "n": len(ps),
                     "activos": sum(1 for p in ps if _active(p)), "rojo": colors.get("Rojo", 0),
                     "amarillo": colors.get("Amarillo", 0), "verde": colors.get("Verde", 0)})
    rows.sort(key=lambda r: (-r["n"], str(r["number"])))
    return {"kind": level, "total": len(inv), "rows": rows, "con_proyectos": len(rows),
            "sin_proyectos": max(0, len(ents) - len([r for r in rows if r["id"] in ents])),
            "source_field": f"pm_project.{'primary_program' if key == 'program' else 'primary_portfolio'}"}


def by_program(c: dict, t: dict | None) -> dict[str, Any]:
    return _by_parent(c, t, "program", "programas", "program")


def by_portfolio(c: dict, t: dict | None) -> dict[str, Any]:
    return _by_parent(c, t, "portfolio", "portafolios", "portfolio")


def data_quality(c: dict, t: dict | None = None) -> dict[str, Any]:
    dq = c.get("data_quality", [])
    groups: dict[str, list] = defaultdict(list)
    for f in dq:
        groups[f["rule"]].append(f)
    rows = []
    for rule in sorted(groups):
        fs = groups[rule]
        projs = sorted({f.get("project_number") for f in fs if f.get("project_number")})
        rows.append({"rule": rule, "label": DQ_LABELS.get(rule, rule), "severity": fs[0]["severity"],
                     "n": len(projs), "excluded": any(f["excluded"] for f in fs), "projects": projs})
    affected = {f.get("project_number") for f in dq if f.get("project_number")}
    return {"kind": "calidad", "rows": rows, "proyectos_afectados": len(affected),
            "evaluados": c.get("signal", {}).get("records_in", 0),
            "nota": "Se evalúan proyectos activos (no cerrados ni cancelados).",
            "source_field": "Reglas DQ de Cronos sobre pm_project y project_status"}


HANDLERS = {"total": total, "categorias": by_category, "regiones": by_region, "programas": by_program,
            "portafolios": by_portfolio, "calidad": data_quality}


def answer(intent: str, cronos_out: dict, thanatos_out: dict | None) -> dict[str, Any]:
    return HANDLERS[intent](cronos_out, thanatos_out)


# ---------------------------------------------------------------------------------- estatus por ID (opción 7)
ID_RX = {"proyecto": r"\bPRJ\d{3,}\b", "programa": r"\bPRG\d{3,}\b", "portafolio": r"\bPFL\d{3,}\b"}


def _sum_ctl(reports: list[dict], key: str, field: str) -> int | None:
    vals = [r["control"][key][field] for r in reports if isinstance(r["control"].get(key), dict)]
    return sum(vals) if vals else None


def project_status(code: str, c: dict, t: dict | None) -> dict[str, Any]:
    code = code.upper()
    inv = next((p for p in c.get("inventory", []) if str(p.get("number", "")).upper() == code), None)
    if inv is None:
        return {"kind": "estatus", "level": "proyecto", "found": False, "code": code}
    rep = next((r for r in (t or {}).get("project_reports", []) if r["project_id"] == inv["id"]), None)
    hier = c.get("hierarchy", {})
    users = hier.get("user", {})
    prog = hier.get("program", {}).get(inv.get("program") or "", {})
    port = hier.get("portfolio", {}).get(inv.get("portfolio") or "", {})
    dq = [f for f in c.get("data_quality", []) if f.get("project_id") == inv["id"]]
    base = {"kind": "estatus", "level": "proyecto", "found": True, "code": code, "name": inv.get("name"),
            "state": inv.get("state"), "categoria": category(inv.get("state")), "region": inv.get("region"),
            "pm": (users.get(inv.get("project_manager") or "", {}) or {}).get("name"),
            "programa": prog.get("number"), "portafolio": port.get("number"),
            "dq": [{"rule": f["rule"], "label": DQ_LABELS.get(f["rule"], f["rule"]), "severity": f["severity"],
                    "excluded": f["excluded"]} for f in dq],
            "source_field": "pm_project, project_status y tablas de control"}
    if rep is None:
        why = ("cerrado o cancelado" if not _active(inv) else
               "excluido por calidad de datos" if any(f["excluded"] for f in dq) else "sin análisis")
        return {**base, "analyzed": False, "why": why}
    return {**base, "analyzed": True, "report": rep}


def rollup_status(level: str, code: str, c: dict, t: dict | None) -> dict[str, Any]:
    from .rollup import rollup  # import local para evitar ciclos

    code = code.upper()
    key, hkey = ("program", "program") if level == "programa" else ("portfolio", "portfolio")
    ent_id, ent = next(((i, e) for i, e in c.get("hierarchy", {}).get(hkey, {}).items()
                        if str(e.get("number", "")).upper() == code), (None, None))
    if ent_id is None:
        return {"kind": "estatus", "level": level, "found": False, "code": code}
    inv = [p for p in c.get("inventory", []) if p.get(key) == ent_id]
    reps = [r for r in (t or {}).get("project_reports", []) if r.get(key) == ent_id]
    users = c.get("hierarchy", {}).get("user", {})
    ru = rollup("Programa" if level == "programa" else "Portafolio", {**ent, "id": ent_id}, reps)
    pc = [(r["performance"]["schedule"].get("percent_complete"), r["performance"]["cost"].get("planned_cost"))
          for r in reps]
    w = [(p, b) for p, b in pc if p is not None and b]
    pcs = sorted(p for p, _ in pc if p is not None)
    perf = {
        "pc_ponderado": round(sum(p * b for p, b in w) / sum(b for _, b in w), 1) if w else None,
        "pc_mediana": pcs[len(pcs) // 2] if pcs else None, "pc_min": pcs[0] if pcs else None,
        "pc_max": pcs[-1] if pcs else None,
        "costo_plan": sum(r["performance"]["cost"].get("planned_cost") or 0 for r in reps),
        "costo_real": sum(r["performance"]["cost"].get("actual_cost") or 0 for r in reps),
        "esfuerzo_plan": sum(r["performance"]["resources"].get("planned_effort") or 0 for r in reps),
        "esfuerzo_real": sum(r["performance"]["resources"].get("actual_effort") or 0 for r in reps),
        "vencidos": sum(1 for r in reps if r["performance"]["schedule"].get("overdue")),
    }
    ctl = {"hitos_vencidos": _sum_ctl(reps, "milestones", "overdue"),
           "hitos_pendientes": _sum_ctl(reps, "milestones", "pending"),
           "riesgos_abiertos": _sum_ctl(reps, "risks", "open"), "riesgos_altos": _sum_ctl(reps, "risks", "open_high"),
           "issues_abiertos": _sum_ctl(reps, "issues", "open"), "decisiones_pend": _sum_ctl(reps, "decisions", "pending"),
           "acciones_pend": _sum_ctl(reps, "actions", "pending"), "acciones_vencidas": _sum_ctl(reps, "actions", "overdue"),
           "cambios_pend": _sum_ctl(reps, "change_requests", "pending")}
    projects = sorted(({"number": p["number"], "overall": next((r["health"]["overall"]["calculated"] for r in reps
                                                                if r["project_id"] == p["id"]), None),
                        "categoria": category(p.get("state"))} for p in inv), key=lambda x: x["number"])
    return {"kind": "estatus", "level": level, "found": True, "code": code, "name": ent.get("name"),
            "manager": (users.get(str(ent.get("manager")) or "", {}) or {}).get("name"),
            "total": len(inv), "activos": sum(1 for p in inv if _active(p)), "analizados": len(reps),
            "rollup": ru, "perf": perf, "ctl": ctl, "projects": projects,
            "source_field": f"pm_project.{'primary_program' if key == 'program' else 'primary_portfolio'} + KPIs por proyecto"}


def status_by_id(text: str, c: dict, t: dict | None) -> dict[str, Any]:
    import re

    for level, rx in ID_RX.items():
        m = re.search(rx, text or "", re.IGNORECASE)
        if m:
            code = m.group(0).upper()
            return project_status(code, c, t) if level == "proyecto" else rollup_status(level, code, c, t)
    return {"kind": "estatus", "level": None, "found": False, "code": None}
