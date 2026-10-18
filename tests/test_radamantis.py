"""Radamantis (bot): intención, autorización, las 6 consultas y respuesta vía Zeus sobre la BD sintética."""
import datetime as dt
import sqlite3

import pytest

from conftest import no_sleep
from scripts.generate_spm_dummy import CHUNK, Gen, to_sql
from spm_sr.core.config import load_all
from spm_sr.radamantis import Radamantis, parse_intent
from spm_sr.zeus import Zeus

ANCHOR = dt.date(2026, 10, 18)


class FakeBot:
    configured = True

    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, reply_markup=None):
        assert len(text) <= 4096
        self.sent.append((str(chat_id), text, reply_markup))
        return str(len(self.sent))

    def send_photo(self, chat_id, png, caption="", reply_markup=None):
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(caption) <= 1024
        self.photos = getattr(self, "photos", []) + [(str(chat_id), len(png), reply_markup)]
        return "p"


@pytest.fixture(scope="module")
def dummy_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("bot") / "dummy.db"
    con = sqlite3.connect(db)
    for chunk in to_sql(Gen(ANCHOR, 20261018).build()).split(CHUNK)[1:]:
        con.executescript(chunk)
    con.commit(); con.close()
    return db


@pytest.fixture
def rad(dummy_db, tmp_path):
    settings, schema_map, thresholds, recipients = load_all()
    settings["db"]["url"] = f"sqlite:///{dummy_db}"
    settings["runs_dir"] = str(tmp_path / "runs")
    bot = FakeBot()
    z = Zeus(settings, {}, telegram_sender=bot, sleep=no_sleep)
    r = Radamantis(settings, schema_map, thresholds, z, allowed_chat_ids={"42"}, today=lambda: ANCHOR)
    return r, bot


@pytest.mark.parametrize("text,intent", [
    ("/start", "menu"), ("/menu", "menu"), ("1️⃣ Total projects", "total"), ("/total@SN_SPM_bot", "total"),
    ("2", "categorias"), ("how many open and closed?", "categorias"), ("3️⃣ By region", "regiones"),
    ("/programs", "programas"), ("4️⃣ By program", "programas"), ("5", "portafolios"), ("5️⃣ By portfolio", "portafolios"),
    ("6️⃣ Data quality", "calidad"), ("/dataquality", "calidad"), ("/categories", "categorias"), ("/regions", "regiones"),
    ("/portfolios", "portafolios"), ("/programas", "programas"), ("6️⃣ Calidad de datos", "calidad"), ("hello", None)])
def test_parse_intent(text, intent):
    assert parse_intent(text) == intent


def test_unauthorized_chat(rad):
    r, bot = rad
    res = r.handle(999, "/total")
    assert res["status"] == "UNAUTHORIZED" and "not authorized" in bot.sent[-1][1]


def test_six_options_answer_with_real_counts(rad):
    r, bot = rad
    out = {i: r.handle(42, t)["answer"] for i, t in
           [("total", "1"), ("categorias", "2"), ("regiones", "3"), ("programas", "4"), ("portafolios", "5"),
            ("calidad", "6")]}
    tot = out["total"]["total"]
    assert tot == 150 and out["total"]["activos"] + out["total"]["cerrados_cancelados"] == tot
    assert sum(x["n"] for x in out["categorias"]["rows"]) == tot
    assert {x["categoria"] for x in out["categorias"]["rows"]} >= {"En progreso", "Cerrado"}
    assert sum(x["n"] for x in out["regiones"]["rows"]) == tot
    assert any(x["region"] == "(sin región)" for x in out["regiones"]["rows"])
    assert sum(x["n"] for x in out["programas"]["rows"]) == tot
    assert sum(x["n"] for x in out["portafolios"]["rows"]) == tot
    assert out["programas"]["con_proyectos"] + out["programas"]["sin_proyectos"] == 100
    rules = {x["rule"] for x in out["calidad"]["rows"]}
    assert {"DQ-01", "DQ-03", "DQ-04", "DQ-10"} <= rules
    assert len(bot.photos) == 6 and all(p[2] and "keyboard" in p[2] for p in bot.photos)   # 1 gráfica por opción + menú


