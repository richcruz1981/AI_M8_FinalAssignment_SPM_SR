"""Crea una BD SQLite DE PRUEBA con estructura tipo ServiceNow SPM OOB.

DATOS SINTÉTICOS: no representan proyectos reales de ninguna empresa. Cada proyecto cubre un caso borde
definido en docs/plan/08 (resultado esperado en la columna 'caso').

Uso: python scripts/seed_demo_db.py [--db data/demo_spm.db] [--anchor YYYY-MM-DD] [--drop-table risk]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE sys_user (sys_id TEXT PRIMARY KEY, name TEXT, email TEXT);
CREATE TABLE pm_portfolio (sys_id TEXT PRIMARY KEY, number TEXT, name TEXT, portfolio_manager TEXT);
CREATE TABLE pm_program (sys_id TEXT PRIMARY KEY, number TEXT, name TEXT, program_manager TEXT, primary_portfolio TEXT);
CREATE TABLE pm_project (sys_id TEXT PRIMARY KEY, number TEXT, short_description TEXT, state TEXT,
  percent_complete REAL, start_date TEXT, end_date TEXT, work_start TEXT, work_end TEXT,
  cost REAL, work_cost REAL, effort REAL, work_effort REAL,
  project_manager TEXT, primary_program TEXT, primary_portfolio TEXT, caso TEXT);
CREATE TABLE project_status (sys_id TEXT PRIMARY KEY, project TEXT, as_on TEXT, overall_health TEXT,
  schedule TEXT, cost TEXT, resources TEXT, scope TEXT, comments TEXT);
CREATE TABLE pm_project_task (sys_id TEXT PRIMARY KEY, top_task TEXT, short_description TEXT, state TEXT,
  end_date TEXT, work_end TEXT, milestone INTEGER);
CREATE TABLE risk (sys_id TEXT PRIMARY KEY, task TEXT, short_description TEXT, state TEXT, probability TEXT,
  impact TEXT, owner TEXT, due_date TEXT);
CREATE TABLE issue (sys_id TEXT PRIMARY KEY, parent TEXT, short_description TEXT, state TEXT, priority TEXT, assigned_to TEXT);
CREATE TABLE dmn_decision (sys_id TEXT PRIMARY KEY, task TEXT, short_description TEXT, state TEXT, sys_created_on TEXT);
CREATE TABLE project_action (sys_id TEXT PRIMARY KEY, task TEXT, short_description TEXT, state TEXT, approval TEXT, due_date TEXT);
CREATE TABLE project_change_request (sys_id TEXT PRIMARY KEY, parent TEXT, short_description TEXT, state TEXT, sys_created_on TEXT);
CREATE TABLE resource_allocation (sys_id TEXT PRIMARY KEY, task TEXT, allocated_hours REAL, actual_hours REAL);
"""


