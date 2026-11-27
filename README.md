# El escudo fiscal y su efecto sobre el costo de capital de las empresas peruanas

Base de datos y código de extracción, limpieza y análisis del artículo de aplicación.

| Dato | Detalle |
|---|---|
| **Estudiante** | Noemi Julia Rodrigo Quinto |
| **Código de matrícula** | 2024200521A |
| **Asignatura** | Finanzas I (055D) · Escuela Profesional de Economía · UNCP |
| **Unidad** | Unidad II · S10 · El costo del capital |
| **Repositorio** | https://github.com/NoemiRodrigo/Finanzas1-u2-escudo-fiscal |

## 1. Objetivo

Medir el ahorro fiscal que genera la deuda (escudo fiscal) y su impacto en el costo promedio ponderado de
capital (WACC) de 20 emisoras no financieras de la Bolsa de Valores de Lima, entre 2013 y 2025.

## 2. Fuentes de datos y vías de extracción

| Vía | Fuente | Procedimiento | Variables aportadas |
|---|---|---|---|
| **API** | BCRPData | `GET https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01129XM-PN01142MM/json/2010-1/2025-12/esp` | Riesgo país; rendimiento del mercado (para la beta) |
| **API** | Yahoo Finance (librería `yfinance`) | `yf.Ticker(<ticker>).history(start="2010-01-01", end="2026-01-01", interval="1mo", auto_adjust=False)` | Precios mensuales de 20 acciones; tasa libre de riesgo (`^TNX`) |
| **Web scraping** | Bolsa de Valores de Lima (portal web) | `POST https://dataondemand.bvl.com.pe/v1/issuers/search` y `POST https://dataondemand.bvl.com.pe/v1/financial-statements/` (solicitudes internas del portal, paginadas) | Gasto financiero, utilidad antes de impuestos, impuesto a la renta, deuda, patrimonio, activo total |

### Series y cuentas utilizadas

| Código | Variable | Descripción | URL de verificación |
|---|---|---|---|
| PN01129XM | `riesgo_pais` | EMBIG Perú, diferencial de rendimientos (pb) | https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01129XM/html |
| PN01142MM | (beta) | Índice General BVL (base 31/12/91 = 100) | https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01142MM/html |
| ^TNX | `rf` | Rendimiento del bono del Tesoro de EE. UU. a 10 años | https://finance.yahoo.com/quote/%5ETNX/ |
| 2D0402 | `gasto_financiero` | Gastos financieros | Ficha del emisor en https://www.bvl.com.pe → Información financiera |
| 2D04ST | `utilidad_antes_impuestos` | Ganancia (pérdida) antes de impuestos | Ídem |
| 2D0502 | `impuesto_renta` | Ingreso (gasto) por impuesto | Ídem |
| 1D0309 + 1D0401 | `deuda` | Otros pasivos financieros corrientes y no corrientes | Ídem |
| 1D07ST | `patrimonio` | Total patrimonio | Ídem |
| 1D020T | `activo_total` | Total de activos | Ídem |

Estados financieros: **Individual · Trimestral No Auditada**, primera columna (trimestre específico / saldo al cierre).
El detalle completo está en `diccionario_variables.md`.

### Emisoras

ALICORC1, UNACEMC1, FERREYC1, CPACASC1, CORAREI1, SIDERC1, BACKUSI1, MINSURI1, VOLCABC1, ATACOBC1,
BVN (BUENAVC1 en la BVL), CVERDEC1, ENGIEC1, LUSURC1, AUSTRAC1, AIHC1, INRETC1, GLORIAI1, NEXAPEC1, EXALMC1.
Se excluyen bancos y aseguradoras. La hoja de especificación del tema indica 25 emisoras; la muestra tiene 20
porque solo esas tienen historial de precios mensuales en Yahoo Finance, necesario para estimar la beta, el costo
del patrimonio y el WACC. En la ejecución final se probaron 28 emisoras no financieras y 8 no tenían historial
(GRAMONC1, ENDISPC1, ENGEPEC1, TELEFBC1, MINCORI1, LAIVEBC1, CERVESC1, ETERNII1); antes se habían descartado
otras 6 por la misma razón (BROCALC1, RELAPAC1, AENZAC1, INVCENC1, CASAGRC1, POMALCC1). Esas empresas sí publican
estados financieros en la BVL. El detalle está en el encabezado de `01_extraccion_api.py` y en el log.

