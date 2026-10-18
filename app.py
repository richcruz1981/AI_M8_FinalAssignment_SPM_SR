"""App en vivo del servidor del curso (hatchvps): arranca el bot Radamantis en un hilo y muestra su estado.

El servidor solo mantiene vivo app.py (los demás .py los ejecuta como scripts de 150 s en un entorno sin
librerías). Por eso el bot de Telegram vive aquí. @st.cache_resource garantiza UN solo bot y UNA sola
conexión compartida, como pide el kit.
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

st.set_page_config(page_title="SR SPM · Radamantis", page_icon="📊", layout="wide")


@st.cache_resource
def bot() -> BotRunner:
    setup_logging(None)
    runner = BotRunner()
    threading.Thread(target=runner.run, name="radamantis", daemon=True).start()
    return runner


runner = bot()
s = runner.status
st.title("📊 SR de proyectos · Bot Radamantis")
st.caption("Cronos (lee) → Thanatos (analiza) → Zeus (comunica), orquestados por Radamantis desde Telegram. "
           "Datos **sintéticos** de demostración.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Estado del bot", s["state"])
c2.metric("Peticiones atendidas", s["handled"])
c3.metric("Errores", s["errors"])
c4.metric("Chats autorizados", s["allowed_chats"])
st.write(f"Inicio: `{s['started_at']}` · último polling: `{s['last_poll']}` · BD: `{s['db_origin']}`")
if s.get("last_error"):
    st.warning(f"Último error: {s['last_error']}")
if s["by_intent"]:
    st.bar_chart(s["by_intent"])

st.subheader("Resumen (mismas consultas que el bot)")
try:
    c, t, when, _ = runner.rad._data()
    if c["signal"]["status"] == "FAILED":
        st.error("No se pudo leer la base de datos.")
    else:
        tot = queries.total(c, t)
        a, b, cc = st.columns(3)
        a.metric("Total de proyectos", tot["total"])
        b.metric("Activos", tot["activos"])
        cc.metric("Con problemas de datos", queries.data_quality(c, t)["proyectos_afectados"])
        l, r = st.columns(2)
        l.write("**Por categoría**")
        l.dataframe([{"Categoría": x["categoria"], "Proyectos": x["n"]} for x in queries.by_category(c)["rows"]],
                    hide_index=True, use_container_width=True)
        r.write("**Por región**")
        r.dataframe([{"Región": x["region"], "Proyectos": x["n"], "Activos": x["activos"]}
                     for x in queries.by_region(c)["rows"]], hide_index=True, use_container_width=True)
        st.caption(f"Datos leídos {when}. Telegram: /total, /categorias, /regiones, /programas, /portafolios, /calidad")
except Exception as e:  # noqa: BLE001
    st.error(f"Error leyendo datos: {type(e).__name__}")

if st.button("Actualizar"):
    st.rerun()
st.caption(f"Página generada {dt.datetime.now().strftime('%H:%M:%S')}")
