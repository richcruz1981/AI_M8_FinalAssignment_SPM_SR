"""Reporte de Fallas de la corrida (docs/plan/07): markdown + json."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .state import RunState
from .util import write_json

SEV = {"Alta": "High", "Media": "Medium", "Baja": "Low"}
ACTIONS = {
    "E-CONN-01": "Check that the replica is up, reachable from this machine/runner, and that DB_URL is correct.",
    "E-CONN-02": "Check the DB user/password in the secrets / .env.",
    "E-CONN-03": "Check the DB_URL format and install the engine driver (psycopg, pymysql, pyodbc).",
    "E-SCHEMA-01": "The core table is missing or lacks columns: adjust config/schema_map.yaml.",
    "E-SCHEMA-02": "Auxiliary table missing: related KPIs are reported as no data.",
    "E-SCHEMA-03": "Optional columns missing: review config/schema_map.yaml.",
    "E-READ-01": "Retry; check SELECT permissions and locks on the replica.",
    "E-DATA-00": "No valid projects: review the scope (SCOPE) and DQ findings.",
    "E-CALC-00": "Thanatos received no valid data from Cronos.",
    "E-CALC-01": "Review the project indicated; the rest of the run continued.",
    "E-LLM-01": "The deterministic template was used; check ANTHROPIC_API_KEY / model.",
    "E-LLM-02": "The LLM cited figures not present in the data; the deterministic template was used (control working).",
    "E-LLM-03": "The LLM returned empty text; the deterministic template was used.",
    "E-SEND-01": "Check TELEGRAM_TOKEN, that the recipient sent /start to the bot, and connectivity.",
    "E-SEND-02": "Register the recipient chat_id (RECIPIENTS_YAML; /start in the bot) or use REDIRECT_TELEGRAM_CHAT_ID.",
    "E-SEND-03": "Set the TELEGRAM_TOKEN secret.",
}


def build_failure_report(state: RunState) -> dict[str, Any]:
    c = state.cronos or {}
    dq = c.get("data_quality", [])
    t = state.thanatos or {}
    df_kpis: Counter = Counter()
    for r in t.get("project_reports", []):
        for k, v in r["health"].items():
            if v["calculated"] == "DATO_FALTANTE":
                df_kpis[k] += 1
        for k, v in r["control"].items():
            if v == "DATO_FALTANTE":
                df_kpis[k] += 1
    return {
        "run_id": state.run_id, "run_date": state.run_date.isoformat(), "final_status": state.final_status().value,
        "signals": {a: (getattr(state, a) or {}).get("signal", {}).get("status") for a in ("cronos", "thanatos", "zeus")},
        "errors": [vars(e) for e in state.errors],
        "source_availability": c.get("source_availability", {}),
        "data_quality": {"by_rule": dict(Counter(f["rule"] for f in dq)),
                         "top": [f for f in dq if f["severity"] == "Alta"][:10]},
        "impact_dato_faltante": dict(df_kpis),
        "suggested_actions": {e.code: ACTIONS.get(e.code, "Review the run log") for e in state.errors},
    }


def failure_markdown(rep: dict[str, Any]) -> str:
    L = [f"# Failure Report · {rep['run_date']}", "",
         f"- run_id: `{rep['run_id']}`", f"- Final status: **{rep['final_status']}**",
         f"- Signals: Cronos={rep['signals']['cronos']} · Thanatos={rep['signals']['thanatos']} · Zeus={rep['signals']['zeus']}",
         "", "## Errors", "| Code | Agent | Severity | Blocking | Message |", "|---|---|---|---|---|"]
    for e in rep["errors"]:
        L.append(f"| {e['code']} | {e['agent']} | {SEV.get(e['severity'], e['severity'])} | {'Yes' if e['blocking'] else 'No'} | {e['message']} |")
    if not rep["errors"]:
        L.append("| — | — | — | — | No errors |")
    L += ["", "## Source availability", "| Source | Table | Exists | Rows |", "|---|---|---|---|"]
    for k, v in rep["source_availability"].items():
        L.append(f"| {k} | {v.get('table')} | {'Yes' if v.get('exists') else 'No'} | {v.get('rows', 0)} |")
    L += ["", "## Data quality", "| Rule | Findings |", "|---|---|"]
    for k, v in sorted(rep["data_quality"]["by_rule"].items()):
        L.append(f"| {k} | {v} |")
    if rep["data_quality"]["top"]:
        L += ["", "Top high-severity findings:", "| Rule | Project | Field | Value | Excluded |", "|---|---|---|---|---|"]
        for f in rep["data_quality"]["top"]:
            L.append(f"| {f['rule']} | {f['project_number']} | {f['field']} | {f['value']} | {'Yes' if f['excluded'] else 'No'} |")
    L += ["", "## Impact (KPIs with no data, project count)"]
    L += [f"- {k}: {v}" for k, v in rep["impact_dato_faltante"].items()] or ["- None"]
    L += ["", "## Suggested actions"]
    L += [f"- **{k}**: {v}" for k, v in rep["suggested_actions"].items()] or ["- None"]
    return "\n".join(L) + "\n"


def write_failure_report(state: RunState, run_dir: Path) -> str:
    rep = build_failure_report(state)
    md = failure_markdown(rep)
    write_json(run_dir / "failure_report.json", rep)
    (run_dir / "failure_report.md").write_text(md, encoding="utf-8")
    return md
