# Plan de Implementación — Sistema Multi-Agente SR (SPM ServiceNow)

**Proyecto:** Tec_AI_FinalAssignment-SPM_SR · **Empresa (ficticia):** PepAIDummy · **Versión:** 0.1 (2026-10-18)

## Conclusión
El sistema se implementa en **6 módulos independientes** (M0–M5) con contratos de datos explícitos entre ellos. Los 3 agentes (Cronos → Thanatos → Zeus) cubren los puntos 1–4.iii del contexto general; **el dashboard web (4.iv) y el bot de consulta bajo demanda (4.v) NO están cubiertos por los 3 agentes** y se plantean como fase 2 (M4, M5).

## Correcciones a la premisa (leer antes de implementar)
| # | Premisa original | Problema | Ajuste propuesto | Etiqueta |
|---|---|---|---|---|
| 1 | Cronos lee solo *Projects* y *Status Reports* | Los KPIs 13–19 (recursos, hitos, riesgos, issues, decisiones, acciones, cambios) viven en otras tablas OOB | Cronos lee 2 tablas **núcleo** + tablas **auxiliares** configurables; si faltan, el KPI se marca `DATO_FALTANTE` | INFERENCIA (estructura OOB por verificar en la réplica) |
| 2 | Los 3 son "agentes de IA" | Calcular KPIs con un LLM introduce riesgo de cifras inventadas | KPIs y semáforos se calculan en **código determinista**; el LLM solo redacta la narrativa a partir de valores ya calculados | INFERENCIA |
| 3 | "Guardar en memoria" | La memoria volátil se pierde al fallar y no deja rastro auditable | Estado en memoria **+ snapshot persistido** (JSON/Parquet) por corrida | INFERENCIA |
| 4 | Enviar Telegram al PM/PgM/PfM | La tabla `sys_user` OOB no tiene `chat_id`; un bot no puede escribir a quien no lo inició | Tabla de mapeo `notif_recipient` + flujo de alta (`/start`) | HECHO (restricción de Telegram Bot API) |
| 5 | Semáforos Verde/Amarillo/Rojo estándar | El estándar define los campos, **no los umbrales** | Umbrales propuestos en `05_M2`, parametrizables y a validar con la PMO | SUPUESTO |
| 6 | "Overall Health" como KPI | En OOB es un valor **declarado por el PM** | Thanatos calcula un Overall **derivado** y lo compara con el declarado (bandera de discrepancia) | INFERENCIA |

## Índice de documentos
| Archivo | Módulo | Contenido |
|---|---|---|
| `01_Arquitectura_y_Flujo.md` | — | Vista general, flujo secuencial, stack |
| `02_Contratos_de_Datos_y_Estado.md` | Transversal | Esquemas de entrada/salida entre agentes y señal de completado |
| `03_M0_Plataforma_Orquestacion.md` | M0 | Configuración, secretos, orquestador, scheduler |
| `04_M1_Agente_Cronos_Lector.md` | M1 | Conexión BD, lectura, validación, reporte de fallas |
| `05_M2_Agente_Thanatos_Analista.md` | M2 | Reglas de KPIs, semáforos, roll-up Programa/Portafolio |
| `06_M3_Agente_Zeus_Comunicador.md` | M3 | Correo y Telegram diarios por destinatario |
| `07_Error_Handling_y_Observabilidad.md` | Transversal | Taxonomía de errores, reintentos, logs, alertas |
| `08_Pruebas_y_Criterios_de_Aceptacion.md` | Transversal | Estrategia de pruebas y datos de prueba |
| `09_Roadmap_e_Implementacion.md` | — | Fases, entregables, piloto |
| `10_Riesgos_Brechas_y_Pendientes.md` | — | Riesgos, fase 2 (M4 Dashboard, M5 Bot) y qué falta verificar |

## Mapa de módulos
| Módulo | Nombre | Depende de | Puede desarrollarse en paralelo con |
|---|---|---|---|
| M0 | Plataforma y orquestación | — | M1, M2, M3 (con mocks) |
| M1 | Cronos (lector) | M0 | M2, M3 |
| M2 | Thanatos (analista) | Contrato C1 | M1, M3 |
| M3 | Zeus (comunicador) | Contrato C2 | M1, M2 |
| M4 | Dashboard web (fase 2) | Snapshots M1/M2 | — |
| M5 | Bot Telegram bajo demanda (fase 2) | M2 + M3 | — |

## Qué falta verificar
- Motor RDBMS de la réplica (PostgreSQL / MySQL / SQL Server) — **DATO FALTANTE**.
- Que la réplica conserve nombres de tablas/campos OOB (ver `04_M1`) — **SUPUESTO**.
- Fecha de entrega del Final Assignment para calibrar el roadmap — **DATO FALTANTE**.