## 3. Periodo y fecha de corte

| Parámetro | Valor |
|---|---|
| `FECHA_INICIO` (API) | 2010-01 (los meses 2010-2012 solo se usan para estimar la beta) |
| `ANIO_INICIO` (scraping) | 2013 |
| `FECHA_CORTE` / `ANIO_CORTE` | 2025-12 / 2025 |
| Periodo del análisis | 2013-T1 a 2025-T4 |
| Observaciones | 1 039 emisora-trimestres (20 emisoras × 52 trimestres, menos 1 no publicado) |
| Fecha de extracción | 2026-11-20 |

Los parámetros están declarados como constantes al inicio de cada script, no como fechas dinámicas.

## 4. Orden de ejecución

```
pip install -r requirements.txt
python codigo/01_extraccion_api.py      # ~1 minuto
python codigo/02_scraping_web.py        # ~45 minutos (pausa de 1,5 s entre solicitudes)
python codigo/03_limpieza_datos.py      # segundos (genera el CSV oficial y su copia en Excel)
python codigo/04_analisis.py            # segundos
```

Cada ejecución añade su registro (fecha, hora, endpoints, códigos HTTP, filas y hashes) a `log_ejecucion.txt`.
`codigo/00_diagnostico_fuentes.py` es un script auxiliar de verificación de fuentes y no forma parte de la cadena. Su resultado (`salidas/diagnostico_fuentes.txt`) documenta la revisión de `robots.txt` y la disponibilidad de cada fuente, incluido el bloqueo de la SMV que llevó a usar el portal de la BVL.

## 5. Verificación de integridad (SHA-256)

| Archivo | Hash SHA-256 |
|---|---|
| `datos_crudos/datos_crudos_api_bcrp_2024200521A.json` | `29bd67eb93f8404d685ad7469a1f2185be129d8ef36f405177c75676684cca83` |
| `datos_crudos/datos_crudos_api_bcrp_2024200521A.csv` | `38a83efae658265093d8804c77d7e11f08e0c699b648be9ee2373c03a62d6a4b` |
| `datos_crudos/datos_crudos_api_yahoo_2024200521A.csv` | `22f19712846d061316a7e23ef09b075d59c1a75da963cc850de4de81884beb74` |
| `datos_crudos/datos_crudos_scraping_bvl_2024200521A.csv` | `1d2109b626743a4f6e0de7b312160cfb63e1a0b79c9ea2d1615b1addb772c72e` |
| `datos_crudos/emisores_bvl_2024200521A.csv` | `ad46b4b199f2fe413b08923123e31309de0be9e0dc11e73edd6feabc0aced650` |
| **`datos_procesados/datos_procesados_2024200521A.csv`** | **`5613d24f71888554352a1d9e801dc219181fd362aea8abf7d7a11fa1197859de`** |

Los hashes de las respuestas originales de la BVL (`datos_crudos/bvl_json/*.json.gz`) figuran en `log_ejecucion.txt`.

El archivo oficial de la base procesada es el **CSV**. El script 03 genera además una copia en Excel
(`datos_procesados_2024200521A.xlsx`) solo para revisarla cómodamente: tiene el encabezado fijo, filtros en cada
columna y una hoja `diccionario` que indica el grupo de cada variable (las seis variables del tema están resaltadas)
y cuándo queda vacía. La copia no se edita a mano y no lleva hash, porque el formato .xlsx guarda la fecha de creación.

