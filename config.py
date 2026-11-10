# -*- coding: utf-8 -*-
"""
CONFIGURACIÓN DE LA APP DE COSTOS ADMINISTRATIVOS
=================================================
Aquí está todo lo que se puede ajustar sin tocar el resto del código:
dónde están los Excel, cómo se llaman sus hojas y columnas, y los
umbrales del control de entrada.

IMPORTANTE: AGROCACAY y KAHAI son dos empresas separadas.
Cada una tiene su propio Excel, sus propias tablas en la base de datos,
su propio control de entrada y su propia aprobación.
"""
import os

# ---------------------------------------------------------------
# 1. DÓNDE ESTÁN LOS EXCEL (la base oficial que maneja administración)
# ---------------------------------------------------------------
# Carpeta de OneDrive donde viven los dos consolidados.
CARPETA_EXCEL = os.path.join(os.path.expanduser("~"), "OneDrive", "ANALISIS ADMINISTRATIVO")

# Si existe la variable de entorno CARPETA_EXCEL, se usa esa
# (sirve para hacer pruebas con copias sin tocar los originales).
CARPETA_EXCEL = os.environ.get("CARPETA_EXCEL", CARPETA_EXCEL)

# Base de datos local donde la app guarda lo que lee (nunca escribe en los Excel).
CARPETA_APP = os.path.dirname(os.path.abspath(__file__))
BASE_LOCAL = os.path.join(CARPETA_APP, "base_admin.db")
CARPETA_REPORTES = os.path.join(CARPETA_APP, "reportes_revision")

# ---------------------------------------------------------------
# 2. LAS DOS EMPRESAS
# ---------------------------------------------------------------
# Para cada empresa: archivo, hoja, y cómo se llama cada columna en SU Excel.
# A la izquierda el nombre estándar que usa la app; a la derecha el nombre
# real de la columna en el Excel de esa empresa.
EMPRESAS = {
    "AGROCACAY": {
        "archivo": "CONSOLIDADO_AGROCACAY.xlsx",
        "hoja": "CONSOLIDADO",
        "tabla": "agrocacay",          # prefijo de sus tablas en la base de datos
        "columnas": {
            "fecha":       "FECHA",
            "anio":        "AÑO",
            "mes":         "MES",
            "ceco":        "CECO",
            "planta":      "PLANTA",
            "cuenta":      "CUENTA",
            "tercero":     "TERCERO",
            "rubro":       "RUBRO",
            "detalle":     "DETALLE",
            "descripcion": "DESCRIPCIÓN",
            "ubicacion":   "ASIGNACION",
            "actividad":   "NOTAS",
            "documento":   "DOCUMENTO",
            "valor":       "DEBITO",
            "gerente":     "RUBRO CON GERENTES",
            "tipo_gasto":  "TIPO GASTO",
        },
        # Palabra que identifica a la empresa hermana como tercero
        # (para marcar las compras entre empresas).
        "empresa_hermana": "KAHAI",
    },
    "KAHAI": {
        "archivo": "CONSOLIDADO_KAHAI.xlsx",
        "hoja": "CONSOLIDADO_KAHAI",
        "tabla": "kahai",
        "columnas": {
            "fecha":       "FECHA",
            "anio":        "AÑO",
            "mes":         "MES",
            "ceco":        "CECO",
            "planta":      "PLANTA",
            "cuenta":      "CuentaContable",
            "tercero":     "Cuenta Tercero",
            "rubro":       "RUBRO_2",
            "detalle":     "DETALLE",
            "descripcion": "DESCRIPCION",
            "ubicacion":   "UBICACIÓN",
            "actividad":   "Actividad",
            "documento":   "NumDoc",
            "valor":       "Débitos",
            "gerente":     "GERENTES",
            "tipo_gasto":  "TIPO GASTO",
        },
        "empresa_hermana": "AGROCACAY",
    },
}

# Columnas sin las cuales no se puede cargar (si faltan en el Excel, se detiene).
COLUMNAS_OBLIGATORIAS = ["anio", "mes", "ceco", "rubro", "valor", "tipo_gasto"]

# Orden de las columnas en la base (estándar para las dos empresas).
COLUMNAS_ESTANDAR = ["fecha", "anio", "mes", "ceco", "planta", "cuenta", "tercero",
                     "rubro", "detalle", "descripcion", "ubicacion", "actividad",
                     "documento", "valor", "gerente", "tipo_gasto"]

MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}

# ---------------------------------------------------------------
# 3. NATURALEZA DEL GASTO (para separar la operación del resto)
# ---------------------------------------------------------------
CECOS_FINANCIERO = ["FINANCIERO"]
CECOS_INVERSION = ["ACTIVOS"]

# ---------------------------------------------------------------
# 4. UMBRALES DEL CONTROL DE ENTRADA
# ---------------------------------------------------------------
# Un rubro se marca como "fuera de lo normal" si en el mes supera
# este múltiplo de su promedio de los 12 meses anteriores...
UMBRAL_MULTIPLO_PROMEDIO = 2.0
# ...y además la diferencia es mayor a este valor (para no alertar por centavos).
UMBRAL_DIFERENCIA_MINIMA = 5_000_000

# Cambios (filas borradas o modificadas) en meses con más de esta
# antigüedad se reportan como "ajuste a mes anterior".
MESES_ABIERTOS = 2

# ---------------------------------------------------------------
# 5. DASHBOARD
# ---------------------------------------------------------------
# Nombres que aparecen en la columna de gerentes (GERENTES en KAHAI)
GERENTES = ["Alberto", "Camilo"]

# Naturalezas que el dashboard muestra al abrir (se pueden cambiar en pantalla).
# Intercompañía se incluye: así cada empresa ve las compras a su hermana como
# costo, igual que en su Excel (decisión del 29-oct-2026).
NATURALEZAS_POR_DEFECTO = ["Operativo", "Intercompañía"]

# Color fijo de cada empresa en las gráficas
COLOR_EMPRESA = {"AGROCACAY": "#2a78d6", "KAHAI": "#eb6834"}

# ---------------------------------------------------------------
# 6. COSTO UNITARIO (por ahora solo la parte agrícola: AGROCACAY)
# ---------------------------------------------------------------
# Las referencias de producción (reglas por rubro, cosecha PXN, censo,
# siembra/resiembra y árboles vivos) se siguen manteniendo en este Excel,
# igual que hoy. El motor solo las LEE.
ARCHIVO_REFERENCIAS_CU = os.path.join(CARPETA_EXCEL, "Graficas", "Ana_Costos_AGRO.xlsx")
EMPRESAS_COSTO_UNITARIO = ["AGROCACAY"]

# Divisores de procesamiento de KAHAI (kg por año: concha, nuez, aceite) y qué costo va con cada uno
ARCHIVO_PRODUCCION_KAHAI = os.path.join(CARPETA_EXCEL, "Graficas", "PRODUCCION_KAHAI.xlsx")
