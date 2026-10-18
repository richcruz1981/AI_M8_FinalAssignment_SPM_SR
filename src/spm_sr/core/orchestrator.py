"""Orquestador M0: Cronos -> Thanatos -> Zeus con aristas condicionales (docs/plan/01).

Se implementó un orquestador propio (alternativa listada en el plan) en lugar de LangGraph para minimizar
dependencias; mantiene la misma semántica: estado compartido tipado + transición según la señal de cada agente.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from ..contracts import validate_contract
from ..cronos import Cronos
from ..thanatos import Thanatos
from ..zeus import Zeus
from .logging_setup import setup_logging
from .reporting import build_failure_report, failure_markdown, write_failure_report
from .state import RunState, Signal
from .util import write_json

log = logging.getLogger("spm_sr.orchestrator")


def _check(state: RunState, contract: str, data: dict, agent: str) -> bool:
    try:
        validate_contract(contract, data)
        return True
    except ValidationError as e:
        state.add_error("E-CONTRACT-01", agent, f"Salida viola contrato {contract}", blocking=True,
                        detail=str(e)[:500])
        data["signal"]["status"] = Signal.FAILED.value
        return False


def run_pipeline(settings: dict, schema_map: dict, thresholds: dict, recipients: dict, as_of: dt.date,
                 scope: list[str] | None = None, dry_run: bool | None = None, agents: list[str] | None = None,
                 sleep: Callable[[float], None] = time.sleep, zeus: Zeus | None = None) -> RunState:
    dry = settings["notifications"].get("dry_run", True) if dry_run is None else dry_run
    state = RunState(run_date=as_of, scope=scope or settings.get("scope", ["all"]), dry_run=dry)
    run_dir = Path(settings["runs_dir"]) / as_of.isoformat()
    setup_logging(run_dir)
    log.info("Inicio corrida %s · fecha %s · alcance %s · dry_run=%s", state.run_id, as_of, state.scope, dry)
    agents = agents or ["cronos", "thanatos", "zeus"]
    zeus = zeus or Zeus(settings, recipients, sleep=sleep)

    # 1) Cronos (o snapshot previo para depurar agentes aguas abajo)
    if "cronos" in agents:
        state.cronos = Cronos(settings, schema_map, sleep=sleep).run(state)
    else:
        state.cronos = json.loads((run_dir / "cronos.json").read_text(encoding="utf-8"))
    write_json(run_dir / "cronos.json", state.cronos)
    ok = _check(state, "C1", state.cronos, "cronos")

    if not ok or state.cronos["signal"]["status"] == Signal.FAILED.value:
        log.error("Cronos FAILED -> se omite Thanatos; Zeus envía solo el reporte de fallas")
        md = failure_markdown(build_failure_report(state))
        if "zeus" in agents:
            state.zeus = zeus.run(state, mode="failure", failure_md=md)
    else:
        # 2) Thanatos
        state.thanatos = Thanatos(settings, schema_map, thresholds).run(state)
        write_json(run_dir / "thanatos.json", state.thanatos)
        ok = _check(state, "C2", state.thanatos, "thanatos")
        md = failure_markdown(build_failure_report(state))
        if "zeus" in agents:
            if not ok or state.thanatos["signal"]["status"] == Signal.FAILED.value:
                state.zeus = zeus.run(state, mode="failure", failure_md=md)
            else:
                state.zeus = zeus.run(state, mode="reports", failure_md=md)
    if state.zeus:
        _check(state, "C3", state.zeus, "zeus")
        write_json(run_dir / "zeus.json", state.zeus)

    write_failure_report(state, run_dir)
    write_json(run_dir / f"run_{state.run_id}.json", state.to_dict())
    log.info("Fin corrida %s · estado final %s · errores %s", state.run_id, state.final_status().value,
             len(state.errors))
    return state
