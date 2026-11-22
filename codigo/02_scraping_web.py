# Estudiante: Noemi Julia Rodrigo Quinto
# Código de matrícula: 2024200521A
# Tema S10 · El costo del capital: El escudo fiscal y su efecto sobre el costo de capital de las empresas peruanas
# Fecha de extracción: se registra en log_ejecucion.txt en cada ejecución
"""
02_scraping_web.py — Vía 2: web scraping del portal de la Bolsa de Valores de Lima (BVL).

Qué extrae y para qué:
  Estados financieros trimestrales (individuales, no auditados) de las emisoras,
  publicados en la ficha "Información financiera" de cada empresa en www.bvl.com.pe:
    - Estado de Situación Financiera -> deuda, patrimonio, activo total
    - Estado de Resultados           -> gasto financiero, utilidad antes de impuestos, impuesto a la renta

Cómo funciona el portal (inspeccionado con las herramientas de desarrollador del navegador):
  La página de la BVL no trae los datos en su HTML: al abrirse, el navegador pide los datos
  a dos direcciones internas del propio portal, sin clave ni registro. El script repite
  exactamente esas mismas solicitudes, con pausa entre cada una:
    1) POST https://dataondemand.bvl.com.pe/v1/issuers/search
         -> lista de emisoras; de aquí se toma el código RPJ de cada empresa (ej. Alicorp = B30006)
    2) POST https://dataondemand.bvl.com.pe/v1/financial-statements/
         -> documentos de una empresa y un año, paginados de 12 en 12 (como en la web)

Entradas : ninguna (consulta el portal en línea).
Salidas  : datos_crudos/bvl_json/emisores_search_<matricula>.json  -> lista de emisoras, byte por byte
           datos_crudos/bvl_json/<TICKER>_<matricula>.json.gz      -> respuestas originales de cada empresa (comprimidas)
           datos_crudos/datos_crudos_scraping_bvl_<matricula>.csv  -> cuentas de los estados financieros en tabla
           datos_crudos/emisores_bvl_<matricula>.csv               -> correspondencia ticker -> código RPJ
           log_ejecucion.txt                                        -> registro acumulativo de cada ejecución
Ejecución: python codigo/02_scraping_web.py   (desde la carpeta del proyecto; tarda unos 25-35 minutos)
"""

import gzip
import hashlib
import json
import shutil
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# =============================================================================
# 1. PARÁMETROS CONGELADOS (nunca fechas dinámicas como "hoy")
# =============================================================================
ANIO_INICIO = 2013   # primer año del análisis
ANIO_CORTE = 2025    # último año del análisis

CODIGO_MATRICULA = "2024200521A"

URL_EMISORES = "https://dataondemand.bvl.com.pe/v1/issuers/search"
URL_ESTADOS = "https://dataondemand.bvl.com.pe/v1/financial-statements/"
URL_ROBOTS = ["https://www.bvl.com.pe/robots.txt", "https://dataondemand.bvl.com.pe/robots.txt"]

# Mismos filtros que se eligen en la web: "Individual" y "Trimestral No Auditada".
TIPO_ESTADO = 1        # 1 = Individual
TIPO_PERIODO = 1       # 1 = Trimestral no auditada (trimestres 1 a 4)
TAMANIO_PAGINA = 12    # documentos por página, igual que la web

