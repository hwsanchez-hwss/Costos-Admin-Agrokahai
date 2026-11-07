# -*- coding: utf-8 -*-
"""
CONTROL DE ACCESO (solo en la nube)
===================================
En Streamlit Cloud la app pide "Iniciar sesión con Google" y solo deja pasar
los correos de la lista ACCESO de los Secretos (los correos NO están en el código,
que es público). En el PC no pide nada.

Secretos que necesita (en Streamlit Cloud → Settings → Secrets):
    ACCESO = ["correo1@kahai.co", "correo2@kahai.co"]
    [auth]
    redirect_uri = "https://<la-app>.streamlit.app/oauth2callback"
    cookie_secret = "<texto largo al azar>"
    client_id = "<ID de cliente de Google>"
    client_secret = "<Secreto del cliente de Google>"
    server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
"""
import streamlit as st


def exigir_acceso():
    """Detiene la página si la persona no ha entrado o no está en la lista.
    Si puede pasar, devuelve su correo."""
    try:
        permitidos = {c.strip().lower() for c in st.secrets.get("ACCESO", [])}
        hay_google = "auth" in st.secrets
    except Exception:
        permitidos, hay_google = set(), False

    # Si falta la configuración, NO se muestra nada (mejor cerrado que abierto)
    if not permitidos or not hay_google:
        st.error("La app no tiene configurado el acceso (faltan ACCESO o [auth] en los Secretos).")
        st.stop()

    if not st.user.get("is_logged_in", False):
        st.title("📊 Costos AGROCACAY · KAHAI")
        st.write("Acceso solo para personal autorizado de KAHAI. Entre con su correo **@kahai.co**.")
        st.button("Iniciar sesión con Google", on_click=st.login, type="primary")
        st.stop()

    correo = str(st.user.get("email", "")).lower()
    if correo not in permitidos:
        st.error(f"El correo {correo} no tiene acceso a esta app. Pida acceso a administración.")
        st.button("Salir", on_click=st.logout)
        st.stop()

    return correo   # el encabezado del dashboard lo muestra junto a "Cerrar sesión"
