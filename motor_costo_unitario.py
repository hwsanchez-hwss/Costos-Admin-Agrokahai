# -*- coding: utf-8 -*-
"""
MOTOR DE COSTO UNITARIO — PARTE AGRÍCOLA (AGROCACAY)
====================================================
Hace exactamente lo mismo que la hoja UNIT de Ana_Costos_AGRO.xlsx:
a cada fila de costo (nómina y terceros) le busca un DIVISOR según la
regla de su rubro y calcula  COSTO_UNITARIO = DEBITO / DIVISOR.

Reglas (se leen de la hoja "⚙ CONFIG" del Excel, no están escritas aquí):
    CENSO           -> árboles del lote en ese año (hoja CENSO)
    PXN_KG          -> kg cosechados en el lote ese año y mes (hoja PXN).
                       Si la asignación es "Cosecha" (sin lote), los kg de TODO el año.
    SITIOS_SIEMBRA  -> sitios sembrados en el año (hoja ARB_TOTAL, tabla de la derecha)
    SYRS_ARBOLES    -> árboles sembrados/resembrados del lote en el año (hoja SYRS)
    ARB_TotalVivos  -> total de sitios vivos del año (hoja ARB_TOTAL)
    Rubro sin regla -> ARB_TotalVivos

Respaldo (igual que la fórmula del Excel):
  - EXCEPCIÓN SIEMBRA: si no hay sitios sembrados para el año (SITIOS_SIEMBRA vacío o 0),
    el costo unitario queda EN BLANCO (no se divide por los árboles vivos de la finca).
  - Si el divisor de la regla da 0 (no hay censo de ese lote ese año, no hubo
    cosecha ese mes en ese lote, etc.) se usa ARB_TotalVivos del año.
  - Si tampoco hay ARB_TotalVivos para el año, el costo unitario queda igual
    al débito (así lo hace el Excel; queda marcado como "sin divisor").

Uso (desde la carpeta de la app):
    python motor_costo_unitario.py
Se corre solo al aprobar una carga de AGROCACAY, y también a mano cuando se
actualicen las hojas PXN, CENSO, SYRS o ARB_TOTAL del Excel de referencias.
"""
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook

import config as C

REGLAS_VALIDAS = ["PXN_KG", "SYRS_ARBOLES", "SITIOS_SIEMBRA", "CENSO", "ARB_TOTALVIVOS"]


def clave(v):
    """Texto en minúsculas y sin espacios a los lados: Excel compara sin
    distinguir mayúsculas ("Cosecha" = "COSECHA")."""
    return "" if v is None or pd.isna(v) else str(v).strip().lower()