# Las mismas 20 emisoras con precios en Yahoo Finance (script 01).
# Clave: ticker de Yahoo. Valor: nemónicos con que puede figurar en la BVL.
# (Buenaventura figura como BVN en Yahoo y como BUENAVC1 en la BVL.)
EMISORAS = {
    "ALICORC1.LM": ["ALICORC1"],
    "UNACEMC1.LM": ["UNACEMC1"],
    "FERREYC1.LM": ["FERREYC1"],
    "CPACASC1.LM": ["CPACASC1"],
    "CORAREI1.LM": ["CORAREI1"],
    "SIDERC1.LM": ["SIDERC1"],
    "BACKUSI1.LM": ["BACKUSI1"],
    "MINSURI1.LM": ["MINSURI1"],
    "VOLCABC1.LM": ["VOLCABC1"],
    "ATACOBC1.LM": ["ATACOBC1"],
    "BVN.LM": ["BUENAVC1", "BVN"],
    "CVERDEC1.LM": ["CVERDEC1"],
    "ENGIEC1.LM": ["ENGIEC1"],
    "LUSURC1.LM": ["LUSURC1"],
    "AUSTRAC1.LM": ["AUSTRAC1"],
    "AIHC1.LM": ["AIHC1"],
    "INRETC1.LM": ["INRETC1"],
    "GLORIAI1.LM": ["GLORIAI1"],
    "NEXAPEC1.LM": ["NEXAPEC1"],
    "EXALMC1.LM": ["EXALMC1"],
}

# Solo se guardan en el CSV los dos estados que necesita el análisis. Se reconocen por
# el título de su primera fila (encabezado); los nombres cambiaron con los años
# ("Balance General" -> "Estado de Situación Financiera"). Las comparaciones se hacen
# sin tildes y en mayúsculas. Los demás estados (flujo de efectivo, cambios en el
# patrimonio, resultados integrales) quedan igual en los JSON originales.
TITULOS_BALANCE = ["SITUACION FINANCIERA", "BALANCE GENERAL"]
TITULOS_RESULTADOS = ["ESTADO DE RESULTADOS", "GANANCIAS Y PERDIDAS"]
EXCLUIR_SI_CONTIENE = ["INTEGRAL"]  # "Estado de Resultados Integrales" no se usa

# Mínimo de emisoras con datos (20 x 52 trimestres = 1 040 observaciones).
MIN_EMISORAS_CON_DATOS = 18

# --- Parámetros de conexión y ética del scraping (numeral 2.4.8) ---------------
PAUSA_SEGUNDOS = 1.5   # pausa entre solicitudes (la consigna exige mínimo 1 s)
TIMEOUT_SEGUNDOS = 60
MAX_INTENTOS = 3
HEADERS = {
    # User-Agent identificable: no se hace pasar por un navegador
    "User-Agent": "UNCP-Finanzas1-Proyecto-Academico/1.0 (uso academico; N. Rodrigo)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# =============================================================================
# 2. RUTAS RELATIVAS A LA CARPETA DEL PROYECTO
# =============================================================================
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_CRUDOS = CARPETA_PROYECTO / "datos_crudos"
CARPETA_JSON = CARPETA_CRUDOS / "bvl_json"
ARCHIVO_EMISORES_JSON = CARPETA_JSON / f"emisores_search_{CODIGO_MATRICULA}.json"
ARCHIVO_CSV = CARPETA_CRUDOS / f"datos_crudos_scraping_bvl_{CODIGO_MATRICULA}.csv"
ARCHIVO_EMISORES_CSV = CARPETA_CRUDOS / f"emisores_bvl_{CODIGO_MATRICULA}.csv"
ARCHIVO_LOG = CARPETA_PROYECTO / "log_ejecucion.txt"


class ErrorExtraccion(Exception):
    """Problema que impide continuar: el script se detiene sin guardar el CSV."""


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


def normalizar(texto):
    """Quita tildes y pasa a mayúsculas, para comparar títulos de forma segura."""
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).upper()


