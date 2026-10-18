"""Punto de entrada. Ejemplos:
    python main.py                                   # corrida diaria con config/settings.yaml
    python main.py --dry-run --scope program:PRG001  # sin envíos, solo un programa
    python main.py --as-of 2026-10-19 --agents thanatos,zeus   # reprocesa con el snapshot de Cronos
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from spm_sr.core.config import load_all  # noqa: E402
from spm_sr.core.orchestrator import run_pipeline  # noqa: E402

try:
    from dotenv import load_dotenv  # noqa: E402

    load_dotenv()
except ImportError:
    pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SR diario multi-agente (Cronos -> Thanatos -> Zeus)")
    ap.add_argument("--scope", help="all | project:<n>,program:<n>,portfolio:<n>")
    ap.add_argument("--as-of", help="Fecha de corte YYYY-MM-DD (default: hoy)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=None, help="No envía; guarda en runs/<fecha>/outbox")
    g.add_argument("--send", action="store_true", help="Envía aunque settings tenga dry_run=true")
    ap.add_argument("--agents", help="Subconjunto: cronos,thanatos,zeus")
    ap.add_argument("--settings", default="config/settings.yaml")
    a = ap.parse_args(argv)

    settings, schema_map, thresholds, recipients = load_all(a.settings)
    as_of = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    scope = [s.strip() for s in a.scope.split(",")] if a.scope else None
    dry = True if a.dry_run else (False if a.send else None)
    agents = [x.strip() for x in a.agents.split(",")] if a.agents else None
    state = run_pipeline(settings, schema_map, thresholds, recipients, as_of, scope, dry, agents)
    final = state.final_status().value
    print(f"\nEstado final: {final} · run_id {state.run_id} · salida en {settings['runs_dir']}/{as_of.isoformat()}/")
    return 1 if final == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
