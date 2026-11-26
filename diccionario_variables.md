# Diccionario de variables

**Proyecto:** El escudo fiscal y su efecto sobre el costo de capital de las empresas peruanas
**Estudiante:** Noemi Julia Rodrigo Quinto · 2024200521A
**Archivo descrito:** `datos_procesados/datos_procesados_2024200521A.csv`
**Unidad de observación:** emisora × trimestre · **Periodo:** 2013-T1 a 2025-T4 · **Filas:** 1 039 · **Columnas:** 29

**Copia en Excel:** `datos_procesados/datos_procesados_2024200521A.xlsx` (generada por `03_limpieza_datos.py`) contiene
la misma tabla y una hoja `diccionario` con el grupo de cada columna. Grupos: identificación (5), variables del tema (6:
`gasto_financiero`, `utilidad_antes_impuestos`, `impuesto_renta`, `tasa_efectiva`, `deuda`, `wacc`), insumos para el
WACC (12), resultados del tema (4) y control de calidad (2).

Los montos de los estados financieros están en **miles** de la moneda de presentación de cada empresa
(soles o dólares, ver columna `moneda`). Las variables del análisis son proporciones o tasas, por lo que no
dependen de la moneda.

## 1. Identificación (llave común)

| Variable | Tipo | Descripción |
|---|---|---|
| `ticker` | texto | Código de la acción en Yahoo Finance (nemónico BVL + `.LM`) |
| `anio` | entero | Año del estado financiero |
| `trimestre` | entero | Trimestre (1 a 4) |
| `periodo` | texto | Año y trimestre, formato `AAAAQn` (ej. `2024Q4`) |
| `moneda` | texto | Moneda declarada en el estado financiero: `PEN` o `USD` |

## 2. Variables de los estados financieros (vía 2: scraping BVL)

| Variable | Unidad | Cuenta SMV | Descripción |
|---|---|---|---|
| `gasto_financiero` | miles | 2D0402 | Gastos financieros del trimestre (valor absoluto) |
| `utilidad_antes_impuestos` | miles | 2D04ST | Ganancia (pérdida) antes de impuestos del trimestre |
| `impuesto_renta` | miles | 2D0502 | Gasto por impuesto a la renta del trimestre (−1 × valor de la fuente) |
| `deuda` | miles | 1D0309 + 1D0401 | Otros pasivos financieros corrientes + no corrientes, al cierre |
| `patrimonio` | miles | 1D07ST | Total patrimonio, al cierre |
| `activo_total` | miles | 1D020T | Total de activos, al cierre |

## 3. Variables de mercado (vía 1: API BCRP y Yahoo Finance)

| Variable | Unidad | Fuente | Descripción |
|---|---|---|---|
| `rf` | % | Yahoo Finance, `^TNX` | Rendimiento del bono del Tesoro de EE. UU. a 10 años, promedio trimestral |
| `riesgo_pais` | % | BCRP, PN01129XM | EMBIG Perú (puntos básicos ÷ 100), promedio trimestral |
| `beta_bruta` | — | Yahoo Finance + BCRP, PN01142MM | Cov(rend. acción, rend. Índice General BVL) ÷ Var(rend. índice), 36 meses previos |
| `beta` | — | calculada | Beta ajustada de Blume: 0,67 × beta bruta + 0,33 |
| `prima_mercado` | % | Damodaran (2025) | Prima de riesgo de mercado constante: 4,33 % |

## 4. Variables calculadas

| Variable | Unidad | Cálculo |
|---|---|---|
| `tasa_legal` | % | Tasa del IR de tercera categoría: 30 (2013-2014), 28 (2015-2016), 29,5 (desde 2017) |
| `tasa_efectiva` | % | impuesto_renta ÷ utilidad_antes_impuestos × 100 (solo si UAI > 0) |
| `escudo_fiscal` | miles | tasa_legal ÷ 100 × gasto_financiero |
| `escudo_fiscal_activos` | % | escudo_fiscal ÷ activo_total × 100 |
| `deuda_material` | 0/1 | 1 si deuda ÷ activo_total × 100 ≥ 5 |
| `kd` | % anual | gasto_financiero × 4 ÷ deuda × 100 (solo si deuda_material = 1) |
| `peso_deuda` | proporción | deuda ÷ (deuda + patrimonio) (solo si patrimonio > 0) |
| `ke` | % | rf + beta × prima_mercado + riesgo_pais |
| `wacc` | % | (1 − D/V) × ke + D/V × kd × (1 − tasa_legal); D/V = 0 si deuda_material = 0 |
| `wacc_sin_escudo` | % | (1 − D/V) × ke + D/V × kd |
| `reduccion_wacc` | p. p. | wacc_sin_escudo − wacc |

## 5. Marcas de calidad

| Variable | Valores | Descripción |
|---|---|---|
| `atipico_tasa_efectiva` | 0/1 | 1 si tasa_efectiva < 0 % o > 100 % (se conserva; se excluye en las tablas) |
| `atipico_kd` | 0/1 | 1 si kd > 40 % (se conserva; se excluye en las tablas y la regresión) |

## 6. Valores faltantes

Se dejan vacíos, sin imputar: `tasa_efectiva` cuando la utilidad antes de impuestos es ≤ 0; `kd` cuando la
deuda no es material; `beta` y `ke` cuando hay menos de 24 meses de precios; `wacc` cuando falta `ke` o
`peso_deuda`. Falta un trimestre completo: ATACOBC1, 2023-T1 (no publicado en la BVL).

| Columna | Celdas vacías | Causa |
|---|---|---|
| `beta_bruta`, `beta`, `ke` | 16 | AIHC1 (2013-T1 a T4), EXALMC1 (2013-T1 a 2014-T1) e INRETC1 (2013-T1 a 2014-T3): sus precios en Yahoo Finance empiezan en 2012, así que no hay 24 meses previos |
| `tasa_efectiva` | 185 | Trimestres con utilidad antes de impuestos menor o igual a cero |
| `kd` | 207 | Trimestres con deuda financiera menor al 5 % del activo |
| `peso_deuda` | 18 | ATACOBC1 con patrimonio negativo (2020-T1 a 2024-T3) |
| `wacc`, `wacc_sin_escudo`, `reduccion_wacc` | 34 | 16 sin `ke` + 18 sin `peso_deuda` |