# ===============================================================
# 1. LEER LAS REFERENCIAS DEL EXCEL
# ===============================================================
def leer_referencias(ruta=None):
    ruta = ruta or C.ARCHIVO_REFERENCIAS_CU
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No encuentro el Excel de referencias: {ruta}")
    temporal = os.path.join(tempfile.gettempdir(), "lectura_referencias_cu.xlsx")
    shutil.copy2(ruta, temporal)          # por si está abierto en Excel
    libro = load_workbook(temporal, read_only=True, data_only=True)

    def hoja(nombre):
        filas = list(libro[nombre].iter_rows(values_only=True))
        return filas

    # --- Reglas por rubro (hoja ⚙ CONFIG, bloque "RUBRO | REGLA_DIVISOR")
    reglas = {}
    leyendo = False
    for fila in hoja("⚙ CONFIG"):
        a, b = (fila + (None, None))[:2]
        if a == "RUBRO" and b == "REGLA_DIVISOR":
            leyendo = True
            continue
        if leyendo:
            if a is None or b is None:
                break
            reglas[clave(a)] = str(b).strip()

    def tabla(nombre, primera_col=0, n_cols=None):
        filas = hoja(nombre)
        enc = [str(c).strip() if c is not None else "" for c in filas[0]]
        fin = primera_col + n_cols if n_cols else len(enc)
        df = pd.DataFrame([f[primera_col:fin] for f in filas[1:]], columns=enc[primera_col:fin])
        return df.dropna(how="all")

    pxn = tabla("PXN")
    censo = tabla("CENSO")
    syrs = tabla("SYRS", 0, 9)
    arb = tabla("ARB_TOTAL", 0, 5)
    sembrados = tabla("ARB_TOTAL", 6, 2)
    libro.close()
    os.remove(temporal)

    ref = {"reglas": reglas, "archivo": ruta,
           "fecha_archivo": datetime.fromtimestamp(os.path.getmtime(ruta)).strftime("%Y-%m-%d %H:%M")}

    # Años como número: hay celdas con el año escrito como texto ("2023"),
    # y SUMIFS de Excel las cuenta igual que si fueran número.
    for df, col in [(pxn, "Año"), (censo, "AÑO"), (syrs, "AÑO")]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Sumas tipo SUMIFS (llaves en minúsculas)
    pxn["k_u"] = pxn["Ubicación"].map(clave)
    pxn["k_m"] = pxn["Mes"].map(clave)
    pxn["Kg Fruto Cosechado"] = pd.to_numeric(pxn["Kg Fruto Cosechado"], errors="coerce").fillna(0)
    ref["pxn_mes"] = pxn.groupby(["Año", "k_m", "k_u"])["Kg Fruto Cosechado"].sum().to_dict()
    ref["pxn_anio"] = pxn.groupby("Año")["Kg Fruto Cosechado"].sum().to_dict()

    # Filas repetidas (mismo año, lote y árboles) se cuentan una sola vez: en la hoja CENSO
    # el bloque 2023-2026 llegó a estar copiado dos veces y duplicaba el divisor.
    repetidas = censo.dropna(subset=["AÑO"]).duplicated(subset=["AÑO", "UBICA", "Arboles"]).sum()
    censo = censo[~(censo["AÑO"].notna() & censo.duplicated(subset=["AÑO", "UBICA", "Arboles"]))]
    censo["k_u"] = censo["UBICA"].map(clave)
    censo["Arboles"] = pd.to_numeric(censo["Arboles"], errors="coerce").fillna(0)
    ref["censo"] = censo.groupby(["AÑO", "k_u"])["Arboles"].sum().to_dict()

    syrs["k_u"] = syrs["ASIGNACION"].map(clave)
    syrs["TAREA"] = pd.to_numeric(syrs["TAREA"], errors="coerce").fillna(0)
    ref["syrs"] = syrs.groupby(["AÑO", "k_u"])["TAREA"].sum().to_dict()

    # Búsquedas tipo XLOOKUP: año que no está -> None (sin dato); celda vacía -> 0
    ref["arb"] = {a: (0 if pd.isna(v) else v) for a, v in zip(arb["AÑO"], arb["TOTAL SITIOS VIVOS"]) if pd.notna(a)}
    ref["sembrados"] = {a: (0 if pd.isna(v) else v)
                        for a, v in zip(sembrados["AÑO"], sembrados["Sitios Sembrados"]) if pd.notna(a)}
    ref["resumen"] = {"reglas": len(reglas), "PXN": len(pxn), "CENSO": len(censo),
                      "CENSO repetidas ignoradas": int(repetidas), "SYRS": len(syrs),
                      "años ARB": len(ref["arb"]), "años sembrados": len(ref["sembrados"])}
    return ref


