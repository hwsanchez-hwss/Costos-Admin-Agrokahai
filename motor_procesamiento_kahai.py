# -*- coding: utf-8 -*-
"""
DIVISORES DE PROCESAMIENTO KAHAI
================================
Lee Graficas\\PRODUCCION_KAHAI.xlsx (hojas DIVISORES, REGLAS y LOTES_ACEITE) y lo guarda en la base,
para que el dashboard calcule el costo por kg de concha procesada, nuez obtenida,
nuez pelada y aceite (extracción, filtrado, envasado, laboratorios, empaque).

    Costo por kg = costo del año (CONSOLIDADO_KAHAI aprobado) ÷ kg del divisor del año

Uso (desde la carpeta de la app), cada vez que se cambie ese Excel:
    python motor_procesamiento_kahai.py
Al terminar sube las tablas a la nube (si está configurada).
"""
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

import pandas as pd

import config as C


def leer(ruta=None):
    ruta = ruta or C.ARCHIVO_PRODUCCION_KAHAI
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No encuentro {ruta}")
    temporal = os.path.join(tempfile.gettempdir(), "lectura_produccion_kahai.xlsx")
    shutil.copy2(ruta, temporal)            # por si está abierto en Excel
    hojas = pd.read_excel(temporal, sheet_name=["DIVISORES", "REGLAS"])
    os.remove(temporal)

    div = hojas["DIVISORES"].dropna(subset=["DIVISOR"])
    div = div[div["DIVISOR"].astype(str).str.upper() != "NAN"]
    anios = [c for c in div.columns if str(c).strip().isdigit()]
    div = div.melt(id_vars="DIVISOR", value_vars=anios, var_name="anio", value_name="kg").dropna(subset=["kg"])
    div["anio"] = div["anio"].astype(int)
    div["kg"] = pd.to_numeric(div["kg"], errors="coerce")
    div = div.dropna(subset=["kg"]).rename(columns={"DIVISOR": "divisor"})
    div["divisor"] = div["divisor"].astype(str).str.strip().str.upper()

    reg = hojas["REGLAS"].dropna(subset=["LINEA", "DIVISOR"]).copy()
    reg.columns = [c.lower() for c in reg.columns]
    if "descripcion" not in reg.columns:          # columna opcional (versiones viejas del Excel)
        reg["descripcion"] = "*"
    for c in ["seccion", "linea", "ceco", "rubro", "detalle", "descripcion", "divisor"]:
        reg[c] = reg[c].fillna("*").astype(str).str.strip()
    reg["divisor"] = reg["divisor"].str.upper()
    reg["orden"] = range(1, len(reg) + 1)
    faltan = sorted(set(reg["divisor"]) - set(div["divisor"]))
    if faltan:
        print(f"  Aviso: estas reglas usan divisores que no están en la hoja DIVISORES: {faltan}")
    return div[["divisor", "anio", "kg"]], reg, ruta


COLS_LOTES = {"AÑO": "anio", "LOTE ACEITE": "lote", "NUEZ TESTA (kg)": "nuez_testa", "NUEZ PELADA (kg)": "nuez_pelada",
              "BLANCA (kg)": "blanca", "ROJA (kg)": "roja", "HONGO (kg)": "hongo",
              "NUEZ PARA ACEITE (kg)": "nuez_aceite", "ACEITE (kg)": "aceite"}


def leer_vivero_fruta(ruta=None):
    """Hojas VIVERO (AÑO, PLANTAS PRODUCIDAS) y FRUTA_COMPRADA (AÑO, TIPO, KG COMPRADOS): divisores del costo
    unitario de los CECO VIVERO y FRUTA de KAHAI. Si no existen, tablas vacías."""
    ruta = ruta or C.ARCHIVO_PRODUCCION_KAHAI
    temporal = os.path.join(tempfile.gettempdir(), "lectura_vivero_fruta.xlsx")
    shutil.copy2(ruta, temporal)
    try:
        hojas = pd.read_excel(temporal, sheet_name=None)
    finally:
        os.remove(temporal)
    viv = pd.DataFrame(columns=["anio", "plantas"])
    fru = pd.DataFrame(columns=["anio", "tipo", "kg"])
    if "VIVERO" in hojas:
        h = hojas["VIVERO"].iloc[:, :2]
        h.columns = ["anio", "plantas"]
        h = h[pd.to_numeric(h["anio"], errors="coerce").notna()].copy()
        viv = pd.DataFrame({"anio": pd.to_numeric(h["anio"]).astype(int), "plantas": pd.to_numeric(h["plantas"], errors="coerce")})
    if "FRUTA_COMPRADA" in hojas:
        h = hojas["FRUTA_COMPRADA"].iloc[:, :3]
        h.columns = ["anio", "tipo", "kg"]
        h = h[pd.to_numeric(h["anio"], errors="coerce").notna() & h["tipo"].notna()].copy()
        fru = pd.DataFrame({"anio": pd.to_numeric(h["anio"]).astype(int), "tipo": h["tipo"].astype(str).str.strip().str.upper(),
                            "kg": pd.to_numeric(h["kg"], errors="coerce")})
    return viv.reset_index(drop=True), fru.reset_index(drop=True)


