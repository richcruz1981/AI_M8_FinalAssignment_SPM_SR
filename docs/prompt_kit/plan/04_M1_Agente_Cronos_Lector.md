# 04 · M1 — Agente "Cronos" (Lector)

## Conclusión
Cronos abre conexión, lee tablas núcleo y auxiliares, valida calidad mínima, guarda el snapshot en memoria/disco y emite la señal. **Una falla parcial no detiene el flujo**: se excluyen registros y se reporta.

## Pasos
| # | Paso | Detalle | Falla posible → manejo |
|---|---|---|---|
| a | Abrir conexión | SQLAlchemy engine, `pool_pre_ping`, timeout 30 s, usuario **solo lectura** | `E-CONN-*` → 3 reintentos con backoff (5/15/45 s) → `FAILED` |
| b1 | Verificar esquema | Existencia de tablas y columnas esperadas | Tabla núcleo ausente → `FAILED`; auxiliar ausente → `PARTIAL` + KPI `DATO_FALTANTE` |
| b2 | Leer núcleo | `pm_project` (activos en alcance) + `project_status` (último por proyecto) | `E-READ-*` → reintento; si persiste → `FAILED` |
| b3 | Leer auxiliares | Hitos, riesgos, issues, decisiones, acciones, cambios, recursos | Por tabla, independiente |
| c1 | Validar calidad | Reglas DQ (tabla abajo) | Registro inválido → excluido + hallazgo |
| c2 | Guardar | `RunState.cronos` en memoria + `runs/.../cronos.json` | Error de disco → `WARNING`, el flujo sigue en memoria |
| d | Señal | `COMPLETED / PARTIAL / FAILED` al orquestador | — |
| e | Reporte de fallas | Siempre se genera (vacío si no hubo) | Ver `07_Error_Handling` |

## Mapeo de tablas (SUPUESTO — estructura OOB a confirmar en la réplica)
| Rol | Tabla OOB | Campos clave |
|---|---|---|
| Núcleo · Proyecto | `pm_project` | `sys_id, number, short_description, state, percent_complete, start_date, end_date, work_start, work_end, cost, work_cost, effort, work_effort, project_manager, primary_program, primary_portfolio` |
| Núcleo · Status Report | `project_status` | `project, as_on, overall_health, schedule, cost, resources, scope, comments` |
| Jerarquía | `pm_program`, `pm_portfolio`, `sys_user` | `program_manager`, `portfolio_manager`, `email` |
| Hitos | `pm_project_task` (`milestone = true`) | `state, end_date, work_end` |
| Riesgos | `risk` | `state, probability, impact, owner, due_date` |
| Issues | `issue` | `state, priority, assigned_to` |
| Decisiones | `dmn_decision` | `state` |
| Acciones | `project_action` | `state, approval, due_date` |
| Cambios | `project_change_request` | `state` |
| Recursos | `resource_allocation` / `time_card` | horas asignadas / horas reales |

> Nota: el contexto pide leer "Projects y Status Reports". Con solo esas 2 tablas se cubren KPIs 1–12; los KPIs 13–19 requieren las auxiliares. Si el alcance del curso se limita a 2 tablas, esos KPIs se reportan como `DATO_FALTANTE`, no como cero.

## Reglas de calidad mínima (DQ)
| Código | Regla | Severidad | Efecto |
|---|---|---|---|
| DQ-01 | Proyecto sin Status Report | Alta | Se reporta; KPIs 1–5 declarados = `DATO_FALTANTE` |
| DQ-02 | Status Report con antigüedad > 7 días (`as_on`) | Media | Bandera "SR desactualizado" (umbral SUPUESTO) |
| DQ-03 | `percent_complete` fuera de 0–100 | Alta | Registro excluido |
| DQ-04 | `end_date < start_date` | Alta | Registro excluido |
| DQ-05 | `percent_complete > 0` y `work_start` nulo | Baja | Hallazgo |
| DQ-06 | Costo/esfuerzo planeado nulo o 0 | Media | KPI Cost/Resources = `DATO_FALTANTE` |
| DQ-07 | Proyecto sin PM o PM sin email | Alta | Sin destinatario; se escala al PgM |
| DQ-08 | Valor de semáforo fuera del catálogo (ej. vacío) | Media | Declarado = `DATO_FALTANTE` |
| DQ-09 | Duplicados por `sys_id` | Alta | Se conserva el más reciente |

## Seguridad
- Usuario de BD con permisos `SELECT` únicamente.
- Consultas parametrizadas (sin SQL concatenado).

## Criterios de aceptación
| Criterio | Meta |
|---|---|
| Conciliación | `records_in = records_ok + records_excluded` en el 100 % de corridas |
| Caída de BD simulada | Señal `FAILED` y reporte de fallas generado en < 3 min |
| Tabla auxiliar eliminada en prueba | Señal `PARTIAL`, flujo continúa |

## Qué falta verificar
- Esquema real de la réplica (ejecutar `information_schema` y cerrar este mapeo).
- Si `project_status` guarda varios SR por proyecto (histórico) o solo el último.
- Si los semáforos se guardan como texto (`green/yellow/red`) o como código numérico.
