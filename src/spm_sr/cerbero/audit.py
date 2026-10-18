"""Log de auditoría de seguridad con cadena de hashes (evidencia de manipulación).

Destino principal: tabla `security_audit_log` en la misma BD del proyecto (la comparten el bot en el servidor y
las corridas en GitHub Actions; así el dashboard del bot ve todo). Respaldo: memoria (siempre) y archivo JSONL
local solo si AUDIT_FILE_LOG=1 — en el servidor del curso NO, porque todo archivo en /www se publica.

Nunca se guarda el texto completo de un mensaje o dato: solo su SHA-256 y un extracto corto ya neutralizado.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

log = logging.getLogger("spm_sr.cerbero.audit")
TABLE = "security_audit_log"
GENESIS = "0" * 64


def sha256(text: str | bytes | None) -> str | None:
    if text is None:
        return None
    b = text if isinstance(text, bytes) else str(text).encode("utf-8", "replace")
    return hashlib.sha256(b).hexdigest()


def mask_chat(chat_id: Any) -> str:
    s = str(chat_id or "")
    return f"chat ***{s[-4:]}" if len(s) > 4 else "chat ***"


def _excerpt(text: str | None, n: int = 60) -> str | None:
    if not text:
        return None
    from .rules import strip_control

    t = strip_control(str(text)).replace("<", "‹").replace(">", "›").replace("\n", " ")
    return t[:n] + ("…" if len(t) > n else "")


def chain_hash(prev: str, row: dict[str, Any]) -> str:
    body = {k: row.get(k) for k in ("ts", "source", "session", "agent", "action", "gate", "decision", "severity",
                                    "reasons", "subject", "content_sha256")}
    return sha256(prev + json.dumps(body, sort_keys=True, ensure_ascii=False))


def verify_chain(rows: list[dict[str, Any]]) -> tuple[bool, int]:
    """rows de UNA sesión en orden de inserción. Devuelve (íntegra, índice del primer eslabón roto o -1)."""
    prev = GENESIS
    for i, r in enumerate(rows):
        if r.get("prev_hash") != prev or chain_hash(prev, r) != r.get("hash"):
            return False, i
        prev = r["hash"]
    return True, -1


class AuditLog:
    def __init__(self, source: str, db_url: str | None = None, file_dir: str | Path | None = None,
                 memory: int = 500):
        self.source = source
        self.session = f"{source}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.db_url = db_url
        self.recent: deque[dict[str, Any]] = deque(maxlen=memory)
        self.file = Path(file_dir) / "security_audit.jsonl" if file_dir else None
        self._prev = GENESIS
        self._lock = threading.Lock()
        self._engine = None
        self._table = None
        self._db_ok: bool | None = None
        self._retry_at = 0.0                  # 0 = no reintentar (sin URL o SQLite inexistente)
        self.db_errors = 0

    # ------------------------------------------------------------------ BD
    def _ensure_db(self) -> bool:
        if self._db_ok:
            return True
        if self._db_ok is False and (self._retry_at == 0 or time.monotonic() < self._retry_at):
            return False
        if not self.db_url:
            self._db_ok = False
            return False
        if self.db_url.startswith("sqlite:///"):            # nunca crear una BD nueva: solo usar la existente
            path = self.db_url[len("sqlite:///"):]
            if path and path != ":memory:" and not Path(path).exists():
                self._db_ok = False
                return False
        try:
            from sqlalchemy import (BigInteger, Column, Integer, MetaData, String, Table, Text, create_engine)

            md = MetaData()
            self._table = Table(
                TABLE, md,
                Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
                Column("ts", String(40), nullable=False, index=True), Column("source", String(40)),
                Column("session", String(80), index=True), Column("agent", String(40)), Column("action", String(80)),
                Column("gate", String(40)), Column("decision", String(20)), Column("severity", String(10)),
                Column("reasons", Text), Column("subject", String(200)), Column("content_sha256", String(64)),
                Column("excerpt", String(120)), Column("prev_hash", String(64)), Column("hash", String(64)))
            kw = {} if self.db_url.startswith("sqlite") else {"pool_size": 1, "max_overflow": 1, "pool_recycle": 300}
            self._engine = create_engine(self.db_url, pool_pre_ping=True, **kw)
            md.create_all(self._engine, checkfirst=True)    # solo crea si no existe: nunca borra ni altera
            self._db_ok = True
        except Exception as e:  # noqa: BLE001 - la auditoría nunca tumba al agente; queda en memoria
            from ..core.config import redact

            log.warning("Auditoría sin BD (%s): queda en memoria; reintento en 60 s", redact(str(e))[:160])
            self._db_ok = False
            self._retry_at = time.monotonic() + 60     # p. ej. carrera al crear la tabla
        return self._db_ok

    # ------------------------------------------------------------------ registro
    def record(self, agent: str, action: str, gate: str, decision: str, severity: str = "LOW",
               reasons: list[str] | None = None, subject: str | None = None, content: str | bytes | None = None,
               excerpt: bool = False) -> dict[str, Any]:
        with self._lock:
            row = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "source": self.source,
                   "session": self.session, "agent": agent, "action": action[:80], "gate": gate,
                   "decision": decision, "severity": severity, "reasons": json.dumps(reasons or [], ensure_ascii=False),
                   "subject": (subject or "")[:200], "content_sha256": sha256(content),
                   "excerpt": _excerpt(content if isinstance(content, str) else None) if excerpt else None,
                   "prev_hash": self._prev}
            row["hash"] = chain_hash(self._prev, row)
            self._prev = row["hash"]
            self.recent.append(row)
            if self._ensure_db():
                try:
                    with self._engine.begin() as conn:
                        conn.execute(self._table.insert().values(**row))
                except Exception as e:  # noqa: BLE001
                    self.db_errors += 1
                    log.warning("No se pudo escribir auditoría en BD: %s", type(e).__name__)
            if self.file and os.environ.get("AUDIT_FILE_LOG", "1") != "0":
                try:
                    self.file.parent.mkdir(parents=True, exist_ok=True)
                    with self.file.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                except OSError:
                    pass
            if decision in ("BLOCK", "HALT", "QUARANTINE"):
                log.warning("CERBERO %s · %s/%s · %s · %s", decision, agent, gate, row["reasons"], row["subject"])
            return row

    # ------------------------------------------------------------------ lectura (dashboard)
    def fetch(self, limit: int = 300, since_hours: int | None = None) -> list[dict[str, Any]]:
        if not self._ensure_db():
            return list(self.recent)[::-1][:limit]
        from sqlalchemy import select

        t = self._table
        q = select(t).order_by(t.c.id.desc()).limit(limit)
        if since_hours:
            cut = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=since_hours)).isoformat(timespec="seconds")
            q = q.where(t.c.ts >= cut)
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(q).mappings().all()]

    def fetch_session(self, session: str) -> list[dict[str, Any]]:
        if not self._ensure_db():
            return [r for r in self.recent if r["session"] == session]
        from sqlalchemy import select

        t = self._table
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(t).where(t.c.session == session).order_by(t.c.id)).mappings()]
