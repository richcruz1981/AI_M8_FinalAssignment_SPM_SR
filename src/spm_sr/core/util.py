from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def parse_date(v: Any) -> dt.date | None:
    """Acepta date, datetime o texto 'YYYY-MM-DD[ HH:MM:SS]'. Vacío/inválido -> None."""
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        pass
    try:
        return dt.datetime.strptime(s[:10], "%d/%m/%Y").date()
    except ValueError:
        return None


def to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def norm(v: Any) -> str:
    return "" if v is None else str(v).strip().lower()


def json_default(o: Any):
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    if hasattr(o, "value"):
        return o.value
    return str(o)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
