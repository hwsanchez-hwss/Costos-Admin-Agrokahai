# -*- coding: utf-8 -*-
"""
ACTUALIZAR DESDE EXCEL
======================
Lee los consolidados de AGROCACAY y KAHAI (la base oficial que maneja
administración), compara contra lo último aprobado y genera un
REPORTE DE REVISIÓN en Excel con lo que cambió y las alertas.

La app SOLO LEE los Excel. Nunca los modifica.
Si el reporte muestra algo que corregir, se corrige en el Excel y se
vuelve a correr este script.

Uso (desde la carpeta de la app):
    python actualizar_desde_excel.py              -> revisa las dos empresas
    python actualizar_desde_excel.py AGROCACAY    -> solo AGROCACAY
    python actualizar_desde_excel.py KAHAI        -> solo KAHAI

Después de revisar el reporte:
    python aprobar_carga.py AGROCACAY aprobar "Nombre de quien aprueba"
"""
import os
import sys
import shutil
import sqlite3
import hashlib
import tempfile
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook

import config as C


# ===============================================================
# 1. LEER EL EXCEL DE UNA EMPRESA
# ===============================================================
def leer_excel(empresa):
    """Lee la hoja del consolidado y la devuelve con las columnas estándar."""
    conf = C.EMPRESAS[empresa]
    ruta = os.path.join(C.CARPETA_EXCEL, conf["archivo"])
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No encuentro el archivo de {empresa}: {ruta}")

    # Se copia a una carpeta temporal para no chocar si alguien lo tiene abierto.
    temporal = os.path.join(tempfile.gettempdir(), f"lectura_{conf['archivo']}")
    shutil.copy2(ruta, temporal)
    fecha_archivo = datetime.fromtimestamp(os.path.getmtime(ruta))

    # data_only=True: lee el VALOR que Excel dejó calculado al guardar (no la fórmula).
    libro = load_workbook(temporal, read_only=True, data_only=True)
    if conf["hoja"] not in libro.sheetnames:
        raise ValueError(f"El archivo de {empresa} no tiene la hoja '{conf['hoja']}'. "
                         f"Hojas encontradas: {libro.sheetnames}")
    filas = list(libro[conf["hoja"]].iter_rows(values_only=True))
    libro.close()
    os.remove(temporal)

    encabezado = [str(c).strip() if c is not None else "" for c in filas[0]]

    # Verificar que estén las columnas que la app necesita
    faltan = []
    posicion = {}
    for estandar, nombre_excel in conf["columnas"].items():
        if nombre_excel in encabezado:
            posicion[estandar] = encabezado.index(nombre_excel)
        elif estandar in C.COLUMNAS_OBLIGATORIAS:
            faltan.append(nombre_excel)
    if faltan:
        raise ValueError(f"En {empresa} faltan columnas obligatorias: {faltan}. "
                         "¿Se cambió el nombre de alguna columna?")

    # Armar la tabla estándar fila por fila (fila 1 = encabezado, por eso empieza en 2)
    registros = []
    for numero, fila in enumerate(filas[1:], start=2):
        if all(v is None or str(v).strip() == "" for v in fila):
            continue  # fila completamente vacía
        r = {"fila_excel": numero}
        for estandar in C.COLUMNAS_ESTANDAR:
            r[estandar] = fila[posicion[estandar]] if estandar in posicion and posicion[estandar] < len(fila) else None
        registros.append(r)

    df = pd.DataFrame(registros)
    return limpiar(df, empresa), fecha_archivo


