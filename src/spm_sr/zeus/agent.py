"""Agente 3 "Zeus" — Comunicador. Un mensaje de Telegram por destinatario por día (PM, PgM, PfM, Admin).

El canal de correo se retiró el 2026-10-18 por falta de servidor SMTP (brecha vs requisito 4.ii del contexto).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from ..core.state import RunState, Signal, make_signal
from ..core.util import now_iso, write_json
from . import render
from .senders import SendError, TelegramSender

log = logging.getLogger("spm_sr.zeus")
CHANNEL = "telegram"


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)[:80]


class Zeus:
    name = "zeus"

    def __init__(self, settings: dict, recipients_cfg: dict, telegram_sender: TelegramSender | None = None,
                 sleep: Callable[[float], None] = time.sleep, retry_backoff: tuple[float, ...] = (2, 6, 18)):
        self.settings = settings
        self.n = settings.get("notifications", {})
        self.dir_map = {str(r.get("email", "")).lower(): r for r in (recipients_cfg or {}).get("recipients", [])}
        self.telegram = telegram_sender or TelegramSender(sleep=sleep)
        self.sleep = sleep
        self.backoff = retry_backoff
        self.interval = float(self.n.get("telegram_min_interval_s", 1.1))   # ~1 msg/s por chat (límite Telegram)
        self.runs_dir = Path(settings["runs_dir"])
        self._last_send = 0.0

    # ------------------------------------------------------------------ ledger / idempotencia
    def _ledger_path(self) -> Path:
        return self.runs_dir / "ledger.json"

    def _ledger(self) -> dict:
        p = self._ledger_path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def _send_paced(self, chat: str, text: str) -> str:
        wait = self.interval - (time.monotonic() - self._last_send)
        if wait > 0 and self._last_send:
            self.sleep(wait)
        try:
            return self.telegram.send(chat, text)
        finally:
            self._last_send = time.monotonic()

    def _deliver(self, state: RunState, ledger: dict, recipient: str, target: str | None,
                 messages: list[str]) -> dict[str, Any]:
        # SR_SLOT separa los envíos del mismo día (p. ej. "am"/"pm" o una corrida manual); vacío = uno por día
        slot = os.environ.get("SR_SLOT", "").strip()
        key = f"{state.run_date.isoformat()}{'|' + slot if slot else ''}|{recipient.lower()}|{CHANNEL}"
        base = {"recipient": recipient, "channel": CHANNEL, "target": target, "ts": now_iso(), "attempt": 0,
                "parts": len(messages)}
        if ledger.get(key, {}).get("status") == "SENT":
            return {**base, "status": "SKIPPED", "reason": "ya enviado en este turno (idempotencia)"}
        outbox = self.runs_dir / state.run_date.isoformat() / "outbox"
        write_json(outbox / f"{_slug(recipient)}__{CHANNEL}.json", {"target": target, "messages": messages})
        if state.dry_run:
            return {**base, "status": "SKIPPED", "reason": "dry-run"}
        if not target:
            state.add_error("E-SEND-02", self.name, f"Sin chat_id de Telegram para {recipient}", severity="Baja")
            return {**base, "status": "SKIPPED", "reason": "sin destino telegram"}
        if not self.telegram.configured:
            state.add_error("E-SEND-03", self.name, "Telegram sin token (TELEGRAM_TOKEN)", severity="Media")
            return {**base, "status": "SKIPPED", "reason": "canal telegram no configurado"}
        ids, last = [], None
        for part in messages:
            for i, wait in enumerate(self.backoff, start=1):
                try:
                    ids.append(self._send_paced(target, part))
                    last = None
                    break
                except SendError as e:
                    last = str(e)
                    if i < len(self.backoff):
                        self.sleep(wait)
            if last:
                state.add_error("E-SEND-01", self.name, f"Fallo enviando Telegram a {recipient}", severity="Media",
                                detail=last)
                return {**base, "status": "FAILED", "attempt": len(self.backoff), "reason": last,
                        "message_id": ",".join(ids) or None}
        ledger[key] = {"status": "SENT", "ts": now_iso(), "message_id": ",".join(ids)}
        return {**base, "status": "SENT", "attempt": 1, "message_id": ",".join(ids)}

    def _target(self, email_addr: str | None) -> tuple[str | None, bool, bool]:
        """(chat_id, activo, redirigido)."""
        cfg = self.dir_map.get((email_addr or "").lower(), {})
        if cfg and (not cfg.get("active", True) or CHANNEL not in cfg.get("channels", [CHANNEL])):
            return None, False, False
        redirect = self.n.get("redirect_telegram_chat_id")
        chat = redirect or cfg.get("telegram_chat_id") or None
        return (str(chat) if chat else None), True, bool(redirect)

    # ------------------------------------------------------------------ respuesta bajo demanda (bot)
    def reply(self, chat_id: str, messages: list[str], reply_markup: dict | None = None,
              photo: bytes | None = None, caption: str = "") -> list[dict[str, Any]]:
        """Responde en el chat que hizo la petición (usado por Radamantis). Sin ledger: cada petición se responde.
        Si hay gráfica, se envía después del texto y lleva el menú; si la foto falla, el texto ya llegó."""
        out = []
        for i, part in enumerate(messages):
            markup = reply_markup if i == len(messages) - 1 and not photo else None
            last = None
            for attempt, wait in enumerate(self.backoff, start=1):
                try:
                    wait_pace = self.interval - (time.monotonic() - self._last_send)
                    if wait_pace > 0 and self._last_send:
                        self.sleep(wait_pace)
                    mid = self.telegram.send(chat_id, part, reply_markup=markup)
                    self._last_send = time.monotonic()
                    out.append({"recipient": str(chat_id), "channel": CHANNEL, "status": "SENT", "attempt": attempt,
                                "message_id": mid, "ts": now_iso()})
                    last = None
                    break
                except SendError as e:
                    last = str(e)
                    if attempt < len(self.backoff):
                        self.sleep(wait)
            if last:
                out.append({"recipient": str(chat_id), "channel": CHANNEL, "status": "FAILED",
                            "attempt": len(self.backoff), "reason": last, "ts": now_iso()})
                log.error("Zeus no pudo responder a %s: %s", chat_id, last)
                return out
        if photo and hasattr(self.telegram, "send_photo"):
            try:
                wait_pace = self.interval - (time.monotonic() - self._last_send)
                if wait_pace > 0 and self._last_send:
                    self.sleep(wait_pace)
                mid = self.telegram.send_photo(chat_id, photo, caption, reply_markup=reply_markup)
                self._last_send = time.monotonic()
                out.append({"recipient": str(chat_id), "channel": CHANNEL, "status": "SENT", "attempt": 1,
                            "message_id": mid, "kind": "photo", "ts": now_iso()})
            except SendError as e:
                log.warning("Gráfica no enviada a %s: %s", chat_id, e)
                out.append({"recipient": str(chat_id), "channel": CHANNEL, "status": "FAILED", "kind": "photo",
                            "reason": str(e), "ts": now_iso()})
        return out

    # ------------------------------------------------------------------ modos
    def _send_failure(self, state: RunState, ledger: dict, failure_md: str) -> list[dict]:
        body = render.failure_text(failure_md)[:3800].replace("&", "&amp;").replace("<", "&lt;")
        chat = self.n.get("admin_telegram_chat_id")
        return [self._deliver(state, ledger, "admin", str(chat) if chat else None, [f"<pre>{body}</pre>"])]

    def run(self, state: RunState, mode: str = "reports", failure_md: str | None = None) -> dict[str, Any]:
        started = now_iso()
        ledger = self._ledger()
        deliveries: list[dict] = []
        if not self.n.get("telegram_enabled", True):
            log.warning("Telegram deshabilitado en settings: Zeus no envía nada")
        elif mode == "failure":
            deliveries += self._send_failure(state, ledger, failure_md or "Falla sin detalle")
        else:
            t = state.thanatos or {}
            reps = {r["project_id"]: r for r in t.get("project_reports", [])}
            rus = {(ru["level"], ru["id"]): ru for ru in t.get("rollups", [])}
            partial = None
            if t.get("signal", {}).get("status") == Signal.PARTIAL.value:
                q = t.get("quality_summary", {})
                partial = (f"la corrida global excluyó {q.get('excluded', 0)} proyecto(s) por calidad de datos "
                           f"y registró {q.get('findings', 0)} hallazgo(s); el administrador recibe el detalle.")
            for rc in t.get("recipients_plan", []):
                chat, active, redirected = self._target(rc.get("email"))
                if not active:
                    continue
                my = [reps[p] for p in rc["projects"] if p in reps]
                esc = [reps[p] for p in rc["escalations"] if p in reps]
                my_ru = [rus[("Programa", p)] for p in rc["programs"] if ("Programa", p) in rus] + \
                        [rus[("Portafolio", p)] for p in rc["portfolios"] if ("Portafolio", p) in rus]
                msgs = render.telegram(rc, my, my_ru, esc, state.run_date,
                                       bool(self.n.get("telegram_include_costs")), partial, redirected)
                deliveries.append(self._deliver(state, ledger, rc.get("email") or rc["user_id"], chat, msgs))
            if failure_md and any(e.severity == "Alta" for e in state.errors):
                deliveries += self._send_failure(state, ledger, failure_md)
        write_json(self._ledger_path(), ledger)

        attempted = [d for d in deliveries if d["status"] in ("SENT", "FAILED")]
        failed = [d for d in attempted if d["status"] == "FAILED"]
        skipped_bad = [d for d in deliveries if d["status"] == "SKIPPED" and d.get("reason") not in
                       ("dry-run", "ya enviado en este turno (idempotencia)")]
        if attempted and len(failed) == len(attempted):
            status = Signal.FAILED
        elif failed or skipped_bad:
            status = Signal.PARTIAL
        else:
            status = Signal.COMPLETED
        log.info("Zeus %s (%s): %s entregas, %s enviadas, %s fallidas", status.value, mode, len(deliveries),
                 sum(1 for d in deliveries if d["status"] == "SENT"), len(failed))
        return {"signal": make_signal(status, started, records_in=len(deliveries),
                                      records_ok=sum(1 for d in deliveries if d["status"] == "SENT"),
                                      records_excluded=len(failed)),
                "mode": mode, "deliveries": deliveries}
