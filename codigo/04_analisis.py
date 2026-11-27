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
        celdas = [c if i == 0 else c.replace("= -", "= $-$") for i, c in enumerate(celdas)]
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


def valor_p(p):
    # Valor p con coma decimal; los muy pequeños se muestran como "< 0,001"
    return "< 0,001" if p < 0.001 else numero_es(p, 3)


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
                  f"Variable dependiente: D/V (%); {f'{n:,}'.replace(',', ' ')} observaciones de {G} emisoras. Efectos aleatorios por MCG "
                  "factibles (Swamy-Arora). La prueba clásica compara los cuatro coeficientes con varianzas "
                  "convencionales; la versión de Mundlak contrasta las medias de empresa del escudo y del ROA con "
                  "errores agrupados por empresa. H0: los efectos de empresa no están correlacionados con los "
                  "regresores (efectos aleatorios consistentes).", log, ancho="2.6cm")
    registrar(f"Hausman: H={H:.3f}, p={p_H:.4f}; Mundlak robusta: W={W:.3f}, p={p_W:.4f}", log)
    return H, p_H, W, p_W


def indice_trimestre(periodo):
    # "2013Q1" -> 8052 ; trimestres consecutivos difieren en 1
    return int(periodo[:4]) * 4 + int(periodo[-1]) - 1


def con_rezago(m, d, variable, rezago):
    # Agrega a la muestra m el valor de la variable de la misma emisora "rezago" trimestres antes
    # Se busca en la base completa d, así un trimestre faltante no desplaza el rezago
    previo = d[["ticker", "periodo", variable]].copy()
    previo["q"] = previo["periodo"].map(indice_trimestre) + rezago
    previo = previo.rename(columns={variable: f"{variable}_r{rezago}"}).drop(columns="periodo")
    m = m.copy()
    m["q"] = m["periodo"].map(indice_trimestre)
    return m.merge(previo, on=["ticker", "q"], how="left")


