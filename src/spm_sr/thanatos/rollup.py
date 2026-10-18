"""Roll-up a Programa/Portafolio sin promediar colores (distribución + peor caso + dispersión)."""
from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from .kpi_rules import DF, G, R, RANK, Y

HEALTH = ("overall", "schedule", "cost", "resources", "scope")


def _dist(colors: list[str]) -> dict[str, Any]:
    c = Counter(colors)
    n = len(colors) or 1
    return {k: {"n": c.get(k, 0), "pct": round(100 * c.get(k, 0) / n, 1)} for k in (G, Y, R, DF)}


def rollup(level: str, entity: dict, reports: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {"level": level, "id": entity.get("id"), "number": entity.get("number"),
                           "name": entity.get("name"), "manager": entity.get("manager"),
                           "n_projects": len(reports)}
    if not reports:
        out["note"] = "Sin proyectos válidos en el alcance"
        out["worst_overall"] = DF
        return out
    out["distribution"] = {h: _dist([r["health"][h]["calculated"] for r in reports]) for h in HEALTH}
    ranked = [r["health"]["overall"]["calculated"] for r in reports if r["health"]["overall"]["calculated"] in RANK]
    out["worst_overall"] = max(ranked, key=RANK.get) if ranked else DF
    reds = [r for r in reports if r["health"]["overall"]["calculated"] == R]
    out["red_projects"] = [{"number": r["number"], "name": r["name"]} for r in reds]
    total_budget = sum(r["performance"]["cost"].get("planned_cost") or 0 for r in reports)
    red_budget = sum(r["performance"]["cost"].get("planned_cost") or 0 for r in reds)
    out["budget_in_red_pct"] = round(100 * red_budget / total_budget, 1) if total_budget else None
    ev = sum(r["performance"]["cost"].get("earned_value") or 0 for r in reports if r["performance"]["cost"].get("cpi") is not None)
    ac = sum(r["performance"]["cost"].get("actual_cost") or 0 for r in reports if r["performance"]["cost"].get("cpi") is not None)
    cpis = [r["performance"]["cost"]["cpi"] for r in reports if r["performance"]["cost"].get("cpi") is not None]
    out["cpi"] = {"aggregate": round(ev / ac, 2) if ac else None,
                  "median": round(statistics.median(cpis), 2) if cpis else None,
                  "min": min(cpis) if cpis else None, "max": max(cpis) if cpis else None, "n": len(cpis)}
    out["optimism_discrepancies"] = sum(1 for r in reports if r["health"]["overall"]["comparison"] == "Optimismo")
    out["stale_reports"] = sum(1 for r in reports if r.get("sr_stale"))
    return out
