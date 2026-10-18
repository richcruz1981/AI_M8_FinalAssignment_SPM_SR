"""Genera DATOS SINTÉTICOS (ficticios) con estructura tipo ServiceNow SPM OOB para demostrar el proyecto.

- 12 tablas, cada una con 100-200 registros, valores aleatorios reproducibles (semilla fija).
- Mezcla deliberada de proyectos sanos, atrasados, con sobrecosto, vencidos y con fallas de calidad de datos,
  para que se vean todos los semáforos y reglas DQ.
- Salida: un .sql compatible con PostgreSQL (y SQLite, para probar en local).

Uso:
  python scripts/generate_spm_dummy.py --out data/spm_dummy_postgres.sql [--sqlite data/spm_dummy.db] [--anchor 2026-10-18]
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spm_sr.thanatos import kpi_rules as K  # noqa: E402

CHUNK = "-- @@CHUNK"
REGIONS = ["Norte", "Noreste", "Centro", "Bajío", "Occidente", "Sureste"]


def region_for(number: str) -> str | None:
    """Región determinista por número de proyecto (campo personalizado u_region). ~6 % queda sin región (DQ-10)."""
    import hashlib

    h = int(hashlib.sha256(number.encode()).hexdigest(), 16)
    return None if h % 100 < 6 else REGIONS[(h // 100) % len(REGIONS)]
TABLES = ["sys_user", "pm_portfolio", "pm_program", "pm_project", "project_status", "pm_project_task", "risk",
          "issue", "dmn_decision", "project_action", "project_change_request", "resource_allocation"]

DDL = """
CREATE TABLE sys_user (sys_id varchar(32) PRIMARY KEY, name varchar(100), email varchar(120), title varchar(60));
CREATE TABLE pm_portfolio (sys_id varchar(32) PRIMARY KEY, number varchar(20), name varchar(120), portfolio_manager varchar(32));
CREATE TABLE pm_program (sys_id varchar(32) PRIMARY KEY, number varchar(20), name varchar(120), program_manager varchar(32),
  primary_portfolio varchar(32));
CREATE TABLE pm_project (sys_id varchar(32) PRIMARY KEY, number varchar(20), short_description varchar(160), state varchar(30),
  percent_complete numeric(6,2), start_date date, end_date date, work_start date, work_end date,
  cost numeric(14,2), work_cost numeric(14,2), effort numeric(10,1), work_effort numeric(10,1),
  project_manager varchar(32), primary_program varchar(32), primary_portfolio varchar(32), sys_created_on timestamp,
  u_region varchar(30));
CREATE TABLE project_status (sys_id varchar(32) PRIMARY KEY, project varchar(32), as_on date, overall_health varchar(10),
  schedule varchar(10), cost varchar(10), resources varchar(10), scope varchar(10), comments text);
CREATE TABLE pm_project_task (sys_id varchar(32) PRIMARY KEY, top_task varchar(32), short_description varchar(160),
  state varchar(30), end_date date, work_end date, milestone smallint);
CREATE TABLE risk (sys_id varchar(32) PRIMARY KEY, task varchar(32), short_description varchar(160), state varchar(30),
  probability varchar(10), impact varchar(10), owner varchar(32), due_date date);
CREATE TABLE issue (sys_id varchar(32) PRIMARY KEY, parent varchar(32), short_description varchar(160), state varchar(30),
  priority varchar(5), assigned_to varchar(32));
CREATE TABLE dmn_decision (sys_id varchar(32) PRIMARY KEY, task varchar(32), short_description varchar(160), state varchar(30),
  sys_created_on timestamp);
CREATE TABLE project_action (sys_id varchar(32) PRIMARY KEY, task varchar(32), short_description varchar(160), state varchar(30),
  approval varchar(30), due_date date);
CREATE TABLE project_change_request (sys_id varchar(32) PRIMARY KEY, parent varchar(32), short_description varchar(160),
  state varchar(30), sys_created_on timestamp);
