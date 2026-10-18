"""Agente 2 "Thanatos" — Analista. Calcula KPIs 1-19, compara declarado vs calculado, roll-up y narrativa."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from ..cerbero import get_cerbero
from ..core.state import RunState, Signal, make_signal
from ..core.util import norm, now_iso
from . import kpi_rules as K
from .control import control_kpis
from .narrative import Narrator, template_project, template_rollup, top_alerts
from .rollup import rollup

log = logging.getLogger("spm_sr.thanatos")
AUX_KEYS = ("milestones", "risks", "issues", "decisions", "actions", "change_requests", "resources")


class Thanatos:
    name = "thanatos"

    def __init__(self, settings: dict, schema_map: dict, thresholds: dict):
        self.settings = settings
        self.states = schema_map.get("states", {})
        self.th = thresholds

    def _project_report(self, p: dict, sr: dict | None, aux: dict, available: dict, as_of, stale_ids: set) -> dict:
        pid = p["id"]
        a = {k: aux.get(k, {}).get(pid, []) for k in AUX_KEYS}
        sch = K.schedule(p, as_of, self.th["schedule"])
        cst = K.cost(p, self.th["cost"])
        res = K.resources(p, a["resources"] if available.get("resources") else None, self.th["resources"])
        pend = {norm(s) for s in self.states.get("pending_change", [])}
        scp = K.scope(a["change_requests"], bool(available.get("change_requests")), self.th["scope"], pend)
        comps = {"schedule": sch["color"], "cost": cst["color"], "resources": res["color"], "scope": scp["color"]}
        ovr = K.overall(comps)
        declared = sr or {}
        health = {}
        for key, calc in (("overall", ovr["color"]), *comps.items()):
            dec = declared.get(key)
            health[key] = {"calculated": calc, "declared": dec, "comparison": K.compare(dec, calc),
                           "source_field": f"project_status.{key}" if key != "overall" else "project_status.overall_health"}
        health["overall"]["incomplete_evidence"] = ovr["incomplete_evidence"]
        rep = {
            "project_id": pid, "number": p["number"], "name": p.get("name"),
            "project_manager": p.get("project_manager"), "program": p.get("program"), "portfolio": p.get("portfolio"),
            "sr_as_on": declared.get("as_on"), "sr_stale": pid in stale_ids, "sr_missing": sr is None,
            "health": health,
            "performance": {
                "schedule": sch, "cost": cst, "resources": res, "scope": scp,
                "dates": {"planned_start": p.get("planned_start"), "planned_end": p.get("planned_end"),
                          "actual_start": p.get("actual_start"), "actual_end": p.get("actual_end"),
                          "source_field": "pm_project.start_date/end_date/work_start/work_end"},
            },
            "control": control_kpis(a, available, as_of, self.states, self.th["control"]),
        }
        rep["alerts"] = top_alerts(rep)
        return rep

    def _recipients(self, reports: list[dict], rollups: list[dict], hier: dict) -> list[dict]:
        users = hier.get("user", {})
        programs = hier.get("program", {})
        plan: dict[str, dict] = {}

        def entry(uid: str) -> dict:
            u = users.get(uid, {})
            return plan.setdefault(uid, {"user_id": uid, "name": u.get("name"), "email": u.get("email"),
                                         "roles": [], "projects": [], "programs": [], "portfolios": [],
                                         "escalations": []})

        for r in reports:
            pm = r.get("project_manager")
            if pm and users.get(pm, {}).get("email"):
                e = entry(pm)
                "PM" in e["roles"] or e["roles"].append("PM")
                e["projects"].append(r["project_id"])
            else:
                pgm = programs.get(r.get("program") or "", {}).get("manager")
                if pgm:
                    e = entry(str(pgm))
                    e["escalations"].append(r["project_id"])
        for ru in rollups:
            mgr = ru.get("manager")
            if not mgr:
                continue
            e = entry(str(mgr))
            role = "PgM" if ru["level"] == "Programa" else "PfM"
            role in e["roles"] or e["roles"].append(role)
            e["programs" if role == "PgM" else "portfolios"].append(ru["id"])
        return [e for e in plan.values() if e["projects"] or e["programs"] or e["portfolios"] or e["escalations"]]

    def run(self, state: RunState) -> dict[str, Any]:
        started = now_iso()
        c = state.cronos or {}
        if not c or c.get("signal", {}).get("status") == Signal.FAILED.value:
            state.add_error("E-CALC-00", self.name, "Entrada de Cronos inexistente o FAILED", blocking=True)
            return {"signal": make_signal(Signal.FAILED, started), "project_reports": [], "rollups": [],
                    "quality_summary": {}, "recipients_plan": []}
        as_of = state.run_date
        avail_src = c.get("source_availability", {})
        available = {k: bool(avail_src.get(k, {}).get("exists")) and not avail_src.get(k, {}).get("read_error")
                     for k in AUX_KEYS}
        stale_ids = {f.get("project_id") for f in c.get("data_quality", []) if f["rule"] == "DQ-02"}
        reports, calc_errors = [], 0
        for p in c["projects"]:
            try:
                reports.append(self._project_report(p, c["status_reports"].get(p["id"]), c.get("aux", {}),
                                                    available, as_of, stale_ids))
            except Exception as e:  # noqa: BLE001 - un proyecto no tumba la corrida
                calc_errors += 1
                state.add_error("E-CALC-01", self.name, f"Error calculando {p.get('number')}: {e}",
                                severity="Media", project=p.get("number"))

        hier = c.get("hierarchy", {})
        by_prog, by_port = defaultdict(list), defaultdict(list)
        for r in reports:
            if r.get("program"):
                by_prog[r["program"]].append(r)
            if r.get("portfolio"):
                by_port[r["portfolio"]].append(r)
        rollups = []
        for pid, reps in by_prog.items():
            ent = dict(hier.get("program", {}).get(pid, {"id": pid}))
            rollups.append(rollup("Programa", {**ent, "id": pid}, reps))
        for pid, reps in by_port.items():
            ent = dict(hier.get("portfolio", {}).get(pid, {"id": pid}))
            rollups.append(rollup("Portafolio", {**ent, "id": pid}, reps))

        narrator = Narrator(self.settings)
        guard = get_cerbero(self.settings)
        flagged = set((c.get("security") or {}).get("flagged_records", []))

        def _narrate(facts: dict, fallback: str, subject: str) -> dict:
            ok = not narrator.enabled or guard.llm_input(facts, flagged, subject)   # Cerbero (gate "llm_in")
            return narrator.narrate(facts, fallback, guard=guard, subject=subject, allow_llm=ok)

        # Primero los roll-ups (su narrativa es la que se envía por Telegram a PgM/PfM): portafolios y luego
        # programas, de mayor a menor número de proyectos; el presupuesto de llamadas restante va a proyectos.
        order = sorted(rollups, key=lambda ru: (ru["level"] != "Portafolio", -(ru.get("n_projects") or 0)))
        for ru in order:
            ru["narrative"] = _narrate(ru, template_rollup(ru), f"{ru['level']} {ru.get('number')}")
        for r in reports:
            facts = {k: r[k] for k in ("number", "name", "health", "performance", "control", "alerts", "sr_stale")}
            r["narrative"] = _narrate(facts, template_project(r), str(r.get("number")))
        for f in narrator.failures:
            code = f.split()[0].rstrip(":") if f.startswith(("E-LLM-", "E-SEC-")) else "E-LLM-01"
            state.add_error(code, self.name, f, severity="Baja")

        dq = c.get("data_quality", [])
        quality = {"findings": len(dq), "excluded": sum(1 for f in dq if f["excluded"]),
                   "by_rule": {r: sum(1 for f in dq if f["rule"] == r) for r in sorted({f["rule"] for f in dq})},
                   "excluded_projects": [f["project_number"] for f in dq if f["excluded"]],
                   "cronos_status": c["signal"]["status"]}

        if not reports:
            status = Signal.FAILED
        elif calc_errors or narrator.failures or c["signal"]["status"] == Signal.PARTIAL.value:
            status = Signal.PARTIAL
        else:
            status = Signal.COMPLETED
        out = {"signal": make_signal(status, started, records_in=len(c["projects"]), records_ok=len(reports),
                                     records_excluded=calc_errors),
               "project_reports": reports, "rollups": rollups, "quality_summary": quality,
               "recipients_plan": self._recipients(reports, rollups, hier)}
        log.info("Thanatos %s: %s reportes, %s roll-ups", status.value, len(reports), len(rollups))
        return out
