# Estudiante: Noemi Julia Rodrigo Quinto
# Código de matrícula: 2024200521A
# Tema S10 · El costo del capital: El escudo fiscal y su efecto sobre el costo de capital de las empresas peruanas
# Fecha de análisis: se registra en log_ejecucion.txt en cada ejecución
"""
04_analisis.py — Tablas, figuras y regresión del artículo.
Entrada: datos_procesados/datos_procesados_<matricula>.csv
Salidas: salidas/ (tablas en .csv y .tex, figuras en .png, resumen_resultados.txt)
Ejecución: python codigo/04_analisis.py
"""

import hashlib
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # genera imágenes sin abrir ventanas
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
from PIL import Image  # viene instalada con matplotlib
from scipy import stats

# =============================================================================
# 1. PARÁMETROS
# =============================================================================
CODIGO_MATRICULA = "2024200521A"
WINSOR_INFERIOR = 0.01   # recorte del ROA en percentiles 1 y 99
WINSOR_SUPERIOR = 0.99
DPI = 300

# Colores (paleta validada para daltonismo)
AZUL = "#2a78d6"
NARANJA = "#eb6834"
GRIS = "#52514e"
GRILLA = "#e4e3df"

# Nombres de las variables en tablas y figuras
ETIQUETAS = {
    "tasa_efectiva": "Tasa efectiva (%)",
    "escudo_fiscal_activos": "Escudo fiscal / activos (%)",
    "kd": "Costo de la deuda, kd (%)",
    "peso_deuda": "Peso de la deuda, D/V (%)",
    "beta": "Beta ajustada",
    "rf": "Tasa libre de riesgo (%)",
    "riesgo_pais": "Riesgo país, EMBIG (%)",
    "ke": "Costo del patrimonio, ke (%)",
    "wacc": "WACC con escudo (%)",
    "wacc_sin_escudo": "WACC sin escudo (%)",
    "reduccion_wacc": "Reducción del WACC (p. p.)",
    "roa": "Rentabilidad del activo, ROA (%)",
    "tasa_legal": "Tasa legal del IR (%)",
}

# =============================================================================
# 2. RUTAS
# =============================================================================
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
PROCESADO = CARPETA_PROYECTO / "datos_procesados" / f"datos_procesados_{CODIGO_MATRICULA}.csv"
SALIDAS = CARPETA_PROYECTO / "salidas"
ARCHIVO_LOG = CARPETA_PROYECTO / "log_ejecucion.txt"


# =============================================================================
# 3. FUNCIONES AUXILIARES
# =============================================================================
def registrar(mensaje, log):
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
    print(linea)
    log.append(linea)


def sha256(archivo):
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


def numero_es(valor, decimales=2):
    # Formato con coma decimal (APA en español)
    if pd.isna(valor):
        return "--"
    valor = round(float(valor), decimales) + 0.0  # evita "-0,00"
    return f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", " ")


def escapar_latex(texto):
    for a, b in [("%", r"\%"), ("_", r"\_"), ("&", r"\&"), ("^", r"\textasciicircum{}")]:
        texto = str(texto).replace(a, b)
    return texto


def guardar_tabla(tabla, nombre, titulo, nota, log, decimales=2, ancho="1.5cm"):
    # Guarda la tabla en .csv (datos) y en .tex (formato APA para el artículo en LaTeX)
    # Columnas numéricas de ancho fijo y centradas: los encabezados largos pasan a dos líneas
    ruta_csv = SALIDAS / f"{nombre}.csv"
    tabla.to_csv(ruta_csv, encoding="utf-8", lineterminator="\n", float_format="%.6f")
    columnas = [escapar_latex(c) for c in [tabla.index.name or ""] + list(tabla.columns)]
    columna_num = r">{\centering\arraybackslash}p{" + ancho + "}"
    lineas = [r"\begin{table}[htbp]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
              rf"\caption{{{escapar_latex(titulo)}}}", rf"\label{{tab:{nombre}}}",
              r"\begin{tabular}{l" + columna_num * len(tabla.columns) + "}", r"\toprule",
              " & ".join(columnas) + r" \\", r"\midrule"]
    for indice, fila in tabla.iterrows():
        # Las filas de errores estándar (regresión) no repiten el nombre de la variable
        etiqueta = "" if str(indice).endswith("(e. e.)") else indice
        celdas = [escapar_latex(etiqueta)] + [
            escapar_latex(v) if isinstance(v, str) else numero_es(v, decimales) for v in fila]
        # Signo menos tipográfico en los valores negativos
        celdas = [c if i == 0 or not c.startswith("-") else "$-$" + c[1:] for i, c in enumerate(celdas)]
        lineas.append(" & ".join(celdas) + r" \\")
    lineas += [r"\bottomrule", r"\end{tabular}",
               rf"\par\vspace{{2pt}}\footnotesize\raggedright \textit{{Nota.}} {escapar_latex(nota)}",
               r"\end{table}"]
    ruta_tex = SALIDAS / f"{nombre}.tex"
    ruta_tex.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    registrar(f"Tabla: {ruta_csv.name} y {ruta_tex.name}", log)


