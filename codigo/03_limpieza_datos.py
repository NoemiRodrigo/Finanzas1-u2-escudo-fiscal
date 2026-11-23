# Autora: Noemi Julia Rodrigo Quinto
# Código de matrícula: 2024200521A
# Tema S10 · El costo del capital: El escudo fiscal y su efecto sobre el costo de capital de las empresas peruanas
# Fecha de procesamiento: se registra en log_ejecucion.txt en cada ejecución
"""
03_limpieza_datos.py — Limpieza, unión de fuentes y cálculo de variables.
Entradas: datos_crudos/ (BVL, Yahoo, BCRP). Salida: datos_procesados/datos_procesados_<matricula>.csv
Llave común: ticker + trimestre. Ejecución: python codigo/03_limpieza_datos.py
"""

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================================
# 1. PARÁMETROS
# =============================================================================
CODIGO_MATRICULA = "2024200521A"
TRIMESTRE_INICIO = "2013Q1"
TRIMESTRE_CORTE = "2025Q4"

# Cuentas de los estados financieros (formato estándar SMV)
CUENTAS = {
    "2D0402": "gasto_financiero_bruto",
    "2D04ST": "utilidad_antes_impuestos",
    "2D0502": "impuesto_renta_bruto",
    "2D0503": "utilidad_operaciones_continuas",  # solo control
    "1D0309": "deuda_corriente",
    "1D0401": "deuda_no_corriente",
    "1D07ST": "patrimonio",
    "1D020T": "activo_total",
    "1D070T": "pasivo_y_patrimonio",             # solo control
}

# Tasa legal del impuesto a la renta (%): Ley N.º 30296 y D. Leg. N.º 1261
TASA_LEGAL = {2013: 30.0, 2014: 30.0, 2015: 28.0, 2016: 28.0}
TASA_LEGAL_DESDE_2017 = 29.5

# CAPM: prima de mercado de Damodaran (enero 2025)
PRIMA_MERCADO = 4.33
VENTANA_BETA = 36
MIN_MESES_BETA = 24
TICKER_RF = "^TNX"

# Umbrales
UMBRAL_DEUDA_MATERIAL = 5.0    # % del activo total
KD_MAXIMO_PLAUSIBLE = 40.0     # % anual (solo para marcar)
TOLERANCIA_COHERENCIA = 2.0    # miles

# =============================================================================
# 2. RUTAS
# =============================================================================
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_CRUDOS = CARPETA_PROYECTO / "datos_crudos"
CARPETA_PROCESADOS = CARPETA_PROYECTO / "datos_procesados"
CRUDO_BVL = CARPETA_CRUDOS / f"datos_crudos_scraping_bvl_{CODIGO_MATRICULA}.csv"
CRUDO_YAHOO = CARPETA_CRUDOS / f"datos_crudos_api_yahoo_{CODIGO_MATRICULA}.csv"
CRUDO_BCRP = CARPETA_CRUDOS / f"datos_crudos_api_bcrp_{CODIGO_MATRICULA}.csv"
PROCESADO = CARPETA_PROCESADOS / f"datos_procesados_{CODIGO_MATRICULA}.csv"
ARCHIVO_LOG = CARPETA_PROYECTO / "log_ejecucion.txt"


class ErrorLimpieza(Exception):
    """Error que detiene el script sin guardar."""


# =============================================================================
# 3. FUNCIONES AUXILIARES
# =============================================================================
def registrar(mensaje, log):
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
    print(linea)
    log.append(linea)


def sha256(archivo):
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


def leer_crudo(archivo, log):
    # Lectura como texto + hash del crudo
    if not archivo.exists():
        raise ErrorLimpieza(f"No existe {archivo.relative_to(CARPETA_PROYECTO)}: ejecuta antes 01 y 02")
    tabla = pd.read_csv(archivo, dtype=str, keep_default_na=False)
    registrar(f"Leído {archivo.relative_to(CARPETA_PROYECTO)}: {len(tabla)} filas (SHA-256 {sha256(archivo)})", log)
    return tabla


