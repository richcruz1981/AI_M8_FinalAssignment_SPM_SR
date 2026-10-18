from __future__ import annotations

import copy
import os
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


def load_settings(path: str | Path = "config/settings.yaml") -> dict[str, Any]:
    s = copy.deepcopy(_load_yaml(path))
    env = os.environ
    if env.get("DB_URL"):
        s["db"]["url"] = env["DB_URL"]
    if env.get("SCOPE"):
        s["scope"] = [x.strip() for x in env["SCOPE"].split(",") if x.strip()]
    if env.get("DRY_RUN"):
        s["notifications"]["dry_run"] = _bool(env["DRY_RUN"])
    if env.get("LLM_MODEL"):
        s["llm"]["model"] = env["LLM_MODEL"]
    for key, env_key in (("admin_email", "ADMIN_EMAIL"), ("admin_telegram_chat_id", "ADMIN_TELEGRAM_CHAT_ID"),
                         ("redirect_all_to", "REDIRECT_ALL_TO"),
                         ("redirect_telegram_chat_id", "REDIRECT_TELEGRAM_CHAT_ID")):
        if env.get(env_key):
            s["notifications"][key] = env[env_key]
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


def secret(name: str) -> str:
    return os.environ.get(name, "").strip()