def respaldar_si_existe(archivo, log):
    """Si ya existe un archivo con ese nombre, lo mueve a datos_crudos/respaldos/ en vez de pisarlo."""
    if archivo.exists():
        carpeta = CARPETA_CRUDOS / "respaldos"
        carpeta.mkdir(parents=True, exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta / f"{archivo.stem}_{marca}{archivo.suffix}"
        shutil.move(str(archivo), str(destino))
        registrar(f"Archivo anterior movido a {destino.relative_to(CARPETA_PROYECTO)}", log)


def solicitar(url, cuerpo, log, etiqueta):
    """POST con pausa previa y reintentos.

    Reintenta ante fallas de red o errores del servidor (5xx); ante 4xx se detiene,
    porque la solicitud está mal formada y repetirla no cambia nada.
    Devuelve la respuesta completa (para guardar sus bytes originales).
    """
    for intento in range(1, MAX_INTENTOS + 1):
        time.sleep(PAUSA_SEGUNDOS)  # pausa SIEMPRE antes de cada solicitud
        try:
            r = requests.post(url, json=cuerpo, headers=HEADERS, timeout=TIMEOUT_SEGUNDOS)
        except requests.RequestException as e:
            registrar(f"  {etiqueta}: error de red en intento {intento} ({type(e).__name__})", log)
        else:
            if r.status_code == 200:
                return r
            registrar(f"  {etiqueta}: HTTP {r.status_code} en intento {intento}", log)
            if r.status_code < 500:
                raise ErrorExtraccion(f"{etiqueta}: HTTP {r.status_code}: {r.text[:200]!r}")
        time.sleep(PAUSA_SEGUNDOS * intento)
    return None  # se registra arriba; quien llama decide si es crítico


def revisar_robots(log):
    """Registra qué dice el robots.txt de cada dominio (numeral 2.4.8)."""
    for url in URL_ROBOTS:
        time.sleep(PAUSA_SEGUNDOS)
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SEGUNDOS)
        except requests.RequestException as e:
            registrar(f"robots.txt {url}: sin respuesta ({type(e).__name__})", log)
            continue
        es_robots = "text/plain" in r.headers.get("Content-Type", "")
        if r.status_code == 200 and es_robots:
            registrar(f"robots.txt {url}: HTTP 200. Contenido: {r.text.strip()[:300]!r}", log)
        else:
            # Si devuelve la página web normal (HTML) o un 404, el dominio no publica robots.txt
            registrar(f"robots.txt {url}: HTTP {r.status_code}, "
                      f"{r.headers.get('Content-Type', '?')} -> el dominio no publica reglas de rastreo", log)


# =============================================================================
# 4. PASO 1: LISTA DE EMISORAS Y SUS CÓDIGOS RPJ
# =============================================================================
def obtener_emisoras(log):
    """Pide la lista de emisoras y busca el código RPJ de cada ticker de EMISORAS."""
    r = solicitar(URL_EMISORES, {"firstLetter": "", "sectorCode": "", "companyName": ""},
                  log, "Lista de emisoras")
    if r is None:
        raise ErrorExtraccion("No se obtuvo la lista de emisoras de la BVL")
    try:
        lista = r.json()
    except ValueError:
        raise ErrorExtraccion("La lista de emisoras no es JSON válido")
    if not isinstance(lista, list) or not lista:
        raise ErrorExtraccion("La lista de emisoras llegó vacía o con otra estructura")
    registrar(f"Lista de emisoras: {len(lista)} empresas en el portal", log)

    filas, sin_codigo = [], []
    for ticker_yahoo, nemonicos in EMISORAS.items():
        encontradas = [e for e in lista
                       if any(n in (e.get("stock") or []) for n in nemonicos)]
        if not encontradas:
            sin_codigo.append(ticker_yahoo)
            registrar(f"  {ticker_yahoo}: no figura en la lista de la BVL", log)
            continue
        emp = encontradas[0]
        memorias = emp.get("memory") or []
        rpj = memorias[0].get("rpjCode") if memorias else None
        if not rpj:
            sin_codigo.append(ticker_yahoo)
            registrar(f"  {ticker_yahoo}: figura en la BVL pero sin código RPJ", log)
            continue
        filas.append({"ticker": ticker_yahoo,
                      "nemonicos_bvl": "|".join(emp.get("stock") or []),
                      "empresa": emp.get("companyName"),
                      "company_code": emp.get("companyCode"),
                      "rpj_code": rpj,
                      "sector": emp.get("sectorDescription")})
    emisoras = pd.DataFrame(filas, dtype=str)
    registrar(f"Emisoras con código RPJ: {len(emisoras)} de {len(EMISORAS)}; sin código: {sin_codigo}", log)
    return r, emisoras