def limpiar(df, empresa):
    """Deja los datos en un formato uniforme SIN cambiar su contenido."""
    conf = C.EMPRESAS[empresa]

    # Textos: quitar espacios sobrantes y saltos de línea raros de Excel
    import re
    for col in ["mes", "ceco", "planta", "cuenta", "tercero", "rubro", "detalle",
                "descripcion", "ubicacion", "actividad", "documento", "gerente", "tipo_gasto"]:
        df[col] = df[col].map(lambda v: None if v is None or str(v).strip() in ("", "nan", "None")
                              else str(v).replace("_x000D_", " ").replace("\r", " ")
                              .replace("\n", " ").replace("\t", " ").strip())
        # varios espacios seguidos cuentan como uno
        df[col] = df[col].map(lambda v: re.sub(r"\s+", " ", v) if isinstance(v, str) else v)

    # Fecha como texto AAAA-MM-DD (las filas de nómina no traen fecha, solo año y mes)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Valor numérico. Si no es número, queda vacío y se alerta en el control.
    df["valor_original"] = df["valor"].astype(str)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    # Año: si la fórmula no tenía valor guardado, se toma de la fecha
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    sin_anio = df["anio"].isna() & df["fecha"].notna()
    df.loc[sin_anio, "anio"] = pd.to_datetime(df.loc[sin_anio, "fecha"]).dt.year
    df["anio"] = df["anio"].astype("Int64")

    # Mes: texto (ENE, FEB...) y número (1..12)
    # Si un computador tiene Excel en inglés, la fórmula del mes da JAN/APR/AUG/DEC:
    # se pasan a español para que el mismo mes no aparezca con dos nombres.
    ingles = {"JAN": "ENE", "APR": "ABR", "AUG": "AGO", "DEC": "DIC"}
    df["mes"] = df["mes"].map(lambda v: None if v is None or pd.isna(v)
                              else ingles.get(str(v).upper()[:3], str(v).upper()[:3]))
    sin_mes = df["mes"].isna() & df["fecha"].notna()
    inv = {v: k for k, v in C.MESES.items()}
    df.loc[sin_mes, "mes"] = pd.to_datetime(df.loc[sin_mes, "fecha"]).dt.month.map(inv)
    df["mes_num"] = df["mes"].map(C.MESES).astype("Int64")
    df["periodo"] = (df["anio"] * 100 + df["mes_num"]).astype("Int64")   # ej. 202609

    # Naturaleza del gasto: Operativo / Financiero / Inversión / Intercompañía
    hermana = conf["empresa_hermana"]

    def naturaleza(r):
        if r["ceco"] in C.CECOS_FINANCIERO:
            return "Financiero"
        if r["ceco"] in C.CECOS_INVERSION:
            return "Inversión"
        if isinstance(r["tercero"], str) and hermana in r["tercero"].upper():
            return "Intercompañía"
        return "Operativo"
    df["naturaleza"] = df.apply(naturaleza, axis=1)
    df["empresa"] = empresa

    # Huella: identifica el contenido de la fila (si cambia cualquier dato, cambia la huella)
    # El valor se toma redondeado a 2 decimales: así un cambio de precisión
    # interna de Excel (decimales 13, 14, 15...) no se confunde con un cambio real.
    from decimal import Decimal, ROUND_HALF_UP

    def valor_estable(v):
        # 12 cifras significativas y luego centavos, redondeando .5 hacia arriba
        return str(Decimal(f"{v:.12g}").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def huella(r):
        texto = "|".join("" if pd.isna(r[c]) else (valor_estable(r[c]) if c == "valor" else str(r[c]))
                         for c in C.COLUMNAS_ESTANDAR)
        return hashlib.md5(texto.encode("utf-8")).hexdigest()
    df["huella"] = df.apply(huella, axis=1)
    return df


# ===============================================================
# 2. COMPARAR CONTRA LO ÚLTIMO APROBADO
# ===============================================================
def comparar(nuevo, vigente):
    """
    Devuelve qué filas son nuevas y cuáles se borraron.
    Funciona aunque se reordene el Excel: compara por contenido (huella),
    y si hay filas idénticas cuenta cuántas copias había antes y cuántas hay ahora.
    """
    nuevo = nuevo.copy()
    vigente = vigente.copy()
    nuevo["copia"] = nuevo.groupby("huella").cumcount()
    vigente["copia"] = vigente.groupby("huella").cumcount()
    llave_vig = set(zip(vigente["huella"], vigente["copia"]))
    llave_nue = set(zip(nuevo["huella"], nuevo["copia"]))
    nuevas = nuevo[[(h, c) not in llave_vig for h, c in zip(nuevo["huella"], nuevo["copia"])]].copy()
    borradas = vigente[[(h, c) not in llave_nue for h, c in zip(vigente["huella"], vigente["copia"])]].copy()

    # Posibles modificaciones: una fila borrada y una nueva del mismo
    # año-mes, tercero, cuenta y documento = probablemente se editó un dato.
    llave = ["periodo", "tercero", "cuenta", "documento"]
    def k(df):
        return df[llave].apply(lambda r: "|".join(map(str, r.values)), axis=1)
    nuevas["llave_mod"] = k(nuevas) if len(nuevas) else []
    borradas["llave_mod"] = k(borradas) if len(borradas) else []
    comunes = set(nuevas["llave_mod"]) & set(borradas["llave_mod"])
    nuevas["cambio"] = nuevas["llave_mod"].map(lambda x: "Modificada (valor nuevo)" if x in comunes else "Nueva")
    borradas["cambio"] = borradas["llave_mod"].map(lambda x: "Modificada (valor anterior)" if x in comunes else "Borrada")
    return nuevas, borradas


# ===============================================================
# 3. CONTROL DE ENTRADA: ALERTAS SOBRE LO QUE CAMBIÓ
# ===============================================================
def alertar(nuevas, borradas, todo, vigente):
    alertas = []

    def agregar(fila, tipo, detalle):
        alertas.append({"tipo_alerta": tipo, "detalle_alerta": detalle,
                        "fila_excel": fila.get("fila_excel"), "periodo": fila.get("periodo"),
                        "ceco": fila.get("ceco"), "rubro": fila.get("rubro"),
                        "tercero": fila.get("tercero"), "documento": fila.get("documento"),
                        "actividad": fila.get("actividad"), "valor": fila.get("valor")})

    if len(nuevas):
        # 3.1 Filas idénticas dentro del archivo
        conteo = todo["huella"].value_counts()
        for _, f in nuevas.iterrows():
            if conteo.get(f["huella"], 0) > 1:
                filas = todo.loc[todo["huella"] == f["huella"], "fila_excel"].tolist()
                agregar(f, "1. Fila repetida",
                        f"Hay {len(filas)} filas idénticas en el Excel (filas {', '.join(map(str, filas))})")

        # 3.2 Misma factura (tercero + documento + valor) en otro mes
        ter = todo[(todo["tipo_gasto"].fillna("").str.upper() != "NOMINA") & todo["documento"].notna()
                   & todo["tercero"].notna()]
        grupos = ter.groupby(["tercero", "documento", "valor"])["periodo"].apply(set)
        for _, f in nuevas.iterrows():
            if str(f["tipo_gasto"]).upper() == "NOMINA" or pd.isna(f["documento"]) or pd.isna(f["tercero"]):
                continue
            periodos = grupos.get((f["tercero"], f["documento"], f["valor"]), set())
            otros = sorted(p for p in periodos if p != f["periodo"])
            if otros:
                agregar(f, "2. Factura en otro mes",
                        f"El mismo tercero, documento y valor ya aparece en: {', '.join(map(str, otros))}")

        # 3.3 Campos vacíos o valor que no es número
        for _, f in nuevas.iterrows():
            vacios = [c for c in C.COLUMNAS_OBLIGATORIAS if f[c] is None or pd.isna(f[c])]
            if pd.isna(f["mes_num"]) and "mes" not in vacios:
                vacios.append("mes válido")
            if vacios:
                extra = f" (valor escrito: '{f['valor_original']}')" if "valor" in vacios else ""
                agregar(f, "3. Dato vacío o inválido", f"Sin: {', '.join(vacios)}{extra}")

        # 3.4 Nombres que nunca habían aparecido (o variantes de mayúsculas)
        for col in ["ceco", "rubro", "detalle", "planta", "tipo_gasto"]:
            conocidos = set(vigente[col].dropna()) if len(vigente) else set()
            if not conocidos:
                continue
            import unicodedata

            def simple(x):  # sin tildes, mayúsculas, espacios ni guiones bajos
                x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
                return x.lower().replace(" ", "").replace("_", "")
            normal = {simple(x): x for x in conocidos}
            for valor in sorted(set(nuevas[col].dropna()) - conocidos):
                parecido = normal.get(simple(valor))
                msg = (f"'{valor}' es variante de '{parecido}' (tildes, mayúsculas o espacios)" if parecido
                       else f"'{valor}' no existía antes en {col.upper()}")
                ejemplo = nuevas[nuevas[col] == valor].iloc[0]
                n = int((nuevas[col] == valor).sum())
                agregar(ejemplo, "4. Nombre nuevo", f"{msg} — {n} fila(s)")

        # 3.5 Rubro del mes muy por encima de su promedio de 12 meses
        tot = todo.groupby(["rubro", "periodo"])["valor"].sum()
        tocados = nuevas[["rubro", "periodo"]].dropna().drop_duplicates()
        periodos = sorted(todo["periodo"].dropna().unique())
        for _, t in tocados.iterrows():
            idx = periodos.index(t["periodo"])
            anteriores = periodos[max(0, idx - 12):idx]
            if len(anteriores) < 3:
                continue
            prom = sum(tot.get((t["rubro"], p), 0) for p in anteriores) / len(anteriores)
            actual = tot.get((t["rubro"], t["periodo"]), 0)
            if actual > C.UMBRAL_MULTIPLO_PROMEDIO * prom and actual - prom > C.UMBRAL_DIFERENCIA_MINIMA:
                ej = nuevas[(nuevas["rubro"] == t["rubro"]) & (nuevas["periodo"] == t["periodo"])].iloc[0]
                agregar(ej, "5. Valor fuera de lo normal",
                        f"{t['rubro']} en {t['periodo']}: {actual:,.0f} vs promedio 12 meses {prom:,.0f} "
                        f"({actual / prom if prom else 0:.1f} veces)")

    # 3.6 Cambios en meses ya reportados (ajustes manuales a meses anteriores)
    if len(todo["periodo"].dropna()):
        ultimo = int(todo["periodo"].max())
        a, m = divmod(ultimo, 100)
        m -= C.MESES_ABIERTOS
        while m <= 0:
            a, m = a - 1, m + 12
        corte = a * 100 + m
        for df in (nuevas, borradas):
            for _, f in df.iterrows():
                if pd.notna(f["periodo"]) and f["periodo"] <= corte:
                    agregar(f, "6. Cambio en mes anterior",
                            f"{f['cambio']} en {f['periodo']} (meses abiertos: posteriores a {corte})")

    return pd.DataFrame(alertas)


# ===============================================================
# 4. GUARDAR EN LA BASE LOCAL Y GENERAR EL REPORTE
# ===============================================================
def conectar():
    con = sqlite3.connect(C.BASE_LOCAL)
    con.execute("""CREATE TABLE IF NOT EXISTS historial_cargas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, fecha_lectura TEXT,
        fecha_archivo TEXT, filas INTEGER, total_valor REAL,
        nuevas INTEGER, borradas INTEGER, valor_nuevas REAL, valor_borradas REAL,
        alertas INTEGER, estado TEXT, responsable TEXT, fecha_decision TEXT,
        comentario TEXT, reporte TEXT)""")
    return con


def leer_tabla(con, nombre):
    try:
        return pd.read_sql(f"SELECT * FROM {nombre}", con)
    except Exception:
        return pd.DataFrame()


COLS_GUARDAR = ["empresa", "fila_excel"] + C.COLUMNAS_ESTANDAR + \
               ["mes_num", "periodo", "naturaleza", "huella"]


def procesar(empresa):
    conf = C.EMPRESAS[empresa]
    t = conf["tabla"]
    print(f"\n=== {empresa} ===")
    print("Leyendo Excel...")
    todo, fecha_archivo = leer_excel(empresa)
    print(f"  {len(todo):,} filas · total {todo['valor'].sum():,.0f} · último mes {todo['periodo'].max()}")

    con = conectar()
    vigente = leer_tabla(con, f"{t}_vigente")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ---- Primera vez: el histórico se acepta tal como viene
    if vigente.empty:
        todo[COLS_GUARDAR].to_sql(f"{t}_vigente", con, if_exists="replace", index=False)
        con.execute("""INSERT INTO historial_cargas (empresa, fecha_lectura, fecha_archivo, filas,
                       total_valor, nuevas, borradas, valor_nuevas, valor_borradas, alertas, estado,
                       responsable, fecha_decision, comentario) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (empresa, ahora, str(fecha_archivo), len(todo), float(todo["valor"].sum()),
                     len(todo), 0, float(todo["valor"].sum()), 0.0, 0, "aprobada", "sistema", ahora,
                     "Carga inicial: el histórico se acepta tal como viene en el Excel"))
        con.commit()
        con.close()
        print("  Carga inicial guardada. El histórico queda aceptado tal como viene.")
        return

    # ---- Cargas siguientes: comparar, alertar y dejar pendiente de aprobación
    nuevas, borradas = comparar(todo, vigente)
    alertas = alertar(nuevas, borradas, todo, vigente)
    print(f"  Nuevas: {len(nuevas):,} · Borradas: {len(borradas):,} · Alertas: {len(alertas):,}")

    if nuevas.empty and borradas.empty:
        print("  No hay cambios desde la última carga aprobada. Nada que revisar.")
        con.close()
        return

    # Guardar la versión leída como PENDIENTE (reemplaza una pendiente anterior)
    todo[COLS_GUARDAR].to_sql(f"{t}_pendiente", con, if_exists="replace", index=False)
    con.execute("DELETE FROM historial_cargas WHERE empresa=? AND estado='pendiente'", (empresa,))
    reporte = generar_reporte(empresa, todo, nuevas, borradas, alertas, fecha_archivo)
    con.execute("""INSERT INTO historial_cargas (empresa, fecha_lectura, fecha_archivo, filas, total_valor,
                   nuevas, borradas, valor_nuevas, valor_borradas, alertas, estado, reporte)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (empresa, ahora, str(fecha_archivo), len(todo), float(todo["valor"].sum()),
                 len(nuevas), len(borradas), float(nuevas["valor"].sum()), float(borradas["valor"].sum()),
                 len(alertas), "pendiente", reporte))
    con.commit()
    con.close()
    print(f"  Reporte de revisión: {reporte}")
    print(f"  Para aprobar:  python aprobar_carga.py {empresa} aprobar \"Su nombre\"")
    print(f"  Para rechazar: python aprobar_carga.py {empresa} rechazar \"Su nombre\"")


def generar_reporte(empresa, todo, nuevas, borradas, alertas, fecha_archivo):
    os.makedirs(C.CARPETA_REPORTES, exist_ok=True)
    nombre = f"Revision_{empresa}_{datetime.now():%Y-%m-%d_%H%M}.xlsx"
    ruta = os.path.join(C.CARPETA_REPORTES, nombre)

    cols = ["cambio", "fila_excel", "periodo", "fecha", "ceco", "rubro", "detalle", "descripcion",
            "ubicacion", "actividad", "tercero", "cuenta", "documento", "valor", "tipo_gasto", "naturaleza"]
    cambios = pd.concat([nuevas.assign(origen="Excel actual"), borradas.assign(origen="Versión aprobada")])
    cambios = cambios.sort_values(["periodo", "tercero"], na_position="last")

    if len(alertas):
        res_alertas = alertas.groupby("tipo_alerta").agg(filas=("tipo_alerta", "size"),
                                                         valor=("valor", "sum")).reset_index()
    else:
        res_alertas = pd.DataFrame({"tipo_alerta": ["Sin alertas"], "filas": [0], "valor": [0]})

    resumen = pd.DataFrame([
        ["Empresa", empresa],
        ["Archivo leído", C.EMPRESAS[empresa]["archivo"]],
        ["Guardado en Excel el", f"{fecha_archivo:%Y-%m-%d %H:%M}"],
        ["Filas en el Excel", len(todo)],
        ["Filas nuevas o modificadas", len(nuevas)],
        ["Valor de filas nuevas o modificadas", nuevas["valor"].sum()],
        ["Filas borradas o con valor anterior", len(borradas)],
        ["Valor de filas borradas", borradas["valor"].sum()],
        ["Alertas", len(alertas)],
        ["", ""],
        ["Qué hacer", "Revise las alertas. Si algo está mal, corríjalo en el Excel y vuelva a correr "
                      "actualizar_desde_excel.py. Si todo está bien, apruebe con aprobar_carga.py."],
        ["", "La columna FILA_EXCEL indica la fila en el consolidado tal como estaba al leerlo."],
    ], columns=["Concepto", "Valor"])

    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        resumen.to_excel(w, sheet_name="Resumen", index=False)
        res_alertas.to_excel(w, sheet_name="Resumen", index=False, startrow=len(resumen) + 2)
        (alertas if len(alertas) else pd.DataFrame({"tipo_alerta": ["Sin alertas"]})) \
            .to_excel(w, sheet_name="Alertas", index=False)
        cambios[["origen"] + cols].to_excel(w, sheet_name="Cambios", index=False)
        dar_formato(w.book)
    return ruta


def dar_formato(libro):
    from openpyxl.styles import Font, PatternFill, Alignment
    titulo = PatternFill("solid", fgColor="1F4E3D")
    for hoja in libro.worksheets:
        for celda in hoja[1]:
            celda.font = Font(name="Arial", bold=True, color="FFFFFF")
            celda.fill = titulo
        for fila in hoja.iter_rows(min_row=2):
            for celda in fila:
                celda.font = Font(name="Arial", size=10, bold=celda.font.bold)
                if isinstance(celda.value, (int, float)) and celda.column_letter != "B" or \
                        (hoja.title == "Resumen" and isinstance(celda.value, float)):
                    celda.number_format = "#,##0"
        for col in hoja.columns:
            ancho = max(len(str(c.value)) if c.value is not None else 0 for c in list(col)[:300])
            hoja.column_dimensions[col[0].column_letter].width = min(max(10, ancho + 2), 60)
        hoja.freeze_panes = "A2"
    r = libro["Resumen"]
    r.column_dimensions["B"].width = 70
    for fila in r.iter_rows(min_row=2):
        for celda in fila:
            celda.alignment = Alignment(wrap_text=True, vertical="top")


# ===============================================================
if __name__ == "__main__":
    pedidas = [a.upper() for a in sys.argv[1:]] or list(C.EMPRESAS)
    for e in pedidas:
        if e not in C.EMPRESAS:
            print(f"Empresa desconocida: {e}. Use AGROCACAY o KAHAI.")
            continue
        procesar(e)