def leer_vivero_campo(carpeta=None):
    """Plantas producidas por el vivero, desde el respaldo más reciente de la app de Campo (tabla vivero_mov).
    Cada vivero es una camada: VIVERO_24 = bolsas llenadas en 2024. Plantas de la camada =
    entregadas (siembra + resiembra, AGROCACAY y terceros) + las que quedan en el vivero (inventario actual).
    Por eso las camadas recientes cambian a medida que se entregan o se descartan plantas."""
    import glob, re, zipfile
    carpeta = carpeta or C.CARPETA_RESPALDOS_CAMPO
    zips = sorted(glob.glob(os.path.join(carpeta, "respaldo_*.zip")))
    vacio = pd.DataFrame(columns=["anio", "plantas", "entregadas", "en_vivero", "llenadas", "descartes", "fuente"])
    if not zips:
        return vacio
    with zipfile.ZipFile(zips[-1]) as z:
        nombre = next((n for n in z.namelist() if n.replace("\\", "/").endswith("campo/csv/vivero_mov.csv")), None)
        if not nombre:
            return vacio
        with z.open(nombre) as f:
            v = pd.read_csv(f)
    v = v[pd.to_numeric(v.get("anulado", 0), errors="coerce").fillna(0) == 0].copy()
    v["cantidad"] = pd.to_numeric(v["cantidad"], errors="coerce").fillna(0)
    v["n"] = v["vivero"].astype(str).str.extract(r"VIVERO_(\d+)", flags=re.I)[0]
    v = v[v["n"].notna()]
    if v.empty:
        return vacio
    p = v.pivot_table(index="vivero", columns="tipo", values="cantidad", aggfunc="sum", fill_value=0)
    for c in ("Llenado", "Entrega", "Descarte"):
        if c not in p:
            p[c] = 0
    # año de la camada: el del llenado; si no hay llenado registrado, 2000 + número del vivero
    anio_llen = v[v["tipo"] == "Llenado"].groupby("vivero")["anio"].min()
    p["anio"] = [int(anio_llen.get(viv_, 2000 + int(re.search(r"\d+", viv_).group()))) for viv_ in p.index]
    p["en_vivero"] = (p["Llenado"] - p["Entrega"] - p["Descarte"]).clip(lower=0)
    out = p.groupby("anio").agg(entregadas=("Entrega", "sum"), en_vivero=("en_vivero", "sum"),
                                llenadas=("Llenado", "sum"), descartes=("Descarte", "sum")).reset_index()
    out["plantas"] = out["entregadas"] + out["en_vivero"]
    out["fuente"] = os.path.basename(zips[-1])
    return out[vacio.columns]


def leer_cultivo_lotes(ruta=None):
    """Hoja CULTIVO_LOTES: árboles y kg cosechados de cada BLOQUE de los lotes de cultivo de KAHAI por año
    (Cumaral = bloques HM y MME; Restrepo = MPB). La app suma los bloques de cada lote. Vacío = sin dato."""
    ruta = ruta or C.ARCHIVO_PRODUCCION_KAHAI
    temporal = os.path.join(tempfile.gettempdir(), "lectura_cultivo_kahai.xlsx")
    shutil.copy2(ruta, temporal)
    try:
        h = pd.read_excel(temporal, sheet_name="CULTIVO_LOTES")
    except ValueError:
        return pd.DataFrame(columns=["lote", "bloque", "anio", "arboles", "kg"])
    finally:
        os.remove(temporal)
    h.columns = [str(c).strip().upper() for c in h.columns]
    if "BLOQUE" not in h.columns:           # hoja vieja sin la columna BLOQUE
        h.insert(1, "BLOQUE", None)
    h = h[["LOTE", "BLOQUE", "AÑO", "ÁRBOLES", "KG COSECHADOS"]]
    h.columns = ["lote", "bloque", "anio", "arboles", "kg"]
    h = h[h["lote"].notna() & pd.to_numeric(h["anio"], errors="coerce").notna()].copy()
    h["lote"] = h["lote"].astype(str).str.strip().str.upper()
    h["bloque"] = h["bloque"].fillna("").astype(str).str.strip().str.upper()
    h["anio"] = pd.to_numeric(h["anio"]).astype(int)
    for c in ["arboles", "kg"]:
        h[c] = pd.to_numeric(h[c], errors="coerce")
    return h.reset_index(drop=True)


