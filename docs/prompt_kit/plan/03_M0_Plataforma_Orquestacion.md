# 03 · M0 — Plataforma y Orquestación

## Conclusión
M0 es el "chasis": configura, ejecuta y registra. Sin M0 los agentes funcionan en pruebas, pero no de forma autónoma diaria.

## Componentes
| Componente | Función | Entregable |
|---|---|---|
| Configuración | `settings.yaml` (BD, alcance, horario, canales) y `thresholds.yaml` (umbrales de semáforo) | Archivos versionados sin secretos |
| Secretos | Credenciales BD, SMTP, token Telegram, API key LLM | `.env` local / gestor de secretos; nunca en repo |
| Orquestador | Ejecuta el grafo Cronos → Thanatos → Zeus con aristas condicionales | `core/orchestrator.py` |
| Run store | Guarda `RunState` serializado por corrida | `runs/AAAA-MM-DD/run_<id>.json` |
| Logging | JSON estructurado con `run_id`, agente, nivel | `runs/.../run.log` |
| Scheduler | Disparo diario | Tarea programada (ej. 07:00 America/Mexico_City, SUPUESTO) |
| Modo manual | `python main.py --scope program:PRG001 --dry-run` | CLI |

## Parámetros de ejecución
| Parámetro | Default | Uso |
|---|---|---|
| `--scope` | todos los proyectos activos | Uno o más proyectos / programas / portafolios |
| `--dry-run` | false | Ejecuta todo y **no envía**; guarda los mensajes renderizados |
| `--as-of` | hoy | Re-ejecutar un día pasado (reproceso) |
| `--agents` | todos | Ejecutar un solo agente con el snapshot previo (depuración) |

## Idempotencia
- Llave de envío: `run_date + recipient + channel`. Si ya existe `SENT`, Zeus no reenvía (evita duplicados al reintentar).

## Criterios de aceptación
| Criterio | Verificación |
|---|---|
| La corrida diaria inicia sin intervención | Log de 5 días hábiles consecutivos |
| `--dry-run` no produce envíos | Bitácora C3 con `SKIPPED` |
| Re-ejecutar el mismo día no duplica mensajes | Prueba de integración |

## Qué falta verificar
- Hora de corte de datos de la réplica (cuándo se refresca) para fijar la hora del scheduler — **DATO FALTANTE**.
- Máquina/servidor donde vivirá el proceso (¿la laptop del alumno o un servidor?) — **DATO FALTANTE**.
