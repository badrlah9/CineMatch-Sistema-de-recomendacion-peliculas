import os
import re
from datetime import datetime

import altair as alt
import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Cinematch - Dashboard", page_icon="🎬", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #161614; }
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
if st.sidebar.button("← Inicio"):
    st.switch_page("app.py")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.authenticated = False
    st.session_state.token = None
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
likes    = sum(1 for r in ratings_raw if r["rating"] >= 4.0)
dislikes = sum(1 for r in ratings_raw if r["rating"] <= 2.0)
neutral  = total - likes - dislikes
precision = round(likes / total * 100) if total else 0

fav_genre = prefs_raw[0]["genre_name"] if prefs_raw else "—"

dates = [r["rated_at"][:10] for r in ratings_raw if r.get("rated_at")]
dias_activo = len(set(dates))

source_labels = {"model": "Modelo IA", "genre_based": "Por género", "popularity": "Popularidad"}
source_colors = {"Modelo IA": "#78444A", "Por género": "#A08B77", "Popularidad": "#3B443F"}

# ── Cabecera ──────────────────────────────────────────────────────────────────
st.markdown("<h1 style='margin-bottom:4px;'>📊 Mi Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#555;font-size:0.85rem;margin-top:0;'>Así te está conociendo CineMatch</p>", unsafe_allow_html=True)
st.divider()

# ── Fila de métricas ──────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Películas valoradas", total)
c2.metric("Precisión del modelo", f"{precision}%", help="% de recomendaciones que te gustaron")
c3.metric("Días activo", dias_activo)
c4.metric("Género favorito", fav_genre)

st.divider()

# ── Fila principal: Precisión + Fuente de recomendaciones ────────────────────
col_prec, col_source = st.columns([1, 1])

with col_prec:
    with st.container(border=True):
        st.markdown("<p class='section-title'>Precisión del modelo sobre ti</p>", unsafe_allow_html=True)

        if total == 0:
            st.caption("Valora algunas películas para ver la precisión.")
        else:
            df_donut = pd.DataFrame({
                "tipo":  ["Te gustaron ❤️", "No te gustaron ❌", "Neutral ⭐"],
                "count": [likes, dislikes, neutral],
            })
            donut = (
                alt.Chart(df_donut)
                .mark_arc(innerRadius=65, outerRadius=110, cornerRadius=4)
                .encode(
                    theta=alt.Theta("count:Q"),
                    color=alt.Color(
                        "tipo:N",
                        scale=alt.Scale(
                            domain=["Te gustaron ❤️", "No te gustaron ❌", "Neutral ⭐"],
                            range=["#4ade80", "#f87171", "#6b7280"],
                        ),
                        legend=alt.Legend(orient="bottom", labelColor="#A08B77", titleColor="#A08B77"),
                    ),
                    tooltip=["tipo:N", "count:Q"],
                )
                .properties(width=260, height=260, background="#1e1e1c")
                .configure_view(strokeWidth=0)
            )

            center_col, _ = st.columns([1, 0.01])
            with center_col:
                st.altair_chart(donut, use_container_width=True)

            st.markdown(
                f"<p style='text-align:center;font-size:1.6rem;font-weight:900;color:#FAD9B9;margin-top:-8px;'>"
                f"{precision}% de acierto</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='text-align:center;font-size:0.8rem;color:#666;'>"
                f"De {total} swipes: {likes} gustaron · {dislikes} no gustaron</p>",
                unsafe_allow_html=True,
            )

with col_source:
    with st.container(border=True):
        st.markdown("<p class='section-title'>¿De dónde vienen tus recomendaciones?</p>", unsafe_allow_html=True)

        if not recs_items:
            st.caption("No hay recomendaciones disponibles.")
        else:
            source_counts: dict[str, int] = {label: 0 for label in source_labels.values()}
            for item in recs_items:
                label = source_labels.get(item.get("source", ""), item.get("source", "Desconocido"))
                source_counts[label] = source_counts.get(label, 0) + 1

            df_source = pd.DataFrame(
                [{"Origen": k, "Películas": v} for k, v in source_counts.items()]
            )
            color_range = [source_colors.get(k, "#555") for k in df_source["Origen"]]

            bars = (
                alt.Chart(df_source)
                .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
                .encode(
                    x=alt.X("Origen:N", axis=alt.Axis(labelColor="#A08B77", tickColor="#A08B77", domainColor="#333", labelAngle=0)),
                    y=alt.Y("Películas:Q", axis=alt.Axis(labelColor="#A08B77", tickColor="#A08B77", domainColor="#333", grid=False)),
                    color=alt.Color(
                        "Origen:N",
                        scale=alt.Scale(domain=list(df_source["Origen"]), range=color_range),
                        legend=None,
                    ),
                    tooltip=["Origen:N", "Películas:Q"],
                )
                .properties(width=280, height=240, background="#1e1e1c")
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(bars, use_container_width=True)

            primary = max(source_counts, key=source_counts.get)
            explanations = {
                "Modelo IA":    "El modelo te conoce bien y usa tu historial para recomendar.",
                "Por género":   "El sistema usa tus géneros favoritos como base principal.",
                "Popularidad":  "Aún aprendiendo sobre ti — usa películas populares como base.",
            }
            st.info(explanations.get(primary, ""))

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
with st.container(border=True):
    st.markdown("<p class='section-title'>Historial de valoraciones</p>", unsafe_allow_html=True)

    if not ratings_raw:
        st.caption("Todavía no has valorado ninguna película.")
    else:
        f1, f2 = st.columns([1, 2])
        filtro   = f1.selectbox("", ["Todas", "❤️ Me gustaron", "❌ No me gustaron"], label_visibility="collapsed")
        busqueda = f2.text_input("", placeholder="Buscar por título...", label_visibility="collapsed")

        shown = ratings_raw
        if filtro == "❤️ Me gustaron":
            shown = [r for r in shown if r["rating"] >= 4.0]
        elif filtro == "❌ No me gustaron":
            shown = [r for r in shown if r["rating"] <= 2.0]
        if busqueda:
            shown = [r for r in shown if busqueda.lower() in r["title"].lower()]

        st.caption(f"{len(shown)} de {total} valoraciones")

        for r in shown:
            badge = "❤️" if r["rating"] >= 4.0 else ("❌" if r["rating"] <= 2.0 else "⭐")
            date_str = r["rated_at"][:10] if r.get("rated_at") else ""
            st.markdown(
                f"{badge} &nbsp; **{_clean_title(r['title'])}** "
                f"<span style='color:#555;font-size:0.82em;'>· {_extract_year(r['title'])} · {date_str}</span>",
                unsafe_allow_html=True,
            )
