# -*- coding: utf-8 -*-
"""
DASHBOARD MENSUAL — COSTOS ADMINISTRATIVOS AGROCACAY y KAHAI
=============================================================
Muestra lo que está APROBADO en base_admin.db (lo que dejó aprobar_carga.py).
No lee los Excel directamente ni los modifica.

Para abrirlo (desde la carpeta de la app):
    python -m streamlit run dashboard.py

Pestañas:
  1. Resumen         -> el mes contra el anterior, contra el mismo mes del año
                        pasado y el acumulado del año (o el año completo contra el anterior)
  2. Tabla mensual   -> CECO → Rubro → Detalle... con los meses en columnas
  3. Costo unitario  -> costo por árbol / por kg (AGROCACAY), igual a Ana_Costos_AGRO
  4. Gerentes        -> gastos marcados a Alberto y Camilo
  5. Intercompañía   -> compras entre AGROCACAY y KAHAI
  6. Movimientos     -> las filas del mes, con buscador
  6. Cargas          -> historial: quién aprobó qué y cuándo
"""
import os
import io
import re

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import config as C
import fuente_datos as F

st.set_page_config(page_title="Costos AGROCACAY · KAHAI", page_icon="📊", layout="wide",
                   initial_sidebar_state="collapsed")

# Evitar que el navegador (Edge/Chrome) traduzca la página: el traductor cambia el HTML por dentro
# y Streamlit se cae con 'removeChild'. Va ANTES del inicio de sesión para que proteja también esa pantalla.
# ===============================================================
# 3. FILTROS (barra lateral, con botones)
# ===============================================================
# Evitar que el navegador "traduzca" la página (ya está en español; el traductor
# cambiaba, por ejemplo, "Nómina" por "Nombre")
_SIN_TRADUCIR = """
document.documentElement.lang = 'es';
document.documentElement.setAttribute('translate', 'no');
document.documentElement.setAttribute('lang', 'es');
document.documentElement.classList.add('notranslate');
if (!document.querySelector('meta[name="google"]')) {
  const m = document.createElement('meta'); m.name = 'google'; m.content = 'notranslate';
  document.head.appendChild(m);
}"""
try:
    st.html(f"<script>{_SIN_TRADUCIR}</script>", unsafe_allow_javascript=True)
except TypeError:   # versiones de Streamlit más antiguas
    import streamlit.components.v1 as componentes
    componentes.html("<script>" + _SIN_TRADUCIR.replace("document", "window.parent.document") + "</script>",
                     height=0)


# En la nube se exige "Iniciar sesión con Google" (solo correos autorizados); en el PC no.
USUARIO = None
if F.en_la_nube():
    from acceso import exigir_acceso
    USUARIO = exigir_acceso()

# ---------------------------------------------------------------
# ESTILO EJECUTIVO (encabezado, barra de filtros arriba, tarjetas de indicadores)
# ---------------------------------------------------------------
VERDE = "#1B5E20"          # color de marca (el mismo de la app de campo)
st.markdown(f"""
<style>
  /* Sin barra lateral: los filtros van arriba */
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}
  .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1500px; }}

  /* Encabezado */
  .enc {{ display:flex; align-items:center; gap:1rem; padding:0.9rem 1.3rem; border-radius:14px;
          background: linear-gradient(120deg, #0F3D1F 0%, {VERDE} 70%, #2E7D32 100%); color:#fff; }}
  .enc .logos {{ display:flex; align-items:center; gap:10px; background:#fff; border-radius:12px; padding:7px 12px; }}
  .enc .logos img {{ height:60px; width:auto; display:block; }}
  .enc .logos .sep {{ width:1px; height:48px; background:#D1D5DB; }}
  .enc .tit {{ font-size:1.55rem; font-weight:700; line-height:1.15; letter-spacing:0.2px; }}
  .enc .sub {{ font-size:0.92rem; opacity:0.88; margin-top:2px; }}
  @media (max-width: 640px) {{
    .enc {{ flex-direction:column; align-items:flex-start; gap:0.5rem; }}
    .enc .logos img {{ height:40px; }}
    .enc .tit {{ font-size:1.2rem; }}
  }}
  .enc .chip {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem;
                font-weight:600; background:rgba(255,255,255,0.16); margin-right:6px; }}

  /* ===== Panel de filtros: una sola tarjeta ejecutiva ===== */
  .st-key-barra_filtros {{ position:relative; overflow:hidden; margin-top:0.7rem; background:#FFFFFF;
        border:1px solid #E3E8E2; border-radius:16px; padding:0.75rem 1.2rem 0.6rem 1.2rem;
        box-shadow:0 1px 2px rgba(16,24,40,0.04), 0 10px 28px -14px rgba(16,24,40,0.18); gap:0.25rem; }}
  .st-key-barra_filtros [data-testid="stHorizontalBlock"] {{ gap:0.6rem; }}
  .st-key-barra_filtros [data-testid="stVerticalBlock"] {{ gap:0.25rem; }}
  .st-key-barra_filtros [data-testid="stElementContainer"] {{ margin:0; }}
  .st-key-barra_filtros::before {{ content:""; position:absolute; left:0; right:0; top:0; height:3px;
        background:linear-gradient(90deg, {VERDE} 0%, #43A047 55%, var(--acento) 100%); }}
  .st-key-bloque_alcance, .st-key-bloque_periodo {{ gap:0.55rem; }}
  .st-key-bloque_alcance [data-testid="stVerticalBlock"],
  .st-key-bloque_periodo [data-testid="stVerticalBlock"] {{ gap:0.55rem; }}
  .st-key-bloque_periodo {{ border-left:1px solid #EDF1EC; padding-left:1.4rem; }}
  @media (max-width: 900px) {{
    .st-key-bloque_periodo {{ border-left:none; padding-left:0; border-top:1px solid #EDF1EC; padding-top:0.7rem; }}
  }}
  /* Sin recorte ni desvanecido al borde: todas las fichas se ven completas */
  .st-key-barra_filtros [data-testid="stButtonGroup"], .st-key-barra_filtros [data-testid="stButtonGroup"] * {{
        mask-image:none !important; -webkit-mask-image:none !important; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] {{ overflow:visible !important; }}
  /* Títulos de cada filtro: pequeños, en mayúsculas, discretos */
  .st-key-barra_filtros [data-testid="stWidgetLabel"] {{ margin-bottom:0.05rem; min-height:0; height:auto; }}
  .st-key-barra_filtros [data-testid="stWidgetLabel"] label {{ min-height:0; }}
  .st-key-barra_filtros [data-testid="stTooltipIcon"] svg {{ width:0.85rem; height:0.85rem; }}
  .st-key-barra_filtros label p {{ font-size:0.66rem !important; font-weight:700 !important; letter-spacing:1px;
        text-transform:uppercase; color:#7A867C !important; }}
  /* Botones: fichas suaves; la elegida, sólida y con sombra */
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button {{ border-radius:9px !important; border:1px solid #E3E8E2 !important;
        background:#F7F9F7 !important; min-height:1.8rem; padding:0.05rem 0.8rem !important;
        transition:background .15s, border-color .15s, box-shadow .15s, transform .15s; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button p {{ color:#344054 !important; font-weight:500; font-size:0.86rem; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button:hover {{ background:#FFFFFF !important;
        border-color:#9CC79F !important; transform:translateY(-1px); }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button[aria-pressed="true"],
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button[aria-checked="true"],
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button[kind$="Active"] {{
        background:{VERDE} !important; border-color:{VERDE} !important;
        box-shadow:0 3px 8px -2px rgba(27,94,32,0.45); }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button[aria-pressed="true"] p,
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button[aria-checked="true"] p,
  .st-key-barra_filtros [data-testid="stButtonGroup"] :is([role="toolbar"],[role="radiogroup"]) > button[kind$="Active"] p {{ color:#fff !important; font-weight:600; }}

  /* Empresa: fichas grandes con el punto de color de cada empresa; Grupo ocupa el alto completo */
  .st-key-f_empresa [role="radiogroup"] {{ display:grid !important; grid-template-columns:repeat(3, max-content);
        gap:6px; overflow:visible !important; width:fit-content; }}
  .st-key-f_empresa [role="radiogroup"] > button {{ border-radius:10px !important; width:100%; min-width:0; min-height:1.85rem;
        padding:0.1rem 0.8rem !important;
        border:1px solid #E3E8E2 !important; margin:0 !important; background:#F7F9F7 !important; justify-content:flex-start; }}
  .st-key-f_empresa [role="radiogroup"] > button p {{ font-weight:600; letter-spacing:0.3px; color:#344054 !important; }}
  .st-key-f_empresa [role="radiogroup"] > button::before {{ content:""; width:9px; height:9px; border-radius:50%;
        margin-right:8px; flex:none; background:#2a78d6; box-shadow:0 0 0 3px rgba(42,120,214,0.15); }}
  .st-key-f_empresa [role="radiogroup"] > button:nth-child(2)::before {{ background:#eb6834;
        box-shadow:0 0 0 3px rgba(235,104,52,0.15); }}
  .st-key-f_empresa [role="radiogroup"] > button:nth-child(3)::before {{
        background:linear-gradient(135deg, #2a78d6 50%, #eb6834 50%); box-shadow:0 0 0 3px rgba(27,94,32,0.12); }}

  .st-key-barra_filtros .st-key-f_empresa [role="radiogroup"] > button:is([data-selected="true"],[aria-checked="true"],[kind$="Active"]) {{ background:var(--acento) !important;
        border-color:var(--acento) !important; box-shadow:0 4px 12px -4px var(--acento); }}
  .st-key-barra_filtros .st-key-f_empresa [role="radiogroup"] > button:is([data-selected="true"],[aria-checked="true"],[kind$="Active"])::before {{ background:#fff !important;
        box-shadow:0 0 0 3px rgba(255,255,255,0.35) !important; }}
  .st-key-barra_filtros .st-key-f_empresa [role="radiogroup"] > button:is([data-selected="true"],[aria-checked="true"],[kind$="Active"]) p {{ color:#fff !important; }}

  /* Año y mes: cada uno en un "riel" gris claro; la ficha elegida resalta encima */
  .st-key-f_anio [role="toolbar"], .st-key-f_anio [role="radiogroup"],
  [class*="st-key-f_mes"] [role="toolbar"], [class*="st-key-f_mes"] [role="radiogroup"] {{
        background:#F1F4F0; border-radius:11px; padding:3px; gap:3px !important; overflow:visible !important; }}
  .st-key-f_anio [role="toolbar"], .st-key-f_anio [role="radiogroup"] {{ display:flex !important; flex-wrap:wrap;
        width:fit-content; }}
  [class*="st-key-f_mes"] [role="toolbar"], [class*="st-key-f_mes"] [role="radiogroup"] {{ display:flex !important;
        flex-wrap:wrap; width:fit-content; }}
  /* "Todos" y "Año completo" separados del resto con una línea fina */
  .st-key-f_anio :is([role="toolbar"],[role="radiogroup"]) > button:first-child,
  [class*="st-key-f_mes"] :is([role="toolbar"],[role="radiogroup"]) > button:first-child {{
        margin-right:6px !important; }}
  .st-key-f_anio button, [class*="st-key-f_mes"] button {{ min-height:1.7rem !important; padding:0.02rem 0.6rem !important; }}
  .st-key-f_anio button p, [class*="st-key-f_mes"] button p {{ font-size:0.82rem !important; }}
  .st-key-f_anio button, [class*="st-key-f_mes"] button {{ margin:0 !important; justify-content:center;
        background:transparent !important; border-color:transparent !important; }}
  .st-key-f_anio button:hover, [class*="st-key-f_mes"] button:hover {{ background:#FFFFFF !important;
        border-color:#E3E8E2 !important; }}
  /* Naturaleza: 2 x 2 · Tipo de gasto: uno debajo del otro */
  .st-key-f_naturaleza [role="toolbar"] {{ display:grid !important; grid-template-columns:repeat(4, max-content);
        gap:6px; overflow:visible !important; width:fit-content; }}
  .st-key-f_naturaleza [role="toolbar"] > button {{ width:100%; margin:0 !important; }}
  .st-key-f_tipo [role="toolbar"] {{ display:grid !important; grid-template-columns:repeat(2, max-content); gap:6px;
        width:fit-content; overflow:visible !important; }}
  .st-key-f_tipo [role="toolbar"] > button {{ width:100%; margin:0 !important; }}

  /* Resumen de lo que se está viendo (abajo del panel) */
  .resumen {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; padding-top:0.6rem;
              border-top:1px dashed #E3E8E2; }}
  .resumen .lbl {{ font-size:0.66rem; font-weight:700; letter-spacing:1px; text-transform:uppercase;
                   color:#7A867C; margin-right:2px; }}
  .resumen .ch {{ display:inline-flex; align-items:center; gap:6px; padding:2px 9px; border-radius:999px;
                  background:#F3F6F3; border:1px solid #E6EBE5; font-size:0.76rem; color:#344054; white-space:nowrap; }}
  .resumen .ch .pt {{ width:8px; height:8px; border-radius:50%; background:var(--acento); }}
  .resumen .ch.per {{ background:#EAF3EA; border-color:#CFE3D0; color:{VERDE}; font-weight:600; }}
  .periodo {{ display:flex; justify-content:flex-end; align-items:center; gap:8px; flex-wrap:wrap; padding-bottom:3px; }}
  .periodo .lbl {{ font-size:0.66rem; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#7A867C; }}
  .periodo .ch {{ padding:3px 11px; border-radius:999px; background:#EAF3EA; border:1px solid #CFE3D0; color:{VERDE};
                  font-weight:600; font-size:0.8rem; white-space:nowrap; }}
  a.restablecer {{ display:inline-block; margin-bottom:2px; font-size:0.76rem; font-weight:600; color:#5B6B5E !important;
                   text-decoration:none; white-space:nowrap; padding:4px 11px; border-radius:999px; border:1px solid #E3E8E2; }}
  a.restablecer:hover {{ color:{VERDE} !important; border-color:#9CC79F; background:#F7FBF7; }}

  /* Tarjetas de indicadores */
  [data-testid="stMetric"] {{ background:#fff; border:1px solid #E5E7EB; border-left:5px solid var(--acento);
                              border-radius:12px; padding:0.8rem 1rem; box-shadow:0 1px 2px rgba(16,24,40,0.05); }}
  [data-testid="stMetricLabel"] p {{ font-size:0.8rem !important; color:#5B6470 !important; font-weight:600; }}
  [data-testid="stMetricValue"] {{ font-size:1.65rem !important; font-weight:700; color:#111827; }}

  /* Pestañas */
  .stTabs [data-baseweb="tab-list"] {{ gap:0.3rem; border-bottom:1px solid #E5E7EB; }}
  .stTabs [data-baseweb="tab"] {{ padding:0.5rem 0.9rem; font-weight:600; }}
  .stTabs [aria-selected="true"] {{ color:{VERDE} !important; }}
  .stTabs [data-baseweb="tab-highlight"] {{ background-color:{VERDE} !important; }}
</style>
""", unsafe_allow_html=True)

NOMBRE_MES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
              7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
GRUPO = "Grupo"


# ===============================================================
# 1. AYUDAS DE FORMATO (números al estilo colombiano: 1.234.567,8)
# ===============================================================
def pesos(v):
    """Valor en pesos con puntos de miles: 1.234.567"""
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.0f}".replace(",", ".")


def millones(v):
    """Valor en millones con un decimal: 1.234,5 M"""
    if v is None or pd.isna(v):
        return "—"
    return f"{v / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " M"


def porcentaje(v):
    if v is None or pd.isna(v) or np.isinf(v):
        return "—"
    return f"{v:+.1%}".replace(".", ",")


def variacion(actual, anterior):
    if anterior is None or pd.isna(anterior) or anterior == 0:
        return None
    return actual / anterior - 1


def etiqueta(periodo):
    """202609 -> 'Sep-2026'"""
    a, m = divmod(int(periodo), 100)
    return f"{NOMBRE_MES[m]}-{a}"