# =============================================================================
# 5. PASO 2: ESTADOS FINANCIEROS DE CADA EMPRESA Y AÑO
# =============================================================================
def clasificar(titulo):
    """Devuelve 'balance', 'resultados' o None según el título del encabezado del estado."""
    t = normalizar(titulo)
    if any(x in t for x in EXCLUIR_SI_CONTIENE):
        return None
    if any(x in t for x in TITULOS_BALANCE):
        return "balance"
    if any(x in t for x in TITULOS_RESULTADOS):
        return "resultados"
    return None


def descargar_empresa(emp, log):
    """Recorre todos los años y páginas de una empresa.

    Devuelve (respuestas originales, filas de cuentas, títulos omitidos).
    """
    respuestas, filas, omitidos = [], [], set()
    for anio in range(ANIO_INICIO, ANIO_CORTE + 1):
        pagina = 1
        while True:
            cuerpo = {"page": pagina, "period": TIPO_PERIODO, "periodAccount": "",
                      "rpjCode": emp["rpj_code"], "search": "", "size": TAMANIO_PAGINA,
                      "type": TIPO_ESTADO, "yearPeriod": str(anio)}
            r = solicitar(URL_ESTADOS, cuerpo, log, f"{emp['ticker']} {anio} p{pagina}")
            if r is None:
                registrar(f"  {emp['ticker']} {anio} p{pagina}: sin respuesta tras {MAX_INTENTOS} intentos", log)
                break
            try:
                datos = r.json()
            except ValueError:
                registrar(f"  {emp['ticker']} {anio} p{pagina}: respuesta no es JSON", log)
                break
            # Se guarda la respuesta tal cual llegó (texto original), para la evidencia.
            respuestas.append({"ticker": emp["ticker"], "anio": anio, "pagina": pagina,
                               "solicitud": cuerpo, "respuesta_texto": r.text})

            for doc in datos.get("content") or []:
                renglones = doc.get("document") or []
                if not renglones:
                    continue
                encabezado = renglones[0]  # primera fila: títulos y fechas de las columnas
                estado = clasificar(encabezado.get("title"))
                if estado is None:
                    omitidos.add(normalizar(encabezado.get("title"))[:60])
                    continue
                for fila in renglones[1:]:
                    if not fila.get("caccount"):
                        continue  # filas sin código de cuenta: subtítulos, no montos
                    # Los montos se copian como texto, sin convertir ni redondear.
                    filas.append({
                        "ticker": emp["ticker"], "rpj_code": emp["rpj_code"],
                        "anio": str(doc.get("yearPeriod")), "trimestre": str(doc.get("period")),
                        "estado": estado,
                        "tipo_documento": doc.get("documentType"),
                        "nombre_documento": doc.get("documentName"),
                        "fecha_envio": doc.get("dateHour"),
                        "titulo_principal": encabezado.get("mainTitle"),  # aquí dice la moneda
                        "columna1": encabezado.get("value1"), "columna2": encabezado.get("value2"),
                        "columna3": encabezado.get("value3"), "columna4": encabezado.get("value4"),
                        "cuenta": fila.get("caccount"), "descripcion": fila.get("title"),
                        "valor1": fila.get("value1"), "valor2": fila.get("value2"),
                        "valor3": fila.get("value3"), "valor4": fila.get("value4"),
                    })

            # Paginación: se sigue mientras la respuesta diga que no es la última página.
            total_paginas = datos.get("totalPages") or 1
            if datos.get("last", True) or pagina >= total_paginas:
                break
            pagina += 1
    return respuestas, filas, omitidos


