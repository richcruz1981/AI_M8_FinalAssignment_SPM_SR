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
    ("/start", "menu"), ("/menu", "menu"), ("1️⃣ Total de proyectos", "total"), ("/total@SN_SPM_bot", "total"),
    ("2", "categorias"), ("¿cuántos abiertos y cerrados?", "categorias"), ("3️⃣ Por región", "regiones"),
    ("/programas", "programas"), ("5", "portafolios"), ("6️⃣ Calidad de datos", "calidad"), ("hola", None)])
def test_parse_intent(text, intent):
    assert parse_intent(text) == intent


def test_unauthorized_chat(rad):
    r, bot = rad
    res = r.handle(999, "/total")
    assert res["status"] == "UNAUTHORIZED" and "no está autorizado" in bot.sent[-1][1]


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
    assert all(m[2] and "keyboard" in m[2] for m in bot.sent[-1:])           # menú visible tras responder


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
    assert "No pude obtener los datos" in bot.sent[-1][1]


@pytest.mark.parametrize("text", ["PRJ1001002", "/estatus PRG0002", "/programa PRG0002", "pfl0001"])
def test_id_routes_to_status(text):
    assert parse_intent(text) == "estatus"


def test_status_project_has_19_kpis(rad):
    r, bot = rad
    res = r.handle(42, "PRJ1001002")["answer"]
    assert res["found"] and res["analyzed"]
    txt = bot.sent[-1][1]
    for n in ["1 Overall", "2 Cronograma", "3 Costo", "4 Recursos", "5 Alcance", "6 Avance", "7-8 Plan", "9-10 Real",
              "11-12 Costo", "13 Esfuerzo", "14 Hitos", "15 Riesgos", "16 Issues", "17 Decisiones", "18 Acciones",
              "19 Cambios"]:
        assert n in txt, n


def test_status_rollup_counts_match_inventory(rad):
    r, _ = rad
    res = r.handle(42, "/estatus PFL0001")["answer"]
    assert res["found"] and res["level"] == "portafolio"
    assert res["total"] == len(res["projects"])
    d = res["rollup"]["distribution"]["overall"]
    assert sum(v["n"] for v in d.values()) == res["analizados"]


def test_status_excluded_and_not_found(rad):
    r, bot = rad
    res = r.handle(42, "PRJ1001062")["answer"]                  # DQ-03 en los datos sintéticos
    assert res["found"] and not res["analyzed"] and "excluido" in res["why"]
    r.handle(42, "PRJ9999999")
    assert "No encontré" in bot.sent[-1][1]
    r.handle(42, "7️⃣ Estatus por ID (proyecto / programa / portafolio)")
    assert "Escribe el ID" in bot.sent[-1][1]
