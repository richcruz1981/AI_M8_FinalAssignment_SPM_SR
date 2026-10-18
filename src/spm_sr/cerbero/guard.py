"""Agente de seguridad "Cerbero" — guardián que revisa CADA acción de los agentes y deja rastro auditable.

Puertas (gates) y dónde se invocan:
| Gate      | Agente que la dispara        | Qué revisa                                                         | Acción ante riesgo            |
|-----------|------------------------------|--------------------------------------------------------------------|-------------------------------|
| inbound   | Radamantis (chat Telegram)   | autorización, tamaño, caracteres de control, ráfagas, inyección    | BLOCK; cuarentena del chat    |
| data      | Cronos (lectura de la BD)    | texto malicioso en campos (prompt injection, HTML/JS, SQL, control)| SANITIZE; HALT si hay masivo  |
| llm_in    | Thanatos (antes de la IA)    | que no viajen datos marcados como maliciosos                       | template sin IA               |
| llm_out   | Thanatos (respuesta de la IA)| enlaces, HTML, secretos, instrucciones, longitud                   | BLOCK -> plantilla            |
| outbound  | Zeus (todo mensaje saliente) | secretos, enlaces ajenos, HTML no permitido, destinatario          | BLOCK; HALT si hay secretos   |

Decisiones: ALLOW · SANITIZE · BLOCK · QUARANTINE · HALT. HALT detiene al agente (excepción SecurityHalt).
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Any, Iterable

from . import rules
from .audit import AuditLog, mask_chat

BLOCKED_MARK = "[removed by security]"


class SecurityHalt(Exception):
    """Cerbero detuvo al agente: la acción no debe continuar."""

    def __init__(self, agent: str, reason: str):
        super().__init__(f"Cerbero detuvo a {agent}: {reason}")
        self.agent, self.reason = agent, reason


class Cerbero:
    name = "cerbero"

    def __init__(self, audit: AuditLog, max_msg_len: int = 300, rate_per_min: int = 12,
                 strikes_to_quarantine: int = 3, quarantine_s: int = 1800, field_max_len: int = 400,
                 halt_ratio: float = 0.2, clock=time.monotonic):
        self.audit = audit
        self.max_msg_len, self.rate, self.strikes_n = max_msg_len, rate_per_min, strikes_to_quarantine
        self.quarantine_s, self.field_max, self.halt_ratio = quarantine_s, field_max_len, halt_ratio
        self.clock = clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._strikes: dict[str, deque] = defaultdict(deque)
        self._quarantine: dict[str, float] = {}
        self._lock = threading.Lock()

    # ================================================================== 1) entrada del chat (Radamantis)
    def quarantined(self) -> dict[str, float]:
        now = self.clock()
        return {c: t - now for c, t in self._quarantine.items() if t > now}

    def _strike(self, chat: str, now: float) -> bool:
        s = self._strikes[chat]
        s.append(now)
        while s and now - s[0] > 600:
            s.popleft()
        if len(s) >= self.strikes_n:
            self._quarantine[chat] = now + self.quarantine_s
            s.clear()
            return True
        return False

    def inbound(self, chat_id: Any, text: str | None, authorized: bool) -> dict[str, Any]:
        """Veredicto para un mensaje entrante. decision: ALLOW | BLOCK | QUARANTINE (no responder)."""
        chat, raw = str(chat_id), text or ""
        subj = mask_chat(chat)
        with self._lock:
            now = self.clock()
            if self._quarantine.get(chat, 0) > now:
                self.audit.record("radamantis", "telegram_message", "inbound", "QUARANTINE", rules.HIGH,
                                  ["Q-ACTIVE"], subj, raw)
                return {"decision": "QUARANTINE", "reasons": ["Q-ACTIVE"], "text": None}
            reasons: list[str] = []
            if not authorized:
                reasons.append("AUTH-01")
            hits = self._hits[chat]
            hits.append(now)
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) > self.rate:
                reasons.append("RATE-01")
            if len(raw) > self.max_msg_len:
                reasons.append("LEN-01")
            clean = rules.strip_control(raw)
            if clean != raw:
                reasons.append("CTRL-01")
            reasons += rules.scan(clean)
            blocking = [r for r in reasons if r != "CTRL-01"]
            if not blocking:
                self.audit.record("radamantis", "telegram_message", "inbound",
                                  "SANITIZE" if reasons else "ALLOW", rules.MEDIUM if reasons else rules.LOW,
                                  reasons, subj, raw)
                return {"decision": "ALLOW", "reasons": reasons, "text": clean}
            quarantined = self._strike(chat, now) if blocking != ["AUTH-01"] else False
            self.audit.record("radamantis", "telegram_message", "inbound", "BLOCK", rules.HIGH, reasons, subj, raw,
                              excerpt=True)
            if quarantined:
                self.audit.record("cerbero", "quarantine_chat", "inbound", "QUARANTINE", rules.HIGH,
                                  ["Q-START", f"{self.quarantine_s // 60} min"], subj)
            return {"decision": "BLOCK", "reasons": reasons, "text": None, "quarantined": quarantined}

    # ================================================================== 2) datos leídos de la BD (Cronos)
    def _clean_field(self, value: str) -> tuple[str, list[str]]:
        reasons: list[str] = []
        v = rules.strip_control(value)
        if v != value:
            reasons.append("CTRL-01")
        hits = rules.scan(v) + rules.scan_secrets(v)
        if hits:
            return BLOCKED_MARK, reasons + hits
        if len(v) > self.field_max:
            reasons.append("LEN-02")
            v = v[: self.field_max] + "…"
        return v, reasons

    def _walk(self, obj: Any, path: str, found: list, rec_id: str | None):
        if isinstance(obj, dict):
            rid = str(obj.get("number") or obj.get("id")) if (obj.get("number") or obj.get("id")) else rec_id
            for k, v in list(obj.items()):
                if isinstance(v, str):
                    nv, rs = self._clean_field(v)
                    if rs:
                        obj[k] = nv
                        found.append({"path": f"{path}.{k}", "record": rid, "reasons": rs, "blocked": nv == BLOCKED_MARK,
                                      "value": v})
                elif isinstance(v, (dict, list)):
                    self._walk(v, f"{path}.{k}", found, rid)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, str):
                    nv, rs = self._clean_field(v)
                    if rs:
                        obj[i] = nv
                        found.append({"path": f"{path}[{i}]", "record": rec_id, "reasons": rs,
                                      "blocked": nv == BLOCKED_MARK, "value": v})
                else:
                    self._walk(v, f"{path}[{i}]", found, rec_id)

    def inspect_data(self, cronos_out: dict[str, Any], agent: str = "cronos") -> dict[str, Any]:
        """Sanitiza EN SITIO lo leído de la BD. Marca los registros para que no viajen a la IA. Puede detener."""
        found: list[dict] = []
        for key in ("projects", "inventory", "hierarchy", "status_reports", "aux"):
            if key in cronos_out:
                self._walk(cronos_out[key], key, found, None)
        flagged = sorted({f["record"] for f in found if f["blocked"] and f["record"]})
        total = max(1, len(cronos_out.get("inventory") or cronos_out.get("projects") or []))
        for f in found:
            self.audit.record(agent, "db_field", "data", "BLOCK" if f["blocked"] else "SANITIZE",
                              rules.HIGH if f["blocked"] else rules.MEDIUM, f["reasons"],
                              f"{f['record'] or '-'} · {f['path'][:120]}", f["value"])
        summary = {"fields_checked": True, "findings": len(found), "blocked_fields": sum(f["blocked"] for f in found),
                   "flagged_records": flagged}
        decision = "ALLOW" if not found else "SANITIZE"
        self.audit.record(agent, "db_read", "data", decision, rules.LOW if not found else rules.MEDIUM,
                          [f"findings={len(found)}", f"flagged={len(flagged)}"], f"{total} records")
        cronos_out["security"] = summary
        if len(flagged) / total > self.halt_ratio:
            self.audit.record("cerbero", "halt_agent", "data", "HALT", rules.HIGH,
                              ["DATA-MASS", f"{len(flagged)}/{total}"], agent)
            raise SecurityHalt(agent, f"{len(flagged)} de {total} registros con contenido malicioso")
        return summary

    # ================================================================== 3) IA (Thanatos)
    @staticmethod
    def _mentions(facts: Any, flagged: Iterable[str]) -> bool:
        s = str(facts)
        return BLOCKED_MARK in s or any(f and f in s for f in flagged)

    def llm_input(self, facts: Any, flagged: Iterable[str], subject: str) -> bool:
        """True si los hechos pueden enviarse a la IA."""
        if self._mentions(facts, flagged):
            self.audit.record("thanatos", "llm_request", "llm_in", "BLOCK", rules.MEDIUM, ["FLAGGED-DATA"], subject)
            return False
        return True

    def llm_output(self, text: str, subject: str) -> bool:
        reasons = rules.scan(text) + rules.scan_secrets(text)
        if rules.foreign_urls(text) or rules.URL_RX.search(text or ""):
            reasons.append("URL-01")
        if rules.TAG_RX.search(text or ""):
            reasons.append("HTML-01")
        if len(text or "") > 1200:
            reasons.append("LEN-03")
        ok = not reasons
        self.audit.record("thanatos", "llm_response", "llm_out", "ALLOW" if ok else "BLOCK",
                          rules.LOW if ok else rules.HIGH, reasons, subject, text, excerpt=not ok)
        return ok

    # ================================================================== 4) salida (Zeus)
    def outbound(self, agent: str, chat_id: Any, text: str, allowed_chats: set[str] | None = None,
                 kind: str = "telegram_message") -> str:
        """Revisa un mensaje antes de enviarlo. Devuelve el texto (quizá neutralizado) o lanza SecurityHalt."""
        subj = mask_chat(chat_id)
        secrets = rules.scan_secrets(text)
        if secrets:
            self.audit.record(agent, kind, "outbound", "HALT", rules.HIGH, secrets, subj, text)
            raise SecurityHalt(agent, f"mensaje con posible secreto ({', '.join(secrets)})")
        reasons: list[str] = []
        if allowed_chats is not None and str(chat_id) not in allowed_chats:
            self.audit.record(agent, kind, "outbound", "BLOCK", rules.HIGH, ["DEST-01"], subj, text)
            raise SecurityHalt(agent, "destinatario fuera de la lista autorizada")
        bad_tags = rules.disallowed_tags(text)
        if bad_tags:
            reasons.append("HTML-02:" + ",".join(bad_tags[:5]))
            text = rules.TAG_RX.sub(lambda m: m.group(0) if m.group(1).lower() in rules.ALLOWED_TAGS else "", text)
        urls = rules.foreign_urls(text)
        if urls:
            reasons.append("URL-02")
            for u in urls:
                text = text.replace(u, "[link removed]")
        clean = rules.strip_control(text)
        if clean != text:
            reasons.append("CTRL-01")
        self.audit.record(agent, kind, "outbound", "SANITIZE" if reasons else "ALLOW",
                          rules.MEDIUM if reasons else rules.LOW, reasons, subj, clean)
        return clean

    def note(self, agent: str, action: str, decision: str = "ALLOW", reasons: list[str] | None = None,
             subject: str | None = None, severity: str = rules.LOW) -> None:
        """Registro genérico de una acción de agente (inicio/fin de corrida, lectura de BD, etc.)."""
        self.audit.record(agent, action, "action", decision, severity, reasons, subject)


# ---------------------------------------------------------------------- instancia compartida por proceso
_INSTANCE: Cerbero | None = None
_ILOCK = threading.Lock()


def get_cerbero(settings: dict | None = None, source: str | None = None) -> Cerbero:
    """Un Cerbero por proceso (bot, corrida del SR o export del dashboard) con su propia cadena de auditoría."""
    global _INSTANCE
    with _ILOCK:
        if _INSTANCE is None:
            s = settings or {}
            sec = s.get("security", {}) or {}
            url = os.environ.get("AUDIT_DB_URL") or (s.get("db") or {}).get("url")
            file_dir = s.get("runs_dir") if os.environ.get("AUDIT_FILE_LOG", "1") != "0" else None
            _INSTANCE = Cerbero(AuditLog(source or os.environ.get("AUDIT_SOURCE", "sr"), url, file_dir),
                                max_msg_len=int(sec.get("max_message_len", 300)),
                                rate_per_min=int(sec.get("rate_per_min", 12)),
                                strikes_to_quarantine=int(sec.get("strikes_to_quarantine", 3)),
                                quarantine_s=int(sec.get("quarantine_min", 30)) * 60,
                                field_max_len=int(sec.get("field_max_len", 400)),
                                halt_ratio=float(sec.get("halt_ratio", 0.2)))
        return _INSTANCE


def reset_cerbero() -> None:
    """Solo para pruebas."""
    global _INSTANCE
    with _ILOCK:
        _INSTANCE = None
