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

# Registros de insumos con el lote mal cargado (confirmado por Wal, 27/11/2026): en vez de su lote, se reparten
# entre los lotes que tuvieron jornales de esa misma actividad ese mismo día, en proporción a sus árboles (censo).
#  - Fertilizante 21,1-13,3-16 del 26 al 28/07/2022: 8 salidas (6.382 kg) cargadas todas a ML4 (INSUMOS_AGRO.xlsx,
#    hoja DIARIO, filas 1892-1895, 1904-1906 y 1914). A 50-60 g/árbol, ML4 necesitaba ~240 kg; los jornales de esos
#    días muestran la fertilización en ML15, ML16, ML17, ML5, ML1, ML2, ML3, ML4, L1, L2 y L3.
REASIGNAR_POR_JORNALES = {1891, 1892, 1893, 1894, 1903, 1904, 1905, 1913}
#    Los lotes que ese día (o ±2 días) ya tienen su PROPIO registro de fertilizante no entran: L1, L2 y L3 tuvieron
#    jornales el 28/07, pero recibieron su propio DURAMON 13,8-11,8-25,7 (árboles maduros, ~150 g/árbol); el 21-13-16
#    es de los lotes ML jóvenes. Entre los lotes que quedan, se reparte por árboles.
# Cantidades con error de decimales (insumo_id: cantidad correcta)
#  - fila 1387 de INSUMOS_AGRO.xlsx (DIARIO), 04/06/2022, ML4: 1.309 kg -> 130,9 kg
CORREGIR_CANTIDAD = {1386: 130.9}

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
        jor = _leer_csv_respaldo(z, "principal/csv/registros_diarios.csv")
        cat = _leer_csv_respaldo(z, "principal/csv/cat_act_ubic.csv")
        prod = _leer_csv_respaldo(z, "principal/csv/productos_insumos.csv")
        mo = _leer_csv_respaldo(z, "principal/csv/costos_actividad_mes.csv")
    cat_act = cat.drop_duplicates("cod_act_ubic")[["cod_act_ubic", "actividad", "ubicacion"]]
    cat = cat.drop_duplicates("cod_act_ubic")[["cod_act_ubic", "actividad", "ubicacion", "empresa"]]
    ins = ins.merge(cat, on="cod_act_ubic", how="left").merge(prod[["codigo_producto", "grupo"]],
                                                              on="codigo_producto", how="left")
    ins["anio"] = pd.to_datetime(ins["fecha"], errors="coerce").dt.year
    ins["lote"] = ins["ubicacion"].astype(str).str.strip().str.upper()
    ins["cant"] = pd.to_numeric(ins["cant_sale"], errors="coerce")
    ins = ins[(ins["empresa"] == "AGROCACAY") & ins["lote"].str.match(LOTE) & (ins["cant"] > 0)]
    mo["lote"] = mo["ubicacion"].astype(str).str.strip().str.upper()
    mo["valor"] = pd.to_numeric(mo["valor_total_actividad"], errors="coerce")
    mo = mo[(mo["empresa"] == "AGROCACAY") & mo["lote"].str.match(LOTE) & (mo["valor"] > 0)]
    # jornales: qué lotes tuvieron cada actividad cada día (para corregir insumos con el lote mal cargado)
    jor = jor[["fecha", "cod_act_ubic"]].merge(cat_act, on="cod_act_ubic", how="left")
    jor["dia"] = pd.to_datetime(jor["fecha"], errors="coerce").dt.normalize()
    jor["lote"] = jor["ubicacion"].astype(str).str.strip().str.upper()
    jor = jor[jor["lote"].str.match(LOTE)][["dia", "actividad", "lote"]].drop_duplicates()
    ins.attrs["jornales"] = jor
    return ins, mo, os.path.basename(zips[-1])


def censo_lote(ref_censo, anio, lote):
    """Árboles del lote ese año en el archivo de referencias; si ese año no está, el censo anterior más cercano."""
    k = lote.strip().lower()
    v = ref_censo.get((anio, k), 0)
    if v:
        return v
    previos = sorted(a for (a, l_) in ref_censo if l_ == k and a < anio and ref_censo[(a, l_)])
    return ref_censo[(previos[-1], k)] if previos else 0


def corregir_lotes(ins, ref_censo):
    """Registros de REASIGNAR_POR_JORNALES: su cantidad se reparte entre los lotes con jornales de la misma actividad
    ese mismo día, en proporción a sus árboles. Devuelve los insumos corregidos y un resumen de lo que se movió."""
    jor = ins.attrs.get("jornales")
    if jor is None or "insumo_id" not in ins:
        return ins, []
    for id_, cant in CORREGIR_CANTIDAD.items():          # errores de decimales
        ins.loc[ins["insumo_id"] == id_, "cant"] = cant
    malos = ins[ins["insumo_id"].isin(REASIGNAR_POR_JORNALES)]
    nuevos, resumen, movidos = [], [], []
    for _, r in malos.iterrows():
        dia = pd.to_datetime(r["fecha"], errors="coerce").normalize()
        lotes = jor[(jor["dia"] == dia) & (jor["actividad"] == r["actividad"])]["lote"].unique().tolist()
        # fuera los lotes con su propio registro de un insumo del mismo grupo esos días (±2)
        f_ = pd.to_datetime(ins["fecha"], errors="coerce").dt.normalize()
        propios = ins[(ins["grupo"] == r["grupo"]) & ~ins["insumo_id"].isin(REASIGNAR_POR_JORNALES)
                      & ((f_ - dia).abs() <= pd.Timedelta(days=2))]["lote"].unique()
        lotes = [l_ for l_ in lotes if l_ not in set(propios)]
        arb = {l_: censo_lote(ref_censo, int(r["anio"]), l_) for l_ in lotes}
        arb = {l_: v for l_, v in arb.items() if v > 0}
        if not arb:
            continue                       # sin jornales ese día: se deja como estaba
        tot = sum(arb.values())
        movidos.append(r.name)
        for l_, v in arb.items():
            n = r.copy()
            n["lote"], n["cant"] = l_, r["cant"] * v / tot
            nuevos.append(n)
        kg_txt = f"{r['cant']:,.0f}".replace(",", ".")
        resumen.append(f"{dia:%d/%m/%Y} {kg_txt} kg de {r['lote']} → {', '.join(sorted(arb))}")
    if not nuevos:
        return ins, resumen
    corregidos = pd.concat([ins.drop(index=movidos), pd.DataFrame(nuevos)], ignore_index=True)
    corregidos.attrs = ins.attrs
    return corregidos, resumen


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
    ins, movidos = corregir_lotes(ins, ref["censo"])
    for m_ in movidos:
        print(f"  Corrección de lote (insumo mal cargado): {m_}")
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