def test_cache_avoids_rereading_db(rad, monkeypatch):
    r, _ = rad
    r.handle(42, "1")
    calls = []
    import spm_sr.radamantis.agent as A
    monkeypatch.setattr(A.Cronos, "run", lambda self, st: calls.append(1) or {})
    r.handle(42, "2")
    assert calls == []


def test_db_failure_replies_friendly_error(rad):
    r, bot = rad
    r.settings["db"]["url"] = "sqlite:////no/existe.db"
    r._cache = None
    res = r.handle(42, "1")
    assert res["status"] == "FAILED" and res["error"] == "E-CONN-01"
    assert "couldn't retrieve the data" in bot.sent[-1][1]


@pytest.mark.parametrize("text", ["PRJ1001002", "/status PRG0002", "/estatus PRG0002", "/programs PRG0002", "pfl0001", "7️⃣ Status by ID (project / program / portfolio)"])
def test_id_routes_to_status(text):
    assert parse_intent(text) == "estatus"


def test_status_project_has_19_kpis(rad):
    r, bot = rad
    res = r.handle(42, "PRJ1001002")["answer"]
    assert res["found"] and res["analyzed"]
    txt = bot.sent[-1][1]
    for n in ["1 Overall", "2 Schedule", "3 Cost", "4 Resources", "5 Scope", "6 Progress", "7-8 Planned", "9-10 Actual",
              "11-12 Cost", "13 Effort", "14 Milestones", "15 Risks", "16 Issues", "17 Decisions", "18 Actions",
              "19 Change requests"]:
        assert n in txt, n


def test_status_rollup_counts_match_inventory(rad):
    r, _ = rad
    res = r.handle(42, "/status PFL0001")["answer"]
    assert res["found"] and res["level"] == "portafolio"
    assert res["total"] == len(res["projects"])
    d = res["rollup"]["distribution"]["overall"]
    assert sum(v["n"] for v in d.values()) == res["analizados"]


def test_status_excluded_and_not_found(rad):
    r, bot = rad
    res = r.handle(42, "PRJ1001062")["answer"]                  # DQ-03 en los datos sintéticos
    assert res["found"] and not res["analyzed"] and "excluido" in res["why"]
    r.handle(42, "PRJ9999999")
    assert "couldn't find project" in bot.sent[-1][1]
    r.handle(42, "7️⃣ Status by ID (project / program / portfolio)")
    assert "Type the ID" in bot.sent[-1][1]


@pytest.mark.parametrize("code", ["PRJ1001002", "PRG0002", "PFL0001"])
def test_status_sends_chart(rad, code):
    r, bot = rad
    res = r.handle(42, code)
    assert res["chart"] is True and bot.photos[-1][1] > 10_000


def test_no_chart_for_excluded_project_still_answers_text(rad):
    r, bot = rad
    res = r.handle(42, "PRJ1001062")
    assert res["chart"] is False and "No KPIs" in bot.sent[-1][1] and bot.sent[-1][2]   # menú va con el texto


SPANISH = ["Proyectos", "proyecto", "Salud", "Costo", "Riesgos", "Hitos", "datos leídos", "Fuente", "Calidad", "Sin ",
           "Verde", "Amarillo", "Rojo", "DATO_FALTANTE", "Abierto", "En progreso", "Cerrado", "pendientes", "vencid",
           "Alta", "Media", "Baja", "región", "activos"]


def test_all_replies_are_in_english(rad):
    """Labels written by the bot must be English (names stored in the DB may stay in Spanish)."""
    r, bot = rad
    for t in ["/start", "1", "2", "3", "4", "5", "6", "7", "PRJ1001002", "PRJ1001062", "PRG0002", "PFL0001", "zzz"]:
        r.handle(42, t)
    import re
    for _, text, _ in bot.sent:
        # strip project/program names and states that come from the database
        clean = re.sub(r"<b>(PRJ|PRG|PFL)\d+</b>[^\n]*", "", text)
        clean = re.sub(r"\((?:[a-z_]+|\(empty\))\)", "", clean)
        clean = re.sub(r"(Region|PM|Owner): [^·\n]*", "", clean)
        clean = re.sub(r"— [^\n]*", "", clean) if "Projects by category" in text else clean
        clean = re.sub(r"• <b>[^<]*</b>(?: [^:]*)?:", "•", clean)
        for w in SPANISH:
            assert w not in clean, (w, clean[:400])
