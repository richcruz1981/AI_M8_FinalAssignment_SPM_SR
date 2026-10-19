# SR multi-agente para ServiceNow SPM — Cronos · Thanatos · Zeus

Proceso autónomo que lee la réplica de ServiceNow SPM, calcula los KPIs estándar del Status Report (19 indicadores en 3 niveles: Salud, Desempeño, Control) y los envía dos veces al día (07:00 y 15:00 CDMX, lunes a viernes) por Telegram al PM, PgM y PfM (el correo se retiró el 2026-10-18: no hay servidor SMTP).

```
Scheduler ─► Cronos (lector) ──C1──► Thanatos (analista) ──C2──► Zeus (comunicador) ─► Telegram
                 │ FAILED ─────────────────────────────────────► Zeus: solo reporte de fallas al Admin
```

| Agente | Hace | LLM |
|---|---|---|
| **Cronos** | Conecta (3 reintentos), lee tablas núcleo + auxiliares, aplica reglas de calidad DQ-01…09, guarda snapshot, emite `COMPLETED/PARTIAL/FAILED` y reporte de fallas | No |
| **Thanatos** | Calcula semáforos (Schedule, Cost, Resources, Scope, Overall), compara **calculado vs declarado** por el PM, KPIs 6–19, roll-up Programa/Portafolio sin promediar colores | Solo narrativa, con verificación de cifras |
| **Zeus** | 1 mensaje de Telegram por destinatario/día (se divide si excede 4,096 caracteres), idempotente, reintentos, ritmo ~1 msg/s, dry-run | No |

