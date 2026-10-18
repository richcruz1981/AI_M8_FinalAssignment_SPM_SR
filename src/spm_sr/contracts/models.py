"""Contratos C1 (Cronos->Thanatos), C2 (Thanatos->Zeus), C3 (Zeus->Orquestador). Ver docs/plan/02."""
from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class SignalModel(BaseModel):
    status: Literal["COMPLETED", "PARTIAL", "FAILED"]
    started_at: str
    finished_at: str
    records_in: int = 0
    records_ok: int = 0
    records_excluded: int = 0
    contract_version: str


class ProjectRecord(_Open):
    id: str
    number: str
    name: str | None = None
    percent_complete: float | None = None
    planned_start: dt.date | None = None
    planned_end: dt.date | None = None
    actual_start: dt.date | None = None
    actual_end: dt.date | None = None
    planned_cost: float | None = None
    actual_cost: float | None = None
    planned_effort: float | None = None
    actual_effort: float | None = None
    project_manager: str | None = None
    program: str | None = None
    portfolio: str | None = None


class DQFinding(_Open):
    rule: str
    severity: str
    project_number: str | None = None
    field: str | None = None
    value: Any = None
    excluded: bool = False
    message: str = ""


class CronosOutput(_Open):
    signal: SignalModel
    projects: list[ProjectRecord] = []
    status_reports: dict[str, dict[str, Any]] = {}
    hierarchy: dict[str, dict[str, dict[str, Any]]] = {}
    aux: dict[str, dict[str, list[dict[str, Any]]]] = {}
    data_quality: list[DQFinding] = []
    source_availability: dict[str, dict[str, Any]] = {}


class ThanatosOutput(_Open):
    signal: SignalModel
    project_reports: list[dict[str, Any]] = []
    rollups: list[dict[str, Any]] = []
    quality_summary: dict[str, Any] = {}
    recipients_plan: list[dict[str, Any]] = []


class Delivery(_Open):
    recipient: str
    channel: Literal["telegram"]
    status: Literal["SENT", "FAILED", "SKIPPED"]
    attempt: int = 0
    message_id: str | None = None
    reason: str | None = None
    ts: str


class ZeusOutput(_Open):
    signal: SignalModel
    mode: Literal["reports", "failure"]
    deliveries: list[Delivery] = []


_MODELS = {"C1": CronosOutput, "C2": ThanatosOutput, "C3": ZeusOutput}


def validate_contract(name: str, data: dict[str, Any]) -> BaseModel:
    """Lanza pydantic.ValidationError si la salida de un agente rompe su contrato."""
    return _MODELS[name].model_validate(data)
