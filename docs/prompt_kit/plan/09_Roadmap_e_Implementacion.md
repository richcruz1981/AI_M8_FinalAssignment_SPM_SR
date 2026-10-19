# 09 · Roadmap e Implementación

## Conclusión
Seis iteraciones semanales (S0–S5) para la fase 1 (3 agentes). Las semanas son **relativas**: la fecha de entrega del Final Assignment es DATO FALTANTE.

## Fases
| Iteración | Objetivo | Módulos | Entregable verificable |
|---|---|---|---|
| S0 | Descubrimiento | — | Esquema real de la réplica documentado; mapeo `04_M1` cerrado; umbrales validados o aceptados como SUPUESTO |
| S1 | Chasis + contratos | M0, contratos | Orquestador con agentes *stub*; C1/C2/C3 en Pydantic; `--dry-run` corre extremo a extremo |
| S2 | Cronos | M1 | Lectura real + reglas DQ + reporte de fallas; pruebas de caos de BD |
| S3 | Thanatos | M2 | KPIs 1–19 + roll-up + narrativa con verificación de cifras; 100 % en dataset de prueba |
| S4 | Zeus | M3 | Correo + Telegram a buzones de prueba; `notif_recipient` y flujo `/start` |
| S5 | Operación | M0–M3 | Scheduler diario; 5 corridas consecutivas; documentación final |
| Fase 2 | Consulta | M4, M5 | Dashboard web y bot bajo demanda (ver `10_`) |

## Dependencias críticas
| Dependencia | Bloquea | Mitigación |
|---|---|---|
| Acceso a la réplica | S2 | Desarrollar M1 contra fixture SQL con el mismo esquema |
| Token del bot Telegram | S4 | Crear bot con @BotFather en S1 |
| Cuenta SMTP | S4 | Validar en S1 con un correo de prueba |
| API key LLM | S3 | Fallback de plantilla permite avanzar sin ella |

## Piloto (S5) — 3 acciones
| Acción | Responsable | KPI calculable | Meta con plazo | Riesgo residual | Condición de detención |
|---|---|---|---|---|---|
| Ejecutar corrida diaria automática sobre 1 portafolio de la réplica | Desarrollador del sistema (alumno) | Corridas `COMPLETED+PARTIAL` / corridas programadas | 5 de 5 días hábiles en S5 | La réplica no se refresca diario → SR idénticos | 2 corridas `FAILED` consecutivas por la misma causa |
| Validar semáforos calculados vs cálculo manual en muestra | Analista PMO (revisor) | % de semáforos coincidentes en muestra de 20 proyectos | ≥ 95 % al cierre de S5 | Umbrales supuestos no representan el criterio de la PMO | < 85 % de coincidencia → revisar umbrales antes de seguir |
| Entregar SR a destinatarios de prueba (PM, PgM, PfM) | Desarrollador del sistema | Entregas `SENT` / entregas programadas válidas; duplicados | ≥ 98 % y 0 duplicados en S5 | Usuarios sin `chat_id` quedan fuera de Telegram | ≥ 1 envío con alcance equivocado (fuga de datos de otro proyecto) |

## Qué falta verificar
- Fecha de entrega y si la fase 2 (dashboard/bot) es obligatoria para la calificación.
- Disponibilidad de un revisor PMO para el piloto (si no existe, el alumno valida con cálculo manual documentado).