CREATE TABLE resource_allocation (sys_id varchar(32) PRIMARY KEY, task varchar(32), allocated_hours numeric(10,1),
  actual_hours numeric(10,1));
"""

FIRST = ["Ana", "Luis", "Sofía", "Carlos", "Marta", "Jorge", "Lucía", "Diego", "Valeria", "Andrés", "Paola", "Ricardo",
         "Fernanda", "Miguel", "Daniela", "Héctor", "Camila", "Raúl", "Gabriela", "Óscar", "Elena", "Iván", "Natalia",
         "Tomás", "Regina", "Emilio", "Ximena", "Rodrigo", "Adriana", "Sergio"]
LAST = ["García", "Hernández", "López", "Martínez", "González", "Pérez", "Rodríguez", "Sánchez", "Ramírez", "Torres",
        "Flores", "Rivera", "Gómez", "Díaz", "Cruz", "Morales", "Reyes", "Ortiz", "Castillo", "Vargas"]
THEMES = ["Transformación Digital", "Experiencia del Cliente", "Cadena de Suministro", "Manufactura Inteligente",
          "Datos y Analítica", "Ciberseguridad", "Comercial", "Finanzas", "Talento", "Sustentabilidad",
          "Logística", "Innovación de Producto", "Infraestructura TI", "Cumplimiento", "Marketing Digital"]
PROJ_NOUNS = ["Migración", "Implementación", "Rediseño", "Automatización", "Integración", "Modernización", "Despliegue",
              "Optimización", "Piloto", "Consolidación"]
PROJ_OBJ = ["ERP", "CRM", "portal de clientes", "data lake", "red de distribución", "planta norte", "app móvil",
            "facturación electrónica", "WMS", "tablero de KPIs", "pricing dinámico", "e-commerce B2B", "SOC",
            "nube híbrida", "mesa de servicio", "MES", "programa de lealtad", "trazabilidad", "forecast de demanda",
            "IAM"]
RISKS = ["Retraso del proveedor", "Rotación de personal clave", "Cambio regulatorio", "Dependencia de otro proyecto",
         "Presupuesto insuficiente", "Integración inestable", "Calidad de datos de origen", "Disponibilidad de ambientes"]
ISSUES = ["Ambiente QA caído", "Datos maestros incompletos", "Defecto crítico en pruebas", "Licencias pendientes",
          "Acceso a sistemas bloqueado", "Recurso no asignado", "Retraso en aprobación de diseño"]
DECISIONS = ["Aprobar presupuesto adicional", "Elegir proveedor de integración", "Priorizar alcance de fase 2",
             "Mover fecha de salida", "Aceptar riesgo residual"]
ACTIONS = ["Replanificar sprint", "Escalar con el proveedor", "Enviar minuta al comité", "Actualizar plan de pruebas",
           "Validar estimación con finanzas", "Contratar recurso temporal"]
CHANGES = ["Nuevo módulo", "Reporte adicional", "Integración extra", "Ajuste de alcance", "Nueva región",
           "Cambio de plataforma"]


class Gen:
    def __init__(self, anchor: dt.date, seed: int):
        self.a = anchor
        self.r = random.Random(seed)
        self.ids: set[str] = set()
        self.rows: dict[str, list[dict]] = {t: [] for t in TABLES}

    def sid(self) -> str:
        while True:
            s = "%032x" % self.r.getrandbits(128)
            if s not in self.ids:
                self.ids.add(s)
                return s

    def d(self, days: int) -> dt.date:
        return self.a + dt.timedelta(days=days)

    def ts(self, days: int) -> str:
        return (dt.datetime.combine(self.d(days), dt.time(self.r.randint(8, 19), self.r.randint(0, 59)))).isoformat(" ")

    # ------------------------------------------------------------------ entidades
    def users(self, n=120):
        used = set()
        for i in range(n):
            while True:
                f, l1, l2 = self.r.choice(FIRST), self.r.choice(LAST), self.r.choice(LAST)
                if (f, l1, l2) not in used:
                    used.add((f, l1, l2))
                    break
            title = "PfM" if i < 6 else "PgM" if i < 31 else "PM" if i < 71 else "Equipo"
            slug = (f + "." + l1 + "." + l2).lower()
            for a, b in zip("áéíóúñ", "aeioun"):
                slug = slug.replace(a, b)
            email = "" if (title == "PM" and self.r.random() < 0.06) else f"{slug}@pepaidummy.example"
            self.rows["sys_user"].append({"sys_id": self.sid(), "name": f"{f} {l1} {l2}", "email": email, "title": title})
        U = self.rows["sys_user"]
        self.pfm = [u for u in U if u["title"] == "PfM"]
        self.pgm = [u for u in U if u["title"] == "PgM"]
        self.pm = [u for u in U if u["title"] == "PM"]
        self.team = U

    def portfolios(self, n=100):
        for i in range(n):
            theme = THEMES[i % len(THEMES)]
            self.rows["pm_portfolio"].append({"sys_id": self.sid(), "number": f"PFL{i + 1:04d}",
                                              "name": f"{theme} {2026 + i // len(THEMES)}",
                                              "portfolio_manager": self.pfm[i % len(self.pfm)]["sys_id"]})
        self.active_pf = self.rows["pm_portfolio"][:6]                     # concentran la operación

    def programs(self, n=100):
        for i in range(n):
            pf = self.active_pf[i % 6] if self.r.random() < 0.8 else self.r.choice(self.rows["pm_portfolio"])
            self.rows["pm_program"].append({"sys_id": self.sid(), "number": f"PRG{i + 1:04d}",
                                            "name": f"Programa {self.r.choice(THEMES)} {i + 1}",
                                            "program_manager": self.pgm[i % len(self.pgm)]["sys_id"],
                                            "primary_portfolio": pf["sys_id"]})
        self.active_pg = self.rows["pm_program"][:25]

    def projects(self, n=150):
        arche = (["on_track"] * 40 + ["slip"] * 15 + ["overrun"] * 15 + ["both"] * 8 + ["overdue"] * 7 +
                 ["early"] * 8 + ["dq"] * 7)
        for i in range(n):
            pg = self.r.choice(self.active_pg) if self.r.random() < 0.9 else self.r.choice(self.rows["pm_program"])
            kind = self.r.choice(arche)
            start = self.d(-self.r.randint(10, 300))
            dur = self.r.randint(60, 400)
            end = start + dt.timedelta(days=dur)
            if kind == "overdue":
                end = self.d(-self.r.randint(3, 60))
                start = end - dt.timedelta(days=dur)
            if kind == "early":
                start = self.d(self.r.randint(-5, 20))
                end = start + dt.timedelta(days=dur)
            exp = max(0.0, min(1.0, (self.a - start).days / max(1, (end - start).days))) * 100
            if kind in ("slip", "both"):
                pc = exp - self.r.uniform(8, 35)
            elif kind == "overdue":
                pc = self.r.uniform(60, 95)
            else:
                pc = exp + self.r.gauss(0, 4)
            pc = round(max(0.0, min(100.0, pc)), 1)
            state = "work_in_progress" if pc > 0 else "pending"
            r = self.r.random()
            if r < 0.08:
                state, pc = "closed_complete", 100.0
            elif r < 0.11:
                state = "cancelled"
            elif r < 0.15:
                state = "on_hold"
            cost = round(self.r.uniform(50, 2000)) * 1000.0
            cpi = self.r.uniform(0.70, 0.92) if kind in ("overrun", "both") else self.r.gauss(1.0, 0.04)
            work_cost = round(cost * pc / 100 / max(cpi, 0.5), 2)
            effort = float(round(self.r.uniform(400, 8000)))
            ef = self.r.uniform(1.15, 1.5) if kind in ("overrun", "both") and self.r.random() < 0.6 else self.r.uniform(0.9, 1.1)
            work_effort = round(effort * pc / 100 * ef, 1)
            work_start = None if pc == 0 else start + dt.timedelta(days=self.r.randint(-3, 10))
            if pc > 0 and self.r.random() < 0.04:
                work_start = None                                          # DQ-05
            work_end = self.d(-self.r.randint(1, 60)) if state == "closed_complete" else None
            if kind == "dq":
                bad = self.r.choice(["pc_hi", "pc_lo", "dates", "cost0", "costnull", "effort0"])
                if bad == "pc_hi":
                    pc = round(self.r.uniform(101, 140), 1)
                elif bad == "pc_lo":
                    pc = -round(self.r.uniform(1, 10), 1)
                elif bad == "dates":
                    end = start - dt.timedelta(days=self.r.randint(5, 40))
                elif bad == "cost0":
                    cost = 0.0
                elif bad == "costnull":
                    cost = None
                else:
                    effort = 0.0
            pm = self.r.choice(self.pm)
            self.rows["pm_project"].append({
                "sys_id": self.sid(), "number": f"PRJ{1001000 + i + 1}",
                "short_description": f"{self.r.choice(PROJ_NOUNS)} de {self.r.choice(PROJ_OBJ)}",
                "state": state, "percent_complete": pc, "start_date": start, "end_date": end,
                "work_start": work_start, "work_end": work_end, "cost": cost, "work_cost": work_cost,
                "effort": effort, "work_effort": work_effort, "project_manager": pm["sys_id"],
                "primary_program": pg["sys_id"], "primary_portfolio": pg["primary_portfolio"],
                "sys_created_on": self.ts(-(self.a - start).days - 15),
                "u_region": region_for(f"PRJ{1001000 + i + 1}"), "_kind": kind})
        self.active_proj = [p for p in self.rows["pm_project"] if p["state"] not in ("closed_complete", "cancelled")]

    def _pick(self, weight_bad=0.6):
        """Proyecto activo; los que tienen problemas reciben más registros de control."""
        bad = [p for p in self.active_proj if p["_kind"] in ("slip", "both", "overdue", "overrun")]
        return self.r.choice(bad if bad and self.r.random() < weight_bad else self.active_proj)["sys_id"]

    def controls(self):
        A = self.active_proj
        for i in range(180):
            p = self.r.choice(A)
            ms = self.r.random() < 0.9
            due = p["start_date"] + dt.timedelta(days=self.r.randint(5, max(6, (p["end_date"] - p["start_date"]).days or 30)))
            done = due < self.a and self.r.random() < (0.55 if p["_kind"] in ("slip", "both", "overdue") else 0.85)
            self.rows["pm_project_task"].append({
                "sys_id": self.sid(), "top_task": p["sys_id"],
                "short_description": ("Hito: " if ms else "Tarea: ") + self.r.choice(
                    ["Kickoff", "Diseño aprobado", "Construcción", "Pruebas integrales", "Piloto", "Go-live", "Cierre"]),
                "state": "closed_complete" if done else "open", "end_date": due,
                "work_end": due + dt.timedelta(days=self.r.randint(-3, 7)) if done else None, "milestone": 1 if ms else 0})
        for i in range(160):
            st = "open" if self.r.random() < 0.7 else "closed"
            self.rows["risk"].append({
                "sys_id": self.sid(), "task": self._pick(), "short_description": self.r.choice(RISKS), "state": st,
                "probability": self.r.choices(["high", "medium", "low"], [25, 45, 30])[0],
                "impact": self.r.choices(["high", "medium", "low"], [30, 45, 25])[0],
                "owner": None if self.r.random() < 0.1 else self.r.choice(self.team)["sys_id"],
                "due_date": self.d(self.r.randint(-20, 60))})
        for i in range(150):
            self.rows["issue"].append({
                "sys_id": self.sid(), "parent": self._pick(), "short_description": self.r.choice(ISSUES),
                "state": "open" if self.r.random() < 0.65 else "resolved",
                "priority": self.r.choices(["1", "2", "3", "4"], [15, 30, 35, 20])[0],
                "assigned_to": None if self.r.random() < 0.1 else self.r.choice(self.team)["sys_id"]})
        for i in range(120):
            self.rows["dmn_decision"].append({
                "sys_id": self.sid(), "task": self._pick(0.5), "short_description": self.r.choice(DECISIONS),
                "state": self.r.choices(["open", "approved", "rejected"], [50, 35, 15])[0],
                "sys_created_on": self.ts(-self.r.randint(1, 60))})
        for i in range(150):
            st = "open" if self.r.random() < 0.6 else "closed"
            self.rows["project_action"].append({
                "sys_id": self.sid(), "task": self._pick(0.5), "short_description": self.r.choice(ACTIONS), "state": st,
                "approval": self.r.choices(["requested", "approved", "not_yet_requested"], [30, 50, 20])[0],
                "due_date": self.d(self.r.randint(-15, 30))})
        scope_hot = self.r.sample(A, 8)                                    # proyectos con muchos cambios pendientes
        for i in range(150):
            p = scope_hot[i % 8] if i < 32 else self.r.choice(A)
            st = "requested" if i < 32 else self.r.choices(
                ["requested", "pending", "in_review", "approved", "rejected"], [18, 15, 12, 35, 20])[0]
            self.rows["project_change_request"].append({
                "sys_id": self.sid(), "parent": p["sys_id"],
                "short_description": f"{self.r.choice(CHANGES)} ({self.r.choice(PROJ_OBJ)})", "state": st,
                "sys_created_on": self.ts(-self.r.randint(1, 90))})
        targets = [self.r.choice(A) for _ in range(150)]
        for p in targets:
            alloc = round(self.r.uniform(100, 2000), 1)
            ratio = self.r.uniform(1.1, 1.4) if p["_kind"] in ("overrun", "both") else self.r.uniform(0.75, 1.1)
            self.rows["resource_allocation"].append({"sys_id": self.sid(), "task": p["sys_id"],
                                                     "allocated_hours": alloc, "actual_hours": round(alloc * ratio, 1)})

    def status_reports(self, n=180):
        """Semáforo declarado ≈ calculado; ~20 % 'optimista', ~5 % conservador, ~3 % vacío (DQ-08)."""
        th = {"schedule": {"yellow_gap_pp": -5, "red_gap_pp": -15},
              "cost": {"green_cpi": 0.95, "yellow_cpi": 0.85, "max_consumption": 1.0},
              "resources": {"green_low": 0.9, "green_high": 1.1, "yellow_low": 0.8, "yellow_high": 1.25},
              "scope": {"yellow_pending": 1, "red_pending": 3}}
        pend = {"requested", "pending", "in_review"}
        crs: dict[str, list] = {}
        for c in self.rows["project_change_request"]:
            crs.setdefault(c["parent"], []).append(c)
        order = ["green", "yellow", "red"]
        to_en = {K.G: "green", K.Y: "yellow", K.R: "red"}
        eligible = [p for p in self.rows["pm_project"] if p["state"] != "cancelled"]
        with_sr = [p for p in eligible if self.r.random() < 0.93]          # ~7 % sin SR (DQ-01)
        plan = list(with_sr) + [self.r.choice(with_sr) for _ in range(max(0, n - len(with_sr)))]
        plan = plan[:n]
        seen: dict[str, int] = {}
        for p in plan:
            k = seen.get(p["sys_id"], 0)
            seen[p["sys_id"]] = k + 1
            stale = k == 0 and self.r.random() < 0.15
            as_on = self.d(-self.r.randint(8, 35)) if stale else self.d(-self.r.randint(0, 6) - 7 * k)
            proj = {**p, "planned_start": p["start_date"], "planned_end": p["end_date"],
                    "planned_cost": p["cost"], "actual_cost": p["work_cost"],
                    "planned_effort": p["effort"], "actual_effort": p["work_effort"]}
            try:
                calc = {"schedule": K.schedule(proj, self.a, th["schedule"])["color"],
                        "cost": K.cost(proj, th["cost"])["color"],
                        "resources": K.resources(proj, None, th["resources"])["color"],
                        "scope": K.scope(crs.get(p["sys_id"], []), True, th["scope"], pend)["color"]}
            except Exception:  # noqa: BLE001 - registros con DQ
                calc = {k2: K.DF for k2 in ("schedule", "cost", "resources", "scope")}
            calc["overall"] = K.overall(calc)["color"]
            dec = {}
            mood = self.r.random()
            for key, c in calc.items():
                v = to_en.get(c, self.r.choice(order))
                if mood < 0.20:                                            # optimista
                    v = order[max(0, order.index(v) - 1)]
                elif mood < 0.25:                                          # conservador
                    v = order[min(2, order.index(v) + 1)]
                if self.r.random() < 0.03:
                    v = ""
                dec[key] = v
            self.rows["project_status"].append({
                "sys_id": self.sid(), "project": p["sys_id"], "as_on": as_on, "overall_health": dec["overall"],
                "schedule": dec["schedule"], "cost": dec["cost"], "resources": dec["resources"], "scope": dec["scope"],
                "comments": self.r.choice(["Avance conforme al plan", "Se requiere apoyo del comité",
                                           "Riesgos bajo control", "Dependencia externa en seguimiento",
                                           "Replanificación en curso", ""])})

    def build(self):
        self.users(); self.portfolios(); self.programs(); self.projects(); self.controls(); self.status_reports()
        return self


def sql_value(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(round(v, 2)) if isinstance(v, float) else str(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return "'" + v.isoformat() + "'"
    return "'" + str(v).replace("'", "''") + "'"


def to_sql(g: Gen, drop: bool = True) -> str:
    out = ["-- DATOS SINTÉTICOS para demostrar el proyecto SR (no son datos reales de ninguna empresa).",
           f"-- Generado {dt.datetime.now().isoformat(timespec='seconds')} · fecha ancla {g.a.isoformat()}", CHUNK]
    if drop:
        out.append("".join(f"DROP TABLE IF EXISTS {t};\n" for t in reversed(TABLES)))
    out.append(DDL.strip())
    for t in TABLES:
        rows = g.rows[t]
        cols = [c for c in rows[0] if not c.startswith("_")]
        out.append(CHUNK)
        vals = ",\n".join("(" + ", ".join(sql_value(r[c]) for c in cols) + ")" for r in rows)
        out.append(f"INSERT INTO {t} ({', '.join(cols)}) VALUES\n{vals};")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "spm_dummy_postgres.sql"))
    ap.add_argument("--sqlite", help="Además, cargar en esta BD SQLite (pruebas locales)")
    ap.add_argument("--anchor", default=dt.date.today().isoformat())
    ap.add_argument("--seed", type=int, default=20261018)
    a = ap.parse_args()
    g = Gen(dt.date.fromisoformat(a.anchor), a.seed).build()
    sql = to_sql(g)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(sql, encoding="utf-8")
    counts = {t: len(g.rows[t]) for t in TABLES}
    assert all(100 <= n <= 200 for n in counts.values()), counts
    print("Registros por tabla:", counts)
    print(f"SQL: {a.out} ({len(sql) // 1024} KB)")
    if a.sqlite:
        p = Path(a.sqlite)
        if p.exists():
            p.unlink()
        con = sqlite3.connect(p)
        for chunk in sql.split(CHUNK)[1:]:
            con.executescript(chunk)
        con.commit(); con.close()
        print(f"SQLite: {p}")


if __name__ == "__main__":
    main()