**Bot bajo demanda — Radamantis (ejecutor):** recibe peticiones en Telegram (en inglés: `/total`, `/categories`, `/regions`, `/programs`, `/portfolios`, `/dataquality`, `/status <ID>` o el menú de botones) y las resuelve con Cronos → Thanatos → Zeus. Ver [`docs/plan/11`](docs/plan/11_M5_Agente_Radamantis_Bot.md). Se publica en el servidor del curso con el workflow *Publicar bot Radamantis en hatchvps*: el bot corre dentro de `app.py` (página de estado en https://hatchvps.com/iaang01/edgarcruz/app/) y el workflow *Despertar bot Radamantis* lo reactiva cada hora.

Plan completo de implementación: [`docs/plan/`](docs/plan/00_README_Indice.md).

## Inicio rápido (local, 2 minutos)

```bash
python -m venv .venv && .venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt
python scripts/seed_demo_db.py                           # BD demo con DATOS SINTÉTICOS
python main.py --dry-run                                 # corre los 3 agentes sin enviar nada
python -m pytest -q                                      # 22 pruebas
```

Salida en `runs/<fecha>/`: `cronos.json`, `thanatos.json`, `zeus.json`, `outbox/` (mensajes renderizados), `failure_report.md`, `run.log`.

Opciones: `--scope program:PRG001,project:PRJ0004` · `--as-of 2026-10-19` · `--send` · `--agents thanatos,zeus` (reprocesa con el snapshot de Cronos).

## Credenciales (repo público: nunca en el código)

| Dónde | Cómo |
|---|---|
| Local | Archivo `.env` en la raíz (ignorado por git). Acepta **tal cual** el `.env` del kit del curso: `DATABASE_URL`, `DATABASE_URL_LOCAL`, `TELEGRAM_TOKEN`, `TELEGRAM_ID`, `ANTHROPIC_API_KEY`. Plantilla: `.env.example` |
| GitHub Actions | *Settings → Secrets and variables → Actions* (tabla abajo) |

- `DB_TARGET=auto` usa `DATABASE_URL` si el host `alumnos-pgbouncer` resuelve (app desplegada en el servidor del curso) y si no, `DATABASE_URL_LOCAL` (requiere `./tunel.sh` abierto en tu computadora).
- Logs, reportes de fallas y artefactos **ocultan** claves, tokens y contraseñas (`***`).
- El CI falla si algún archivo versionado contiene una llave de Anthropic, un token de Telegram o una URL de BD con contraseña.

## Ejecutar desde GitHub

Dos workflows en *Actions*:

| Workflow | Disparo | Qué hace |
|---|---|---|
| `CI (pruebas)` | cada push / PR | pytest + corrida de humo |
| `SR dos veces al día` | lunes–viernes 07:00 y 15:00 CDMX y manual (*Run workflow*) | Corre los 3 agentes; publica `runs/` como artefacto y el reporte de fallas en el resumen |

Las corridas programadas **envían de verdad** (variable `SCHEDULE_DRY_RUN=true` las pasa a simulacro); la idempotencia es por turno (`SR_SLOT` = am / pm / manual), así que nadie recibe el mismo turno dos veces. Sin `DB_SOURCE=real` usa la BD demo. Para hacerlo real, en *Settings → Secrets and variables → Actions*:

| Secret | Uso |
|---|---|
| `DATABASE_URL` | URL de la BD del curso (o `DB_URL` para otra réplica; tiene prioridad) |
| `TELEGRAM_TOKEN` | Token del bot (@BotFather) |
| `TELEGRAM_CHAT_ID` (o `TELEGRAM_ID`) | Tu chat_id: recibe el reporte de fallas |
| `RECIPIENTS_YAML` | Contenido de `config/recipients.yaml` con los `chat_id` reales |
| `ANTHROPIC_API_KEY` | Narrativa con LLM (sin ella: plantilla) |
| `REDIRECT_TELEGRAM_CHAT_ID` | Pruebas: todos los mensajes llegan a tu chat, indicando el destinatario original |

| Variable | Uso |
|---|---|
| `DB_SOURCE` | `demo` (default, BD sintética) o `real` (usa `DATABASE_URL`/`DB_URL`) |
| `DB_TARGET` | `server` (default en Actions) / `local` / `auto` |
| `LLM_ENABLED` | `false` para no consumir tokens de Anthropic en las corridas programadas |
| `DRY_RUN` | `false` para que la corrida programada envíe (default `true`) |
| `SCOPE` | Alcance por defecto |
| `RUNNER_LABEL` | `self-hosted` si la BD es local (ver abajo) |

> **BD del curso:** `alumnos-pgbouncer` solo es alcanzable desde el servidor del curso (hatchvps). Con `DB_SOURCE=real` en un runner de GitHub, Cronos falla con `E-CONN-01`. Opciones: desplegar el proceso en el servidor del curso (cron + `python main.py`) o un self-hosted runner allí.
>
> **Importante — BD local:** los runners de GitHub corren en la nube y **no alcanzan una BD en tu equipo o LAN**. Si la réplica es local, registra un *self-hosted runner* en ese equipo (*Settings → Actions → Runners → New self-hosted runner*) y define `RUNNER_LABEL=self-hosted`. Alternativa: exponer la réplica con acceso restringido por IP.

### Telegram: alta de destinatarios
Un bot no puede escribir a quien no le ha hablado. Cada PM/PgM/PfM abre el bot y envía `/start`; luego:
```bash
TELEGRAM_BOT_TOKEN=xxx python scripts/telegram_chat_ids.py
```
y se agrega su `chat_id` en `RECIPIENTS_YAML`.

## Skills del proyecto (Claude Code)

En `.claude/skills/` (se cargan solos al abrir el repo con Claude Code):

| Skill | Para qué |
|---|---|
| `hatchvps-publicar` | Publicar y verificar bot, portada y dashboard en el servidor del curso |
| `sr-cambio-seguro` | Cambiar textos, idioma, horario, KPIs o IA del SR y del bot con pruebas y simulacro |
| `cerbero-revision` | Revisión semanal de seguridad con el log de Cerbero, en formato DAM |
| `dashboard-kpi` | Agregar KPIs o gráficas al dashboard con paleta validada, capturas y prueba del PDF |

Helper común: `scripts/gh_workflow.sh <workflow.yml> [-f inputs...]` lanza un workflow, espera y muestra pasos fallidos y anotaciones.

## Seguridad — agente Cerbero

Cada acción de los agentes pasa por una puerta de seguridad: mensajes de Telegram (`inbound`), datos leídos de la BD (`data`), entrada y salida de la IA (`llm_in` / `llm_out`) y todo mensaje enviado (`outbound`). Cerbero bloquea, neutraliza o **detiene al agente** (HALT) y pone en cuarentena a los chats reincidentes. El log de auditoría (tabla `security_audit_log`, encadenado por hashes) se consulta en el dashboard del bot (`/app/`). Detalle: [`docs/plan/12_Seguridad_Cerbero.md`](docs/plan/12_Seguridad_Cerbero.md).

## Dashboard web (React)

Portada: https://hatchvps.com/iaang01/edgarcruz/ — página original de hatch con paleta PepsiCo y, al inicio, la sección **Proyecto Final Edgar Cruz** con dos links: dashboard de uso del bot (`/app/`) y dashboard de KPIs (`/dashboard/`). La portada se arma con `scripts/build_landing.py` desde `site/original_index.html`.

Dashboard: https://hatchvps.com/iaang01/edgarcruz/dashboard/ — interfaz en inglés, paleta PepsiCo, 19 KPIs en gráficas.

| Pieza | Detalle |
|---|---|
| Datos | `scripts/export_dashboard_data.py` corre Cronos → Thanatos (sin LLM) y genera `data/kpis.json` |
| Front | `dashboard/` — Vite 5 + React 18 + Recharts; filtros (portafolio, programa, región, categoría, salud, PM, búsqueda, activos/todos) y toggle Bars / Columns / Donut |
| Publicación | `.github/workflows/publish_dashboard.yml`: túnel SSH → export → build → SFTP a `/www` (cada hora + manual). No sube `.py` |
| Respaldo | Portada original en el servidor (`_hatch_welcome_backup.html`) y en el repo (`site/original_index.html`) |

Local: `python scripts/export_dashboard_data.py && cd dashboard && npm ci && npm run dev`.

## Datos de prueba en PostgreSQL

`scripts/generate_spm_dummy.py` genera **datos sintéticos** (ficticios, semilla fija) para las 12 tablas tipo SPM, cada una con 100–200 registros: proyectos sanos, atrasados, con sobrecosto, vencidos y con fallas de calidad de datos, más SR declarados con ~20 % de "optimismo".

```bash
python scripts/generate_spm_dummy.py --out data/spm_dummy_postgres.sql            # SQL para PostgreSQL
python scripts/generate_spm_dummy.py --sqlite data/spm_dummy.db                    # o BD local SQLite
DB_URL=sqlite:///data/spm_dummy.db python main.py --dry-run
```

> Los 100 portafolios y 100 programas cumplen el mínimo de registros, pero la operación se concentra en 6 portafolios y 25 programas para que los roll-ups tengan sentido; los demás quedan sin proyectos y no generan mensajes.

## Adaptar a la réplica real
Solo se editan archivos de `config/`:

| Archivo | Contenido |
|---|---|
| `schema_map.yaml` | Mapeo lógico → físico de tablas/columnas (SUPUESTO: nombres OOB) y catálogos de estados |
| `thresholds.yaml` | Umbrales Verde/Amarillo/Rojo (SUPUESTO, validar con PMO) |
| `settings.yaml` | Alcance, antigüedad máxima del SR, LLM, canales |

## Estructura
```
config/            settings, umbrales, mapeo de esquema, destinatarios
src/spm_sr/core    orquestador, estado compartido, config, logging, reporte de fallas
src/spm_sr/contracts  contratos C1/C2/C3 (Pydantic)
src/spm_sr/cronos  M1 lector + reglas DQ
src/spm_sr/thanatos M2 KPIs, control, roll-up, narrativa
src/spm_sr/zeus    M3 render, envío, idempotencia
scripts/           BD demo sintética, utilitario de chat_id
tests/             unitarias, contrato, integración, caos
docs/plan/         plan de implementación modular
```

## Limitaciones conocidas
- **Sin correo:** el requisito 4.ii (correo diario al PM) quedó fuera por falta de SMTP; Telegram lleva el detalle completo.
- Avance esperado **lineal**: subestima proyectos con curva S.
- Umbrales y mapeo OOB son **supuestos** hasta validar con la réplica y la PMO.
- La regla de Scope "cambio aprobado sin re-línea base" no es calculable con campos OOB.
- Fase 2 pendiente: dashboard web (M4) y bot de consulta bajo demanda (M5).
