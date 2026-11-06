# -*- coding: utf-8 -*-
"""
SUBIR LO APROBADO A LA NUBE (base Turso "costos-admin")
=======================================================
Copia a la nube las tablas que muestra el dashboard, para que las 4-5 personas
autorizadas lo vean en internet. Solo sube lo APROBADO (las tablas *_vigente,
el costo unitario y el historial); lo pendiente de revisión NUNCA sube.

Sube solo lo que cambió: compara fila por fila (con una "firma" de cada fila)
y borra/agrega únicamente las diferencias. La primera vez sube todo
(unas 150.000 filas: puede tardar 10-20 minutos); después, segundos.

Se corre solo al aprobar una carga y después de motor_costo_unitario.py.
A mano (desde la carpeta de la app):
    python subir_a_nube.py
Para borrar la nube y subir todo de nuevo:
    python subir_a_nube.py --completo

Necesita el archivo .streamlit\\secrets.toml en esta carpeta con:
    TURSO_URL = "libsql://costos-admin-....turso.io"
    TURSO_AUTH_TOKEN = "..."
(Es la base NUEVA de costos, no la de la app de campo.)
"""
import hashlib
import os
import sqlite3
import sys
import time
import tomllib
from datetime import datetime

import pandas as pd

import config as C
from fuente_datos import TABLAS_NUBE

ARCHIVO_SECRETS = os.path.join(C.CARPETA_APP, ".streamlit", "secrets.toml")
FILAS_POR_ENVIO = 400      # filas por cada envío a Turso
INTENTOS = 6


# ---------------------------------------------------------------
# Conexión y reintentos (internet inestable)
# ---------------------------------------------------------------
def conectar_nube():
    if not os.path.exists(ARCHIVO_SECRETS):
        sys.exit(f"No encuentro {ARCHIVO_SECRETS}. Créelo con TURSO_URL y TURSO_AUTH_TOKEN de la base costos-admin.")
    with open(ARCHIVO_SECRETS, "rb") as f:
        s = tomllib.load(f)
    if "TURSO_URL" not in s or "TURSO_AUTH_TOKEN" not in s:
        sys.exit("Faltan TURSO_URL o TURSO_AUTH_TOKEN en .streamlit\\secrets.toml")
    if "agrokahai" in s["TURSO_URL"]:
        sys.exit("¡Cuidado! TURSO_URL apunta a la base de la app de CAMPO. Use la base nueva costos-admin.")
    import turso_serverless
    return turso_serverless.connect(s["TURSO_URL"], auth_token=s["TURSO_AUTH_TOKEN"])


def reintentar(func, que):
    for intento in range(1, INTENTOS + 1):
        try:
            return func()
        except Exception as e:
            if intento == INTENTOS:
                raise
            espera = min(5 * 2 ** (intento - 1), 60)
            print(f"\n    Aviso: falló la red al {que} (intento {intento}/{INTENTOS}): {e}")
            print(f"    Reintentando en {espera} s...")
            time.sleep(espera)


def consultar(con, sql, params=()):
    def f():
        cur = con.execute(sql, params)
        return cur.fetchall()
    return reintentar(f, "consultar la nube")


# ---------------------------------------------------------------
# Firma de cada fila: si cualquier dato cambia, cambia la firma
# ---------------------------------------------------------------
def firmar(df):
    texto = pd.Series([""] * len(df), index=df.index)
    for c in df.columns:   # vacíos como "" (no "nan") y cada columna separada
        texto = texto + "\x1f" + df[c].astype(object).where(df[c].notna(), "").map(str)
    base = texto.map(lambda t: hashlib.md5(t.encode("utf-8")).hexdigest())
    # filas idénticas (repetidas) se distinguen con un contador: #1, #2...
    return base + "#" + (base.groupby(base).cumcount() + 1).astype(str)


def tipo_sql(serie):
    if pd.api.types.is_integer_dtype(serie):
        return "INTEGER"
    if pd.api.types.is_float_dtype(serie):
        return "REAL"
    return "TEXT"


def valor(v):
    try:
        if v is None or pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):          # números de numpy -> número normal
        return v.item()
    return v


def subir_filas(con, tabla, df):
    columnas = list(df.columns)
    sql = (f'INSERT INTO "{tabla}" (' + ", ".join(f'"{c}"' for c in columnas) + ") VALUES ("
           + ", ".join(["?"] * len(columnas)) + ")")
    filas = [tuple(valor(v) for v in fila) for fila in df.itertuples(index=False, name=None)]
    for i in range(0, len(filas), FILAS_POR_ENVIO):
        lote = filas[i:i + FILAS_POR_ENVIO]

        def f(lote=lote):
            con.executemany(sql, lote)
            con.commit()
        reintentar(f, f"subir filas de {tabla}")
        print(f"    {tabla}: {min(i + FILAS_POR_ENVIO, len(filas)):,} / {len(filas):,} filas", end="\r")
    if filas:
        print()