def a_numero(serie, nombre, log):
    # Texto a número: quita espacios y comas
    limpio = serie.astype(str).str.strip().str.replace(",", "", regex=False)
    limpio = limpio.replace({"": np.nan, "nan": np.nan, "None": np.nan, "n.d.": np.nan})
    numeros = pd.to_numeric(limpio, errors="coerce")
    fallidos = limpio.notna() & numeros.isna()
    if fallidos.any():
        registrar(f"ADVERTENCIA {nombre}: {fallidos.sum()} valores no convertibles, "
                  f"ejemplos {sorted(set(limpio[fallidos]))[:5]}", log)
    return numeros


def tasa_legal(anio):
    return TASA_LEGAL.get(int(anio), TASA_LEGAL_DESDE_2017)


# =============================================================================
# 4. ESTADOS FINANCIEROS (BVL)
# =============================================================================
def preparar_bvl(crudo, log):
    # Selección de cuentas y conversión a número
    t = crudo[crudo["cuenta"].isin(CUENTAS)].copy()
    t["valor"] = a_numero(t["valor1"], "BVL valor1", log)
    t["fecha_envio_dt"] = pd.to_datetime(t["fecha_envio"], format="%d-%m-%Y %H:%M:%S", errors="coerce")

    # Reenvíos: se conserva el más reciente
    llave = ["ticker", "anio", "trimestre", "cuenta"]
    antes = len(t)
    t = t.sort_values(llave + ["fecha_envio_dt"]).drop_duplicates(llave, keep="last")
    registrar(f"BVL: {antes - len(t)} cuentas reenviadas descartadas (se conserva el envío más reciente)", log)

    # Moneda del estado (informativa)
    t["moneda"] = np.where(t["titulo_principal"].str.contains("lares", case=False), "USD", "PEN")
    moneda = t.groupby(["ticker", "anio", "trimestre"])["moneda"].first()

    # De formato largo a panel emisora x trimestre
    panel = t.pivot_table(index=["ticker", "anio", "trimestre"], columns="cuenta",
                          values="valor", aggfunc="first").rename(columns=CUENTAS)
    panel = panel.join(moneda).reset_index()
    for falta in set(CUENTAS.values()) - set(panel.columns):
        panel[falta] = np.nan
    panel["periodo"] = pd.PeriodIndex(panel["anio"] + "Q" + panel["trimestre"], freq="Q")

    # Variables directas (gastos en positivo)
    positivos = (panel["gasto_financiero_bruto"] > 0).sum()
    if positivos:
        registrar(f"ADVERTENCIA BVL: {positivos} trimestres con gasto financiero positivo en la fuente; "
                  f"se usa su valor absoluto", log)
    # Gasto financiero
    # Cálculo: |Gastos Financieros (2D0402)|
    panel["gasto_financiero"] = panel["gasto_financiero_bruto"].abs()
    # Impuesto a la renta
    # Cálculo: −1 × Ingreso (Gasto) por Impuesto (2D0502)
    panel["impuesto_renta"] = -panel["impuesto_renta_bruto"]
    # Deuda
    # Cálculo: Otros Pasivos Financieros corrientes (1D0309) + no corrientes (1D0401)
    panel["deuda"] = panel[["deuda_corriente", "deuda_no_corriente"]].sum(axis=1, min_count=1)

    # Controles de coherencia contable
    descuadre_balance = (panel["activo_total"] - panel["pasivo_y_patrimonio"]).abs() > TOLERANCIA_COHERENCIA
    descuadre_resultados = ((panel["utilidad_antes_impuestos"] + panel["impuesto_renta_bruto"]
                             - panel["utilidad_operaciones_continuas"]).abs() > TOLERANCIA_COHERENCIA)
    registrar(f"Control: activo = pasivo + patrimonio en {(~descuadre_balance).sum()} de {len(panel)} trimestres", log)
    registrar(f"Control: UAI - impuesto = utilidad de operaciones continuas en "
              f"{(~descuadre_resultados).sum()} de {len(panel)} trimestres", log)
    return panel