# =============================================================================
# 6. PROGRAMA PRINCIPAL
# =============================================================================
def main():
    log = []
    estado_final = "ERROR"
    inicio = time.time()
    registrar("===== INICIO DE EXTRACCIÓN (02_scraping_web.py) =====", log)
    registrar(f"Fuente: portal de la BVL. Años: {ANIO_INICIO} a {ANIO_CORTE}. "
              f"Pausa entre solicitudes: {PAUSA_SEGUNDOS} s", log)

    try:
        revisar_robots(log)
        r_emisoras, emisoras = obtener_emisoras(log)

        CARPETA_JSON.mkdir(parents=True, exist_ok=True)
        respaldar_si_existe(ARCHIVO_EMISORES_JSON, log)
        ARCHIVO_EMISORES_JSON.write_bytes(r_emisoras.content)  # copia exacta de lo recibido

        todas_filas, todos_omitidos, archivos_json = [], set(), [ARCHIVO_EMISORES_JSON]
        for _, emp in emisoras.iterrows():
            registrar(f"{emp['ticker']} — {emp['empresa']} (RPJ {emp['rpj_code']})", log)
            respuestas, filas, omitidos = descargar_empresa(emp, log)
            todas_filas.extend(filas)
            todos_omitidos |= omitidos
            trimestres = {(f["anio"], f["trimestre"]) for f in filas}
            registrar(f"  -> {len(respuestas)} respuestas, {len(filas)} cuentas, "
                      f"{len(trimestres)} trimestres con datos", log)

            # Respuestas originales de la empresa, comprimidas (sin modificar su contenido).
            nombre = emp["ticker"].replace(".LM", "")
            archivo = CARPETA_JSON / f"{nombre}_{CODIGO_MATRICULA}.json.gz"
            respaldar_si_existe(archivo, log)
            with gzip.open(archivo, "wt", encoding="utf-8") as f:
                json.dump(respuestas, f, ensure_ascii=False)
            archivos_json.append(archivo)

        tabla = pd.DataFrame(todas_filas, dtype=str)

        # Validaciones críticas antes de guardar el CSV.
        if tabla.empty:
            raise ErrorExtraccion("No se extrajo ninguna cuenta de los estados financieros")
        con_datos = tabla["ticker"].nunique()
        if con_datos < MIN_EMISORAS_CON_DATOS:
            raise ErrorExtraccion(f"Solo {con_datos} emisoras con estados financieros "
                                  f"(mínimo {MIN_EMISORAS_CON_DATOS})")

        respaldar_si_existe(ARCHIVO_CSV, log)
        respaldar_si_existe(ARCHIVO_EMISORES_CSV, log)
        tabla.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8", lineterminator="\n")
        emisoras.to_csv(ARCHIVO_EMISORES_CSV, index=False, encoding="utf-8", lineterminator="\n")

        # Resumen de cobertura: trimestres con balance y con estado de resultados por empresa.
        cobertura = (tabla.drop_duplicates(["ticker", "anio", "trimestre", "estado"])
                     .groupby(["ticker", "estado"]).size().unstack(fill_value=0))
        registrar("Cobertura (trimestres con datos por empresa):", log)
        for ticker, fila in cobertura.iterrows():
            registrar(f"  {ticker}: " + ", ".join(f"{k}={v}" for k, v in fila.items()), log)
        if todos_omitidos:
            registrar(f"Estados no usados (quedan en los JSON): {sorted(todos_omitidos)}", log)

        registrar(f"Filas del CSV: {len(tabla)} | Emisoras: {con_datos}", log)
        for archivo in [ARCHIVO_CSV, ARCHIVO_EMISORES_CSV] + archivos_json:
            registrar(f"Guardado: {archivo.relative_to(CARPETA_PROYECTO)} (SHA-256 {sha256(archivo)})", log)
        estado_final = "OK"

    except ErrorExtraccion as e:
        registrar(f"ERROR: {e}", log)
    except Exception as e:  # cualquier falla no prevista también queda en el log
        registrar(f"ERROR INESPERADO: {type(e).__name__}: {e}", log)
    finally:
        registrar(f"Duración: {(time.time() - inicio) / 60:.1f} minutos", log)
        registrar(f"===== FIN. Estado: {estado_final} =====", log)
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n\n")

    if estado_final == "ERROR":
        sys.exit(1)


if __name__ == "__main__":
    main()