def mover(periodo, meses):
    """Suma o resta meses a un periodo AAAAMM: mover(202601, -1) = 202512"""
    a, m = divmod(int(periodo), 100)
    total = a * 12 + (m - 1) + meses
    return (total // 12) * 100 + total % 12 + 1


# ===============================================================
# 1b. MANO DE OBRA vs OTROS COSTOS
# ===============================================================
BLOQUES = ["Mano de obra (nómina)", "Mano de obra al contrato", "Otros costos",
           "Intercompañía", "Financiero", "Inversión"]
COLOR_BLOQUE = {"Mano de obra (nómina)": "#2a78d6", "Mano de obra al contrato": "#eb6834",
                "Otros costos": "#1baf7a", "Intercompañía": "#eda100", "Financiero": "#e87ba4",
                "Inversión": "#008300"}


def clasificar_bloque(d):
    """Mano de obra (nómina)    = TIPO GASTO Nómina: los jornales por actividad que vienen de la
                                  app de campo con prefijo AC_ (AGROCACAY), KC_ (KAHAI cultivo/planta)
                                  o KV_ (KAHAI vivero), más los ajustes de nómina sin prefijo.
       Mano de obra al contrato = terceros pagados por contrato: la actividad dice "contrato"
                                  (ej. "FC DS 1394 - Contrato Nomina Guadañador") o el DETALLE /
                                  DESCRIPCIÓN dice "mano de obra" (recolección, llenado de bolsa,
                                  pelado...), tal como lo clasificó administración. El transporte
                                  de personal (descripción "Transporte") va a otros costos.
       Otros costos             = el resto de terceros (insumos, combustible, administración...)
       Lo que no es operativo se muestra con su naturaleza (Intercompañía, Financiero, Inversión)."""
    actividad = d["actividad"].fillna("").str.lower()
    texto = (d["detalle"].fillna("") + " " + d["descripcion"].fillna("")).str.lower()
    contrato = actividad.str.contains("contrat", regex=False) | texto.str.contains("mano de obra", regex=False)
    # El transporte de personal (pasajes, taxis) va a otros costos aunque diga "mano de obra"
    transporte = d["descripcion"].fillna("").str.lower().str.contains("transporte", regex=False)
    contrato = contrato & ~transporte
    bloque = np.where(d["tipo"] == "Nómina", "Mano de obra (nómina)",
                      np.where(contrato, "Mano de obra al contrato", "Otros costos"))
    return np.where(d["naturaleza"] == "Operativo", bloque, d["naturaleza"])


def prefijo_actividad(d):
    """AC / KC / KV según el código de la actividad (solo viene en la nómina)."""
    p = d["actividad"].fillna("").str.extract(r"^\s*([A-Za-z]{2})[_\-]")[0].str.upper()
    p = p.where(p.isin(["AC", "KC", "KV"]))
    return np.where(d["tipo"] == "Nómina", p.fillna("Nómina sin prefijo"), "(terceros)")


# ===============================================================
# 2. CARGAR LA BASE (se guarda en memoria hasta que la base cambie)
# ===============================================================
@st.cache_data(show_spinner="Cargando la base...")
def cargar(version_datos):
    # Lee del PC (base_admin.db) o de la nube (Turso), según dónde corra (ver fuente_datos.py)
    partes = []
    for empresa, conf in C.EMPRESAS.items():
        tabla = F.leer_tabla(f"{conf['tabla']}_vigente")
        if not tabla.empty:          # si está vacía, esa empresa aún no tiene carga
            partes.append(tabla)
    historial = F.leer_tabla("historial_cargas", "ORDER BY id DESC")
    if not partes:
        return pd.DataFrame(), historial

    df = pd.concat(partes, ignore_index=True)
    df = df[df["periodo"].notna()].copy()
    df["periodo"] = df["periodo"].astype(int)
    df["valor"] = df["valor"].fillna(0)

    # Tipo de gasto unificado (AGROCACAY escribe "Tercero" y "Terceros")
    t = df["tipo_gasto"].fillna("").str.upper()
    df["tipo"] = np.where(t.str.startswith("NOMINA"), "Nómina",
                          "Terceros")   # todo lo que no es nómina
    df["bloque"] = clasificar_bloque(df)
    df["prefijo"] = prefijo_actividad(df)
    for col in ["ceco", "rubro", "detalle", "ubicacion", "actividad", "descripcion", "tercero"]:
        df[col] = df[col].fillna("(sin dato)")
    return df, historial


VERSION_DATOS = F.version()
datos, historial = cargar(VERSION_DATOS)
if datos.empty:
    if F.en_la_nube():
        st.error("La base de la nube está vacía. En el PC corra:  python subir_a_nube.py")
    else:
        st.error("La base está vacía. Corra primero:  python actualizar_desde_excel.py")
    st.stop()




def boton_unico(lugar, etiqueta_f, opciones, defecto, clave, ayuda=None, formato=None, segmentado=False):
    """Botones de una sola selección. Si el usuario quita la selección, vuelve al valor por defecto."""
    widget = lugar.segmented_control if segmentado else lugar.pills
    valor = widget(etiqueta_f, opciones, selection_mode="single", default=defecto, key=clave,
                   help=ayuda, format_func=formato)
    return defecto if valor is None else valor


# El encabezado se dibuja ARRIBA de los filtros, pero se llena después (necesita el periodo elegido)
encabezado = st.container()

# ---- Filtros arriba, en 3 filas horizontales: (1) empresa · tipo · naturaleza  (2) año  (3) mes ----
with st.container(key="barra_filtros"):
    f1 = st.columns([1.45, 0.78, 1.8, 0.42], gap="small", vertical_alignment="bottom")
    vista = boton_unico(f1[0], "Empresa", ["AGROCACAY", "KAHAI", GRUPO], "AGROCACAY", "f_empresa",
                        "Las empresas se ven por separado. 'Grupo' suma las dos.", segmentado=True)
    tipos = f1[1].pills("Tipo de gasto", ["Nómina", "Terceros"], selection_mode="multi",
                        default=["Nómina", "Terceros"], key="f_tipo",
                        help="Nómina = empleados de la empresa. Terceros = todo lo demás: proveedores, "
                             "contratistas, servicios, impuestos, bancos. Los dos encendidos = gasto total.")
    naturalezas = f1[2].pills(
        "Naturaleza del gasto", ["Operativo", "Intercompañía", "Financiero", "Inversión"],
        selection_mode="multi", default=C.NATURALEZAS_POR_DEFECTO, key="f_naturaleza",
        help="Toque para activar o quitar. Financiero = CECO FINANCIERO (intereses, créditos). "
             "Inversión = CECO ACTIVOS. Intercompañía = compras a la empresa hermana.")
    # Restablecer = volver a abrir la página (empieza limpia; la sesión de Google se mantiene)
    f1[3].markdown('<div style="text-align:right"><a class="restablecer" href="./" target="_self" '
                   'title="Vuelve todos los filtros a como abre la app">↺ Restablecer</a></div>', unsafe_allow_html=True)
    empresas_vista = list(C.EMPRESAS) if vista == GRUPO else [vista]
    base_empresa = datos[datos["empresa"].isin(empresas_vista)]
    periodos = sorted(base_empresa["periodo"].unique())

    # Fila 2: año ("Todos" = todos los años, una columna por año) y, a la derecha, contra qué se compara
    f2 = st.columns([2.6, 1.5], gap="small", vertical_alignment="bottom")
    anios = sorted({p // 100 for p in periodos})
    TODOS_ANIOS = "Todos"
    anio_sel = boton_unico(f2[0], "Año", [TODOS_ANIOS] + anios, anios[-1], "f_anio")
    todos = anio_sel == TODOS_ANIOS
    anio = anios[-1] if todos else anio_sel
    meses_del_anio = [p % 100 for p in periodos if p // 100 == anio]
    AÑO_COMPLETO = "Año completo"
    # Fila 3: mes
    if todos:
        # Con "Todos" también se puede elegir un mes: ese mes en cada año (Sep-2018 … Sep-2026)
        meses_todos = sorted({p % 100 for p in periodos})
        mes_txt = boton_unico(st, "Mes", [AÑO_COMPLETO] + [NOMBRE_MES[m] for m in meses_todos],
                              AÑO_COMPLETO, "f_mes_todos")
        ultimo_m = NOMBRE_MES[meses_del_anio[-1]]
        if mes_txt == AÑO_COMPLETO:
            frase = (f"Todos los años ({anios[0]}–{anios[-1]}) · una columna por año. "
                     f"{anios[-1]} va hasta {ultimo_m}" if meses_del_anio[-1] < 12 else
                     f"Todos los años ({anios[0]}–{anios[-1]}) · una columna por año")
            frase_c = f"Todos los años ({anios[0]}–{anios[-1]})"
        else:
            frase = f"{mes_txt} de cada año · una columna por año, para ver cómo se comporta ese mes en el tiempo"
            frase_c = f"{mes_txt} de cada año"
    else:
        opciones_mes = [AÑO_COMPLETO] + [NOMBRE_MES[m] for m in meses_del_anio]
        # Año en curso: abre en el último mes. Años anteriores: abre en el año completo.
        defecto_mes = NOMBRE_MES[meses_del_anio[-1]] if anio == anios[-1] else AÑO_COMPLETO
        mes_txt = boton_unico(st, "Mes", opciones_mes, defecto_mes, f"f_mes_{anio}")
        # Frase que explica contra qué se compara lo elegido (para leer las tarjetas sin dudas)
        if mes_txt == AÑO_COMPLETO:
            ultimo_m = NOMBRE_MES[meses_del_anio[-1]]
            hasta = "" if meses_del_anio[-1] == 12 else f" (Ene–{ultimo_m})"
            frase = f"Año {anio}{hasta} · se compara con los mismos meses de {anio - 1}"
            frase_c = f"Año {anio}{hasta} · vs mismos meses {anio - 1}"
        else:
            n_m = [k for k, v in NOMBRE_MES.items() if v == mes_txt][0]
            previo = f"{NOMBRE_MES[n_m - 1]}-{anio}" if n_m > 1 else f"Dic-{anio - 1}"
            frase = (f"{mes_txt}-{anio} · se compara con {previo} (mes anterior) y "
                     f"{mes_txt}-{anio - 1} (año anterior)")
            frase_c = f"{mes_txt}-{anio} · vs {previo} y {mes_txt}-{anio - 1}"
    f2[1].markdown(f'<div class="periodo" title="{frase}"><span class="lbl">Comparando</span>'
                   f'<span class="ch">📅 {frase_c}</span></div>', unsafe_allow_html=True)

df = base_empresa[base_empresa["naturaleza"].isin(naturalezas) & base_empresa["tipo"].isin(tipos)]

# Color de acento de las tarjetas: el de la empresa elegida (verde de marca para Grupo)
st.markdown(f"<style>:root {{ --acento: {C.COLOR_EMPRESA.get(vista, VERDE)}; }}</style>", unsafe_allow_html=True)

# Cargas pendientes y última aprobación (se muestran en el encabezado)
pendientes, texto_aprobacion = [], ""
if not historial.empty:
    pend = historial[historial["estado"] == "pendiente"]
    pendientes = [f"{p['empresa']}: hay una lectura del {p['fecha_lectura']} pendiente de aprobar; "
                  "aquí se ve aún la versión anterior." for _, p in pend.iterrows()
                  if p["empresa"] in empresas_vista]
    aprob = historial[historial["estado"] == "aprobada"].groupby("empresa")["fecha_decision"].max()
    texto_aprobacion = " · ".join(f"{e} {str(f)[:10]}" for e, f in aprob.items() if e in empresas_vista)

if df.empty:
    st.warning("No hay datos con estos filtros.")
    st.stop()

# ---------------------------------------------------------------
# Periodo que se analiza
#   Mes:          el mes contra el mes anterior, contra el mismo mes del año pasado y el acumulado
#   Año completo: los meses del año contra los mismos meses del año anterior
# ---------------------------------------------------------------
anual = mes_txt == AÑO_COMPLETO
if todos and anual:
    seleccion = list(periodos)          # todos los meses de todos los años
    mes = seleccion[-1]
elif todos:
    n_mes_todos = [k for k, v in NOMBRE_MES.items() if v == mes_txt][0]
    seleccion = [p for p in periodos if p % 100 == n_mes_todos]   # ese mes en cada año
    mes = seleccion[-1]
    anio = mes // 100
elif anual:
    seleccion = [p for p in periodos if p // 100 == anio]
    mes = seleccion[-1]
else:
    mes = anio * 100 + [m for m in meses_del_anio if NOMBRE_MES[m] == mes_txt][0]
    seleccion = [mes]
num_mes = mes % 100
mes_ant = mover(mes, -1)
mes_anio_ant = mover(mes, -12)
acum = [p for p in periodos if p // 100 == anio and p % 100 <= num_mes]
acum_ant = [mover(p, -12) for p in acum]
ult12 = [mover(mes, -k) for k in range(1, 13)]
anio_ant_completo = [anio * 100 - 100 + m for m in range(1, 13)]
rango_meses = "" if num_mes == 12 else f" (Ene–{NOMBRE_MES[num_mes]})"
etq_sel = (f"Todos los años {anios[0]}–{anios[-1]}" if todos and anual else
           f"{mes_txt} de todos los años" if todos else
           f"Año {anio}{rango_meses}" if anual else etiqueta(mes))
etq_acum, etq_acum_ant = f"Ene–{NOMBRE_MES[num_mes]} {anio}", f"Ene–{NOMBRE_MES[num_mes]} {anio - 1}"


def suma(d, lista):
    return d.loc[d["periodo"].isin(lista), "valor"].sum()


# Columnas de comparación que usan las tablas, según se mire un mes, un año o todos los años
anios_completos = [a for a in anios if len({p for p in periodos if p // 100 == a}) == 12]


def etq_anio(a):
    """'2025' si el año tiene los 12 meses; si no, con su tramo real: '2026 (Ene–Sep)', '2016 (Mar–Dic)'."""
    m = sorted(p % 100 for p in periodos if p // 100 == a)
    return str(a) if len(m) == 12 or not m else f"{a} ({NOMBRE_MES[m[0]]}–{NOMBRE_MES[m[-1]]})"
if todos and not anual:
    # Un mes en cada año: una columna por año; la variación, el último contra el anterior
    COLUMNAS = [(etiqueta(p), [p]) for p in seleccion]
    PARTICIPACION = {}
    VARIACIONES = ([(len(COLUMNAS) - 1, len(COLUMNAS) - 2,
                     f"Var {etiqueta(seleccion[-1])} vs {etiqueta(seleccion[-2])}")] if len(COLUMNAS) >= 2 else [])
elif todos:
    COLUMNAS = [(f"Total {anios[0]}–{anios[-1]}", seleccion)] + \
               [(etq_anio(a), [p for p in periodos if p // 100 == a])
                for a in anios]
    PARTICIPACION = {0: "% del total"}
    # Variación entre los dos últimos años COMPLETOS (el año en curso va incompleto)
    if len(anios_completos) >= 2:
        i_u, i_p = anios.index(anios_completos[-1]) + 1, anios.index(anios_completos[-2]) + 1
        VARIACIONES = [(i_u, i_p, f"Var {anios_completos[-1]} vs {anios_completos[-2]}")]
    else:
        VARIACIONES = []
elif anual:
    COLUMNAS = [(etq_acum, acum), (etq_acum_ant, acum_ant)]
    if num_mes < 12:   # año en curso: también el año anterior completo, como referencia
        COLUMNAS.append((f"Año {anio - 1} completo", anio_ant_completo))
    VARIACIONES = [(0, 1, f"Var vs {anio - 1}")]
    PARTICIPACION = {0: "% del año"}
else:
    COLUMNAS = [(etiqueta(mes), [mes]), (etiqueta(mes_ant), [mes_ant]), (etiqueta(mes_anio_ant), [mes_anio_ant]),
                (f"Acum {etq_acum}", acum), (f"Acum {etq_acum_ant}", acum_ant)]
    VARIACIONES = [(0, 1, "Var vs mes ant."), (0, 2, "Var vs año ant."), (3, 4, "Var acum.")]
    PARTICIPACION = {0: "% del mes", 3: "% del año"}


def tabla_comparativa(d, llaves, orden=None, subtotales=None):
    """Tabla con las columnas de COMPARAR para cada grupo de 'llaves', más TOTAL.
       subtotales = {"Nombre del subtotal": [filas que suma]} (se ubica después de la última de ellas)."""
    valores = pd.concat([d[d["periodo"].isin(lista)].groupby(llaves)["valor"].sum().rename(nombre)
                         for nombre, lista in COLUMNAS], axis=1).fillna(0)
    if orden is not None:
        valores = valores.reindex([o for o in orden if o in valores.index])
    filas = []
    for idx, fila in valores.iterrows():
        filas.append((idx, fila))
        for nombre_sub, miembros in (subtotales or {}).items():
            presentes = [m for m in miembros if m in valores.index]
            if len(presentes) > 1 and idx == presentes[-1]:
                filas.append((nombre_sub, valores.loc[presentes].sum()))
    total = valores.sum()
    filas.append(("TOTAL", total))
    salida = []
    for idx, fila in filas:
        registro = {}
        claves = idx if isinstance(idx, tuple) else (idx,)
        for nombre_llave, v in zip(llaves, claves if len(claves) == len(llaves) else (claves[0],) * len(llaves)):
            registro[nombre_llave] = v
        for i, (nombre, _) in enumerate(COLUMNAS):
            registro[nombre] = fila[nombre]
            if i in PARTICIPACION:
                registro[PARTICIPACION[i]] = fila[nombre] / total[nombre] if total[nombre] else None
            for a, b, nombre_var in VARIACIONES:
                if max(a, b) == i:   # la variación va después de la última de las dos columnas
                    registro[nombre_var] = variacion(fila[COLUMNAS[a][0]], fila[COLUMNAS[b][0]])
        salida.append(registro)
    t = pd.DataFrame(salida)
    if len(llaves) > 1:   # en TOTAL / subtotales solo se escribe en la primera columna
        mascara = t[llaves[0]].isin(["TOTAL"] + list((subtotales or {}).keys()))
        for c in llaves[1:]:
            t.loc[mascara, c] = ""
    return t


def mostrar_comparativa(t, nombres):
    cols_val = [n for n, _ in COLUMNAS]
    for c in [v[2] for v in VARIACIONES]:
        t[c] = t[c].map(porcentaje)
    for c in PARTICIPACION.values():
        t[c] = t[c].map(lambda v: "—" if v is None or pd.isna(v) else f"{v:.1%}".replace(".", ","))
    t = t.rename(columns=nombres)
    destacadas = {"TOTAL", "Subtotal mano de obra"}
    st.dataframe(t.style.format(pesos, subset=cols_val)
                 .apply(lambda r: ["font-weight: bold" if (i == 0 and r.iloc[0] in destacadas) else ""
                                   for i, _ in enumerate(r)], axis=1),   # negrita solo en el nombre
                 hide_index=True, width="stretch")


titulo_vista = "Grupo AGROCACAY + KAHAI" if vista == GRUPO else vista


def _logo_html():
    """Logo de la empresa elegida (en alta resolución); en Grupo, los dos."""
    import base64

    def img(nombre):
        ruta = os.path.join(C.CARPETA_APP, nombre)
        if not os.path.exists(ruta):
            return ""
        return f'<img src="data:image/png;base64,{base64.b64encode(open(ruta, "rb").read()).decode()}" alt="">'
    archivos = {"AGROCACAY": ["logo_agrocacay.png"], "KAHAI": ["logo_kahai_solo.png"]}.get(
        vista, ["logo_agrocacay.png", "logo_kahai_solo.png"])
    imgs = [img(a) for a in archivos if img(a)]
    if not imgs:   # respaldo: el logo combinado anterior
        imgs = [img("logo_kahai_recortado.png") or img("logo_kahai.png")]
    return '<div class="logos">' + '<span class="sep"></span>'.join(imgs) + "</div>"


with encabezado:
    e1, e2 = st.columns([5, 1], vertical_alignment="center") if USUARIO else (st.container(), None)
    chips = "".join(f'<span class="chip">{t}</span>' for t in
                    [", ".join(naturalezas) or "sin naturaleza", " + ".join(tipos) or "sin tipo", "Pesos COP · M = millones"])
    aprobado = f"Cifras aprobadas · última aprobación {texto_aprobacion}" if texto_aprobacion else "Cifras aprobadas"
    e1.markdown(f"""<div class="enc">{_logo_html()}<div>
        <div class="tit">Costos {titulo_vista} · {etq_sel}</div>
        <div class="sub">{aprobado}</div>
        <div class="sub" style="margin-top:6px">{chips}</div></div></div>""", unsafe_allow_html=True)
    if USUARIO:
        e2.caption(f"👤 {USUARIO}")
        e2.button("Cerrar sesión", on_click=st.logout, key="btn_salir", width="stretch")
    for aviso in pendientes:
        st.warning(aviso, icon="⏳")

pest = st.tabs(["Resumen", "Tabla mensual", "Costo unitario", "Gerentes", "Intercompañía", "Movimientos", "Cargas"])


# ===============================================================
# 4. PESTAÑA RESUMEN
# ===============================================================
with pest[0]:
    k = st.columns(4)
    # delta_color="inverse": si el gasto SUBE se muestra en rojo
    if todos and not anual:
        por_p = df[df["periodo"].isin(seleccion)].groupby("periodo")["valor"].sum().reindex(seleccion).fillna(0)
        previo = por_p.iloc[-2] if len(por_p) >= 2 else None
        k[0].metric(etiqueta(mes), millones(por_p.iloc[-1]),
                    f"{porcentaje(variacion(por_p.iloc[-1], previo))} vs {etiqueta(seleccion[-2])}"
                    if previo else None, delta_color="inverse")
        k[1].metric(f"Promedio de {mes_txt} ({len(por_p)} años)", millones(por_p.mean()))
        k[2].metric(f"Mayor: {etiqueta(por_p.idxmax())}", millones(por_p.max()))
        k[3].metric(f"Menor: {etiqueta(por_p.idxmin())}", millones(por_p.min()))
    elif todos:
        por_anio = df.groupby(df["periodo"] // 100)["valor"].sum()
        k[0].metric(f"Gasto total {anios[0]}–{anios[-1]}", millones(por_anio.sum()))
        if len(anios_completos) >= 2:
            a_u, a_p = anios_completos[-1], anios_completos[-2]
            k[1].metric(f"Año {a_u} (último completo)", millones(por_anio.get(a_u, 0)),
                        f"{porcentaje(variacion(por_anio.get(a_u, 0), por_anio.get(a_p, 0)))} vs {a_p}",
                        delta_color="inverse")
        completos = por_anio.reindex(anios_completos).dropna()
        k[2].metric(f"Promedio por año ({len(completos)} años completos)",
                    millones(completos.mean()) if len(completos) else "—")
        v_sel, v_comp = suma(df, acum), suma(df, acum_ant)
        k[3].metric(f"Año en curso {etq_acum}", millones(v_sel),
                    f"{porcentaje(variacion(v_sel, v_comp))} vs {etq_acum_ant}", delta_color="inverse")
    elif anual:
        v_sel, v_comp = suma(df, acum), suma(df, acum_ant)
        k[0].metric(f"Gasto {etq_acum}", millones(v_sel),
                    f"{porcentaje(variacion(v_sel, v_comp))} vs {etq_acum_ant}", delta_color="inverse")
        k[1].metric(f"Mismo periodo {etq_acum_ant}", millones(v_comp))
        prom, prom_ant = v_sel / len(acum), v_comp / len(acum)
        k[2].metric(f"Promedio mensual {anio}", millones(prom),
                    f"{porcentaje(variacion(prom, prom_ant))} vs promedio {anio - 1}", delta_color="inverse")
        if num_mes < 12:
            k[3].metric(f"Año {anio - 1} completo", millones(suma(df, anio_ant_completo)))
        else:
            por_mes = df[df["periodo"].isin(acum)].groupby("periodo")["valor"].sum()
            k[3].metric(f"Mes de mayor gasto ({etiqueta(por_mes.idxmax())})", millones(por_mes.max()))
    else:
        v_mes, v_ant, v_aa = suma(df, [mes]), suma(df, [mes_ant]), suma(df, [mes_anio_ant])
        v_acum, v_acum_ant = suma(df, acum), suma(df, acum_ant)
        prom12 = suma(df, ult12) / 12
        k[0].metric("Gasto del mes", millones(v_mes),
                    f"{porcentaje(variacion(v_mes, v_ant))} vs {etiqueta(mes_ant)}", delta_color="inverse")
        k[1].metric(f"Mismo mes año anterior ({etiqueta(mes_anio_ant)})", millones(v_aa),
                    f"{porcentaje(variacion(v_mes, v_aa))} el mes actual", delta_color="inverse")
        k[2].metric(f"Acumulado {etq_acum}", millones(v_acum),
                    f"{porcentaje(variacion(v_acum, v_acum_ant))} vs mismo periodo {anio - 1}",
                    delta_color="inverse")
        k[3].metric("Promedio mensual últimos 12 meses", millones(prom12),
                    f"{porcentaje(variacion(v_mes, prom12))} el mes actual", delta_color="inverse")

    # ---- Gráfica: año completo = los 12 meses del año; mes = últimos 24 meses
    if anual:
        rango = [anio * 100 + m for m in range(1, 13)]
        titulo_g = f"Gasto mensual {anio} (millones)"
    else:
        rango = [mover(mes, -k) for k in range(23, -1, -1)]
        titulo_g = "Gasto mensual — últimos 24 meses (millones)"
    g = df[df["periodo"].isin(rango)]
    if vista == GRUPO:
        g = g.assign(serie=g["empresa"])
        orden, colores = list(C.EMPRESAS), C.COLOR_EMPRESA
    else:
        # Lo operativo se parte en mano de obra / otros costos; lo demás se ve como su propio bloque,
        # para que una compra a la empresa hermana o un pago de intereses no se confunda con la operación.
        g = g.assign(serie=g["bloque"])
        orden, colores = BLOQUES, COLOR_BLOQUE
    tabla_g = g.pivot_table(index="periodo", columns="serie", values="valor", aggfunc="sum").reindex(rango).fillna(0)
    tabla_g = tabla_g[[c for c in orden if c in tabla_g.columns]]
    fig = go.Figure()
    for col in tabla_g.columns:
        fig.add_bar(x=[etiqueta(p) for p in rango], y=tabla_g[col] / 1e6, name=col,
                    marker_color=colores.get(col, "#9a9893"),
                    hovertemplate="%{x}<br>" + col + ": %{y:,.1f} M<extra></extra>")
    fig.update_layout(barmode="stack", height=360, separators=",.", bargap=0.25, title=titulo_g,
                      legend=dict(orientation="h", y=1.12, x=0, traceorder="normal"), margin=dict(l=10, r=10, t=70, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="rgba(128,128,128,0.2)"))
    st.plotly_chart(fig, width="stretch")

    # ---- Mano de obra y otros costos
    st.subheader("Mano de obra y otros costos")
    mo = [x for x in BLOQUES if x.startswith("Mano de obra")]
    tb = tabla_comparativa(df, ["bloque"], orden=BLOQUES, subtotales={"Subtotal mano de obra": mo})
    mostrar_comparativa(tb, {"bloque": "Concepto"})
    st.caption("Mano de obra (nómina) = TIPO GASTO Nómina: jornales por actividad con prefijo AC_, KC_ o KV_ "
               "(app de campo). Mano de obra al contrato = terceros cuya actividad dice 'contrato' "
               "(ej. FC DS … Contrato Nomina Guadañador) o cuyo detalle/descripción dice 'mano de obra' "
               "(recolección, llenado de bolsa, pelado...); el transporte de personal va en otros costos. "
               "En Tabla mensual use los niveles 'Mano de obra / Otros' y 'Prefijo actividad (AC/KC/KV)'.")

    # ---- Tabla por CECO
    st.subheader("Por centro de costo")
    llaves = ["empresa", "ceco"] if vista == GRUPO else ["ceco"]
    mostrar_comparativa(tabla_comparativa(df, llaves), {"empresa": "Empresa", "ceco": "CECO"})

    # ---- Rubros que más se movieron
    llaves_r = ["empresa", "ceco", "rubro"]
    if anual:
        st.subheader(f"Rubros que más cambiaron: {etq_acum} frente a {etq_acum_ant}")
        r_a = df[df["periodo"].isin(acum)].groupby(llaves_r)["valor"].sum()
        r_b = df[df["periodo"].isin(acum_ant)].groupby(llaves_r)["valor"].sum()
        nombres_r = [etq_acum, etq_acum_ant]
    else:
        st.subheader(f"Rubros que más se alejaron de su promedio de 12 meses en {etiqueta(mes)}")
        r_a = df[df["periodo"] == mes].groupby(llaves_r)["valor"].sum()
        r_b = df[df["periodo"].isin(ult12)].groupby(llaves_r)["valor"].sum() / 12
        nombres_r = [etiqueta(mes), "Promedio 12 meses"]
    r = pd.concat([r_a.rename("a"), r_b.rename("b")], axis=1).fillna(0)
    r["Diferencia"] = r["a"] - r["b"]
    r = r.reindex(r["Diferencia"].abs().sort_values(ascending=False).index).head(10).reset_index()
    r.columns = ["Empresa", "CECO", "Rubro"] + nombres_r + ["Diferencia"]
    if vista != GRUPO:
        r = r.drop(columns="Empresa")
    st.dataframe(r.style.format(pesos, subset=nombres_r + ["Diferencia"]), hide_index=True, width="stretch")


# ===============================================================
# 5. PESTAÑA TABLA MENSUAL (como la tabla dinámica de Excel)
# ===============================================================
NIVELES = {"Mano de obra / Otros": "bloque", "Prefijo actividad (AC/KC/KV)": "prefijo", "CECO": "ceco", "Rubro": "rubro", "Detalle": "detalle", "Ubicación": "ubicacion",
           "Actividad / Notas": "actividad", "Tercero": "tercero", "Descripción": "descripcion"}

with pest[1]:
    # Tabla mensual con el mismo formato del costo unitario: se baja CECO › Rubro › Actividad › Ubicación
    st.markdown("<div style='display:flex;align-items:baseline;gap:0.8rem;flex-wrap:wrap;margin:0.2rem 0 0.1rem'>"
                "<span style='font-size:1.35rem;font-weight:700;color:#111827'>Tabla mensual</span>"
                "<span style='font-size:0.8rem;color:#6B7280'>gasto por mes en millones de pesos · el color marca los "
                "meses de mayor gasto de cada fila</span></div>", unsafe_allow_html=True)
    tm = df.copy()
    tm["ubic"] = tm["ubicacion"].fillna("").astype(str).str.strip()
    if "planta" in tm.columns:        # KAHAI no llena Ubicación: el lote está en PLANTA
        tm["ubic"] = tm["ubic"].where(tm["ubic"] != "", tm["planta"].fillna("").astype(str).str.strip())
    for c_ in ["ceco", "rubro", "actividad", "detalle", "tercero", "descripcion", "bloque"]:
        if c_ in tm.columns:
            tm[c_] = tm[c_].fillna("").astype(str).str.strip().replace("", "(sin dato)")
    tm["ubic"] = tm["ubic"].replace("", "(sin dato)")
    NIV_TM = ([("Empresa", "empresa")] if vista == GRUPO else []) + \
        [("CECO", "ceco"), ("Rubro", "rubro"), ("Actividad", "actividad"), ("Ubicación / Lote", "ubic")]
    cols_t = st.columns([1] * len(NIV_TM) + [1.6])
    base_t, elegidos_t = tm, []
    for i, (nom, campo) in enumerate(NIV_TM):
        libre = len(elegidos_t) < i
        ops = sorted(base_t[campo].unique().tolist()) if not libre else []
        val = cols_t[i].selectbox(nom, ["Todos"] + ops, key=f"tm_{'_'.join(elegidos_t)}_{campo}", disabled=libre,
                                  help="Elija el nivel de arriba primero" if libre else None)
        if val != "Todos" and not libre:
            base_t = base_t[base_t[campo] == val]
            elegidos_t.append(val)
    desde, hasta = cols_t[-1].select_slider(
        "Meses", options=periodos, format_func=etiqueta,
        value=((max(periodos[0], mover(mes, -11)), mes) if todos else (seleccion[0], mes) if anual
               else (max(periodos[0], mover(mes, -11)), mes)))
    sig = NIV_TM[len(elegidos_t)] if len(elegidos_t) < len(NIV_TM) else ("Descripción", "descripcion")
    ABRIR = {"Siguiente nivel": sig, "Lote / ubicación": ("Ubicación / Lote", "ubic"), "Detalle": ("Detalle", "detalle"),
             "Tercero": ("Tercero", "tercero"), "Mano de obra / otros": ("Mano de obra / otros", "bloque")}
    r1, r2 = st.columns([2.2, 3], vertical_alignment="center")
    abrir = r2.segmented_control("Abrir por", list(ABRIR), default="Siguiente nivel", key="tm_abrir",
                                 label_visibility="collapsed") or "Siguiente nivel"
    ver_t, por_t = ABRIR[abrir]
    ruta_t = " › ".join([titulo_vista] + elegidos_t)
    r1.markdown(f'<div style="font-size:0.82rem;color:#374151">📍 <b>{ruta_t}</b> &nbsp;·&nbsp; filas por '
                f'<b>{ver_t}</b></div>', unsafe_allow_html=True)

    meses_rango = [p for p in periodos if desde <= p <= hasta]
    d_t = base_t[base_t["periodo"].isin(meses_rango)]
    if d_t.empty:
        st.info("Sin gasto con estos filtros.")
    else:
        piv = d_t.pivot_table(index=por_t, columns="periodo", values="valor", aggfunc="sum", fill_value=0)
        piv = piv.reindex(columns=meses_rango, fill_value=0)
        piv["Total"] = piv.sum(axis=1)
        piv = piv.sort_values("Total", ascending=False)
        n_max = 15
        if len(piv) > n_max + 1 and not st.session_state.get("tm_todas"):
            resto = piv.iloc[n_max:]
            piv = pd.concat([piv.iloc[:n_max], resto.sum().to_frame(f"Otras ({len(resto)})").T])
        total_t = piv.sum()

        def m_(v):
            if not v:
                return "—"
            return f"{v / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def fila_html(nombre, fila, clase=""):
            vals = [fila[p_] for p_ in meses_rango]
            tope = max([abs(v_) for v_ in vals] + [1])
            celdas = ""
            for v_ in vals:
                a_ = 0 if clase or not v_ else 0.06 + 0.30 * abs(v_) / tope     # intensidad según el mes más alto
                estilo = f" style='background:rgba(27,94,32,{a_:.2f})'" if a_ else ""
                celdas += f"<td{estilo}>{m_(v_)}</td>"
            pct = fila["Total"] / total_t["Total"] if total_t["Total"] else 0
            pct_txt = f"{pct:.1%}".replace(".", ",")
            return (f"<tr{clase}><td class='izq'>{__import__('html').escape(str(nombre))}</td>{celdas}"
                    f"<td class='tt'>{m_(fila['Total'])}</td><td class='pc'>{pct_txt}</td></tr>")

        cab_t = ("<tr><th class='izq'>" + ver_t + "</th>" + "".join(f"<th>{etiqueta(p_)}</th>" for p_ in meses_rango)
                 + "<th>Total</th><th>%</th></tr>")
        filas_t = [fila_html(n_, f_) for n_, f_ in piv.iterrows()]
        filas_t.append(fila_html("TOTAL", total_t, " class='tot'"))
        html_t = "".join(filas_t)
        st.markdown("""<style>
          .ttm { overflow-x:auto; border:1px solid #E5E7EB; border-radius:10px; margin-top:0.3rem; }
          .ttm table { border-collapse:collapse; width:100%; font-size:0.8rem; font-variant-numeric:tabular-nums; }
          .ttm th { background:#F6F8F5; color:#374151; font-weight:600; text-align:right; padding:0.32rem 0.45rem;
                    border-bottom:1px solid #E1E8DF; white-space:nowrap; }
          .ttm td { text-align:right; padding:0.24rem 0.45rem; border-bottom:1px solid #F0F2F0; white-space:nowrap; }
          .ttm .izq { text-align:left; white-space:normal; min-width:130px; max-width:220px; line-height:1.2; }
          .ttm td.tt { font-weight:700; background:#FAFBFA; border-left:1px solid #E5E7EB; }
          .ttm td.pc { color:#6B7280; }
          .ttm tr.tot td { font-weight:800; border-top:2px solid #CBD5CC; background:#F3F6F3; }
        </style>""", unsafe_allow_html=True)
        st.markdown(f"<div class='ttm'><table><thead>{cab_t}</thead><tbody>{html_t}</tbody></table></div>",
                    unsafe_allow_html=True)
        n_filas = d_t[por_t].nunique()
        if n_filas > n_max + 1:
            st.toggle(f"Ver todas las filas ({n_filas})", key="tm_todas",
                      help="Por defecto se muestran las 15 de mayor gasto y el resto se junta en 'Otras'.")
        st.caption(f"Millones de pesos · {etiqueta(meses_rango[0])} a {etiqueta(meses_rango[-1])} · % = parte del total "
                   "del periodo. Con 'Abrir por' se ve la misma selección por lote, detalle, tercero o mano de obra.")

        def excel_tabla(d=d_t):
            campos_x = [c_ for _, c_ in NIV_TM] + ["detalle", "descripcion"]
            px = d.pivot_table(index=campos_x, columns="periodo", values="valor", aggfunc="sum", fill_value=0)
            px.columns = [etiqueta(c_) for c_ in px.columns]
            px["Total"] = px.sum(axis=1)
            salida = io.BytesIO()
            px.reset_index().rename(columns={c_: n_ for n_, c_ in NIV_TM}).to_excel(salida, index=False,
                                                                                   sheet_name="Tabla mensual")
            return salida.getvalue()
        # El Excel se arma solo al tocar el botón (y trae todo el detalle de la selección)
        st.download_button("Descargar en Excel (con todo el detalle)", excel_tabla,
                           file_name=f"Tabla_{vista.split()[0]}_{desde}_{hasta}.xlsx")


# ===============================================================
# 5b. PESTAÑA COSTO UNITARIO (parte agrícola: AGROCACAY)
# ===============================================================
def unitario(v):
    """Costo unitario con 2 decimales: 1.234,56"""
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data(show_spinner="Cargando costo unitario...")
def cargar_cu(version_datos):
    cu = F.leer_tabla("agrocacay_costo_unitario")
    ultimo = F.leer_tabla("calculos_cu", "ORDER BY fecha DESC").head(1)
    if not cu.empty:
        t = cu["tipo_gasto"].fillna("").str.upper()
        cu["tipo"] = np.where(t.str.startswith("NOMINA"), "Nómina",
                              "Terceros")   # todo lo que no es nómina
        cu["valor"] = cu["valor"].fillna(0)
        cu["bloque"] = clasificar_bloque(cu)
        for col in ["ceco", "rubro", "actividad", "ubicacion", "regla_divisor", "detalle", "descripcion"]:
            cu[col] = cu[col].fillna("(sin dato)")
        # Mismo nombre con distinta mayúscula = lo mismo: se queda la forma de escribir más usada
        for col in ["rubro", "detalle", "descripcion"]:
            t_ = cu[col].astype(str).str.strip()
            forma = t_.groupby(t_.str.lower()).agg(lambda x: x.value_counts().index[0])
            cu[col] = t_.str.lower().map(forma)
    return cu, ultimo


def ponderado(d, por, eje):
    """Medida DAX 'Costo Unitario Ponderado' de Power BI (la misma de la app de campo):
       grupos (mes, lote, regla): vDebito = suma débito; vDivisor = máx divisor; vCU = vDebito / vDivisor
       resultado = suma(vDebito × vCU) / suma(vDebito)
    El lote siempre queda en el grupo más fino porque el divisor depende del lote."""
    llaves = [c for c in [por, eje] if c]
    finas = llaves + [c for c in ["mes", "ubicacion", "regla_divisor"] if c not in llaves]
    # Filas cuyo divisor es de TODO el año (Poscosecha y gastos sin lote: kg del año de la finca; lote sin kg en el
    # mes: kg del lote en el año) no se parten por mes ni por ubicación: si se parten, el promedio sale por debajo
    # del costo real por kg (ej. Poscosecha 2024: $1.004/kg real vs $186 partido por mes).
    if "origen_divisor" in d.columns:
        o = d["origen_divisor"].astype(str)
        finca, lote_a = o.str.contains("toda la finca"), o.str.contains("lote en el año")
        if finca.any() or lote_a.any():
            d = d.copy()
            if "mes" not in llaves:
                d.loc[finca | lote_a, "mes"] = "AÑO"
            if "ubicacion" not in llaves:
                d.loc[finca, "ubicacion"] = "TODA LA FINCA"
    g = d.groupby(finas, dropna=False).agg(
        vDebito=("valor", "sum"), vDivisor=("divisor", "max")).reset_index()
    g["vCU"] = np.where((g["vDivisor"] == 0) | g["vDivisor"].isna(), np.nan, g["vDebito"] / g["vDivisor"])
    g["prod"] = g["vDebito"] * g["vCU"]
    # Lo que no tiene divisor (ej. Siembra de un año sin sitios sembrados) no entra al promedio:
    # así queda EN BLANCO y no como $0.
    g["deb_ok"] = g["vDebito"].where(g["vCU"].notna())
    if not llaves:
        tot = g["deb_ok"].sum()
        return g["prod"].sum() / tot if tot else None
    r = g.groupby(llaves).agg(prod=("prod", "sum"), deb=("deb_ok", "sum"))
    return (r["prod"] / r["deb"].replace(0, np.nan)).rename("cu")


def orden_lote(nombre):
    """L1, L2 ... L25, luego ML1 ... (orden natural, no alfabético)."""
    import re
    m = re.match(r"([A-Za-z]+)(\d+)$", str(nombre))
    return (m.group(1), int(m.group(2))) if m else (str(nombre), 0)


def componente_gerencial(d):
    """Componentes que entiende gerencia: la mano de obra se separa y 'Otros costos' se abre
    en sus 3 detalles más grandes (insumos, herramientas, etc.); lo demás queda en 'Otros'."""
    comp = d["bloque"].copy()
    otros = d["bloque"] == "Otros costos"
    top = d[otros].groupby("detalle")["valor"].sum().nlargest(3).index
    comp[otros] = np.where(d.loc[otros, "detalle"].isin(top), d.loc[otros, "detalle"], "Otros (resto)")
    return comp


def mostrar_procesamiento_kahai():
    """Costo por kg de la planta de KAHAI: costo del año ÷ kg del divisor (Graficas\\PRODUCCION_KAHAI.xlsx)."""
    import html as _h
    div = F.leer_tabla("kahai_divisores")
    reg = F.leer_tabla("kahai_reglas_proc", "ORDER BY orden")
    st.subheader("🏭 Procesamiento KAHAI · costo por kg")
    if div.empty or reg.empty:
        st.info("Faltan los divisores de procesamiento. Llene Graficas\\PRODUCCION_KAHAI.xlsx y corra:  "
                "python motor_procesamiento_kahai.py")
        return
    k = datos[(datos["empresa"] == "KAHAI") & datos["naturaleza"].isin(naturalezas) & datos["tipo"].isin(tipos)].copy()
    k["anio"] = k["periodo"] // 100
    k["bloque"] = clasificar_bloque(k)
    anios_p = sorted(div["anio"].astype(int).unique())
    kg = div.assign(anio=div["anio"].astype(int)).set_index(["divisor", "anio"])["kg"]
    ult_mes_k = int(k.loc[k["anio"] == anios_p[-1], "periodo"].max() % 100) if (k["anio"] == anios_p[-1]).any() else 12

    def coincide(serie, patron):
        return pd.Series(True, index=serie.index) if patron.strip() == "*" else \
            serie.fillna("").str.strip().str.lower() == patron.strip().lower()

    import unicodedata

    def sin_tildes(t):
        return "".join(ch for ch in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(ch) != "Mn")

    def cumple_descripcion(serie, patron):
        """'*' = todas; 'texto' = la descripción contiene ese texto; '!texto' = NO lo contiene."""
        patron = str(patron if patron is not None and str(patron) != "nan" else "*").strip()
        if patron in ("", "*"):
            return pd.Series(True, index=serie.index)
        negar = patron.startswith("!")
        contiene = serie.fillna("").map(sin_tildes).str.contains(sin_tildes(patron.lstrip("!").strip()), regex=False)
        return ~contiene if negar else contiene

    lineas = []
    for _, r in reg.iterrows():
        m = coincide(k["ceco"], r["ceco"]) & coincide(k["rubro"], r["rubro"]) & coincide(k["detalle"], r["detalle"]) & \
            cumple_descripcion(k["descripcion"], r.get("descripcion", "*"))
        sub = k[m]
        costo = sub.groupby("anio")["valor"].sum()
        mo = sub[sub["bloque"].isin(["Mano de obra (nómina)", "Mano de obra al contrato"])].groupby("anio")["valor"].sum()
        previa = next((l for l in lineas if (l["seccion"], l["linea"], l["divisor"]) ==
                       (r["seccion"], r["linea"], r["divisor"])), None)
        if previa:      # varias reglas con el mismo nombre de línea se suman (ej. Mantenimiento)
            previa["costo"] = previa["costo"].add(costo, fill_value=0)
            previa["mo"] = previa["mo"].add(mo, fill_value=0)
        else:
            lineas.append({"seccion": r["seccion"], "linea": r["linea"], "divisor": r["divisor"],
                           "costo": costo, "mo": mo})

    def cpk(costo, divisor, a):
        kg_a = kg.get((divisor, a))
        c = costo.get(a, 0)
        return (c / kg_a) if kg_a else None, c, kg_a

    # ---- Tarjetas: el año elegido arriba (o el último con divisores)
    a_ref = anio if anio in anios_p else anios_p[-1]
    def lineas_total(sec):
        """Líneas que se suman en el total de la sección: en Aceite todas las etapas; en las demás, las que
        comparten el divisor de la primera (ej. Poscosecha: todo lo que va ÷ kg de concha, no Nuez obtenida)."""
        ls = [l for l in lineas if l["seccion"] == sec]
        if not ls or sec.lower().startswith("aceite"):
            return ls
        return [l for l in ls if l["divisor"] == ls[0]["divisor"]]

    def nombre_total(sec):
        ls = lineas_total(sec)
        if sec.lower().startswith("aceite"):
            return "Costo kg aceite (suma)"
        return {"CONCHA PROCESADA": "Costo kg concha (suma)"}.get(ls[0]["divisor"], f"Costo kg {ls[0]['divisor'].lower()} (suma)")

    def total_seccion(sec, a):
        vals = [cpk(l["costo"], l["divisor"], a)[0] for l in lineas_total(sec)]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None
    def primera(sec, a):
        l = next((l for l in lineas if l["seccion"] == sec), None)
        return cpk(l["costo"], l["divisor"], a)[0] if l else None
    t1, t2, t3, t4 = st.columns(4)
    for col, nombre, f in [(t1, "Poscosecha (kg concha)", lambda a: total_seccion("Poscosecha", a)),
                           (t2, "Nuez pelada", lambda a: primera("Nuez", a)),
                           (t3, "Aceite (suma de etapas)", lambda a: total_seccion("Aceite", a))]:
        v, v0 = f(a_ref), f(a_ref - 1)
        col.metric(f"{nombre} {a_ref} · $/kg", unitario(v),
                   f"{porcentaje(variacion(v, v0))} vs {a_ref - 1}" if v and v0 else None, delta_color="inverse")
    t4.metric(f"Kg aceite filtrado {a_ref}", pesos(kg.get(("FILTRADO", a_ref))))
    if a_ref == anios_p[-1] and ult_mes_k < 12:
        st.caption(f"⚠️ El costo de {a_ref} va hasta {NOMBRE_MES[ult_mes_k]}; revise que los kg de {a_ref} "
                   "correspondan al mismo tramo.")

    # ---- Tabla: $/kg grande y, debajo, costo ÷ kg
    def etq_a(a):
        return f"{a} (Ene–{NOMBRE_MES[ult_mes_k]})" if a == anios_p[-1] and ult_mes_k < 12 else str(a)
    cab = "<tr><th class='izq'>Línea</th><th class='izq'>Divisor</th>" + "".join(
        f"<th class='anio'>{etq_a(a)}</th>" for a in anios_p) + "</tr>"
    filas, sec_actual = [], None
    for l in lineas:
        if l["seccion"] != sec_actual:
            sec_actual = l["seccion"]
            filas.append(f"<tr class='sec'><td colspan='{2 + len(anios_p)}'>{_h.escape(sec_actual)}</td></tr>")
        celdas = []
        for a in anios_p:
            v, c, kg_a = cpk(l["costo"], l["divisor"], a)
            det = f"{millones(c)} ÷ {pesos(kg_a)} kg" if kg_a else "sin kg"
            celdas.append(f"<td>{pesos(v) if v is not None else '—'}<div class='det'>{det}</div></td>")
        filas.append(f"<tr><td class='izq'>{_h.escape(l['linea'])}</td><td class='izq div'>{_h.escape(l['divisor'])}</td>"
                     + "".join(celdas) + "</tr>")
        if l is lineas_total(sec_actual)[-1] and len(lineas_total(sec_actual)) > 1:   # total tras su última línea
            tot = [total_seccion(sec_actual, a) for a in anios_p]
            filas.append(f"<tr class='tot'><td class='izq' colspan='2'>{nombre_total(sec_actual)}</td>"
                         + "".join(f"<td>{pesos(v) if v else '—'}</td>" for v in tot) + "</tr>")
    st.markdown("""<style>
      .tpk { overflow-x:auto; border:1px solid #E5E7EB; border-radius:10px; }
      .tpk table { border-collapse:collapse; width:100%; font-size:0.86rem; font-variant-numeric:tabular-nums; }
      .tpk th { background:#F6F8F5; color:#374151; font-weight:600; padding:0.5rem 0.6rem; border-bottom:1px solid #E1E8DF;
                white-space:nowrap; }
      .tpk th.anio { text-align:center; } .tpk .izq { text-align:left; }
      .tpk td { text-align:right; padding:0.4rem 0.6rem; border-bottom:1px solid #F0F2F0; white-space:nowrap;
                font-weight:600; color:#111827; }
      .tpk td.izq { font-weight:500; } .tpk td.div { color:#6B7280; font-size:0.78rem; font-weight:400; }
      .tpk .det { font-size:0.72rem; font-weight:400; color:#6B7280; }
      .tpk tr.sec td { text-align:left; background:#EEF4EE; color:#1B5E20; font-weight:700; padding:0.35rem 0.6rem; }
      .tpk tr.tot td { border-top:2px solid #CBD5CC; background:#FAFBFA; font-weight:800; }
    </style>""", unsafe_allow_html=True)
    st.markdown(f"<div class='tpk'><table><thead>{cab}</thead><tbody>{''.join(filas)}</tbody></table></div>",
                unsafe_allow_html=True)
    st.caption("Pesos por kg = costo del año en CONSOLIDADO_KAHAI (aprobado, con los filtros de arriba) ÷ kg del divisor "
               "(Graficas\\PRODUCCION_KAHAI.xlsx). Debajo de cada valor: costo ÷ kg. La energía no está en el "
               "consolidado, así que no se incluye.")

    # ---- Gráfica del costo por kg por año (una sección a la vez)
    secciones = list(dict.fromkeys(l["seccion"] for l in lineas))
    sec_g = st.segmented_control("Graficar", secciones, default=secciones[-1], key="kpk_sec") or secciones[-1]
    apilar = len(lineas_total(sec_g)) > 1          # las líneas que se suman van apiladas, con el total encima
    lin_g = lineas_total(sec_g) if apilar else [l for l in lineas if l["seccion"] == sec_g]
    paleta = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6", "#008300", "#e34948"]
    fig = go.Figure()
    for i, l in enumerate(lin_g):
        ys = [cpk(l["costo"], l["divisor"], a)[0] for a in anios_p]
        fig.add_bar(x=[etq_a(a) for a in anios_p], y=ys, name=l["linea"], marker_color=paleta[i % len(paleta)],
                    hovertemplate=l["linea"] + "<br>%{x}: $%{y:,.0f}/kg<extra></extra>")
    if apilar:
        tot = [total_seccion(sec_g, a) for a in anios_p]
        fig.add_scatter(x=[etq_a(a) for a in anios_p], y=tot, mode="text", showlegend=False, hoverinfo="skip",
                        text=[f"${pesos(v)}" if v else "" for v in tot], textposition="top center",
                        textfont=dict(size=12, color="#111827"))
    fig.update_layout(barmode="stack" if apilar else "group", height=360, separators=",.", bargap=0.3,
                      title=f"{sec_g} · pesos por kg" + (f" ({nombre_total(sec_g).replace('Costo ', '')})" if apilar else ""),
                      legend=dict(orientation="h", y=1.15, x=0, traceorder="normal"), margin=dict(l=10, r=10, t=70, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="rgba(128,128,128,0.2)", tickprefix="$"),
                      xaxis=dict(type="category"))
    st.plotly_chart(fig, width="stretch")

    with st.expander("👷 Mano de obra y otros costos por línea ($/kg)"):
        filas_mo = []
        for l in lineas:
            for nombre, serie in [("Mano de obra", l["mo"]), ("Otros costos", l["costo"].sub(l["mo"], fill_value=0))]:
                fila = {"Línea": l["linea"], "Parte": nombre}
                for a in anios_p:
                    kg_a = kg.get((l["divisor"], a))
                    fila[etq_a(a)] = pesos(serie.get(a, 0) / kg_a) if kg_a else "—"
                filas_mo.append(fila)
        st.dataframe(pd.DataFrame(filas_mo), hide_index=True, width="stretch")
        st.caption("Mano de obra = nómina (actividades KV_) + mano de obra al contrato. Otros = facturas de terceros "
                   "(insumos, servicios, empaques…).")

    mostrar_lotes_aceite(a_ref, kg)


def mostrar_lotes_aceite(a_ref, kg):
    """De la nuez al aceite: rendimiento por lote de aceite KNO (hoja LOTES_ACEITE de PRODUCCION_KAHAI.xlsx)."""
    import html as _h
    lt = F.leer_tabla("kahai_lotes_aceite", "ORDER BY orden")
    st.markdown("#### 🥜 De la nuez al aceite · rendimiento por lote de aceite (KNO)")
    if lt.empty:
        st.info("Falta la hoja LOTES_ACEITE en Graficas\\PRODUCCION_KAHAI.xlsx. Llénela y corra:  "
                "python motor_procesamiento_kahai.py")
        return
    for c in ["nuez_testa", "nuez_pelada", "blanca", "roja", "hongo", "nuez_aceite", "aceite"]:
        lt[c] = pd.to_numeric(lt[c], errors="coerce")
    lt["anio"] = lt["anio"].astype(int)

    def div_(a, b):
        return a / b if b and pd.notna(b) and pd.notna(a) and b > 0 else None

    def pct(v):
        return "" if v is None else f"{v * 100:.0f}%"

    def resumen(d):
        con_testa = d[d["nuez_testa"] > 0]              # los reprocesos (H, R) no traen nuez testa
        te, pe = con_testa["nuez_testa"].sum(), con_testa["nuez_pelada"].sum()
        return {"testa": d["nuez_testa"].sum(min_count=1), "pelada": d["nuez_pelada"].sum(min_count=1),
                "blanca": d["blanca"].sum(min_count=1), "roja": d["roja"].sum(min_count=1),
                "hongo": d["hongo"].sum(min_count=1), "nuez_aceite": d["nuez_aceite"].sum(min_count=1),
                "aceite": d["aceite"].sum(min_count=1), "p_pelado": div_(pe, te),
                "p_blanca": div_(d["blanca"].sum(), pe), "p_roja": div_(d["roja"].sum(), pe),
                "p_hongo": div_(d["hongo"].sum(), pe),
                "p_aceite": div_(d["aceite"].sum(), d["nuez_aceite"].sum()),
                "testa_x_kg": div_(te, d["aceite"].sum())}

    anios_l = sorted(lt["anio"].unique())
    res = {a: resumen(lt[lt["anio"] == a]) for a in anios_l}
    a_k = a_ref if a_ref in res else anios_l[-1]

    # ---- Tarjetas del año elegido
    c1, c2, c3, c4 = st.columns(4)
    for col, nombre, clave, inv in [(c1, "Pelado (pelada ÷ testa)", "p_pelado", False),
                                     (c2, "Nuez blanca (÷ pelada)", "p_blanca", False),
                                     (c3, "Rendimiento aceite (÷ nuez p/aceite)", "p_aceite", False),
                                     (c4, "Kg nuez testa por kg de aceite", "testa_x_kg", True)]:
        v, v0 = res[a_k][clave], res.get(a_k - 1, {}).get(clave)
        if clave == "testa_x_kg":
            txt = "—" if v is None else f"{v:,.1f}".replace(".", ",")
            delta = f"{v - v0:+.1f} kg vs {a_k - 1}".replace(".", ",") if v and v0 else None
        else:
            txt = pct(v) or "—"
            delta = f"{(v - v0) * 100:+.1f} pts vs {a_k - 1}".replace(".", ",") if v and v0 else None
        col.metric(f"{nombre} · {a_k}", txt, delta, delta_color="inverse" if inv else "normal")

    # ---- Tabla: kg grande y, debajo, el %
    def celda(v, p=None):
        if v is None or pd.isna(v):
            return "<td>—</td>"
        sub = f"<div class='det'>{pct(p)}</div>" if p is not None else ""
        return f"<td>{pesos(v)}{sub}</td>"

    def fila_html(nombre, r, clase=""):
        return (f"<tr{clase}><td class='izq'>{_h.escape(str(nombre))}</td>" + celda(r["testa"])
                + celda(r["pelada"], r["p_pelado"]) + celda(r["blanca"], r["p_blanca"]) + celda(r["roja"], r["p_roja"])
                + celda(r["hongo"], r["p_hongo"]) + celda(r["nuez_aceite"]) + celda(r["aceite"], r["p_aceite"]) + "</tr>")

    cab = ("<tr><th class='izq'>Lote de aceite</th><th>Nuez testa</th><th>Nuez pelada<div class='det'>% pelado</div></th>"
           "<th>Blanca<div class='det'>% de pelada</div></th><th>Roja<div class='det'>% de pelada</div></th>"
           "<th>Hongo<div class='det'>% de pelada</div></th><th>Nuez para aceite</th>"
           "<th>Aceite<div class='det'>% rendimiento</div></th></tr>")
    filas = []
    for a in sorted(anios_l, reverse=True):
        filas.append(f"<tr class='sec'><td colspan='8'>{a}</td></tr>")
        for _, r in lt[lt["anio"] == a].iterrows():
            filas.append(fila_html(r["lote"], resumen(lt[lt["orden"] == r["orden"]])))
        filas.append(fila_html(f"Total {a}", res[a], " class='tot'"))
    # ---- Balance de masa: de cada 100 kg de nuez testa, ¿cuánto termina en aceite y a dónde va el resto?
    def balance(a):
        d = lt[lt["anio"] == a]
        T = d.loc[d["nuez_testa"] > 0, "nuez_testa"].sum()
        P = d.loc[d["nuez_testa"] > 0, "nuez_pelada"].sum()
        N, A = d["nuez_aceite"].sum(), d["aceite"].sum()
        if not T:
            return None
        par = not (((d["nuez_aceite"] > 0) & d["aceite"].isna()).any() or (d["nuez_aceite"].isna() & (d["aceite"] > 0)).any())
        return {"T": T, "P": P, "N": N, "A": A, "par": par,
                "aceite": A / T * 100, "torta": max(N - A, 0) / T * 100,
                "apartada": max(P - N, 0) / T * 100, "testa": max(T - P, 0) / T * 100,
                "pelada": P / T * 100, "nuez_ac": N / T * 100}
    bal = {a: balance(a) for a in anios_l if balance(a)}
    ACEITE, TORTA, APARTADA, TESTA = "#E8A33D", "#C9B79C", "#9CA3AF", "#7B5B45"
    capa = dict(separators=",.", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")

    st.markdown("##### De cada 100 kg de nuez testa…")
    izq, der = st.columns([1, 1.35], gap="large")
    with izq:
        anios_b = list(bal)
        a_f = st.segmented_control("Año", anios_b, default=a_k if a_k in bal else anios_b[-1], key="kla_anio",
                                   format_func=str, label_visibility="collapsed") or anios_b[-1]
        b = bal[a_f]
        fig = go.Figure(go.Funnel(
            y=["Nuez testa", "Nuez pelada", "Nuez para aceite", "Aceite"],
            x=[100, b["pelada"], b["nuez_ac"], b["aceite"]],
            customdata=[b["T"], b["P"], b["N"], b["A"]],
            texttemplate="<b>%{value:.0f} kg</b><br>%{percentPrevious:.0%} del paso anterior",
            textposition=["inside", "inside", "inside", "outside"],
            textfont=dict(size=13, color=["white", "white", "white", "#7A4F00"]),
            marker=dict(color=["#7B5B45", "#A07850", "#C99A55", ACEITE]),
            connector=dict(fillcolor="rgba(201,154,85,0.18)", line=dict(width=0)),
            hovertemplate="%{y}: %{customdata:,.0f} kg reales<extra></extra>"))
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                          yaxis=dict(tickfont=dict(size=13)), **capa)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.markdown(f"<div style='text-align:center;margin-top:-6px;font-size:0.95rem'>En <b>{a_f}</b> se necesitaron "
                    f"<b>{b['T'] / b['A']:,.1f} kg</b> de nuez testa por cada kg de aceite".replace(".", ",")
                    + ("" if b["par"] else " <span style='color:#9A5B00'>(*año con aceite y nuez en lotes distintos)</span>")
                    + "</div>", unsafe_allow_html=True)
    with der:
        anios_o = list(reversed(list(bal)))              # el más reciente arriba
        etq = [f"{a}" + ("" if bal[a]["par"] else " *") for a in anios_o]
        fig = go.Figure()
        for clave, nombre, color, txt_color in [("aceite", "Aceite", ACEITE, "#3B2A00"),
                                                 ("torta", "Torta (lo que queda al extraer)", TORTA, "#3B2F22"),
                                                 ("apartada", "Nuez roja/hongo no usada", APARTADA, "white"),
                                                 ("testa", "Testa retirada al pelar", TESTA, "white")]:
            vals = [bal[a][clave] for a in anios_o]
            fig.add_bar(y=etq, x=vals, name=nombre, orientation="h", marker_color=color,
                        text=[f"{v:.0f}" if v >= 4 else "" for v in vals], textposition="inside",
                        insidetextanchor="middle", textfont=dict(color=txt_color, size=13),
                        hovertemplate=nombre + " · %{y}: %{x:.1f} kg de cada 100<extra></extra>")
        fig.update_layout(barmode="stack", height=360, bargap=0.28, margin=dict(l=10, r=10, t=40, b=10),
                          title=dict(text="¿A dónde va cada 100 kg de nuez testa?", font=dict(size=15)),
                          legend=dict(orientation="h", y=-0.08, x=0, traceorder="normal"),
                          xaxis=dict(range=[0, 100], ticksuffix=" kg", gridcolor="rgba(128,128,128,0.15)"),
                          yaxis=dict(type="category", tickfont=dict(size=13)), **capa)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        if not all(bal[a]["par"] for a in bal):
            st.caption("\\* Año con aceite y nuez en lotes distintos (ej. KNO034 sin aceite y KNO035 solo aceite): "
                       "su reparto no es comparable.")

    # ---- Lectura automática del año elegido
    a_ant = max([a for a in bal if a < a_f and bal[a]["par"]], default=None)   # se salta años no comparables (2024)
    if a_ant:
        b0 = bal[a_ant]
        def cambio(v, v0, nombre):
            d = v - v0
            return f"{nombre} **{v:.0f} kg** ({'+' if d >= 0 else ''}{d:.0f} vs {a_ant})"
        st.markdown("📌 **Lectura " + str(a_f) + ":** de cada 100 kg de nuez testa salieron " + cambio(b["aceite"], b0["aceite"], "aceite")
                    + "; se apartaron " + cambio(b["apartada"], b0["apartada"], "nuez roja/hongo")
                    + " y la testa retirada fue " + cambio(b["testa"], b0["testa"], "") .strip() + ".")

    # ---- Rendimiento de aceite de cada lote KNO frente al promedio
    lt_g = lt.sort_values("orden").copy()
    lt_g["r"] = [div_(a_, n_) for a_, n_ in zip(lt_g["aceite"], lt_g["nuez_aceite"])]
    rs = [None if pd.isna(r) else float(r) for r in lt_g["r"]]      # pandas guarda None como NaN
    con_par = lt_g[lt_g["r"].notna()]
    prom = div_(con_par["aceite"].sum(), con_par["nuez_aceite"].sum())

    def color_r(r):
        if r is None:
            return "#D1D5DB"
        return "#1baf7a" if r >= prom - 0.02 else ("#eda100" if r >= prom - 0.07 else "#e34948")
    xs = [lt_g["anio"].astype(str).tolist(), lt_g["lote"].astype(str).tolist()]
    ys = [r if r is not None else 0.012 for r in rs]   # sin pareja nuez-aceite: barrita gris con aviso
    textos = []
    for r, na, ac in zip(rs, lt_g["nuez_aceite"], lt_g["aceite"]):
        textos.append(f"<b>{r * 100:.0f}%</b>" if r is not None else ("sin aceite" if pd.notna(na) else "solo aceite"))
    fig = go.Figure()
    fig.add_bar(x=xs, y=ys, marker_color=[color_r(r) for r in rs], text=textos, textposition="outside",
                textfont=dict(size=12), cliponaxis=False,
                customdata=list(zip(lt_g["nuez_aceite"].fillna(0), lt_g["aceite"].fillna(0))),
                hovertemplate="%{x}<br>Nuez para aceite: %{customdata[0]:,.0f} kg<br>Aceite: %{customdata[1]:,.0f} kg"
                              "<br>Rendimiento: %{y:.1%}<extra></extra>")
    if prom:
        fig.add_hline(y=prom, line=dict(color="#374151", dash="dash", width=1.5), layer="below")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10), showlegend=False, bargap=0.35,
                      title=dict(text=f"Rendimiento de aceite por lote KNO (aceite ÷ nuez para aceite) · línea punteada = "
                                      f"promedio {prom * 100:.0f}%" if prom else "Rendimiento de aceite por lote KNO",
                                 font=dict(size=15)),
                      yaxis=dict(tickformat=".0%", range=[0, max(ys + [prom or 0]) * 1.22], layer="below traces",
                                 gridcolor="rgba(128,128,128,0.15)"), **capa)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("🟢 en o sobre el promedio · 🟠 hasta 7 puntos por debajo · 🔴 más de 7 puntos por debajo. "
               "Los lotes que terminan en H o R se hicieron con nuez de hongo o roja.")

    with st.expander("📋 Tabla por lote de aceite (kg y %)"):
        st.markdown(f"<div class='tpk'><table><thead>{cab}</thead><tbody>{''.join(filas)}</tbody></table></div>",
                    unsafe_allow_html=True)

    # ---- Avisos: lotes incompletos y cuadre con la hoja DIVISORES
    avisos = []
    sin_ac = lt[(lt["nuez_aceite"] > 0) & lt["aceite"].isna()]["lote"].tolist()
    solo_ac = lt[lt["nuez_aceite"].isna() & (lt["aceite"] > 0)]["lote"].tolist()
    if sin_ac:
        avisos.append(f"Lotes de aceite con nuez pero sin aceite registrado: {', '.join(sin_ac)}")
    if solo_ac:
        avisos.append(f"Lotes de aceite con aceite pero sin nuez: {', '.join(solo_ac)} (el % del año mezcla los dos)")
    for a in anios_l:
        for divisor, campo, nombre in [("NUEZ PELADA", "pelada", "nuez pelada"), ("EXTRACCIÓN", "aceite", "aceite")]:
            k_div, k_lot = kg.get((divisor, a)), res[a][campo]
            if k_div and k_lot and abs(k_lot / k_div - 1) > 0.01:
                avisos.append(f"{a}: {nombre} de los lotes {pesos(k_lot)} kg ≠ hoja DIVISORES ({divisor}) "
                              f"{pesos(k_div)} kg")
    st.caption("Fuente: hoja LOTES_ACEITE de Graficas\\PRODUCCION_KAHAI.xlsx. Cada KNO es un lote de aceite; los "
               "que terminan en H (hongo) o R (roja) se hicieron con esa nuez. Total del año: % pelado solo con lotes que traen nuez testa.")
    if avisos:
        st.caption("⚠️ Para revisar: " + " · ".join(avisos))


LOTES_KAHAI = {"CUMARAL": "CUMARAL (HM + MME)", "RESTREPO": "RESTREPO (MPB)", "PTO GAITAN": "PTO GAITAN",
               "VILLA/CIO": "General (Villavicencio)"}


def mostrar_cultivo_kahai():
    """Cultivo de KAHAI por lote (columna PLANTA del consolidado): gasto por lote y por rubro, año contra año.
    Si la hoja CULTIVO_LOTES de PRODUCCION_KAHAI.xlsx trae árboles y kg por lote, muestra también $/árbol y $/kg."""
    import html as _h
    import re as _re
    st.subheader("🌱 Cultivo KAHAI por lote")
    k = datos[(datos["empresa"] == "KAHAI") & datos["naturaleza"].isin(naturalezas) & datos["tipo"].isin(tipos)
              & (datos["ceco"].str.upper() == "CULTIVO")].copy()
    if k.empty:
        st.info("No hay gasto de cultivo de KAHAI con estos filtros.")
        return
    k["anio"] = k["periodo"] // 100
    k["lote"] = k["planta"].fillna("(sin lote)").astype(str).str.strip().str.upper()
    # Rubro sin el sufijo del lote (MIAR_HM y MIAR_MPB -> MIAR) para comparar lotes con el mismo nombre
    k["rubro_b"] = k["rubro"].astype(str).str.strip().map(lambda r: _re.sub(r"_(HM|MPB)$", "", r, flags=_re.I))
    k["rubro_b"] = k["rubro_b"].map(lambda r: r[:1].upper() + r[1:])
    k["es_mo"] = k["bloque"].isin(["Mano de obra (nómina)", "Mano de obra al contrato"])

    div = F.leer_tabla("kahai_cultivo_lotes")
    arb, kgl, bloques_txt = {}, {}, {}
    if not div.empty:
        div["lote"] = div["lote"].astype(str).str.strip().str.upper()
        div["bloque"] = div["bloque"].fillna("").astype(str) if "bloque" in div.columns else ""
        for c_ in ["arboles", "kg"]:
            div[c_] = pd.to_numeric(div[c_], errors="coerce")
        # Cumaral = bloques HM + MME: se suman, porque el gasto de cosecha no dice el bloque
        sumas = div.groupby(["lote", "anio"])[["arboles", "kg"]].sum(min_count=1)
        arb = {(l, int(a)): v for (l, a), v in sumas["arboles"].items() if pd.notna(v) and v > 0}
        kgl = {(l, int(a)): v for (l, a), v in sumas["kg"].items() if pd.notna(v) and v > 0}
        for (l, a), g_ in div[div["bloque"] != ""].groupby(["lote", "anio"]):
            partes = [f"{b_}: {pesos(r_)} árb · {pesos(k_)} kg" for b_, r_, k_ in zip(g_["bloque"], g_["arboles"].fillna(0),
                                                                                    g_["kg"].fillna(0)) if r_ or k_]
            if len(partes) > 1:
                bloques_txt[(l, int(a))] = " + ".join(partes)

    def por_kg(rubro):
        return str(rubro).lower().startswith(("cosecha", "fruto verde"))

    lotes = [l for l in LOTES_KAHAI if l in set(k["lote"])] + sorted(set(k["lote"]) - set(LOTES_KAHAI))
    lote_sel = st.segmented_control("Lote", ["Todos los lotes"] + lotes, default="Todos los lotes", key="kc_lote",
                                    format_func=lambda l: LOTES_KAHAI.get(l, l)) or "Todos los lotes"
    todos_l = lote_sel == "Todos los lotes"
    kl = k if todos_l else k[k["lote"] == lote_sel]
    if kl.empty:
        st.info("Este lote no tiene gasto con estos filtros.")
        return
    anios_k = sorted(kl["anio"].unique())[-8:]
    a_ref = anio if anio in anios_k else anios_k[-1]
    ult_m = int(kl.loc[kl["anio"] == a_ref, "periodo"].max() % 100)
    parcial = ult_m < 12
    hasta = f" (Ene–{NOMBRE_MES[ult_m]})" if parcial else ""

    def etq(a):
        m = int(kl.loc[kl["anio"] == a, "periodo"].max() % 100)
        return f"{a} (Ene–{NOMBRE_MES[m]})" if a == anios_k[-1] and m < 12 else str(a)

    # ---- Tarjetas
    g_act = kl.loc[kl["anio"] == a_ref, "valor"].sum()
    g_prev = kl.loc[(kl["anio"] == a_ref - 1) & (kl["periodo"] % 100 <= ult_m), "valor"].sum()
    mo_act = kl.loc[(kl["anio"] == a_ref) & kl["es_mo"], "valor"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Gasto cultivo {a_ref}{hasta}", millones(g_act),
              f"{porcentaje(variacion(g_act, g_prev))} vs {a_ref - 1}{hasta}" if g_prev else None, delta_color="inverse")
    c2.metric("Peso de la mano de obra", f"{mo_act / g_act:.0%}" if g_act else "—",
              help="Nómina + mano de obra al contrato, como % del gasto de cultivo")
    if todos_l:
        g_l = k[k["anio"] == a_ref].groupby("lote")["valor"].sum().sort_values(ascending=False)
        c3.metric(f"Lote con más gasto {a_ref}", LOTES_KAHAI.get(g_l.index[0], g_l.index[0]) if len(g_l) else "—",
                  f"{millones(g_l.iloc[0])}" if len(g_l) else None, delta_color="off")
        c4.metric("Lotes con gasto", str(int((g_l > 0).sum())))
    else:
        a_l, kg_l = arb.get((lote_sel, a_ref)), kgl.get((lote_sel, a_ref))
        c3.metric(f"Costo por árbol {a_ref}{hasta}", unitario(g_act / a_l) if a_l else "sin árboles",
                  help="Gasto del lote ÷ árboles del lote (hoja CULTIVO_LOTES de PRODUCCION_KAHAI.xlsx)")
        g_kg = kl.loc[(kl["anio"] == a_ref) & kl["rubro_b"].map(por_kg), "valor"].sum()
        c4.metric(f"Cosecha $/kg {a_ref}", unitario(g_kg / kg_l) if kg_l else "sin kg",
                  help="Gasto de cosecha del lote ÷ kg cosechados del lote (hoja CULTIVO_LOTES)")

    # ---- Tabla HTML: gasto grande y, debajo, $/árbol o $/kg cuando hay divisor
    def celda(sub, a, rubro=None, lote=None):
        v = sub.loc[sub["anio"] == a, "valor"].sum()
        if not v:
            return "<td>—</td>"
        det = ""
        if lote is not None and lote in LOTES_KAHAI:
            tip = _h.escape(bloques_txt.get((lote, a), ""))
            if rubro is not None and por_kg(rubro):
                d = kgl.get((lote, a))
                det = (f"<div class='det' title='{tip}'>${pesos(v / d)}/kg · {pesos(d)} kg</div>" if d else
                       "<div class='det' style='color:#9A5B00'>sin kg</div>")
            else:
                d = arb.get((lote, a))
                det = (f"<div class='det' title='{tip}'>${pesos(v / d)}/árbol · {pesos(d)} árb</div>" if d else
                       "<div class='det' style='color:#9A5B00'>sin árboles</div>")
        return f"<td>{millones(v)}{det}</td>"

    def tabla(filas_def, titulo_col):
        cab = (f"<tr><th class='izq'>{titulo_col}</th>" + "".join(f"<th class='anio'>{etq(a)}</th>" for a in anios_k)
               + "<th class='anio'>Var.</th></tr>")
        filas = []
        for nombre, sub, rubro, lote, clase in filas_def:
            v_a = sub.loc[sub["anio"] == a_ref, "valor"].sum()
            v_p = sub.loc[(sub["anio"] == a_ref - 1) & (sub["periodo"] % 100 <= ult_m), "valor"].sum()
            var = variacion(v_a, v_p) if v_p and v_a else None   # sin gasto aún este año: "—", no -100%
            color = "#B42318" if var and var > 0 else "#067647"
            var_t = f"<td style='color:{color}'>{porcentaje(var)}</td>" if var is not None else "<td>—</td>"
            filas.append(f"<tr{clase}><td class='izq'>{_h.escape(str(nombre))}</td>"
                         + "".join(celda(sub, a, rubro, lote) for a in anios_k) + var_t + "</tr>")
        return f"<div class='tpk'><table><thead>{cab}</thead><tbody>{''.join(filas)}</tbody></table></div>"

    st.markdown("""<style>
      .tpk { overflow-x:auto; border:1px solid #E5E7EB; border-radius:10px; }
      .tpk table { border-collapse:collapse; width:100%; font-size:0.86rem; font-variant-numeric:tabular-nums; }
      .tpk th { background:#F6F8F5; color:#374151; font-weight:600; padding:0.5rem 0.6rem; border-bottom:1px solid #E1E8DF;
                white-space:nowrap; }
      .tpk th.anio { text-align:center; } .tpk .izq { text-align:left; }
      .tpk td { text-align:right; padding:0.4rem 0.6rem; border-bottom:1px solid #F0F2F0; white-space:nowrap;
                font-weight:600; color:#111827; }
      .tpk td.izq { font-weight:500; } .tpk .det { font-size:0.72rem; font-weight:400; color:#6B7280; }
      .tpk tr.tot td { border-top:2px solid #CBD5CC; background:#FAFBFA; font-weight:800; }
    </style>""", unsafe_allow_html=True)

    lote_d = None if todos_l else lote_sel
    if todos_l:
        st.markdown("##### Gasto por lote")
        defs = [(LOTES_KAHAI.get(l, l), k[k["lote"] == l], None, l, "") for l in lotes]
        defs.append(("TOTAL", k, None, None, " class='tot'"))
        st.markdown(tabla(defs, "Lote"), unsafe_allow_html=True)
    st.markdown("##### Gasto por rubro" + ("" if todos_l else f" · {LOTES_KAHAI.get(lote_sel, lote_sel)}"))
    orden_r = kl.groupby("rubro_b")["valor"].sum().sort_values(ascending=False).index
    defs = [(r, kl[kl["rubro_b"] == r], r, lote_d, "") for r in orden_r]
    defs.append(("Mano de obra (nómina + contrato)", kl[kl["es_mo"]], None, None, ""))
    defs.append(("TOTAL", kl, None, lote_d, " class='tot'"))
    st.markdown(tabla(defs, "Rubro"), unsafe_allow_html=True)
    sin_div = not todos_l and lote_sel in LOTES_KAHAI and not any(l == lote_sel for l, _ in arb)
    st.caption(f"Pesos en millones. Var. = {a_ref}{hasta} contra los mismos meses de {a_ref - 1} (rojo = subió el gasto). "
               "El lote sale de la columna PLANTA del consolidado; los rubros _HM (Cumaral) y _MPB (Restrepo) se juntan "
               "con su rubro base. Cumaral junta sus dos bloques, HM y MME."
               + (" ⚠️ Para ver $/árbol y $/kg, llene la hoja CULTIVO_LOTES de Graficas\\PRODUCCION_KAHAI.xlsx "
                  "(árboles y kg por bloque: Cumaral HM y MME, Restrepo MPB) y corra:  python motor_procesamiento_kahai.py"
                  if not arb and not kgl else " Cumaral suma sus bloques HM y MME (pase el mouse sobre el valor para ver cada bloque)."))

    # ---- Gráfica: gasto por año, apilado por lote (o por rubro si se eligió un lote)
    por_g = "lote" if todos_l else "rubro_b"
    g = kl[kl["anio"].isin(anios_k)].groupby([por_g, "anio"])["valor"].sum().unstack(fill_value=0)
    g = g.loc[g.sum(axis=1).sort_values(ascending=False).index]
    if not todos_l and len(g) > 6:
        g = pd.concat([g.iloc[:6], g.iloc[6:].sum().to_frame("Otros").T])
    paleta = ["#1B5E20", "#eb6834", "#2a78d6", "#9CA3AF", "#eda100", "#e87ba4", "#6250d6"]
    fig = go.Figure()
    for i, (nombre, fila) in enumerate(g.iterrows()):
        fig.add_bar(x=[etq(a) for a in g.columns], y=fila.values / 1e6, name=LOTES_KAHAI.get(nombre, nombre),
                    marker_color=paleta[i % len(paleta)],
                    hovertemplate=f"{LOTES_KAHAI.get(nombre, nombre)}<br>%{{x}}: %{{y:,.1f}} M<extra></extra>")
    fig.update_layout(barmode="stack", height=340, separators=",.", bargap=0.3,
                      title="Gasto de cultivo por año" + (" y lote" if todos_l else " y rubro") + " (millones)",
                      legend=dict(orientation="h", y=1.16, x=0, traceorder="normal"), margin=dict(l=10, r=10, t=70, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="rgba(128,128,128,0.2)", ticksuffix=" M"),
                      xaxis=dict(type="category"))
    st.plotly_chart(fig, width="stretch")


LOTES_REALES_KAHAI = {"CUMARAL", "RESTREPO", "PTO GAITAN"}    # VILLA/CIO es gasto general, no lote
PRODUCTOS_KAHAI = {"hidratante", "proteina", "proteína", "blister", "jabon", "jabón", "miel", "harina", "accesorios",
                   "exfoliante", "galletas", "lipstick"}
GENERALES_KAHAI = "kg de aceite producido (fila FILTRADO de la hoja DIVISORES)"


def mostrar_cu_kahai():
    """Costo unitario de KAHAI con el mismo formato de AGROCACAY: costo real (gasto ÷ unidades) y, debajo de cada
    valor, con qué se dividió. Reglas (acordadas con Wal):
      CULTIVO        -> lote = PLANTA. Cosecha / fruto verde ÷ kg del lote; lo demás ÷ árboles del lote
                        (hoja CULTIVO_LOTES; Cumaral = HM + MME).
      POSCOSECHA     -> ÷ kg de concha procesada (DIVISORES).
      PROCESAMIENTO  -> Nuez ÷ kg nuez pelada; aceite y gastos generales de planta ÷ kg de aceite (Extracción ÷ EXTRACCIÓN);
                        productos (hidratante, proteína, jabón…) sin divisor por ahora.
      FRUTA          -> ÷ kg comprados de ese tipo (hoja FRUTA_COMPRADA).
      VIVERO         -> ÷ plantas producidas (hoja VIVERO).
      Generales (ADMINISTRATIVO, COMERCIALIZACIÓN, ALMACEN, INFRAESTRUCTURA…) -> ÷ kg de aceite producido.
    Celdas que mezclan unidades: ÷ árboles (si todo es cultivo) o ÷ kg de aceite (costo de la empresa por kg)."""
    import html as _h
    import re as _re
    k = datos[(datos["empresa"] == "KAHAI") & datos["naturaleza"].isin(naturalezas) & datos["tipo"].isin(tipos)].copy()
    if k.empty:
        st.info("No hay gasto de KAHAI con estos filtros.")
        return
    k["anio"] = (k["periodo"] // 100).astype(int)
    for c_ in ["ceco", "rubro", "detalle", "descripcion", "actividad", "planta"]:
        k[c_] = k[c_].fillna("").astype(str).str.strip() if c_ in k.columns else ""
    # Mismo nombre con distinta mayúscula = lo mismo ("Mano de Obra" / "Mano de obra", "Cosecha" / "cosecha")
    for c_ in ["rubro", "detalle", "descripcion"]:    # se queda la forma de escribir más usada
        forma = k.groupby(k[c_].str.lower())[c_].agg(lambda x: x.value_counts().index[0])
        k[c_] = k[c_].str.lower().map(forma)
    for c_ in ["detalle", "descripcion"]:
        k[c_] = k[c_].replace("", "(sin dato)")
    k["lote"] = k["planta"].str.upper().replace("", "(sin lote)")

    # ---- Divisores
    dv = F.leer_tabla("kahai_divisores")
    kgdiv = {(str(d_).upper(), int(a_)): v_ for d_, a_, v_ in zip(dv.get("divisor", []), dv.get("anio", []), dv.get("kg", []))
             if pd.notna(v_) and v_ > 0} if not dv.empty else {}
    cl = F.leer_tabla("kahai_cultivo_lotes")
    arb, kgl = {}, {}
    if not cl.empty:
        cl["lote"] = cl["lote"].astype(str).str.strip().str.upper()
        for c_ in ["arboles", "kg"]:
            cl[c_] = pd.to_numeric(cl[c_], errors="coerce")
        sm = cl.groupby(["lote", "anio"])[["arboles", "kg"]].sum(min_count=1)
        arb = {(l_, int(a_)): v_ for (l_, a_), v_ in sm["arboles"].items() if pd.notna(v_) and v_ > 0}
        kgl = {(l_, int(a_)): v_ for (l_, a_), v_ in sm["kg"].items() if pd.notna(v_) and v_ > 0}
    vv = F.leer_tabla("kahai_vivero")
    plantas = {int(a_): v_ for a_, v_ in zip(vv.get("anio", []), pd.to_numeric(vv.get("plantas", pd.Series(dtype=float)),
                                                                            errors="coerce")) if pd.notna(v_) and v_ > 0} \
        if not vv.empty else {}
    fc = F.leer_tabla("kahai_fruta_comprada")
    kgf = {}
    if not fc.empty:
        fc["tipo"] = fc["tipo"].astype(str).str.strip().str.upper()
        kgf = {(t_, int(a_)): v_ for (t_, a_), v_ in
               fc.groupby(["tipo", "anio"])["kg"].sum(min_count=1).items() if pd.notna(v_) and v_ > 0}

    # ---- Regla de cada fila: unidad, tipo de suma y "bolsa" de divisor
    #  suma   = bolsas en paralelo (lotes, tipos de fruta): gasto total ÷ suma de las unidades
    #  etapa  = etapas en serie de la empresa (concha, nuez, aceite): se suman los $/unidad de cada etapa
    def regla_fila(ceco, rubro, detalle, lote):
        ce, rb, de = ceco.upper(), rubro.lower(), detalle.lower()
        rb_base = _re.sub(r"_(hm|mpb)$", "", rb)
        if ce == "CULTIVO":
            if rb_base.startswith(("cosecha", "fruto verde")):
                return ("kg", "suma", ("kg_lote", lote))
            return ("árb", "suma", ("arb_lote", lote))
        if ce == "POSCOSECHA":
            return ("kg concha", "etapa", ("div", "CONCHA PROCESADA"))
        if ce == "PROCESAMIENTO":
            if rb_base in PRODUCTOS_KAHAI:
                return ("sin divisor", "", None)
            if rb_base.startswith("nuez"):
                return ("kg nuez pelada", "etapa", ("div", "NUEZ PELADA"))
            if rb_base.startswith("aceite") and de.startswith("extracci"):
                return ("kg aceite", "etapa", ("div", "EXTRACCIÓN"))
            return ("kg aceite", "etapa", ("div", "FILTRADO"))
        if ce == "FRUTA":
            return ("kg comprados", "suma", ("fruta", rubro.upper()))
        if ce == "VIVERO":
            return ("plantas", "etapa", ("plantas", ""))
        return ("kg aceite", "etapa", ("div", "FILTRADO"))

    combos = k[["ceco", "rubro", "detalle", "lote"]].drop_duplicates()
    reglas_c = {tuple(r_): regla_fila(*r_) for r_ in combos.itertuples(index=False, name=None)}
    trip = [reglas_c[t_] for t_ in zip(k["ceco"], k["rubro"], k["detalle"], k["lote"])]
    k["unidad"] = [t_[0] for t_ in trip]
    k["suma"] = [t_[1] for t_ in trip]
    k["bolsa"] = [t_[2] for t_ in trip]

    def valor_bolsa(bolsa, a):
        if bolsa is None:
            return None
        t_, n_ = bolsa
        return {"kg_lote": kgl, "arb_lote": arb}.get(t_, {}).get((n_, a)) if t_ in ("kg_lote", "arb_lote") else \
            kgdiv.get((n_, a)) if t_ == "div" else kgf.get((n_, a)) if t_ == "fruta" else plantas.get(a)

    ICONO = {"kg": "⚖️", "kg concha": "⚖️", "kg nuez pelada": "⚖️", "kg aceite": "🛢️", "kg comprados": "⚖️",
             "árb": "🌳", "plantas": "🌱"}

    _kg_tabla = {}

    def kg_tabla(a):
        if a not in _kg_tabla:
            b_a = base[(base["anio"] == a) & base["bolsa"].map(lambda b_: bool(b_) and b_[0] == "kg_lote")]
            lotes_a = set(b_a["lote"])
            if lotes_a - LOTES_REALES_KAHAI:            # hay gasto general de cosecha: todos los lotes
                lotes_a = set(LOTES_REALES_KAHAI)
            _kg_tabla[a] = sum(kgl.get((l_, a), 0) for l_ in lotes_a & LOTES_REALES_KAHAI)
        return _kg_tabla[a]

    def costo_y_etiqueta(sub):
        """(costo real, etiqueta del divisor) de un grupo de filas de UN año."""
        if sub.empty:
            return np.nan, ""
        a = int(sub["anio"].iloc[0])
        con = sub[sub["unidad"] != "sin divisor"]
        unidades = set(con["unidad"])
        if not unidades:
            return np.nan, "<span class='dv'>sin divisor</span>"
        if len(unidades) > 1:
            if set(sub["ceco"].str.upper()) == {"CULTIVO"}:
                lotes_ = {b_[1] for b_ in con["bolsa"] if b_}
                d_ = sum(arb.get((l_, a), 0) for l_ in lotes_)
                if d_:
                    return sub["valor"].sum() / d_, f"<span class='dv'>🌳 {pesos(d_)} árb · varias reglas</span>"
                return np.nan, "<span class='dv' style='color:#9A5B00'>🌳 sin árboles</span>"
            d_ = kgdiv.get(("FILTRADO", a))
            if d_:
                return sub["valor"].sum() / d_, f"<span class='dv'>🛢️ {pesos(d_)} kg aceite · varias reglas</span>"
            return np.nan, "<span class='dv' style='color:#9A5B00'>sin kg de aceite</span>"
        u = unidades.pop()
        ic = ICONO.get(u, "")
        bolsas = con.groupby(con["bolsa"].map(str))
        vals = {b_: (g_["valor"].sum(), valor_bolsa(g_["bolsa"].iloc[0], a)) for b_, g_ in bolsas}
        faltan = [b_ for b_, (_, d_) in vals.items() if not d_]
        tipos_b0 = {b_[0] for b_ in con["bolsa"] if b_}
        if len(faltan) == len(vals) and not (tipos_b0 and tipos_b0 <= {"kg_lote", "arb_lote"}):
            return np.nan, f"<span class='dv' style='color:#9A5B00'>{ic} sin dato</span>"
        tipos_b = {b_[0] for b_ in con["bolsa"] if b_}
        if tipos_b and tipos_b <= {"kg_lote", "arb_lote"}:
            # Cultivo: cada lote real usa sus kg / árboles; lo que no es lote (Villavicencio, sin lote) se reparte
            # entre los kg / árboles de TODOS los lotes del año. Así todas las filas del año usan el mismo divisor.
            mapa = kgl if "kg_lote" in tipos_b else arb
            lotes_c = {b_[1] for b_ in con["bolsa"] if b_}
            reales = lotes_c & LOTES_REALES_KAHAI
            general = bool(lotes_c - LOTES_REALES_KAHAI)
            con_dato = {l_ for l_ in reales if mapa.get((l_, a))}
            faltan_l = sorted(reales - con_dato)
            d_lotes = sum(mapa[(l_, a)] for l_ in con_dato)
            d_todos = sum(mapa.get((l_, a), 0) for l_ in LOTES_REALES_KAHAI)
            d_ = max(d_lotes, d_todos if general else 0)
            if "kg_lote" in tipos_b and por != "lote":
                # Cosecha: un solo divisor por año para TODA la tabla que se está viendo = kg de los lotes que
                # tienen gasto de cosecha en esa tabla (si hay gasto general, todos los lotes). Así las filas
                # suman el TOTAL. El costo de cada lote se ve con "Ver por lote".
                d_, faltan_l, general = kg_tabla(a), [], True
            if not d_:
                return np.nan, f"<span class='dv' style='color:#9A5B00'>{ic} sin dato</span>"
            g_ = con.loc[~con["lote"].isin(faltan_l), "valor"].sum()
            extra = ""
            falta = (f" <span style='color:#9A5B00' title='Este gasto no entra: el lote no tiene {u} ese año'>"
                     f"· falta {', '.join(LOTES_KAHAI.get(l_, l_) for l_ in faltan_l)}</span>") if faltan_l else ""
            return g_ / d_, f"<span class='dv'>{ic} {pesos(d_)} {u}{extra}{falta}</span>"
        if con["suma"].iloc[0] == "suma":
            g_ok = sum(g_ for g_, d_ in vals.values() if d_)
            d_ok = sum(d_ for _, d_ in vals.values() if d_)
            extra = " · falta dato" if faltan else ""
            return g_ok / d_ok, f"<span class='dv'>{ic} {pesos(d_ok)} {u}{extra}</span>"
        c_ = sum(g_ / d_ for g_, d_ in vals.values() if d_)
        ds = sorted({d_ for _, d_ in vals.values() if d_})
        txt = f"{pesos(ds[0])} {u}" if len(ds) == 1 else f"{u} · {len(ds)} etapas"
        return c_, f"<span class='dv'>{ic} {txt}{' · falta dato' if faltan else ''}</span>"

    # ---- Recorrido CECO › Rubro › Actividad › Lote (como en AGROCACAY)
    st.markdown("<div style='display:flex;align-items:baseline;gap:0.8rem;flex-wrap:wrap;margin:0.2rem 0 0.1rem'>"
                "<span style='font-size:1.35rem;font-weight:700;color:#111827'>Costo unitario</span>"
                "<span style='font-size:0.8rem;color:#6B7280'>gasto ÷ unidades (kg, árboles, plantas) · debajo de cada "
                "valor, con qué se dividió</span></div>", unsafe_allow_html=True)
    # En KAHAI la columna Actividad cambia de nombre entre años y trae facturas: se baja por Detalle y Descripción
    NIV = [("CECO", "ceco"), ("Rubro", "rubro"), ("Detalle", "detalle"), ("Descripción", "descripcion")]
    cols_n = st.columns([1, 1, 1.3, 1])
    base, elegidos = k, []
    for i, (nom, campo) in enumerate(NIV):
        libre = len(elegidos) < i
        ops = sorted(base[campo].replace("", np.nan).dropna().unique().tolist()) if not libre else []
        val = cols_n[i].selectbox(nom, ["Todos"] + ops, key=f"kcu_{'_'.join(elegidos)}_{campo}", disabled=libre)
        if val != "Todos" and not libre:
            base = base[base[campo] == val]
            elegidos.append(val)
    ver, por = (NIV[len(elegidos)] if len(elegidos) < len(NIV) else ("Lote", "lote"))
    r1, r2 = st.columns([4, 1.2], vertical_alignment="center")
    r1.markdown(f'<div style="font-size:0.82rem;color:#374151;margin:-0.35rem 0 0.1rem">📍 <b>{" › ".join(["KAHAI"] + elegidos)}'
                f'</b> &nbsp;·&nbsp; filas por <b>{ver}</b></div>', unsafe_allow_html=True)
    if por != "lote" and r2.toggle("📍 Ver por lote", key="kcu_por_lote",
                                   help="Filas por lote (PLANTA), ordenadas del más caro al más barato, con su "
                                        "diferencia contra el promedio de los lotes."):
        ver, por = "Lote", "lote"
    anios_t = sorted(base["anio"].unique())[-6:]
    base = base[base["anio"].isin(anios_t)]
    if base.empty:
        st.info("Sin gasto en los últimos años con estos filtros.")
        return

    filas_k = base.groupby(por)["valor"].sum().sort_values(ascending=False)
    celdas = {(f_, a_): costo_y_etiqueta(g_) for (f_, a_), g_ in base.groupby([por, "anio"])}
    tot = {a_: costo_y_etiqueta(g_) for a_, g_ in base.groupby("anio")}
    orden = list(filas_k.index)
    vs, a_ref = {}, (anio if anio in anios_t else anios_t[-1])
    if por == "lote":
        lotes_ok = [l_ for l_ in orden if l_ in LOTES_KAHAI and l_ != "VILLA/CIO"]
        prom = costo_y_etiqueta(base[(base["anio"] == a_ref) & base["lote"].isin(lotes_ok)])[0]
        for l_ in lotes_ok:
            v_ = celdas.get((l_, a_ref), (np.nan, ""))[0]
            vs[l_] = (v_ / prom - 1) if prom and pd.notna(v_) else None
        orden = sorted(lotes_ok, key=lambda l_: -(celdas.get((l_, a_ref), (np.nan,))[0]
                                                  if pd.notna(celdas.get((l_, a_ref), (np.nan,))[0]) else -1e18)) + \
            [o for o in orden if o not in lotes_ok]

    def td(v, etq):
        if v is None or pd.isna(v):
            return f"<td>—{('<br>' + etq) if etq and 'sin' in etq else ''}</td>"
        return f"<td>{unitario(v)}{etq}</td>"

    def badge(v):
        if v is None:
            return "<td>—</td>"
        cl_ = "alto" if v > 0.10 else ("bajo" if v < -0.10 else "medio")
        return f'<td><span class="vs {cl_}">{porcentaje(v)}</span></td>'

    con_vs = por == "lote"
    cab = (f"<tr><th class='izq'>{ver}</th><th>Gasto total</th><th>% del gasto</th>"
           + (f"<th class='anio'>vs promedio<div class='sub'>lotes {a_ref}</div></th>" if con_vs else "")
           + "".join(f"<th class='anio'>{a_}</th>" for a_ in anios_t) + "</tr>")
    total_g = base["valor"].sum()
    filas = []
    for f_ in orden:
        nombre = LOTES_KAHAI.get(f_, f_) if por == "lote" else f_
        filas.append(f"<tr><td class='izq'>{_h.escape(str(nombre))}</td><td>{millones(filas_k[f_])}</td>"
                     + "<td>" + f"{filas_k[f_] / total_g:.1%}".replace(".", ",") + "</td>"
                     + (badge(vs.get(f_)) if con_vs else "")
                     + "".join(td(*celdas.get((f_, a_), (np.nan, ""))) for a_ in anios_t) + "</tr>")
    filas.append(f"<tr class='tot'><td class='izq'>TOTAL</td><td>{millones(total_g)}</td><td>100,0%</td>"
                 + ("<td></td>" if con_vs else "") + "".join(td(*tot.get(a_, (np.nan, ""))) for a_ in anios_t) + "</tr>")
    st.markdown("""<style>
      .tck { overflow-x:auto; border:1px solid #E5E7EB; border-radius:10px; }
      .tck table { border-collapse:collapse; width:100%; font-size:0.81rem; font-variant-numeric:tabular-nums; }
      .tck th { background:#F6F8F5; color:#374151; font-weight:600; text-align:right; padding:0.32rem 0.45rem;
                border-bottom:1px solid #E1E8DF; white-space:nowrap; }
      .tck th.anio { text-align:center; } .tck .izq { text-align:left; white-space:normal; min-width:120px; max-width:200px; }
      .tck th .sub { font-size:0.66rem; font-weight:600; color:#1B5E20; }
      .tck td { text-align:right; padding:0.22rem 0.45rem; border-bottom:1px solid #F0F2F0; white-space:nowrap; }
      .tck tr.tot td { font-weight:700; border-top:2px solid #CBD5CC; background:#FAFBFA; }
      .tck .dv { display:block; font-size:0.66rem; color:#8A949B; font-weight:400; }
      .tck .vs { display:inline-block; min-width:3.6rem; text-align:center; padding:1px 8px; border-radius:999px;
                 font-weight:700; font-size:0.76rem; }
      .tck .vs.alto { background:#FDECEA; color:#B42318; } .tck .vs.bajo { background:#E7F5EC; color:#067647; }
      .tck .vs.medio { background:#F2F4F7; color:#475467; }
    </style>""", unsafe_allow_html=True)
    st.markdown(f"<div class='tck'><table><thead>{cab}</thead><tbody>{''.join(filas)}</tbody></table></div>",
                unsafe_allow_html=True)
    faltan_txt = []
    if not plantas and (base["ceco"].str.upper() == "VIVERO").any():
        faltan_txt.append("plantas producidas del vivero (hoja VIVERO)")
    if not kgf and (base["ceco"].str.upper() == "FRUTA").any():
        faltan_txt.append("kg de fruta comprada (hoja FRUTA_COMPRADA)")
    if not arb and (base["ceco"].str.upper() == "CULTIVO").any():
        faltan_txt.append("árboles y kg por lote (hoja CULTIVO_LOTES)")
    st.caption("Cultivo: cosecha ÷ kg del lote, lo demás ÷ árboles (Cumaral = HM + MME) · Poscosecha ÷ kg de concha · "
               "Nuez ÷ kg nuez pelada · Aceite y gastos generales ÷ kg de aceite · Productos (hidratante, proteína…): "
               "sin divisor por ahora. Si una fila mezcla unidades, se divide por kg de aceite (o por árboles en cultivo)."
               + (f" ⚠️ Falta en Graficas\\\\PRODUCCION_KAHAI.xlsx: {'; '.join(faltan_txt)}." if faltan_txt else ""))


with pest[2]:
    if vista == "KAHAI":
        vista_k = st.segmented_control("Ver", ["📊 Costo unitario", "🏭 Procesamiento"], default="📊 Costo unitario",
                                       key="kahai_cu_vista", label_visibility="collapsed") or "📊 Costo unitario"
        if vista_k.startswith("📊"):
            mostrar_cu_kahai()
        else:
            mostrar_procesamiento_kahai()
    else:
        datos_cu, ultimo_cu = cargar_cu(VERSION_DATOS)
        if datos_cu.empty:
            st.warning("Todavía no hay costo unitario calculado. Corra:  python motor_costo_unitario.py")
        else:
            if vista == GRUPO:
                st.caption("Vista Grupo: el costo unitario se muestra solo para AGROCACAY.")
            # ¿Cambió el Excel de referencias después del último cálculo?
            # (en la nube no hay Excel: solo se muestra la fecha del último cálculo)
            if os.path.exists(C.ARCHIVO_REFERENCIAS_CU) and not ultimo_cu.empty:
                from datetime import datetime
                f_ref = datetime.fromtimestamp(os.path.getmtime(C.ARCHIVO_REFERENCIAS_CU)).strftime("%Y-%m-%d %H:%M")
                if f_ref > ultimo_cu["fecha_referencias"].iloc[0]:
                    st.warning(f"El Excel de referencias (PXN, CENSO, SYRS, ARB_TOTAL) se guardó el {f_ref}, "
                               "después del último cálculo. Corra:  python motor_costo_unitario.py")
            if not ultimo_cu.empty:
                st.caption(f"Último cálculo: {ultimo_cu['fecha'].iloc[0]} · referencias: "
                           f"{os.path.basename(C.ARCHIVO_REFERENCIAS_CU)} ({ultimo_cu['fecha_referencias'].iloc[0]})")

            cu = datos_cu[datos_cu["naturaleza"].isin(naturalezas) & datos_cu["tipo"].isin(tipos)]

            # ---- Indicadores: costo total por árbol vivo (todos los rubros juntos)
            # (El ponderado total mezcla unidades distintas —por árbol, por kg, por sitio sembrado—,
            #  por eso arriba se muestra el costo por árbol vivo, que se lee directo.)
            arb_anio = datos_cu.groupby("anio")["arb_total_vivos"].max()
            # Lotes: ubicaciones con censo o con kg cosechados propios (L1…L25, ML1…, HMPG)
            lotes_cu = {u for u in datos_cu["ubicacion"].dropna().unique()
                        if re.match(r"^(ML|L)\d+$|^HMPG$", str(u).strip(), flags=re.I)}

            # ---- Tabla ponderada (igual a la de la app de campo / Power BI)
            st.markdown("<div style='display:flex;align-items:baseline;gap:0.8rem;flex-wrap:wrap;margin:0.2rem 0 0.1rem'>"
                        "<span style='font-size:1.35rem;font-weight:700;color:#111827'>Costo unitario</span>"
                        "<span style='font-size:0.8rem;color:#6B7280'>gasto ÷ unidades de su regla (árboles, kg o sitios "
                        "sembrados) · debajo de cada valor, con qué se dividió</span></div>", unsafe_allow_html=True)
            # Recorrido como en una junta: la empresa ya está en el encabezado; aquí se baja
            # CECO → Rubro → Detalle → Descripción (igual que KAHAI). La tabla muestra siempre el SIGUIENTE nivel
            # al último elegido; con todo elegido, una fila por lote. "Ver por lote" abre cualquier nivel por lote.
            NIVELES = [("CECO", "ceco"), ("Rubro", "rubro"), ("Detalle", "detalle"), ("Descripción", "descripcion")]
            TODOS = "Todos"
            cols_n = st.columns([0.9, 1.1, 1.3, 1.7, 1.3])
            eje = cols_n[0].radio("Columnas", ["Año", "Mes"], horizontal=True)
            base = cu
            elegidos_n, clave = [], "cu"
            for i, (nombre_n, campo_n) in enumerate(NIVELES):
                opciones_n = list(base.groupby(campo_n)["valor"].sum().sort_values(ascending=False).index)
                clave += "_" + (elegidos_n[-1] if elegidos_n else "x")   # al cambiar el nivel de arriba, se reinicia
                anterior_libre = len(elegidos_n) < i
                valor_n = cols_n[i + 1].selectbox(nombre_n, [TODOS] + opciones_n, key=f"{clave}_{campo_n}",
                                                  disabled=anterior_libre,
                                                  help="Elija el nivel de arriba primero" if anterior_libre else None)
                if valor_n != TODOS and not anterior_libre:
                    base = base[base[campo_n] == valor_n]
                    elegidos_n.append(valor_n)
            # El nivel que se muestra en filas: el siguiente al último elegido
            if len(elegidos_n) < len(NIVELES):
                ver, por = NIVELES[len(elegidos_n)]
            else:
                ver, por = "Ubicación", "ubicacion"
            ruta = " › ".join([titulo_vista] + elegidos_n)
            rc1, rc3, rc2 = st.columns([3.7, 1.1, 1.3], vertical_alignment="center")
            # Ver por lote en cualquier nivel (ej. MIAR por lote sin elegir actividad)
            if por != "ubicacion":
                if rc3.toggle("📍 Ver por lote", key="cu_por_lote", value=False,
                              help="Filas por lote (ubicación), ordenadas del más caro al más barato, con su "
                                   "diferencia contra el promedio de los lotes."):
                    ver, por = "Ubicación", "ubicacion"
            rc1.markdown(f'<div style="font-size:0.82rem;color:#374151;margin:-0.35rem 0 0.1rem">📍 <b>{ruta}</b>'
                         f' &nbsp;·&nbsp; filas por <b>{ver}</b></div>', unsafe_allow_html=True)
            # El costo real es gasto ÷ unidades. El ponderado de Power BI queda solo para cuadrar con el informe viejo.
            ver_pond = rc2.toggle("Ver ponderado (Power BI)", key="cu_pond", value=False,
                                  help="Muestra la medida 'Costo Unitario Ponderado' de Power BI (promedio de los costos "
                                       "de cada mes y lote, pesado por el gasto). No es el costo real por unidad: "
                                       "úsela solo para cuadrar con ese informe.")

            if eje == "Mes":
                per_cu = sorted(base["periodo"].unique())
                if len(per_cu) >= 2:
                    # Rango por defecto: el año elegido (o los 12 meses hasta el mes elegido), ajustado
                    # a los meses que sí tienen gasto con estos filtros
                    ini_d, fin_d = (acum[0], mes) if todos else (seleccion[0], mes) if anual else (mover(mes, -11), mes)
                    ini_v = next((p for p in per_cu if p >= ini_d), per_cu[0])
                    fin_v = next((p for p in reversed(per_cu) if p <= fin_d), per_cu[-1])
                    if ini_v > fin_v:
                        ini_v, fin_v = per_cu[0], per_cu[-1]
                    d1, d2 = st.select_slider("Meses ", options=per_cu, format_func=etiqueta, value=(ini_v, fin_v))
                    base = base[(base["periodo"] >= d1) & (base["periodo"] <= d2)]
                base = base.assign(_x=base["periodo"])
            else:
                base = base.assign(_x=base["anio"])

            if base.empty:
                st.info("No hay datos con estos filtros.")
            else:
                import html as _html

                def armar_tabla_cu(b, por_c, nombre_c):
                    """Tabla ponderada: filas = por_c (orden de mayor a menor gasto) + TOTAL; columnas = años o meses."""
                    t = ponderado(b, por_c, "_x").unstack("_x")
                    t.loc["TOTAL"] = ponderado(b, None, "_x")
                    g = b.groupby(por_c)["valor"].sum()
                    orden_g = list(g.sort_values(ascending=False).index)
                    orden_g = [o for o in orden_g if not str(o).startswith("Otras (")] + \
                              [o for o in orden_g if str(o).startswith("Otras (")]   # 'Otras' al final
                    t = t.reindex([o for o in orden_g + ["TOTAL"] if o in t.index])
                    t.columns = [etiqueta(c) for c in t.columns] if eje == "Mes" else [str(int(c)) for c in t.columns]
                    t.insert(0, "Gasto total", g.reindex(t.index).fillna(b["valor"].sum()))
                    t.insert(1, "% del gasto", t["Gasto total"] / b["valor"].sum())
                    t.index.name = nombre_c
                    return t.reset_index()

                def costo_directo(sub):
                    """COSTO REAL de una celda: gasto ÷ unidades de su regla.
                    - kg (PXN_KG): gasto ÷ kg cosechados (sin contar dos veces los kg de lotes y de la finca)
                    - censo / SYRS: gasto cargado a lotes ÷ árboles de esos lotes, más lo general ÷ árboles vivos
                    - sitios sembrados, árboles vivos: gasto ÷ ese número
                    - si la celda mezcla reglas (ej. un CECO entero): gasto ÷ árboles vivos del año."""
                    if sub is None or sub.empty:
                        return np.nan
                    o = sub["origen_divisor"].astype(str)
                    sub = sub[~o.str.contains("CU en blanco") & ~o.str.startswith("Sin divisor")]
                    if sub.empty:
                        return np.nan
                    arb = arb_anio.get(int(sub["anio"].iloc[0]))
                    reglas = set(sub["regla_divisor"].map(norm_regla))
                    if len(reglas) > 1:
                        return sub["valor"].sum() / arb if arb else np.nan
                    rg = reglas.pop()
                    o = sub["origen_divisor"].astype(str)
                    resp, prop = sub[o.str.startswith("Respaldo")], sub[~o.str.startswith("Respaldo")]
                    v_resp = resp["valor"].sum() / arb if (len(resp) and arb) else 0
                    if prop.empty:
                        return v_resp if len(resp) and arb else np.nan
                    if rg == "PXN_KG":
                        u = kg_pxn(prop)
                    elif rg == "SITIOS_SIEMBRA":
                        u = prop["sitios_siembra"].max()
                    elif rg == "CENSO":
                        u = prop[prop["censo"] > 0].groupby("ubicacion")["censo"].max().sum()
                    elif rg == "SYRS_ARBOLES":
                        u = prop[prop["syrs_arboles"] > 0].groupby("ubicacion")["syrs_arboles"].max().sum()
                    else:
                        u = arb
                    return (prop["valor"].sum() / u if u and u > 0 else np.nan) + v_resp

                def armar_tabla_directo(b, por_c, nombre_c):
                    """Misma forma que armar_tabla_cu, pero cada valor es el costo real (gasto ÷ unidades)."""
                    xs = sorted(b["_x"].dropna().unique())
                    filas = {k: {x: costo_directo(s_) for x, s_ in g_.groupby("_x")} for k, g_ in b.groupby(por_c)}
                    t = pd.DataFrame.from_dict(filas, orient="index").reindex(columns=xs)
                    t.loc["TOTAL"] = pd.Series({x: costo_directo(s_) for x, s_ in b.groupby("_x")})
                    g = b.groupby(por_c)["valor"].sum()
                    orden_g = list(g.sort_values(ascending=False).index)
                    orden_g = [o for o in orden_g if not str(o).startswith("Otras (")] + \
                              [o for o in orden_g if str(o).startswith("Otras (")]
                    t = t.reindex([o for o in orden_g + ["TOTAL"] if o in t.index])
                    t.columns = [etiqueta(c) for c in t.columns] if eje == "Mes" else [str(int(c)) for c in t.columns]
                    t.insert(0, "Gasto total", g.reindex(t.index).fillna(b["valor"].sum()))
                    t.insert(1, "% del gasto", t["Gasto total"] / b["valor"].sum())
                    t.index.name = nombre_c
                    return t.reset_index()

                armar = armar_tabla_cu if ver_pond else armar_tabla_directo

                # Divisor que se muestra debajo de cada año: el de la REGLA de lo que hay en la tabla
                # (Siembra -> sitios sembrados del año; MIAR, Nutrición -> censo de los lotes; Cosecha -> kg; etc.)
                DIV_REGLA = {"SITIOS_SIEMBRA": ("🌱", "sitios sembrados en el año (hoja ARB_TOTAL, derecha)"),
                             "CENSO": ("🌳", "árboles del censo de los lotes con gasto"),
                             "PXN_KG": ("⚖️", "kg cosechados (Cosecha en un lote: kg del lote; Poscosecha y gastos sin lote: "
                                               "kg cosechados en el año en toda la finca, la fruta que pasa por poscosecha)"),
                             "SYRS_ARBOLES": ("🌱", "árboles sembrados/resembrados (SYRS)"),
                             "ARB_TOTALVIVOS": ("🌳", "árboles vivos de la finca (ARB_TOTAL)")}

                def regla_de(b):
                    rr = {str(x).upper() for x in b["regla_divisor"].dropna().unique()}
                    rr = {"ARB_TOTALVIVOS" if x in ("—", "ARB_TOTALVIVOS") else x for x in rr}
                    return rr.pop() if len(rr) == 1 else None      # None = varias reglas mezcladas

                def norm_regla(x):
                    x = str(x).upper()
                    return "ARB_TOTALVIVOS" if x in ("—", "ARB_TOTALVIVOS") else x

                def regla_principal(b):
                    """Regla de la tabla: la única, o la que lleva >= 80% del gasto. Devuelve (regla, participación)."""
                    if b.empty:
                        return None, 0
                    g = b.groupby(b["regla_divisor"].map(norm_regla))["valor"].sum()
                    if g.sum() <= 0:
                        return None, 0
                    r, part = g.idxmax(), g.max() / g.sum()
                    return (r, part) if part >= 0.8 else (None, part)

                def kg_pxn(sub):
                    """Kg cosechados de un grupo de filas con regla PXN_KG, sin contar dos veces:
                    lotes por mes, lotes por año, y la finca completa en el año (Poscosecha, asignaciones sin lote)."""
                    sub = sub[(sub["regla_divisor"].map(norm_regla) == "PXN_KG") & (sub["pxn_kg"] > 0)]
                    if sub.empty:
                        return 0
                    o = sub["origen_divisor"].astype(str)
                    # por lote: la suma de sus meses, o su total del año si alguna fila usó el año (lo mayor)
                    por_mes = (sub[o == "Propio de la regla"].groupby(["anio", "mes", "ubicacion"])["pxn_kg"].max()
                               .groupby(level=["anio", "ubicacion"]).sum())
                    por_anio = sub[o.str.contains("lote en el año")].groupby(["anio", "ubicacion"])["pxn_kg"].max()
                    lotes = pd.concat([por_mes, por_anio]).groupby(level=[0, 1]).max().sum()
                    finca = sub[o.str.contains("toda la finca|kg del mes")].groupby("anio")["pxn_kg"].max().sum()
                    return max(lotes, finca)

                def divisor_anio(b, a, regla):
                    ba = b[b["anio"] == a]
                    if ba.empty:
                        return None, False
                    if regla == "SITIOS_SIEMBRA":
                        v = ba["sitios_siembra"].max()
                    elif regla == "CENSO":
                        v = ba[ba["censo"] > 0].groupby("ubicacion")["censo"].max().sum()
                    elif regla == "SYRS_ARBOLES":
                        v = ba[ba["syrs_arboles"] > 0].groupby("ubicacion")["syrs_arboles"].max().sum()
                    elif regla == "PXN_KG":
                        v = kg_pxn(ba)
                    else:
                        return arb_anio.get(a), False
                    if v and v > 0:
                        return v, False
                    if regla in ("SITIOS_SIEMBRA", "PXN_KG"):
                        return None, True          # sin sitios sembrados: el costo queda en blanco
                    return arb_anio.get(a), True   # la regla no tiene su divisor ese año: respaldo árboles vivos

                UNI_DIV = {"SITIOS_SIEMBRA": "sitios", "CENSO": "árb.", "PXN_KG": "kg", "SYRS_ARBOLES": "árb.", "ARB_TOTALVIVOS": "árb."}

                def divisor_celda(sub):
                    """Divisor de la regla de UNA celda (fila × año/mes), para mostrarlo en pequeño debajo del costo unitario."""
                    if sub is None or sub.empty:
                        return ""
                    rr = {"ARB_TOTALVIVOS" if str(x).upper() in ("—", "ARB_TOTALVIVOS") else str(x).upper() for x in sub["regla_divisor"].dropna().unique()}
                    if len(rr) != 1:
                        if not ver_pond and arb_anio.get(int(sub["anio"].iloc[0])):
                            return (f'<span class="dv" title="Esta celda mezcla reglas distintas (árboles, kg, sitios): '
                                    f'para tener una sola cifra se divide todo por los árboles vivos del año">'
                                    f'🌳 {pesos(arb_anio.get(int(sub["anio"].iloc[0])))} árb. vivos · varias reglas</span>')
                        return '<span class="dv" title="Esta celda mezcla varias reglas de divisor">varias reglas</span>'
                    rg = rr.pop()
                    if rg == "SITIOS_SIEMBRA":
                        v = sub["sitios_siembra"].max()
                    elif rg == "CENSO":
                        v = sub[sub["censo"] > 0].groupby("ubicacion")["censo"].max().sum()
                    elif rg == "SYRS_ARBOLES":
                        v = sub[sub["syrs_arboles"] > 0].groupby("ubicacion")["syrs_arboles"].max().sum()
                    elif rg == "PXN_KG":
                        # lotes: kg del lote (mes o año); Poscosecha y gastos sin lote: kg del año de toda la finca
                        v = kg_pxn(sub)
                    else:
                        v = arb_anio.get(int(sub["anio"].iloc[0]))
                    ic = DIV_REGLA.get(rg, ("🌳", ""))[0]
                    o = sub["origen_divisor"].astype(str)
                    hay_resp = o.str.startswith("Respaldo").any()      # parte del gasto se dividió por árboles vivos
                    arb_r = arb_anio.get(int(sub["anio"].iloc[0]))
                    if not v or pd.isna(v) or v <= 0:
                        if hay_resp and arb_r:
                            return (f'<span class="dv" style="color:#9A5B00" title="La regla {rg} no tiene dato aquí '
                                    f'(ej. lote sin censo): se dividió por los árboles vivos del año">'
                                    f'🌳 {pesos(arb_r)} árb. vivos (respaldo)</span>')
                        if o.str.contains("CU en blanco").all():
                            return f'<span class="dv" title="Regla {rg}: sin dato, el costo queda en blanco">{ic} sin dato</span>'
                        return f'<span class="dv" title="Regla {rg}: sin divisor en este período">{ic} sin divisor</span>'
                    extra = (' <span style="color:#9A5B00" title="Parte del gasto de esta celda no tiene dato de la regla '
                             '(ej. lote sin censo) y se dividió por los árboles vivos del año">+ respaldo</span>') if hay_resp else ""
                    return f'<span class="dv" title="Divisor de la regla {rg}">{ic} {pesos(v)} {UNI_DIV.get(rg, "")}{extra}</span>'

                def html_tabla_cu(t, nombre_c, b=None, bg=None, por_c=None):
                    """Tabla ejecutiva en HTML: el año arriba y, en una segunda línea, el divisor de su regla."""
                    cols = [c for c in t.columns if c not in (nombre_c, "Gasto total", "% del gasto", "_vs")]
                    con_vs = "_vs" in t.columns
                    b = base if b is None else b
                    b_todo = b           # todo el gasto de la tabla (para el TOTAL directo)
                    regla, part_r = regla_principal(b)
                    if regla:            # el encabezado usa solo las filas de la regla principal
                        b = b[b["regla_divisor"].map(norm_regla) == regla]
                    icono = DIV_REGLA.get(regla, ("🌳", ""))[0]
                    txt_cab = {}      # divisor del encabezado por columna: si la celda tiene el mismo, no se repite
                    div_cab = {}      # el número del divisor del encabezado, para el TOTAL directo
                    def th_anio(c):
                        if eje == "Año":
                            v, resp = divisor_anio(b, int(c), regla) if regla else (arb_anio.get(int(c)), False)
                            if resp and not v:
                                return f'<th class="anio">{c}</th>'   # el divisor va debajo de cada valor, no en el encabezado
                            if v and resp:
                                return f'<th class="anio">{c}</th>'   # el divisor va debajo de cada valor, no en el encabezado
                            if v:
                                uni = " kg" if regla == "PXN_KG" else ""
                                txt_cab[c] = f"{icono} {pesos(v)}"
                                div_cab[c] = v
                                return f'<th class="anio">{c}</th>'
                        return f'<th class="anio">{c}</th>'
                    cab = (f'<tr><th class="izq">{_html.escape(nombre_c)}</th><th>Gasto total</th><th>% del gasto</th>'
                           + (f'<th class="anio">Costo {vs_ref}</th><th class="anio">vs promedio<div class="sub">lotes {vs_ref}</div></th>'
                              if con_vs else "")
                           + "".join(th_anio(c) for c in cols)
                           + "</tr>")
                    filas_h = []
                    if bg is not None and por_c is not None:
                        _x_de = {(str(int(p)) if eje == "Año" else etiqueta(p)): p for p in bg["_x"].dropna().unique()}
                        _celdas = {k: g for k, g in bg.groupby([por_c, "_x"])}
                    else:
                        _x_de, _celdas = {}, {}

                    def celda_html(fila, col, val):
                        if pd.isna(val):
                            return "<td>—</td>"
                        sub = None
                        if fila == "TOTAL":
                            sub = bg[bg["_x"] == _x_de.get(col)] if bg is not None and col in _x_de else None
                        elif fila == "PROMEDIO LOTES":
                            sub = (bg[(bg["_x"] == _x_de.get(col)) & bg["ubicacion"].isin(lotes_cu)]
                                   if bg is not None and col in _x_de else None)
                        else:
                            sub = _celdas.get((fila, _x_de.get(col)))
                        dv = divisor_celda(sub) if sub is not None else ""
                        return f"<td>{unitario(val)}{dv}</td>"
                    hay_directo = eje == "Año" and bool(div_cab) and ver_pond
                    def celda_vs(v, costo_ref=None):
                        if not con_vs:
                            return ""
                        c_ref = f"<td style='font-weight:700;background:#FAFBFA'>{unitario(costo_ref)}</td>"
                        return c_ref + celda_vs_sola(v)

                    def celda_vs_sola(v):
                        if v == "general":
                            return '<td><span class="vs gen" title="Gasto general (sin lote): se reparte entre todos los árboles vivos">general</span></td>'
                        if v is None or pd.isna(v):
                            return "<td>—</td>"
                        clase_v = "alto" if v > 0.10 else ("bajo" if v < -0.10 else "medio")
                        return f'<td><span class="vs {clase_v}">{porcentaje(v)}</span></td>'
                    for _, r in t.iterrows():
                        clase = (' class="tot"' if r[nombre_c] == "TOTAL" else
                                 ' class="prom"' if r[nombre_c] == "PROMEDIO LOTES" else "")
                        nombre_f = "TOTAL ponderado" if (r[nombre_c] == "TOTAL" and hay_directo) else str(r[nombre_c])
                        pct_txt = f"{r['% del gasto']:.1%}".replace(".", ",")
                        filas_h.append(f"<tr{clase}><td class='izq'>{_html.escape(nombre_f)}</td>"
                                       f"<td>{millones(r['Gasto total'])}</td><td>{pct_txt}</td>"
                                       + celda_vs(r["_vs"] if con_vs else None, r[vs_ref] if con_vs else None)
                                       + "".join(celda_html(r[nombre_c], c, r[c]) for c in cols) + "</tr>")
                    if hay_directo:
                        # TOTAL directo: todo el gasto del año ÷ el divisor del encabezado (lo que costó cada unidad)
                        uni_d = {"PXN_KG": "kg", "SITIOS_SIEMBRA": "sitio sembrado", "CENSO": "árbol del censo",
                                 "SYRS_ARBOLES": "árbol sembrado"}.get(regla, "árbol vivo")
                        g_anio = b_todo.groupby("anio")["valor"].sum()
                        celdas_d = "".join(
                            f"<td>{unitario(g_anio.get(int(c), 0) / div_cab[c])}</td>" if c in div_cab and g_anio.get(int(c))
                            else "<td>—</td>" for c in cols)
                        filas_h.append(f"<tr class='dir'><td class='izq'>TOTAL directo<div class='dvl'>gasto ÷ {uni_d}"
                                       f"</div></td><td>{millones(b_todo['valor'].sum())}</td><td></td>{celdas_d}</tr>")
                    return f'<div class="tcu"><table><thead>{cab}</thead><tbody>{"".join(filas_h)}</tbody></table></div>'

                st.markdown("""<style>
                  .tcu { overflow-x:auto; border:1px solid #E5E7EB; border-radius:10px; margin:0.3rem 0 0.4rem 0; }
                  .tcu table { border-collapse:collapse; width:100%; font-size:0.81rem; font-variant-numeric:tabular-nums; }
                  .tcu th { background:#F6F8F5; color:#374151; font-weight:600; text-align:right; padding:0.32rem 0.45rem;
                            border-bottom:1px solid #E1E8DF; white-space:nowrap; vertical-align:bottom; }
                  .tcu th.anio { text-align:center; }
                  .tcu th .sub { display:table; margin:2px auto 0 auto; padding:0 6px; border-radius:999px;
                                 background:#E8F1E8; color:#1B5E20; font-weight:700; font-size:0.72rem; }
                  .tcu th .sub.resp { background:#FFF4E0; color:#9A5B00; }
                  .tcu td { text-align:right; padding:0.22rem 0.45rem; border-bottom:1px solid #F0F2F0; white-space:nowrap; }
                  .tcu td .dv { display:block; font-size:0.64rem; font-weight:400; color:#8A949B; line-height:1.1; margin-top:1px; }
                  .tcu .izq { text-align:left; white-space:normal; min-width:120px; max-width:190px; line-height:1.2; }
                  .tcu tbody tr:hover td { background:#F9FBF9; }
                  .tcu tr.tot td { font-weight:700; border-top:2px solid #CBD5CC; background:#FAFBFA; }
                  .tcu tr.dir td { font-weight:700; color:#1B5E20; background:#F1F7F1; border-top:1px dashed #B9D3BA; }
                  .tcu tr.prom td { font-weight:700; background:#F7FAF7; border-top:1px dashed #CBD5CC; }
                  .tcu .vs { display:inline-block; min-width:3.6rem; text-align:center; padding:1px 8px; border-radius:999px;
                             font-weight:700; font-size:0.76rem; }
                  .tcu .vs.alto { background:#FDECEA; color:#B42318; } .tcu .vs.bajo { background:#E7F5EC; color:#067647; }
                  .tcu .vs.medio { background:#F2F4F7; color:#475467; } .tcu .vs.gen { background:#F2F4F7; color:#98A2B3; font-weight:500; }
                  .tcu tr.dir .dvl { font-size:0.64rem; font-weight:400; color:#5B6B5E; }
                </style>""", unsafe_allow_html=True)

                def agrupar_resto(b, por_c, n=15):
                    """Para leer en una junta: los n de mayor gasto y el resto junto en 'Otras (k)'."""
                    g = b.groupby(por_c)["valor"].sum().sort_values(ascending=False)
                    if len(g) <= n + 1 or st.session_state.get("cu_ver_todas"):
                        return b
                    resto = g.index[n:]
                    return b.assign(**{por_c: b[por_c].where(~b[por_c].isin(resto), f"Otras ({len(resto)})")})

                if por == "ubicacion" and not ver_pond:
                    # Por lote: todos los lotes; lo que no es lote, junto en una fila
                    bg_cu = base.assign(ubicacion=base["ubicacion"].where(base["ubicacion"].isin(lotes_cu),
                                                                          "General (sin lote)"))
                else:
                    bg_cu = agrupar_resto(base, por)
                tabla_cu = armar(bg_cu, por, ver)
                # Nivel LOTE: costo real de cada lote frente al promedio de los lotes (del más caro al más barato)
                vs_ref = None
                if por == "ubicacion" and not ver_pond and eje == "Año":
                    cols_a = [c for c in tabla_cu.columns if c not in (ver, "Gasto total", "% del gasto")]
                    vs_ref = str(anio) if str(anio) in cols_a else (cols_a[-1] if cols_a else None)
                if vs_ref:
                    en_lote = bg_cu["ubicacion"].isin(lotes_cu)
                    if en_lote.any():
                        prom = {(str(int(x))): costo_directo(s_) for x, s_ in bg_cu[en_lote].groupby("_x")}
                        fila_p = {ver: "PROMEDIO LOTES", "Gasto total": bg_cu.loc[en_lote, "valor"].sum(),
                                  "% del gasto": bg_cu.loc[en_lote, "valor"].sum() / bg_cu["valor"].sum()}
                        fila_p.update({c: prom.get(c, np.nan) for c in cols_a})
                        p_ref = prom.get(vs_ref)
                        cuerpo = tabla_cu[~tabla_cu[ver].isin(["TOTAL"])].copy()
                        es_l = cuerpo[ver].isin(lotes_cu)
                        cuerpo["_vs"] = [(v / p_ref - 1) if (l and p_ref and pd.notna(v)) else ("general" if not l else None)
                                         for v, l in zip(cuerpo[vs_ref], es_l)]
                        lotes_t = cuerpo[es_l].sort_values(vs_ref, ascending=False, na_position="last")
                        otros_t = cuerpo[~es_l]
                        otras_t = otros_t[otros_t[ver].astype(str).str.startswith("Otras (")]
                        otros_t = otros_t[~otros_t[ver].astype(str).str.startswith("Otras (")]
                        tot_t = tabla_cu[tabla_cu[ver] == "TOTAL"].assign(_vs=None)
                        tabla_cu = pd.concat([lotes_t, otros_t, otras_t, pd.DataFrame([{**fila_p, "_vs": None}]), tot_t],
                                             ignore_index=True)
                cols_cu = [c for c in tabla_cu.columns if c not in (ver, "Gasto total", "% del gasto", "_vs")]
                st.markdown(html_tabla_cu(tabla_cu, ver, None, bg_cu, por), unsafe_allow_html=True)
                if base[por].nunique() > 16:
                    st.toggle(f"Ver todas las filas ({base[por].nunique()})", key="cu_ver_todas",
                              help="Por defecto se muestran los 15 de mayor gasto y el resto se junta en 'Otras'.")
                pro_a = base[base["origen_divisor"].astype(str).str.startswith("Propio de la regla")]
                if eje == "Año":
                    regla_t, part_t = regla_principal(base)
                    if regla_t:
                        resp_a = [int(a) for a in sorted(base["anio"].dropna().unique())
                                  if divisor_anio(base[base["regla_divisor"].map(norm_regla) == regla_t], int(a), regla_t)[1]] \
                            if regla_t != "ARB_TOTALVIVOS" else []
                        anios_r = ", ".join(map(str, resp_a))
                        if resp_a and regla_t == "PXN_KG":
                            txt_resp = f" ⚠️ {anios_r}: sin kg en PXN, queda en blanco."
                        elif resp_a and regla_t == "SITIOS_SIEMBRA":
                            txt_resp = f" ⚠️ {anios_r}: sin sitios sembrados en ARB_TOTAL, queda en blanco."
                        elif resp_a:
                            txt_resp = f" ⚠️ {anios_r} (naranja *): sin dato propio, se usó árboles vivos."
                        else:
                            txt_resp = ""
                        otras = ""
                        if part_t < 0.999:
                            otros_r = (base[base["regla_divisor"].map(norm_regla) != regla_t]
                                       .groupby(por)["valor"].sum().sort_values(ascending=False).index[:4])
                            otras = f" · {', '.join(map(str, otros_r))}: su propio divisor, en gris."
                        CORTO = {"PXN_KG": "kg cosechados", "CENSO": "árboles del censo", "SITIOS_SIEMBRA": "sitios sembrados",
                                 "SYRS_ARBOLES": "árboles sembrados/resembrados", "ARB_TOTALVIVOS": "árboles vivos"}
                        st.caption(f"Debajo de cada valor: con qué se dividió ({CORTO.get(regla_t, regla_t)}).{otras}{txt_resp}")
                    else:
                        reglas_t = ", ".join(sorted(str(x) for x in base["regla_divisor"].dropna().unique()))
                        st.caption("Cada fila usa su propia regla; debajo de cada valor se ve con qué se dividió.")
                    # Aviso automático cuando la base cambia mucho de un año a otro
                    serie = (pro_a.groupby("anio")["valor"].sum() / base.groupby("anio")["valor"].sum()).fillna(0)
                    serie = serie.reindex(sorted(base["anio"].dropna().unique())).fillna(0)
                    for b_a, a_a in zip(serie.index[:-1], serie.index[1:]):
                        if ver_pond and abs(serie[a_a] - serie[b_a]) >= 0.25:   # solo afecta al ponderado
                            st.warning(f"**Cambio de base en {int(a_a)}:** el gasto cargado a lotes pasó de "
                                       f"{serie[b_a]:.0%} a {serie[a_a]:.0%}. El ponderado de {int(a_a)} no es comparable "
                                       f"con el de {int(b_a)}: para comparar años use el costo por árbol vivo (más abajo).",
                                       icon="⚠️")


                # Pestañas desplegables: la misma tabla solo con mano de obra, y los insumos/servicios por DETALLE
                total_base = base["valor"].sum()
                mo_b = base[base["bloque"].isin(["Mano de obra (nómina)", "Mano de obra al contrato"])]
                ot_b = base[base["bloque"] == "Otros costos"]
                pct = lambda d: f"{d['valor'].sum() / total_base:.0%}" if total_base else "—"
                with st.expander(f"👷 Mano de obra · {millones(mo_b['valor'].sum())} ({pct(mo_b)} del gasto)"):
                    if mo_b.empty:
                        st.info("No hay mano de obra con estos filtros.")
                    else:
                        st.markdown(html_tabla_cu(armar(agrupar_resto(mo_b, por), por, ver), ver, mo_b),
                                    unsafe_allow_html=True)
                        st.caption("Nómina + mano de obra al contrato.")
                with st.expander(f"📦 Insumos, servicios y otros costos · {millones(ot_b['valor'].sum())} "
                                 f"({pct(ot_b)} del gasto)"):
                    if ot_b.empty:
                        st.info("No hay insumos ni servicios con estos filtros.")
                    else:
                        st.markdown(html_tabla_cu(armar(agrupar_resto(ot_b, "detalle"), "detalle", "Detalle"),
                                                  "Detalle", ot_b),
                                    unsafe_allow_html=True)
                        st.caption("Por la columna DETALLE del Excel.")
                if ver_pond:
                    st.caption("TOTAL ponderado: promedio según el gasto (Power BI), por eso no suma las filas. "
                               "TOTAL directo: gasto total del año ÷ divisor del encabezado = lo que costó cada unidad.")
                else:
                    st.caption("Cada valor es el costo real: gasto ÷ unidades. Si las filas usan las mismas unidades, "
                               "suman el TOTAL. Lo que no tiene lote o censo se reparte entre los árboles vivos.")

                # Gráfica: los 5 de mayor gasto (se pueden cambiar)
                opciones = [o for o in tabla_cu[ver] if o != "TOTAL" and not str(o).startswith("Otras (")]
                elegidos = st.multiselect("Graficar", opciones + ["TOTAL"], default=opciones[:5], placeholder="Elija qué graficar")
                if elegidos:
                    fig = go.Figure()
                    paleta = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
                    for i, nombre in enumerate(elegidos):
                        fila = tabla_cu[tabla_cu[ver] == nombre].iloc[0]
                        fig.add_scatter(x=cols_cu, y=[fila[c] for c in cols_cu], mode="lines+markers", name=nombre,
                                        line=dict(width=2, color=paleta[i % len(paleta)] if nombre != "TOTAL" else "#52514e"),
                                        hovertemplate=nombre + "<br>%{x}: %{y:,.2f}<extra></extra>")
                    fig.update_layout(height=360, separators=",.", title="Costo unitario ponderado",
                                      legend=dict(orientation="h", y=1.15, x=0), margin=dict(l=10, r=10, t=70, b=10),
                                      plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="rgba(128,128,128,0.2)"))
                    st.plotly_chart(fig, width="stretch")

                # De dónde salió el divisor (para saber qué tanto se apoya en el respaldo)
                origen = base.groupby("origen_divisor")["valor"].agg(["size", "sum"])
                origen["% del gasto"] = origen["sum"] / origen["sum"].sum()
                origen = origen.reset_index().rename(columns={"origen_divisor": "Origen del divisor",
                                                              "size": "Filas", "sum": "Gasto"})
                with st.expander("¿De dónde sale el divisor?"):
                    st.caption("'Respaldo: árboles vivos' = la regla del rubro no encontró dato (ej. insumos sin lote, "
                               "o lote sin censo ese año) y se usó el total de árboles vivos del año, igual que el Excel.")
                    st.dataframe(origen.style.format(pesos, subset=["Gasto"])
                                 .format(lambda v: f"{v:.1%}".replace(".", ","), subset=["% del gasto"]),
                                 hide_index=True)

                filas_xls = base.drop(columns=["_x", "huella"], errors="ignore")

                def excel_cu(b=base, f=filas_xls):
                    salida = io.BytesIO()
                    with pd.ExcelWriter(salida, engine="openpyxl") as w:
                        armar_tabla_directo(b, por, ver).to_excel(w, index=False, sheet_name="Costo unitario")
                        armar_tabla_cu(b, por, ver).to_excel(w, index=False, sheet_name="Ponderado Power BI")
                        f.to_excel(w, index=False, sheet_name="Detalle filas")
                    return salida.getvalue()
                # El Excel se arma solo al tocar el botón (antes se armaba en cada clic: unos 20 segundos)
                st.download_button("Descargar costo unitario en Excel", excel_cu,
                                   file_name=f"Costo_unitario_AGROCACAY_{'anual' if eje == 'Año' else 'mensual'}.xlsx")

            st.divider()
            st.subheader("Costo por árbol vivo · todos los rubros")

            def por_arbol(lista, a):
                arb_a = arb_anio.get(a)
                return suma(cu, lista) / arb_a if arb_a else None
            # Columnas: mes / acumulado / acumulado año anterior  (o, en año completo:
            # año / mismo periodo año anterior / año anterior completo)
            if anual:
                cols_pa = [(etq_acum, acum, anio), (etq_acum_ant, acum_ant, anio - 1)]
                if num_mes < 12:
                    cols_pa.append((f"Año {anio - 1} completo", anio_ant_completo, anio - 1))
                i_act, i_ant = 0, 1
            else:
                cols_pa = [(etiqueta(mes), [mes], anio), (etq_acum, acum, anio), (etq_acum_ant, acum_ant, anio - 1)]
                i_act, i_ant = 1, 2
            totales = [por_arbol(lista, a) for _, lista, a in cols_pa]
            k = st.columns(3)
            for i, (nombre, _, _) in enumerate(cols_pa):
                delta = (f"{porcentaje(variacion(totales[i_act], totales[i_ant]))} vs {cols_pa[i_ant][0]}"
                         if i == i_act else None)
                k[i].metric(f"Costo por árbol vivo — {nombre}", unitario(totales[i]), delta, delta_color="inverse")
            # Separado en mano de obra y otros costos
            filas_pa = []
            for nombre in [x for x in BLOQUES if x in set(cu["bloque"])] + ["TOTAL"]:
                cb = cu if nombre == "TOTAL" else cu[cu["bloque"] == nombre]
                vals = [suma(cb, lista) / arb_anio.get(a) if arb_anio.get(a) else None for _, lista, a in cols_pa]
                fila = {"Concepto": nombre}
                fila.update({cols_pa[i][0]: unitario(v) for i, v in enumerate(vals)})
                fila["Variación"] = porcentaje(variacion(vals[i_act], vals[i_ant]))
                filas_pa.append(fila)
            st.dataframe(pd.DataFrame(filas_pa).style.apply(
                lambda r: ["font-weight: bold" if (i == 0 and r.iloc[0] == "TOTAL") else ""
                           for i, _ in enumerate(r)], axis=1),
                hide_index=True, width="stretch")
            st.caption(f"Gasto del periodo ÷ árboles vivos del año (hoja ARB_TOTAL: "
                       f"{pesos(arb_anio.get(anio))} en {anio}, {pesos(arb_anio.get(anio - 1))} en {anio - 1}).")


# ===============================================================
# 6. PESTAÑA GERENTES
# ===============================================================
with pest[3]:
    g = df[df["gerente"].isin(C.GERENTES)]
    if g.empty:
        st.info("No hay gastos marcados a gerentes con estos filtros. "
                "Hoy la marca de gerente (columna GERENTES) solo existe en el Excel de KAHAI.")
    else:
        st.caption(f"Gastos marcados en la columna de gerentes: {', '.join(C.GERENTES)}")
        k = st.columns(len(C.GERENTES))
        for i, ger in enumerate(C.GERENTES):
            gi = g[g["gerente"] == ger]
            k[i].metric(f"{ger} — {etq_sel}", millones(suma(gi, seleccion)))
            if not anual:
                k[i].caption(f"Acumulado {etq_acum}: {millones(suma(gi, acum))}")
        rango = [anio * 100 + m for m in range(1, 13)] if anual else [mover(mes, -k) for k in range(11, -1, -1)]
        tg = g[g["periodo"].isin(rango)].pivot_table(index=["gerente", "ceco", "rubro"], columns="periodo",
                                                    values="valor", aggfunc="sum", fill_value=0)
        tg = tg.reindex(columns=rango, fill_value=0)
        tg.columns = [etiqueta(p) for p in tg.columns]
        tg["Total 12 meses"] = tg.sum(axis=1)
        tg = tg.reset_index().rename(columns={"gerente": "Gerente", "ceco": "CECO", "rubro": "Rubro"})
        st.dataframe(tg.style.format(pesos, subset=[c for c in tg.columns if c not in ("Gerente", "CECO", "Rubro")]),
                     hide_index=True, width="stretch")


# ===============================================================
# 7. PESTAÑA INTERCOMPAÑÍA
# ===============================================================
with pest[4]:
    ic = base_empresa[base_empresa["naturaleza"] == "Intercompañía"]
    st.caption("Compras de una empresa a su hermana (el tercero es AGROCACAY o KAHAI). "
               "Para quien compra son costo real. En la vista Grupo se suman tal como vienen en los Excel; "
               "para sacarlas, quite 'Intercompañía' en Naturaleza.")
    if ic.empty:
        st.info("No hay movimientos intercompañía para esta vista.")
    else:
        resumen = ic.assign(Año=ic["periodo"] // 100).pivot_table(
            index="Año", columns="empresa", values="valor", aggfunc="sum", fill_value=0)
        resumen.columns = [f"Compra {e}" for e in resumen.columns]
        st.dataframe(resumen.reset_index().style.format(pesos, subset=list(resumen.columns)),
                     hide_index=True)
        lista = ic.sort_values("periodo", ascending=False)[
            ["empresa", "periodo", "fecha", "ceco", "rubro", "detalle", "tercero", "actividad", "documento", "valor"]]
        lista["periodo"] = lista["periodo"].map(etiqueta)
        st.dataframe(lista.rename(columns=str.capitalize).style.format(pesos, subset=["Valor"]),
                     hide_index=True, width="stretch")


# ===============================================================
# 8. PESTAÑA MOVIMIENTOS DEL MES
# ===============================================================
with pest[5]:
    c1, c2 = st.columns([1, 2])
    meses_mov = c1.multiselect("Meses", periodos[::-1], default=(acum if todos else seleccion)[::-1], format_func=etiqueta,
                               placeholder="Elija meses")
    buscar = c2.text_input("Buscar (tercero, descripción, actividad, documento, rubro...)")
    m = df[df["periodo"].isin(meses_mov)]
    if buscar:
        texto = pd.Series("", index=m.index)
        for col in ["tercero", "descripcion", "actividad", "documento", "rubro", "detalle", "ceco"]:
            texto = texto + " " + m[col].fillna("").astype(str)
        m = m[texto.str.contains(buscar, case=False, regex=False)]
    cols = ["empresa", "fila_excel", "periodo", "fecha", "ceco", "rubro", "detalle", "ubicacion",
            "actividad", "tercero", "descripcion", "documento", "tipo", "naturaleza", "valor"]
    m = m[cols].sort_values("valor", ascending=False)
    st.caption(f"{len(m):,} movimientos · total {millones(m['valor'].sum())}".replace(",", "."))
    vista_m = m.head(5000).assign(periodo=lambda x: x["periodo"].map(etiqueta))
    st.dataframe(vista_m.style.format(pesos, subset=["valor"]) if len(vista_m) <= 3000 else vista_m,
                 hide_index=True, width="stretch", height=550)
    if len(m) > 5000:
        st.caption("Se muestran los 5.000 de mayor valor; la descarga trae todos.")
    def excel_mov(m=m):
        salida = io.BytesIO()
        m.to_excel(salida, index=False, sheet_name="Movimientos")
        return salida.getvalue()
    st.download_button("Descargar movimientos en Excel", excel_mov,
                       file_name=f"Movimientos_{vista.split()[0]}.xlsx")


# ===============================================================
# 9. PESTAÑA CARGAS (historial de aprobaciones)
# ===============================================================
with pest[6]:
    if historial.empty:
        st.info("Aún no hay historial.")
    else:
        h = historial[historial["empresa"].isin(empresas_vista)][
            ["empresa", "fecha_lectura", "fecha_archivo", "filas", "total_valor", "nuevas", "borradas",
             "valor_nuevas", "valor_borradas", "alertas", "estado", "responsable", "fecha_decision", "comentario"]]
        h = h.rename(columns={"empresa": "Empresa", "fecha_lectura": "Leído", "fecha_archivo": "Excel guardado",
                              "filas": "Filas", "total_valor": "Total", "nuevas": "Nuevas", "borradas": "Borradas",
                              "valor_nuevas": "Valor nuevas", "valor_borradas": "Valor borradas",
                              "alertas": "Alertas", "estado": "Estado", "responsable": "Responsable",
                              "fecha_decision": "Decisión", "comentario": "Comentario"})
        st.dataframe(h.style.format(pesos, subset=["Total", "Valor nuevas", "Valor borradas"]),
                     hide_index=True, width="stretch")
