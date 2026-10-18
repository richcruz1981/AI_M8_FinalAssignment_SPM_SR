"""App en vivo del servidor del curso (hatchvps): arranca el bot Radamantis en un hilo y muestra su estado.

El servidor solo mantiene vivo app.py (los demás .py los ejecuta como scripts de 150 s en un entorno sin
librerías). Por eso el bot de Telegram vive aquí. @st.cache_resource garantiza UN solo bot y UNA sola
conexión compartida, como pide el kit. La interfaz está en inglés.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from html import escape
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

from spm_sr.cerbero import verify_chain  # noqa: E402
from spm_sr.core.logging_setup import setup_logging  # noqa: E402
from spm_sr.radamantis.runner import BotRunner  # noqa: E402
from spm_sr.thanatos import queries  # noqa: E402
from spm_sr.zeus import i18n  # noqa: E402

st.set_page_config(page_title="SPM Status Reports · Radamantis", page_icon="📊", layout="wide")

# PepsiCo palette (navy #28458E, electric blue #0096D6, tangelo #EB7B30) — same as the web dashboard
NAVY, BLUE, TANGELO, INK, INK2 = "#28458E", "#0096D6", "#EB7B30", "#14213D", "#5B6475"
st.markdown(f"""<style>
  .stApp {{ background:#F4F6FA; }}
  header[data-testid="stHeader"] {{ background:transparent; }}
  .block-container {{ padding-top:1.2rem; }}
  .pf-hero {{ background:linear-gradient(110deg,{NAVY} 0%,#1F3A7D 60%,#0B6FAE 100%); color:#fff; border-radius:14px;
             padding:20px 26px; margin-bottom:18px; border-bottom:4px solid {TANGELO}; }}
  .pf-hero h1 {{ color:#fff; font-size:1.7rem; margin:0; padding:0; }}
  .pf-hero p {{ color:#DCE6F5; margin:.35rem 0 0; font-size:.92rem; }}
  .pf-hero a {{ color:#FFB98A; font-weight:600; }}
  .pf-row {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; }}
  .pf-row > div:first-child {{ flex:1 1 auto; min-width:0; }}
  @media (max-width: 700px) {{ .pf-row {{ flex-direction:column; }} .pf-stamp {{ text-align:left; }} }}
  .pf-stamp {{ text-align:right; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.25);
              border-radius:10px; padding:8px 12px; flex:0 0 auto; white-space:nowrap; }}
  .pf-stamp span {{ display:block; font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; color:#BFE6FA; }}
  .pf-stamp b {{ color:#fff; font-size:.95rem; }}
  div[data-testid="stMetric"] {{ background:#fff; border:1px solid #E1E6EE; border-top:4px solid {NAVY};
             border-radius:12px; padding:12px 16px; }}
  div[data-testid="stMetricValue"] {{ color:{INK}; }}
  div[data-testid="stMetricLabel"] p {{ color:{INK2}; font-weight:600; }}
  h2, h3 {{ color:{NAVY} !important; }}
  .stButton > button {{ background:{NAVY}; color:#fff; border:0; border-radius:8px; }}
  .stButton > button:hover {{ background:{BLUE}; color:#fff; }}
  a {{ color:{BLUE}; }}
  span[data-baseweb="tag"] {{ background:{NAVY} !important; }}
</style>""", unsafe_allow_html=True)

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
guard = runner.rad.guard

# Read data first so the header can show when the database was last queried
data_err = None
try:
    c, t, when, _ = runner.rad._data()
except Exception as e:  # noqa: BLE001
    c, t, when, data_err = None, None, None, type(e).__name__
last_db = runner.rad.last_db_read or "not queried yet"

st.markdown(
    '<div class="pf-hero"><div class="pf-row"><div><h1>📊 Project Status Reports · Radamantis bot</h1>'
    "<p>Cronos (reads) → Thanatos (analyzes) → Zeus (communicates), guarded by Cerbero, orchestrated by "
    "Radamantis from Telegram. <b>Synthetic</b> demo data. · <a href=\"../dashboard/\">Portfolio Health Dashboard</a>"
    " · <a href=\"../\">Proyecto Final Edgar Cruz</a></p></div>"
    f'<div class="pf-stamp"><span>Last DB query</span><b>{escape(last_db)}</b></div></div></div>',
    unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Bot status", s["state"])
c2.metric("Requests handled", s["handled"])
c3.metric("Errors", s["errors"])
c4.metric("Authorized chats", s["allowed_chats"])
st.write(f"Started: `{s['started_at']}` · last poll: `{s['last_poll']}` · DB: `{s['db_origin']}`")
if s.get("last_error"):
    st.warning(f"Last error: {s['last_error']}")
if s["by_intent"]:
    data = {INTENT_EN.get(k, k): v for k, v in s["by_intent"].items()}
    try:
        st.bar_chart(data, color=BLUE)
    except TypeError:  # older Streamlit without the color argument
        st.bar_chart(data)

st.subheader("Summary (same queries as the bot)")
if data_err:
    st.error(f"Error reading data: {data_err}")
elif c["signal"]["status"] == "FAILED":
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

# ------------------------------------------------------------------ security audit log (Cerbero)
st.subheader("🛡️ Security audit log · Cerbero")
st.caption("Every agent action passes a security gate: inbound (Telegram messages), data (database fields), "
           "llm_in / llm_out (AI narrative) and outbound (every message sent). Entries are hash-chained per "
           "session; message content is never stored, only its SHA-256. Chat IDs are masked.")
try:
    rows = guard.audit.fetch(limit=400)
except Exception as e:  # noqa: BLE001
    rows = list(guard.audit.recent)[::-1]
    st.warning(f"Audit table not reachable ({type(e).__name__}); showing this process only.")


def _cdmx(ts: str) -> str:
    try:
        d = dt.datetime.fromisoformat(ts)
        return (d + dt.timedelta(hours=-6)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return str(ts)


now_utc = dt.datetime.now(dt.timezone.utc)
day = [r for r in rows if r.get("ts") and dt.datetime.fromisoformat(r["ts"]) > now_utc - dt.timedelta(hours=24)]
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Events (24 h)", len(day))
k2.metric("Blocked (24 h)", sum(r["decision"] == "BLOCK" for r in day))
k3.metric("Sanitized (24 h)", sum(r["decision"] == "SANITIZE" for r in day))
k4.metric("Agent halts (24 h)", sum(r["decision"] == "HALT" for r in day))
k5.metric("Chats in quarantine", len(guard.quarantined()))

sessions = sorted({r["session"] for r in rows if r.get("session")}, reverse=True)[:6]
checks = []
for sess in sessions:
    ok, idx = verify_chain(guard.audit.fetch_session(sess))
    checks.append({"Session": sess, "Chain": "✅ intact" if ok else f"❌ broken at entry {idx}"})
if checks:
    st.write("**Chain integrity (latest sessions)**")
    st.dataframe(checks, hide_index=True, use_container_width=True)

f1, f2, f3 = st.columns(3)
src_opts = sorted({r["source"] for r in rows if r.get("source")})
dec_opts = ["ALLOW", "SANITIZE", "BLOCK", "QUARANTINE", "HALT", "ERROR"]
gate_opts = sorted({r["gate"] for r in rows if r.get("gate")})
f_src = f1.multiselect("Source", src_opts, default=src_opts)
f_dec = f2.multiselect("Decision", dec_opts, default=["SANITIZE", "BLOCK", "QUARANTINE", "HALT", "ERROR"])
f_gate = f3.multiselect("Gate", gate_opts, default=gate_opts)
view = [r for r in rows if r.get("source") in f_src and r.get("decision") in f_dec and r.get("gate") in f_gate]
st.dataframe([{"Time (CDMX)": _cdmx(r["ts"]), "Source": r["source"], "Agent": r["agent"], "Action": r["action"],
               "Gate": r["gate"], "Decision": r["decision"], "Severity": r["severity"],
               "Reasons": ", ".join(json.loads(r["reasons"] or "[]")), "Subject": r["subject"]} for r in view],
             hide_index=True, use_container_width=True, height=360)
st.caption(f"{len(view)} of {len(rows)} most recent events shown. Store: table security_audit_log in the project "
           "database (shared by the bot on this server and the GitHub Actions runs).")

if st.button("Refresh"):
    st.rerun()
st.caption(f"Page generated {dt.datetime.now().strftime('%H:%M:%S')}")