# ===============================================================
# 2. CALCULAR DIVISOR Y COSTO UNITARIO
# ===============================================================
def calcular(costos, ref):
    d = costos.copy()
    anio = d["anio"].astype("Int64")
    k_u = d["ubicacion"].map(clave)
    k_m = d["mes"].map(clave)

    # Regla del rubro (si el rubro no está en CONFIG -> "—", que usa ARB_TotalVivos)
    d["regla_divisor"] = d["rubro"].map(lambda r: ref["reglas"].get(clave(r), "—"))

    pares = list(zip(anio, k_m, k_u))
    d["pxn_kg"] = [ref["pxn_anio"].get(a, 0) if u == "cosecha" else ref["pxn_mes"].get((a, m, u), 0)
                   for a, m, u in pares]
    d["syrs_arboles"] = [ref["syrs"].get((a, u), 0) for a, _, u in pares]
    d["sitios_siembra"] = [ref["sembrados"].get(a) for a in anio]
    d["censo"] = [ref["censo"].get((a, u), 0) for a, _, u in pares]
    d["arb_total_vivos"] = [ref["arb"].get(a) for a in anio]

    columna = {"PXN_KG": "pxn_kg", "SYRS_ARBOLES": "syrs_arboles", "SITIOS_SIEMBRA": "sitios_siembra",
               "CENSO": "censo", "ARB_TOTALVIVOS": "arb_total_vivos"}
    divisores, origen = [], []
    for _, f in d.iterrows():
        regla = str(f["regla_divisor"]).upper()
        valor = f[columna.get(regla, "arb_total_vivos")]
        if regla == "SITIOS_SIEMBRA" and (valor is None or pd.isna(valor) or valor == 0):
            divisores.append(None)           # sin sitios sembrados del año: costo unitario en blanco
            origen.append("Sin sitios sembrados (CU en blanco)")
            continue
        if valor == 0:                       # divisor propio en cero -> árboles vivos del año
            valor = f["arb_total_vivos"]
            origen.append("Respaldo: árboles vivos")
        else:
            origen.append("Propio de la regla" if regla in columna else "Árboles vivos (rubro sin regla)")
        divisores.append(valor)
    d["divisor"] = divisores
    d["origen_divisor"] = origen

    def cu(f):
        if f["origen_divisor"] == "Sin sitios sembrados (CU en blanco)":
            return None
        div = f["divisor"]
        debito = 0 if pd.isna(f["valor"]) else f["valor"]   # débito vacío cuenta como 0
        if div is None or pd.isna(div) or div == 0:
            return debito                   # igual que el Excel: sin divisor, CU = débito
        return debito / div
    d["costo_unitario"] = d.apply(cu, axis=1)
    sin = (d["divisor"].isna() | (d["divisor"] == 0)) & (d["origen_divisor"] != "Sin sitios sembrados (CU en blanco)")
    d.loc[sin, "origen_divisor"] = "Sin divisor (CU = débito)"
    return d


# ===============================================================
# 3. CORRER PARA LAS EMPRESAS CONFIGURADAS
# ===============================================================
COLUMNAS_SALIDA = ["empresa", "fila_excel", "periodo", "anio", "mes", "mes_num", "ceco", "rubro", "detalle",
                   "descripcion", "ubicacion", "actividad", "tercero", "tipo_gasto", "naturaleza", "valor",
                   "regla_divisor", "pxn_kg", "syrs_arboles", "sitios_siembra", "censo", "arb_total_vivos",
                   "divisor", "origen_divisor", "costo_unitario", "huella"]


def correr():
    print("Leyendo referencias de producción...")
    ref = leer_referencias()
    print(f"  {ref['archivo']} (guardado {ref['fecha_archivo']})")
    print("  " + " · ".join(f"{k}: {v}" for k, v in ref["resumen"].items()))

    con = sqlite3.connect(C.BASE_LOCAL)
    for empresa in C.EMPRESAS_COSTO_UNITARIO:
        t = C.EMPRESAS[empresa]["tabla"]
        costos = pd.read_sql(f"SELECT * FROM {t}_vigente", con)
        print(f"\n{empresa}: calculando costo unitario de {len(costos):,} filas...")
        res = calcular(costos, ref)
        res[COLUMNAS_SALIDA].to_sql(f"{t}_costo_unitario", con, if_exists="replace", index=False)
        print(res["regla_divisor"].value_counts().to_string())
        print(res["origen_divisor"].value_counts().to_string())

    con.execute("CREATE TABLE IF NOT EXISTS calculos_cu (fecha TEXT, archivo_referencias TEXT, "
                "fecha_referencias TEXT)")
    con.execute("INSERT INTO calculos_cu VALUES (?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), ref["archivo"], ref["fecha_archivo"]))
    con.commit()
    con.close()
    print("\nListo. El dashboard ya muestra el costo unitario actualizado.")


if __name__ == "__main__":
    correr()
    # Corrido a mano: sube el costo unitario nuevo a la nube (si ya está configurada)
    from subir_a_nube import subir_si_esta_configurada
    subir_si_esta_configurada()
