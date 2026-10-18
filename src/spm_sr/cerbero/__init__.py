"""Agente 5 "Cerbero" — Seguridad: revisa cada acción de los agentes y registra un log de auditoría."""
from .audit import AuditLog, verify_chain
from .guard import BLOCKED_MARK, Cerbero, SecurityHalt, get_cerbero, reset_cerbero

__all__ = ["AuditLog", "BLOCKED_MARK", "Cerbero", "SecurityHalt", "get_cerbero", "reset_cerbero", "verify_chain"]
