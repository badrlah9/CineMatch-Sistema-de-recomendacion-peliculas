import os

import requests
import streamlit as st
import base64
import os

<<<<<<< HEAD
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
=======
# 1. Configuración (DEBE SER LO PRIMERO)
>>>>>>> frontv2
st.set_page_config(page_title="Cinematch - Registro Completo", page_icon="🎬", layout="centered")

# --- LÓGICA DE FONDO ---
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None

current_dir = os.path.dirname(os.path.abspath(__file__))
path_to_img = os.path.join(current_dir, "assets", "fondo.png") 
img_b64 = get_base64_image(path_to_img)

if img_b64:
    bg_style = f"""
    <style>
    .stApp {{
        background-image: linear-gradient(rgba(22, 22, 20, 0.5), rgba(22, 22, 20, 0.5)), 
                          url("data:image/png;base64,{img_b64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    """
else:
    bg_style = "<style>.stApp { background-color: #161614; }"

st.markdown(bg_style + """
    h1, h2, h3, p, label { color: #d0b59b !important; }

    .st-emotion-cache-1gz5zxc {
        background-color: rgba(22, 22, 20, 0.85) !important;
        border-radius: 20px !important;
        padding: 2rem !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
    }

    .genre-label {
        color: #A08B77;
        font-weight: bold;
        text-align: center;
        margin-top: -10px;
        margin-bottom: 20px;
    }

    .stButton>button {
        background-color: #78444A !important;
        color: white !important;
        border-radius: 10px !important;
        height: 3.5em !important;
        width: 100% !important;
        border: none !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- TU LÓGICA ORIGINAL ---
API_URL = "http://localhost:8000"

GENRE_MAP = {
    "Acción":           "Action",
    "Comedia":          "Comedy",
    "Drama":            "Drama",
    "Terror":           "Horror",
    "Ciencia Ficción":  "Sci-Fi",
    "Romance":          "Romance",
    "Animación":        "Animation",
    "Aventura":         "Adventure",
    "Bélica":           "War",
    "Crimen":           "Crime",
    "Documental":       "Documentary",
    "Fantasía":         "Fantasy",
    "Musical":          "Musical",
    "Misterio":         "Mystery",
    "Western":          "Western",
    "Cine Negro":       "Film-Noir",
}

def _fetch_genre_name_to_id() -> dict[str, int]:
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
    prefs: dict[int, float] = {}
    for es_name, rating_val in votos_estrellas.items():
        if rating_val is None:
            continue
        en_name = GENRE_MAP.get(es_name)
        if en_name and en_name in name_to_id:
            prefs[name_to_id[en_name]] = float(rating_val + 1)

    for es_name in generos_extra:
        en_name = GENRE_MAP.get(es_name)
        if en_name and en_name in name_to_id:
            genre_id = name_to_id[en_name]
            if genre_id not in prefs:
                prefs[genre_id] = 3.0
    return [{"genre_id": gid, "score": score} for gid, score in prefs.items()]

def registro_total():
    # 1. PRIMERO DEFINIMOS LA VARIABLE (Línea clave)
    path_logo = os.path.join(current_dir, "assets", "logobg.png")
    
    # 2. LUEGO LA USAMOS (Aquí es donde te fallaba)
    logo_b64 = get_base64_image(path_logo)

    if logo_b64:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; margin-bottom: 20px;">
                <img src="data:image/png;base64,{logo_b64}" width="200">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown("<h1 style='text-align: center; color: #A08B77;'>🎬 Registro Cinematch</h1>", unsafe_allow_html=True)

    # 3. CONTINUAMOS CON EL CONTENEDOR (El que ya tienes que funciona)
    st.markdown('<div class="custom-container">', unsafe_allow_html=True)

    st.markdown("<h1 style='text-align:center; color:#d0b59b;'>Registro Cinematch</h1>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("1. Crear Cuenta")
        c1, c2 = st.columns(2)
        user = c1.text_input("Usuario", placeholder="usuario123")
        password = c2.text_input("Contraseña", type="password")

        st.divider()

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
                        votos_estrellas[gen] = rating

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
            
            try:
                login_resp = requests.post(
                    f"{API_URL}/auth/login",
                    json={"username": user, "password": password},
                    timeout=5,
                )
                if login_resp.status_code == 200:
                    token = login_resp.json()["access_token"]
                    name_to_id = _fetch_genre_name_to_id()
                    prefs = _build_preferences(votos_estrellas, generos_extra, name_to_id)
                    
                    if prefs:
                        requests.put(
                            f"{API_URL}/users/me/preferences",
                            json=prefs,
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=5,
                        )
                    
                    st.session_state.token = token
                    st.session_state.authenticated = True
                    st.success(f"¡Perfil creado con éxito para {user}!")
                    st.balloons()
                    st.switch_page("app.py")
                else:
                    st.warning("Registro correcto. Inicia sesión manualmente.")
            except Exception:
                st.warning("Registro correcto. Inicia sesión manualmente.")

if __name__ == "__main__":
    registro_total()