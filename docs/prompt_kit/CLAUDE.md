# CLAUDE.md · Reglas de trabajo del proyecto SPM SR (Proyecto Final Edgar Cruz)

Instrucciones permanentes para cualquier asistente que trabaje en este repositorio
(`richcruz1981/AI_M8_FinalAssignment_SPM_SR`). Complementan `PROMPT_MAESTRO.md`.

## 1. Cómo responder al usuario
- Español de México. Conclusión primero, tablas breves, sin preámbulo.
- Máximo 2–3 hallazgos y máximo 3 acciones (Acción | Responsable rol | KPI | Meta con plazo | Riesgo residual | Condición de detención).
- Etiqueta afirmaciones: HECHO / INFERENCIA / SUPUESTO / DATO FALTANTE. Nunca inventes cifras; cita archivo, tabla y campo o la anotación del workflow.
- Si la premisa del usuario está mal, dilo antes de ejecutar. No valides por defecto.
- Cierra siempre con "Qué falta verificar".
- Para análisis, diagnóstico o auditoría usa la metodología DAM (Diagnóstico → Auditoría → Mejora).
- Voz de marca: profesional y directa; nunca "disruptivo".

## 2. Idioma del producto
Bot, reportes de Telegram, gráficas y dashboards en **inglés**. Los valores internos siguen en español (`Verde`, `En progreso`, `Alta`) y se traducen en la capa de presentación (`src/spm_sr/zeus/i18n.py`). Los nombres guardados en la BD se muestran tal cual.

## 3. Seguridad y secretos (no negociable)
- El repo es **público**: nunca subir `.env`, `.hatch_key`, `CREDENCIALES*.txt`, `Tokens*.txt` ni valores de secretos. `tests/test_no_secrets.py` lo vigila.
- Secretos solo en GitHub Secrets y en el `.env` del servidor (verificado como no público).
- Si un control bloquea escribir una llave privada, no lo rodees: lo hace el usuario.
- Antes de borrar o reemplazar una tabla con datos, preguntar. Nunca `DROP DATABASE`, `CREATE/ALTER ROLE`, `GRANT`, `REVOKE`.
- Todo archivo bajo `/www` del servidor es público: nada de logs ni auditoría en archivos (`BOT_FILE_LOGS=0`, `AUDIT_FILE_LOG=0`).
- Inputs de workflows por `env:` y validados; nunca `${{ inputs.* }}` dentro de `run:`.
- Toda acción de agente pasa por Cerbero (`src/spm_sr/cerbero/`). Un cambio que agregue una salida nueva (mensaje, archivo, llamada a IA) debe pasar por la puerta correspondiente.

## 4. Servidor del curso (hatchvps)
- Solo `app.py` queda vivo; el bot corre en un hilo dentro de él. El paquete viaja como `spm_sr.zip`; la config también como JSON.
- No subir `.py` sueltos (se ejecutan como scripts de 150 s y reinician la app).
- El puerto 22 no es alcanzable desde la nube del asistente: todo SFTP/túnel corre en GitHub Actions.
- Límite de BD: 8 conexiones, 60 s por consulta.

## 5. Acciones que requieren confirmación del usuario
Envío real a Telegram fuera del horario programado, cambiar horario o frecuencia, borrar datos o archivos del servidor, reemplazar páginas públicas, agregar costo recurrente de IA. Lo reversible y verificable se hace sin pedir permiso.

## 6. Verificación antes de decir "listo"
| Cambio | Evidencia mínima |
|---|---|
| Código Python | `python -m pytest -q` en verde |
| SR / bot | Simulacro en GitHub (`scripts/gh_workflow.sh daily_sr.yml -f 'inputs[dry_run]=true' …`) con anotación de BD, entregas, IA y guías |
| Servidor | `scripts/gh_workflow.sh deploy_bot.yml` / `publish_dashboard.yml` con HTTP 200 en `/`, `/app/`, `/dashboard/` y 404 en `/.env`; bot en "listening" |
| Dashboard | `npm run build`, capturas escritorio (1366 px) y celular (390 px, sin scroll horizontal), PDF revisado |
| Seguridad | `tests/test_cerbero.py` en verde; cadena íntegra en `/app/` |

## 7. Skills del proyecto
| Skill | Cuándo |
|---|---|
| `hatchvps-publicar` | Publicar o verificar bot, portada o dashboard |
| `sr-cambio-seguro` | Cambiar textos, idioma, horario, KPIs o IA del SR y del bot |
| `cerbero-revision` | Revisión semanal de seguridad (formato DAM) |
| `dashboard-kpi` | Agregar o modificar KPIs, gráficas o filtros del dashboard |

## 8. Commits
Mensajes en español, descriptivos; terminar con las líneas de atribución que indique el entorno. Commit y push a `main` solo cuando el usuario lo pidió o el flujo del proyecto lo requiere (despliegues).
