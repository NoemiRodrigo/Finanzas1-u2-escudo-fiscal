# Estudiante: Noemi Julia Rodrigo Quinto
# Código de matrícula: 2024200521A
# Tema S10 · El costo del capital: El escudo fiscal y su efecto sobre el costo de capital de las empresas peruanas
# Fecha de extracción: se registra en log_ejecucion.txt en cada ejecución
"""
01_extraccion_api.py — Vía 1: extracción automatizada por API.

Qué descarga y para qué:
  A) API de BCRPData (no requiere clave):
       PN01129XM  EMBIG Perú (riesgo país)          -> entra en el costo del patrimonio (Ke)
       PN01142MM  Índice General de la BVL          -> rendimiento del mercado, para la beta
  B) API de Yahoo Finance mediante la librería yfinance (no requiere clave):
       Precios mensuales de las acciones de las emisoras -> beta de cada empresa
       ^TNX  Rendimiento del bono del Tesoro de EE. UU. a 10 años -> tasa libre de riesgo (rf)


"""

import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

# =============================================================================
# 1. PARÁMETROS CONGELADOS (nunca fechas dinámicas como "hoy")
# =============================================================================
# Se descarga desde 2010 aunque el análisis empieza en 2013: la beta se estima con
# los 36 meses previos a cada trimestre, así que la de 2013-T1 necesita datos de 2010.
FECHA_INICIO = "2010-01"
FECHA_CORTE = "2025-12"

CODIGO_MATRICULA = "2024200521A"

# --- A) Series del BCRP ---------------------------------------------------------
# Código -> (nombre de la variable, textos que DEBE contener el nombre oficial).
# Los textos permiten comprobar que la API devolvió justo la serie pedida, porque
# el BCRP no respeta el orden de los códigos en su respuesta.
SERIES_BCRP = {
    "PN01129XM": ("embig_peru_pb", ["EMBIG", "Perú"]),
    "PN01142MM": ("indice_general_bvl", ["Índice General BVL"]),
}
URL_BCRP = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

# --- B) Acciones en Yahoo Finance -------------------------------------------------
# Emisoras no financieras de la BVL. Base: constituyentes del S&P/BVL Peru General
# (lista oficial de S&P Dow Jones Indices), ampliada con otras emisoras no financieras
# de la BVL para alcanzar el tamaño mínimo de la consigna (1 000 observaciones).
# Se excluyen bancos y aseguradoras: para ellos la deuda es materia prima, no
# financiamiento, y siguen reglas contables de la SBS.
# Formato de Yahoo para la BVL: nemónico + ".LM".
#
# Excluidas tras la primera ejecución (2026-11-20) porque Yahoo no tiene su historial:
# BROCALC1 (El Brocal), RELAPAC1 (Refinería La Pampilla), AENZAC1 (Aenza),
# INVCENC1 (Inversiones Centenario), CASAGRC1 (Casa Grande), POMALCC1 (Pomalca).
#
# Si un nemónico no tiene datos en Yahoo, el script lo informa en el log y sigue;
# las emisoras con historial incompleto se tratan en 03_limpieza_datos.py, nunca
# editando el archivo crudo.
EMISORAS = {
    # Constituyentes del S&P/BVL Peru General con datos en Yahoo (verificados en la 1.ª ejecución)
    "ALICORC1.LM": "Alicorp",
    "UNACEMC1.LM": "Unacem",
    "FERREYC1.LM": "Ferreycorp",
    "CPACASC1.LM": "Cementos Pacasmayo",
    "CORAREI1.LM": "Corporación Aceros Arequipa",
    "SIDERC1.LM": "Siderperú",
    "BACKUSI1.LM": "Backus",
    "MINSURI1.LM": "Minsur",
    "VOLCABC1.LM": "Volcan",
    "ATACOBC1.LM": "Atacocha",
    "BVN.LM": "Buenaventura",
    "CVERDEC1.LM": "Cerro Verde",
    "ENGIEC1.LM": "Engie Energía Perú",
    "LUSURC1.LM": "Luz del Sur",
    "AUSTRAC1.LM": "Austral Group",
    "AIHC1.LM": "Andino Investment Holding",
    "INRETC1.LM": "InRetail Perú",
    # Otras emisoras no financieras de la BVL (candidatas: se verifican en esta ejecución)
    "GRAMONC1.LM": "Graña y Montero (nemónico anterior de Aenza)",
    "GLORIAI1.LM": "Leche Gloria",
    "ENDISPC1.LM": "Enel Distribución Perú (hoy Pluz Energía)",
    "ENGEPEC1.LM": "Enel Generación Perú",
    "TELEFBC1.LM": "Telefónica del Perú",
    "MINCORI1.LM": "Sociedad Minera Corona",
    "NEXAPEC1.LM": "Nexa Resources Perú (ex Milpo)",
    "LAIVEBC1.LM": "Laive",
    "CERVESC1.LM": "Corporación Cervesur",
    "ETERNII1.LM": "Fábrica Peruana Eternit",
    "EXALMC1.LM": "Pesquera Exalmar",
}
TICKER_RF = "^TNX"  # Rendimiento del bono del Tesoro de EE. UU. a 10 años (en %)

