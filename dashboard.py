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

  /* Barra de filtros */
  .st-key-barra_filtros {{ margin-top:0.5rem; }}
  .st-key-bloque_periodo, .st-key-bloque_alcance {{ background:#FFFFFF; border:1px solid #E1E8DF;
        border-radius:12px; padding:0.45rem 0.9rem 0.15rem 0.9rem; box-shadow:0 1px 3px rgba(16,24,40,0.06);
        height:100%; gap:0.35rem; }}
  .st-key-bloque_periodo [data-testid="stVerticalBlock"],
  .st-key-bloque_alcance [data-testid="stVerticalBlock"] {{ gap:0.35rem; }}
  .st-key-barra_filtros [data-testid="stWidgetLabel"] {{ margin-bottom:0.1rem; min-height:0; }}
  .st-key-bloque_periodo {{ border-top:4px solid {VERDE}; }}
  .st-key-bloque_alcance {{ border-top:4px solid var(--acento); }}
  .frase {{ margin:0 0 0.45rem 0; padding:0.35rem 0.7rem; border-radius:10px; background:#F3F7F3;
             font-size:0.85rem; color:#374151; }}
  a.restablecer {{ font-size:0.82rem; color:#5B6B5E !important; text-decoration:none; white-space:nowrap; }}
  a.restablecer:hover {{ color:{VERDE} !important; text-decoration:underline; }}
  .st-key-barra_filtros label p {{ font-size:0.74rem !important; font-weight:700 !important;
                                   text-transform:uppercase; letter-spacing:0.6px; color:#5B6B5E !important; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] button {{ border-radius:999px; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[aria-pressed="true"],
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[aria-checked="true"],
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[kind$="Active"] {{
        background:{VERDE} !important; border-color:{VERDE} !important; color:#fff !important; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[aria-pressed="true"] p,
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[aria-checked="true"] p,
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[kind$="Active"] p {{ color:#fff !important; }}

  /* Empresa: AGROCACAY y KAHAI una debajo de la otra; Grupo en su propia columna (alto completo) */
  .st-key-f_empresa [role="radiogroup"] {{ display:grid !important; grid-template-columns:auto auto;
        grid-template-rows:auto auto; gap:6px 8px; overflow:visible !important; width:fit-content; }}
  .st-key-f_empresa [role="radiogroup"] > button {{ border-radius:10px !important; width:100%;
        border:1px solid #CBD5CC !important; margin:0 !important; }}
  .st-key-f_empresa [role="radiogroup"] > button:nth-child(1) {{ grid-column:1; grid-row:1; }}
  .st-key-f_empresa [role="radiogroup"] > button:nth-child(2) {{ grid-column:1; grid-row:2; }}
  .st-key-f_empresa [role="radiogroup"] > button:nth-child(3) {{ grid-column:2; grid-row:1 / span 2; height:auto; }}
  .st-key-f_empresa [role="radiogroup"] > button[data-selected="true"] {{
        background:{VERDE} !important; border-color:{VERDE} !important; }}
  .st-key-f_empresa [role="radiogroup"] > button[data-selected="true"] p {{ color:#fff !important; font-weight:600; }}
  /* Año: 6 por fila (Todos + 5 años arriba, el resto abajo) */
  .st-key-f_anio [role="toolbar"], .st-key-f_anio [role="radiogroup"] {{ display:grid !important;
        grid-template-columns:repeat(6, minmax(3.6rem, max-content)); gap:6px; overflow:visible !important; }}
  .st-key-f_anio button {{ margin:0 !important; justify-content:center; }}
  /* Naturaleza: 2 x 2 */
  .st-key-f_naturaleza [role="toolbar"] {{ display:grid !important; grid-template-columns:repeat(2, 1fr);
        gap:6px; overflow:visible !important; width:fit-content; }}
  .st-key-f_naturaleza [role="toolbar"] > button {{ width:100%; margin:0 !important; }}
  /* Tipo de gasto: Nómina y Terceros uno debajo del otro */
  .st-key-f_tipo [role="toolbar"] {{ display:grid !important; grid-template-columns:7.5rem; gap:6px;
        width:fit-content; overflow:visible !important; }}
  .st-key-f_tipo [role="toolbar"] > button {{ width:100%; margin:0 !important; }}

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

# ---- Filtros arriba, en dos bloques: PERIODO (cuándo) y ALCANCE (qué se mira) ----
with st.container(key="barra_filtros"):
    col_alcance, col_periodo = st.columns([0.8, 1.5], gap="small")
    bloque_periodo = col_periodo.container(key="bloque_periodo")
    bloque_alcance = col_alcance.container(key="bloque_alcance")

    # ALCANCE: empresa, tipo y naturaleza (va primero en el código: los años dependen de la empresa)
    with bloque_alcance:
        a1, a2 = st.columns([1.6, 1], gap="small")
        vista = boton_unico(a1, "Empresa", ["AGROCACAY", "KAHAI", GRUPO], "AGROCACAY", "f_empresa",
                            "Las empresas se ven por separado. 'Grupo' suma las dos.", segmentado=True)
        tipos = a2.pills("Tipo de gasto", ["Nómina", "Terceros"], selection_mode="multi",
                         default=["Nómina", "Terceros"], key="f_tipo",
                         help="Nómina = empleados de la empresa. Terceros = todo lo demás: proveedores, "
                              "contratistas, servicios, impuestos, bancos. Los dos encendidos = gasto total.")
        naturalezas = st.pills(
            "Naturaleza del gasto", ["Operativo", "Intercompañía", "Financiero", "Inversión"],
            selection_mode="multi", default=C.NATURALEZAS_POR_DEFECTO, key="f_naturaleza",
            help="Toque para activar o quitar. Financiero = CECO FINANCIERO (intereses, créditos). "
                 "Inversión = CECO ACTIVOS. Intercompañía = compras a la empresa hermana.")
    empresas_vista = list(C.EMPRESAS) if vista == GRUPO else [vista]
    base_empresa = datos[datos["empresa"].isin(empresas_vista)]
    periodos = sorted(base_empresa["periodo"].unique())

    # PERIODO: año y mes ("Todos" = todos los años, una columna por año)
    with bloque_periodo:
        anios = sorted({p // 100 for p in periodos})
        TODOS_ANIOS = "Todos"
        anio_sel = boton_unico(st, "Año", [TODOS_ANIOS] + anios, anios[-1], "f_anio")
        todos = anio_sel == TODOS_ANIOS
        anio = anios[-1] if todos else anio_sel
        meses_del_anio = [p % 100 for p in periodos if p // 100 == anio]
        AÑO_COMPLETO = "Año completo"
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
            else:
                frase = f"{mes_txt} de cada año · una columna por año, para ver cómo se comporta ese mes en el tiempo"
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
            else:
                n_m = [k for k, v in NOMBRE_MES.items() if v == mes_txt][0]
                previo = f"{NOMBRE_MES[n_m - 1]}-{anio}" if n_m > 1 else f"Dic-{anio - 1}"
                frase = (f"{mes_txt}-{anio} · se compara con {previo} (mes anterior) y "
                         f"{mes_txt}-{anio - 1} (año anterior)")
        r1, r2 = st.columns([5, 1.1], gap="small", vertical_alignment="center")
        r1.markdown(f'<div class="frase">📌 {frase}</div>', unsafe_allow_html=True)
        # Restablecer = volver a abrir la página (empieza limpia; la sesión de Google se mantiene)
        r2.markdown('<a class="restablecer" href="./" target="_self" '
                    'title="Vuelve todos los filtros a como abre la app">↺ Restablecer</a>', unsafe_allow_html=True)

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
    c1, c2 = st.columns([2, 3])
    niveles = c1.multiselect("Niveles (en orden)", list(NIVELES), default=["CECO", "Rubro", "Detalle"],
                             help="Se agrupa en el orden en que se eligen. Actividad y Tercero "
                                  "tienen miles de valores: úselos con pocos meses o filtrando.")
    desde, hasta = c2.select_slider("Meses", options=periodos, format_func=etiqueta,
                                    value=((acum[0], mes) if todos else (seleccion[0], mes) if anual
                                           else (max(periodos[0], mover(mes, -11)), mes)))
    if not niveles:
        st.info("Elija al menos un nivel.")
    else:
        campos = (["empresa"] if vista == GRUPO else []) + [NIVELES[n] for n in niveles]
        meses_rango = [p for p in periodos if desde <= p <= hasta]
        d = df[df["periodo"].isin(meses_rango)]
        piv = d.pivot_table(index=campos, columns="periodo", values="valor", aggfunc="sum", fill_value=0)
        piv = piv.reindex(columns=meses_rango, fill_value=0)
        piv.columns = [etiqueta(p) for p in piv.columns]
        piv["Total"] = piv.sum(axis=1)
        piv = piv.reset_index()

        # Subtotal por el primer nivel cuando hay más de un nivel
        subt = st.checkbox("Mostrar subtotales por el primer nivel", value=len(campos) > 1)
        cols_num = [c for c in piv.columns if c not in campos]
        total = pd.DataFrame([{**{c: "" for c in campos}, **piv[cols_num].sum()}])
        total[campos[0]] = "TOTAL"
        if subt and len(campos) > 1:
            primero = campos[0]
            sub = piv.groupby(primero)[cols_num].sum().reset_index()
            for c in campos[1:]:
                sub[c] = ""
            sub[campos[1]] = "▸ SUBTOTAL"
            sub["_orden"] = 0
            piv["_orden"] = 1
            piv = pd.concat([sub, piv]).sort_values([primero, "_orden", "Total"],
                                                    ascending=[True, True, False]).drop(columns="_orden")
        piv = pd.concat([piv, total], ignore_index=True)[campos + cols_num]   # niveles primero
        nombres = {"empresa": "Empresa", **{v: k for k, v in NIVELES.items()}}
        piv = piv.rename(columns=nombres)
        etiquetas = [nombres[c] for c in campos]

        st.caption(f"{len(piv) - 1:,} filas".replace(",", "."))
        resaltar = lambda r: ["font-weight: bold; background-color: rgba(128,128,128,0.12)"
                              if (r.iloc[0] == "TOTAL" or (len(etiquetas) > 1 and r[etiquetas[1]] == "▸ SUBTOTAL"))
                              else "" for _ in r]
        if len(piv) > 3000:
            st.warning("Más de 3.000 filas: se muestran sin formato. Reduzca niveles o meses.")
            st.dataframe(piv, hide_index=True, width="stretch", height=600)
        else:
            st.dataframe(piv.style.format(pesos, subset=cols_num).apply(resaltar, axis=1),
                         hide_index=True, width="stretch", height=600)

        def excel_tabla(piv=piv):
            salida = io.BytesIO()
            piv.to_excel(salida, index=False, sheet_name="Tabla mensual")
            return salida.getvalue()
        # El Excel se arma solo al tocar el botón (antes se armaba en cada clic y hacía lenta la app)
        st.download_button("Descargar en Excel", excel_tabla,
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
    return cu, ultimo


def ponderado(d, por, eje):
    """Medida DAX 'Costo Unitario Ponderado' de Power BI (la misma de la app de campo):
       grupos (mes, lote, regla): vDebito = suma débito; vDivisor = máx divisor; vCU = vDebito / vDivisor
       resultado = suma(vDebito × vCU) / suma(vDebito)
    El lote siempre queda en el grupo más fino porque el divisor depende del lote."""
    llaves = [c for c in [por, eje] if c]
    finas = llaves + [c for c in ["mes", "ubicacion", "regla_divisor"] if c not in llaves]
    g = d.groupby(finas, dropna=False).agg(
        vDebito=("valor", "sum"), vDivisor=("divisor", "max")).reset_index()
    g["vCU"] = np.where((g["vDivisor"] == 0) | g["vDivisor"].isna(), np.nan, g["vDebito"] / g["vDivisor"])
    g["prod"] = g["vDebito"] * g["vCU"]
    if not llaves:
        tot = g["vDebito"].sum()
        return g["prod"].sum() / tot if tot else None
    r = g.groupby(llaves).agg(prod=("prod", "sum"), deb=("vDebito", "sum"))
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
        lineas.append({"seccion": r["seccion"], "linea": r["linea"], "divisor": r["divisor"],
                       "costo": costo, "mo": mo})

    def cpk(costo, divisor, a):
        kg_a = kg.get((divisor, a))
        c = costo.get(a, 0)
        return (c / kg_a) if kg_a else None, c, kg_a

    # ---- Tarjetas: el año elegido arriba (o el último con divisores)
    a_ref = anio if anio in anios_p else anios_p[-1]
    def total_seccion(sec, a):
        vals = [cpk(l["costo"], l["divisor"], a)[0] for l in lineas if l["seccion"] == sec]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None
    def primera(sec, a):
        l = next((l for l in lineas if l["seccion"] == sec), None)
        return cpk(l["costo"], l["divisor"], a)[0] if l else None
    t1, t2, t3, t4 = st.columns(4)
    for col, nombre, f in [(t1, "Concha procesada", lambda a: primera("Poscosecha", a)),
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
        siguiente = lineas[lineas.index(l) + 1]["seccion"] if lineas.index(l) + 1 < len(lineas) else None
        n_sec = sum(1 for x in lineas if x["seccion"] == sec_actual)
        if siguiente != sec_actual and n_sec > 1 and sec_actual.lower().startswith("aceite"):
            tot = [total_seccion(sec_actual, a) for a in anios_p]
            filas.append(f"<tr class='tot'><td class='izq' colspan='2'>Costo kg aceite (suma)</td>"
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


with pest[2]:
    if vista == "KAHAI":
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

            # ---- FICHA POR RUBRO (vista de gerencia): costo por árbol al año, por componente y por lote
            st.subheader("🔎 Ficha por rubro")
            st.caption("Lectura directa: **gasto del año ÷ árboles**. Las partes suman el total, se puede "
                       "comparar año contra año y filtrar por lote.")
            lotes_cu = sorted(datos_cu.loc[datos_cu["censo"] > 0, "ubicacion"].unique(), key=orden_lote)
            gasto_rubro = cu.groupby("rubro")["valor"].sum().sort_values(ascending=False)
            fr1, fr2, fr3 = st.columns([1.3, 1.3, 2.4])
            rubro_f = fr1.selectbox("Rubro", list(gasto_rubro.index),
                                    index=list(gasto_rubro.index).index("MIAR") if "MIAR" in gasto_rubro.index else 0,
                                    key="ficha_rubro")
            ceco_f = fr2.multiselect("CECO", sorted(cu.loc[cu["rubro"] == rubro_f, "ceco"].unique()),
                                     placeholder="Todos", key="ficha_ceco")
            lote_f = fr3.multiselect("Lote", lotes_cu, placeholder="Toda la finca (todos los lotes y lo general)",
                                     key="ficha_lote",
                                     help="Sin lote elegido: gasto total del rubro ÷ árboles vivos del año. "
                                          "Con lotes: solo el gasto cargado a esos lotes ÷ sus árboles del censo.")
            fi = cu[cu["rubro"] == rubro_f]
            if ceco_f:
                fi = fi[fi["ceco"].isin(ceco_f)]
            fi = fi.assign(componente=componente_gerencial(fi))
            if lote_f:
                fi_l = fi[fi["ubicacion"].isin(lote_f)]
                # árboles de la base: censo de los lotes elegidos, cada año
                arboles_base = (datos_cu[datos_cu["ubicacion"].isin(lote_f)]
                                .groupby(["anio", "ubicacion"])["censo"].max().groupby("anio").sum())
                texto_base = f"árboles del censo de {', '.join(lote_f) if len(lote_f) <= 4 else str(len(lote_f)) + ' lotes'}"
            else:
                fi_l = fi
                arboles_base = arb_anio
                texto_base = "árboles vivos de la finca (hoja ARB_TOTAL)"
            anios_f = sorted(fi_l["anio"].dropna().unique().astype(int))

            if fi_l.empty or not anios_f:
                st.info("No hay gasto de este rubro con estos filtros.")
            else:
                gasto_anio = fi_l.groupby("anio")["valor"].sum()
                cpa = (gasto_anio / arboles_base.reindex(gasto_anio.index).replace(0, np.nan))
                a_ref = anio if anio in cpa.index else anios_f[-1]
                mo = fi_l[fi_l["bloque"].isin(["Mano de obra (nómina)", "Mano de obra al contrato"])]
                pct_mo = None
                if gasto_anio.get(a_ref):
                    pct_mo = mo.loc[mo["anio"] == a_ref, "valor"].sum() / gasto_anio.get(a_ref)
                # ¿El año de referencia está completo? (si no, se compara contra los mismos meses del año anterior)
                ult_mes = int(datos_cu.loc[datos_cu["anio"] == a_ref, "mes_num"].max())
                parcial = ult_mes < 12
                hasta = f" (Ene–{NOMBRE_MES[ult_mes]})" if parcial else ""
                g_prev = fi_l[(fi_l["anio"] == a_ref - 1) & (fi_l["mes_num"] <= ult_mes)]["valor"].sum()
                arb_prev = arboles_base.get(a_ref - 1)
                cpa_prev = g_prev / arb_prev if arb_prev and g_prev else None
                k1, k2, k3, k4 = st.columns(4)
                k1.metric(f"Costo por árbol {a_ref}{hasta}", unitario(cpa.get(a_ref)),
                          f"{porcentaje(variacion(cpa.get(a_ref), cpa_prev))} vs {a_ref - 1}{hasta}"
                          if cpa_prev else None, delta_color="inverse")
                k2.metric(f"Gasto {a_ref}{hasta}", millones(gasto_anio.get(a_ref, 0)))
                k3.metric("Árboles de la base", pesos(arboles_base.get(a_ref)), help=texto_base)
                k4.metric("Peso de la mano de obra", "—" if pct_mo is None else f"{pct_mo:.0%}",
                          help="Mano de obra de nómina + al contrato, como % del gasto del rubro")
                if parcial:
                    st.caption(f"{a_ref} va hasta {NOMBRE_MES[ult_mes]}: en las tablas de abajo su valor es parcial.")

                t_comp, t_lote = st.tabs(["👷 Mano de obra vs otros costos", "📍 Por lote"])
                cols_anio = [str(a) for a in anios_f]

                with t_comp:
                    comp = fi_l.groupby(["componente", "anio"])["valor"].sum().unstack("anio")
                    comp = comp.div(arboles_base.reindex(comp.columns).replace(0, np.nan), axis=1)
                    orden_c = [c for c in ["Mano de obra (nómina)", "Mano de obra al contrato"] if c in comp.index]
                    resto = [c for c in comp.index if c not in orden_c and c not in ("Otros (resto)",
                                                                                     "Intercompañía", "Financiero",
                                                                                     "Inversión")]
                    orden_c += sorted(resto, key=lambda c: -comp.loc[c].fillna(0).sum())
                    orden_c += [c for c in ["Otros (resto)", "Intercompañía", "Financiero", "Inversión"]
                                if c in comp.index]
                    comp = comp.reindex(orden_c)
                    # para la variación: mismo tramo de meses del año anterior (si el último año va incompleto)
                    a_ult, a_pen = anios_f[-1], (anios_f[-2] if len(anios_f) >= 2 else None)
                    prev = fi_l[fi_l["anio"] == a_pen]
                    if a_ult == a_ref and parcial:
                        prev = prev[prev["mes_num"] <= ult_mes]
                    comp_prev = (prev.groupby("componente")["valor"].sum()
                                 / (arboles_base.get(a_pen) or np.nan)).reindex(comp.index)
                    comp = comp.assign(_prev=comp_prev)
                    filas_c = []
                    n_mo = len([c for c in orden_c if c.startswith("Mano de obra")])
                    sub_mo = comp.iloc[:n_mo].sum(min_count=1)
                    for i, (nombre, fila) in enumerate(comp.iterrows()):
                        filas_c.append([("   " if nombre.startswith("Mano de obra") else "") + nombre] + list(fila))
                        if n_mo and i == n_mo - 1:
                            filas_c.append(["Subtotal mano de obra"] + list(sub_mo))
                    filas_c.append(["TOTAL"] + list(comp.sum(min_count=1)))
                    tabla_c = pd.DataFrame(filas_c, columns=["Componente"] + cols_anio + ["_prev"])
                    if a_pen is not None:
                        tramo = f" ({hasta.strip(' ()')})" if (a_ult == a_ref and parcial) else ""
                        tabla_c[f"Var. {a_ult} vs {a_pen}{tramo}"] = [porcentaje(variacion(a, b)) for a, b in
                                                                       zip(tabla_c[str(a_ult)], tabla_c["_prev"])]
                    tabla_c = tabla_c.drop(columns="_prev")
                    comp = comp.drop(columns="_prev")
                    vis = tabla_c.copy()
                    for c in cols_anio:
                        vis[c] = vis[c].map(unitario)
                    # Fila del divisor: con qué número de árboles se dividió cada año
                    nombre_div = "Divisor · árboles censo lotes" if lote_f else "Divisor · árboles vivos"
                    fila_div = {"Componente": nombre_div}
                    fila_div.update({c: pesos(arboles_base.get(int(c))) if arboles_base.get(int(c)) else "—"
                                     for c in cols_anio})
                    vis = pd.concat([vis, pd.DataFrame([fila_div])], ignore_index=True).fillna("")
                    if parcial and str(a_ref) in vis.columns:
                        vis = vis.rename(columns={str(a_ref): f"{a_ref}{hasta}"})
                    negrita = lambda r: (["font-weight: bold" for _ in r]
                                         if r.iloc[0] in ("TOTAL", "Subtotal mano de obra") else
                                         ["font-style: italic; color: #5B6470; background-color: #F6F8F5" for _ in r]
                                         if str(r.iloc[0]).startswith("Divisor") else ["" for _ in r])
                    st.dataframe(vis.style.apply(negrita, axis=1), hide_index=True, width="stretch")
                    st.caption(f"Pesos por árbol al año = gasto del componente ÷ {texto_base}. "
                               "'Otros costos' se abre en sus 3 detalles más grandes.")
                    # gráfica apilada: cuánto de cada peso por árbol es mano de obra
                    fig_c = go.Figure()
                    paleta_c = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6", "#008300", "#52514e"]
                    for i, (nombre, fila) in enumerate(comp.iterrows()):
                        fig_c.add_bar(x=cols_anio, y=fila.values, name=nombre, marker_color=paleta_c[i % len(paleta_c)],
                                      hovertemplate=nombre + "<br>%{x}: $%{y:,.0f} por árbol<extra></extra>")
                    fig_c.update_layout(barmode="stack", height=340, separators=",.", bargap=0.35,
                                        title=f"{rubro_f}: pesos por árbol al año",
                                        legend=dict(orientation="h", y=1.18, x=0), margin=dict(l=10, r=10, t=80, b=10),
                                        plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="rgba(128,128,128,0.2)"))
                    st.plotly_chart(fig_c, width="stretch")

                with t_lote:
                    en_lote = fi[fi["ubicacion"].isin(lotes_cu)]
                    if lote_f:
                        en_lote = en_lote[en_lote["ubicacion"].isin(lote_f)]
                    if en_lote.empty:
                        st.info("Este rubro no tiene gasto cargado a lotes (todo es general de la finca).")
                    else:
                        g_l = en_lote.groupby(["ubicacion", "anio"])["valor"].sum()
                        a_l = (datos_cu[datos_cu["ubicacion"].isin(g_l.index.get_level_values(0))]
                               .groupby(["ubicacion", "anio"])["censo"].max())
                        t_l = (g_l / a_l.reindex(g_l.index).replace(0, np.nan)).unstack("anio")
                        t_l = t_l.reindex(sorted(t_l.index, key=orden_lote))
                        t_l.columns = [str(int(c)) for c in t_l.columns]
                        gasto_l = en_lote[en_lote["anio"] == a_ref].groupby("ubicacion")["valor"].sum()
                        vis_l = t_l.copy()
                        for c in vis_l.columns:
                            vis_l[c] = vis_l[c].map(unitario)
                        vis_l.insert(0, f"Gasto {a_ref}", gasto_l.reindex(t_l.index).fillna(0).map(millones))
                        vis_l.insert(1, f"Árboles {a_ref}", a_l.xs(a_ref, level="anio").reindex(t_l.index).map(pesos)
                                     if a_ref in a_l.index.get_level_values("anio") else "—")
                        st.dataframe(vis_l.reset_index().rename(columns={"ubicacion": "Lote"}),
                                     hide_index=True, width="stretch", height=min(38 * (len(vis_l) + 1) + 4, 520))
                        sin_lote = fi[~fi["ubicacion"].isin(lotes_cu) & (fi["anio"] == a_ref)]["valor"].sum()
                        st.caption(f"Pesos por árbol al año = gasto cargado al lote ÷ árboles del lote en el censo de ese año. "
                                   f"Además, {millones(sin_lote)} de {a_ref} no están cargados a ningún lote "
                                   "(compras generales de insumos, maquinaria, herramientas): esos solo entran en la vista "
                                   "de toda la finca.")


            st.divider()
            # ---- Tabla ponderada (igual a la de la app de campo / Power BI)
            st.subheader("Costo unitario ponderado")
            st.caption("Cada mes: costo ÷ divisor de su regla (árboles del censo, kg cosechados, sitios sembrados "
                       "o árboles vivos). Varios meses o lotes se promedian ponderando por lo que se gastó en cada uno "
                       "— la misma medida 'Costo Unitario Ponderado' de Power BI.")
            # Recorrido como en una junta: la empresa ya está en el encabezado; aquí se baja
            # CECO → Rubro → Actividad → Ubicación. La tabla muestra siempre el SIGUIENTE nivel
            # al último elegido (sin CECO elegido: una fila por CECO; con CECO: una por rubro; etc.).
            NIVELES = [("CECO", "ceco"), ("Rubro", "rubro"), ("Actividad", "actividad"), ("Ubicación", "ubicacion")]
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
                ver, por = "Detalle", "descripcion"
            ruta = " › ".join([titulo_vista] + elegidos_n)
            st.markdown(f'<div class="frase">📍 <b>{ruta}</b> &nbsp;·&nbsp; filas por <b>{ver}</b></div>',
                        unsafe_allow_html=True)

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

                # Divisor que se muestra debajo de cada año: el de la REGLA de lo que hay en la tabla
                # (Siembra -> sitios sembrados del año; MIAR, Nutrición -> censo de los lotes; Cosecha -> kg; etc.)
                DIV_REGLA = {"SITIOS_SIEMBRA": ("🌱", "sitios sembrados en el año (hoja ARB_TOTAL, derecha)"),
                             "CENSO": ("🌳", "árboles del censo de los lotes con gasto"),
                             "PXN_KG": ("⚖️", "kg cosechados"),
                             "SYRS_ARBOLES": ("🌱", "árboles sembrados/resembrados (SYRS)"),
                             "ARB_TOTALVIVOS": ("🌳", "árboles vivos de la finca (ARB_TOTAL)")}

                def regla_de(b):
                    rr = {str(x).upper() for x in b["regla_divisor"].dropna().unique()}
                    rr = {"ARB_TOTALVIVOS" if x in ("—", "ARB_TOTALVIVOS") else x for x in rr}
                    return rr.pop() if len(rr) == 1 else None      # None = varias reglas mezcladas

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
                        v = ba[ba["pxn_kg"] > 0].groupby(["mes", "ubicacion"])["pxn_kg"].max().sum()
                    else:
                        return arb_anio.get(a), False
                    if v and v > 0:
                        return v, False
                    return arb_anio.get(a), True   # la regla no tiene su divisor ese año: respaldo árboles vivos

                def html_tabla_cu(t, nombre_c, b=None):
                    """Tabla ejecutiva en HTML: el año arriba y, en una segunda línea, el divisor de su regla."""
                    cols = [c for c in t.columns if c not in (nombre_c, "Gasto total", "% del gasto")]
                    b = base if b is None else b
                    regla = regla_de(b)
                    icono = DIV_REGLA.get(regla, ("🌳", ""))[0]
                    def th_anio(c):
                        if eje == "Año":
                            v, resp = divisor_anio(b, int(c), regla) if regla else (arb_anio.get(int(c)), False)
                            if v and resp:
                                return (f'<th class="anio">{c}<div class="sub resp" title="Sin dato propio de la regla '
                                        f'este año: se dividió por árboles vivos">🌳 {pesos(v)} *</div></th>')
                            if v:
                                return f'<th class="anio">{c}<div class="sub">{icono} {pesos(v)}</div></th>'
                        return f'<th class="anio">{c}</th>'
                    cab = (f'<tr><th class="izq">{_html.escape(nombre_c)}</th><th>Gasto total</th><th>% del gasto</th>'
                           + "".join(th_anio(c) for c in cols) + "</tr>")
                    filas_h = []
                    for _, r in t.iterrows():
                        clase = ' class="tot"' if r[nombre_c] == "TOTAL" else ""
                        pct_txt = f"{r['% del gasto']:.1%}".replace(".", ",")
                        filas_h.append(f"<tr{clase}><td class='izq'>{_html.escape(str(r[nombre_c]))}</td>"
                                       f"<td>{millones(r['Gasto total'])}</td><td>{pct_txt}</td>"
                                       + "".join(f"<td>{unitario(r[c])}</td>" for c in cols) + "</tr>")
                    return f'<div class="tcu"><table><thead>{cab}</thead><tbody>{"".join(filas_h)}</tbody></table></div>'

                st.markdown("""<style>
                  .tcu { overflow-x:auto; border:1px solid #E5E7EB; border-radius:10px; margin:0.3rem 0 0.4rem 0; }
                  .tcu table { border-collapse:collapse; width:100%; font-size:0.84rem; font-variant-numeric:tabular-nums; }
                  .tcu th { background:#F6F8F5; color:#374151; font-weight:600; text-align:right; padding:0.45rem 0.6rem;
                            border-bottom:1px solid #E1E8DF; white-space:nowrap; vertical-align:bottom; }
                  .tcu th.anio { text-align:center; }
                  .tcu th .sub { display:table; margin:4px auto 0 auto; padding:1px 7px; border-radius:999px;
                                 background:#E8F1E8; color:#1B5E20; font-weight:700; font-size:0.72rem; }
                  .tcu th .sub.resp { background:#FFF4E0; color:#9A5B00; }
                  .tcu td { text-align:right; padding:0.38rem 0.5rem; border-bottom:1px solid #F0F2F0; white-space:nowrap; }
                  .tcu .izq { text-align:left; white-space:normal; min-width:140px; max-width:220px; }
                  .tcu tbody tr:hover td { background:#F9FBF9; }
                  .tcu tr.tot td { font-weight:700; border-top:2px solid #CBD5CC; background:#FAFBFA; }
                </style>""", unsafe_allow_html=True)

                def agrupar_resto(b, por_c, n=15):
                    """Para leer en una junta: los n de mayor gasto y el resto junto en 'Otras (k)'."""
                    g = b.groupby(por_c)["valor"].sum().sort_values(ascending=False)
                    if len(g) <= n + 1 or st.session_state.get("cu_ver_todas"):
                        return b
                    resto = g.index[n:]
                    return b.assign(**{por_c: b[por_c].where(~b[por_c].isin(resto), f"Otras ({len(resto)})")})

                tabla_cu = armar_tabla_cu(agrupar_resto(base, por), por, ver)
                cols_cu = [c for c in tabla_cu.columns if c not in (ver, "Gasto total", "% del gasto")]
                st.markdown(html_tabla_cu(tabla_cu, ver), unsafe_allow_html=True)
                if base[por].nunique() > 16:
                    st.toggle(f"Ver todas las filas ({base[por].nunique()})", key="cu_ver_todas",
                              help="Por defecto se muestran los 15 de mayor gasto y el resto se junta en 'Otras'.")
                pro_a = base[base["origen_divisor"] == "Propio de la regla"]
                if eje == "Año":
                    regla_t = regla_de(base)
                    if regla_t:
                        resp_a = [int(a) for a in sorted(base["anio"].dropna().unique())
                                  if divisor_anio(base, int(a), regla_t)[1]] if regla_t != "ARB_TOTALVIVOS" else []
                        txt_resp = (f" ⚠️ **{', '.join(map(str, resp_a))}** (en naranja, con *): la hoja ARB_TOTAL aún no "
                                    "tiene ese dato para el año, por eso el cálculo usó árboles vivos como respaldo. "
                                    "Al completarlo, el costo se corrige solo.") if resp_a else ""
                        st.caption(f"Debajo de cada año: el divisor de la regla **{regla_t}** — "
                                   f"{DIV_REGLA.get(regla_t, ('', 'árboles vivos'))[1]}.{txt_resp}")
                    else:
                        reglas_t = ", ".join(sorted(str(x) for x in base["regla_divisor"].dropna().unique()))
                        st.caption(f"Debajo de cada año: árboles vivos de la finca (ARB_TOTAL), solo como referencia. "
                                   f"La tabla mezcla varias reglas ({reglas_t}); cada fila usa el divisor de la suya. "
                                   "Elija un rubro para ver su divisor exacto.")
                    # Aviso automático cuando la base cambia mucho de un año a otro
                    serie = (pro_a.groupby("anio")["valor"].sum() / base.groupby("anio")["valor"].sum()).fillna(0)
                    serie = serie.reindex(sorted(base["anio"].dropna().unique())).fillna(0)
                    for b_a, a_a in zip(serie.index[:-1], serie.index[1:]):
                        if abs(serie[a_a] - serie[b_a]) >= 0.25:
                            st.warning(f"**Cambio de base en {int(a_a)}:** el gasto cargado a lotes pasó de "
                                       f"{serie[b_a]:.0%} a {serie[a_a]:.0%}. El ponderado de {int(a_a)} no es comparable "
                                       f"con el de {int(b_a)}: para comparar años use el costo por árbol de la Ficha.",
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
                        st.markdown(html_tabla_cu(armar_tabla_cu(agrupar_resto(mo_b, por), por, ver), ver, mo_b),
                                    unsafe_allow_html=True)
                        st.caption("Nómina (jornales de la app de campo) + mano de obra al contrato.")
                with st.expander(f"📦 Insumos, servicios y otros costos · {millones(ot_b['valor'].sum())} "
                                 f"({pct(ot_b)} del gasto)"):
                    if ot_b.empty:
                        st.info("No hay insumos ni servicios con estos filtros.")
                    else:
                        st.markdown(html_tabla_cu(armar_tabla_cu(agrupar_resto(ot_b, "detalle"), "detalle", "Detalle"),
                                                  "Detalle", ot_b),
                                    unsafe_allow_html=True)
                        st.caption("Abierto por la columna DETALLE del Excel (insumos agrícolas, herramientas y equipos, "
                                   "servicios, combustible…).")
                st.caption("El costo unitario ponderado es un promedio pesado por el gasto: por eso las partes "
                           "(ej. mano de obra e insumos) no suman el TOTAL. Para ver cuánto pesa cada parte use "
                           "'% del gasto'.")

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

                tabla_xls, filas_xls = armar_tabla_cu(base, por, ver), base.drop(columns=["_x", "huella"], errors="ignore")

                def excel_cu(t=tabla_xls, f=filas_xls):
                    salida = io.BytesIO()
                    with pd.ExcelWriter(salida, engine="openpyxl") as w:
                        t.to_excel(w, index=False, sheet_name="CU ponderado")  # completa
                        f.to_excel(w, index=False, sheet_name="Detalle filas")
                    return salida.getvalue()
                # El Excel se arma solo al tocar el botón (antes se armaba en cada clic: unos 20 segundos)
                st.download_button("Descargar costo unitario en Excel", excel_cu,
                                   file_name=f"Costo_unitario_AGROCACAY_{'anual' if eje == 'Año' else 'mensual'}.xlsx")


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
