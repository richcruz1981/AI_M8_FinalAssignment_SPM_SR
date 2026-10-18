"""Migración NO destructiva: agrega el campo personalizado u_region a pm_project y lo llena (datos sintéticos).

Usa la misma asignación determinista que generate_spm_dummy.py. Requiere DB_URL / DATABASE_URL(_LOCAL).
Uso: python scripts/migrate_add_region.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from scripts.generate_spm_dummy import region_for  # noqa: E402
from spm_sr.core.config import load_settings  # noqa: E402


def main() -> int:
    url = load_settings()["db"]["url"]
    eng = create_engine(url)
    with eng.begin() as con:
        cols = {c["name"] for c in inspect(con).get_columns("pm_project")}
        if "u_region" not in cols:
            con.execute(text("ALTER TABLE pm_project ADD COLUMN u_region varchar(30)"))
            print("Columna u_region creada")
        rows = con.execute(text("SELECT sys_id, number FROM pm_project")).all()
        for sid, number in rows:
            con.execute(text("UPDATE pm_project SET u_region = :r WHERE sys_id = :s"), {"r": region_for(number), "s": sid})
        res = con.execute(text("SELECT coalesce(u_region, '(sin región)'), count(*) FROM pm_project GROUP BY 1 ORDER BY 2 DESC")).all()
    print(f"Proyectos actualizados: {len(rows)}")
    for r, n in res:
        print(f"  {r}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