# Mínimo de emisoras con datos para continuar: 52 trimestres (2013-2025) x 20 emisoras
# = 1 040 observaciones. Con menos de 20 no se alcanza el mínimo de la consigna (1 000).
MIN_EMISORAS_CON_DATOS = 20

# --- Parámetros de conexión -----------------------------------------------------
TIMEOUT_SEGUNDOS = 60
MAX_INTENTOS = 3
PAUSA_SEGUNDOS = 1.5  # pausa entre solicitudes, para no saturar los servidores
USER_AGENT = "UNCP-Finanzas1-Proyecto-Academico/1.0 (uso academico; N. Rodrigo)"

# =============================================================================
# 2. RUTAS RELATIVAS A LA CARPETA DEL PROYECTO
# =============================================================================
# Este archivo está en <proyecto>/codigo/, por eso la carpeta del proyecto es la "abuela".
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_CRUDOS = CARPETA_PROYECTO / "datos_crudos"
ARCHIVO_BCRP_JSON = CARPETA_CRUDOS / f"datos_crudos_api_bcrp_{CODIGO_MATRICULA}.json"
ARCHIVO_BCRP_CSV = CARPETA_CRUDOS / f"datos_crudos_api_bcrp_{CODIGO_MATRICULA}.csv"
ARCHIVO_YAHOO_CSV = CARPETA_CRUDOS / f"datos_crudos_api_yahoo_{CODIGO_MATRICULA}.csv"
ARCHIVO_LOG = CARPETA_PROYECTO / "log_ejecucion.txt"

# El BCRP escribe los meses abreviados en español ("Ene.2013"). "Set" por precaución.
MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7,
         "Ago": 8, "Sep": 9, "Set": 9, "Oct": 10, "Nov": 11, "Dic": 12}


class ErrorExtraccion(Exception):
    """Problema que impide continuar: el script se detiene sin guardar datos."""


# =============================================================================
# 3. FUNCIONES AUXILIARES
# =============================================================================
def registrar(mensaje, log):
    """Muestra el mensaje en la consola y lo guarda para escribirlo en el log."""
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
    print(linea)
    log.append(linea)


def sha256(archivo):
    """Huella digital del archivo: si cambia un solo byte, cambia el hash."""
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


def respaldar_si_existe(archivo, log):
    """Si ya existe un archivo con ese nombre, lo mueve a datos_crudos/respaldos/ en vez de pisarlo."""
    if archivo.exists():
        carpeta = archivo.parent / "respaldos"
        carpeta.mkdir(exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta / f"{archivo.stem}_{marca}{archivo.suffix}"
        shutil.move(str(archivo), str(destino))
        registrar(f"Archivo anterior movido a {destino.relative_to(CARPETA_PROYECTO)}", log)


# =============================================================================
# 4. PARTE A: API DEL BCRP
# =============================================================================
def url_bcrp():
    """Arma el endpoint: /api/[códigos]/json/[inicio]/[fin]/esp. Ejemplo de periodo: 2010-1."""
    codigos = "-".join(SERIES_BCRP)
    ini_anio, ini_mes = FECHA_INICIO.split("-")
    fin_anio, fin_mes = FECHA_CORTE.split("-")
    return f"{URL_BCRP}/{codigos}/json/{ini_anio}-{int(ini_mes)}/{fin_anio}-{int(fin_mes)}/esp"


def descargar_bcrp(url, log):
    """GET con reintentos: reintenta ante fallas de red o errores 5xx; se detiene ante 4xx."""
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SEGUNDOS)
        except requests.RequestException as e:
            registrar(f"BCRP intento {intento}: error de red ({type(e).__name__})", log)
        else:
            registrar(f"BCRP intento {intento}: código HTTP {r.status_code}", log)
            if r.status_code == 200:
                return r
            if r.status_code < 500:  # 4xx: la solicitud está mal, reintentar no sirve
                raise ErrorExtraccion(f"BCRP respondió HTTP {r.status_code}: {r.text[:200]!r}")
        if intento < MAX_INTENTOS:
            time.sleep(PAUSA_SEGUNDOS * intento)
    raise ErrorExtraccion(f"BCRP sin respuesta válida tras {MAX_INTENTOS} intentos")