# =============================================================================
# 5. MERCADO: BETA, TASA LIBRE DE RIESGO Y RIESGO PAÍS
# =============================================================================
def preparar_mercado(yahoo, bcrp, log):
    # BCRP: EMBIG e Índice General BVL
    bcrp = bcrp.copy()
    bcrp["mes"] = pd.PeriodIndex(bcrp["fecha"], freq="M")
    bcrp["embig_pb"] = a_numero(bcrp["embig_peru_pb"], "BCRP EMBIG", log)
    bcrp["indice_bvl"] = a_numero(bcrp["indice_general_bvl"], "BCRP Índice BVL", log)
    bcrp = bcrp.sort_values("mes").set_index("mes")
    # Rendimiento del mercado
    # Cálculo: índice del mes ÷ índice del mes anterior − 1
    rend_mercado = bcrp["indice_bvl"].pct_change()

    # Yahoo: precios y ^TNX
    yahoo = yahoo.copy()
    yahoo["mes"] = pd.PeriodIndex(yahoo["fecha"], freq="M")
    yahoo["precio"] = a_numero(yahoo["Adj Close"], "Yahoo Adj Close", log)
    yahoo["cierre"] = a_numero(yahoo["Close"], "Yahoo Close", log)

    # Tasa libre de riesgo (rf)
    # Cálculo: promedio trimestral de ^TNX (%)
    rf = yahoo[yahoo["ticker"] == TICKER_RF].set_index("mes")["cierre"]
    macro = pd.DataFrame({"rf": rf, "embig_pb": bcrp["embig_pb"]})
    macro["periodo"] = macro.index.asfreq("Q")
    macro = macro.groupby("periodo").mean()
    # Riesgo país
    # Cálculo: promedio trimestral del EMBIG Perú (pb) ÷ 100
    macro["riesgo_pais"] = macro["embig_pb"] / 100

    # Beta
    # Cálculo: Cov(rend. acción, rend. mercado) ÷ Var(rend. mercado), últimos 36 meses
    acciones = yahoo[yahoo["ticker"] != TICKER_RF].pivot(index="mes", columns="ticker", values="precio")
    rendimientos = acciones.sort_index().pct_change()
    filas = []
    for ticker in rendimientos.columns:
        datos = pd.DataFrame({"ri": rendimientos[ticker], "rm": rend_mercado}).dropna()
        for fin in pd.period_range(TRIMESTRE_INICIO, TRIMESTRE_CORTE, freq="Q"):
            mes_fin = fin.asfreq("M", how="end")
            ventana = datos[(datos.index > mes_fin - VENTANA_BETA) & (datos.index <= mes_fin)]
            beta = np.nan
            if len(ventana) >= MIN_MESES_BETA and ventana["rm"].var() > 0:
                beta = ventana["ri"].cov(ventana["rm"]) / ventana["rm"].var()
            filas.append({"ticker": ticker, "periodo": fin, "beta_bruta": beta, "meses_beta": len(ventana)})
    betas = pd.DataFrame(filas)
    # Beta ajustada (Blume)
    # Cálculo: 0,67 × beta bruta + 0,33
    betas["beta"] = 0.67 * betas["beta_bruta"] + 0.33
    registrar(f"Betas estimadas: {betas['beta'].notna().sum()} de {len(betas)} emisora-trimestres "
              f"(ventana {VENTANA_BETA} meses, mínimo {MIN_MESES_BETA})", log)
    return betas, macro


