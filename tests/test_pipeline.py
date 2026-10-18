"""Integración extremo a extremo + caos sobre la BD sintética (docs/plan/08)."""
import json
import sqlite3
from pathlib import Path

from conftest import AS_OF, no_sleep
from spm_sr.contracts import validate_contract
from spm_sr.core.orchestrator import run_pipeline
from spm_sr.zeus import Zeus
from spm_sr.zeus.senders import SendError


def _run(cfg, **kw):
    settings, schema_map, thresholds, recipients, _ = cfg
    return run_pipeline(settings, schema_map, thresholds, recipients, AS_OF, sleep=no_sleep, **kw)


def _by_number(state):
    return {r["number"]: r for r in state.thanatos["project_reports"]}


def test_end_to_end_expected_cases(cfg):
    st = _run(cfg, dry_run=True)
    assert st.cronos["signal"]["status"] == "PARTIAL"
    s = st.cronos["signal"]
    assert s["records_in"] == s["records_ok"] + s["records_excluded"]          # conciliación
    r = _by_number(st)
    assert "PRJ0011" not in r                                                   # cerrado fuera de alcance
    assert {"PRJ0007", "PRJ0009"} == set(st.thanatos["quality_summary"]["excluded_projects"])
    assert r["PRJ0001"]["health"]["overall"]["calculated"] == "Verde"
    assert r["PRJ0002"]["health"]["schedule"]["calculated"] == "Rojo"
    assert r["PRJ0002"]["health"]["overall"]["comparison"] == "Optimismo"
    assert r["PRJ0003"]["health"]["cost"]["calculated"] == "Amarillo"
    assert r["PRJ0003"]["sr_as_on"].isoformat() == "2026-10-16"                 # usa el SR más reciente
    assert r["PRJ0004"]["health"]["schedule"]["calculated"] == "Rojo"
    assert r["PRJ0005"]["health"]["cost"]["calculated"] == "DATO_FALTANTE"
    assert r["PRJ0006"]["sr_missing"] is True
    assert r["PRJ0008"]["health"]["scope"]["calculated"] == "Rojo"
    assert r["PRJ0008"]["health"]["overall"]["calculated"] == "Amarillo"
    assert r["PRJ0010"]["sr_stale"] is True
    assert r["PRJ0002"]["control"]["milestones"]["overdue"] == 1               # tarea no-hito ignorada
    assert r["PRJ0002"]["control"]["risks"]["open_high"] == 1


def test_routing_and_escalation(cfg):
    st = _run(cfg, dry_run=True)
    plan = {p["email"]: p for p in st.thanatos["recipients_plan"]}
    assert set(plan["ana.pm@example.com"]["projects"]) == {"p1", "p2", "p3"}
    assert "p10" in plan["carlos.pgm@example.com"]["escalations"]               # PM sin email -> PgM
    assert plan["marta.pfm@example.com"]["roles"] == ["PfM"]
    assert all(d["status"] == "SKIPPED" and d["reason"] == "dry-run" for d in st.zeus["deliveries"])


def test_rollup_no_color_average(cfg):
    st = _run(cfg, dry_run=True)
    pf = next(ru for ru in st.thanatos["rollups"] if ru["level"] == "Portafolio")
    d = pf["distribution"]["overall"]
    assert sum(v["n"] for v in d.values()) == pf["n_projects"] == 8
    assert pf["worst_overall"] == "Rojo"
    assert pf["cpi"]["min"] <= pf["cpi"]["median"] <= pf["cpi"]["max"]


def test_contracts_valid(cfg):
    st = _run(cfg, dry_run=True)
    validate_contract("C1", st.cronos)
    validate_contract("C2", st.thanatos)
    validate_contract("C3", st.zeus)


def test_scope_program_only(cfg):
    st = _run(cfg, dry_run=True, scope=["program:PRG002"])
    assert set(_by_number(st)) == {"PRJ0006", "PRJ0008", "PRJ0010"}


def test_db_missing_fails_and_reports(cfg):
    settings = cfg[0]
    settings["db"]["url"] = "sqlite:///" + str(cfg[4] / "no_existe.db")
    st = _run(cfg, dry_run=True)
    assert st.final_status().value == "FAILED"
    assert st.thanatos is None
    assert st.zeus["mode"] == "failure"
    assert any(e.code == "E-CONN-01" for e in st.errors)
    assert (Path(settings["runs_dir"]) / AS_OF.isoformat() / "failure_report.md").exists()


def test_core_table_missing_fails(cfg):
    con = sqlite3.connect(cfg[0]["db"]["url"].replace("sqlite:///", ""))
    con.execute("DROP TABLE project_status")
    con.commit(); con.close()
    st = _run(cfg, dry_run=True)
    assert st.cronos["signal"]["status"] == "FAILED"
    assert any(e.code == "E-SCHEMA-01" for e in st.errors)