def estilo_figura(ax):
    # Ejes discretos: grilla suave, sin marco superior ni derecho
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRIS)
    ax.tick_params(colors=GRIS, labelsize=9)
    ax.grid(axis="y", color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    # Coma decimal en los ejes
    coma = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
    ax.yaxis.set_major_formatter(coma)
    if not getattr(ax, "_eje_x_anios", False):
        ax.xaxis.set_major_formatter(coma)


def guardar_figura(fig, nombre, log):
    ruta = SALIDAS / f"{nombre}.png"
    fig.savefig(ruta, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    # PNG sin canal de transparencia: LaTeX lo inserta más rápido
    Image.open(ruta).convert("RGB").save(ruta)
    registrar(f"Figura: {ruta.name}", log)


def periodo_a_numero(periodo):
    # "2013Q1" -> 2013.0 ; "2013Q4" -> 2013.75
    return int(periodo[:4]) + (int(periodo[-1]) - 1) / 4


def mco_cluster(y, X, grupos):
    # Mínimos cuadrados ordinarios con errores estándar agrupados por empresa
    # Cálculo: b = (X'X)^-1 X'y ; V = c (X'X)^-1 [Σ_g X_g' e_g e_g' X_g] (X'X)^-1
    n, k = X.shape
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    xtx_inv = np.linalg.pinv(X.T @ X)
    ids = np.unique(grupos)
    carne = np.zeros((k, k))
    for g in ids:
        s = X[grupos == g].T @ e[grupos == g]
        carne += np.outer(s, s)
    G = len(ids)
    c = (G / (G - 1)) * ((n - 1) / (n - k))   # corrección para pocos grupos
    V = c * xtx_inv @ carne @ xtx_inv
    ee = np.sqrt(np.diag(V))
    t = b / ee
    p = 2 * stats.t.sf(np.abs(t), G - 1)       # t con G-1 grados de libertad
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return b, ee, p, r2, n


def estrellas(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


# =============================================================================
# 4. TABLAS
# =============================================================================
def tabla_descriptivos(d, log):
    # Tabla 1: estadísticos descriptivos
    # Cálculo: N, media, desviación estándar, mínimo, mediana y máximo de cada variable
    variables = ["tasa_efectiva", "escudo_fiscal_activos", "kd", "peso_deuda", "beta", "rf",
                 "riesgo_pais", "ke", "wacc", "wacc_sin_escudo", "reduccion_wacc"]
    filas = {}
    for v in variables:
        s = d[v].dropna()
        filas[ETIQUETAS[v]] = {"N": len(s), "Media": s.mean(), "Desv. est.": s.std(), "Mínimo": s.min(),
                               "Mediana": s.median(), "Máximo": s.max()}
    t = pd.DataFrame(filas).T
    t["N"] = t["N"].map(lambda n: f"{int(n):,}".replace(",", " "))  # N sin decimales
    t.index.name = "Variable"
    guardar_tabla(t, "tabla1_descriptivos", "Estadísticos descriptivos, 20 emisoras, 2013-T1 a 2025-T4",
                  "Tasa efectiva y kd excluyen observaciones atípicas (tasa fuera de 0-100 %; kd > 40 %). "
                  "Fuentes: BVL (estados financieros), Yahoo Finance (precios y ^TNX) y BCRP (EMBIG e Índice "
                  "General BVL). N = número de emisora-trimestres con dato disponible.", log)
    return t


def tabla_por_anio(d, log):
    # Tabla 2: medianas por año
    # Cálculo: mediana anual de tasa legal, tasa efectiva, escudo/activos, WACC con y sin escudo y reducción
    v = ["tasa_legal", "tasa_efectiva", "escudo_fiscal_activos", "wacc", "wacc_sin_escudo", "reduccion_wacc"]
    t = d.groupby("anio")[v].median().rename(columns=ETIQUETAS)
    t.index.name = "Año"
    t.index = t.index.astype(str)
    guardar_tabla(t, "tabla2_por_anio", "Escudo fiscal y WACC por año (medianas)",
                  "Tasa legal: 30 % (2013-2014), 28 % (2015-2016, Ley N.º 30296) y 29,5 % (desde 2017, "
                  "D. Leg. N.º 1261). Reducción del WACC = WACC sin escudo - WACC con escudo.", log,
                  ancho="2.0cm")
    return t


def tabla_por_empresa(d, log):
    # Tabla 3: medianas por empresa
    # Cálculo: mediana 2013-2025 de D/V, kd, ke, WACC con y sin escudo y reducción, por emisora
    v = ["peso_deuda", "kd", "ke", "wacc", "wacc_sin_escudo", "reduccion_wacc"]
    t = d.groupby("ticker")[v].median()
    t["peso_deuda"] = t["peso_deuda"] * 100
    t = t.sort_values("reduccion_wacc", ascending=False).rename(columns=ETIQUETAS)
    t.index = t.index.str.replace(".LM", "", regex=False)
    t.index.name = "Emisora"
    guardar_tabla(t, "tabla3_por_empresa", "Escudo fiscal y WACC por emisora (medianas 2013-2025)",
                  "Ordenado de mayor a menor reducción del WACC. Cada columna es la mediana de los "
                  "trimestres con dato de esa variable; kd solo se calcula cuando la deuda financiera es "
                  "al menos el 5 % del activo.", log, ancho="2.0cm")
    return t


def tabla_regresion(d, log):
    # Tabla 4: regresión de panel
    # Modelo: D/V (%) = a + b1 escudo/activos + b2 ROA + b3 riesgo país + b4 tasa legal + e
    m = d.dropna(subset=["peso_deuda", "escudo_fiscal_activos", "roa", "riesgo_pais"]).copy()
    m = m[m["atipico_kd"] == 0]
    # ROA recortado en percentiles 1 y 99
    # Cálculo: valores fuera de [p1, p99] se reemplazan por p1 o p99
    li, ls = m["roa"].quantile([WINSOR_INFERIOR, WINSOR_SUPERIOR])
    m["roa"] = m["roa"].clip(li, ls)
    y = m["peso_deuda"].values * 100
    grupos = m["ticker"].values
    base = ["escudo_fiscal_activos", "roa", "riesgo_pais", "tasa_legal"]
    ef_empresa = pd.get_dummies(m["ticker"], drop_first=True, dtype=float).values
    ef_anio = pd.get_dummies(m["anio"], drop_first=True, dtype=float).values
    constante = np.ones((len(m), 1))
    modelos = {
        "(1) MCO agrupado": (base, np.hstack([constante, m[base].values])),
        "(2) Efectos fijos empresa": (base, np.hstack([constante, m[base].values, ef_empresa])),
        "(3) EF empresa y año": (base[:2], np.hstack([constante, m[base[:2]].values, ef_empresa, ef_anio])),
    }
    columnas = {}
    for nombre, (vars_x, X) in modelos.items():
        b, ee, p, r2, n = mco_cluster(y, X, grupos)
        col = {}
        for i, v in enumerate(vars_x, start=1):
            col[ETIQUETAS[v]] = f"{numero_es(b[i], 3)}{estrellas(p[i])}"
            col[f"{ETIQUETAS[v]} (e. e.)"] = f"({numero_es(ee[i], 3)})"
        col["Efectos fijos de empresa"] = "No" if nombre.startswith("(1)") else "Sí"
        col["Efectos fijos de año"] = "Sí" if nombre.startswith("(3)") else "No"
        col["Observaciones"] = f"{n:,}".replace(",", " ")
        col["Empresas"] = str(len(np.unique(grupos)))
        col["R²"] = numero_es(r2, 3)
        columnas[nombre] = col
        registrar(f"Regresión {nombre}: b(escudo)={b[1]:.3f}, ee={ee[1]:.3f}, p={p[1]:.4f}, R2={r2:.3f}, n={n}", log)
    t = pd.DataFrame(columnas).fillna("")
    t.index.name = "Variable dependiente: D/V (%)"
    guardar_tabla(t, "tabla4_regresion", "Escudo fiscal y endeudamiento: regresión de panel",
                  "Errores estándar agrupados por empresa entre paréntesis. *** p < 0,01; ** p < 0,05; "
                  "* p < 0,10. ROA recortado en los percentiles 1 y 99. En (3) los efectos fijos de año "
                  "absorben la tasa legal y el riesgo país.", log, ancho="2.6cm")
    return t, m


def tabla_hausman(m, log):
    # Tabla 5: prueba de Hausman (efectos fijos frente a efectos aleatorios)
    # Modelo: D/V (%) = a_i + b1 escudo/activos + b2 ROA + b3 riesgo país + b4 tasa legal + e
    y = m["peso_deuda"].values * 100
    vars_x = ["escudo_fiscal_activos", "roa", "riesgo_pais", "tasa_legal"]
    X = m[vars_x].values
    n, k = X.shape
    ids, idx = np.unique(m["ticker"].values, return_inverse=True)
    G = len(ids)
    T_i = np.bincount(idx)

    def media_empresa(a):
        # Cálculo: promedio de cada empresa, repetido en cada uno de sus trimestres
        suma = np.zeros((G,) + a.shape[1:])
        np.add.at(suma, idx, a)
        return suma / (T_i[:, None] if a.ndim > 1 else T_i)

    y_m, X_m = media_empresa(y), media_empresa(X)

    # Efectos fijos (within)
    # Cálculo: b_EF = MCO de (y - media de la empresa) sobre (X - media de la empresa)
    y_w, X_w = y - y_m[idx], X - X_m[idx]
    b_ef = np.linalg.lstsq(X_w, y_w, rcond=None)[0]
    e_w = y_w - X_w @ b_ef
    s2_e = (e_w @ e_w) / (n - G - k)                     # varianza del error idiosincrático
    V_ef = s2_e * np.linalg.inv(X_w.T @ X_w)

    # Efectos aleatorios (MCG factibles, Swamy-Arora para panel no balanceado)
    # Cálculo: s2_u = varianza de la regresión entre empresas - s2_e / T armónico
    #          theta_i = 1 - raíz(s2_e / (s2_e + T_i s2_u)); MCO de (y - theta_i ȳ_i) sobre (X - theta_i X̄_i)
    Z_b = np.column_stack([np.ones(G), X_m])
    e_b = y_m - Z_b @ np.linalg.lstsq(Z_b, y_m, rcond=None)[0]
    s2_b = (e_b @ e_b) / (G - k - 1)
    s2_u = max(s2_b - s2_e / (G / np.sum(1 / T_i)), 0.0)  # varianza del efecto de empresa
    theta = 1 - np.sqrt(s2_e / (s2_e + T_i * s2_u))
    y_q = y - theta[idx] * y_m[idx]
    X_q = np.column_stack([1 - theta[idx], X - theta[idx][:, None] * X_m[idx]])
    b_ea = np.linalg.lstsq(X_q, y_q, rcond=None)[0][1:]
    V_ea = (s2_e * np.linalg.inv(X_q.T @ X_q))[1:, 1:]

    # Prueba de Hausman clásica
    # Cálculo: H = (b_EF - b_EA)' [V_EF - V_EA]^-1 (b_EF - b_EA) ~ chi2(k)
    q = b_ef - b_ea
    H = float(q @ np.linalg.pinv(V_ef - V_ea) @ q)
    p_H = float(stats.chi2.sf(H, k))

    # Versión robusta (Mundlak): agrega las medias de empresa del escudo y del ROA
    # Cálculo: MCO de y sobre [1, X, X̄_i]; Wald conjunto de las medias = 0 con errores agrupados por empresa
    Z = np.column_stack([np.ones(n), X, X_m[idx][:, :2]])
    b_z = np.linalg.lstsq(Z, y, rcond=None)[0]
    e_z = y - Z @ b_z
    ztz_inv = np.linalg.pinv(Z.T @ Z)
    carne = np.zeros((Z.shape[1], Z.shape[1]))
    for g in range(G):
        s = Z[idx == g].T @ e_z[idx == g]
        carne += np.outer(s, s)
    V_z = (G / (G - 1)) * ((n - 1) / (n - Z.shape[1])) * ztz_inv @ carne @ ztz_inv
    gamma = b_z[-2:]
    W = float(gamma @ np.linalg.inv(V_z[-2:, -2:]) @ gamma)
    p_W = float(stats.chi2.sf(W, 2))

    filas = {}
    for i, v in enumerate(vars_x):
        filas[ETIQUETAS[v]] = {"Efectos fijos": numero_es(b_ef[i], 3), "Efectos aleatorios": numero_es(b_ea[i], 3),
                               "Diferencia": numero_es(q[i], 3)}
    filas["Hausman clásica, chi² (4)"] = {"Efectos fijos": numero_es(H, 2),
                                          "Efectos aleatorios": f"p = {numero_es(p_H, 3)}", "Diferencia": ""}
    filas["Mundlak robusta, chi² (2)"] = {"Efectos fijos": numero_es(W, 2),
                                          "Efectos aleatorios": f"p = {numero_es(p_W, 3)}", "Diferencia": ""}
    t = pd.DataFrame(filas).T
    t.index.name = "Coeficiente"
    guardar_tabla(t, "tabla5_hausman", "Prueba de Hausman: efectos fijos frente a efectos aleatorios",
                  f"Variable dependiente: D/V (%); {n} observaciones de {G} emisoras. Efectos aleatorios por MCG "
                  "factibles (Swamy-Arora). La prueba clásica compara los cuatro coeficientes con varianzas "
                  "convencionales; la versión de Mundlak contrasta las medias de empresa del escudo y del ROA con "
                  "errores agrupados por empresa. H0: los efectos de empresa no están correlacionados con los "
                  "regresores (efectos aleatorios consistentes).", log, ancho="2.6cm")
    registrar(f"Hausman: H={H:.3f}, p={p_H:.4f}; Mundlak robusta: W={W:.3f}, p={p_W:.4f}", log)
    return H, p_H, W, p_W


# =============================================================================
# 5. FIGURAS
# =============================================================================
def figura_wacc(d, log):
    # Figura 1: WACC con y sin escudo fiscal (mediana trimestral)
    s = d.groupby("periodo")[["wacc", "wacc_sin_escudo"]].median()
    x = [periodo_a_numero(p) for p in s.index]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.fill_between(x, s["wacc"], s["wacc_sin_escudo"], color=AZUL, alpha=0.12, linewidth=0)
    ax.plot(x, s["wacc_sin_escudo"], color=NARANJA, linewidth=2, label="WACC sin escudo")
    ax.plot(x, s["wacc"], color=AZUL, linewidth=2, label="WACC con escudo")
    ax.set_ylabel("Mediana (%)", color=GRIS, fontsize=9)
    ax._eje_x_anios = True
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    estilo_figura(ax)
    guardar_figura(fig, "figura1_wacc_con_sin_escudo", log)


def figura_empresas(tabla3, log):
    # Figura 2: reducción del WACC por emisora (barras horizontales)
    col = ETIQUETAS["reduccion_wacc"]
    s = tabla3[col].sort_values()
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    ax.barh(s.index, s.values, color=AZUL, height=0.7)
    for i, v in enumerate(s.values):
        ax.text(v + 0.02, i, numero_es(v), va="center", fontsize=8, color=GRIS)
    ax.set_xlabel("Reducción mediana del WACC (puntos porcentuales)", color=GRIS, fontsize=9)
    estilo_figura(ax)
    ax.yaxis.set_major_formatter(matplotlib.ticker.NullFormatter())
    ax.set_yticks(range(len(s)), s.index)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRILLA, linewidth=0.8)
    guardar_figura(fig, "figura2_reduccion_por_empresa", log)


def figura_riesgo_pais(d, log):
    # Figura 3: riesgo país (BCRP) y costo del patrimonio (mediana trimestral)
    s = d.groupby("periodo")[["riesgo_pais", "ke"]].median()
    x = [periodo_a_numero(p) for p in s.index]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.plot(x, s["ke"], color=AZUL, linewidth=2, label="Costo del patrimonio, ke (mediana)")
    ax.plot(x, s["riesgo_pais"], color=NARANJA, linewidth=2, label="Riesgo país, EMBIG Perú")
    ax.set_ylabel("Porcentaje (%)", color=GRIS, fontsize=9)
    ax.set_ylim(bottom=0)
    ax._eje_x_anios = True
    ax.legend(frameon=False, fontsize=9, loc="center left")
    estilo_figura(ax)
    guardar_figura(fig, "figura3_riesgo_pais_ke", log)


def figura_dispersion(m, log):
    # Figura 4: escudo fiscal / activos frente a D/V
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    x = m["escudo_fiscal_activos"].clip(upper=m["escudo_fiscal_activos"].quantile(0.99))
    y = m["peso_deuda"] * 100
    ax.scatter(x, y, s=10, color=AZUL, alpha=0.45, edgecolors="none")
    pendiente, intercepto = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(xs, intercepto + pendiente * xs, color=NARANJA, linewidth=2, label="Recta de MCO")
    ax.set_xlabel("Escudo fiscal / activos (%)", color=GRIS, fontsize=9)
    ax.set_ylabel("Peso de la deuda, D/V (%)", color=GRIS, fontsize=9)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    estilo_figura(ax)
    guardar_figura(fig, "figura4_escudo_vs_deuda", log)


# =============================================================================
# 6. PROGRAMA PRINCIPAL
# =============================================================================
def main():
    log = []
    estado = "ERROR"
    registrar("===== INICIO DE ANÁLISIS (04_analisis.py) =====", log)
    try:
        if not PROCESADO.exists():
            raise FileNotFoundError("No existe el archivo procesado: ejecuta antes 03_limpieza_datos.py")
        d = pd.read_csv(PROCESADO)
        registrar(f"Leído {PROCESADO.name}: {len(d)} filas (SHA-256 {sha256(PROCESADO)})", log)
        SALIDAS.mkdir(exist_ok=True)

        # Variable de control: ROA anualizado
        # Cálculo: utilidad antes de impuestos × 4 ÷ activo total × 100
        d["roa"] = np.where(d["activo_total"] > 0, d["utilidad_antes_impuestos"] * 4 / d["activo_total"] * 100, np.nan)

        # Muestra sin atípicos para tasa efectiva y kd
        d.loc[d["atipico_tasa_efectiva"] == 1, "tasa_efectiva"] = np.nan
        d.loc[d["atipico_kd"] == 1, "kd"] = np.nan
        d["peso_deuda_pct"] = d["peso_deuda"] * 100

        t1 = tabla_descriptivos(d.assign(peso_deuda=d["peso_deuda_pct"]), log)
        t2 = tabla_por_anio(d, log)
        t3 = tabla_por_empresa(d, log)
        t4, muestra = tabla_regresion(d, log)
        H, p_H, W, p_W = tabla_hausman(muestra, log)
        figura_wacc(d, log)
        figura_empresas(t3, log)
        figura_riesgo_pais(d, log)
        figura_dispersion(muestra, log)

        # Resumen de cifras clave para el artículo
        med = d[["wacc", "wacc_sin_escudo", "reduccion_wacc", "tasa_efectiva"]].median()
        resumen = [
            f"Resumen de resultados — {datetime.now():%Y-%m-%d %H:%M}",
            f"Observaciones: {len(d)} emisora-trimestres, {d['ticker'].nunique()} emisoras, "
            f"{d['periodo'].min()} a {d['periodo'].max()}",
            f"Mediana WACC con escudo: {med['wacc']:.2f} %",
            f"Mediana WACC sin escudo: {med['wacc_sin_escudo']:.2f} %",
            f"Mediana reducción del WACC por el escudo fiscal: {med['reduccion_wacc']:.2f} p. p.",
            f"Mediana tasa efectiva (sin atípicos): {med['tasa_efectiva']:.2f} %",
            f"Emisora con mayor reducción: {t3.index[0]} ({t3.iloc[0][ETIQUETAS['reduccion_wacc']]:.2f} p. p.)",
            f"Emisora con menor reducción: {t3.index[-1]} ({t3.iloc[-1][ETIQUETAS['reduccion_wacc']]:.2f} p. p.)",
            f"Prueba de Hausman clásica: chi2(4) = {H:.2f}, p = {p_H:.3f}",
            f"Prueba de Mundlak robusta: chi2(2) = {W:.2f}, p = {p_W:.3f}",
        ]
        (SALIDAS / "resumen_resultados.txt").write_text("\n".join(resumen) + "\n", encoding="utf-8")
        for linea in resumen[1:]:
            registrar(linea, log)
        estado = "OK"

    except Exception as e:
        registrar(f"ERROR: {type(e).__name__}: {e}", log)
    finally:
        registrar(f"===== FIN. Estado: {estado} =====", log)
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n\n")

    if estado == "ERROR":
        sys.exit(1)


if __name__ == "__main__":
    main()