# =============================================================================
# 6. CÁLCULO DE VARIABLES
# =============================================================================
def calcular_variables(panel, log):
    p = panel.copy()
    p["tasa_legal"] = p["anio"].map(tasa_legal)

    # Variable 1: tasa efectiva
    # Cálculo: impuesto a la renta ÷ utilidad antes de impuestos × 100 (solo si UAI > 0)
    p["tasa_efectiva"] = np.where(p["utilidad_antes_impuestos"] > 0,
                                  p["impuesto_renta"] / p["utilidad_antes_impuestos"] * 100, np.nan)

    # Variable 2: escudo fiscal
    # Cálculo: tasa legal ÷ 100 × gasto financiero
    p["escudo_fiscal"] = p["tasa_legal"] / 100 * p["gasto_financiero"]
    # Escudo fiscal sobre activos
    # Cálculo: escudo fiscal ÷ activo total × 100
    p["escudo_fiscal_activos"] = np.where(p["activo_total"] > 0,
                                          p["escudo_fiscal"] / p["activo_total"] * 100, np.nan)

    # Deuda material
    # Cálculo: deuda ÷ activo total × 100 ≥ 5
    deuda_activos = np.where(p["activo_total"] > 0, p["deuda"] / p["activo_total"] * 100, np.nan)
    p["deuda_material"] = (deuda_activos >= UMBRAL_DEUDA_MATERIAL).astype(int)

    # Variable 3: costo de la deuda (kd)
    # Cálculo: gasto financiero × 4 ÷ deuda × 100 (solo con deuda material)
    p["kd"] = np.where(p["deuda_material"] == 1, p["gasto_financiero"] * 4 / p["deuda"] * 100, np.nan)

    # Variable 4: peso de la deuda (D/V)
    # Cálculo: deuda ÷ (deuda + patrimonio) (solo si patrimonio > 0)
    valor = p["deuda"] + p["patrimonio"]
    p["peso_deuda"] = np.where((p["patrimonio"] > 0) & (valor > 0), p["deuda"] / valor, np.nan)

    # Variable 5: costo del patrimonio (ke)
    # Cálculo: rf + beta × prima de mercado + riesgo país
    p["prima_mercado"] = PRIMA_MERCADO
    p["ke"] = p["rf"] + p["beta"] * PRIMA_MERCADO + p["riesgo_pais"]

    # Variable 6: WACC
    # Cálculo: (1 − D/V) × ke + D/V × kd × (1 − tasa legal); deuda no material -> D/V = 0
    t = p["tasa_legal"] / 100
    peso_wacc = np.where(p["deuda_material"] == 1, p["peso_deuda"], 0.0)
    peso_wacc = np.where(p["peso_deuda"].isna(), np.nan, peso_wacc)
    termino_deuda = np.where(peso_wacc == 0, 0.0, peso_wacc * p["kd"])
    p["wacc"] = (1 - peso_wacc) * p["ke"] + termino_deuda * (1 - t)

    # WACC sin escudo
    # Cálculo: (1 − D/V) × ke + D/V × kd
    p["wacc_sin_escudo"] = (1 - peso_wacc) * p["ke"] + termino_deuda

    # Variable 7: reducción del WACC por el escudo fiscal
    # Cálculo: WACC sin escudo − WACC
    p["reduccion_wacc"] = p["wacc_sin_escudo"] - p["wacc"]
    registrar(f"Deuda material (>= {UMBRAL_DEUDA_MATERIAL} % del activo): {p['deuda_material'].sum()} "
              f"de {len(p)} emisora-trimestres; el resto se trata como no endeudado en el WACC", log)

    # Marcas de atípicos (no se eliminan)
    p["atipico_tasa_efectiva"] = ((p["tasa_efectiva"] < 0) | (p["tasa_efectiva"] > 100)).astype(int)
    p["atipico_kd"] = (p["kd"] > KD_MAXIMO_PLAUSIBLE).astype(int)
    registrar(f"Atípicos marcados (no eliminados): tasa efectiva fuera de 0-100 % = "
              f"{p['atipico_tasa_efectiva'].sum()}; kd > {KD_MAXIMO_PLAUSIBLE} % = {p['atipico_kd'].sum()}", log)
    return p


# =============================================================================
# 7. PROGRAMA PRINCIPAL
# =============================================================================
COLUMNAS_FINALES = [
    "ticker", "anio", "trimestre", "periodo", "moneda",
    "gasto_financiero", "utilidad_antes_impuestos", "impuesto_renta", "deuda", "patrimonio", "activo_total",
    "rf", "riesgo_pais", "beta_bruta", "beta", "prima_mercado",
    "tasa_legal", "tasa_efectiva", "escudo_fiscal", "escudo_fiscal_activos",
    "deuda_material", "kd", "peso_deuda",
    "ke", "wacc", "wacc_sin_escudo", "reduccion_wacc",
    "atipico_tasa_efectiva", "atipico_kd",
]


