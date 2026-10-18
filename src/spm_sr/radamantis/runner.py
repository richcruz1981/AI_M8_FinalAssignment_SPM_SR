"""Bucle del bot (long polling) reutilizable desde bot.py (CLI) o app.py (servidor del curso, hilo de fondo)."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from ..core.config import load_all, secret
from ..core.util import json_default, now_iso
from ..zeus import Zeus
from ..zeus.render_bot import COMMANDS
from ..zeus.senders import SendError, TelegramBotAPI
from .agent import Radamantis

log = logging.getLogger("spm_sr.bot")
MAX_AGE_S = 600  # mensajes acumulados con el bot apagado se ignoran


def allowed_chats(settings: dict, recipients: dict) -> set[str]:
    ids = {x.strip() for x in os.environ.get("BOT_ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
    n = settings.get("notifications", {})
    ids |= {str(v) for v in (n.get("admin_telegram_chat_id"), n.get("redirect_telegram_chat_id")) if v}
    ids |= {str(r["telegram_chat_id"]) for r in (recipients or {}).get("recipients", []) if r.get("telegram_chat_id")}
    return ids


class BotRunner:
    def __init__(self, cache_ttl_s: int = 60, file_logs: bool | None = None):
        self.settings, schema_map, thresholds, recipients = load_all()
        fl = os.environ.get("BOT_FILE_LOGS", "0").strip().lower() in ("1", "true", "si", "yes")
        self.file_logs = fl if file_logs is None else file_logs
        self.journal = Path(self.settings["runs_dir"]) / "bot" / "requests.jsonl"
        self.api = TelegramBotAPI()
        self.zeus = Zeus(self.settings, recipients, telegram_sender=self.api)
        self.allowed = allowed_chats(self.settings, recipients)
        self.rad = Radamantis(self.settings, schema_map, thresholds, self.zeus, allowed_chat_ids=self.allowed,
                              cache_ttl_s=cache_ttl_s)
        self.stop_event = threading.Event()
        self.status: dict[str, Any] = {"state": "creado", "started_at": None, "last_poll": None, "handled": 0,
                                       "by_intent": {}, "errors": 0, "last_error": None,
                                       "allowed_chats": len(self.allowed), "db_origin": self.settings["db"].get("url_origin")}

    def _record(self, res: dict) -> None:
        self.status["handled"] += 1
        k = res.get("intent") or "otro"
        self.status["by_intent"][k] = self.status["by_intent"].get(k, 0) + 1
        if not self.file_logs:
            return
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": now_iso(), **res}, default=json_default, ensure_ascii=False) + "\n")

    def run(self, once: bool = False, max_minutes: float = 0) -> int:
        if not secret("TELEGRAM_BOT_TOKEN"):
            self.status.update(state="sin token", last_error="Falta TELEGRAM_TOKEN")
            log.error("Falta TELEGRAM_TOKEN")
            return 2
        try:
            self.api.delete_webhook()
            self.api.set_my_commands(COMMANDS)
        except SendError as e:
            log.warning("No se registraron comandos: %s", e)
        self.status.update(state="escuchando", started_at=now_iso())
        log.info("Radamantis escuchando · chats autorizados: %s", len(self.allowed))
        deadline = time.time() + max_minutes * 60 if max_minutes else None
        offset, backoff = None, 2
        while not self.stop_event.is_set():
            try:
                updates = self.api.get_updates(offset, timeout=0 if once else 30)
                self.status["last_poll"] = now_iso()
                backoff = 2
            except SendError as e:
                self.status.update(errors=self.status["errors"] + 1, last_error=str(e)[:200])
                log.warning("getUpdates falló: %s (reintento en %ss)", e, backoff)
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 60)
                continue
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                if not msg.get("chat"):
                    continue
                if time.time() - msg.get("date", 0) > MAX_AGE_S:
                    continue
                try:
                    res = self.rad.handle(msg["chat"]["id"], msg.get("text"), (msg.get("from") or {}).get("first_name"))
                except Exception as e:  # noqa: BLE001 - una petición no debe tumbar el bot
                    log.exception("Error atendiendo petición")
                    self.status.update(errors=self.status["errors"] + 1, last_error=str(e)[:200])
                    res = {"chat_id": msg["chat"]["id"], "status": "ERROR", "error": str(e)[:200]}
                res.pop("answer", None)
                self._record(res)
            if once and not updates:
                break
            if deadline and time.time() > deadline:
                break
        self.status["state"] = "detenido"
        return 0
