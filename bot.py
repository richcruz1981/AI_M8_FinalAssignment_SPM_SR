"""Bot de Telegram en tiempo real: Radamantis (ejecutor) -> Cronos -> Thanatos -> Zeus.

Uso:
    python bot.py                    # escucha indefinidamente (long polling)
    python bot.py --max-minutes 30   # sesión acotada (p. ej. en GitHub Actions)
    python bot.py --once             # procesa lo pendiente y termina

Variables: TELEGRAM_TOKEN, BD (DATABASE_URL / DATABASE_URL_LOCAL / DB_URL),
BOT_ALLOWED_CHAT_IDS (opcional, separados por coma), BOT_FILE_LOGS=1 para guardar runs/bot/*. Se autorizan además TELEGRAM_CHAT_ID,
REDIRECT_TELEGRAM_CHAT_ID y los chat_id de RECIPIENTS_YAML.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from spm_sr.core.config import load_all, secret  # noqa: E402
from spm_sr.core.logging_setup import setup_logging  # noqa: E402
from spm_sr.core.util import json_default  # noqa: E402
from spm_sr.radamantis import Radamantis  # noqa: E402
from spm_sr.zeus import Zeus  # noqa: E402
from spm_sr.zeus.render_bot import COMMANDS  # noqa: E402
from spm_sr.zeus.senders import SendError, TelegramBotAPI  # noqa: E402

log = logging.getLogger("spm_sr.bot")
MAX_AGE_S = 600  # mensajes más viejos (p. ej. acumulados con el bot apagado) se ignoran


def allowed_chats(settings: dict, recipients: dict) -> set[str]:
    ids = {x.strip() for x in os.environ.get("BOT_ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
    n = settings.get("notifications", {})
    ids |= {str(v) for v in (n.get("admin_telegram_chat_id"), n.get("redirect_telegram_chat_id")) if v}
    ids |= {str(r["telegram_chat_id"]) for r in (recipients or {}).get("recipients", []) if r.get("telegram_chat_id")}
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bot Radamantis (SR bajo demanda)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=0)
    ap.add_argument("--cache-ttl", type=int, default=60)
    a = ap.parse_args(argv)

    settings, schema_map, thresholds, recipients = load_all()
    # En el servidor del curso la carpeta publicada es pública: por defecto el bot solo registra en consola.
    file_logs = os.environ.get("BOT_FILE_LOGS", "0").strip().lower() in ("1", "true", "si", "yes")
    run_dir = Path(settings["runs_dir"]) / "bot"
    setup_logging(run_dir if file_logs else None)
    if not secret("TELEGRAM_BOT_TOKEN"):
        log.error("Falta TELEGRAM_TOKEN")
        return 2
    api = TelegramBotAPI()
    zeus = Zeus(settings, recipients, telegram_sender=api)
    allowed = allowed_chats(settings, recipients)
    if not allowed:
        log.warning("Sin chats autorizados: el bot responderá 'no autorizado' a todos")
    rad = Radamantis(settings, schema_map, thresholds, zeus, allowed_chat_ids=allowed, cache_ttl_s=a.cache_ttl)
    try:
        api.delete_webhook()
        api.set_my_commands(COMMANDS)
    except SendError as e:
        log.warning("No se registraron comandos: %s", e)
    log.info("Radamantis escuchando · chats autorizados: %s", len(allowed))

    deadline = time.time() + a.max_minutes * 60 if a.max_minutes else None
    offset, backoff = None, 2
    journal = run_dir / "requests.jsonl"
    while True:
        try:
            updates = api.get_updates(offset, timeout=0 if a.once else 30)
            backoff = 2
        except SendError as e:
            log.warning("getUpdates falló: %s (reintento en %ss)", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            if not msg.get("chat"):
                continue
            if time.time() - msg.get("date", 0) > MAX_AGE_S:
                log.info("Mensaje viejo ignorado (update %s)", u["update_id"])
                continue
            try:
                res = rad.handle(msg["chat"]["id"], msg.get("text"), (msg.get("from") or {}).get("first_name"))
            except Exception as e:  # noqa: BLE001 - el bot no debe caerse por una petición
                log.exception("Error atendiendo petición: %s", e)
                res = {"chat_id": msg["chat"]["id"], "status": "ERROR", "error": str(e)[:200]}
            res.pop("answer", None)
            if not file_logs:
                continue
            with journal.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **res}, default=json_default,
                                    ensure_ascii=False) + "\n")
        if a.once and not updates:
            break
        if deadline and time.time() > deadline:
            log.info("Fin de la sesión del bot (max-minutes)")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
