"""Canal de envío Telegram (el correo se retiró el 2026-10-18). Credenciales solo por variables de entorno."""
from __future__ import annotations

import time

import requests

from ..core.config import redact, secret


class SendError(Exception):
    def __init__(self, msg: str):
        super().__init__(redact(msg))


class TelegramSender:
    API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, sleep=time.sleep):
        self.token = secret("TELEGRAM_BOT_TOKEN")
        self.sleep = sleep

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def send(self, chat_id: str, text: str, reply_markup: dict | None = None) -> str:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            resp = requests.post(self.API.format(token=self.token), json=payload, timeout=30)
        except requests.RequestException as e:
            raise SendError(f"Telegram: {e}") from e
        if resp.status_code == 429:
            wait = resp.json().get("parameters", {}).get("retry_after", 5)
            self.sleep(min(int(wait), 60))
            raise SendError(f"Telegram 429, retry_after={wait}")
        data = resp.json() if resp.content else {}
        if not data.get("ok"):
            raise SendError(f"Telegram {resp.status_code}: {data.get('description')}")
        return str(data["result"]["message_id"])


class TelegramBotAPI(TelegramSender):
    """Recepción de mensajes (long polling) y registro de comandos para el bot Radamantis."""

    BASE = "https://api.telegram.org/bot{token}/{method}"

    def _call(self, method: str, payload: dict, timeout: int = 30) -> dict:
        try:
            resp = requests.post(self.BASE.format(token=self.token, method=method), json=payload, timeout=timeout)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise SendError(f"Telegram {method}: {e}") from e
        if not data.get("ok"):
            raise SendError(f"Telegram {method} {resp.status_code}: {data.get('description')}")
        return data

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        payload = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", payload, timeout=timeout + 15)["result"]

    def set_my_commands(self, commands: list[tuple[str, str]]) -> None:
        self._call("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in commands]})

    def delete_webhook(self) -> None:
        self._call("deleteWebhook", {"drop_pending_updates": False})
