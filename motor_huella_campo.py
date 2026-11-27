"""
HUELLA DE CAMPO: cómo repartir por lote el gasto de AGROCACAY que la contabilidad no carga a un lote
====================================================================================================
En la contabilidad, buena parte de Nutrición, MIAR, Riego y Act. complementarias se carga a "Insumos Agricolas",
"Fertilizante", "CIMARRON"…, no a un lote. Para dividirlo por el censo del lote (regla CENSO) hay que saber
a qué lote fue. La app de Campo sí lo registra:
  - insumos aplicados en cada lote (insumos_diario): kg de fertilizante, de herbicida…
  - mano de obra de cada actividad en cada lote (costos_actividad_mes)

Este motor calcula, para cada año y rubro, qué parte (peso) le toca a cada lote:
  - tipo "insumo"    -> según la cantidad de insumos del grupo del rubro aplicados en el lote
                        (si ese año no hay insumos por lote, según la mano de obra del rubro)
  - tipo "mano_obra" -> según la mano de obra de campo del rubro en el lote
Solo entran lotes con censo ese año (el mismo archivo de referencias del costo unitario).

Lee el respaldo más reciente de la app de Campo (Aplicacion_AgroKahai/Respaldos) y guarda la tabla
agrocacay_huella_campo (anio, rubro, tipo, lote, peso, censo, fuente). La app la usa cuando se enciende
"Repartir con datos de campo" en Costo unitario. Se corre solo al final de motor_costo_unitario.py,
o a mano:   python motor_huella_campo.py
"""
import glob
import os
import re
import sqlite3
import zipfile

import pandas as pd

import config as C

LOTE = re.compile(r"^(ML|L)\d+$|^HMPG$", re.I)

# rubro contable -> (grupos de insumos de la app de Campo, rubros de mano de obra de la app de Campo)
RUBROS = {
    "nutrición_vegetal": (["Fertilizante", "BIOL", "Microorganismos"], ["Fertilización", "Enmienda"]),
    "miar": (["Herbicida", "Coadyuvante"], ["MIAR"]),
    "riego": (["RIEGO"], ["Riego"]),
    "act_complementarias": ([], ["Act_Complementarias"]),
}


def _leer_csv_respaldo(z, nombre):
    n = next((x for x in z.namelist() if x.replace("\\", "/").endswith(nombre)), None)
    if not n:
        return pd.DataFrame()
    with z.open(n) as f:
        return pd.read_csv(f, low_memory=False)


def leer_campo(carpeta=None):
    """Insumos por lote y mano de obra por lote (AGROCACAY), del respaldo más reciente de la app de Campo."""
    carpeta = carpeta or C.CARPETA_RESPALDOS_CAMPO
    zips = sorted(glob.glob(os.path.join(carpeta, "respaldo_*.zip")))
    if not zips:
        return None, None, ""
    with zipfile.ZipFile(zips[-1]) as z:
        ins = _leer_csv_respaldo(z, "principal/csv/insumos_diario.csv")
        cat = _leer_csv_respaldo(z, "principal/csv/cat_act_ubic.csv")
        prod = _leer_csv_respaldo(z, "principal/csv/productos_insumos.csv")
        mo = _leer_csv_respaldo(z, "principal/csv/costos_actividad_mes.csv")
    cat = cat.drop_duplicates("cod_act_ubic")[["cod_act_ubic", "ubicacion", "empresa"]]
    ins = ins.merge(cat, on="cod_act_ubic", how="left").merge(prod[["codigo_producto", "grupo"]],
                                                              on="codigo_producto", how="left")
    ins["anio"] = pd.to_datetime(ins["fecha"], errors="coerce").dt.year
    ins["lote"] = ins["ubicacion"].astype(str).str.strip().str.upper()
    ins["cant"] = pd.to_numeric(ins["cant_sale"], errors="coerce")
    ins = ins[(ins["empresa"] == "AGROCACAY") & ins["lote"].str.match(LOTE) & (ins["cant"] > 0)]
    mo["lote"] = mo["ubicacion"].astype(str).str.strip().str.upper()
    mo["valor"] = pd.to_numeric(mo["valor_total_actividad"], errors="coerce")
    mo = mo[(mo["empresa"] == "AGROCACAY") & mo["lote"].str.match(LOTE) & (mo["valor"] > 0)]
    return ins, mo, os.path.basename(zips[-1])


def censo_lote(ref_censo, anio, lote):
    """Árboles del lote ese año en el archivo de referencias; si ese año no está, el censo anterior más cercano."""
    k = lote.strip().lower()
    v = ref_censo.get((anio, k), 0)
    if v:
        return v
    previos = sorted(a for (a, l_) in ref_censo if l_ == k and a < anio and ref_censo[(a, l_)])
    return ref_censo[(previos[-1], k)] if previos else 0


def calcular(ins, mo, ref_censo, fuente):
    filas = []
    anios = sorted(set(ins["anio"].dropna().astype(int)) | set(mo["anio"].dropna().astype(int)))
    for rubro, (grupos, rubros_mo) in RUBROS.items():
        for a in anios:
            w_mo = mo[(mo["anio"] == a) & mo["rubro"].isin(rubros_mo)].groupby("lote")["valor"].sum()
            w_in = (ins[(ins["anio"] == a) & ins["grupo"].isin(grupos)].groupby("lote")["cant"].sum()
                    if grupos else pd.Series(dtype=float))
            for tipo, w, base in (("insumo", w_in if len(w_in) else w_mo,
                                   "insumos aplicados" if len(w_in) else "mano de obra"),
                                  ("mano_obra", w_mo, "mano de obra")):
                cen = {l_: censo_lote(ref_censo, a, l_) for l_ in w.index}
                w = w[[l_ for l_ in w.index if cen[l_] > 0]]        # solo lotes con censo
                if w.sum() <= 0:
                    continue
                for l_, v in (w / w.sum()).items():
                    filas.append(dict(anio=a, rubro=rubro, tipo=tipo, lote=l_, peso=float(v), censo=float(cen[l_]),
                                      base=base, fuente=fuente))
    return pd.DataFrame(filas, columns=["anio", "rubro", "tipo", "lote", "peso", "censo", "base", "fuente"])


def correr(ref=None):
    ins, mo, fuente = leer_campo()
    if ins is None:
        print("⚠️ Huella de campo: no encontré respaldos de la app de Campo; no se reparte por lote.")
        return
    if ref is None:
        from motor_costo_unitario import leer_referencias
        ref = leer_referencias()
    h = calcular(ins, mo, ref["censo"], fuente)
    con = sqlite3.connect(C.BASE_LOCAL)
    h.to_sql("agrocacay_huella_campo", con, if_exists="replace", index=False)
    con.close()
    res = h.groupby(["rubro", "tipo"])["anio"].agg(lambda s: f"{s.min()}–{s.max()}")
    print(f"Huella de campo ({fuente}): {len(h)} pesos por lote · " + " · ".join(f"{r}/{t} {v}" for (r, t), v in res.items()))


if __name__ == "__main__":
    correr()
    from subir_a_nube import subir_si_esta_configurada
    subir_si_esta_configurada()
