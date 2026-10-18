"""English labels for user-facing output (Telegram bot and web dashboard).

Internal values stay as Thanatos/Cronos produce them (Spanish keys such as "Verde", "En progreso", "Alta");
only the presentation layer translates. Data stored in the database (project names, regions, people) is shown
as stored.
"""
from __future__ import annotations

from typing import Any

HEALTH = {"Verde": "Green", "Amarillo": "Amber", "Rojo": "Red", "DATO_FALTANTE": "No data", None: "No data"}
CMP = {"Optimismo": "Optimistic", "Conservador": "Conservative", "Consistente": "Consistent",
       "No comparable": "Not comparable"}
CATEGORY = {"Abierto": "Open", "En progreso": "In progress", "En pausa": "On hold", "Cerrado": "Closed",
            "Cancelado": "Cancelled", "Otro": "Other"}
SEVERITY = {"Alta": "High", "Media": "Medium", "Baja": "Low"}
DQ = {"DQ-01": "Missing status report", "DQ-02": "Stale status report", "DQ-03": "Invalid % complete",
      "DQ-04": "Invalid or empty planned dates", "DQ-05": "Progress without actual start",
      "DQ-06": "Missing planned cost or effort", "DQ-07": "No PM or PM without email",
      "DQ-08": "Empty declared health", "DQ-09": "Duplicate record", "DQ-10": "Missing region"}
PLACEHOLDER = {"(sin región)": "(no region)", "(sin asignar)": "(unassigned)", "(vacío)": "(empty)"}
WHY = {"cerrado o cancelado": "closed or cancelled", "excluido por calidad de datos": "excluded by data quality",
       "sin análisis": "not analyzed"}
LEVEL = {"proyecto": "project", "programa": "program", "portafolio": "portfolio"}
SOURCE = {
    "pm_project (todos los registros del alcance)": "pm_project (all records in scope)",
    "pm_project.u_region (campo personalizado)": "pm_project.u_region (custom field)",
    "Reglas DQ de Cronos sobre pm_project y project_status": "Cronos DQ rules on pm_project and project_status",
    "pm_project, project_status y tablas de control": "pm_project, project_status and control tables",
}
NAMES = {"schedule": "Schedule", "cost": "Cost", "resources": "Resources", "scope": "Scope"}


def h(v: Any) -> str:
    return HEALTH.get(v, str(v))


def cat(v: Any) -> str:
    return CATEGORY.get(v, str(v))


def sev(v: Any) -> str:
    return SEVERITY.get(v, str(v))


def cmp(v: Any) -> str:
    return CMP.get(v, str(v))


def dq(rule: str, fallback: str | None = None) -> str:
    return DQ.get(rule, fallback or rule)


def ph(v: Any) -> str:
    return PLACEHOLDER.get(v, str(v))


def source(v: str) -> str:
    v = SOURCE.get(v, v)
    return v.replace(" + KPIs por proyecto", " + per-project KPIs")


def alerts(rep: dict[str, Any], n: int = 4) -> list[str]:
    """Same rules as Thanatos.top_alerts, phrased in English."""
    out: list[str] = []
    hh, ctl = rep["health"], rep.get("control", {})
    out += [f"{lbl} is Red" for k, lbl in NAMES.items() if hh[k]["calculated"] == "Rojo"]
    if hh["overall"]["comparison"] == "Optimismo":
        out.append(f"Overall declared {h(hh['overall']['declared'])} vs calculated {h(hh['overall']['calculated'])}")
    if isinstance(ctl.get("milestones"), dict) and ctl["milestones"].get("overdue"):
        out.append(f"{ctl['milestones']['overdue']} overdue milestone(s)")
    if isinstance(ctl.get("risks"), dict) and ctl["risks"].get("open_high"):
        out.append(f"{ctl['risks']['open_high']} high open risk(s)")
    if rep.get("sr_stale"):
        out.append("Stale status report")
    out += [f"{lbl} is Amber" for k, lbl in NAMES.items() if hh[k]["calculated"] == "Amarillo"]
    return out[:n]
