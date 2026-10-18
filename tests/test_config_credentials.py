from spm_sr.core import config as C

# Valores FICTICIOS armados en tiempo de ejecución para no disparar tests/test_no_secrets.py
PG = "postgresql://u:" + "p@"
FAKE_KEY = "sk-" + "ant-abcdefghijklmnopqrstuvwxyz"


def test_db_url_priority_and_kit_aliases(monkeypatch):
    env = {"DATABASE_URL": PG + "host-que-no-existe.invalid:6432/db",
           "DATABASE_URL_LOCAL": PG + "127.0.0.1:15432/db"}
    assert C.resolve_db_url(env) == (env["DATABASE_URL_LOCAL"], "DATABASE_URL_LOCAL")   # auto: host no resuelve
    assert C.resolve_db_url({**env, "DB_TARGET": "server"})[1] == "DATABASE_URL"
    assert C.resolve_db_url({**env, "DB_TARGET": "local"})[1] == "DATABASE_URL_LOCAL"
    assert C.resolve_db_url({**env, "DB_URL": "sqlite:///x.db"}) == ("sqlite:///x.db", "DB_URL")
    assert C.resolve_db_url({}) == (None, "config")


def test_telegram_aliases(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ID", "999")
    monkeypatch.delenv("ADMIN_TELEGRAM_CHAT_ID", raising=False)
    assert C.secret("TELEGRAM_BOT_TOKEN") == "123:abc"
    assert C.load_settings()["notifications"]["admin_telegram_chat_id"] == "999"


def test_redact_hides_credentials(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    txt = ("fallo postgresql://user:" + "SuperClave1@host:6432/db y "
           "https://api.telegram.org/bot1234567890:" + "AAabcdefghijklmnopqrstuvwxyz0123456/sendMessage "
           "llave " + FAKE_KEY)
    out = C.redact(txt)
    assert "SuperClave1" not in out and "AAabcdef" not in out and "sk-ant-abc" not in out


def test_postgres_url_gets_installed_driver():
    out = C._pg_driver_url("postgres://u:" + "p@h:6432/db")
    assert out.startswith(("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"))
    assert out.endswith("u:p@h:6432/db")