def convertir_fecha_bcrp(texto):
    """Convierte 'Ene.2013' en '2013-01'. Si el formato es otro, detiene el script."""
    try:
        mes, anio = texto.split(".")
        return f"{int(anio):04d}-{MESES[mes]:02d}"
    except (ValueError, KeyError, AttributeError):
        raise ErrorExtraccion(f"Fecha del BCRP con formato inesperado: {texto!r}")


def tabla_bcrp(texto, log):
    """Valida el JSON del BCRP, identifica cada serie por su nombre oficial y arma la tabla."""
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        raise ErrorExtraccion(f"El BCRP no devolvió JSON válido: {texto[:200]!r}")
    if "config" not in datos or "periods" not in datos or not datos["periods"]:
        raise ErrorExtraccion("El JSON del BCRP no tiene la estructura esperada o viene vacío")

    # Control de identidad: cada serie recibida debe encajar con UN solo código pedido.
    series_api = datos["config"].get("series", [])
    if len(series_api) != len(SERIES_BCRP):
        raise ErrorExtraccion(f"Se pidieron {len(SERIES_BCRP)} series y llegaron {len(series_api)}")
    pendientes = dict(SERIES_BCRP)
    nombres = []
    for serie in series_api:
        oficial = serie.get("name", "")
        encajan = [c for c, (_, textos) in pendientes.items()
                   if all(t.lower() in oficial.lower() for t in textos)]
        if len(encajan) != 1:
            raise ErrorExtraccion(f"No se pudo identificar la serie {oficial!r} sin ambigüedad")
        nombre = pendientes.pop(encajan[0])[0]
        nombres.append(nombre)
        registrar(f"BCRP {encajan[0]} -> {nombre}: {oficial}", log)

    # Los valores se copian como texto, sin convertir ni redondear.
    filas = []
    for periodo in datos["periods"]:
        valores = periodo.get("values", [])
        if len(valores) != len(SERIES_BCRP):
            raise ErrorExtraccion(f"El periodo {periodo.get('name')!r} trae valores incompletos")
        fila = {"periodo_bcrp": periodo["name"], "fecha": convertir_fecha_bcrp(periodo["name"])}
        fila.update(zip(nombres, valores))
        filas.append(fila)
    columnas = ["periodo_bcrp", "fecha"] + [n for n, _ in SERIES_BCRP.values()]
    tabla = pd.DataFrame(filas, dtype=str)[columnas]
    if tabla["fecha"].duplicated().any():
        raise ErrorExtraccion("El BCRP devolvió meses repetidos")
    return tabla


def advertencias_bcrp(tabla):
    """Controles que solo avisan: meses faltantes y valores no numéricos (p. ej. 'n.d.')."""
    avisos = []
    esperados = set(pd.period_range(FECHA_INICIO, FECHA_CORTE, freq="M").strftime("%Y-%m"))
    faltan = sorted(esperados - set(tabla["fecha"]))
    if faltan:
        avisos.append(f"BCRP: faltan {len(faltan)} meses: {faltan[:12]}")
    for nombre, _ in SERIES_BCRP.values():
        numeros = pd.to_numeric(tabla[nombre], errors="coerce")
        if numeros.isna().any():
            avisos.append(f"BCRP {nombre}: {numeros.isna().sum()} valores no numéricos")
    return avisos


# =============================================================================
# 5. PARTE B: API DE YAHOO FINANCE (librería yfinance)
# =============================================================================
def descargar_yahoo(log):
    """Descarga precios mensuales de cada emisora y de ^TNX, uno por uno, con pausa.

    Devuelve una tabla "larga": una fila por ticker y mes, con los precios tal como
    los entrega Yahoo. Los tickers sin datos se informan y se omiten.
    """
    # Yahoo trata la fecha final como excluyente: se pide hasta el 1 de enero siguiente
    # para incluir el último mes completo (FECHA_CORTE).
    inicio = f"{FECHA_INICIO}-01"
    fin = str((pd.Period(FECHA_CORTE, freq="M") + 1).start_time.date())

    tickers = {**EMISORAS, TICKER_RF: "Bono Tesoro EE. UU. 10 años"}
    partes, sin_datos = [], []
    for ticker, nombre in tickers.items():
        time.sleep(PAUSA_SEGUNDOS)
        try:
            h = yf.Ticker(ticker).history(start=inicio, end=fin, interval="1mo",
                                          auto_adjust=False, actions=False)
        except Exception as e:  # yfinance puede lanzar errores variados; se registran todos
            registrar(f"Yahoo {ticker}: ERROR {type(e).__name__}: {e}", log)
            sin_datos.append(ticker)
            continue
        if h.empty:
            registrar(f"Yahoo {ticker} ({nombre}): sin datos", log)
            sin_datos.append(ticker)
            continue
        h = h.reset_index()
        # La fecha llega con zona horaria; se guarda como AAAA-MM para unir por mes.
        h.insert(0, "fecha", pd.to_datetime(h["Date"]).dt.strftime("%Y-%m"))
        h.insert(1, "ticker", ticker)
        h.insert(2, "empresa", nombre)
        h = h.drop(columns=["Date"])
        partes.append(h)
        registrar(f"Yahoo {ticker} ({nombre}): {len(h)} meses, "
                  f"{h['fecha'].iloc[0]} a {h['fecha'].iloc[-1]}", log)

    if not partes:
        raise ErrorExtraccion("Yahoo Finance no devolvió datos para ningún ticker")
    tabla = pd.concat(partes, ignore_index=True)

    # Validaciones críticas: sin la tasa libre de riesgo o con muy pocas emisoras
    # no se puede calcular el WACC ni alcanzar el tamaño mínimo de la consigna.
    if TICKER_RF not in set(tabla["ticker"]):
        raise ErrorExtraccion(f"No llegaron datos de {TICKER_RF} (tasa libre de riesgo)")
    con_datos = tabla.loc[tabla["ticker"] != TICKER_RF, "ticker"].nunique()
    registrar(f"Yahoo: {con_datos} de {len(EMISORAS)} emisoras con datos; sin datos: {sin_datos}", log)
    if con_datos < MIN_EMISORAS_CON_DATOS:
        raise ErrorExtraccion(f"Solo {con_datos} emisoras con datos (mínimo {MIN_EMISORAS_CON_DATOS})")
    return tabla


