import os

import requests
import streamlit as st

API_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# Mapeo de nombres en español a los nombres en inglés que usa la base de datos (MovieLens)
GENRE_MAP = {
    "Acción":          "Action",
    "Comedia":         "Comedy",
    "Drama":           "Drama",
    "Terror":          "Horror",
    "Ciencia Ficción": "Sci-Fi",
    "Romance":         "Romance",
    "Animación":       "Animation",
    "Aventura":        "Adventure",
    "Bélica":          "War",
    "Crimen":          "Crime",
    "Documental":      "Documentary",
    "Fantasía":        "Fantasy",
    "Musical":         "Musical",
    "Misterio":        "Mystery",
    "Western":         "Western",
    "Cine Negro":      "Film-Noir",
}

# 1. Configuración
st.set_page_config(page_title="Cinematch - Registro Completo", page_icon="🎬", layout="centered")

# Estilo con vuestra paleta
st.markdown(f"""
    <style>
    .stApp {{ background-color: #161614; }}
    h1, h2, h3, p, label {{ color: #A08B77 !important; }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: #3B443F !important;
        border-radius: 20px !important;
        padding: 40px !important;
        border: 1px solid #3F2B1F !important;
    }}

    .genre-label {{
        color: #A08B77;
        font-weight: bold;
        text-align: center;
        margin-top: -10px;
        margin-bottom: 20px;
    }}

    .stButton>button {{
        background-color: #78444A !important;
        color: white !important;
        border-radius: 10px !important;
        height: 3.5em !important;
        width: 100% !important;
        border: none !important;
        font-weight: bold !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def _fetch_genre_name_to_id() -> dict[str, int]:
    """Obtiene el mapa nombre_inglés → genre_id desde el backend."""
    try:
        resp = requests.get(f"{API_URL}/genres", timeout=5)
        if resp.status_code == 200:
            return {g["name"]: g["genre_id"] for g in resp.json()}
    except requests.RequestException:
        pass
    return {}


def _build_preferences(
    votos_estrellas: dict[str, int | None],
    generos_extra: list[str],
    name_to_id: dict[str, int],
) -> list[dict]:
    """Construye la lista de preferencias para la API a partir de los datos del formulario."""
    prefs: dict[int, float] = {}

    # Géneros valorados con estrellas: st.feedback devuelve 0-4 (None = sin valorar)
    # Mapeamos 0→1.0 ... 4→5.0
    for es_name, rating_val in votos_estrellas.items():
        if rating_val is None:
            continue
        en_name = GENRE_MAP.get(es_name)
        if en_name and en_name in name_to_id:
            prefs[name_to_id[en_name]] = float(rating_val + 1)

    # Géneros extra seleccionados: score por defecto 3.0
    for es_name in generos_extra:
        en_name = GENRE_MAP.get(es_name)
        if en_name and en_name in name_to_id:
            genre_id = name_to_id[en_name]
            if genre_id not in prefs:
                prefs[genre_id] = 3.0

    return [{"genre_id": gid, "score": score} for gid, score in prefs.items()]


def registro_total():
    st.markdown("<h1 style='text-align: center;'>🎬 Registro Cinematch</h1>", unsafe_allow_html=True)

    with st.container(border=True):
        # --- SECCIÓN 1: DATOS DE CUENTA ---
        st.subheader("1. Crear Cuenta")
        c1, c2 = st.columns(2)
        user = c1.text_input("Usuario", placeholder="usuario123")
        password = c2.text_input("Contraseña", type="password")

        st.divider()

        # --- SECCIÓN 2: ESTRELLAS (Géneros Principales) ---
        st.subheader("2. Tus Imprescindibles")
        st.write("Puntúa estos géneros base:")

        generos_top = ["Acción", "Comedia", "Drama", "Terror", "Ciencia Ficción", "Romance"]
        votos_estrellas: dict[str, int | None] = {}

        for i in range(0, len(generos_top), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(generos_top):
                    gen = generos_top[i + j]
                    with cols[j]:
                        rating = st.feedback("stars", key=f"star_{gen}")
                        st.markdown(f"<p class='genre-label'>{gen}</p>", unsafe_allow_html=True)
                        votos_estrellas[gen] = rating  # None si no se ha valorado

        # --- SECCIÓN 3: SELECTOR (Géneros Extra) ---
        st.subheader("3. Otros intereses")
        st.write("¿Te gusta algo más específico?")

        otros_generos = [
            "Animación", "Aventura", "Bélica", "Crimen",
            "Documental", "Fantasía", "Musical", "Misterio", "Western", "Cine Negro",
        ]

        generos_extra = st.multiselect(
            "Busca y añade otros géneros:",
            options=otros_generos,
            placeholder="Ej: Documental, Misterio...",
        )

        st.divider()

        if st.button("Finalizar Registro"):
            if not user or not password:
                st.error("Faltan datos por rellenar.")
                return

            # 1. Registrar usuario
            try:
                reg_resp = requests.post(
                    f"{API_URL}/auth/register",
                    json={"username": user, "password": password},
                    timeout=5,
                )
            except requests.RequestException:
                st.error("No se puede conectar con el servidor. ¿Está el backend en marcha?")
                return

            if reg_resp.status_code == 409:
                st.error("El nombre de usuario ya está en uso.")
                return
            if reg_resp.status_code != 201:
                detail = reg_resp.json().get("detail", "Error desconocido")
                st.error(f"Error al registrar: {detail}")
                return

            # 2. Login para obtener el token
            try:
                login_resp = requests.post(
                    f"{API_URL}/auth/login",
                    json={"username": user, "password": password},
                    timeout=5,
                )
            except requests.RequestException:
                st.warning("Registro correcto, pero no se pudo iniciar sesión automáticamente.")
                return

            if login_resp.status_code != 200:
                st.warning("Registro correcto. Inicia sesión manualmente.")
                return

            token = login_resp.json()["access_token"]

            # 3. Guardar preferencias de género (si el usuario valoró algo)
            name_to_id = _fetch_genre_name_to_id()
            prefs = _build_preferences(votos_estrellas, generos_extra, name_to_id)

            if prefs:
                try:
                    requests.put(
                        f"{API_URL}/users/me/preferences",
                        json=prefs,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5,
                    )
                except requests.RequestException:
                    pass  # Las preferencias son opcionales; no bloqueamos el registro

            # 4. Guardar sesión y redirigir al dashboard
            st.session_state.token = token
            st.session_state.authenticated = True
            st.success(f"¡Perfil creado con éxito para {user}!")
            st.balloons()
            st.switch_page("app.py")


if __name__ == "__main__":
    registro_total()
