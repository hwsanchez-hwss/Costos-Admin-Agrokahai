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
  .enc img {{ height:52px; background:#fff; border-radius:10px; padding:4px 8px; }}
  .enc .tit {{ font-size:1.55rem; font-weight:700; line-height:1.15; letter-spacing:0.2px; }}
  .enc .sub {{ font-size:0.92rem; opacity:0.88; margin-top:2px; }}
  @media (max-width: 640px) {{
    .enc {{ flex-direction:column; align-items:flex-start; gap:0.5rem; }}
    .enc img {{ height:38px; }}
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
  .st-key-btn_restablecer button p {{ font-size:0.82rem; color:#5B6B5E; }}
  .st-key-barra_filtros label p {{ font-size:0.74rem !important; font-weight:700 !important;
                                   text-transform:uppercase; letter-spacing:0.6px; color:#5B6B5E !important; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] button {{ border-radius:999px; }}
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[aria-checked="true"],
  .st-key-barra_filtros [data-testid="stButtonGroup"] button[kind$="Active"] {{
        background:{VERDE} !important; border-color:{VERDE} !important; color:#fff !important; }}
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


# ===============================================================
# 3. FILTROS (barra lateral, con botones)
# ===============================================================
# Evitar que el navegador "traduzca" la página (ya está en español; el traductor
# cambiaba, por ejemplo, "Nómina" por "Nombre")
_SIN_TRADUCIR = """
document.documentElement.lang = 'es';
document.documentElement.setAttribute('translate', 'no');
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


def boton_unico(lugar, etiqueta_f, opciones, defecto, clave, ayuda=None, formato=None, segmentado=False):
    """Botones de una sola selección. Si el usuario quita la selección, vuelve al valor por defecto."""
    widget = lugar.segmented_control if segmentado else lugar.pills
    valor = widget(etiqueta_f, opciones, selection_mode="single", default=defecto, key=clave,
                   help=ayuda, format_func=formato)
    return defecto if valor is None else valor


# El encabezado se dibuja ARRIBA de los filtros, pero se llena después (necesita el periodo elegido)
encabezado = st.container()

# ---- Filtros arriba, en dos bloques: PERIODO (cuándo) y ALCANCE (qué se mira) ----
def restablecer_filtros():
    """Vuelve todos los filtros a como abre la app."""
    for k in [k for k in st.session_state if str(k).startswith("f_")]:
        del st.session_state[k]


with st.container(key="barra_filtros"):
    col_alcance, col_periodo = st.columns([1.12, 1.5], gap="small")
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

    # PERIODO: año y mes
    with bloque_periodo:
        anios = sorted({p // 100 for p in periodos})
        anio = boton_unico(st, "Año", anios, anios[-1], "f_anio")
        meses_del_anio = [p % 100 for p in periodos if p // 100 == anio]
        AÑO_COMPLETO = "Año completo"
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
            frase = f"{mes_txt}-{anio} · se compara con {previo} (mes anterior) y {mes_txt}-{anio - 1} (año anterior)"
        r1, r2 = st.columns([5, 1.1], gap="small", vertical_alignment="center")
        r1.markdown(f'<div class="frase">📌 {frase}</div>', unsafe_allow_html=True)
        r2.button("↺ Restablecer", on_click=restablecer_filtros, type="tertiary", key="btn_restablecer",
                  help="Vuelve todos los filtros a como abre la app")

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
if anual:
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
etq_sel = f"Año {anio}{rango_meses}" if anual else etiqueta(mes)
etq_acum, etq_acum_ant = f"Ene–{NOMBRE_MES[num_mes]} {anio}", f"Ene–{NOMBRE_MES[num_mes]} {anio - 1}"


def suma(d, lista):
    return d.loc[d["periodo"].isin(lista), "valor"].sum()


# Columnas de comparación que usan las tablas, según se mire un mes o un año
if anual:
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
                if b == i:
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
    import base64
    ruta = os.path.join(C.CARPETA_APP, "logo_kahai.png")
    if not os.path.exists(ruta):
        return ""
    return f'<img src="data:image/png;base64,{base64.b64encode(open(ruta, "rb").read()).decode()}">'


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
    if anual:
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
                                    value=((seleccion[0], mes) if anual else (max(periodos[0], mover(mes, -11)), mes)))
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

        salida = io.BytesIO()
        piv.to_excel(salida, index=False, sheet_name="Tabla mensual")
        st.download_button("Descargar en Excel", salida.getvalue(),
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
        for col in ["ceco", "rubro", "ubicacion", "regla_divisor", "detalle", "descripcion"]:
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


with pest[2]:
    if vista == "KAHAI":
        st.info("Por ahora el costo unitario se calcula solo para la parte agrícola (AGROCACAY). "
                "Elija AGROCACAY en la barra lateral.")
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

            # ---- Tabla ponderada (igual a la de la app de campo / Power BI)
            st.subheader("Costo unitario ponderado")
            st.caption("Cada mes: costo ÷ divisor de su regla (árboles del censo, kg cosechados, sitios sembrados "
                       "o árboles vivos). Varios meses o lotes se promedian ponderando por lo que se gastó en cada uno "
                       "— la misma medida 'Costo Unitario Ponderado' de Power BI.")
            c1, c2, c3, c4 = st.columns([1.2, 1, 2, 2])
            OPC_VER = {"Rubro": "rubro", "Mano de obra / Otros": "bloque", "Detalle": "detalle",
                       "Descripción (producto / labor)": "descripcion", "Tipo de gasto": "tipo",
                       "Ubicación (lote)": "ubicacion", "CECO": "ceco", "Regla de divisor": "regla_divisor"}
            ver = c1.selectbox("Ver por", list(OPC_VER),
                               help="Para ver los insumos de un rubro (ej. MIAR): filtre el rubro y elija "
                                    "'Mano de obra / Otros', 'Detalle' o 'Descripción (producto / labor)'.")
            por = OPC_VER[ver]
            eje = c2.radio("Columnas", ["Año", "Mes"], horizontal=True)
            f_ceco = c3.multiselect("CECO", sorted(cu["ceco"].unique()), placeholder="Todos")
            f_rubro = c4.multiselect("Rubro", sorted(cu["rubro"].unique()), placeholder="Todos")
            base = cu
            if f_ceco:
                base = base[base["ceco"].isin(f_ceco)]
            if f_rubro:
                base = base[base["rubro"].isin(f_rubro)]

            if eje == "Mes":
                per_cu = sorted(base["periodo"].unique())
                if len(per_cu) >= 2:
                    d1, d2 = st.select_slider("Meses ", options=per_cu, format_func=etiqueta,
                                              value=((max(per_cu[0], seleccion[0]), mes) if anual else
                                                     (max(per_cu[0], mover(mes, -11)),
                                                      mes if mes in per_cu else per_cu[-1])))
                    base = base[(base["periodo"] >= d1) & (base["periodo"] <= d2)]
                base = base.assign(_x=base["periodo"])
            else:
                base = base.assign(_x=base["anio"])

            if base.empty:
                st.info("No hay datos con estos filtros.")
            else:
                tabla_cu = ponderado(base, por, "_x").unstack("_x")
                total_cu = ponderado(base, None, "_x")
                tabla_cu.loc["TOTAL"] = total_cu
                gasto = base.groupby(por)["valor"].sum()
                orden = list(gasto.sort_values(ascending=False).index) + ["TOTAL"]
                tabla_cu = tabla_cu.reindex([o for o in orden if o in tabla_cu.index])
                if eje == "Mes":
                    tabla_cu.columns = [etiqueta(c) for c in tabla_cu.columns]
                else:
                    tabla_cu.columns = [str(int(c)) for c in tabla_cu.columns]
                tabla_cu.insert(0, "Gasto total", gasto.reindex(tabla_cu.index).fillna(base["valor"].sum()))
                tabla_cu.insert(1, "% del gasto", tabla_cu["Gasto total"] / base["valor"].sum())
                tabla_cu = tabla_cu.reset_index().rename(columns={por: ver})
                cols_cu = [c for c in tabla_cu.columns if c not in (ver, "Gasto total", "% del gasto")]
                mostrar = tabla_cu.copy()
                for c in cols_cu:   # como texto, para que lo vacío salga "—"
                    mostrar[c] = mostrar[c].map(unitario)
                mostrar["% del gasto"] = mostrar["% del gasto"].map(lambda v: f"{v:.1%}".replace(".", ","))
                st.dataframe(mostrar.style.format(pesos, subset=["Gasto total"])
                             .apply(lambda r: ["font-weight: bold" if r.iloc[0] == "TOTAL" else "" for _ in r], axis=1),
                             hide_index=True, width="stretch", height=450)

                st.caption("El costo unitario ponderado es un promedio pesado por el gasto: por eso las partes "
                           "(ej. mano de obra e insumos) no suman el TOTAL. Para ver cuánto pesa cada parte use "
                           "'% del gasto'.")

                # Gráfica: los 5 de mayor gasto (se pueden cambiar)
                opciones = [o for o in tabla_cu[ver] if o != "TOTAL"]
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

                salida = io.BytesIO()
                with pd.ExcelWriter(salida, engine="openpyxl") as w:
                    tabla_cu.to_excel(w, index=False, sheet_name="CU ponderado")
                    base.drop(columns=["_x", "huella"], errors="ignore").to_excel(w, index=False, sheet_name="Detalle filas")
                st.download_button("Descargar costo unitario en Excel", salida.getvalue(),
                                   file_name=f"Costo_unitario_AGROCACAY_{eje}.xlsx")


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
    meses_mov = c1.multiselect("Meses", periodos[::-1], default=seleccion[::-1], format_func=etiqueta,
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
    salida = io.BytesIO()
    m.to_excel(salida, index=False, sheet_name="Movimientos")
    st.download_button("Descargar movimientos en Excel", salida.getvalue(),
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