def tabla_diagnostico(m, d, log):
    # Tabla 6: pruebas de diagnóstico del modelo de efectos fijos de empresa (columna 2 de la Tabla 4)
    vars_x = ["escudo_fiscal_activos", "roa", "riesgo_pais", "tasa_legal"]
    m = m.sort_values(["ticker", "periodo"]).reset_index(drop=True)
    y = m["peso_deuda"].values * 100
    grupos = m["ticker"].values
    ids, idx = np.unique(grupos, return_inverse=True)
    G, n = len(ids), len(m)
    ef_empresa = pd.get_dummies(m["ticker"], drop_first=True, dtype=float).values
    X = np.hstack([np.ones((n, 1)), m[vars_x].values, ef_empresa])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b                                        # residuos del modelo de efectos fijos
    filas = {}

    # 1) Multicolinealidad: factor de inflación de la varianza
    # Cálculo: VIF_j = 1 / (1 - R²_j), R²_j de regresar x_j sobre los demás regresores
    vif = {}
    for j, v in enumerate(vars_x):
        otros = np.column_stack([np.ones(n), np.delete(m[vars_x].values, j, axis=1)])
        xj = m[v].values
        r = xj - otros @ np.linalg.lstsq(otros, xj, rcond=None)[0]
        vif[v] = 1 / (r @ r / ((xj - xj.mean()) @ (xj - xj.mean())))
    v_max = max(vif.values())
    filas["Multicolinealidad (VIF máx.)"] = [numero_es(v_max, 2), "",
                                               "No hay" if v_max < 5 else "Sí hay"]

    # 2) Heterocedasticidad entre emisoras: Wald modificado (Greene, 2018)
    # Cálculo: W = Σ (s²_i - s²)² / V_i ; V_i = Σ (e²_it - s²_i)² / [T_i (T_i - 1)] ; W ~ chi2(G)
    T_i = np.bincount(idx)
    s2_i = np.bincount(idx, weights=e ** 2) / T_i
    s2 = e @ e / n
    V_i = np.bincount(idx, weights=(e ** 2 - s2_i[idx]) ** 2) / (T_i * (T_i - 1))
    W_h = float(np.sum((s2_i - s2) ** 2 / V_i))
    p_h = float(stats.chi2.sf(W_h, G))
    filas["Heterocedasticidad (Wald mod.)"] = [f"chi²({G}) = {numero_es(W_h, 1)}", valor_p(p_h),
                                                     "Sí; errores agrupados" if p_h < 0.05 else "No hay"]

    # 3) Autocorrelación de primer orden: Wooldridge (2010)
    # Cálculo: MCO en primeras diferencias; el residuo se regresa sobre su rezago; H0: coeficiente = -0,5
    m["q"] = m["periodo"].map(indice_trimestre)
    consecutivo = (m["ticker"] == m["ticker"].shift(1)) & (m["q"] - m["q"].shift(1) == 1)
    Dy = (pd.Series(y) - pd.Series(y).shift(1))[consecutivo].values
    DX = (m[vars_x] - m[vars_x].shift(1))[consecutivo].values
    u = Dy - DX @ np.linalg.lstsq(DX, Dy, rcond=None)[0]
    du = pd.DataFrame({"g": grupos[consecutivo.values], "q": m["q"][consecutivo].values, "u": u})
    du["u_r"] = du.groupby("g")["u"].shift(1)
    du = du[(du["g"] == du["g"].shift(1)) & (du["q"] - du["q"].shift(1) == 1)]
    b_w, ee_w, _, _, _ = mco_cluster(du["u"].values, du[["u_r"]].values, du["g"].values)
    F_w = float(((b_w[0] + 0.5) / ee_w[0]) ** 2)
    G_w = du["g"].nunique()
    p_w = float(stats.f.sf(F_w, 1, G_w - 1))
    filas["Autocorrelación (Wooldridge)"] = [f"F(1, {G_w - 1}) = {numero_es(F_w, 1)}", valor_p(p_w),
                                             "Sí; errores agrupados" if p_w < 0.05 else "No hay"]

    # 4) Dependencia transversal entre emisoras: CD de Pesaran (2004)
    # Cálculo: CD = raíz(2 / (G (G - 1))) Σ_i<j raíz(T_ij) ρ_ij, con ρ_ij correlación de residuos de i y j
    E = pd.DataFrame({"g": grupos, "periodo": m["periodo"], "e": e}).pivot(index="periodo", columns="g", values="e")
    suma = 0.0
    for i in range(G):
        for j in range(i + 1, G):
            par = E.iloc[:, [i, j]].dropna()
            if len(par) > 3:
                suma += np.sqrt(len(par)) * np.corrcoef(par.iloc[:, 0], par.iloc[:, 1])[0, 1]
    CD = float(np.sqrt(2 / (G * (G - 1))) * suma)
    p_cd = float(2 * stats.norm.sf(abs(CD)))
    filas["Dependencia entre emisoras (CD)"] = [numero_es(CD, 2), valor_p(p_cd),
                                                     "Sí hay" if p_cd < 0.05 else "No hay"]

    # 5) Endogeneidad del escudo: función de control (Wooldridge, 2010)
    # Cálculo: etapa 1: escudo sobre su valor de 4 trimestres antes y los demás regresores (con efectos fijos);
    #          etapa 2: se agrega el residuo de la etapa 1; si es significativo, el escudo no es exógeno
    r = con_rezago(m, d, "escudo_fiscal_activos", 4).dropna(subset=["escudo_fiscal_activos_r4"])
    y_r = r["peso_deuda"].values * 100
    ef_r = pd.get_dummies(r["ticker"], drop_first=True, dtype=float).values
    otros = np.hstack([np.ones((len(r), 1)), r[vars_x[1:]].values, ef_r])
    Z1 = np.hstack([r[["escudo_fiscal_activos_r4"]].values, otros])
    x1 = r["escudo_fiscal_activos"].values
    b1, ee1, _, _, _ = mco_cluster(x1, Z1, r["ticker"].values)
    v = x1 - Z1 @ b1
    X2 = np.hstack([r[["escudo_fiscal_activos"]].values, v[:, None], otros])
    b2, ee2, p2, _, _ = mco_cluster(y_r, X2, r["ticker"].values)
    t_v = float(b2[1] / ee2[1])
    filas["Endogeneidad del escudo"] = [f"t = {numero_es(t_v, 2)}", valor_p(float(p2[1])),
                                                             "Sí; se lee como asociación" if p2[1] < 0.05 else "No hay"]

    # 6) Robustez: el mismo modelo con el escudo de 1 y 4 trimestres antes
    # Si la relación se mantiene con el escudo pasado, no se explica solo por el cálculo del mismo trimestre
    for rezago in [1, 4]:
        r = con_rezago(m, d, "escudo_fiscal_activos", rezago).dropna(subset=[f"escudo_fiscal_activos_r{rezago}"])
        X_r = np.hstack([np.ones((len(r), 1)), r[[f"escudo_fiscal_activos_r{rezago}"] + vars_x[1:]].values,
                         pd.get_dummies(r["ticker"], drop_first=True, dtype=float).values])
        b_r, ee_r, p_r, _, n_r = mco_cluster(r["peso_deuda"].values * 100, X_r, r["ticker"].values)
        texto = "trimestre" if rezago == 1 else "trimestres"
        filas[f"Escudo de {rezago} {texto} antes"] = [f"b = {numero_es(b_r[1], 3)} ({numero_es(ee_r[1], 3)})",
                                                      valor_p(float(p_r[1])),
                                                      "Se mantiene" if p_r[1] < 0.05 and b_r[1] > 0 else "No se mantiene"]
        registrar(f"Robustez escudo rezagado {rezago}: b={b_r[1]:.3f}, ee={ee_r[1]:.3f}, p={p_r[1]:.4f}, n={n_r}", log)

    t = pd.DataFrame(filas, index=["Estadístico", "Valor p", "Resultado"]).T
    t.index.name = "Prueba"
    nombres_vif = {"escudo_fiscal_activos": "escudo fiscal", "roa": "ROA", "riesgo_pais": "riesgo país",
                   "tasa_legal": "tasa legal"}
    vif_txt = "; ".join(f"{nombres_vif[k]} {numero_es(x, 2)}" for k, x in vif.items())
    guardar_tabla(t, "tabla6_diagnostico", "Pruebas de diagnóstico y robustez del modelo de efectos fijos",
                  f"Modelo (2) de la Tabla 4: {f'{n:,}'.replace(',', ' ')} observaciones de {G} emisoras. VIF por variable: "
                  f"{vif_txt}; se considera alto por encima de 5. H0 de cada prueba: varianza del error igual en todas "
                  "las emisoras (Wald modificado); sin autocorrelación de primer orden (Wooldridge); residuos no "
                  "correlacionados entre emisoras (CD de Pesaran); escudo exógeno (función de control, con el escudo de "
                  f"cuatro trimestres antes como instrumento; etapa 1: t = {numero_es(float(b1[0] / ee1[0]), 2)}). "
                  "Las dos últimas filas repiten el modelo con el escudo de trimestres anteriores (coeficiente y error estándar "
                  "agrupado por empresa). Los errores agrupados por emisora son válidos con heterocedasticidad y "
                  "autocorrelación dentro de cada emisora.",
                  log, ancho="2.7cm")
    registrar(f"Diagnóstico: VIF máx={v_max:.2f}; Wald het={W_h:.1f} (p={p_h:.4f}); Wooldridge F={F_w:.2f} "
              f"(p={p_w:.4f}); Pesaran CD={CD:.2f} (p={p_cd:.4f}); endogeneidad t={t_v:.2f} (p={p2[1]:.4f})", log)
    return {"vif": v_max, "W_h": W_h, "p_h": p_h, "F_w": F_w, "p_w": p_w, "CD": CD, "p_cd": p_cd,
            "t_v": t_v, "p_v": float(p2[1])}


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
        diag = tabla_diagnostico(muestra, d, log)
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
            f"VIF máximo: {diag['vif']:.2f}",
            f"Heterocedasticidad (Wald modificado): chi2 = {diag['W_h']:.1f}, p = {diag['p_h']:.4f}",
            f"Autocorrelación (Wooldridge): F = {diag['F_w']:.2f}, p = {diag['p_w']:.4f}",
            f"Dependencia transversal (Pesaran CD): {diag['CD']:.2f}, p = {diag['p_cd']:.4f}",
            f"Endogeneidad del escudo (función de control): t = {diag['t_v']:.2f}, p = {diag['p_v']:.4f}",
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
