import datetime as dt
import sqlite3

from conftest import no_sleep
from scripts.generate_spm_dummy import CHUNK, TABLES, Gen, to_sql
from spm_sr.core.config import load_all
from spm_sr.core.orchestrator import run_pipeline

ANCHOR = dt.date(2026, 10, 18)


def test_each_table_between_100_and_200_rows():
    g = Gen(ANCHOR, 20261018).build()
    counts = {t: len(g.rows[t]) for t in TABLES}
    assert all(100 <= n <= 200 for n in counts.values()), counts


def test_dummy_data_exercises_all_colors(tmp_path):
    sql = to_sql(Gen(ANCHOR, 20261018).build())
    db = tmp_path / "dummy.db"
    con = sqlite3.connect(db)
    for chunk in sql.split(CHUNK)[1:]:
        con.executescript(chunk)
    con.commit(); con.close()
    settings, schema_map, thresholds, recipients = load_all()
    settings["db"]["url"] = f"sqlite:///{db}"
    settings["runs_dir"] = str(tmp_path / "runs")
    settings["llm"]["enabled"] = False
    st = run_pipeline(settings, schema_map, thresholds, recipients, ANCHOR, dry_run=True, sleep=no_sleep)
    colors = {r["health"]["overall"]["calculated"] for r in st.thanatos["project_reports"]}
    assert {"Verde", "Amarillo", "Rojo"} <= colors
    assert st.cronos["signal"]["records_excluded"] > 0                      # hay casos DQ
    assert any(r["health"]["overall"]["comparison"] == "Optimismo" for r in st.thanatos["project_reports"])
