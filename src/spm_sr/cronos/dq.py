"""Reglas de calidad mínima DQ-01..DQ-10 (docs/plan/04). DQ-10 aplica solo si existe el campo personalizado u_region."""
from __future__ import annotations

import datetime as dt
from typing import Any

from ..core.util import norm

HEALTH_MAP = {
    "green": "Verde", "verde": "Verde", "g": "Verde", "1": "Verde",
    "yellow": "Amarillo", "amarillo": "Amarillo", "amber": "Amarillo", "y": "Amarillo", "2": "Amarillo",
    "red": "Rojo", "rojo": "Rojo", "r": "Rojo", "3": "Rojo",
}
HEALTH_FIELDS = ("overall", "schedule", "cost", "resources", "scope")


def normalize_health(v: Any) -> str | None:
    return HEALTH_MAP.get(norm(v))


def _f(rule, sev, p, field=None, value=None, excluded=False, msg=""):
    return {"rule": rule, "severity": sev, "project_number": p.get("number"), "project_id": p.get("id"),
            "field": field, "value": value, "excluded": excluded, "message": msg}


def dedupe(projects: list[dict]) -> tuple[list[dict], list[dict]]:
    """DQ-09: conserva el registro con más datos por sys_id."""
    seen: dict[str, dict] = {}
    findings = []
    for p in projects:
        pid = p.get("id")
        if pid in seen:
            findings.append(_f("DQ-09", "Alta", p, "id", pid, False, "Proyecto duplicado; se conserva un solo registro"))
            continue
        seen[pid] = p
    return list(seen.values()), findings


def run_dq(projects: list[dict], latest_sr: dict[str, dict], users: dict[str, dict], as_of: dt.date,
           stale_days: int) -> tuple[list[dict], list[dict]]:
    valid, findings = [], []
    for p in projects:
        excluded = False
        pc = p.get("percent_complete")
        if pc is None or pc < 0 or pc > 100:
            findings.append(_f("DQ-03", "Alta", p, "percent_complete", pc, True, "% de avance fuera de 0-100 o nulo"))
            excluded = True
        ps, pe = p.get("planned_start"), p.get("planned_end")
        if ps is None or pe is None:
            findings.append(_f("DQ-04", "Alta", p, "planned_start/planned_end", None, True, "Fechas planeadas nulas"))
            excluded = True
        elif pe < ps:
            findings.append(_f("DQ-04", "Alta", p, "planned_end", pe.isoformat(), True, "Fin planeado anterior al inicio"))
            excluded = True
        if excluded:
            continue

        sr = latest_sr.get(p["id"])
        if sr is None:
            findings.append(_f("DQ-01", "Alta", p, "status_report", None, False, "Proyecto sin Status Report"))
        else:
            as_on = sr.get("as_on")
            if as_on is None or (as_of - as_on).days > stale_days:
                age = None if as_on is None else (as_of - as_on).days
                findings.append(_f("DQ-02", "Media", p, "as_on", age, False,
                                   f"Status Report desactualizado (> {stale_days} días)"))
            for h in HEALTH_FIELDS:
                if sr.get(h) is None:
                    findings.append(_f("DQ-08", "Media", p, h, sr.get(f"{h}_raw"), False,
                                       "Semáforo declarado vacío o fuera de catálogo"))
        if pc and pc > 0 and p.get("actual_start") is None:
            findings.append(_f("DQ-05", "Baja", p, "actual_start", None, False, "Avance > 0 sin fecha de inicio real"))
        if not p.get("planned_cost"):
            findings.append(_f("DQ-06", "Media", p, "planned_cost", p.get("planned_cost"), False,
                               "Costo planeado nulo o 0"))
        if not p.get("planned_effort"):
            findings.append(_f("DQ-06", "Media", p, "planned_effort", p.get("planned_effort"), False,
                               "Esfuerzo planeado nulo o 0"))
        if p.get("_region_available") and not p.get("region"):
            findings.append(_f("DQ-10", "Baja", p, "region", None, False, "Proyecto sin región (u_region)"))
        pm = users.get(p.get("project_manager") or "")
        if not p.get("project_manager") or pm is None or not pm.get("email"):
            findings.append(_f("DQ-07", "Alta", p, "project_manager", p.get("project_manager"), False,
                               "Proyecto sin PM o PM sin email; se escala al PgM"))
        valid.append(p)
    return valid, findings