def advertencias_yahoo(tabla):
    """Controles que solo avisan: meses repetidos y rendimientos de ^TNX fuera de rango."""
    avisos = []
    repetidos = tabla.duplicated(subset=["ticker", "fecha"]).sum()
    if repetidos:
        avisos.append(f"Yahoo: {repetidos} filas con ticker y mes repetidos (se resuelven en la limpieza)")
    rf = tabla.loc[tabla["ticker"] == TICKER_RF, "Close"]
    if ((rf < 0) | (rf > 20)).any():
        avisos.append(f"Yahoo {TICKER_RF}: valores fuera del rango 0-20 %; revisar la escala")
    return avisos


# =============================================================================
# 6. PROGRAMA PRINCIPAL
# =============================================================================
def main():
    log = []
    estado = "ERROR"
    registrar("===== INICIO DE EXTRACCIÓN (01_extraccion_api.py) =====", log)
    registrar(f"Periodo solicitado: {FECHA_INICIO} a {FECHA_CORTE}", log)

    try:
        # --- A) BCRP ---
        url = url_bcrp()
        registrar(f"Endpoint BCRP: {url}", log)
        respuesta = descargar_bcrp(url, log)
        t_bcrp = tabla_bcrp(respuesta.text, log)

        # --- B) Yahoo Finance ---
        registrar(f"Yahoo Finance mediante yfinance {yf.__version__}", log)
        t_yahoo = descargar_yahoo(log)

        avisos = advertencias_bcrp(t_bcrp) + advertencias_yahoo(t_yahoo)

        # Solo se guarda cuando TODAS las validaciones críticas pasaron.
        CARPETA_CRUDOS.mkdir(exist_ok=True)
        for archivo in (ARCHIVO_BCRP_JSON, ARCHIVO_BCRP_CSV, ARCHIVO_YAHOO_CSV):
            respaldar_si_existe(archivo, log)
        ARCHIVO_BCRP_JSON.write_bytes(respuesta.content)  # copia exacta de lo recibido
        t_bcrp.to_csv(ARCHIVO_BCRP_CSV, index=False, encoding="utf-8", lineterminator="\n")
        t_yahoo.to_csv(ARCHIVO_YAHOO_CSV, index=False, encoding="utf-8", lineterminator="\n")

        registrar(f"BCRP: {len(t_bcrp)} meses, {t_bcrp['fecha'].iloc[0]} a {t_bcrp['fecha'].iloc[-1]}", log)
        registrar(f"Yahoo: {len(t_yahoo)} filas (ticker x mes)", log)
        for archivo in (ARCHIVO_BCRP_JSON, ARCHIVO_BCRP_CSV, ARCHIVO_YAHOO_CSV):
            registrar(f"Guardado: {archivo.relative_to(CARPETA_PROYECTO)} (SHA-256 {sha256(archivo)})", log)
        for aviso in avisos:
            registrar(f"ADVERTENCIA: {aviso}", log)
        estado = "OK" if not avisos else "OK CON ADVERTENCIAS"

    except ErrorExtraccion as e:
        registrar(f"ERROR: {e}", log)
    except Exception as e:  # cualquier falla no prevista también queda en el log
        registrar(f"ERROR INESPERADO: {type(e).__name__}: {e}", log)
    finally:
        registrar(f"===== FIN. Estado: {estado} =====", log)
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n\n")

    if estado == "ERROR":
        sys.exit(1)


if __name__ == "__main__":
    main()
