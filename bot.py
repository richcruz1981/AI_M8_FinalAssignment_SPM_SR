"""Bot de Telegram en tiempo real (uso local o en un servidor con shell): Radamantis -> Cronos -> Thanatos -> Zeus.

    python bot.py                    # escucha indefinidamente (long polling)
    python bot.py --max-minutes 30   # sesión acotada
    python bot.py --once             # procesa lo pendiente y termina

En el servidor del curso (hatchvps) NO se publica este archivo: el bot arranca dentro de app.py.
Variables: TELEGRAM_TOKEN, BD (DATABASE_URL / DATABASE_URL_LOCAL / DB_URL), BOT_ALLOWED_CHAT_IDS (opcional).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "spm_sr.zip") if (_HERE / "spm_sr.zip").exists() else str(_HERE / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(_HERE / ".env")
except ImportError:
    pass

from spm_sr.core.logging_setup import setup_logging  # noqa: E402
from spm_sr.radamantis.runner import BotRunner  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bot Radamantis (SR bajo demanda)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=0)
    ap.add_argument("--cache-ttl", type=int, default=60)
    a = ap.parse_args(argv)
    runner = BotRunner(cache_ttl_s=a.cache_ttl)
    setup_logging(Path(runner.settings["runs_dir"]) / "bot" if runner.file_logs else None)
    return runner.run(once=a.once, max_minutes=a.max_minutes)


if __name__ == "__main__":
    raise SystemExit(main())
