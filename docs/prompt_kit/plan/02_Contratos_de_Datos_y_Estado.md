# 02 · Contratos de Datos y Estado Compartido

## Conclusión
La modularidad depende de 3 contratos versionados. Mientras el contrato no cambie, cada agente puede reemplazarse o probarse de forma aislada con fixtures.

## Estado global de la corrida (`RunState`)
| Campo | Tipo | Escribe | Lee |
|---|---|---|---|
| `run_id` | UUID | M0 | Todos |
| `run_date` | date | M0 | Todos |
| `scope` | lista de {tipo: project/program/portfolio, id} | M0 (config o parámetro) | M1, M2 |
| `cronos` | `CronosOutput` (C1) | M1 | M2, M3 |
| `thanatos` | `ThanatosOutput` (C2) | M2 | M3 |
| `zeus` | `ZeusOutput` (C3) | M3 | M0 |
| `errors` | lista de `ErrorEvent` | Todos | M3, M0 |

## Señal de completado (común a los 3 agentes)
| Campo | Valores | Regla |
|---|---|---|
| `status` | `COMPLETED` | 100 % de registros en alcance leídos/procesados sin error |
| | `PARTIAL` | ≥1 registro válido y ≥1 excluido o tabla auxiliar ausente |
| | `FAILED` | Error bloqueante o 0 registros válidos |
| `started_at`, `finished_at` | datetime | — |
| `records_in` / `records_ok` / `records_excluded` | int | Conteos para conciliación |
| `contract_version` | semver | Ej. `1.0.0` |

## C1 · Cronos → Thanatos (`CronosOutput`)
| Bloque | Contenido | Origen OOB (SUPUESTO) |
|---|---|---|
| `projects[]` | id, number, name, state, % complete, fechas planeadas/reales, costo planeado/real, esfuerzo planeado/real, PM, programa, portafolio | `pm_project` |
| `status_reports[]` | project_id, as_on, overall_health, schedule, cost, resources, scope, comentarios | `project_status` |
| `hierarchy` | programa → PgM, portafolio → PfM | `pm_program`, `pm_portfolio` |
| `milestones[]`, `risks[]`, `issues[]`, `decisions[]`, `actions[]`, `change_requests[]` | Registros de control por proyecto | Tablas auxiliares (ver `04_M1`) |
| `resources[]` | horas asignadas vs reales | `resource_allocation` / `time_card` |
| `data_quality[]` | hallazgos por registro (regla, severidad, campo) | Validación de Cronos |
| `source_availability` | qué tablas existían y cuántas filas | Cronos |
| `signal` | Señal de completado | Cronos |

## C2 · Thanatos → Zeus (`ThanatosOutput`)
| Bloque | Contenido |
|---|---|
| `project_reports[]` | KPIs 1–19 por proyecto: valor, semáforo calculado, semáforo declarado, discrepancia, evidencia (campo origen) |
| `rollups[]` | Programa/Portafolio: distribución V/A/R, peor caso, % presupuesto en Rojo |
| `narrative` | Resumen ejecutivo por proyecto/rollup (texto LLM, con lista de cifras citadas) |
| `quality_summary` | Registros excluidos y motivo |
| `recipients_plan[]` | destinatario → lista de ids de proyectos/rollups que le corresponden |
| `signal` | Señal de completado |

## C3 · Zeus → Orquestador (`ZeusOutput`)
| Campo | Contenido |
|---|---|
| `deliveries[]` | destinatario, canal, estado (`SENT/FAILED/SKIPPED`), message_id, intento, timestamp |
| `signal` | Señal de completado |

## Reglas de los contratos
- **Ningún agente modifica la sección de otro** (solo lectura aguas arriba).
- Todo valor numérico en C2 lleva `source_field` (tabla.campo) → cumple trazabilidad.
- Campo ausente ≠ cero: se representa como `null` + bandera `DATO_FALTANTE`.
- Cambio incompatible en un contrato → sube versión mayor y prueba de contrato en CI.

## Qué falta verificar
- Nombres reales de campos en la réplica para cerrar el mapeo C1 (ver `04_M1`).
