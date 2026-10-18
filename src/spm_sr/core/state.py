from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .util import now_iso


class Signal(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass
class ErrorEvent:
    code: str
    agent: str
    message: str
    severity: str = "Alta"          # Alta / Media / Baja
    blocking: bool = False
    context: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=now_iso)


@dataclass
class RunState:
    """Estado compartido de la corrida ("memoria" entre agentes)."""

    run_date: dt.date
    scope: list[str]
    dry_run: bool
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=now_iso)
    cronos: dict[str, Any] | None = None
    thanatos: dict[str, Any] | None = None
    zeus: dict[str, Any] | None = None
    errors: list[ErrorEvent] = field(default_factory=list)

    def add_error(self, code: str, agent: str, message: str, severity: str = "Alta",
                  blocking: bool = False, **context: Any) -> ErrorEvent:
        ev = ErrorEvent(code=code, agent=agent, message=message, severity=severity,
                        blocking=blocking, context=context)
        self.errors.append(ev)
        return ev

    def errors_of(self, agent: str) -> list[ErrorEvent]:
        return [e for e in self.errors if e.agent == agent]

    def final_status(self) -> Signal:
        sigs = [s.get("signal", {}).get("status") for s in (self.cronos, self.thanatos, self.zeus) if s]
        if not sigs or Signal.FAILED.value in sigs:
            return Signal.FAILED
        if all(s == Signal.COMPLETED.value for s in sigs):
            return Signal.COMPLETED
        return Signal.PARTIAL

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["final_status"] = self.final_status().value
        return d


def make_signal(status: Signal, started_at: str, records_in: int = 0, records_ok: int = 0,
                records_excluded: int = 0) -> dict[str, Any]:
    from .. import CONTRACT_VERSION

    return {
        "status": status.value,
        "started_at": started_at,
        "finished_at": now_iso(),
        "records_in": records_in,
        "records_ok": records_ok,
        "records_excluded": records_excluded,
        "contract_version": CONTRACT_VERSION,
    }
