# 05 · M2 — Agente "Thanatos" (Analista)

## Conclusión
Thanatos calcula los 19 indicadores en 3 niveles (Salud, Desempeño, Control), compara la salud **calculada** contra la **declarada** por el PM, agrega a Programa/Portafolio sin promediar colores y genera la narrativa. **Todo número sale de código; el LLM no calcula.**

## Pipeline interno
| # | Paso | Salida |
|---|---|---|
| 1 | Filtrar alcance (`scope`) | Proyectos/Programas/Portafolios a analizar (uno o varios) |
| 2 | Calcular métricas de desempeño | KPIs 6–13 + variaciones |
| 3 | Calcular semáforos derivados | KPIs 2–5 calculados |
| 4 | Calcular Overall derivado | KPI 1 calculado |
| 5 | Comparar con declarado | Bandera de discrepancia |
| 6 | Resumir controles | KPIs 14–19 |
| 7 | Roll-up | Programa y Portafolio |
| 8 | Narrativa (LLM) | Resumen ejecutivo con cifras citadas |
| 9 | Plan de destinatarios | PM / PgM / PfM → contenido |

## Nivel Desempeño — fórmulas
| KPI | Fórmula | Campo origen (SUPUESTO OOB) |
|---|---|---|
| % Avance esperado | `(hoy − inicio_plan) / (fin_plan − inicio_plan)`, acotado 0–100 % | `start_date`, `end_date` |
| Brecha de avance (pp) | `percent_complete − % esperado` | `percent_complete` |
| Variación de fin (días) | `(work_end o fecha estimada) − end_date` | `work_end`, `end_date` |
| Valor ganado (EV) | `cost × percent_complete` | `cost` |
| CPI | `EV / work_cost` | `work_cost` |
| Consumo de presupuesto | `work_cost / cost` | — |
| Índice de esfuerzo | `work_effort / (effort × percent_complete)` | `effort`, `work_effort` |
| Asignado vs real (h) | `horas_reales / horas_asignadas` | `resource_allocation`, `time_card` |

> Limitación: el avance esperado es **lineal** en el tiempo; subestima proyectos con curva S. Evidencia: Media. Mejora futura: usar línea base de tareas.

## Nivel Salud — semáforos calculados (umbrales SUPUESTO, en `thresholds.yaml`)
| KPI | Verde | Amarillo | Rojo |
|---|---|---|---|
| 2 Schedule | brecha ≥ −5 pp | −15 a −5 pp | < −15 pp **o** hoy > fin plan y < 100 % |
| 3 Cost | CPI ≥ 0.95 y consumo ≤ 100 % | CPI 0.85–0.95 | CPI < 0.85 **o** consumo > 100 % |
| 4 Resources | índice 0.90–1.10 | 0.80–0.90 o 1.10–1.25 | < 0.80 o > 1.25 |
| 5 Scope | 0 cambios pendientes | 1–2 cambios pendientes | ≥ 3 pendientes o cambio aprobado sin re-línea base |
| 1 Overall | Ninguno en Amarillo/Rojo | Cualquier Amarillo, o 1 Rojo en Resources/Scope | Rojo en Schedule o Cost, **o** ≥ 2 Rojos |

Reglas:
- Si falta el insumo → semáforo `DATO_FALTANTE` (gris), **nunca Verde por omisión**.
- Overall con algún componente `DATO_FALTANTE` → se marca "Overall con evidencia incompleta".

## Calculado vs declarado
| Caso | Etiqueta | Uso |
|---|---|---|
| Igual | Consistente | — |
| Declarado mejor que calculado (ej. PM dice Verde, cálculo Rojo) | **Optimismo** | Se destaca en el correo al PgM/PfM |
| Declarado peor que calculado | Conservador | Informativo |

> La discrepancia es una señal para revisión, no prueba de error del PM: el cálculo usa una curva lineal y umbrales supuestos (INFERENCIA, evidencia Media).

## Nivel Control — KPIs 14–19
| KPI | Métrica reportada |
|---|---|
| 14 Hitos | completados / totales; vencidos (fin plan < hoy y no cerrados) |
| 15 Riesgos | abiertos; abiertos alta probabilidad × alto impacto; vencidos; sin responsable |
| 16 Issues | abiertos por prioridad; sin responsable |
| 17 Decisiones | pendientes; antigüedad máxima (días) |
| 18 Acciones | pendientes; pendientes de aprobación; vencidas |
| 19 Cambios | por estado; pendientes > 14 días (umbral SUPUESTO) |

## Roll-up Programa / Portafolio (sin promediar colores)
| Métrica | Por qué |
|---|---|
| Distribución V/A/R/Gris por KPI (conteo y %) | Un promedio de colores esconde los rojos |
| Peor caso + lista de proyectos en Rojo | Acción directa |
| % de presupuesto planeado en proyectos Rojo | Pondera por tamaño sin ocultar casos pequeños |
| CPI agregado = ΣEV / ΣAC, más mediana, mín y máx de CPI por proyecto | Muestra dispersión |
| N° de discrepancias "Optimismo" | Calidad del reporte |

## Narrativa (LLM)
| Regla | Implementación |
|---|---|
| Entrada | Solo el JSON de KPIs ya calculados del proyecto/rollup |
| Salida estructurada | `{resumen, top_3_alertas, cifras_citadas[]}` |
| Verificación | Toda cifra en `cifras_citadas` debe existir en el JSON de entrada; si no → se descarta la narrativa y se usa plantilla determinista |
| Fallback | Falla de API LLM → plantilla sin LLM; señal `PARTIAL` |
| Prohibido | Inferir causas no presentes en los datos; afirmar causalidad entre KPIs |

## Criterios de aceptación
| Criterio | Meta |
|---|---|
| Exactitud de semáforos vs cálculo manual | 100 % en dataset de prueba (≥ 20 proyectos con casos borde) |
| Cifras de la narrativa trazables | 100 % |
| Roll-up correcto con 1 proyecto, varios y programa vacío | Pruebas unitarias en verde |

## Qué falta verificar
- Umbrales oficiales de la PMO (si existen) para reemplazar los SUPUESTO.
- Si existe "fecha estimada de fin" en la réplica para la variación de fin.
- Si los costos están en una sola moneda.