def leer_lotes(ruta=None):
    """Hoja LOTES_ACEITE: la nuez de cada lote y cómo se transforma hasta aceite (los % se calculan en la app)."""
    ruta = ruta or C.ARCHIVO_PRODUCCION_KAHAI
    temporal = os.path.join(tempfile.gettempdir(), "lectura_lotes_kahai.xlsx")
    shutil.copy2(ruta, temporal)
    try:
        h = pd.read_excel(temporal, sheet_name="LOTES_ACEITE", usecols="A:N")
    except ValueError:                       # Excel viejo sin la hoja
        return pd.DataFrame(columns=list(COLS_LOTES.values()))
    finally:
        os.remove(temporal)
    h.columns = [str(c).strip() for c in h.columns]
    h = h[[c for c in COLS_LOTES if c in h.columns]].rename(columns=COLS_LOTES)
    h["lote"] = h["lote"].astype("string").str.strip()
    h = h[h["lote"].notna() & (h["lote"] != "")]          # las notas de abajo no son lotes
    h["anio"] = pd.to_numeric(h["anio"], errors="coerce").ffill().astype(int)   # año vacío = el de arriba
    for c in list(COLS_LOTES.values())[2:]:
        h[c] = pd.to_numeric(h[c], errors="coerce")
    h["orden"] = range(1, len(h) + 1)
    return h.reset_index(drop=True)


def correr():
    div, reg, ruta = leer()
    print(f"Leído {ruta}: {div['divisor'].nunique()} divisores · años {div['anio'].min()}–{div['anio'].max()} · "
          f"{len(reg)} reglas")
    con = sqlite3.connect(C.BASE_LOCAL)
    div.to_sql("kahai_divisores", con, if_exists="replace", index=False)
    reg.to_sql("kahai_reglas_proc", con, if_exists="replace", index=False)
    viv, fru = leer_vivero_fruta(ruta)
    viv_c = leer_vivero_campo()
    if not viv_c.empty:
        # La app de Campo manda; si en la hoja VIVERO escribe un número para un año, ese número reemplaza al de Campo
        manual = viv.dropna(subset=["plantas"]).set_index("anio")["plantas"]
        viv_c["plantas"] = [manual.get(a_, p_) for a_, p_ in zip(viv_c["anio"], viv_c["plantas"])]
        viv = viv_c
        print(f"Vivero desde la app de Campo ({viv_c['fuente'].iloc[0]}): "
              + ", ".join(f"{a_}={int(p_):,}".replace(",", ".") for a_, p_ in zip(viv['anio'], viv['plantas'])))
    else:
        print("⚠️ No encontré respaldos de la app de Campo; el vivero sale de la hoja VIVERO del Excel.")
    viv.to_sql("kahai_vivero", con, if_exists="replace", index=False)
    fru.to_sql("kahai_fruta_comprada", con, if_exists="replace", index=False)
    print(f"Vivero: {viv['plantas'].notna().sum()} años con plantas · Fruta comprada: {fru['kg'].notna().sum()} datos de kg")
    cult = leer_cultivo_lotes(ruta)
    cult.to_sql("kahai_cultivo_lotes", con, if_exists="replace", index=False)
    print(f"Cultivo por lote: {cult['arboles'].notna().sum()} años con árboles, {cult['kg'].notna().sum()} con kg")
    lotes = leer_lotes(ruta)
    lotes.to_sql("kahai_lotes_aceite", con, if_exists="replace", index=False)
    print(f"Lotes de aceite: {len(lotes)} ({', '.join(map(str, sorted(lotes['anio'].unique()))) or 'ninguno'})")
    con.close()
    print(f"Guardado en la base ({datetime.now():%Y-%m-%d %H:%M}).")


if __name__ == "__main__":
    correr()
    from subir_a_nube import subir_si_esta_configurada
    subir_si_esta_configurada()