Para comprobarlos en Windows (PowerShell, desde la carpeta del proyecto):

```
Get-FileHash datos_crudos\*.csv, datos_crudos\*.json, datos_procesados\*.csv -Algorithm SHA256 | Format-Table Hash, Path -AutoSize
```

## 6. Entorno

| Componente | Versión |
|---|---|
| Python | 3.15.2 |
| Sistema operativo | Windows |

Librerías (versiones exactas en `requirements.txt`):

| Librería | Uso |
|---|---|
| `requests` | Solicitudes a la API del BCRP y al portal de la BVL |
| `yfinance` | Precios de Yahoo Finance |
| `pandas`, `numpy` | Limpieza, unión y cálculo de variables |
| `scipy` | Valores p de la regresión y de la prueba de Hausman |
| `matplotlib` | Figuras |
| `openpyxl` | Copia en Excel de la base procesada |

## 7. Estructura de la carpeta

```
.
├── codigo/
│   ├── 00_diagnostico_fuentes.py   (auxiliar)
│   ├── 01_extraccion_api.py
│   ├── 02_scraping_web.py
│   ├── 03_limpieza_datos.py
│   └── 04_analisis.py
├── datos_crudos/
│   ├── bvl_json/                   (respuestas originales de la BVL, comprimidas)
│   ├── datos_crudos_api_bcrp_2024200521A.json / .csv
│   ├── datos_crudos_api_yahoo_2024200521A.csv
│   ├── datos_crudos_scraping_bvl_2024200521A.csv
│   └── emisores_bvl_2024200521A.csv
├── datos_procesados/
│   ├── datos_procesados_2024200521A.csv    (base oficial)
│   └── datos_procesados_2024200521A.xlsx   (copia en Excel con hoja diccionario)
├── salidas/                        (5 tablas .csv/.tex, 4 figuras .png, resumen y diagnóstico de fuentes)
├── diccionario_variables.md
├── log_ejecucion.txt
├── requirements.txt
├── .env.example
├── .gitattributes
└── README.md
```

## 8. Resultados generados por `04_analisis.py`

| Archivo | Contenido |
|---|---|
| `tabla1_descriptivos` (.csv, .tex) | Estadísticos descriptivos |
| `tabla2_por_anio` (.csv, .tex) | Escudo fiscal y WACC por año (medianas) |
| `tabla3_por_empresa` (.csv, .tex) | Escudo fiscal y WACC por emisora (medianas) |
| `tabla4_regresion` (.csv, .tex) | Regresión de panel: escudo fiscal y endeudamiento |
| `tabla5_hausman` (.csv, .tex) | Prueba de Hausman (efectos fijos frente a aleatorios) y su versión robusta de Mundlak |
| `tabla6_diagnostico` (.csv, .tex) | Diagnóstico y robustez: multicolinealidad (VIF), heterocedasticidad, autocorrelación, dependencia entre emisoras, endogeneidad del escudo y regresión con el escudo de 1 y 4 trimestres antes |
| `figura1_wacc_con_sin_escudo.png` | WACC con y sin escudo fiscal, mediana trimestral |
| `figura2_reduccion_por_empresa.png` | Reducción del WACC por emisora |
| `figura3_riesgo_pais_ke.png` | Riesgo país (BCRP) y costo del patrimonio |
| `figura4_escudo_vs_deuda.png` | Escudo fiscal / activos frente a D/V |
| `resumen_resultados.txt` | Cifras clave |

**Resultados principales:** mediana del WACC de 6,91 % con escudo y 7,55 % sin escudo; reducción mediana atribuible
al escudo fiscal de 0,49 puntos porcentuales (máximo por emisora: EXALMC1, 1,08 p. p.); tasa efectiva mediana de
29,25 %; coeficiente del escudo fiscal sobre activos en el panel con efectos fijos de empresa y año: 49,300 (p < 0,01).
Diagnóstico del modelo (tabla 6): sin multicolinealidad (VIF máximo 1,27); con heterocedasticidad y autocorrelación,
cubiertas por los errores agrupados por empresa; sin dependencia entre emisoras (Pesaran CD, p = 0,93). El escudo no es
exógeno (función de control, p = 0,004), por lo que la relación se interpreta como asociación; se mantiene con el escudo
de 1 y 4 trimestres antes (misma tabla 6).

