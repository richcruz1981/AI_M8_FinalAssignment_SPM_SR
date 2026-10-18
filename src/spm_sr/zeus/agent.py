"""Agente 3 "Zeus" — Comunicador. Un mensaje por destinatario y canal por día (PM, PgM, PfM, Admin)."""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

from ..core.state import RunState, Signal, make_signal
from ..core.util import now_iso, write_json
from . import render
from .senders import EmailSender, SendError, TelegramSender

log = logging.getLogger("spm_sr.zeus")


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)[:80]


class Zeus:
    name = "zeus"

    def __init__(self, settings: dict, recipients_cfg: dict, email_sender: EmailSender | None = None,
                 telegram_sender: TelegramSender | None = None, sleep: Callable[[float], None] = time.sleep,
                 retry_backoff: tuple[float, ...] = (2, 6, 18)):
        self.settings = settings
        self.n = settings.get("notifications", {})
        self.dir_map = {str(r.get("email", "")).lower(): r for r in (recipients_cfg or {}).get("recipients", [])}
        self.email = email_sender or EmailSender()
        self.telegram = telegram_sender or TelegramSender(sleep=sleep)
        self.sleep = sleep
        self.backoff = retry_backoff
        self.runs_dir = Path(settings["runs_dir"])

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

    def _deliver(self, state: RunState, ledger: dict, recipient: str, channel: str, target: str | None,
                 send_fn: Callable[[], str], outbox_payload: dict, configured: bool) -> dict[str, Any]:
        key = f"{state.run_date.isoformat()}|{recipient.lower()}|{channel}"
        base = {"recipient": recipient, "channel": channel, "target": target, "ts": now_iso(), "attempt": 0}
        if ledger.get(key, {}).get("status") == "SENT":
            return {**base, "status": "SKIPPED", "reason": "ya enviado hoy (idempotencia)"}
        outbox = self.runs_dir / state.run_date.isoformat() / "outbox"
        write_json(outbox / f"{_slug(recipient)}__{channel}.json", {"target": target, **outbox_payload})
        if state.dry_run:
            return {**base, "status": "SKIPPED", "reason": "dry-run"}
        if not target:
            state.add_error("E-SEND-02", self.name, f"Sin destino {channel} para {recipient}", severity="Baja")
            return {**base, "status": "SKIPPED", "reason": f"sin destino {channel}"}
        if not configured:
            state.add_error("E-SEND-03", self.name, f"Canal {channel} sin credenciales", severity="Media")
            return {**base, "status": "SKIPPED", "reason": f"canal {channel} no configurado"}
        last = None
        for i, wait in enumerate(self.backoff, start=1):
            try:
                mid = send_fn()
                ledger[key] = {"status": "SENT", "ts": now_iso(), "message_id": mid}
                return {**base, "status": "SENT", "attempt": i, "message_id": mid}
            except SendError as e:
                last = str(e)
                if i < len(self.backoff):
                    self.sleep(wait)
        state.add_error("E-SEND-01", self.name, f"Fallo enviando {channel} a {recipient}", severity="Media",
                        detail=last)
        return {**base, "status": "FAILED", "attempt": len(self.backoff), "reason": last}

    def _targets(self, email_addr: str | None) -> tuple[str | None, str | None, list[str]]:
        cfg = self.dir_map.get((email_addr or "").lower(), {})
        if cfg and not cfg.get("active", True):
            return None, None, []
        channels = cfg.get("channels", ["email"])
        mail = self.n.get("redirect_all_to") or email_addr
        chat = self.n.get("redirect_telegram_chat_id") or cfg.get("telegram_chat_id") or None
        return mail, (str(chat) if chat else None), channels

    # ------------------------------------------------------------------ modos
    def _send_failure(self, state: RunState, ledger: dict, failure_md: str) -> list[dict]:
        subj, body = render.failure_text(failure_md)
        out = []
        admin_mail = self.n.get("admin_email")
        admin_chat = self.n.get("admin_telegram_chat_id")
        html = "<pre style='font-family:monospace'>" + body.replace("<", "&lt;") + "</pre>"
        if self.n.get("email_enabled", True):
            out.append(self._deliver(state, ledger, "admin", "email", admin_mail,
                                     lambda: self.email.send(admin_mail, subj, html, body),
                                     {"subject": subj, "text": body}, self.email.configured))
        if self.n.get("telegram_enabled", True):
            short = body[:3500]
            out.append(self._deliver(state, ledger, "admin", "telegram", admin_chat,
                                     lambda: self.telegram.send(admin_chat, f"<pre>{short.replace('<', '&lt;')}</pre>"),
                                     {"text": short}, self.telegram.configured))
        return out

    def run(self, state: RunState, mode: str = "reports", failure_md: str | None = None) -> dict[str, Any]:
        started = now_iso()
        ledger = self._ledger()
        deliveries: list[dict] = []
        if mode == "failure":
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
                my = [reps[p] for p in rc["projects"] if p in reps]
                esc = [reps[p] for p in rc["escalations"] if p in reps]
                my_ru = [rus[("Programa", p)] for p in rc["programs"] if ("Programa", p) in rus] + \
                        [rus[("Portafolio", p)] for p in rc["portfolios"] if ("Portafolio", p) in rus]
                mail, chat, channels = self._targets(rc.get("email"))
                rid = rc.get("email") or rc["user_id"]
                if self.n.get("email_enabled", True) and "email" in channels:
                    subj, html, text = render.email(rc, my, my_ru, esc, state.run_date, partial)
                    deliveries.append(self._deliver(
                        state, ledger, rid, "email", mail, lambda m=mail, s=subj, h=html, x=text: self.email.send(m, s, h, x),
                        {"subject": subj, "html": html, "text": text}, self.email.configured))
                if self.n.get("telegram_enabled", True) and "telegram" in channels:
                    msg = render.telegram(rc, my, my_ru, esc, state.run_date,
                                          bool(self.n.get("telegram_include_costs")), partial)
                    deliveries.append(self._deliver(
                        state, ledger, rid, "telegram", chat, lambda c=chat, m=msg: self.telegram.send(c, m),
                        {"text": msg}, self.telegram.configured))
            if failure_md and any(e.severity == "Alta" for e in state.errors):
                deliveries += self._send_failure(state, ledger, failure_md)
        write_json(self._ledger_path(), ledger)

        attempted = [d for d in deliveries if d["status"] in ("SENT", "FAILED")]
        failed = [d for d in attempted if d["status"] == "FAILED"]
        skipped_bad = [d for d in deliveries if d["status"] == "SKIPPED" and d.get("reason") not in
                       ("dry-run", "ya enviado hoy (idempotencia)")]
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
