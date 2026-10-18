"""Indicadores de control KPIs 14-19 (conteos, no semáforos)."""
from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any

from ..core.util import norm, parse_date

DF = "DATO_FALTANTE"


def _open(r: dict, closed: set[str]) -> bool:
    return norm(r.get("state")) not in closed


def control_kpis(aux: dict[str, list[dict]], available: dict[str, bool], as_of: dt.date, states: dict,
                 th: dict) -> dict[str, Any]:
    closed = {norm(s) for s in states.get("closed", [])}
    high = {norm(s) for s in states.get("high_values", [])}
    pend_appr = {norm(s) for s in states.get("pending_approval", [])}
    pend_chg = {norm(s) for s in states.get("pending_change", [])}
    out: dict[str, Any] = {}

    def due_passed(r, col="due"):
        d = parse_date(r.get(col))
        return d is not None and d < as_of

    if available.get("milestones"):
        ms = aux.get("milestones", [])
        done = [m for m in ms if not _open(m, closed) or parse_date(m.get("done_on"))]
        overdue = [m for m in ms if m not in done and due_passed(m)]
        out["milestones"] = {"total": len(ms), "completed": len(done), "pending": len(ms) - len(done),
                             "overdue": len(overdue), "overdue_names": [m.get("name") for m in overdue][:5],
                             "source_field": "pm_project_task(milestone)"}
    else:
        out["milestones"] = DF

    if available.get("risks"):
        rk = [r for r in aux.get("risks", []) if _open(r, closed)]
        out["risks"] = {"open": len(rk),
                        "open_high": sum(1 for r in rk if norm(r.get("probability")) in high and norm(r.get("impact")) in high),
                        "overdue": sum(1 for r in rk if due_passed(r)),
                        "no_owner": sum(1 for r in rk if not r.get("owner")), "source_field": "risk"}
    else:
        out["risks"] = DF

    if available.get("issues"):
        isu = [r for r in aux.get("issues", []) if _open(r, closed)]
        out["issues"] = {"open": len(isu), "by_priority": dict(Counter(str(r.get("priority")) for r in isu)),
                         "no_owner": sum(1 for r in isu if not r.get("owner")), "source_field": "issue"}
    else:
        out["issues"] = DF

    if available.get("decisions"):
        dec = [r for r in aux.get("decisions", []) if _open(r, closed)]
        ages = [(as_of - d).days for d in (parse_date(r.get("created")) for r in dec) if d]
        out["decisions"] = {"pending": len(dec), "max_age_days": max(ages) if ages else None,
                            "source_field": "dmn_decision"}
    else:
        out["decisions"] = DF

    if available.get("actions"):
        act = [r for r in aux.get("actions", []) if _open(r, closed)]
        out["actions"] = {"pending": len(act),
                          "pending_approval": sum(1 for r in act if norm(r.get("approval")) in pend_appr),
                          "overdue": sum(1 for r in act if due_passed(r)), "source_field": "project_action"}
    else:
        out["actions"] = DF

    if available.get("change_requests"):
        cr = aux.get("change_requests", [])
        pending = [r for r in cr if norm(r.get("state")) in pend_chg]
        old = [r for r in pending if (d := parse_date(r.get("created"))) and (as_of - d).days > th["cr_pending_days"]]
        out["change_requests"] = {"total": len(cr), "by_state": dict(Counter(str(r.get("state")) for r in cr)),
                                  "pending": len(pending), "pending_over_days": len(old),
                                  "threshold_days": th["cr_pending_days"], "source_field": "project_change_request"}
    else:
        out["change_requests"] = DF
    return out
