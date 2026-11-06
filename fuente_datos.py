# -*- coding: utf-8 -*-
"""
DE DÓNDE LEE EL DASHBOARD
=========================
- En el PC (existe base_admin.db en la carpeta): lee la base local, como siempre.
- En la nube (Streamlit Cloud, donde NO hay base_admin.db): lee la base Turso
  "costos-admin", que llena subir_a_nube.py con lo APROBADO.

Las tablas son las mismas en los dos lados; el dashboard no nota la diferencia.
"""
import os
import sqlite3

import pandas as pd
import streamlit as st

import config as C

# Tablas que se suben a la nube (y que el dashboard lee)
TABLAS_NUBE = ["agrocacay_vigente", "kahai_vigente", "agrocacay_costo_unitario",
               "historial_cargas", "calculos_cu"]
FILAS_POR_PARTE = 10_000   # Turso corta respuestas muy grandes: se lee por partes


def en_la_nube():
    """True cuando no hay base local: la app está corriendo en Streamlit Cloud."""
    return not os.path.exists(C.BASE_LOCAL)


def _conectar_turso():
    import turso_serverless
    return turso_serverless.connect(st.secrets["TURSO_URL"], auth_token=st.secrets["TURSO_AUTH_TOKEN"])


def _leer_turso(con, consulta, params=()):
    cur = con.execute(consulta, params)
    columnas = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=columnas)


def version():
    """Un texto que cambia cada vez que hay datos nuevos. Se usa para saber
    cuándo volver a cargar (mientras no cambie, el dashboard usa lo que ya tiene)."""
    if not en_la_nube():
        return str(os.path.getmtime(C.BASE_LOCAL))
    return _version_nube()


@st.cache_data(ttl=120, show_spinner=False)
def _version_nube():
    # Se pregunta a la nube como máximo cada 2 minutos (no en cada clic)
    try:
        con = _conectar_turso()
        v = _leer_turso(con, "SELECT MAX(fecha) AS v FROM _subidas")["v"].iloc[0]
        con.close()
        return str(v)
    except Exception:
        return "sin-version"


def leer_tabla(nombre, orden=""):
    """Toda la tabla como DataFrame. Si no existe, DataFrame vacío."""
    if not en_la_nube():
        con = sqlite3.connect(C.BASE_LOCAL)
        try:
            return pd.read_sql(f'SELECT * FROM "{nombre}" {orden}', con)
        except Exception:
            return pd.DataFrame()
        finally:
            con.close()

    con = _conectar_turso()
    try:
        partes, ultimo = [], 0
        while True:
            parte = _leer_turso(con, f'SELECT rowid AS _fila, * FROM "{nombre}" WHERE rowid > ? '
                                     f'ORDER BY rowid LIMIT {FILAS_POR_PARTE}', (ultimo,))
            if parte.empty:
                break
            partes.append(parte)
            ultimo = int(parte["_fila"].iloc[-1])
        if not partes:
            return pd.DataFrame()
        df = pd.concat(partes, ignore_index=True).drop(columns=["_fila", "_firma"], errors="ignore")
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()
    if orden:   # mismo orden que en el PC (ej. "ORDER BY id DESC")
        partes_orden = orden.replace("ORDER BY", "").split()
        col, desc = partes_orden[0], len(partes_orden) > 1 and partes_orden[1].upper() == "DESC"
        if col in df.columns:
            df = df.sort_values(col, ascending=not desc, ignore_index=True)
    return df
