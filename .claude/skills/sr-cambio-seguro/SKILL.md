---
name: sr-cambio-seguro
description: Cambiar textos, idioma, horario, KPIs o uso de IA del Status Report y del bot Radamantis del proyecto SPM SR sin romper contratos, pruebas ni envíos reales.
---

# Cambio seguro al SR y al bot (proyecto AI_M8_FinalAssignment_SPM_SR)

## Mapa: qué archivo cambia qué
| Quiero cambiar | Archivo(s) |
|---|---|
| Etiquetas en inglés compartidas (salud, categorías, DQ, severidad) | `src/spm_sr/zeus/i18n.py` (lo usan bot, gráficas, `/app/` y export del dashboard) |
| Mensaje del SR por Telegram | `src/spm_sr/zeus/render.py` |
| Respuestas, menú y comandos del bot | `src/spm_sr/zeus/render_bot.py`; intenciones en `src/spm_sr/radamantis/agent.py` (`_PATTERNS`, conservar alias en español) |
| Gráficas del bot | `src/spm_sr/zeus/charts.py` |
| Narrativa, alertas y prompt de la IA | `src/spm_sr/thanatos/narrative.py` (`SYSTEM_PROMPT`, `top_alerts`, plantillas) |
| Orden y presupuesto de llamadas a la IA | `src/spm_sr/thanatos/agent.py` (roll-ups primero) y `config/settings.yaml` → `llm.max_calls` |
| Cálculo de KPIs 1-19 | `src/spm_sr/thanatos/kpi_rules.py`, `control.py`, `rollup.py`; umbrales en `config/thresholds.yaml` |
| Horario / envío real / turnos | `.github/workflows/daily_sr.yml` (cron UTC; CDMX = UTC-6; `SR_SLOT` am/pm/manual) |
| Guía "how to correct" (IA) al final de cada reporte | `src/spm_sr/thanatos/guidance.py` (`PLAYBOOK`, `SYSTEM_PROMPT`, situaciones); bloque en `zeus/render.py` → `guide_block`; config `guidance` en `settings.yaml`. Solo la corrida del SR genera guías por destinatario (`per_recipient`); bot y export no |
| Reporte de fallas | `src/spm_sr/core/reporting.py` |
| Reglas de seguridad | `src/spm_sr/cerbero/rules.py` (ver skill `cerbero-revision`) |

Los valores internos siguen en español (`Verde`, `En progreso`, `Alta`): solo la capa de presentación traduce. Los nombres guardados en la BD se muestran tal cual.

## Procedimiento
1. Leer el/los archivos del mapa antes de editar; no tocar contratos (`src/spm_sr/contracts/models.py`) salvo que el cambio lo exija.
2. Editar y actualizar las pruebas que dependan de textos (`tests/test_radamantis.py`, `tests/test_pipeline.py`). `test_all_replies_are_in_english` vigila que no se cuele español en el bot.
3. `python -m pytest -q` → todo en verde.
4. Vista previa local sin enviar nada (dataset de 150 proyectos):
   ```bash
   python - <<'PY'
   import datetime as dt, sqlite3
   from scripts.generate_spm_dummy import CHUNK, Gen, to_sql
   con = sqlite3.connect("/tmp/spm150.db")
   for chunk in to_sql(Gen(dt.date.today(), 20261018).build()).split(CHUNK)[1:]:
       con.executescript(chunk)
   con.commit()
   PY
   DB_URL=sqlite:////tmp/spm150.db REDIRECT_TELEGRAM_CHAT_ID=111 LLM_ENABLED=false AUDIT_FILE_LOG=0 \
     RUNS_DIR=/tmp/runs_preview python main.py --dry-run
   ```
   y leer `/tmp/runs_preview/<fecha>/outbox/*.json`.
5. Publicar (`git push`) y correr **simulacro** en GitHub contra la BD real:
   ```bash
   scripts/gh_workflow.sh daily_sr.yml -f 'inputs[dry_run]=true' -f 'inputs[scope]=all' -f 'inputs[as_of]='
   ```
   La anotación `SR manual-…` debe mostrar `BD=real`, `entregas {'SKIPPED': N}` y `IA x/y (roll-ups …: 51/51)`.
6. Si el cambio afecta al bot, desplegarlo (skill `hatchvps-publicar`).
7. Solo con permiso explícito del usuario: corrida real (`inputs[dry_run]=false`). Con el redirect activo llegan ~69 mensajes a su chat.

## Cuidados
| Riesgo | Control |
|---|---|
| Frecuencias altas (p. ej. cada 10 min) | ~69 mensajes por corrida; Telegram limita ~1 msg/s por chat. Advertir antes de programar |
| Costo de IA | ≤60 llamadas por corrida; dos corridas/día |
| Duplicados | Idempotencia por `fecha|SR_SLOT|destinatario` en `runs/ledger.json` (caché de Actions) |
| Inputs de workflows | Pasar por `env:` y validar; nunca `${{ inputs.* }}` dentro de `run:` |
