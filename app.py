"""App en vivo del servidor del curso (hatchvps): arranca el bot Radamantis en un hilo y muestra su estado.

El servidor solo mantiene vivo app.py (los demás .py los ejecuta como scripts de 150 s en un entorno sin
librerías). Por eso el bot de Telegram vive aquí. @st.cache_resource garantiza UN solo bot y UNA sola
conexión compartida, como pide el kit. La interfaz está en inglés.
"""
from __future__ import annotations

import datetime as dt
import sys
import threading
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "spm_sr.zip") if (HERE / "spm_sr.zip").exists() else str(HERE / "src"))
try:
    from dotenv import load_dotenv

    load_dotenv(HERE / ".env")
except ImportError:
    pass

from spm_sr.core.logging_setup import setup_logging  # noqa: E402
from spm_sr.radamantis.runner import BotRunner  # noqa: E402
from spm_sr.thanatos import queries  # noqa: E402
from spm_sr.zeus import i18n  # noqa: E402

st.set_page_config(page_title="SPM Status Reports · Radamantis", page_icon="📊", layout="wide")

INTENT_EN = {"total": "Total", "categorias": "Categories", "regiones": "Regions", "programas": "Programs",
             "portafolios": "Portfolios", "calidad": "Data quality", "estatus": "Status by ID", "menu": "Menu"}


@st.cache_resource
def bot() -> BotRunner:
    setup_logging(None)
    runner = BotRunner()
    threading.Thread(target=runner.run, name="radamantis", daemon=True).start()
    return runner


runner = bot()
s = runner.status
st.title("📊 Project Status Reports · Radamantis bot")
st.caption("Cronos (reads) → Thanatos (analyzes) → Zeus (communicates), orchestrated by Radamantis from Telegram. "
           "**Synthetic** demo data. Dashboard: [Portfolio Health Dashboard](../)")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Bot status", s["state"])
c2.metric("Requests handled", s["handled"])
c3.metric("Errors", s["errors"])
c4.metric("Authorized chats", s["allowed_chats"])
st.write(f"Started: `{s['started_at']}` · last poll: `{s['last_poll']}` · DB: `{s['db_origin']}`")
if s.get("last_error"):
    st.warning(f"Last error: {s['last_error']}")
if s["by_intent"]:
    st.bar_chart({INTENT_EN.get(k, k): v for k, v in s["by_intent"].items()})

st.subheader("Summary (same queries as the bot)")
try:
    c, t, when, _ = runner.rad._data()
    if c["signal"]["status"] == "FAILED":
        st.error("Could not read the database.")
    else:
        tot = queries.total(c, t)
        a, b, cc = st.columns(3)
        a.metric("Total projects", tot["total"])
        b.metric("Active", tot["activos"])
        cc.metric("With data-quality issues", queries.data_quality(c, t)["proyectos_afectados"])
        l, r = st.columns(2)
        l.write("**By category**")
        l.dataframe([{"Category": i18n.cat(x["categoria"]), "Projects": x["n"]} for x in queries.by_category(c)["rows"]],
                    hide_index=True, use_container_width=True)
        r.write("**By region**")
        r.dataframe([{"Region": i18n.ph(x["region"]), "Projects": x["n"], "Active": x["activos"]}
                     for x in queries.by_region(c)["rows"]], hide_index=True, use_container_width=True)
        st.caption(f"Data read {when}. Telegram: /total, /categories, /regions, /programs, /portfolios, "
                   "/dataquality, /status <ID>")
except Exception as e:  # noqa: BLE001
    st.error(f"Error reading data: {type(e).__name__}")

if st.button("Refresh"):
    st.rerun()
st.caption(f"Page generated {dt.datetime.now().strftime('%H:%M:%S')}")
