"""El repo es público: falla si algún archivo versionado contiene credenciales reales."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "Llave Anthropic": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "Token Telegram": re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}"),
    "Llave privada SSH": re.compile("-----BEGIN " + "(?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----"),
    "Clave en URL de BD": re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:(?!CLAVE@|clave@|\*\*\*@|password@)[^@\s]+@"),
}


def _tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / f for f in out.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def test_no_credentials_committed():
    hits = []
    for f in _tracked_files():
        if not f.exists() or f.suffix in (".db", ".png", ".jpg"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for name, rx in PATTERNS.items():
            if rx.search(text):
                hits.append(f"{f.relative_to(ROOT)}: {name}")
    assert not hits, "Credenciales en archivos versionados: " + "; ".join(hits)
