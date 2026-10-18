"""Reglas de detección de Cerbero. Patrones conservadores: preferimos un falso positivo auditado a un ataque.

Cada regla tiene un código estable (aparece en el log de auditoría) y una severidad:
  HIGH     -> se bloquea la acción (y cuenta para cuarentena del emisor)
  MEDIUM   -> se neutraliza/sanitiza y se audita
"""
from __future__ import annotations

import re

HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"

# --- Prompt injection (directa por chat o indirecta vía datos de la BD que llegan al LLM)
PROMPT_INJECTION = [
    ("PI-01", r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|all|earlier|system)\b.{0,30}"
              r"\b(instruction|prompt|rule|message|direction)s?\b"),
    ("PI-02", r"\b(ignora|olvida|omite)\b.{0,40}\b(instrucci[oó]n|indicaci[oó]n|regla|prompt)(es|s)?\b"),
    ("PI-03", r"\b(system|developer)\s*(prompt|message|instruction)s?\b|<\s*/?\s*(system|assistant|user)\s*>"),
    ("PI-04", r"\byou\s+are\s+now\b|\bact\s+as\b|\bpretend\s+(to\s+be|you)\b|\bjailbreak\b|"
              r"\bahora\s+eres\b|\bact[uú]a\s+como\b"),
    ("PI-05", r"\b(reveal|print|show|leak|dump|exfiltrate|send)\b.{0,30}\b(prompt|secret|token|api[_ -]?key|"
              r"password|credential|\.env)s?\b"),
    ("PI-06", r"\[\s*(INST|SYS)\s*\]|<\|im_(start|end)\|>|###\s*(instruction|system)"),
]

# --- Inyección técnica (SQL, comandos, HTML/JS)
INJECTION = [
    ("SQL-01", r"('|\")\s*(or|and)\s+('|\")?\d+('|\")?\s*=\s*('|\")?\d+|;\s*(drop|delete|truncate|alter|insert|update)\b|"
               r"\bunion\s+(all\s+)?select\b|--\s*$|/\*.*\*/|\bxp_cmdshell\b|\bpg_sleep\s*\("),
    ("CMD-01", r"\$\(|`[^`]+`|;\s*(rm|curl|wget|bash|sh|python|nc)\s|\|\s*(sh|bash)\b|&&\s*(rm|curl|wget)\b"),
    ("XSS-01", r"<\s*(script|iframe|object|embed|svg|img|link|meta|style|form)\b|javascript\s*:|"
               r"\bon(error|load|click|mouseover)\s*=|data\s*:\s*text/html"),
    ("PATH-01", r"\.\./\.\./|/etc/passwd|\\\\windows\\\\"),
]

# --- Contenido que nunca debe salir hacia el usuario (fuga de secretos)
SECRETS = [
    ("SEC-01", r"bot\d{6,}:[A-Za-z0-9_-]{20,}|\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b"),        # token Telegram
    ("SEC-02", r"sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{32,}"),                         # API keys LLM
    ("SEC-03", r"postgres(ql)?(\+\w+)?://[^\s:@/]+:[^\s@/]+@|mysql://[^\s:@/]+:[^\s@]+@"),  # URL de BD con clave
    ("SEC-04", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),                                    # llave privada (HATCH_KEY)
    ("SEC-05", r"\b(password|passwd|pwd|secret)\s*[=:]\s*\S{4,}"),
]

# --- Enlaces: solo dominios del proyecto pueden aparecer en mensajes salientes
URL_RX = re.compile(r"(?i)\b((?:https?://|www\.)[^\s<>\"']+)")
ALLOWED_URL_HOSTS = ("hatchvps.com", "github.com/richcruz1981")

# --- HTML permitido por Telegram que el proyecto usa
ALLOWED_TAGS = {"b", "i", "code", "pre"}
TAG_RX = re.compile(r"</?\s*([a-zA-Z][a-zA-Z0-9-]*)[^>]*>")

CONTROL_RX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")

_COMPILED = {code: re.compile(rx, re.IGNORECASE | re.DOTALL) for code, rx in PROMPT_INJECTION + INJECTION + SECRETS}


def scan(text: str, families: tuple[str, ...] = ("PI", "SQL", "CMD", "XSS", "PATH")) -> list[str]:
    """Códigos de las reglas que coinciden (por familia: prefijo del código)."""
    if not text:
        return []
    return [code for code, rx in _COMPILED.items() if code.split("-")[0] in families and rx.search(text)]


def scan_secrets(text: str) -> list[str]:
    return scan(text, ("SEC",))


def foreign_urls(text: str) -> list[str]:
    out = []
    for m in URL_RX.findall(text or ""):
        low = m.lower()
        if not any(h in low for h in ALLOWED_URL_HOSTS):
            out.append(m)
    return out


def disallowed_tags(text: str) -> list[str]:
    return sorted({t.lower() for t in TAG_RX.findall(text or "") if t.lower() not in ALLOWED_TAGS})


def strip_control(text: str) -> str:
    return CONTROL_RX.sub("", text)
