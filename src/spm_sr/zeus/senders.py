"""Canales de envío. Credenciales solo por variables de entorno."""
from __future__ import annotations

import smtplib
import ssl
import time
from email.message import EmailMessage

import requests

from ..core.config import redact, secret


class SendError(Exception):
    def __init__(self, msg: str):
        super().__init__(redact(msg))


class EmailSender:
    def __init__(self):
        self.host = secret("SMTP_HOST")
        self.port = int(secret("SMTP_PORT") or 587)
        self.user = secret("SMTP_USER")
        self.password = secret("SMTP_PASSWORD")
        self.sender = secret("SMTP_FROM") or self.user

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)

    def send(self, to: str, subject: str, html: str, text: str) -> str:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = subject, self.sender, to
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=30) as s:
                    if self.user:
                        s.login(self.user, self.password)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=30) as s:
                    s.starttls(context=ssl.create_default_context())
                    if self.user:
                        s.login(self.user, self.password)
                    s.send_message(msg)
        except (smtplib.SMTPException, OSError) as e:
            raise SendError(f"SMTP: {e}") from e
        return msg.get("Message-ID") or "smtp-ok"


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
