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
