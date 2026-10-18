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

    def send(self, chat_id: str, text: str) -> str:
        try:
            resp = requests.post(self.API.format(token=self.token),
                                 json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                       "disable_web_page_preview": True}, timeout=30)
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
