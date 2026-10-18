"""Exporta los KPIs para el dashboard web (JSON estático). Reutiliza Cronos (lectura + DQ) y Thanatos (KPIs).

El dashboard es público: el JSON NO lleva credenciales, correos ni chat_id; solo datos de proyectos
(sintéticos en esta demo) y nombres de responsables.

Uso: python scripts/export_dashboard_data.py --out dashboard/public/data/kpis.json
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spm_sr.core.config import load_all  # noqa: E402
from spm_sr.core.state import RunState, Signal  # noqa: E402
from spm_sr.core.util import json_default  # noqa: E402
from spm_sr.cronos import Cronos  # noqa: E402
from spm_sr.thanatos import Thanatos  # noqa: E402
from spm_sr.thanatos.queries import DQ_LABELS, category  # noqa: E402
from spm_sr.zeus import i18n  # noqa: E402

HEALTH = ("overall", "schedule", "cost", "resources", "scope")
EN_HEALTH, EN_CMP, EN_CAT, EN_DQ, EN_SEV = i18n.HEALTH, i18n.CMP, i18n.CATEGORY, i18n.DQ, i18n.SEVERITY


def en_alerts(rec: dict) -> list[str]:
    """Alertas en inglés derivadas de los KPIs (mismas reglas que el bot)."""
    out, h = [], rec["health"]
    names = {"schedule": "Schedule", "cost": "Cost", "resources": "Resources", "scope": "Scope"}
    out += [f"{n} is Red" for k, n in names.items() if h[k]["calc"] == "Red"]
    if h["overall"]["cmp"] == "Optimistic":
        out.append(f"Overall declared {h['overall']['declared']} vs calculated {h['overall']['calc']}")
    if rec.get("milestonesOverdue"):
        out.append(f"{rec['milestonesOverdue']} overdue milestone(s)")
    if rec.get("risksHigh"):
        out.append(f"{rec['risksHigh']} high open risk(s)")
    if rec.get("srStale"):
        out.append("Stale status report")
    out += [f"{n} is Amber" for k, n in names.items() if h[k]["calc"] == "Amber"]
    return out[:4]


def _ctl(ctl: dict, key: str, field: str):
    v = ctl.get(key)
    return v.get(field) if isinstance(v, dict) else None


def build(as_of: dt.date | None = None) -> dict:
    settings, schema_map, thresholds, _ = load_all()
    settings = copy.deepcopy(settings)
    settings["llm"]["enabled"] = False
    tz = ZoneInfo("America/Mexico_City")
    as_of = as_of or dt.datetime.now(tz).date()
    state = RunState(run_date=as_of, scope=["all"], dry_run=True)
    c = Cronos(settings, schema_map).run(state)
    if c["signal"]["status"] == Signal.FAILED.value:
        raise SystemExit("Cronos FAILED: " + "; ".join(e.message for e in state.errors))
    state.cronos = c
    t = Thanatos(settings, schema_map, thresholds).run(state)
    hier = c["hierarchy"]
    users, progs, ports = hier.get("user", {}), hier.get("program", {}), hier.get("portfolio", {})
    reps = {r["project_id"]: r for r in t["project_reports"]}
    dq_by: dict[str, list] = {}
    for f in c["data_quality"]:
        dq_by.setdefault(f.get("project_id"), []).append(f["rule"])

    projects = []
    for p in c["inventory"]:
        r = reps.get(p["id"])
        prog, port = progs.get(p.get("program") or "", {}), ports.get(p.get("portfolio") or "", {})
        cat = category(p.get("state"))
        rec = {
            "id": p["number"], "name": p.get("name"), "state": p.get("state"), "category": EN_CAT[cat],
            "active": cat not in ("Cerrado", "Cancelado"), "region": p.get("region") or "No region",
            "program": prog.get("number") or "Unassigned", "programName": prog.get("name"),
            "portfolio": port.get("number") or "Unassigned", "portfolioName": port.get("name"),
            "pm": (users.get(p.get("project_manager") or "", {}) or {}).get("name") or "No PM",
            "dq": sorted(set(dq_by.get(p["id"], []))), "analyzed": r is not None,
        }
        if r:
            h, perf, ctl = r["health"], r["performance"], r["control"]
            s, co, rs, d = perf["schedule"], perf["cost"], perf["resources"], perf["dates"]
            rec.update({
                "health": {k: {"calc": EN_HEALTH.get(h[k]["calculated"], "No data"),
                               "declared": EN_HEALTH.get(h[k]["declared"], "No data"),
                               "cmp": EN_CMP.get(h[k]["comparison"], h[k]["comparison"])} for k in HEALTH},
                "pctComplete": s.get("percent_complete"), "pctExpected": s.get("expected_pct"),
                "gapPp": s.get("gap_pp"), "overdue": bool(s.get("overdue")), "endVarianceDays": s.get("end_variance_days"),
                "plannedStart": d.get("planned_start"), "plannedEnd": d.get("planned_end"),
                "actualStart": d.get("actual_start"), "actualEnd": d.get("actual_end"),
                "plannedCost": co.get("planned_cost"), "actualCost": co.get("actual_cost"),
                "earnedValue": co.get("earned_value"), "cpi": co.get("cpi"), "budgetUsedPct": co.get("consumption_pct"),
                "plannedEffort": rs.get("planned_effort"), "actualEffort": rs.get("actual_effort"),
                "effortIndex": rs.get("effort_index"),
                "allocatedHours": (rs.get("allocation") or {}).get("allocated_hours"),
                "allocActualHours": (rs.get("allocation") or {}).get("actual_hours"),
                "milestonesTotal": _ctl(ctl, "milestones", "total"), "milestonesDone": _ctl(ctl, "milestones", "completed"),
                "milestonesOverdue": _ctl(ctl, "milestones", "overdue"),
                "risksOpen": _ctl(ctl, "risks", "open"), "risksHigh": _ctl(ctl, "risks", "open_high"),
                "issuesOpen": _ctl(ctl, "issues", "open"), "decisionsPending": _ctl(ctl, "decisions", "pending"),
                "actionsPending": _ctl(ctl, "actions", "pending"), "actionsOverdue": _ctl(ctl, "actions", "overdue"),
                "changesPending": _ctl(ctl, "change_requests", "pending"),
                "srAsOf": r.get("sr_as_on"), "srStale": bool(r.get("sr_stale")), "srMissing": bool(r.get("sr_missing")),
            })
            rec["alerts"] = en_alerts(rec)
        projects.append(rec)
    return {
        "generatedAt": dt.datetime.now(tz).isoformat(timespec="minutes"), "asOf": as_of.isoformat(),
        "source": "ServiceNow SPM replica (synthetic demo data) · Cronos → Thanatos",
        "dqRules": {k: {"label": EN_DQ[k], "severity": EN_SEV.get(sev, sev)} for k, sev in
                    {"DQ-01": "Alta", "DQ-02": "Media", "DQ-03": "Alta", "DQ-04": "Alta", "DQ-05": "Baja",
                     "DQ-06": "Media", "DQ-07": "Alta", "DQ-08": "Media", "DQ-09": "Alta", "DQ-10": "Baja"}.items()
                    if k in DQ_LABELS},
        "thresholds": thresholds,
        "counts": {"programs": len(progs), "portfolios": len(ports)},
        "projects": projects,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dashboard" / "public" / "data" / "kpis.json"))
    ap.add_argument("--as-of")
    a = ap.parse_args()
    data = build(dt.date.fromisoformat(a.as_of) if a.as_of else None)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, default=json_default, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = len(data["projects"])
    print(f"{n} proyectos exportados ({sum(p['analyzed'] for p in data['projects'])} analizados) -> {out} "
          f"({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
