"""Agente 1 "Cronos" — Lector. Conecta a la réplica, lee, valida calidad, guarda en memoria y emite señal."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ArgumentError, NoSuchModuleError, OperationalError, SQLAlchemyError

from ..cerbero import SecurityHalt, get_cerbero
from ..core.state import RunState, Signal, make_signal
from ..core.util import norm, now_iso, parse_date, to_float
from .dq import HEALTH_FIELDS, dedupe, normalize_health, run_dq

log = logging.getLogger("spm_sr.cronos")
AUTH_HINTS = ("password", "authentication", "access denied", "login failed", "permission denied")
DATE_FIELDS = ("planned_start", "planned_end", "actual_start", "actual_end")
NUM_FIELDS = ("percent_complete", "planned_cost", "actual_cost", "planned_effort", "actual_effort")


class Cronos:
    name = "cronos"

    def __init__(self, settings: dict, schema_map: dict, sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.map = schema_map
        self.sleep = sleep

    # ------------------------------------------------------------------ conexión
    def _connect(self, state: RunState) -> Engine | None:
        db = self.settings["db"]
        url: str = db["url"]
        if url.startswith("sqlite:///"):
            path = url[len("sqlite:///"):]
            if path and path != ":memory:" and not Path(path).exists():
                state.add_error("E-CONN-01", self.name, f"No existe el archivo de BD SQLite: {path}", blocking=True)
                return None
        timeout = int(db.get("connect_timeout_s", 30))
        connect_args = {"timeout": timeout} if url.startswith(("sqlite", "mssql")) else {"connect_timeout": timeout}
        attempts = int(db.get("retries", 3))
        backoff = db.get("backoff_s", [5, 15, 45]) or [0]
        last: Exception | None = None
        for i in range(attempts):
            try:
                engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                log.info("Conexión a BD establecida (intento %s) · origen %s · %s", i + 1,
                         db.get("url_origin", "config"), engine.url.render_as_string(hide_password=True))
                return engine
            except (ArgumentError, NoSuchModuleError, ImportError) as e:
                state.add_error("E-CONN-03", self.name, f"URL de BD o driver inválido: {e}", blocking=True)
                return None
            except OperationalError as e:
                if any(h in str(e).lower() for h in AUTH_HINTS):
                    state.add_error("E-CONN-02", self.name, "Autenticación rechazada por la BD", blocking=True,
                                    detail=str(e.orig)[:300], origin=db.get("url_origin", "config"))
                    return None
                last = e
            except Exception as e:  # noqa: BLE001 - se registra y se reintenta
                last = e
            if i < attempts - 1:
                wait = backoff[min(i, len(backoff) - 1)]
                log.warning("Fallo de conexión (intento %s/%s). Reintento en %ss", i + 1, attempts, wait)
                self.sleep(wait)
        state.add_error("E-CONN-01", self.name, f"No fue posible conectar tras {attempts} intentos", blocking=True,
                        detail=str(last)[:300], origin=db.get("url_origin", "config"))
        return None

    # ------------------------------------------------------------------ lectura genérica
    def _read(self, conn, insp, tables: set[str], key: str, spec: dict, state: RunState, core: bool,
              availability: dict) -> list[dict] | None:
        table = spec["table"]
        if table not in tables:
            availability[key] = {"table": table, "exists": False, "rows": 0}
            code = "E-SCHEMA-01" if core else "E-SCHEMA-02"
            state.add_error(code, self.name, f"Tabla '{table}' ({key}) no existe en la réplica",
                            severity="Alta" if core else "Media", blocking=core)
            return None
        existing = {c["name"] for c in insp.get_columns(table)}
        cols: dict[str, str] = spec["columns"]
        missing = [lg for lg, ph in cols.items() if ph not in existing]
        req_missing = [lg for lg in missing if lg in spec.get("required", [])]
        if req_missing:
            availability[key] = {"table": table, "exists": True, "rows": 0, "missing_columns": missing}
            code = "E-SCHEMA-01" if core else "E-SCHEMA-02"
            state.add_error(code, self.name, f"Columnas obligatorias ausentes en '{table}': {req_missing}",
                            severity="Alta" if core else "Media", blocking=core)
            return None
        if missing:
            state.add_error("E-SCHEMA-03", self.name, f"Columnas opcionales ausentes en '{table}': {missing}",
                            severity="Media", blocking=False)
        q = conn.dialect.identifier_preparer.quote
        select = ", ".join(f"{q(ph)} AS {q(lg)}" for lg, ph in cols.items() if ph in existing)
        try:
            rows = [dict(r) for r in conn.execute(text(f"SELECT {select} FROM {q(table)}")).mappings().all()]
        except SQLAlchemyError as e:
            availability[key] = {"table": table, "exists": True, "rows": 0, "read_error": True}
            state.add_error("E-READ-01", self.name, f"Fallo al leer '{table}'", severity="Alta" if core else "Media",
                            blocking=core, detail=str(e)[:300])
            return None
        for r in rows:
            for lg in missing:
                r[lg] = None
        availability[key] = {"table": table, "exists": True, "rows": len(rows), "missing_columns": missing}
        return rows

    # ------------------------------------------------------------------ alcance
    @staticmethod
    def _in_scope(p: dict, scope: list[str], programs: dict, portfolios: dict) -> bool:
        if not scope or "all" in [s.lower() for s in scope]:
            return True
        prog_num = norm(programs.get(p.get("program") or "", {}).get("number"))
        port_num = norm(portfolios.get(p.get("portfolio") or "", {}).get("number"))
        for item in scope:
            kind, _, val = item.partition(":")
            val = norm(val)
            if kind == "project" and val in (norm(p.get("number")), norm(p.get("id"))):
                return True
            if kind == "program" and val in (prog_num, norm(p.get("program"))):
                return True
            if kind == "portfolio" and val in (port_num, norm(p.get("portfolio"))):
                return True
        return False

    # ------------------------------------------------------------------ ejecución
    def run(self, state: RunState) -> dict[str, Any]:
        started = now_iso()
        out: dict[str, Any] = {"projects": [], "status_reports": {}, "hierarchy": {}, "aux": {},
                               "data_quality": [], "source_availability": {}, "inventory": []}
        guard = get_cerbero(self.settings)
        engine = self._connect(state)
        if engine is None:
            guard.note(self.name, "db_connect", "ERROR", [e.code for e in state.errors_of(self.name)][-1:], None, "MEDIUM")
            out["signal"] = make_signal(Signal.FAILED, started)
            return out
        out["read_at"] = now_iso()
        avail = out["source_availability"]
        try:
            with engine.connect() as conn:
                insp = inspect(conn)
                tables = set(insp.get_table_names())
                core = self.map["core"]
                raw_projects = self._read(conn, insp, tables, "project", core["project"], state, True, avail)
                raw_srs = self._read(conn, insp, tables, "status_report", core["status_report"], state, True, avail)
                if raw_projects is None or raw_srs is None:
                    out["signal"] = make_signal(Signal.FAILED, started)
                    return out
                hier = {}
                for key, spec in self.map.get("hierarchy", {}).items():
                    rows = self._read(conn, insp, tables, key, spec, state, False, avail) or []
                    hier[key] = {str(r["id"]): r for r in rows}
                aux_raw = {key: self._read(conn, insp, tables, key, spec, state, False, avail)
                           for key, spec in self.map.get("auxiliary", {}).items()}
        finally:
            engine.dispose()

        out["hierarchy"] = hier
        closed = {norm(s) for s in self.map.get("states", {}).get("closed_project", [])}

        region_ok = "region" not in avail.get("project", {}).get("missing_columns", ["region"])
        projects, inventory = [], []
        for r in raw_projects:
            p = {k: (str(v) if k in ("id", "project_manager", "program", "portfolio") and v is not None else v)
                 for k, v in r.items()}
            for f in DATE_FIELDS:
                p[f] = parse_date(p.get(f))
            for f in NUM_FIELDS:
                p[f] = to_float(p.get(f))
            p["number"] = str(p.get("number") or p["id"])
            p["_region_available"] = region_ok
            if not self._in_scope(p, state.scope, hier.get("program", {}), hier.get("portfolio", {})):
                continue
            # Inventario: TODOS los proyectos del alcance (incluye cerrados y los que DQ excluya) para conteos
            inventory.append({k: p.get(k) for k in ("id", "number", "name", "state", "region", "program",
                                                    "portfolio", "project_manager")})
            if norm(p.get("state")) in closed:
                continue
            projects.append(p)
        records_in = len(projects)
        projects, dup_findings = dedupe(projects)

        latest: dict[str, dict] = {}
        for r in raw_srs:
            pid = str(r.get("project")) if r.get("project") is not None else None
            if pid is None:
                continue
            sr = dict(r)
            sr["as_on"] = parse_date(sr.get("as_on"))
            for h in HEALTH_FIELDS:
                sr[f"{h}_raw"] = sr.get(h)
                sr[h] = normalize_health(sr.get(h))
            prev = latest.get(pid)
            if prev is None or (sr["as_on"] or parse_date("1900-01-01")) > (prev["as_on"] or parse_date("1900-01-01")):
                latest[pid] = sr

        valid, findings = run_dq(projects, latest, hier.get("user", {}), state.run_date,
                                 int(self.settings.get("dq", {}).get("stale_sr_days", 7)))
        findings = dup_findings + findings
        valid_ids = {p["id"] for p in valid}

        aux_out: dict[str, dict[str, list[dict]]] = {}
        for key, rows in aux_raw.items():
            if rows is None:
                continue
            spec = self.map["auxiliary"][key]
            flt = spec.get("filter")
            fk = spec.get("project_fk", "project")
            grouped: dict[str, list[dict]] = defaultdict(list)
            for r in rows:
                if flt and norm(r.get(flt["column"])) not in {norm(v) for v in flt["values"]}:
                    continue
                pid = str(r.get(fk)) if r.get(fk) is not None else None
                if pid in valid_ids:
                    grouped[pid].append(r)
            aux_out[key] = dict(grouped)

        out["projects"] = valid
        out["inventory"] = inventory
        out["region_available"] = region_ok
        out["status_reports"] = {pid: sr for pid, sr in latest.items() if pid in valid_ids}
        out["aux"] = aux_out
        out["data_quality"] = findings
        excluded = sum(1 for f in findings if f["excluded"])

        # Cerbero (gate "data"): todo texto leído de la BD se revisa y neutraliza antes de llegar a otro agente
        try:
            get_cerbero(self.settings).inspect_data(out, self.name)
        except SecurityHalt as e:
            state.add_error("E-SEC-01", self.name, f"Cerbero detuvo la lectura: {e.reason}", blocking=True)
            out["projects"], out["status_reports"], out["aux"] = [], {}, {}
            out["signal"] = make_signal(Signal.FAILED, started, records_in=records_in)
            return out
        degraded = [e for e in state.errors_of(self.name) if not e.blocking]
        if not valid:
            state.add_error("E-DATA-00", self.name, "0 proyectos válidos en el alcance", blocking=True,
                            scope=state.scope, records_in=records_in)
            status = Signal.FAILED
        elif excluded or degraded:
            status = Signal.PARTIAL
        else:
            status = Signal.COMPLETED
        out["signal"] = make_signal(status, started, records_in=records_in, records_ok=len(valid),
                                    records_excluded=excluded + len(dup_findings))
        log.info("Cronos %s: %s leídos, %s válidos, %s excluidos", status.value, records_in, len(valid),
                 out["signal"]["records_excluded"])
        return out
