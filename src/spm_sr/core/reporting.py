"""Reporte de Fallas de la corrida (docs/plan/07): markdown + json."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .state import RunState
from .util import write_json

ACTIONS = {
    "E-CONN-01": "Verificar que la réplica esté encendida, accesible desde este equipo/runner y que DB_URL sea correcta.",
    "E-CONN-02": "Revisar usuario/contraseña de la BD en los secrets / .env.",
    "E-CONN-03": "Revisar formato de DB_URL e instalar el driver del motor (psycopg2, pymysql, pyodbc).",
    "E-SCHEMA-01": "La tabla núcleo no existe o le faltan columnas: ajustar config/schema_map.yaml.",
    "E-SCHEMA-02": "Tabla auxiliar ausente: los KPIs asociados salen como DATO_FALTANTE.",
    "E-SCHEMA-03": "Columnas opcionales ausentes: revisar config/schema_map.yaml.",
    "E-READ-01": "Reintentar; revisar permisos SELECT y bloqueos en la réplica.",
    "E-DATA-00": "Ningún proyecto válido: revisar alcance (SCOPE) y hallazgos DQ.",
    "E-CALC-00": "Thanatos no recibió datos válidos de Cronos.",
    "E-CALC-01": "Revisar el proyecto indicado; el resto de la corrida continuó.",
    "E-LLM-01": "Se usó la plantilla determinista; revisar ANTHROPIC_API_KEY / modelo.",
    "E-LLM-02": "El LLM citó cifras que no están en los datos; se usó la plantilla determinista (control funcionando).",
    "E-LLM-03": "El LLM devolvió texto vacío; se usó la plantilla determinista.",
    "E-SEND-01": "Revisar TELEGRAM_TOKEN, que el destinatario haya enviado /start al bot y la conectividad.",
    "E-SEND-02": "Registrar el chat_id del destinatario (RECIPIENTS_YAML; /start en el bot) o usar REDIRECT_TELEGRAM_CHAT_ID.",
    "E-SEND-03": "Configurar el secret TELEGRAM_TOKEN.",
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
        "suggested_actions": {e.code: ACTIONS.get(e.code, "Revisar log de la corrida") for e in state.errors},
    }


def failure_markdown(rep: dict[str, Any]) -> str:
    L = [f"# Reporte de Fallas · {rep['run_date']}", "",
         f"- run_id: `{rep['run_id']}`", f"- Estado final: **{rep['final_status']}**",
         f"- Señales: Cronos={rep['signals']['cronos']} · Thanatos={rep['signals']['thanatos']} · Zeus={rep['signals']['zeus']}",
         "", "## Errores", "| Código | Agente | Severidad | Bloqueante | Mensaje |", "|---|---|---|---|---|"]
    for e in rep["errors"]:
        L.append(f"| {e['code']} | {e['agent']} | {e['severity']} | {'Sí' if e['blocking'] else 'No'} | {e['message']} |")
    if not rep["errors"]:
        L.append("| — | — | — | — | Sin errores |")
    L += ["", "## Disponibilidad de fuentes", "| Fuente | Tabla | Existe | Filas |", "|---|---|---|---|"]
    for k, v in rep["source_availability"].items():
        L.append(f"| {k} | {v.get('table')} | {'Sí' if v.get('exists') else 'No'} | {v.get('rows', 0)} |")
    L += ["", "## Calidad de datos", "| Regla | Hallazgos |", "|---|---|"]
    for k, v in sorted(rep["data_quality"]["by_rule"].items()):
        L.append(f"| {k} | {v} |")
    if rep["data_quality"]["top"]:
        L += ["", "Top hallazgos de severidad Alta:", "| Regla | Proyecto | Campo | Valor | Excluido |", "|---|---|---|---|---|"]
        for f in rep["data_quality"]["top"]:
            L.append(f"| {f['rule']} | {f['project_number']} | {f['field']} | {f['value']} | {'Sí' if f['excluded'] else 'No'} |")
    L += ["", "## Impacto (KPIs en DATO_FALTANTE, conteo de proyectos)"]
    L += [f"- {k}: {v}" for k, v in rep["impact_dato_faltante"].items()] or ["- Ninguno"]
    L += ["", "## Acciones sugeridas"]
    L += [f"- **{k}**: {v}" for k, v in rep["suggested_actions"].items()] or ["- Ninguna"]
    return "\n".join(L) + "\n"


def write_failure_report(state: RunState, run_dir: Path) -> str:
    rep = build_failure_report(state)
    md = failure_markdown(rep)
    write_json(run_dir / "failure_report.json", rep)
    (run_dir / "failure_report.md").write_text(md, encoding="utf-8")
    return md
