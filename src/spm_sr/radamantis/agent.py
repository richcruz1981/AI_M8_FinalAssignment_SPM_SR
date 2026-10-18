"""Agente 4 "Radamantis" — Ejecutor. Recibe peticiones del bot de Telegram en tiempo real y orquesta:

    petición (Telegram) ─► Radamantis ─► Cronos (lee BD) ─► Thanatos (analiza / consulta) ─► Zeus (responde)

- Interpreta la petición (comando, botón del menú, número 1-6 o texto libre).
- Autoriza por chat_id (solo chats permitidos).
- Reutiliza la lectura de Cronos + análisis de Thanatos durante `cache_ttl_s` para responder rápido sin
  saturar la BD (límite del servidor: 8 conexiones, 60 s por consulta).
- El análisis bajo demanda NO usa LLM (sin costo de tokens; todas las cifras salen de código).
"""
from __future__ import annotations

import copy
import datetime as dt
import logging
import re
import threading
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..core.state import RunState, Signal
from ..cronos import Cronos
from ..thanatos import Thanatos
from ..thanatos.queries import INTENTS, answer, status_by_id
from ..zeus import Zeus
from ..zeus import render_bot

log = logging.getLogger("spm_sr.radamantis")

_ID_RX = r"\b(PRJ|PRG|PFL)\d{3,}\b"
_PATTERNS = [
    ("menu", r"^/?(start|menu|ayuda|help)\b"),
    ("estatus", r"^/(estatus|status|proyecto|kpi)\b|^7\b|^7️⃣|estatus por id"),
    ("total", r"^/total\b|^1\b|^1️⃣|\btotal\b"),
    ("categorias", r"^/categor|^2\b|^2️⃣|categor|estado|abiert|cerrad"),
    ("regiones", r"^/region|^3\b|^3️⃣|regi[oó]n"),
    ("programas", r"^/programa|^4\b|^4️⃣|programa"),
    ("portafolios", r"^/portafolio|^5\b|^5️⃣|portafolio|portfolio"),
    ("calidad", r"^/calidad|^6\b|^6️⃣|calidad|data quality|\bdq\b|faltan"),
]


def parse_intent(text: str | None) -> str | None:
    t = (text or "").strip().lower()
    t = re.sub(r"@\w+", "", t)  # /total@MiBot
    if re.search(_ID_RX, t, re.IGNORECASE):           # un ID manda sobre cualquier otra palabra (p. ej. /programa PRG0002)
        return "estatus"
    for intent, rx in _PATTERNS:
        if re.search(rx, t):
            return intent
    return None


class Radamantis:
    name = "radamantis"

    def __init__(self, settings: dict, schema_map: dict, thresholds: dict, zeus: Zeus,
                 allowed_chat_ids: set[str] | None = None, cache_ttl_s: int = 60,
                 clock: Callable[[], float] = time.monotonic, today: Callable[[], dt.date] | None = None,
                 tz: str = "America/Mexico_City"):
        self.settings = copy.deepcopy(settings)
        self.settings.setdefault("llm", {})["enabled"] = False      # análisis bajo demanda sin LLM
        self.schema_map, self.thresholds = schema_map, thresholds
        self.zeus = zeus
        self.allowed = {str(x) for x in (allowed_chat_ids or set()) if str(x).strip()}
        self.ttl = cache_ttl_s
        try:
            self.tz = ZoneInfo(tz)
        except Exception:  # noqa: BLE001 - contenedor sin tzdata: CDMX es UTC-6 fijo desde 2022
            self.tz = dt.timezone(dt.timedelta(hours=-6), "CDMX")
        self.clock = clock
        self.today = today or (lambda: dt.datetime.now(self.tz).date())
        self._cache: tuple[float, dict, dict | None, str] | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ datos (Cronos -> Thanatos)
    def _data(self) -> tuple[dict, dict | None, str, list]:
        with self._lock:
            return self._data_unlocked()

    def _data_unlocked(self) -> tuple[dict, dict | None, str, list]:
        now = self.clock()
        if self._cache and now - self._cache[0] < self.ttl:
            return self._cache[1], self._cache[2], self._cache[3], []
        state = RunState(run_date=self.today(), scope=["all"], dry_run=True)
        cronos_out = Cronos(self.settings, self.schema_map).run(state)
        state.cronos = cronos_out
        thanatos_out = None
        if cronos_out["signal"]["status"] != Signal.FAILED.value:
            thanatos_out = Thanatos(self.settings, self.schema_map, self.thresholds).run(state)
        when = dt.datetime.now(self.tz).strftime("%Y-%m-%d %H:%M (CDMX)")
        if cronos_out["signal"]["status"] != Signal.FAILED.value:
            self._cache = (now, cronos_out, thanatos_out, when)
        return cronos_out, thanatos_out, when, state.errors

    # ------------------------------------------------------------------ petición
    def handle(self, chat_id: Any, text: str | None, user_name: str | None = None) -> dict[str, Any]:
        started = time.monotonic()
        chat = str(chat_id)
        intent = parse_intent(text)
        result: dict[str, Any] = {"chat_id": chat, "text": (text or "")[:80], "intent": intent}
        if self.allowed and chat not in self.allowed:
            result.update(status="UNAUTHORIZED", deliveries=self.zeus.reply(chat, render_bot.unauthorized(chat)))
            log.warning("Chat no autorizado %s", chat)
            return result
        if intent in (None, "menu"):
            msgs = render_bot.welcome(user_name) if intent == "menu" else render_bot.not_understood()
            result.update(status="OK", deliveries=self.zeus.reply(chat, msgs, render_bot.keyboard()))
            return result
        if intent == "estatus" and not re.search(_ID_RX, text or "", re.IGNORECASE):
            result.update(status="OK", deliveries=self.zeus.reply(chat, render_bot.ask_id(), render_bot.keyboard()))
            return result
        assert intent in INTENTS or intent == "estatus"
        cronos_out, thanatos_out, when, errors = self._data()
        if cronos_out["signal"]["status"] == Signal.FAILED.value:
            err = next((e for e in errors if e.blocking), None)
            code, detail = (err.code, err.message) if err else ("E-DATA", "Lectura fallida")
            result.update(status="FAILED", error=code,
                          deliveries=self.zeus.reply(chat, render_bot.error(code, detail), render_bot.keyboard()))
            return result
        if intent == "estatus":
            res = status_by_id(text or "", cronos_out, thanatos_out)
            msgs = render_bot.render_status(res, when)
        else:
            res = answer(intent, cronos_out, thanatos_out)
            msgs = render_bot.render(res, when)
        result.update(status="OK", answer=res, deliveries=self.zeus.reply(chat, msgs, render_bot.keyboard()))
        result["latency_s"] = round(time.monotonic() - started, 2)
        log.info("Petición %s de %s respondida en %ss", intent, chat, result["latency_s"])
        return result