Cada fuente participa en al menos un resultado: BVL (escudo fiscal, kd), Yahoo Finance (beta y tasa libre de
riesgo → ke) y BCRP (riesgo país e índice de mercado → ke; Figura 3).

## 9. Nota metodológica

- **Costo del patrimonio:** CAPM con riesgo país (rf de EE. UU. + beta × prima + EMBIG), estándar para mercados emergentes.
- **Beta:** ventana móvil de 36 meses frente al Índice General BVL, con ajuste de Blume por la baja negociación de varias acciones.
- **Pesos del WACC:** valores contables, porque no se dispone del historial de acciones en circulación.
- **Deuda material:** kd solo se calcula si la deuda financiera es al menos el 5 % del activo; por debajo, el cociente gasto/deuda no es interpretable y la empresa se trata como no endeudada.
- **Regresión:** panel con efectos fijos de empresa (y de año en el modelo 3), errores estándar agrupados por empresa. La prueba de Hausman rechaza los efectos aleatorios (χ²(4) = 16,57; p = 0,002); la versión robusta de Mundlak no los rechaza (p = 0,191), pero los coeficientes de ambos modelos son casi idénticos. Las observaciones atípicas se marcan y se excluyen del análisis, pero no se eliminan de la base.
- **Coherencia contable:** activo = pasivo + patrimonio y UAI − impuesto = utilidad de operaciones continuas se cumplen en los 1 039 trimestres.

## 10. Ética y uso de IA

- Los datos provienen íntegramente de la ejecución de los scripts de este repositorio.
- Los datos crudos se conservan tal como salieron de la fuente, sin edición.
- El scraping registra el `robots.txt` de cada dominio (ninguno publica reglas de rastreo), usa una pausa de 1,5 s entre solicitudes y un User-Agent identificable.
- Se utilizó asistencia de IA (Claude, de Anthropic) para escribir y depurar el código y redactar la documentación, bajo revisión y comprensión de la estudiante, conforme a lo permitido en la consigna. La estudiante ejecutó todos los scripts y verificó los datos contra la fuente.

## 11. Cita de las fuentes (APA 7.ª edición)

Banco Central de Reserva del Perú. (2026). *BCRPData: Series estadísticas* [Conjunto de datos]. Recuperado el 20 de noviembre de 2026, de https://estadisticas.bcrp.gob.pe/estadisticas/series/

Bolsa de Valores de Lima. (2026). *Información financiera de emisores* [Conjunto de datos]. Recuperado el 20 de noviembre de 2026, de https://www.bvl.com.pe/emisores/listado-emisores

Yahoo Finance. (2026). *Historical data* [Conjunto de datos]. Recuperado el 20 de noviembre de 2026, de https://finance.yahoo.com/

Congreso de la República del Perú. (2014, 31 de diciembre). *Ley N.º 30296, Ley que promueve la reactivación de la economía*. https://www.mef.gob.pe/contenidos/inv_privada/normas/ejt/Ley_30296.pdf

Damodaran, A. (2025, 17 de enero). *Data update 2 for 2025: The party continued (for US equities)*. Musings on Markets. https://aswathdamodaran.blogspot.com/2025/01/data-update-2-for-2025-party-continued.html

Poder Ejecutivo del Perú. (2016, 10 de diciembre). *Decreto Legislativo N.º 1261, Decreto legislativo que modifica la Ley del Impuesto a la Renta*. https://www.leyes.congreso.gob.pe/Documentos/DecretosLegislativos/01261.pdf
