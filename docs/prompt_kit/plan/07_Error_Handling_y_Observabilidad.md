# 07 · Error Handling y Observabilidad (transversal)

## Conclusión
Los errores se clasifican por **bloqueante vs. degradante**. Solo los bloqueantes detienen el flujo; los degradantes reducen el alcance y se reportan. Todo error termina en el Reporte de Fallas de la corrida.

## Taxonomía
| Código | Tipo | Ejemplo | Bloqueante | Manejo |
|---|---|---|---|---|
| E-CONN-01 | Conexión | Host inalcanzable / timeout | Sí | 3 reintentos backoff → `FAILED` |
| E-CONN-02 | Autenticación | Credencial inválida | Sí | Sin reintento → `FAILED` |
| E-SCHEMA-01 | Esquema | Tabla núcleo inexistente | Sí | `FAILED` |
| E-SCHEMA-02 | Esquema | Tabla auxiliar / columna inexistente | No | `PARTIAL`, KPI `DATO_FALTANTE` |
| E-READ-01 | Lectura | Query falla a media lectura | Sí (núcleo) / No (aux.) | Reintento; luego según tabla |
| E-DATA-xx | Calidad | Reglas DQ-01…DQ-09 | No | Excluir/marcar registro |
| E-CALC-01 | Cálculo | División por cero, tipo inválido | No | KPI `DATO_FALTANTE` + hallazgo |
| E-LLM-01 | LLM | Timeout / cifra no trazable | No | Plantilla determinista |
| E-SEND-01 | Envío | SMTP/Telegram rechaza | No | Reintento; `FAILED` por entrega |
| E-SEND-02 | Envío | Sin `chat_id` / sin email | No | `SKIPPED` + aviso al PgM |

## Reporte de Fallas (generado por Cronos y ampliado por cada agente)
| Sección | Contenido |
|---|---|
| Encabezado | `run_id`, fecha, señal final, duración |
| Conexión | Estado, intentos, último error |
| Disponibilidad de fuentes | Tabla, ¿existe?, filas leídas |
| Calidad de datos | Conteo por regla DQ y top 10 registros afectados (number, campo, valor) |
| Impacto | KPIs que quedaron `DATO_FALTANTE` y proyectos afectados |
| Acción sugerida | Por código de error (ej. "verificar credenciales en .env") |

Formatos: `failure_report.md` + `failure_report.json` en `runs/AAAA-MM-DD/`; Zeus lo envía al Admin técnico si hay ≥1 error de severidad Alta.

## Observabilidad
| Métrica de operación | Cálculo | Alerta si |
|---|---|---|
| Éxito de corrida | corridas `COMPLETED+PARTIAL` / total | < 95 % semanal |
| Duración | `finished_at − started_at` | > 15 min (SUPUESTO) |
| Tasa de exclusión DQ | `records_excluded / records_in` | > 10 % |
| Tasa de entrega | `SENT / (SENT+FAILED)` | < 98 % |
| Discrepancias "Optimismo" | conteo diario | Informativa (tendencia) |

## Qué falta verificar
- Canal para el Admin técnico (¿mismo correo del alumno?).
- Retención de snapshots (propuesta: 90 días).