def crear_tabla(con, tabla, df):
    cols = ", ".join(f'"{c}" {tipo_sql(df[c])}' for c in df.columns)
    reintentar(lambda: (con.execute(f'DROP TABLE IF EXISTS "{tabla}"'), con.commit()), "borrar tabla")
    reintentar(lambda: (con.execute(f'CREATE TABLE "{tabla}" ({cols})'), con.commit()), "crear tabla")
    reintentar(lambda: (con.execute(f'CREATE INDEX "ix_{tabla}_firma" ON "{tabla}" ("_firma")'), con.commit()),
               "crear índice")


def firmas_en_nube(con, tabla):
    firmas, ultimo = [], 0
    while True:
        filas = consultar(con, f'SELECT rowid, "_firma" FROM "{tabla}" WHERE rowid > ? ORDER BY rowid LIMIT 20000',
                          (ultimo,))
        if not filas:
            return firmas
        firmas += [f[1] for f in filas]
        ultimo = filas[-1][0]


# ---------------------------------------------------------------
# Sincronizar una tabla
# ---------------------------------------------------------------
def sincronizar(con_local, con, tabla, completo=False):
    try:
        df = pd.read_sql(f'SELECT * FROM "{tabla}"', con_local)
    except Exception:
        print(f"  {tabla}: no existe en el PC (se omite).")
        return 0, 0
    df.insert(0, "_firma", firmar(df))

    existe = consultar(con, "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabla,))
    cols_nube = [f[1] for f in consultar(con, f'PRAGMA table_info("{tabla}")')] if existe else []
    if completo or not existe or cols_nube != list(df.columns):
        motivo = "subida completa" if completo or not existe else "cambiaron las columnas: se sube completa"
        print(f"  {tabla}: {motivo} ({len(df):,} filas)...")
        crear_tabla(con, tabla, df)
        subir_filas(con, tabla, df)
        return len(df), 0

    nube = set(firmas_en_nube(con, tabla))
    local = set(df["_firma"])
    borrar = list(nube - local)
    agregar = df[~df["_firma"].isin(nube)]
    if not borrar and agregar.empty:
        print(f"  {tabla}: sin cambios.")
        return 0, 0
    print(f"  {tabla}: {len(agregar):,} filas para agregar, {len(borrar):,} para quitar...")
    for i in range(0, len(borrar), 500):
        trozo = borrar[i:i + 500]
        reintentar(lambda t=trozo: (con.execute(f'DELETE FROM "{tabla}" WHERE "_firma" IN ('
                                                + ",".join(["?"] * len(t)) + ")", t), con.commit()),
                   f"quitar filas de {tabla}")
    subir_filas(con, tabla, agregar)
    return len(agregar), len(borrar)


def correr(completo=False):
    if not os.path.exists(C.BASE_LOCAL):
        sys.exit("No existe base_admin.db. Corra primero:  python actualizar_desde_excel.py")
    print("Subiendo lo aprobado a la nube (base costos-admin)...")
    con = conectar_nube()
    con_local = sqlite3.connect(C.BASE_LOCAL)
    agregadas = quitadas = 0
    for tabla in TABLAS_NUBE:
        a, q = sincronizar(con_local, con, tabla, completo)
        agregadas += a
        quitadas += q
    con_local.close()

    # Marca de la subida: el dashboard de la nube la usa para saber que hay datos nuevos
    reintentar(lambda: (con.execute("CREATE TABLE IF NOT EXISTS _subidas (fecha TEXT, agregadas INTEGER, "
                                    "quitadas INTEGER)"), con.commit()), "registrar subida")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reintentar(lambda: (con.execute("INSERT INTO _subidas VALUES (?,?,?)", (ahora, agregadas, quitadas)),
                        con.commit()), "registrar subida")
    con.close()
    print(f"\nListo ({ahora}). Filas agregadas: {agregadas:,} · quitadas: {quitadas:,}. "
          "La app de la nube ya muestra lo aprobado.")


def subir_si_esta_configurada():
    """Para aprobar_carga.py y motor_costo_unitario.py: sube a la nube si ya está
    configurada; si algo falla, avisa pero no detiene lo demás."""
    if not os.path.exists(ARCHIVO_SECRETS):
        print("\n(La nube aún no está configurada: no se sube nada. Ver subir_a_nube.py)")
        return
    print()
    try:
        correr()
    except BaseException as e:   # incluye sys.exit con mensaje
        print(f"Aviso: no se pudo subir a la nube ({e}). Corra después:  python subir_a_nube.py")


if __name__ == "__main__":
    correr(completo="--completo" in sys.argv)
