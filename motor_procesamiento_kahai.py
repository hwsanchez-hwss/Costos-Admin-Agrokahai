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
    lotes = leer_lotes(ruta)
    lotes.to_sql("kahai_lotes_aceite", con, if_exists="replace", index=False)
    print(f"Lotes de aceite: {len(lotes)} ({', '.join(map(str, sorted(lotes['anio'].unique()))) or 'ninguno'})")
    con.close()
    print(f"Guardado en la base ({datetime.now():%Y-%m-%d %H:%M}).")


if __name__ == "__main__":
    correr()
    from subir_a_nube import subir_si_esta_configurada
    subir_si_esta_configurada()
