# 08 · Pruebas y Criterios de Aceptación

## Conclusión
La calidad se asegura con un **dataset sintético controlado** (claramente etiquetado como prueba) con casos borde conocidos y resultados esperados calculados a mano. No se usan datos simulados como si fueran reales.

## Niveles de prueba
| Nivel | Qué prueba | Herramienta | Módulo |
|---|---|---|---|
| Unitaria | Fórmulas KPI, umbrales, roll-up, reglas DQ | pytest | M1, M2 |
| Contrato | C1/C2/C3 validan contra el esquema Pydantic | pytest + fixtures JSON | Todos |
| Integración | Cronos contra BD local de prueba (SQLite/Docker del mismo motor) | pytest + fixture SQL | M1 |
| Extremo a extremo | Corrida completa en `--dry-run` | CLI | M0–M3 |
| Caos | BD apagada, tabla eliminada, token Telegram inválido, LLM caído | scripts | M0–M3 |
| Envío real | Buzones y chats de prueba controlados | manual | M3 |

## Dataset de prueba mínimo (`tests/fixtures/`)
| Caso | Esperado |
|---|---|
| Proyecto en tiempo y presupuesto | Overall Verde |
| Atraso −20 pp | Schedule Rojo → Overall Rojo |
| CPI 0.90 | Cost Amarillo |
| Fin plan vencido con 80 % | Schedule Rojo |
| Costo planeado = 0 | Cost `DATO_FALTANTE` (no Verde) |
| Sin Status Report | DQ-01, declarados `DATO_FALTANTE` |
| PM declara Verde, cálculo Rojo | Discrepancia "Optimismo" |
| `percent_complete = 120` | Excluido (DQ-03) |
| Programa con 1 Rojo y 9 Verdes | Distribución 10 % Rojo; peor caso Rojo |
| PM sin `chat_id` | Telegram `SKIPPED`, correo `SENT` |

## Definición de Terminado (por módulo)
- Pruebas unitarias y de contrato en verde.
- Documentación del módulo actualizada (este set de .md).
- Corrida `--dry-run` revisada contra el dataset.
- Sin secretos en el repositorio.

## Qué falta verificar
- Si el curso exige cobertura mínima de pruebas o evidencia específica (capturas, video).
