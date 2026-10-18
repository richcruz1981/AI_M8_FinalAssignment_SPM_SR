from __future__ import annotations

import copy
import os
import re
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "si", "sí", "y")


def _host_resolves(url: str) -> bool:
    try:
        from sqlalchemy.engine import make_url

        host = make_url(url).host
        if not host:
            return True
        socket.gethostbyname(host)
        return True
    except Exception:  # noqa: BLE001
        return False


def resolve_db_url(env: Mapping[str, str] | None = None) -> tuple[str | None, str]:
    """Prioridad: DB_URL > variables del kit del curso (DATABASE_URL / DATABASE_URL_LOCAL).

    DB_TARGET=server usa DATABASE_URL (app desplegada en el servidor), DB_TARGET=local usa DATABASE_URL_LOCAL
    (túnel desde tu computadora). DB_TARGET=auto (default): DATABASE_URL si su host resuelve; si no, la local.
    """
    env = os.environ if env is None else env
    if env.get("DB_URL"):
        return env["DB_URL"], "DB_URL"
    server, local = env.get("DATABASE_URL", "").strip(), env.get("DATABASE_URL_LOCAL", "").strip()
    target = env.get("DB_TARGET", "auto").strip().lower()
    if target == "local" and local:
        return local, "DATABASE_URL_LOCAL"
    if target == "server" and server:
        return server, "DATABASE_URL"
    if server and (_host_resolves(server) or not local):
        return server, "DATABASE_URL"
    if local:
        return local, "DATABASE_URL_LOCAL"
    return None, "config"


def _pg_driver_url(url: str) -> str:
    """'postgresql://' sin driver -> el driver instalado (psycopg 3 o psycopg2). Evita depender del default de SQLAlchemy."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql://"):
        return url
    import importlib.util

    for module, dialect in (("psycopg", "postgresql+psycopg://"), ("psycopg2", "postgresql+psycopg2://")):
        if importlib.util.find_spec(module):
            return dialect + url[len("postgresql://"):]
    return url


def load_settings(path: str | Path = "config/settings.yaml") -> dict[str, Any]:
    s = copy.deepcopy(_load_yaml(path))
    env = os.environ
    url, origin = resolve_db_url(env)
    if url:
        s["db"]["url"] = _pg_driver_url(url)
    s["db"]["url_origin"] = origin
    if env.get("SCOPE"):
        s["scope"] = [x.strip() for x in env["SCOPE"].split(",") if x.strip()]
    if env.get("DRY_RUN"):
        s["notifications"]["dry_run"] = _bool(env["DRY_RUN"])
    if env.get("LLM_MODEL"):
        s["llm"]["model"] = env["LLM_MODEL"]
    if env.get("LLM_ENABLED"):
        s["llm"]["enabled"] = _bool(env["LLM_ENABLED"])
    for key, env_keys in (("admin_email", ("ADMIN_EMAIL",)),
                          ("admin_telegram_chat_id", ("ADMIN_TELEGRAM_CHAT_ID", "TELEGRAM_ID")),
                          ("redirect_all_to", ("REDIRECT_ALL_TO",)),
                          ("redirect_telegram_chat_id", ("REDIRECT_TELEGRAM_CHAT_ID",))):
        val = next((env[k] for k in env_keys if env.get(k)), None)
        if val:
            s["notifications"][key] = val
    if env.get("RUNS_DIR"):
        s["runs_dir"] = env["RUNS_DIR"]
    if env.get("RECIPIENTS_FILE"):
        s["recipients_file"] = env["RECIPIENTS_FILE"]
    # SQLite relativo -> relativo a la raíz del repo
    url = s["db"]["url"]
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///"):]
        if rel and rel != ":memory:" and not Path(rel).is_absolute():
            s["db"]["url"] = "sqlite:///" + str((ROOT / rel).resolve())
    rd = Path(s.get("runs_dir", "runs"))
    s["runs_dir"] = str(rd if rd.is_absolute() else ROOT / rd)
    return s


def load_all(settings_path: str | Path = "config/settings.yaml") -> tuple[dict, dict, dict, dict]:
    settings = load_settings(settings_path)
    schema_map = _load_yaml(settings.get("schema_map", "config/schema_map.yaml"))
    thresholds = _load_yaml(settings.get("thresholds", "config/thresholds.yaml"))
    recipients = _load_yaml(settings.get("recipients_file", "config/recipients.yaml"))
    return settings, schema_map, thresholds, recipients


SECRET_ALIASES = {"TELEGRAM_BOT_TOKEN": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN")}
SECRET_ENV_KEYS = ("DB_URL", "DATABASE_URL", "DATABASE_URL_LOCAL", "DB_PASSWORD", "SMTP_PASSWORD",
                   "TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "ANTHROPIC_API_KEY")


def secret(name: str) -> str:
    """Lee un secreto del entorno; acepta los nombres del kit del curso (p. ej. TELEGRAM_TOKEN)."""
    for key in SECRET_ALIASES.get(name, (name,)):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


def redact(text: Any) -> Any:
    """Oculta credenciales en mensajes que terminan en logs, reportes o artefactos (repo público)."""
    if not isinstance(text, str) or not text:
        return text
    out = text
    for key in SECRET_ENV_KEYS:
        val = os.environ.get(key, "").strip()
        if len(val) >= 6:
            out = out.replace(val, "***")
    out = re.sub(r"(://[^:/@\s]+:)[^@\s]+@", r"\1***@", out)          # usuario:clave@host
    out = re.sub(r"bot\d{6,}:[A-Za-z0-9_-]{20,}", "bot***", out)        # token de Telegram en URL
    out = re.sub(r"sk-ant-[A-Za-z0-9_-]{10,}", "sk-ant-***", out)
    return out