def main():
    log = []
    estado = "ERROR"
    registrar("===== INICIO DE LIMPIEZA (03_limpieza_datos.py) =====", log)
    try:
        # Lectura de crudos
        bvl = leer_crudo(CRUDO_BVL, log)
        yahoo = leer_crudo(CRUDO_YAHOO, log)
        bcrp = leer_crudo(CRUDO_BCRP, log)

        # Preparación de cada fuente
        panel = preparar_bvl(bvl, log)
        betas, macro = preparar_mercado(yahoo, bcrp, log)

        # Unión por la llave común (ticker + trimestre)
        panel = panel.merge(betas, on=["ticker", "periodo"], how="left")
        panel = panel.merge(macro[["rf", "riesgo_pais"]], left_on="periodo", right_index=True, how="left")

        # Recorte al periodo de análisis (2010-2012 solo para la beta)
        rango = pd.period_range(TRIMESTRE_INICIO, TRIMESTRE_CORTE, freq="Q")
        panel = panel[panel["periodo"].isin(rango)]

        # Huecos del panel (se informan, no se rellenan)
        esperado = len(rango) * panel["ticker"].nunique()
        registrar(f"Panel: {len(panel)} de {esperado} emisora-trimestres posibles", log)
        faltantes = (pd.MultiIndex.from_product([sorted(panel["ticker"].unique()), rango])
                     .difference(pd.MultiIndex.from_frame(panel[["ticker", "periodo"]])))
        if len(faltantes):
            registrar(f"Trimestres sin estados financieros: {[f'{a} {b}' for a, b in faltantes]}", log)

        # Cálculo de variables
        final = calcular_variables(panel, log)
        final["periodo"] = final["periodo"].astype(str)
        final = final[COLUMNAS_FINALES].sort_values(["ticker", "periodo"]).reset_index(drop=True)

        # Validaciones críticas
        if len(final) < 1000:
            raise ErrorLimpieza(f"Solo {len(final)} observaciones (mínimo 1 000)")
        if final.duplicated(["ticker", "periodo"]).any():
            raise ErrorLimpieza("Hay emisora-trimestres repetidos")

        # Resumen de faltantes
        faltan = final[COLUMNAS_FINALES[5:-2]].isna().sum()
        registrar("Valores faltantes por variable: " +
                  ", ".join(f"{k}={v}" for k, v in faltan.items() if v), log)

        # Guardado (con respaldo del archivo anterior)
        CARPETA_PROCESADOS.mkdir(exist_ok=True)
        if PROCESADO.exists():
            respaldo = CARPETA_PROCESADOS / "respaldos"
            respaldo.mkdir(exist_ok=True)
            destino = respaldo / f"{PROCESADO.stem}_{datetime.now():%Y%m%d_%H%M%S}.csv"
            shutil.move(str(PROCESADO), str(destino))
            registrar(f"Archivo anterior movido a {destino.relative_to(CARPETA_PROYECTO)}", log)
        final.round(6).to_csv(PROCESADO, index=False, encoding="utf-8", lineterminator="\n")

        registrar(f"Datos procesados: {len(final)} filas, {final.shape[1]} columnas, "
                  f"{final['ticker'].nunique()} emisoras, {final['periodo'].min()} a {final['periodo'].max()}", log)
        registrar(f"Guardado: {PROCESADO.relative_to(CARPETA_PROYECTO)} (SHA-256 {sha256(PROCESADO)})", log)
        estado = "OK"

    except ErrorLimpieza as e:
        registrar(f"ERROR: {e}", log)
    except Exception as e:
        registrar(f"ERROR INESPERADO: {type(e).__name__}: {e}", log)
    finally:
        registrar(f"===== FIN. Estado: {estado} =====", log)
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n\n")

    if estado == "ERROR":
        sys.exit(1)


if __name__ == "__main__":
    main()
