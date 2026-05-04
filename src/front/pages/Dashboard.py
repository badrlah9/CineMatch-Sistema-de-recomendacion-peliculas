import html
import os
import re
from datetime import datetime, timezone

import altair as alt
import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Cinematch - Dashboard", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    html, body, .stApp {
        min-height: 100vh !important;
    }

    .stApp {
        background-color: #161614;
    }

    /* Header transparente: conservamos la flecha nativa, ocultamos Deploy/toolbar. */
    header[data-testid="stHeader"] {
        display: block !important;
        visibility: visible !important;
        position: fixed !important;
        inset: 0 0 auto 0 !important;
        height: 3.2rem !important;
        min-height: 3.2rem !important;
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
        pointer-events: none !important;
        z-index: 1000000 !important;
    }

    header[data-testid="stHeader"]::after {
        content: "";
        position: fixed;
        top: 0;
        right: 0;
        width: 260px;
        height: 58px;
        background: #161614;
        pointer-events: none;
        z-index: 1000001;
    }

    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="stDeployButton"],
    [data-testid*="Deploy"],
    [data-testid="stSidebarNav"],
    [data-testid="stMainMenu"],
    [data-testid="stToolbarActions"],
    [data-testid="stHeaderActionElements"],
    [data-testid="stToolbar"] button:not([aria-label*="sidebar" i]):not([aria-label*="barra lateral" i]),
    header[data-testid="stHeader"] button:not([aria-label*="sidebar" i]):not([aria-label*="barra lateral" i]),
    header[data-testid="stHeader"] a,
    button[title*="Deploy"],
    button[aria-label*="Deploy"],
    .stDeployButton,
    #MainMenu,
    footer {
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

    [data-testid="stToolbar"] {
        background: transparent !important;
        pointer-events: none !important;
    }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[aria-label*="sidebar" i],
    button[aria-label*="barra lateral" i] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        z-index: 2147483647 !important;
    }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        position: fixed !important;
        top: 0.72rem !important;
        left: 0.72rem !important;
        width: 2.65rem !important;
        height: 2.65rem !important;
        align-items: center !important;
        justify-content: center !important;
        background: rgba(32, 35, 45, 0.96) !important;
        border: 1px solid rgba(250, 217, 185, 0.30) !important;
        border-radius: 999px !important;
        box-shadow: 0 10px 28px rgba(0,0,0,0.55) !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
    }

    [data-testid="collapsedControl"] button,
    [data-testid="stSidebarCollapsedControl"] button,
    button[aria-label*="sidebar" i],
    button[aria-label*="barra lateral" i] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 2.45rem !important;
        height: 2.45rem !important;
        color: #FAD9B9 !important;
        background: rgba(32, 35, 45, 0.96) !important;
        border: 1px solid rgba(250, 217, 185, 0.28) !important;
        border-radius: 999px !important;
        box-shadow: 0 10px 28px rgba(0,0,0,0.55) !important;
        pointer-events: auto !important;
    }

    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg,
    button[aria-label*="sidebar" i] svg,
    button[aria-label*="barra lateral" i] svg {
        width: 1.25rem !important;
        height: 1.25rem !important;
        color: #FAD9B9 !important;
        fill: #FAD9B9 !important;
        stroke: #FAD9B9 !important;
        stroke-width: 2.5px !important;
    }

    section[data-testid="stSidebar"] {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        background-color: #20232D !important;
        border-right: 1px solid rgba(250, 217, 185, 0.06) !important;
        z-index: 1000002 !important;
    }

    section[data-testid="stSidebar"] * {
        pointer-events: auto !important;
    }

    section[data-testid="stSidebar"] .block-container {
        height: 100vh !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
        padding: 0.55rem 0.65rem 0.8rem 0.65rem !important;
    }

    section[data-testid="stSidebar"] .block-container > div:first-child {
        min-height: calc(100vh - 1.35rem) !important;
        display: flex !important;
        flex-direction: column !important;
    }

    .sidebar-user-card {
        margin-top: 0.1rem !important;
        margin-bottom: 0.75rem !important;
        padding: 0 !important;
    }

    .username-link,
    .username-link:visited,
    .username-link:hover,
    .username-link:active {
        color: inherit !important;
        text-decoration: none !important;
    }

    .username-link h3 {
        color: #C7AD93 !important;
        margin: 0 !important;
        cursor: pointer;
        position: relative;
        display: inline-block;
        font-size: 1.15rem !important;
        line-height: 1.1 !important;
        font-weight: 850 !important;
        letter-spacing: 0.03em !important;
        transition: all 0.2s ease;
    }

    .username-link:hover h3 {
        color: #FAD9B9 !important;
        text-shadow: 0 0 8px rgba(250, 217, 185, 0.35);
    }

    .sidebar-actions-spacer {
        padding-top: 0.85rem !important;
        border-top: 1px solid rgba(160, 139, 119, 0.25) !important;
    }

    section[data-testid="stSidebar"] .element-container:has(.sidebar-actions-spacer) {
        margin-top: auto !important;
    }

    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"],
    section[data-testid="stSidebar"] .stButton>button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 2.7rem !important;
        min-height: 2.7rem !important;
        border-radius: 13px !important;
        font-size: 0.78rem !important;
        font-weight: 800 !important;
        padding: 0.2rem 0.7rem !important;
        white-space: nowrap !important;
        background-color: #78444A !important;
        color: #FAD9B9 !important;
        border: 1px solid rgba(250, 217, 185, 0.13) !important;
        box-shadow: 0 9px 19px rgba(0,0,0,0.28) !important;
    }

    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p,
    section[data-testid="stSidebar"] .stButton>button p {
        width: 100% !important;
        margin: 0 !important;
        text-align: center !important;
        color: #FAD9B9 !important;
    }

    h1, h2, h3 { color: #FAD9B9 !important; }
    p, label, div, span { color: #A08B77 !important; }

    [data-testid="stMetricValue"]        { color: #FAD9B9 !important; font-size: 2.2rem !important; font-weight: 900 !important; }
    [data-testid="stMetricLabel"]        { color: #A08B77 !important; font-size: 0.8rem !important; text-transform: uppercase; letter-spacing: 0.1em; }
    [data-testid="stMetricDeltaIcon"]    { display: none; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1e1e1c !important;
        border-radius: 16px !important;
        padding: 28px 36px !important;
        border: 1px solid #2e2e2a !important;
    }

    .section-title {
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: #78444A !important;
        margin-bottom: 12px;
    }

    .source-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        margin: 3px;
    }

    [data-testid="stArrowVegaLiteChart"] > div {
        padding: 12px !important;
    }

    .stButton>button {
        background-color: #78444A !important;
        color: white !important;
        border-radius: 10px !important;
        border: none !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("Debes iniciar sesión para ver tu dashboard.")
    st.switch_page("app.py")

# ── Sidebar ──────────────────────────────────────────────────────────────────
username = st.session_state.get("username") or "Usuario"
st.sidebar.markdown(
    f"""
    <div class="sidebar-user-card">
        <a href="/" target="_self" class="username-link">
            <h3>{html.escape(username)}</h3>
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.divider()

if st.sidebar.button("← Inicio", key="sidebar_home", type="primary", use_container_width=True):
    st.switch_page("app.py")

st.sidebar.markdown("<div class='sidebar-actions-spacer'></div>", unsafe_allow_html=True)
_, col_logout, _ = st.sidebar.columns([0.12, 0.76, 0.12], gap="small")
with col_logout:
    if st.button("Cerrar Sesión", key="sidebar_logout", type="primary", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.token = None
        st.session_state.username = None
        st.switch_page("app.py")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _clean_title(title: str) -> str:
    return re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()

def _extract_year(title: str) -> str:
    m = re.search(r'\((\d{4})\)', title)
    return m.group(1) if m else "—"

def _get(path: str, token: str, params: dict = None) -> dict | list | None:
    try:
        r = requests.get(
            f"{API_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=8,
        )
        return r.json() if r.status_code == 200 else None
    except requests.RequestException:
        return None


# ── Carga de datos ────────────────────────────────────────────────────────────
token = st.session_state.token

with st.spinner("Cargando tu dashboard..."):
    ratings_raw  = _get("/ratings/me", token) or []
    prefs_raw    = _get("/users/me/preferences", token) or []
    recs_raw     = _get("/recommendations/me", token, {"k": 20, "enrich_tmdb": False}) or {}

recs_items = recs_raw.get("recommendations", []) if isinstance(recs_raw, dict) else []

# ── Pre-cálculos ──────────────────────────────────────────────────────────────
total    = len(ratings_raw)
altas    = sum(1 for r in ratings_raw if r["rating"] >= 4.0)   # 4-5 ★
bajas    = sum(1 for r in ratings_raw if r["rating"] <= 2.0)   # 1-2 ★
medias   = total - altas - bajas                                # 3 ★
precision = round(altas / total * 100) if total else 0

fav_genre = prefs_raw[0]["genre_name"] if prefs_raw else "—"

dates = [r["rated_at"][:10] for r in ratings_raw if r.get("rated_at")]
dias_activo = len(set(dates))

if ratings_raw:
    timestamps = [
        datetime.fromisoformat(r["rated_at"].replace("Z", "+00:00"))
        for r in ratings_raw if r.get("rated_at")
    ]
    primera = min(timestamps)
    delta   = datetime.now(timezone.utc) - primera
    _d = delta.days
    _h = delta.seconds // 3600
    _m = (delta.seconds % 3600) // 60
    if _d > 0:
        tiempo_activo = f"{_d}d {_h}h {_m}m"
    elif _h > 0:
        tiempo_activo = f"{_h}h {_m}m"
    else:
        tiempo_activo = f"{_m}m"
else:
    tiempo_activo = "—"

source_labels = {"model": "Modelo IA", "genre_based": "Por género", "popularity": "Popularidad"}
source_colors = {"Modelo IA": "#78444A", "Por género": "#A08B77", "Popularidad": "#3B443F"}

# ── Cabecera ──────────────────────────────────────────────────────────────────
st.markdown("<h1 style='margin-bottom:4px;'>Mi Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#555;font-size:0.85rem;margin-top:0;'>Así te está conociendo CineMatch</p>", unsafe_allow_html=True)
st.divider()

# ── Fila de métricas ──────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Películas valoradas", total)
c2.metric("Bien valoradas", f"{precision}%", help="% de películas a las que diste 4 o 5 estrellas")
c3.metric("Tiempo activo", tiempo_activo, help="Desde tu primera valoración hasta ahora")
c4.metric("Género favorito", fav_genre)

st.divider()

# ── Fila principal: Precisión + Fuente de recomendaciones ────────────────────
col_prec, col_source = st.columns([1, 1])

with col_prec:
    with st.container(border=True):
        st.markdown("<p class='section-title'>Distribución de tus puntuaciones</p>", unsafe_allow_html=True)

        if total == 0:
            st.caption("Valora algunas películas para ver tu distribución.")
        else:
            df_donut = pd.DataFrame({
                "tipo":  ["4-5 ★ Buenas", "3 ★ Regular", "1-2 ★ Malas"],
                "count": [altas, medias, bajas],
            })
            donut = (
                alt.Chart(df_donut)
                .mark_arc(innerRadius=65, outerRadius=110, cornerRadius=4)
                .encode(
                    theta=alt.Theta("count:Q"),
                    color=alt.Color(
                        "tipo:N",
                        scale=alt.Scale(
                            domain=["4-5 ★ Buenas", "3 ★ Regular", "1-2 ★ Malas"],
                            range=["#4ade80", "#fbbf24", "#f87171"],
                        ),
                        legend=alt.Legend(orient="bottom", labelColor="#A08B77", titleColor="#A08B77"),
                    ),
                    tooltip=[
                        alt.Tooltip("tipo:N", title="Categoría"),
                        alt.Tooltip("count:Q", title="Películas"),
                    ],
                )
                .properties(width=260, height=260, background="#1e1e1c")
                .configure_view(strokeWidth=0)
            )

            center_col, _ = st.columns([1, 0.01])
            with center_col:
                st.altair_chart(donut, use_container_width=True)

            st.markdown(
                f"<p style='text-align:center;font-size:1.6rem;font-weight:900;color:#FAD9B9;margin-top:-8px;'>"
                f"{altas} de {total} con 4-5 ★</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='text-align:center;font-size:0.8rem;color:#666;'>"
                f"{altas} buenas · {medias} regular · {bajas} malas</p>",
                unsafe_allow_html=True,
            )

with col_source:
    with st.container(border=True):
        st.markdown("<p class='section-title'>Composición del motor de recomendaciones</p>", unsafe_allow_html=True)

        has_prefs = len(prefs_raw) > 0

        if total == 0:
            w_svd, w_emb, w_content = 0.00, 0.00, 1.00
        elif total < 5:
            w_svd, w_emb, w_content = (0.25, 0.20, 0.55) if has_prefs else (0.40, 0.25, 0.35)
        elif total < 15:
            w_svd, w_emb, w_content = (0.35, 0.25, 0.40) if has_prefs else (0.48, 0.27, 0.25)
        else:
            w_svd, w_emb, w_content = (0.45, 0.30, 0.25) if has_prefs else (0.55, 0.30, 0.15)

        p_svd     = round(w_svd     * 100)
        p_emb     = round(w_emb     * 100)
        p_content = round(w_content * 100)

        def _bar(label, pct, color, desc):
            return f"""
            <div style="margin-bottom:18px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
                    <span style="color:#FAD9B9;font-size:0.85rem;font-weight:700;">{label}</span>
                    <span style="color:#FAD9B9;font-size:0.85rem;font-weight:900;">{pct}%</span>
                </div>
                <div style="background:#2e2e2a;border-radius:6px;height:10px;overflow:hidden;">
                    <div style="width:{pct}%;background:{color};height:100%;border-radius:6px;
                                transition:width 0.6s ease;"></div>
                </div>
                <div style="color:#555;font-size:0.75rem;margin-top:4px;">{desc}</div>
            </div>"""

        if total == 0:
            next_msg = "Valora al menos 1 película para activar el modelo colaborativo."
        elif total < 5:
            next_msg = f"Con {5 - total} valoraciones más subirá el peso colaborativo."
        elif total < 15:
            next_msg = f"Con {15 - total} valoraciones más el modelo te conocerá mejor."
        else:
            next_msg = "El modelo colaborativo tiene suficiente historial tuyo."

        st.markdown(
            _bar("Modelo colaborativo (IA)", p_svd, "#78444A",
                 "Infiere tus gustos a partir de tus valoraciones") +
            _bar("Usuarios similares", p_emb, "#A08B77",
                 "Recomienda lo que valoraron bien personas con gustos parecidos") +
            _bar("Contenido (géneros + popularidad)", p_content, "#3B443F",
                 "Se basa en tus géneros favoritos y el rating histórico de cada película"),
            unsafe_allow_html=True,
        )
        st.caption(f"Basado en {total} valoraciones tuyas · {next_msg}")

st.divider()

# ── Actividad + Géneros en la misma fila ──────────────────────────────────────
col_act, col_gen = st.columns([1, 1])

with col_act:
    with st.container(border=True):
        st.markdown("<p class='section-title'>Actividad — valoraciones por día</p>", unsafe_allow_html=True)

        if not dates:
            st.caption("Aún no has valorado ninguna película.")
        else:
            counts = pd.Series(dates).value_counts().to_dict()
            all_days = pd.date_range(min(dates), max(dates), freq="D")
            df_activity = pd.DataFrame({
                "Fecha":        all_days,
                "Valoraciones": [counts.get(d.strftime("%Y-%m-%d"), 0) for d in all_days],
            })

            area = (
                alt.Chart(df_activity)
                .mark_area(
                    line={"color": "#78444A", "strokeWidth": 2},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="#78444A", offset=0),
                            alt.GradientStop(color="#1e1e1c", offset=1),
                        ],
                        x1=1, x2=1, y1=1, y2=0,
                    ),
                    point=alt.OverlayMarkDef(color="#FAD9B9", size=60),
                )
                .encode(
                    x=alt.X("Fecha:T", axis=alt.Axis(
                        labelColor="#A08B77", domainColor="#333",
                        format="%d %b", tickCount=len(all_days),
                    )),
                    y=alt.Y("Valoraciones:Q", axis=alt.Axis(
                        labelColor="#A08B77", domainColor="#333",
                        grid=False, tickMinStep=1, format="d",
                    )),
                    tooltip=[alt.Tooltip("Fecha:T", format="%d %b %Y"), "Valoraciones:Q"],
                )
                .properties(height=220, background="#1e1e1c")
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(area, use_container_width=True)

with col_gen:
    with st.container(border=True):
        st.markdown("<p class='section-title'>Tus géneros — puntuación declarada</p>", unsafe_allow_html=True)

        if not prefs_raw:
            st.caption("No tienes preferencias de género guardadas.")
        else:
            df_prefs = pd.DataFrame(prefs_raw)[["genre_name", "score"]].rename(
                columns={"genre_name": "Género", "score": "Puntuación"}
            ).sort_values("Puntuación", ascending=False)

            hbar = (
                alt.Chart(df_prefs)
                .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
                .encode(
                    y=alt.Y("Género:N", sort="-x", axis=alt.Axis(labelColor="#A08B77", domainColor="#333")),
                    x=alt.X("Puntuación:Q", scale=alt.Scale(domain=[0, 5]),
                             axis=alt.Axis(labelColor="#A08B77", domainColor="#333", grid=False,
                                           values=[0, 1, 2, 3, 4, 5], format="d")),
                    color=alt.Color(
                        "Puntuación:Q",
                        scale=alt.Scale(domain=[1, 5], range=["#3B443F", "#FAD9B9"]),
                        legend=None,
                    ),
                    tooltip=["Género:N", alt.Tooltip("Puntuación:Q", format="d")],
                )
                .properties(height=220, background="#1e1e1c")
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(hbar, use_container_width=True)

st.divider()

# ── Historial de valoraciones ─────────────────────────────────────────────────
PAGE_SIZE = 10

with st.container(border=True):
    st.markdown("<p class='section-title'>Historial de valoraciones</p>", unsafe_allow_html=True)

    if not ratings_raw:
        st.caption("Todavía no has valorado ninguna película.")
    else:
        f1, f2 = st.columns([1, 2])
        filtro   = f1.selectbox("", ["Todas", "Bien valoradas (4-5 ★)", "Mal valoradas (1-2 ★)"], label_visibility="collapsed", key="hist_filter")
        busqueda = f2.text_input("", placeholder="Buscar por título...", label_visibility="collapsed", key="hist_search")

        # Resetear paginación si cambian los filtros
        filter_key = (filtro, busqueda)
        if st.session_state.get("_hist_filter_key") != filter_key:
            st.session_state["_hist_filter_key"] = filter_key
            st.session_state["hist_shown"] = PAGE_SIZE

        shown = ratings_raw
        if filtro == "Bien valoradas (4-5 ★)":
            shown = [r for r in shown if r["rating"] >= 4.0]
        elif filtro == "Mal valoradas (1-2 ★)":
            shown = [r for r in shown if r["rating"] <= 2.0]
        if busqueda:
            shown = [r for r in shown if busqueda.lower() in r["title"].lower()]

        n_shown = st.session_state.get("hist_shown", PAGE_SIZE)
        displayed = shown[:n_shown]

        st.caption(f"Mostrando {len(displayed)} de {len(shown)} valoraciones")

        for r in displayed:
            filled  = round(r["rating"])
            stars   = "★" * filled + "☆" * (5 - filled)
            date_str = r["rated_at"][:10] if r.get("rated_at") else ""
            st.markdown(
                f"<span style='color:#fbbf24;font-size:1rem;'>{stars}</span> &nbsp;"
                f"**{_clean_title(r['title'])}** "
                f"<span style='color:#555;font-size:0.82em;'>· {_extract_year(r['title'])} · {date_str}</span>",
                unsafe_allow_html=True,
            )

        if n_shown < len(shown):
            remaining = len(shown) - n_shown
            if st.button(f"Cargar {min(PAGE_SIZE, remaining)} más ({remaining} restantes)"):
                st.session_state["hist_shown"] = n_shown + PAGE_SIZE
                st.rerun()
