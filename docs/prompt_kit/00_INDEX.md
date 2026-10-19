# Kit del Prompt maestro · SPM Status Report AI Ecosystem

Proyecto Final Edgar Cruz · versión 2026-10-18 · repo `richcruz1981/AI_M8_FinalAssignment_SPM_SR`

## Cómo usarlo
1. Abre una conversación nueva (Claude, Claude Code u otro LLM) y pega el bloque de `PROMPT_MAESTRO.md`.
2. Adjunta `0_GeneralContext.md`, `CLAUDE.md` y, si la herramienta lo permite, la carpeta `skills/`.
3. Para trabajar dentro del repo con Claude Code: copia `CLAUDE.md` a la raíz y `skills/*` a `.claude/skills/`.

## Contenido
| Archivo | Para qué |
|---|---|
| `PROMPT_MAESTRO.md` | Prompt avanzado (RAAF + blindaje) con la versión vigente de todas las instrucciones del proyecto |
| `CLAUDE.md` | Reglas permanentes de trabajo: respuesta, idioma, secretos, servidor, confirmaciones y verificación |
| `0_GeneralContext.md` | Contexto de negocio original, con nota de los cambios vigentes |
| `ARCHITECTURE_FOR_LLMS.md` | Descripción técnica completa del ecosistema implementado (componentes, flujos, KPIs, seguridad) |
| `skills/hatchvps-publicar/SKILL.md` | Publicar y verificar en el servidor del curso |
| `skills/sr-cambio-seguro/SKILL.md` | Cambios seguros al SR y al bot |
| `skills/cerbero-revision/SKILL.md` | Revisión semanal de seguridad con DAM |
| `skills/dashboard-kpi/SKILL.md` | Cambios al Portfolio Health Dashboard |
| `plan/00…12_*.md` | Plan técnico por módulo (M0–M5 y seguridad) |

## Precedencia
Si dos archivos se contradicen, prevalece: `PROMPT_MAESTRO.md` → `CLAUDE.md` → `skills/` → `ARCHITECTURE_FOR_LLMS.md` → `plan/`.
Los documentos de `plan/` son el diseño original: algunos todavía mencionan el canal de correo, que se retiró por falta de SMTP.

## Excluido a propósito
Las instrucciones sobre la infografía y sobre la generación de este prompt no forman parte del kit.