def seed(db_path: str | Path, anchor: dt.date, drop_tables: tuple[str, ...] = ()) -> Path:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    d = lambda n: (anchor + dt.timedelta(days=n)).isoformat()  # noqa: E731
    con = sqlite3.connect(db_path)
    con.executescript(DDL)
    con.executemany("INSERT INTO sys_user VALUES (?,?,?)", [
        ("u_pm1", "Ana PM (demo)", "ana.pm@example.com"),
        ("u_pm2", "Luis PM (demo)", "luis.pm@example.com"),
        ("u_pm3", "Sin Correo (demo)", ""),
        ("u_pgm1", "Sofía PgM (demo)", "sofia.pgm@example.com"),
        ("u_pgm2", "Carlos PgM (demo)", "carlos.pgm@example.com"),
        ("u_pfm1", "Marta PfM (demo)", "marta.pfm@example.com"),
    ])
    con.execute("INSERT INTO pm_portfolio VALUES ('pf1','PFL001','Transformación Digital (demo)','u_pfm1')")
    con.executemany("INSERT INTO pm_program VALUES (?,?,?,?,?)", [
        ("pg1", "PRG001", "Programa Comercial (demo)", "u_pgm1", "pf1"),
        ("pg2", "PRG002", "Programa Operaciones (demo)", "u_pgm2", "pf1"),
    ])
    P = [  # sys_id, number, name, state, pc, start, end, wstart, wend, cost, wcost, effort, weffort, pm, prog, caso
        ("p1", "PRJ0001", "En tiempo y presupuesto", "work_in_progress", 50, d(-50), d(50), d(-50), None, 100000, 50000, 1000, 500, "u_pm1", "pg1", "Overall Verde"),
        ("p2", "PRJ0002", "Atraso de cronograma", "work_in_progress", 40, d(-60), d(40), d(-60), None, 100000, 40000, 1000, 400, "u_pm1", "pg1", "Schedule Rojo; Optimismo"),
        ("p3", "PRJ0003", "Sobrecosto moderado", "work_in_progress", 50, d(-50), d(50), d(-50), None, 100000, 55556, 1000, 500, "u_pm1", "pg1", "Cost Amarillo (CPI 0.90)"),
        ("p4", "PRJ0004", "Fin planeado vencido", "work_in_progress", 80, d(-100), d(-10), d(-100), None, 200000, 160000, 2000, 1600, "u_pm2", "pg1", "Schedule Rojo (vencido)"),
        ("p5", "PRJ0005", "Sin costo planeado", "work_in_progress", 30, d(-30), d(70), d(-30), None, 0, 10000, 500, 150, "u_pm2", "pg1", "Cost DATO_FALTANTE"),
        ("p6", "PRJ0006", "Sin Status Report", "work_in_progress", 20, d(-20), d(80), d(-20), None, 50000, 10000, 400, 80, "u_pm2", "pg2", "DQ-01"),
        ("p7", "PRJ0007", "Avance inválido", "work_in_progress", 120, d(-20), d(80), d(-20), None, 50000, 10000, 400, 80, "u_pm2", "pg2", "Excluido DQ-03"),
        ("p8", "PRJ0008", "Muchos cambios pendientes", "work_in_progress", 50, d(-50), d(50), d(-50), None, 80000, 40000, 800, 400, "u_pm2", "pg2", "Scope Rojo -> Overall Amarillo"),
        ("p9", "PRJ0009", "Fechas incoherentes", "work_in_progress", 10, d(10), d(-10), None, None, 50000, 0, 400, 0, "u_pm2", "pg2", "Excluido DQ-04"),
        ("p10", "PRJ0010", "SR desactualizado", "work_in_progress", 45, d(-50), d(50), d(-50), None, 60000, 30000, 600, 300, "u_pm3", "pg2", "DQ-02 + DQ-07 (escala a PgM)"),
        ("p11", "PRJ0011", "Proyecto cerrado", "closed_complete", 100, d(-200), d(-100), d(-200), d(-100), 10000, 10000, 100, 100, "u_pm1", "pg1", "Fuera de alcance (cerrado)"),
    ]
    con.executemany("INSERT INTO pm_project VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pf1',?)", P)
    SR = [
        ("sr1", "p1", d(-2), "green", "green", "green", "green", "green", "OK"),
        ("sr2", "p2", d(-2), "green", "green", "green", "green", "green", "PM reporta verde"),
        ("sr3", "p3", d(-3), "yellow", "green", "yellow", "green", "green", ""),
        ("sr3_old", "p3", d(-30), "green", "green", "green", "green", "green", "SR anterior (histórico)"),
        ("sr4", "p4", d(-1), "red", "red", "green", "green", "green", ""),
        ("sr5", "p5", d(-4), "green", "green", "", "green", "green", "Costo sin semáforo"),
        ("sr7", "p7", d(-1), "green", "green", "green", "green", "green", ""),
        ("sr8", "p8", d(-2), "yellow", "green", "green", "green", "yellow", ""),
        ("sr9", "p9", d(-1), "green", "green", "green", "green", "green", ""),
        ("sr10", "p10", d(-20), "green", "green", "green", "green", "green", "Viejo"),
    ]
    con.executemany("INSERT INTO project_status VALUES (?,?,?,?,?,?,?,?,?)", SR)
    con.executemany("INSERT INTO pm_project_task VALUES (?,?,?,?,?,?,?)", [
        ("m1", "p1", "Kickoff", "closed_complete", d(-45), d(-45), 1),
        ("m2", "p1", "Diseño aprobado", "open", d(10), None, 1),
        ("m3", "p2", "Piloto", "open", d(-5), None, 1),
        ("t1", "p2", "Tarea normal (no hito)", "open", d(-5), None, 0),
        ("m4", "p4", "Go-live", "open", d(-10), None, 1),
    ])
    con.executemany("INSERT INTO risk VALUES (?,?,?,?,?,?,?,?)", [
        ("r1", "p2", "Proveedor retrasa entregas", "open", "high", "high", "u_pm1", d(-1)),
        ("r2", "p2", "Rotación de personal", "open", "low", "medium", None, d(30)),
        ("r3", "p4", "Integración inestable", "open", "high", "high", "u_pm2", d(5)),
        ("r4", "p1", "Riesgo cerrado", "closed", "high", "high", "u_pm1", d(-10)),
    ])
    con.executemany("INSERT INTO issue VALUES (?,?,?,?,?,?)", [
        ("i1", "p2", "Ambiente QA caído", "open", "1", "u_pm1"),
        ("i2", "p4", "Datos maestros incompletos", "open", "2", None),
    ])
    con.executemany("INSERT INTO dmn_decision VALUES (?,?,?,?,?)", [
        ("dc1", "p2", "Aprobar presupuesto adicional", "open", d(-12)),
    ])
    con.executemany("INSERT INTO project_action VALUES (?,?,?,?,?,?)", [
        ("a1", "p2", "Replanificar sprint", "open", "requested", d(-3)),
        ("a2", "p1", "Enviar minuta", "closed", "approved", d(-1)),
    ])
    con.executemany("INSERT INTO project_change_request VALUES (?,?,?,?,?)", [
        ("c1", "p8", "Nuevo módulo A", "requested", d(-20)),
        ("c2", "p8", "Nuevo reporte", "pending", d(-5)),
        ("c3", "p8", "Integración extra", "requested", d(-2)),
        ("c4", "p3", "Ajuste menor", "requested", d(-1)),
        ("c5", "p1", "Cambio aprobado", "approved", d(-30)),
    ])
    con.executemany("INSERT INTO resource_allocation VALUES (?,?,?,?)", [
        ("ra1", "p1", 500, 500), ("ra2", "p2", 600, 400),
    ])
    for t in drop_tables:
        con.execute(f"DROP TABLE IF EXISTS {t}")
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).resolve().parents[1] / "data" / "demo_spm.db"))
    ap.add_argument("--anchor", default=dt.date.today().isoformat())
    ap.add_argument("--drop-table", action="append", default=[])
    a = ap.parse_args()
    p = seed(a.db, dt.date.fromisoformat(a.anchor), tuple(a.drop_table))
    print(f"BD demo (datos sintéticos) creada en {p} con fecha ancla {a.anchor}")
