import base64
import html
import json
import os
import re
import time
from typing import Optional

import requests
import streamlit as st
import streamlit.components.v1 as components

API_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
PUBLIC_API_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8000")


# ---------- Utilidades visuales ----------
def get_base64_local_image(path: str) -> str:
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()


st.set_page_config(page_title="Cinematch", page_icon="🎬", layout="centered", initial_sidebar_state="expanded")

try:
    img_base64 = get_base64_local_image(os.path.join("pages", "assets", "fondo.png"))
except FileNotFoundError:
    img_base64 = ""

try:
    logo_base64 = get_base64_local_image(os.path.join("pages", "assets", "logobg.png"))
except FileNotFoundError:
    logo_base64 = ""


# Si el navegador quedó con parámetros antiguos de gustos en la URL
# (?pref_genre_id=...&pref_score=...), los limpiamos para no romper la sesión/login.
try:
    if {"pref_genre_id", "pref_score"}.intersection(set(st.query_params.keys())):
        st.query_params.clear()
        st.rerun()
except Exception:
    pass


# Estado mínimo antes de inyectar CSS: así el login puede ocultar la sidebar
# y la vista de películas puede mostrarla normalmente.
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None

_IS_AUTHENTICATED = bool(st.session_state.get("authenticated") and st.session_state.get("token"))

_LOGIN_ONLY_HIDE_SIDEBAR_CSS = """
    /* Login: sin sidebar, sin botón de sidebar y sin barra superior. */
    header[data-testid="stHeader"],
    header[data-testid="stHeader"] *,
    section[data-testid="stSidebar"],
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarNav"],
    button[aria-label="Open sidebar"],
    button[aria-label="Abrir barra lateral"],
    button[aria-label="Close sidebar"],
    button[aria-label="Cerrar barra lateral"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        min-width: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        pointer-events: none !important;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    section.main {
        margin-left: 0 !important;
    }
""" if not _IS_AUTHENTICATED else ""


