---
name: dashboard-kpi
description: Agregar o modificar un KPI, gráfica o filtro en el Portfolio Health Dashboard (React) del proyecto SPM SR con la paleta PepsiCo validada, capturas de verificación y prueba del PDF.
---

# Cambios al Portfolio Health Dashboard (proyecto AI_M8_FinalAssignment_SPM_SR)

## Arquitectura
| Pieza | Archivo |
|---|---|
| Datos (JSON estático, se regenera cada hora) | `scripts/export_dashboard_data.py` → `dashboard/public/data/kpis.json` |
| Cálculos y filtros del front | `dashboard/src/data.js` (`applyFilters`, `countBy`, `healthByGroup`, …) |
| Gráficas (Recharts) | `dashboard/src/components/Charts.jsx` (`DistChart`, `StackedChart`, `CompareChart`, `CpiChart`, `ProgressScatter`) |
| Pantalla, filtros, toggle de tipo, PDF | `dashboard/src/App.jsx`, `dashboard/src/pdf.js` |
| Paleta | `dashboard/src/theme.js`, `dashboard/src/styles.css` |

Todo el texto visible va en **inglés**. Los nombres de la BD se muestran tal cual.

## Paleta (no inventar colores)
- Series: `#3D63C4`, `#EB7B30`, `#0096D6`; dona de 5: + `#6250D6`, `#E87BA4`; "Other" `#A7AEBB` (más de 5 categorías se pliegan en Other).
- Estado (reservado, siempre con etiqueta): Green `#00984A`, Amber `#E0A000`, Red `#DF002C`, No data `#A7AEBB`.
- Severidad: High `#DF002C`, Medium `#EB7B30`, Low `#E0A000`.
- Color nuevo → validar con el skill `dataviz`: `node <dataviz>/scripts/validate_palette.js "<hex,...>" --mode light`.
- Fuente de la paleta PepsiCo: secundaria (Coloropedia) → evidencia Media; decirlo si se reporta.

## Procedimiento
1. Si el KPI necesita un campo nuevo, agregarlo en `export_dashboard_data.py` (campos en inglés; nada de credenciales, correos ni chat_id: el JSON es público) y regenerar: `python scripts/export_dashboard_data.py`.
2. Implementar en `data.js` + `Charts.jsx` + `App.jsx`. Respetar: la gráfica responde al toggle Bars/Columns/Donut, a los filtros y al clic para filtrar; tooltip; etiquetas en segmentos ≥16 px; ejes con enteros.
3. `cd dashboard && npm run build` (versiones fijas en `package.json`).
4. Capturas con el Playwright global (no instalar otro): `import { chromium } from "$(npm root -g)/playwright/index.mjs"`; servir `dist/` con `python3 -m http.server`. Revisar escritorio 1366 px y celular 390 px (`scrollWidth` debe ser 390: sin scroll horizontal). El error de Google Fonts en el sandbox es esperado.
5. Probar el PDF: clic en `.pdf-btn` con `acceptDownloads`, guardar y revisar con `pdfinfo` + `pdftoppm -r 40`: ninguna gráfica cortada, títulos de sección junto a sus tarjetas, pie con filtros y "Page X of Y".
6. Publicar con el skill `hatchvps-publicar` (`publish_dashboard.yml`).

## Checklist antes de entregar
- [ ] Los 19 KPIs siguen visibles; el panel de proyecto muestra los 19.
- [ ] "Last DB query" arriba a la derecha.
- [ ] Sin colores de estado reutilizados como serie.
- [ ] PDF generado y revisado.
- [ ] Reporte al usuario con tabla y "Qué falta verificar".
