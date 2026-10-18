# 06 · M3 — Agente "Zeus" (Comunicador)


> **Actualización 2026-10-18:** el canal de correo se retiró por falta de servidor SMTP. Zeus opera solo con Telegram y el mensaje lleva el detalle de KPIs (se divide en partes si excede el límite).

## Conclusión
Zeus envía **un mensaje por destinatario y canal por día**, con el alcance que le corresponde (PM: sus proyectos; PgM: su programa; PfM: su portafolio). Enviar uno por proyecto saturaría a PgM/PfM.

## Enrutamiento
| Rol | Origen del destinatario (SUPUESTO OOB) | Contenido |
|---|---|---|
| PM | `pm_project.project_manager` → `sys_user.email` | SR de cada proyecto asignado (KPIs 1–19) |
| PgM | `pm_program.program_manager` | Roll-up del programa + proyectos en Rojo + discrepancias "Optimismo" |
| PfM | `pm_portfolio.portfolio_manager` | Roll-up del portafolio + top programas en riesgo |
| Admin técnico | `settings.yaml` | Reporte de fallas de Cronos/Thanatos/Zeus |

## Canales
| Canal | Formato | Requisito |
|---|---|---|
| Correo | HTML + texto plano; asunto `SR diario · <alcance> · <fecha> · Overall <color>` | Cuenta SMTP/Gmail API con remitente autorizado |
| Telegram | Resumen corto (≤ 4 096 caracteres, límite de la API): Overall, 4 semáforos, top 3 alertas, link al correo/dashboard | `chat_id` por usuario en `notif_recipient` |

## Tabla de mapeo `notif_recipient` (nueva, no OOB)
| Campo | Uso |
|---|---|
| `user_sys_id` | Liga a `sys_user` |
| `email` | Override opcional |
| `telegram_chat_id` | Obtenido cuando el usuario envía `/start` al bot |
| `channels` | `email`, `telegram` o ambos |
| `active` | Opt-out |

> HECHO: la Telegram Bot API no permite iniciar conversación con un usuario que no ha escrito al bot. Sin `/start` no hay envío por Telegram; Zeus registra `SKIPPED (sin chat_id)`.

## Reglas de envío
| Regla | Detalle |
|---|---|
| Idempotencia | Llave `run_date + recipient + channel` |
| Reintentos | 3 intentos con backoff; Telegram respeta `retry_after` de la respuesta 429 |
| Fallo de un canal | No bloquea el otro canal ni a otros destinatarios |
| Sin datos | Si Thanatos `FAILED` → no se envía SR; solo alerta técnica |
| Datos parciales | El SR incluye un aviso visible: "Reporte con evidencia incompleta: <motivo>" |
| Dry-run | Renderiza y guarda en `runs/.../outbox/`, no envía |

## Voz y contenido
- Tono profesional, frases directas.
- Colores siempre acompañados de texto (`Rojo`), no solo emoji/color (accesibilidad).
- Cada cifra muestra su origen en el pie del correo (tabla.campo).

## Criterios de aceptación
| Criterio | Meta |
|---|---|
| Entregas exitosas / programadas (con `chat_id` y email válidos) | ≥ 98 % en 10 corridas |
| Duplicados | 0 |
| Destinatario recibe solo su alcance | 100 % en prueba de enrutamiento |

## Qué falta verificar
- Proveedor de correo disponible y límites de envío diario — **DATO FALTANTE**.
- Si los PM/PgM/PfM de la réplica tienen emails reales o ficticios (para pruebas usar buzones controlados).
- Política de privacidad: ¿se permite enviar costos por Telegram?
