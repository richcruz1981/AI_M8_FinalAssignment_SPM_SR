---
name: hatchvps-publicar
description: Publicar y verificar el proyecto SPM SR (bot Radamantis, portada y dashboard) en hatchvps.com/iaang01/edgarcruz vía GitHub Actions, respetando las reglas del servidor del curso.
---

# Publicar en hatchvps (proyecto AI_M8_FinalAssignment_SPM_SR)

Úsalo cada vez que cambie algo que vive en el servidor: `app.py`, `src/spm_sr/**` (bot), `dashboard/**`, `scripts/build_landing.py`, `site/original_index.html` o `config/*.yaml`.

## Reglas del servidor (no negociables)
| Regla | Consecuencia si se rompe |
|---|---|
| Solo `app.py` queda vivo; cualquier otro `.py` subido se ejecuta como script de 150 s sin librerías | El código del bot viaja en `spm_sr.zip`; nunca subir `.py` sueltos |
| Subir un `.py` reinicia la app (y el bot) | Desplegar el bot solo cuando cambió su código |
| Todo archivo bajo `/www` es público (excepto `.env`, verificado con un `.env` falso) | Nada de logs/auditoría/credenciales en archivos; `BOT_FILE_LOGS=0`, `AUDIT_FILE_LOG=0` |
| El puerto 22 está bloqueado desde la nube de Claude | Todo SFTP/túnel corre en GitHub Actions con el secret `HATCH_KEY` |
| La llave privada nunca se escribe en secrets/archivos por Claude | La agrega el usuario; no intentar rodear el bloqueo |
| Antes de borrar o reemplazar una tabla con datos, preguntar | Solo `CREATE ... IF NOT EXISTS` / inserts |

## Qué workflow usar
| Cambió | Workflow | Verifica |
|---|---|---|
| Bot / `app.py` / config / paquete `spm_sr` | `deploy_bot.yml` | `.env` → 404, `/app/` → 200, getUpdates 409 (= bot escuchando) |
| Dashboard React, portada, export de KPIs | `publish_dashboard.yml` (también corre cada hora) | `/`, `/dashboard/`, `/dashboard/data/kpis.json`, títulos |
| Reporte SR | `daily_sr.yml` (07:00 y 15:00 CDMX L-V) | anotación `SR …` con BD, entregas e IA |
| Portada original | `fetch_original_index.yml` | solo si hay que re-respaldar `site/original_index.html` |

## Procedimiento
1. `python -m pytest -q` en local; si falla, no publicar.
2. Si cambió el dashboard: `cd dashboard && npm run build` (debe decir `✓ built`).
3. `git add -A && git commit` (con las líneas de atribución del sistema) y `git push origin main`.
4. Lanzar y esperar con el helper (los logs están bloqueados por el proxy; el resultado sale en las anotaciones):
   ```bash
   scripts/gh_workflow.sh deploy_bot.yml
   scripts/gh_workflow.sh publish_dashboard.yml
   ```
5. Revisar en la salida: conclusión `success` y la anotación de verificación (HTTP 200 en `/`, `/dashboard/`, `/app/`; 404 en `/.env`).
6. Si se desplegó el bot: abrir `https://hatchvps.com/iaang01/edgarcruz/app/` y confirmar **Bot status = listening** (puede tardar ~20 s tras el reinicio; "created" justo después es normal).
7. Reportar al usuario en una tabla: qué se publicó, verificaciones y "Qué falta verificar".

## Errores conocidos
| Síntoma | Causa | Arreglo |
|---|---|---|
| Paso de verificación falla pero la página está bien | `curl … \| grep -q` con `pipefail` corta el pipe | Guardar a archivo y luego `grep -q` |
| Paso SFTP sale con código 123 | `xargs` sin entrada cuando una carpeta ya no existe | `xargs -r` y `\|\| true` en limpiezas |
| `sftp get` a carpeta inexistente falla | La carpeta no está en el checkout | `mkdir -p` antes |
| `gh workflow run` da 403 GraphQL | GraphQL bloqueado | Usar REST: `scripts/gh_workflow.sh` |
| hatchvps.com no responde desde la nube de Claude | Dominio fuera de la lista del proxy | Verificar desde el workflow o con el navegador del usuario |
| Error 409 en `/app/` tras desplegar | La prueba de getUpdates del workflow compite con el bot | Transitorio; revisar que vuelva a `listening` |
