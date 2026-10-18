# 10 · Riesgos, Brechas y Pendientes

## Conclusión
El riesgo principal no es técnico: es que **los semáforos calculados con umbrales supuestos se lean como verdad oficial**. Segundo riesgo: el alcance de 3 agentes no cubre 2 de los 5 entregables del contexto general.

## Brechas contra el contexto general
| Requisito del contexto | Cubierto por | Estado |
|---|---|---|
| 1 Conectar a réplica | Cronos | Cubierto |
| 2 Leer Projects y Status Reports | Cronos | Cubierto (+ auxiliares) |
| 3 Overall Status Report + estándares de calidad | Cronos (DQ) + Thanatos | Cubierto |
| 4.i KPIs disponibles | Thanatos (snapshot JSON) | Parcial: disponibles en archivo, sin interfaz |
| 4.ii Correo diario | Zeus | Cubierto |
| 4.iii Telegram diario | Zeus | Cubierto (requiere `/start`) |
| 4.iv Dashboard web | — | **Brecha → M4** |
| 4.v Bot bajo demanda (PM/PgM/PfM) | — | **Brecha → M5** |

## Fase 2 (resumen)
| Módulo | Propuesta | Reutiliza |
|---|---|---|
| M4 Dashboard | App web (Streamlit/FastAPI + front) que lee `runs/*/thanatos.json`; vistas Proyecto/Programa/Portafolio; 3 niveles (Salud, Desempeño, Control) | Contrato C2 |
| M5 Bot | Comandos `/sr <proyecto>`, `/programa <id>`, `/portafolio <id>`; ejecuta Cronos→Thanatos con `scope` acotado o lee el último snapshot; autoriza por `chat_id` → rol | M1, M2, `notif_recipient` |

Riesgo M5: un PM no debe poder consultar proyectos ajenos → control de acceso por rol es obligatorio.

## Riesgos
| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Esquema de la réplica distinto a OOB | Media | Alto | S0 de descubrimiento; capa de mapeo configurable |
| Umbrales supuestos generan falsos Rojos | Alta | Medio | Umbrales en YAML; piloto de coincidencia; etiqueta "calculado" visible |
| LLM inventa cifras | Media | Alto | Verificación de `cifras_citadas`; fallback a plantilla |
| Datos sensibles (costos) por Telegram | Media | Medio | Telegram solo con semáforos; costos solo en correo (configurable) |
| SR desactualizados en origen | Alta | Medio | Regla DQ-02 visible en el mensaje |
| Saturación de mensajes | Media | Bajo | Un mensaje por destinatario/canal/día |

## Qué falta verificar (consolidado)
| # | Pendiente | Tipo | Quién lo resuelve |
|---|---|---|---|
| 1 | Motor RDBMS y acceso a la réplica | DATO FALTANTE | Responsable de la réplica / profesor |
| 2 | Nombres reales de tablas/campos (¿OOB intacto?) | SUPUESTO | Desarrollador (S0) |
| 3 | Umbrales oficiales V/A/R | SUPUESTO | PMO / profesor |
| 4 | Frecuencia de refresco de la réplica | DATO FALTANTE | Responsable de la réplica |
| 5 | Proveedor de correo y bot de Telegram | DATO FALTANTE | Desarrollador |
| 6 | Si dashboard y bot son obligatorios para la entrega | DATO FALTANTE | Profesor |
| 7 | Fecha de entrega | DATO FALTANTE | Profesor |