st.markdown(
    f"""
    <style>
    /* ============================================================
       BASE APP
       ============================================================ */
    html, body, .stApp {{
        height: 100vh !important;
        max-height: 100vh !important;
        overflow: hidden !important;
    }}

    .stApp {{
        background-image: linear-gradient(rgba(22, 22, 20, 0.9), rgba(22, 22, 20, 0.9)),
                          url("data:image/png;base64,{img_base64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    [data-testid="stAppViewContainer"] {{
        height: 100vh !important;
        overflow: hidden !important;
    }}

    [data-testid="stAppViewContainer"] > .main,
    section.main {{
        height: 100vh !important;
        overflow: hidden !important;
    }}

    .block-container {{
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        max-width: 100% !important;
        height: 100vh !important;
        overflow: hidden !important;
    }}

    iframe {{
        display: block !important;
        border: none !important;
    }}

    /* ============================================================
       HEADER / DEPLOY / FLECHA SIDEBAR
       Clave del arreglo:
       - El header de Streamlit NO captura clics ni ocupa alto útil.
       - No se usa display:none sobre el header porque Streamlit puede meter
         dentro de él la flecha nativa de abrir/cerrar sidebar.
       - Solo los botones reales del sidebar recuperan pointer-events.
       ============================================================ */
    header[data-testid="stHeader"] {{
        display: block !important;
        visibility: visible !important;
        position: fixed !important;
        inset: 0 0 auto 0 !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
        pointer-events: none !important;
        z-index: 2147483000 !important;
        overflow: visible !important;
    }}

    /* El header y su toolbar quedan vivos, pero son transparentes al ratón.
       Esto evita que bloqueen el botón de ocultar sidebar. */
    header[data-testid="stHeader"] *,
    [data-testid="stToolbar"],
    [data-testid="stToolbar"] *,
    [data-testid="stToolbarActions"],
    [data-testid="stToolbarActions"] *,
    [data-testid="stHeaderActionElements"],
    [data-testid="stHeaderActionElements"] * {{
        pointer-events: none !important;
    }}

    [data-testid="stToolbar"],
    [data-testid="stToolbarActions"],
    [data-testid="stHeaderActionElements"] {{
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        overflow: visible !important;
    }}

    /* Oculta navegación automática de multipágina: app / dashboard / register. */
    [data-testid="stSidebarNav"] {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }}

    /* Ocultar Deploy/menú/estado sin matar la flecha nativa. */
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="stMainMenu"],
    [data-testid="stDeployButton"],
    [data-testid="stToolbar"] [data-testid="stDeployButton"],
    [data-testid="stToolbar"] [data-testid="stStatusWidget"],
    [data-testid="stToolbar"] [data-testid="stMainMenu"],
    .stDeployButton,
    .stAppDeployButton,
    #MainMenu,
    footer,
    button[title="Deploy"],
    button[aria-label="Deploy"],
    a[href*="streamlit.io/cloud"],
    a[href*="share.streamlit.io"] {{
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        min-width: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        pointer-events: none !important;
    }}

    /* Flecha de abrir/cerrar: mismo diseño en estado abierto y cerrado.
       Importante: estos selectores van DESPUÉS del bloqueo del header para
       devolver el click únicamente a la flecha. */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    header[data-testid="stHeader"] [data-testid="collapsedControl"],
    header[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"],
    header[data-testid="stHeader"] [data-testid="stSidebarCollapseButton"] {{
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        position: fixed !important;
        top: 6.8rem !important;
        left: 0.72rem !important;
        width: 2.75rem !important;
        height: 2.75rem !important;
        min-width: 2.75rem !important;
        min-height: 2.75rem !important;
        align-items: center !important;
        justify-content: center !important;
        transform: none !important;
        clip: auto !important;
        overflow: visible !important;
        pointer-events: auto !important;
        z-index: 2147483647 !important;
        background: rgba(32, 35, 45, 0.98) !important;
        border: 1px solid rgba(250, 217, 185, 0.34) !important;
        border-radius: 999px !important;
        box-shadow: 0 12px 32px rgba(0,0,0,0.68) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
    }}

    [data-testid="collapsedControl"] *,
    [data-testid="stSidebarCollapsedControl"] *,
    [data-testid="stSidebarCollapseButton"] *,
    header[data-testid="stHeader"] [data-testid="collapsedControl"] *,
    header[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"] *,
    header[data-testid="stHeader"] [data-testid="stSidebarCollapseButton"] * {{
        pointer-events: auto !important;
    }}

    [data-testid="collapsedControl"] button,
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="stSidebarCollapseButton"] button,
    button[aria-label="Open sidebar"],
    button[aria-label="Close sidebar"],
    button[aria-label="Abrir barra lateral"],
    button[aria-label="Cerrar barra lateral"],
    button[title="Open sidebar"],
    button[title="Close sidebar"],
    button[title="Abrir barra lateral"],
    button[title="Cerrar barra lateral"] {{
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        align-items: center !important;
        justify-content: center !important;
        width: 2.55rem !important;
        height: 2.55rem !important;
        min-width: 2.55rem !important;
        min-height: 2.55rem !important;
        padding: 0 !important;
        margin: 0 !important;
        color: #FAD9B9 !important;
        background: rgba(32, 35, 45, 0.98) !important;
        border: 1px solid rgba(250, 217, 185, 0.34) !important;
        border-radius: 999px !important;
        box-shadow: 0 12px 32px rgba(0,0,0,0.68) !important;
        pointer-events: auto !important;
        cursor: pointer !important;
        z-index: 2147483647 !important;
    }}

    /* Refuerzo para cuando Streamlit deja el botón real fuera del contenedor
       collapsedControl: lo fijamos igualmente más abajo y clicable. */
    button[aria-label="Open sidebar"],
    button[aria-label="Close sidebar"],
    button[aria-label="Abrir barra lateral"],
    button[aria-label="Cerrar barra lateral"],
    button[title="Open sidebar"],
    button[title="Close sidebar"],
    button[title="Abrir barra lateral"],
    button[title="Cerrar barra lateral"] {{
        position: fixed !important;
        top: 6.8rem !important;
        left: 0.85rem !important;
        width: 2.75rem !important;
        height: 2.75rem !important;
        min-width: 2.75rem !important;
        min-height: 2.75rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        visibility: visible !important;
        opacity: 1 !important;
        background: rgba(32, 35, 45, 0.98) !important;
        color: #FAD9B9 !important;
        border: 1px solid rgba(250, 217, 185, 0.34) !important;
        border-radius: 999px !important;
        box-shadow: 0 12px 32px rgba(0,0,0,0.68) !important;
        pointer-events: auto !important;
        cursor: pointer !important;
        z-index: 2147483647 !important;
        transform: none !important;
    }}

    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg,
    button[aria-label="Open sidebar"] svg,
    button[aria-label="Close sidebar"] svg,
    button[aria-label="Abrir barra lateral"] svg,
    button[aria-label="Cerrar barra lateral"] svg {{
        width: 1.35rem !important;
        height: 1.35rem !important;
        color: #FAD9B9 !important;
        fill: #FAD9B9 !important;
        stroke: #FAD9B9 !important;
        stroke-width: 2.7px !important;
        filter: drop-shadow(0 0 5px rgba(250,217,185,0.55)) !important;
    }}


    /* Fallback fuerte: en algunas versiones, el botón de mostrar sidebar no
       usa collapsedControl sino un botón de header genérico. Por eso movemos
       cualquier botón real del header fuera del header y lo dejamos como
       botón flotante dentro de la zona visible de la app. */
    header[data-testid="stHeader"] button,
    header[data-testid="stHeader"] [role="button"],
    [data-testid="stHeader"] button,
    [data-testid="stHeader"] [role="button"],
    [data-testid="stHeader"] [data-testid*="BaseButton"],
    [data-testid="stHeader"] [data-testid*="baseButton"] {{
        position: fixed !important;
        top: 6.8rem !important;
        left: 1rem !important;
        width: 2.85rem !important;
        height: 2.85rem !important;
        min-width: 2.85rem !important;
        min-height: 2.85rem !important;
        max-width: 2.85rem !important;
        max-height: 2.85rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        visibility: visible !important;
        opacity: 1 !important;
        overflow: visible !important;
        transform: none !important;
        clip: auto !important;
        margin: 0 !important;
        padding: 0 !important;
        background: rgba(32, 35, 45, 0.98) !important;
        color: #FAD9B9 !important;
        border: 1px solid rgba(250, 217, 185, 0.36) !important;
        border-radius: 999px !important;
        box-shadow: 0 14px 34px rgba(0,0,0,0.72) !important;
        pointer-events: auto !important;
        cursor: pointer !important;
        z-index: 2147483647 !important;
    }}

    header[data-testid="stHeader"] button svg,
    [data-testid="stHeader"] button svg,
    [data-testid="stHeader"] [role="button"] svg,
    [data-testid="stHeader"] [data-testid*="BaseButton"] svg,
    [data-testid="stHeader"] [data-testid*="baseButton"] svg {{
        width: 1.45rem !important;
        height: 1.45rem !important;
        color: #FAD9B9 !important;
        fill: #FAD9B9 !important;
        stroke: #FAD9B9 !important;
        stroke-width: 2.7px !important;
        filter: drop-shadow(0 0 6px rgba(250,217,185,0.55)) !important;
    }}

    /* Si algún botón del header es Deploy o menú, permanece oculto aunque
       arriba hayamos hecho visibles los botones genéricos del header. */
    header[data-testid="stHeader"] button[title="Deploy"],
    header[data-testid="stHeader"] button[aria-label="Deploy"],
    [data-testid="stHeader"] [data-testid="stDeployButton"],
    [data-testid="stHeader"] [data-testid="stStatusWidget"],
    [data-testid="stHeader"] [data-testid="stMainMenu"] {{
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }}

    /* ============================================================
       SIDEBAR LOGUEADA
       ============================================================ */
    section[data-testid="stSidebar"] {{
        background-color: #20232D !important;
        border-right: 1px solid rgba(250, 217, 185, 0.06) !important;
        z-index: 999999 !important;
    }}

    section[data-testid="stSidebar"] * {{
        pointer-events: auto;
    }}

    section[data-testid="stSidebar"] > div:first-child,
    section[data-testid="stSidebarContent"] {{
        overflow-x: hidden !important;
        overflow-y: auto !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }}

    section[data-testid="stSidebar"] .block-container {{
        height: 100vh !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
        padding: 0.55rem 0.65rem 0.8rem 0.65rem !important;
    }}

    section[data-testid="stSidebar"] .block-container > div:first-child {{
        min-height: calc(100vh - 1.35rem) !important;
        display: flex !important;
        flex-direction: column !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 0.28rem !important;
    }}

    section[data-testid="stSidebar"] hr {{
        margin: 0.75rem 0 0.75rem 0 !important;
        opacity: 0.28 !important;
    }}

    .sidebar-user-card {{
        margin-top: 9.6rem !important;
        margin-bottom: 0.9rem !important;
        padding: 0 !important;
    }}

    .username-link,
    .username-link:visited,
    .username-link:hover,
    .username-link:active {{
        color: inherit !important;
        text-decoration: none !important;
        display: block !important;
    }}

    .profile-card {{
        display: flex !important;
        align-items: center !important;
        gap: 0.85rem !important;
        padding: 0.9rem 0.95rem !important;
        border-radius: 18px !important;
        background: linear-gradient(180deg, rgba(34,39,53,0.96), rgba(26,30,42,0.98)) !important;
        border: 1px solid rgba(250, 217, 185, 0.14) !important;
        box-shadow: 0 14px 26px rgba(0,0,0,0.28) !important;
        transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease !important;
    }}

    .username-link:hover .profile-card {{
        transform: translateY(-1px) !important;
        border-color: rgba(250, 217, 185, 0.32) !important;
        box-shadow: 0 18px 28px rgba(0,0,0,0.34) !important;
    }}

    .profile-avatar {{
        width: 3rem !important;
        height: 3rem !important;
        min-width: 3rem !important;
        border-radius: 999px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.3rem !important;
        font-weight: 900 !important;
        color: #FFF3E4 !important;
        background: linear-gradient(135deg, #8B5A62, #C7AD93) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        box-shadow: 0 8px 18px rgba(0,0,0,0.32) !important;
    }}

    .profile-copy {{
        min-width: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 0.1rem !important;
    }}

    .profile-label {{
        font-size: 0.72rem !important;
        line-height: 1 !important;
        font-weight: 800 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: rgba(199, 173, 147, 0.86) !important;
    }}

    .profile-name {{
        color: #F5DEC4 !important;
        margin: 0 !important;
        font-size: 1.18rem !important;
        line-height: 1.15 !important;
        font-weight: 900 !important;
        letter-spacing: 0.01em !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }}

    .profile-hint {{
        color: rgba(160, 139, 119, 0.92) !important;
        font-size: 0.76rem !important;
        line-height: 1 !important;
        font-weight: 700 !important;
    }}

    /* El perfil se navega con st.switch_page para no perder la sesión.
       Este botón nativo queda encima de la tarjeta, pero invisible. */
    section[data-testid="stSidebar"] .element-container:has([data-testid="stBaseButton-tertiary"]) {{
        margin-top: -5.65rem !important;
        margin-bottom: 0.75rem !important;
        position: relative !important;
        z-index: 60 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stBaseButton-tertiary"] {{
        height: 5.35rem !important;
        min-height: 5.35rem !important;
        width: 100% !important;
        border-radius: 18px !important;
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        opacity: 0.01 !important;
        color: transparent !important;
        cursor: pointer !important;
        pointer-events: auto !important;
        position: relative !important;
        z-index: 70 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stBaseButton-tertiary"] * {{
        opacity: 0 !important;
        color: transparent !important;
    }}

    .sidebar-title {{
        color: #E6C8A8 !important;
        margin: 0.2rem 0 0.75rem !important;
        font-size: 1.08rem !important;
        line-height: 1.1 !important;
        font-weight: 900 !important;
        letter-spacing: 0.02em !important;
        text-align: left !important;
    }}

    .genre-name {{
        color: #E8D2BA !important;
        text-align: left !important;
        font-size: 0.98rem !important;
        line-height: 1.1 !important;
        font-weight: 850 !important;
        letter-spacing: 0.015em !important;
        margin: 0.55rem 0 0.14rem 0 !important;
        padding: 0 !important;
    }}

    /* Estrellas de gustos: más grandes, más juntas y visualmente más limpias. */
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {{
        gap: 0.08rem !important;
    }}

    section[data-testid="stSidebar"] div[data-testid="column"] {{
        padding-left: 0 !important;
        padding-right: 0 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
        width: 100% !important;
        min-width: 0 !important;
        height: 1.95rem !important;
        min-height: 1.95rem !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        background: transparent !important;
        color: #FFD9AD !important;
        font-size: 1.82rem !important;
        line-height: 1 !important;
        font-weight: 900 !important;
        letter-spacing: -0.14em !important;
        text-shadow: 0 0 7px rgba(255, 217, 173, 0.28) !important;
        box-shadow: none !important;
        border-radius: 999px !important;
        transition: transform 0.13s ease, color 0.13s ease, text-shadow 0.13s ease, background-color 0.13s ease !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p {{
        width: 100% !important;
        text-align: center !important;
        line-height: 1 !important;
        margin: 0 !important;
        color: inherit !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{
        background-color: rgba(250, 217, 185, 0.08) !important;
        color: #FFF0C8 !important;
        text-shadow: 0 0 14px rgba(255, 240, 200, 0.75) !important;
        transform: scale(1.13) !important;
    }}

    .sidebar-bottom-push {{
        height: 0 !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }}

    section[data-testid="stSidebar"] .element-container:has(.sidebar-bottom-push) {{
        margin-top: auto !important;
    }}

    .sidebar-actions-spacer {{
        padding-top: 0.95rem !important;
        border-top: 1px solid rgba(160, 139, 119, 0.25) !important;
    }}

    /* Botón Cerrar sesión */
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 3.05rem !important;
        min-height: 3.05rem !important;
        border-radius: 18px !important;
        font-size: 0.92rem !important;
        font-weight: 850 !important;
        padding: 0.25rem 0.8rem !important;
        white-space: nowrap !important;
        background: linear-gradient(180deg, #84505A, #78444A) !important;
        color: #FAD9B9 !important;
        border: 1px solid rgba(250, 217, 185, 0.13) !important;
        box-shadow: 0 12px 22px rgba(0,0,0,0.28) !important;
        transition: transform 0.16s ease, background-color 0.16s ease, border 0.16s ease !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p {{
        width: 100% !important;
        margin: 0 !important;
        text-align: center !important;
        color: #FAD9B9 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {{
        background: linear-gradient(180deg, #935863, #87505A) !important;
        border-color: #d0b59b !important;
        transform: translateY(-1px) !important;
    }}

    /* ============================================================
       LOGIN
       ============================================================ */
    .st-emotion-cache-1gz5zxc {{
        background-color: rgba(22, 22, 20, 0.85) !important;
        border-radius: 20px !important;
        padding: 2.5rem !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(160, 139, 119, 0.2) !important;
        box-shadow: 0 20px 40px rgba(0,0,0,0.6) !important;
    }}

    h2, p, label {{
        color: #d0b59b !important;
        text-align: center;
    }}

    .stTextInput>div>div>input {{
        background-color: rgba(0, 0, 0, 0.6) !important;
        color: #FAD9B9 !important;
        border: 1px solid #3F2B1F !important;
        border-radius: 10px !important;
        height: 2.7em !important;
        display: flex !important;
        align-items: center !important;
        line-height: normal !important;
        padding: 0 15px !important;
    }}

    .stButton>button {{
        background-color: #78444A !important;
        color: white !important;
        border-radius: 10px !important;
        height: 3.25em !important;
        width: 100% !important;
        border: none !important;
        font-weight: bold !important;
        transition: 0.25s;
    }}

    .stButton>button:hover {{
        background-color: #945259 !important;
        border: 1px solid #d0b59b !important;
        transform: scale(1.01);
    }}

    .register-container {{
        text-align: center;
        margin-top: 25px;
    }}

    .register-link {{
        color: #A08B77;
        text-decoration: none;
        font-weight: 500;
    }}

    .register-link:hover {{
        color: #FAD9B9;
        text-decoration: underline;
    }}

{_LOGIN_ONLY_HIDE_SIDEBAR_CSS}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Backend ----------
def _auth_headers(token: Optional[str]) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _login_user(username: str, password: str) -> tuple[Optional[dict], Optional[str]]:
    """Login con un pequeño reintento para evitar el fallo típico del primer click."""
    last_error = "Servidor no disponible"
    payload = {"username": username, "password": password}

    for attempt in range(2):
        try:
            resp = requests.post(
                f"{API_URL}/auth/login",
                json=payload,
                timeout=(3, 12),
            )

            if resp.status_code == 200:
                return resp.json(), None

            if resp.status_code in (400, 401, 403):
                return None, "Credenciales incorrectas"

            last_error = f"El servidor respondió con estado {resp.status_code}"
        except requests.RequestException:
            last_error = "Servidor no disponible"

        if attempt == 0:
            time.sleep(0.6)

    return None, last_error


def _save_preference(token: str, genre_id: int, new_score: float, all_prefs: list[dict]) -> bool:
    updated = [
        {
            "genre_id": p["genre_id"],
            "score": new_score if int(p["genre_id"]) == int(genre_id) else p["score"],
        }
        for p in all_prefs
    ]

    try:
        resp = requests.put(
            f"{API_URL}/users/me/preferences",
            json=updated,
            headers=_auth_headers(token),
            timeout=(3, 8),
        )
        return 200 <= resp.status_code < 300
    except requests.RequestException:
        return False


def _fetch_preferences(token: str) -> list[dict]:
    try:
        resp = requests.get(
            f"{API_URL}/users/me/preferences",
            headers=_auth_headers(token),
            timeout=(3, 8),
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return []


# Orden visual fijo de la sidebar. Así, al cambiar estrellas, el backend puede
# devolver los géneros ordenados por puntuación, pero la UI mantiene cada género
# en su sitio.
_GENRE_VISUAL_ORDER = {
    "action": 0,
    "accion": 0,
    "acción": 0,
    "adventure": 1,
    "aventura": 1,
    "comedy": 2,
    "comedia": 2,
    "drama": 3,
    "romance": 4,
    "horror": 5,
    "terror": 5,
    "sci-fi": 6,
    "scifi": 6,
    "science fiction": 6,
    "ciencia ficcion": 6,
    "ciencia ficción": 6,
    "thriller": 7,
    "crime": 8,
    "crimen": 8,
    "mystery": 9,
    "misterio": 9,
    "fantasy": 10,
    "fantasia": 10,
    "fantasía": 10,
    "animation": 11,
    "animacion": 11,
    "animación": 11,
    "documentary": 12,
    "documental": 12,
}


def _normalize_genre_name(name: str) -> str:
    return str(name or "").strip().lower().replace("_", "-")


def _stable_preference_order(prefs: list[dict]) -> list[dict]:
    """Mantiene un orden visual estable, independiente del score de cada género."""
    return sorted(
        prefs,
        key=lambda pref: (
            _GENRE_VISUAL_ORDER.get(_normalize_genre_name(pref.get("genre_name")), 10_000),
            int(pref.get("genre_id") or 0),
        ),
    )


def _fetch_movies(token: str) -> list[dict]:
    headers = _auth_headers(token)

    try:
        resp = requests.get(
            f"{API_URL}/recommendations/me",
            headers=headers,
            params={"k": 10, "enrich_tmdb": True},
            timeout=(3, 12),
        )
        if resp.status_code == 200:
            return resp.json().get("recommendations", [])
    except requests.RequestException:
        pass

    try:
        resp = requests.get(
            f"{API_URL}/recommendations/popular",
            params={"k": 10, "enrich_tmdb": True},
            timeout=(3, 12),
        )
        if resp.status_code == 200:
            return resp.json().get("recommendations", [])
    except requests.RequestException:
        pass

    return []


def _extract_year(title: str) -> str:
    match = re.search(r"\((\d{4})\)", title or "")
    return match.group(1) if match else ""


def _clean_title(title: str) -> str:
    return re.sub(r"\s*\(\d{4}\)\s*$", "", title or "").strip()


def _to_card(rec: dict) -> dict:
    title = rec.get("title", "")
    score = rec.get("score", rec.get("rating", 3))

    try:
        rating = round(float(score))
    except (TypeError, ValueError):
        rating = 3

    return {
        "movie_id": rec.get("movie_id") or rec.get("movieId"),
        "title": _clean_title(title),
        "year": _extract_year(title),
        "genre": ", ".join(rec.get("genres", [])) if isinstance(rec.get("genres", []), list) else str(rec.get("genres", "")),
        "image": rec.get("poster_url") or rec.get("poster") or rec.get("image") or "",
        "rating": min(5, max(1, rating)),
        "synopsis": rec.get("overview") or rec.get("synopsis") or "Sin sinopsis disponible.",
    }


# ---------- Componentes UI ----------
def _render_preferences_sidebar(prefs: list[dict]) -> Optional[tuple[int, float]]:
    """Devuelve (genre_id, score) cuando se pulsa una estrella. No usa links para no perder sesión."""
    if not prefs:
        st.sidebar.caption("No tienes géneros guardados.")
        return None

    for pref in prefs:
        genre_id = int(pref["genre_id"])
        genre_name = str(pref.get("genre_name", "Género"))
        current = int(round(float(pref.get("score", 0))))

        st.sidebar.markdown(
            f"<div class='genre-name'>{html.escape(genre_name)}</div>",
            unsafe_allow_html=True,
        )

        star_cols = st.sidebar.columns([0.88, 0.88, 0.88, 0.88, 0.88, 5.6], gap="small")
        for index, col in enumerate(star_cols[:5]):
            score = index + 1
            label = "★" if score <= current else "☆"
            with col:
                if st.button(
                    label,
                    key=f"pref_star_{genre_id}_{score}",
                    help=f"{genre_name}: {score} estrellas",
                    type="secondary",
                    use_container_width=True,
                ):
                    return genre_id, float(score)

    return None


def login_screen() -> None:
    # Login estable: volvemos al flujo simple de app.py, sin formulario,
    # porque era el que no rompía el primer inicio de sesión.
    st.markdown(
        """
        <style>
        /* Ajustes SOLO del login: caja centrada, más pequeña y sin tocar el dashboard */
        .block-container {
            max-width: 760px !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            max-width: 430px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            background-color: rgba(22, 22, 20, 0.85) !important;
            border-radius: 20px !important;
            border: 1px solid rgba(160, 139, 119, 0.2) !important;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6) !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 1.55rem 1.7rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='padding-top: 3.8vh;'></div>", unsafe_allow_html=True)
    _, col_card, _ = st.columns([0.5, 1.2, 0.5])

    with col_card:
        with st.container(border=True):
            if logo_base64:
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:center; margin-bottom:10px;">
                        <img src="data:image/png;base64,{logo_base64}" width="118">
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("<h2 style='margin-bottom:0;'>Iniciar Sesión</h2>", unsafe_allow_html=True)
            st.markdown("<p style='margin-bottom:20px;'>Tu próxima película favorita te espera</p>", unsafe_allow_html=True)

            user = st.text_input("Usuario", placeholder="Tu usuario", key="login_username")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••", key="login_password")

            st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

            if st.button("INICIAR SESIÓN", key="login_submit", use_container_width=True):
                if not user or not password:
                    st.warning("Completa los campos")
                else:
                    data, error = _login_user(user.strip(), password)
                    if data and data.get("access_token"):
                        st.session_state.authenticated = True
                        st.session_state.token = data.get("access_token")
                        st.session_state.username = user.strip()
                        st.rerun()
                    else:
                        st.error(error or "No se pudo iniciar sesión")

            st.markdown(
                """
                <div class="register-container">
                    <a href="/Register" target="_self" class="register-link">¿No tienes cuenta? <b>Regístrate aquí</b></a>
                </div>
                """,
                unsafe_allow_html=True,
            )

def dashboard() -> None:
    token = st.session_state.get("token")
    username = st.session_state.get("username") or "Usuario"

    if st.session_state.pop("_prefs_updated", False):
        st.toast("Gustos actualizados. Recalculando recomendaciones…", icon="🎬")

    # Sidebar
    profile_initial = (username[:1] or "U").upper()
    st.sidebar.markdown(
        f"""
        <div class="sidebar-user-card">
            <div class="username-link profile-shell" title="Ir a Mi Dashboard">
                <div class="profile-card">
                    <div class="profile-avatar">{html.escape(profile_initial)}</div>
                    <div class="profile-copy">
                        <div class="profile-label">Mi perfil</div>
                        <div class="profile-name">{html.escape(username)}</div>
                        <div class="profile-hint">Ir a tu dashboard</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.sidebar.button(
        "Ir a Mi Dashboard",
        key="sidebar_profile_dashboard",
        type="tertiary",
        use_container_width=True,
    ):
        st.switch_page("pages/Dashboard.py")
    st.sidebar.divider()

    st.sidebar.markdown("<h4 class='sidebar-title'>Mis gustos</h4>", unsafe_allow_html=True)

    prefs = _stable_preference_order(_fetch_preferences(token))
    preference_change = _render_preferences_sidebar(prefs)

    if preference_change:
        genre_id, score = preference_change
        ok = _save_preference(token, genre_id, score, prefs)
        if ok:
            st.session_state["_prefs_updated"] = True
            st.rerun()
        else:
            st.sidebar.error("No se pudo guardar el gusto.")

    st.sidebar.markdown("<div class='sidebar-bottom-push'></div>", unsafe_allow_html=True)
    st.sidebar.markdown("<div class='sidebar-actions-spacer'></div>", unsafe_allow_html=True)

    _, col_logout, _ = st.sidebar.columns([0.06, 0.88, 0.06], gap="small")
    with col_logout:
        if st.button("Cerrar Sesión", key="sidebar_logout", type="primary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.token = None
            st.session_state.username = None
            st.rerun()

    # Recomendaciones (HTML/JS)
    recs = _fetch_movies(token)
    movies_data = [_to_card(r) for r in recs]
    movies_json = json.dumps(movies_data, ensure_ascii=False)

    html_code = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            html, body {
                width: 100%;
                height: 100%;
                overflow: hidden;
                margin: 0;
                padding: 0;
                background: transparent;
            }
            body {
                color: white;
                font-family: sans-serif;
                display: flex;
                align-items: flex-start;
                justify-content: center;
            }
            .app-shell {
                width: 100%;
                max-width: 34rem;
                min-height: 100%;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 3.7rem 1rem 0;
                box-sizing: border-box;
            }
            .swipe-left { animation: swipe-left 0.6s ease-out forwards; }
            .swipe-right { animation: swipe-right 0.6s ease-out forwards; }
            @keyframes swipe-left { 100% { transform: translateX(-600px) rotate(-35deg); opacity: 0; } }
            @keyframes swipe-right { 100% { transform: translateX(600px) rotate(35deg); opacity: 0; } }
            .perspective-container { perspective: 1200px; }
            .flip-card-inner {
                position: relative;
                width: 100%;
                height: 100%;
                transition: transform 0.7s cubic-bezier(0.4, 0, 0.2, 1);
                transform-style: preserve-3d;
            }
            .flipped { transform: rotateY(180deg); }
            .card-face {
                position: absolute;
                width: 100%;
                height: 100%;
                backface-visibility: hidden;
                border-radius: 2.2rem;
                overflow: hidden;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
                border: 1px solid rgba(255,255,255,0.05);
            }
            .card-back {
                transform: rotateY(180deg);
                background: linear-gradient(145deg, #1e1e1e, #121212);
                border: 1px solid #333;
                padding: 2.2rem;
                display: flex;
                flex-direction: column;
                box-sizing: border-box;
            }
            .cinematch-title {
                font-size: 3.35rem;
                font-weight: 900;
                font-style: italic;
                letter-spacing: -0.05em;
                background: linear-gradient(to right, #C7AD93, #FAD9B9);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                width: 100%;
                text-align: center;
                display: block;
                margin-bottom: 0;
                line-height: 0.95;
            }
            .info-label {
                color: #A08B77;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 10px;
                letter-spacing: 0.1em;
            }
            .no-poster {
                background: linear-gradient(145deg, #2a2a2a, #1a1a1a);
                display: flex;
                align-items: center;
                justify-content: center;
                color: #555;
                font-size: 4rem;
            }
            .rating-stars {
                display: flex;
                justify-content: center;
                gap: 10px;
                margin-bottom: 8px;
            }
            .rating-stars i {
                cursor: pointer;
                font-size: 1.45rem;
                transition: transform 0.15s, color 0.15s, text-shadow 0.15s;
                color: #4b5563;
            }
            .rating-stars i:hover {
                color: #fbbf24;
                transform: scale(1.25);
                text-shadow: 0 0 12px rgba(251, 191, 36, 0.55);
            }
            .rating-stars i.active {
                color: #fbbf24;
                transform: scale(1.1);
                text-shadow: 0 0 12px rgba(251, 191, 36, 0.5);
            }
            @media (max-height: 780px) {
                .app-shell { padding-top: 1.4rem; }
                .cinematch-title { font-size: 2.8rem; }
                #card-wrapper { max-width: 290px !important; }
            }
        </style>
    </head>
    <body>
        <div class="app-shell">
            <header class="mb-5 w-full text-center">
                <h1 class="cinematch-title">CINEMATCH</h1>
                <p class="text-[#C7AD93] text-[10px] uppercase tracking-[0.3em] font-bold mt-2">Tus recomendaciones</p>
            </header>

            <div id="card-wrapper" class="perspective-container w-full aspect-[2/3] max-w-[320px]">
                <div id="flip-inner" class="flip-card-inner"></div>
            </div>

            <div class="rating-stars mt-5" id="star-rating-container">
                <i class="fa-solid fa-star" onclick="setStarRating(1)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(2)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(3)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(4)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(5)"></i>
            </div>
            <p id="stars-hint" class="text-[#C7AD93]/70 text-[9px] uppercase font-bold tracking-widest mt-0">Selecciona una puntuación</p>

            <div class="flex items-center justify-center gap-12 w-full max-w-[300px] mt-4">
                <button onclick="handleSkip()" title="No la he visto" class="w-14 h-14 bg-gray-900/95 border border-white/10 text-red-500 rounded-full hover:bg-red-500 hover:text-white transition-all shadow-xl flex items-center justify-center">
                    <i class="fa-solid fa-eye-slash text-xl"></i>
                </button>
                <button onclick="handleRate()" title="Enviar puntuación" class="w-14 h-14 bg-gray-900/95 border border-white/10 text-emerald-400 rounded-full hover:bg-emerald-500 hover:text-white transition-all shadow-xl flex items-center justify-center">
                    <i class="fa-solid fa-paper-plane text-xl"></i>
                </button>
            </div>

            <p class="mt-5 text-[#C7AD93] text-[9px] uppercase font-bold tracking-widest">Toca la 'i' para ver detalles</p>
        </div>

        <script>
            let movies = __MOVIES_DATA__;
            const AUTH_TOKEN = "__AUTH_TOKEN__";
            const API_URL = "__API_URL__";
            let currentIndex = 0;
            let currentStarRating = 0;
            let isLoadingMore = false;

            function setStarRating(rating) {
                currentStarRating = rating;
                const stars = document.querySelectorAll('#star-rating-container i');
                stars.forEach((star, index) => {
                    star.classList.toggle('active', index < rating);
                });
                const labels = ['', 'Muy mala', 'Mala', 'Regular', 'Buena', 'Muy buena'];
                document.getElementById('stars-hint').textContent = labels[rating] || 'Selecciona una puntuación';
            }

            function resetStars() {
                currentStarRating = 0;
                document.querySelectorAll('#star-rating-container i').forEach(s => s.classList.remove('active'));
                const hint = document.getElementById('stars-hint');
                if (hint) {
                    hint.textContent = 'Selecciona una puntuación';
                    hint.style.color = '';
                }
            }

            function extractYear(title) {
                const match = (title || '').match(/[(]([0-9]{4})[)]/);
                return match ? match[1] : '';
            }

            function cleanTitle(title) {
                return (title || '').replace(/[ ]*[(][0-9]{4}[)][ ]*$/, '').trim();
            }

            function toCard(rec) {
                const title = rec.title || '';
                const genres = Array.isArray(rec.genres) ? rec.genres.join(', ') : (rec.genres || '');
                const score = Number(rec.score ?? rec.rating ?? 3);
                return {
                    movie_id: rec.movie_id ?? rec.movieId,
                    title: cleanTitle(title),
                    year: extractYear(title),
                    genre: genres,
                    image: rec.poster_url || rec.poster || rec.image || '',
                    rating: Math.min(5, Math.max(1, Math.round(score))),
                    synopsis: rec.overview || rec.synopsis || 'Sin sinopsis disponible.',
                };
            }

            async function loadMoreRecommendations() {
                if (isLoadingMore) return;
                isLoadingMore = true;

                const hint = document.getElementById('reload-hint');
                if (hint) hint.textContent = 'Cargando recomendaciones...';

                try {
                    const response = await fetch(`${API_URL}/recommendations/me?k=10&enrich_tmdb=true`, {
                        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` },
                    });

                    if (!response.ok) throw new Error('No se pudieron cargar recomendaciones');

                    const data = await response.json();
                    const recs = data.recommendations || [];
                    if (!recs.length) throw new Error('No hay recomendaciones disponibles');

                    movies = recs.map(toCard);
                    currentIndex = 0;
                    resetStars();
                    document.getElementById('card-wrapper').innerHTML = '<div id="flip-inner" class="flip-card-inner"></div>';
                    renderCard();
                } catch (error) {
                    if (hint) hint.textContent = 'No se pudieron cargar más. Inténtalo de nuevo.';
                } finally {
                    isLoadingMore = false;
                }
            }

            function renderCard() {
                const inner = document.getElementById('flip-inner');
                const movie = movies[currentIndex];

                if (!movie) {
                    document.getElementById('card-wrapper').innerHTML = `
                        <div class='flex flex-col items-center justify-center gap-4 absolute inset-0 text-center px-4'>
                            <div class='text-[#C7AD93] font-bold'>Has visto todas las recomendaciones</div>
                            <button onclick="loadMoreRecommendations()" class="inline-flex items-center gap-2 rounded-full border border-white/20 bg-gray-900 px-7 py-3 text-white text-sm font-semibold transition hover:bg-gray-800 hover:border-[#C7AD93]">
                                <i class="fa-solid fa-arrows-rotate"></i>
                                Cargar más recomendaciones
                            </button>
                            <p id="reload-hint" class="text-gray-600 text-[9px] uppercase font-bold tracking-widest">Sin volver al login</p>
                        </div>
                    `;
                    return;
                }

                let stars = "";
                for (let i = 1; i <= 5; i++) {
                    stars += `<i class="fa-solid fa-star ${i <= movie.rating ? 'text-yellow-500' : 'text-gray-800'} text-xs"></i> `;
                }

                const imgContent = movie.image
                    ? `<img src="${movie.image}" class="w-full h-full object-cover">`
                    : `<div class="w-full h-full no-poster"><i class="fa-solid fa-film"></i></div>`;

                inner.innerHTML = `
                    <div class="card-face">
                        ${imgContent}
                        <button onclick="toggleFlip(event)" class="absolute top-5 right-5 w-11 h-11 bg-black/40 backdrop-blur-xl rounded-full flex items-center justify-center border border-white/20 text-white z-50 hover:scale-110 transition-transform"><i class="fa-solid fa-info"></i></button>
                        <div class="absolute bottom-0 left-0 right-0 p-7 bg-gradient-to-t from-black via-black/80 to-transparent">
                            <h2 class="text-3xl font-extrabold leading-tight">${movie.title}</h2>
                            <div class="flex items-center gap-3 mt-2 text-gray-400 font-medium text-sm">
                                <span>${movie.year}</span>
                                ${movie.year && movie.genre ? '<span>•</span>' : ''}
                                <span>${movie.genre}</span>
                            </div>
                        </div>
                    </div>
                    <div class="card-face card-back">
                        <div class="flex justify-between items-center mb-6">
                            <span class="text-xs font-black text-red-600 uppercase tracking-tighter">Ficha Técnica</span>
                            <button onclick="toggleFlip(event)"><i class="fa-solid fa-arrow-rotate-left text-xl text-gray-500"></i></button>
                        </div>
                        <h2 class="text-2xl font-bold mb-2">${movie.title}</h2>
                        <div class="flex items-center mb-6">${stars}</div>
                        <div class="space-y-4">
                            <div>
                                <h4 class="info-label mb-1">Sinopsis</h4>
                                <p class="text-gray-300 text-sm leading-relaxed">${movie.synopsis}</p>
                            </div>
                            <div class="grid grid-cols-2 gap-4 pt-4">
                                <div class="bg-white/5 p-3 rounded-2xl border border-white/5">
                                    <p class="info-label">Género</p>
                                    <p class="text-xs">${movie.genre || 'N/A'}</p>
                                </div>
                                <div class="bg-white/5 p-3 rounded-2xl border border-white/5">
                                    <p class="info-label">Año</p>
                                    <p class="text-xs">${movie.year || 'N/A'}</p>
                                </div>
                            </div>
                        </div>
                    </div>`;
            }

            function saveRating(movieId, rating) {
                if (!AUTH_TOKEN || !movieId) return;
                fetch(`${API_URL}/ratings`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${AUTH_TOKEN}`,
                    },
                    body: JSON.stringify({ movie_id: movieId, rating: rating }),
                }).catch(() => {});
            }

            function toggleFlip(e) {
                e.stopPropagation();
                document.getElementById('flip-inner').classList.toggle('flipped');
            }

            function advanceCard(direction) {
                const wrapper = document.getElementById('card-wrapper');
                const inner = document.getElementById('flip-inner');
                if (inner) inner.classList.remove('flipped');

                wrapper.classList.add(direction === 'left' ? 'swipe-left' : 'swipe-right');
                setTimeout(() => {
                    currentIndex++;
                    wrapper.classList.remove('swipe-left', 'swipe-right');
                    resetStars();
                    renderCard();
                }, 600);
            }

            function handleSkip() {
                advanceCard('left');
            }

            function handleRate() {
                if (currentStarRating === 0) {
                    const hint = document.getElementById('stars-hint');
                    hint.textContent = '⚠ Elige una puntuación primero';
                    hint.style.color = '#f87171';
                    setTimeout(() => {
                        hint.textContent = 'Selecciona una puntuación';
                        hint.style.color = '';
                    }, 2000);
                    return;
                }

                const movie = movies[currentIndex];
                if (movie) saveRating(movie.movie_id, currentStarRating);
                advanceCard('right');
            }

            renderCard();
        </script>
    </body>
    </html>
    """

    html_code = html_code.replace("__MOVIES_DATA__", movies_json)
    html_code = html_code.replace("__AUTH_TOKEN__", token or "")
    html_code = html_code.replace("__API_URL__", PUBLIC_API_URL)
    components.html(html_code, height=880, scrolling=False)


# ---------- Arranque ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None

if not st.session_state.authenticated or not st.session_state.token:
    login_screen()
else:
    dashboard()
