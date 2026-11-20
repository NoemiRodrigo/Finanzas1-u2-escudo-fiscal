# Estudiante: Noemi Julia Rodrigo Quinto
# Matrícula: 2024200521A
# Tema: S10 · El costo del capital — El escudo fiscal y su efecto sobre el costo de capital de las empresas peruanas
# Fecha de diagnóstico: se registra automáticamente en el archivo de salida
"""
00_diagnostico_fuentes.py
-------------------------
Script de PRUEBA (no forma parte de los cuatro scripts obligatorios).

Objetivo:comprobar desde tu que cada fuente responde, qué permite su robots.txt y qué estructura tienen sus datos.

Qué hace:
  1. Lee el robots.txt de cada portal (numeral 2.4.8 de la consigna).
  2. Prueba la API de datos abiertos de la SMV (estados financieros).
  3. Prueba la API del BCRP con la serie del EMBIG Perú (PN01129XM).
  4. Prueba si Yahoo Finance tiene precios de acciones peruanas (.LM).

Salida: el archivo salidas/diagnostico_fuentes.txt. 

"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# --------------------------------------------------------------------------
# Parámetros
# --------------------------------------------------------------------------
# Ruta relativa: la carpeta del proyecto es la que contiene /codigo
BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "salidas" / "diagnostico_fuentes.txt"

# User-Agent identificable, como exige la consigna (no se disfraza de navegador)
USER_AGENT = "UNCP-Finanzas1-Proyecto-Academico/1.0 (estudiante de Economia, uso academico)"
HEADERS = {"User-Agent": USER_AGENT}

# Pausa mínima entre solicitudes (la consigna exige al menos 1 segundo)
PAUSA_SEGUNDOS = 1.5
TIMEOUT = 30

lineas = []


def registrar(texto=""):
    """Imprime en pantalla y guarda la línea para el archivo de salida."""
    print(texto)
    lineas.append(str(texto))


def pedir(url):
    """Hace una solicitud GET con pausa previa y devuelve la respuesta (o None)."""
    time.sleep(PAUSA_SEGUNDOS)
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        registrar(f"  URL: {url}")
        registrar(f"  HTTP: {r.status_code} | Tipo: {r.headers.get('Content-Type', '?')} | Bytes: {len(r.content)}")
        return r
    except requests.RequestException as e:
        registrar(f"  URL: {url}")
        registrar(f"  ERROR DE CONEXIÓN: {type(e).__name__}: {e}")
        return None


# --------------------------------------------------------------------------
# 1. robots.txt de cada portal
# --------------------------------------------------------------------------
def probar_robots():
    registrar("=" * 70)
    registrar("1. ROBOTS.TXT")
    registrar("=" * 70)
    portales = [
        "https://mvnet.smv.gob.pe/robots.txt",
        "https://www.smv.gob.pe/robots.txt",
        "https://estadisticas.bcrp.gob.pe/robots.txt",
        "https://www.bvl.com.pe/robots.txt",
    ]
    for url in portales:
        registrar()
        r = pedir(url)
        if r is not None and r.status_code == 200:
            contenido = r.text.strip().splitlines()[:30]
            registrar("  Contenido (primeras 30 líneas):")
            for linea in contenido:
                registrar(f"    | {linea}")


# --------------------------------------------------------------------------
# 2. API de datos abiertos de la SMV
# --------------------------------------------------------------------------
def describir_json(r, etiqueta):
    """Muestra cuántos registros trae un JSON y las columnas del primero."""
    try:
        datos = r.json()
    except ValueError:
        registrar(f"  [{etiqueta}] La respuesta NO es JSON. Primeros 300 caracteres:")
        registrar("  " + r.text[:300].replace("\n", " "))
        return
    # La respuesta puede venir como lista o como diccionario con una lista dentro
    if isinstance(datos, dict):
        registrar(f"  [{etiqueta}] Diccionario con claves: {list(datos.keys())[:15]}")
        listas = [v for v in datos.values() if isinstance(v, list)]
        datos = listas[0] if listas else []
    if isinstance(datos, list):
        registrar(f"  [{etiqueta}] Registros: {len(datos)}")
        if datos:
            registrar(f"  [{etiqueta}] Columnas del primer registro: {list(datos[0].keys())}")
            registrar(f"  [{etiqueta}] Primer registro:")
            registrar("  " + json.dumps(datos[0], ensure_ascii=False)[:800])


def probar_smv():
    registrar()
    registrar("=" * 70)
    registrar("2. API DE DATOS ABIERTOS DE LA SMV")
    registrar("=" * 70)
    base = "https://mvnet.smv.gob.pe/SMV.OData.Api/api/InfFinanciera"

    # Endpoint publicado en datosabiertos.gob.pe (Estado de Situación Financiera).
    # Se prueba el inicio y el final del periodo para ver la cobertura real.
    # sPeriodo y sTipoInf: su significado exacto se confirma con el diccionario de datos.
    pruebas = [
        ("Situación financiera 2024-P1-I", f"{base}/SituacionFinancieraSMV?sEjercicio=2024&sPeriodo=1&sTipoInf=I"),
        ("Situación financiera 2013-P1-I", f"{base}/SituacionFinancieraSMV?sEjercicio=2013&sPeriodo=1&sTipoInf=I"),
        ("Situación financiera 2024-P4-I", f"{base}/SituacionFinancieraSMV?sEjercicio=2024&sPeriodo=4&sTipoInf=I"),
    ]
    # El nombre del endpoint del Estado de Resultados NO está confirmado.
    # Estas son pruebas: un 404 solo significa que ese nombre no existe.
    for nombre in ["ResultadosSMV", "EstadoResultadosSMV", "EstResultadoSMV", "ResultadoSMV"]:
        pruebas.append((f"PRUEBA nombre '{nombre}'", f"{base}/{nombre}?sEjercicio=2024&sPeriodo=1&sTipoInf=I"))

    for etiqueta, url in pruebas:
        registrar()
        registrar(f"- {etiqueta}")
        r = pedir(url)
        if r is not None and r.status_code == 200:
            describir_json(r, etiqueta)


# --------------------------------------------------------------------------
# 3. API del BCRP (EMBIG Perú)
# --------------------------------------------------------------------------
def probar_bcrp():
    registrar()
    registrar("=" * 70)
    registrar("3. API DEL BCRP — EMBIG PERÚ (PN01129XM)")
    registrar("=" * 70)
    url = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01129XM/json/2013-1/2025-12"
    r = pedir(url)
    if r is not None and r.status_code == 200:
        try:
            datos = r.json()
            series = datos.get("config", {}).get("series", [])
            periodos = datos.get("periods", [])
            registrar(f"  Nombre oficial: {series[0].get('name') if series else '?'}")
            registrar(f"  Periodos recibidos: {len(periodos)}")
            if periodos:
                registrar(f"  Primero: {periodos[0]} | Último: {periodos[-1]}")
        except ValueError:
            registrar("  La respuesta no es JSON: " + r.text[:300])


# --------------------------------------------------------------------------
# 4. Yahoo Finance (precios de acciones peruanas)
# --------------------------------------------------------------------------
def probar_yahoo():
    registrar()
    registrar("=" * 70)
    registrar("4. YAHOO FINANCE — ACCIONES DE LA BVL")
    registrar("=" * 70)
    try:
        import yfinance as yf
    except ImportError:
        registrar("  yfinance no está instalado. Ejecuta: pip install yfinance")
        return
    registrar(f"  Versión de yfinance: {yf.__version__}")
    # Tickers de prueba: acciones comunes de la BVL con el sufijo .LM de Yahoo
    for ticker in ["ALICORC1.LM", "UNACEMC1.LM", "FERREYC1.LM", "^SPBLPGPT"]:
        time.sleep(PAUSA_SEGUNDOS)
        try:
            h = yf.Ticker(ticker).history(start="2013-01-01", end="2025-12-31", interval="1mo")
            if h.empty:
                registrar(f"  {ticker}: sin datos")
            else:
                registrar(f"  {ticker}: {len(h)} meses | desde {h.index[0].date()} hasta {h.index[-1].date()}")
        except Exception as e:  # noqa: BLE001 — diagnóstico, se reporta cualquier error
            registrar(f"  {ticker}: ERROR {type(e).__name__}: {e}")


# --------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------
if __name__ == "__main__":
    registrar(f"DIAGNÓSTICO DE FUENTES — {datetime.now():%Y-%m-%d %H:%M:%S}")
    registrar(f"Python {sys.version.split()[0]} | requests {requests.__version__}")
    probar_robots()
    probar_smv()
    probar_bcrp()
    probar_yahoo()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(lineas), encoding="utf-8")
    print(f"\nListo. Resultado guardado en: {SALIDA}")
