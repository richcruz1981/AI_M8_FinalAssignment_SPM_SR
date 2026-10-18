"""Narrativa ejecutiva. Plantilla determinista siempre disponible; LLM opcional con verificación de cifras."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..core.config import secret

log = logging.getLogger("spm_sr.thanatos.narrative")
NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")

SYSTEM_PROMPT = (
    "Eres analista de una PMO. Redacta en español de México un resumen ejecutivo de máximo 80 palabras "
    "a partir EXCLUSIVAMENTE del JSON recibido. Reglas: (1) usa solo cifras que aparezcan literalmente en el JSON; "
    "(2) no inventes causas ni afirmes causalidad entre indicadores; (3) si un dato es DATO_FALTANTE dilo así; "
    "(4) tono profesional, frases directas; (5) sin viñetas ni encabezados."
)


def top_alerts(rep: dict[str, Any], n: int = 3) -> list[str]:
    alerts: list[str] = []
    h = rep["health"]
    names = {"schedule": "Cronograma", "cost": "Costo", "resources": "Recursos", "scope": "Alcance"}
    for k, label in names.items():
        if h[k]["calculated"] == "Rojo":
            alerts.append(f"{label} en Rojo")
    if h["overall"]["comparison"] == "Optimismo":
        alerts.append(f"Overall declarado {h['overall']['declared']} vs calculado {h['overall']['calculated']}")
    ctl = rep["control"]
    if isinstance(ctl.get("milestones"), dict) and ctl["milestones"]["overdue"]:
        alerts.append(f"{ctl['milestones']['overdue']} hito(s) vencido(s)")
    if isinstance(ctl.get("risks"), dict) and ctl["risks"]["open_high"]:
        alerts.append(f"{ctl['risks']['open_high']} riesgo(s) alto(s) abierto(s)")
    if rep.get("sr_stale"):
        alerts.append("Status Report desactualizado")
    for k, label in names.items():
        if h[k]["calculated"] == "Amarillo":
            alerts.append(f"{label} en Amarillo")
    return alerts[:n]


def template_project(rep: dict[str, Any]) -> str:
    h, perf = rep["health"], rep["performance"]
    s, c = perf["schedule"], perf["cost"]
    parts = [f"{rep['number']} · Overall {h['overall']['calculated']} (declarado: {h['overall']['declared'] or 'sin dato'})."]
    if s["color"] != "DATO_FALTANTE":
        parts.append(f"Avance {s['percent_complete']}% vs {s['expected_pct']}% esperado ({s['gap_pp']:+} pp).")
    if c["color"] != "DATO_FALTANTE":
        cpi = c["cpi"] if c["cpi"] is not None else "n/c"
        parts.append(f"CPI {cpi}; consumo de presupuesto {c['consumption_pct']}%.")
    else:
        parts.append("Costo: DATO_FALTANTE.")
    al = top_alerts(rep)
    parts.append("Alertas: " + ("; ".join(al) if al else "sin alertas") + ".")
    return " ".join(parts)


def template_rollup(ru: dict[str, Any]) -> str:
    if not ru.get("distribution"):
        return f"{ru['level']} {ru.get('number') or ru.get('name')}: sin proyectos válidos."
    d = ru["distribution"]["overall"]
    txt = (f"{ru['level']} {ru.get('number')} ({ru['n_projects']} proyectos): Verde {d['Verde']['n']}, "
           f"Amarillo {d['Amarillo']['n']}, Rojo {d['Rojo']['n']}, sin dato {d['DATO_FALTANTE']['n']}. "
           f"Peor caso: {ru['worst_overall']}.")
    if ru.get("budget_in_red_pct") is not None:
        txt += f" Presupuesto en proyectos Rojo: {ru['budget_in_red_pct']}%."
    if ru.get("optimism_discrepancies"):
        txt += f" Discrepancias de optimismo: {ru['optimism_discrepancies']}."
    return txt


def _allowed_numbers(obj: Any, acc: set[float]) -> set[float]:
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, (int, float)):
        for v in (obj, round(obj), round(obj, 1), round(obj, 2), abs(obj)):
            acc.add(float(v))
    elif isinstance(obj, str):
        for m in NUM_RE.findall(obj):
            try:
                acc.add(float(m.replace(",", ".")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _allowed_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _allowed_numbers(v, acc)
    return acc


def verify_numbers(text: str, facts: Any) -> tuple[bool, list[str]]:
    """Toda cifra del texto debe existir en los hechos (tolerancia 0.05). Enteros 0-3 permitidos (conteos)."""
    allowed = _allowed_numbers(facts, set())
    cleaned = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # separador de miles
    bad = []
    for m in NUM_RE.findall(cleaned):
        v = float(m.replace(",", "."))
        if v.is_integer() and 0 <= v <= 3:
            continue
        if not any(abs(v - a) <= 0.05 or abs(abs(v) - a) <= 0.05 for a in allowed):
            bad.append(m)
    return (not bad), bad


class Narrator:
    def __init__(self, settings: dict):
        cfg = settings.get("llm", {})
        self.enabled = bool(cfg.get("enabled")) and bool(secret("ANTHROPIC_API_KEY"))
        self.model = cfg.get("model")
        self.max_tokens = int(cfg.get("max_tokens", 400))
        self.max_calls = int(cfg.get("max_calls", 20))
        self.calls = 0
        self.failures: list[str] = []
        self._client = None
        if self.enabled:
            try:
                import anthropic  # noqa: PLC0415

                self._client = anthropic.Anthropic()
            except Exception as e:  # noqa: BLE001
                self.enabled = False
                self.failures.append(f"SDK no disponible: {e}")

    def narrate(self, facts: dict[str, Any], fallback: str) -> dict[str, Any]:
        if not self.enabled or self.calls >= self.max_calls:
            return {"text": fallback, "source": "plantilla"}
        self.calls += 1
        try:
            msg = self._client.messages.create(
                model=self.model, max_tokens=self.max_tokens, system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(facts, ensure_ascii=False, default=str)}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        except Exception as e:  # noqa: BLE001
            self.failures.append(f"E-LLM-01: {str(e)[:200]}")
            return {"text": fallback, "source": "plantilla", "llm_error": "E-LLM-01"}
        ok, bad = verify_numbers(text, facts)
        if not ok:
            self.failures.append(f"E-LLM-02 cifras no trazables: {bad}")
            return {"text": fallback, "source": "plantilla", "llm_rejected_numbers": bad}
        return {"text": text, "source": "llm", "model": self.model}