def test_aux_table_missing_is_partial(cfg):
    con = sqlite3.connect(cfg[0]["db"]["url"].replace("sqlite:///", ""))
    con.execute("DROP TABLE risk")
    con.execute("DROP TABLE project_change_request")
    con.commit(); con.close()
    st = _run(cfg, dry_run=True)
    assert st.cronos["signal"]["status"] == "PARTIAL"
    r = _by_number(st)["PRJ0002"]
    assert r["control"]["risks"] == "DATO_FALTANTE"
    assert r["health"]["scope"]["calculated"] == "DATO_FALTANTE"               # no Verde por omisión


class FakeTelegram:
    configured = True

    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, chat_id, text):
        if self.fail:
            raise SendError("telegram caído")
        assert len(text) <= 4096
        self.sent.append(chat_id)
        return f"tg-{len(self.sent)}"


RECIPS = {"recipients": [{"email": "ana.pm@example.com", "telegram_chat_id": "111", "channels": ["telegram"]},
                         {"email": "sofia.pgm@example.com", "telegram_chat_id": "222", "channels": ["telegram"]}]}


def test_real_send_idempotent_and_skips_missing_chat(cfg):
    settings = cfg[0]
    tg = FakeTelegram()
    z = Zeus(settings, RECIPS, telegram_sender=tg, sleep=no_sleep)
    st = _run(cfg, dry_run=False, zeus=z)
    sent = [d for d in st.zeus["deliveries"] if d["status"] == "SENT"]
    assert {d["target"] for d in sent} == {"111", "222"}
    assert any(d["status"] == "SKIPPED" and d["reason"] == "sin destino telegram" for d in st.zeus["deliveries"])
    n = len(tg.sent)
    st2 = _run(cfg, dry_run=False, zeus=z)                                       # misma fecha
    assert len(tg.sent) == n                                                     # 0 duplicados
    assert all(d["reason"] == "ya enviado en este turno (idempotencia)" for d in st2.zeus["deliveries"] if d["target"] in ("111", "222"))



def test_second_slot_same_day_sends_again(cfg, monkeypatch):
    """Dos envíos al día: el turno de la tarde (SR_SLOT=pm) no se bloquea por el de la mañana."""
    tg = FakeTelegram()
    z = Zeus(cfg[0], RECIPS, telegram_sender=tg, sleep=no_sleep)
    monkeypatch.setenv("SR_SLOT", "am")
    _run(cfg, dry_run=False, zeus=z)
    n = len(tg.sent)
    _run(cfg, dry_run=False, zeus=z)
    assert len(tg.sent) == n                                                     # mismo turno: sin duplicados
    monkeypatch.setenv("SR_SLOT", "pm")
    _run(cfg, dry_run=False, zeus=z)
    assert len(tg.sent) == 2 * n                                                 # turno de la tarde: se envía

def test_redirect_sends_everything_to_one_chat_with_original_recipient(cfg):
    settings = cfg[0]
    settings["notifications"]["redirect_telegram_chat_id"] = "999"
    tg = FakeTelegram()
    z = Zeus(settings, {}, telegram_sender=tg, sleep=no_sleep)
    st = _run(cfg, dry_run=False, zeus=z)
    assert tg.sent and set(tg.sent) == {"999"}
    outbox = Path(settings["runs_dir"]) / AS_OF.isoformat() / "outbox"
    msg = json.loads(next(outbox.glob("*telegram.json")).read_text())["messages"][0]
    assert "Destinatario original" in msg


def test_send_failure_retries_and_fails(cfg):
    z = Zeus(cfg[0], RECIPS, telegram_sender=FakeTelegram(fail=True), sleep=no_sleep)
    st = _run(cfg, dry_run=False, zeus=z)
    assert st.zeus["signal"]["status"] == "FAILED"
    assert all(d["attempt"] == 3 for d in st.zeus["deliveries"] if d["status"] == "FAILED")


def test_long_message_is_split():
    import datetime as dt
    from spm_sr.zeus import render
    rep = {"number": "PRJ1", "name": "x" * 50, "alerts": ["a"] * 3, "sr_missing": False, "sr_stale": False,
           "health": {k: {"calculated": "Rojo", "declared": "Verde"} for k in ("overall", "schedule", "cost", "resources", "scope")},
           "performance": {"schedule": {"percent_complete": 10.0, "expected_pct": 50.0, "gap_pp": -40.0}, "cost": {"cpi": 0.8}},
           "control": {}}
    msgs = render.telegram({"roles": ["PM"], "name": "Ana"}, [rep] * 80, [], [], dt.date(2026, 10, 18), True, None)
    assert len(msgs) > 1 and all(len(m) <= 4096 for m in msgs)


def test_snapshot_replay(cfg):
    _run(cfg, dry_run=True)
    st = _run(cfg, dry_run=True, agents=["thanatos", "zeus"])                   # reusa cronos.json
    assert _by_number(st)["PRJ0002"]["health"]["schedule"]["calculated"] == "Rojo"
    snap = json.loads((Path(cfg[0]["runs_dir"]) / AS_OF.isoformat() / "thanatos.json").read_text())
    assert snap["project_reports"]
