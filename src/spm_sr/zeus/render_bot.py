"""Respuestas del bot (Radamantis) en HTML de Telegram. Cada respuesta indica la fuente de los datos."""
from __future__ import annotations

from html import escape
from typing import Any

from .render import ICON, LIMIT

MENU_BUTTONS = [["1️⃣ Total de proyectos", "2️⃣ Por categoría"],
                ["3️⃣ Por región", "4️⃣ Por programa"],
                ["5️⃣ Por portafolio", "6️⃣ Calidad de datos"]]
COMMANDS = [("total", "Total de proyectos"), ("categorias", "Proyectos por categoría (estado)"),
            ("regiones", "Proyectos por región"), ("programas", "Proyectos por programa"),
            ("portafolios", "Proyectos por portafolio"), ("calidad", "Proyectos con problemas de calidad de datos"),
            ("menu", "Mostrar el menú")]


def keyboard() -> dict:
    return {"keyboard": [[{"text": b} for b in row] for row in MENU_BUTTONS], "resize_keyboard": True,
            "is_persistent": True}


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "—"


def _foot(res: dict, when: str) -> str:
    return f"\n<i>Fuente: {escape(res.get('source_field', ''))} · datos leídos {escape(when)}</i>"


def _split(lines: list[str]) -> list[str]:
    msgs, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > LIMIT:
            msgs.append(cur)
            cur = ln
        else:
            cur = f"{cur}\n{ln}" if cur else ln
    msgs.append(cur)
    return [f"{m}\n<i>({i}/{len(msgs)})</i>" for i, m in enumerate(msgs, 1)] if len(msgs) > 1 else msgs


def welcome(name: str | None) -> list[str]:
    return [f"Hola {escape(name or '')} 👋 Soy <b>Radamantis</b>, el ejecutor del SR de proyectos.\n\n"
            "Elige una opción del menú o escribe un comando:\n"
            + "\n".join(f"/{c} — {escape(d)}" for c, d in COMMANDS[:-1])
            + "\n\nLos datos se leen en tiempo real de la base (son <b>datos sintéticos</b> de demostración)."]


def not_understood() -> list[str]:
    return ["No entendí la petición. Usa el menú o /menu para ver las opciones."]


def unauthorized(chat_id: Any) -> list[str]:
    return [f"⛔ Este chat no está autorizado.\nComparte este chat_id con el administrador: <code>{escape(str(chat_id))}</code>"]


def error(code: str, detail: str) -> list[str]:
    return [f"⚠️ No pude obtener los datos ({escape(code)}).\n{escape(detail[:300])}\nEl administrador recibió el detalle."]


def render(res: dict, when: str) -> list[str]:
    k = res["kind"]
    if k == "total":
        ov = res["overall"]
        lines = ["<b>1. Total de proyectos</b>",
                 f"Total en la base: <b>{res['total']}</b>",
                 f"Activos: {res['activos']} · Cerrados/cancelados: {res['cerrados_cancelados']}",
                 f"Analizados por Thanatos: {res['analizados']} (excluidos por calidad: {res['excluidos_dq']})",
                 "Salud calculada (activos analizados): "
                 + " ".join(f"{ov.get(c, 0)}{ICON[c]}" for c in ("Verde", "Amarillo", "Rojo", "DATO_FALTANTE"))]
    elif k == "categorias":
        lines = ["<b>2. Proyectos por categoría</b>", f"Total: {res['total']}"]
        for r in res["rows"]:
            det = ", ".join(f"{escape(s)} {n}" for s, n in sorted(r["estados"].items(), key=lambda x: -x[1]))
            lines.append(f"• <b>{escape(r['categoria'])}</b>: {r['n']} ({_pct(r['n'], res['total'])}) — {det}")
    elif k == "regiones":
        lines = ["<b>3. Proyectos por región</b>"]
        if not res["available"]:
            lines.append("El campo de región (u_region) no existe en la base.")
        else:
            lines.append(f"Total: {res['total']}")
            lines += [f"• <b>{escape(r['region'])}</b>: {r['n']} ({_pct(r['n'], res['total'])}) · activos {r['activos']}"
                      for r in res["rows"]]
    elif k in ("programas", "portafolios"):
        title = "4. Proyectos por programa" if k == "programas" else "5. Proyectos por portafolio"
        lines = [f"<b>{title}</b>",
                 f"{res['con_proyectos']} con proyectos · {res['sin_proyectos']} sin proyectos · total proyectos {res['total']}",
                 "<i>Formato: proyectos (activos) · salud de activos 🟢🟡🔴</i>"]
        for r in res["rows"]:
            name = f" {escape(r['name'])}" if r.get("name") else ""
            lines.append(f"• <b>{escape(str(r['number']))}</b>{name}: {r['n']} ({r['activos']}) · "
                         f"{r['verde']}🟢 {r['amarillo']}🟡 {r['rojo']}🔴")
    elif k == "calidad":
        lines = ["<b>6. Proyectos con problemas de calidad de datos</b>",
                 f"Afectados: <b>{res['proyectos_afectados']}</b> de {res['evaluados']} evaluados",
                 f"<i>{escape(res['nota'])}</i>"]
        for r in res["rows"]:
            flag = " · <b>excluido del análisis</b>" if r["excluded"] else ""
            lines.append(f"\n<b>{escape(r['rule'])} {escape(r['label'])}</b> ({escape(r['severity'])}){flag}: {r['n']}")
            projs = r["projects"]
            lines.append(", ".join(escape(p) for p in projs[:40]) + (f" … (+{len(projs) - 40})" if len(projs) > 40 else ""))
        if not res["rows"]:
            lines.append("Sin hallazgos ✅")
    else:
        return not_understood()
    lines.append(_foot(res, when))
    return _split(lines)
