import json
import os
import re
import requests
import base64
import os
import streamlit as st
import streamlit.components.v1 as components

API_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

# 1. Función para convertir la imagen local a Base64
def get_base64_local_image(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

# 2. Configuración de página
st.set_page_config(page_title="Cinematch - Login", page_icon="🎬", layout="centered")

# Cargamos imágenes de assets
try:
    path_to_img = os.path.join("pages", "assets", "fondo.png")
    img_base64 = get_base64_local_image(path_to_img)
except FileNotFoundError:
    img_base64 = ""

try:
    path_to_logo = os.path.join("pages", "assets", "logobg.png")
    logo_base64 = get_base64_local_image(path_to_logo)
except FileNotFoundError:
    logo_base64 = ""

# 3. Estilos UNIFICADOS (Estilo Registro aplicado a Login)
st.markdown(f"""
    <style>
    .stApp {{
        background-image: linear-gradient(rgba(22, 22, 20, 0.5), rgba(22, 22, 20, 0.5)), 
                          url("data:image/png;base64,{img_base64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    /* EL CONTENEDOR (Mismo que en registro para consistencia) */
    .st-emotion-cache-1gz5zxc {{
        background-color: rgba(22, 22, 20, 0.85) !important;
        border-radius: 20px !important;
        padding: 2.5rem !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(160, 139, 119, 0.2) !important;
        box-shadow: 0 20px 40px rgba(0,0,0,0.6) !important;
    }}

    h2, p, label {{ color: #d0b59b !important; text-align: center; }}
    
    /* Inputs con estilo oscuro */
    .stTextInput>div>div>input {{
        background-color: rgba(0, 0, 0, 0.6) !important;
        color: #FAD9B9 !important;
        border: 1px solid #3F2B1F !important;
        border-radius: 10px !important;
        height: 2.7em !important;
        display: flex !important;
        align-items: center !important;
        line-height: normal !important;
        padding: 0px 15px !important;
    }}

    /* Botón Cinematch (Borgoña) */
    .stButton>button {{
        background-color: #78444A !important;
        color: white !important;
        border-radius: 10px !important;
        height: 3.5em !important;
        width: 100% !important;
        border: none !important;
        font-weight: bold !important;
        transition: 0.3s;
    }}
    
    .stButton>button:hover {{
        background-color: #945259 !important;
        border: 1px solid #d0b59b !important;
        transform: scale(1.01);
    }}

    .register-container {{ text-align: center; margin-top: 25px; }}
    .register-link {{ color: #A08B77; text-decoration: none; font-weight: 500; }}
    .register-link:hover {{ color: #FAD9B9; text-decoration: underline; }}
    </style>
    """, unsafe_allow_html=True)

# --- Helpers ---
def _extract_year(title: str) -> str:
    m = re.search(r'\((\d{4})\)', title)
    return m.group(1) if m else ""

def _clean_title(title: str) -> str:
    return re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()

def _fetch_movies(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(
            f"{API_URL}/recommendations/me",
            headers=headers,
            params={"k": 10, "enrich_tmdb": True},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("recommendations", [])
    except:
        pass
    try:
        resp = requests.get(
            f"{API_URL}/recommendations/popular",
            params={"k": 10, "enrich_tmdb": True},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("recommendations", [])
    except:
        pass
    return []

def _to_card(rec: dict) -> dict:
    title = rec.get("title", "")
    return {
        "movie_id": rec.get("movie_id"),
        "title":     _clean_title(title),
        "year":      _extract_year(title),
        "genre":     ", ".join(rec.get("genres", [])),
        "image":     rec.get("poster_url") or "",
        "rating":    min(5, max(1, round(rec.get("score", 3)))),
        "synopsis":  rec.get("overview") or "Sin sinopsis disponible.",
    }

def _fetch_preferences(token: str) -> list[dict]:
    try:
        resp = requests.get(
            f"{API_URL}/users/me/preferences",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return []

# --- Pantallas ---

def login_screen():
    st.markdown("<div style='padding-top: 50px;'></div>", unsafe_allow_html=True)
    _, col_card, _ = st.columns([0.5, 1.2, 0.5])
    
    with col_card:
        with st.container(border=True):
            if logo_base64:
                st.markdown(f"""
                    <div style="display: flex; justify-content: center; margin-bottom: 10px;">
                        <img src="data:image/png;base64,{logo_base64}" width="150">
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<h2 style='margin-bottom:0;'>Iniciar Sesión</h2>", unsafe_allow_html=True)
            st.markdown("<p style='margin-bottom:20px;'>Tu próxima película favorita te espera</p>", unsafe_allow_html=True)
            
            user = st.text_input("Usuario", placeholder="Tu usuario")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            
            st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
            
            if st.button("INICIAR SESIÓN"):
                if user and password:
                    try:
                        resp = requests.post(
                            f"{API_URL}/auth/login",
                            json={"username": user, "password": password},
                            timeout=5,
                        )
                        if resp.status_code == 200:
                            st.session_state.authenticated = True
                            st.session_state.token = resp.json()["access_token"]
                            st.rerun()
                        else:
                            st.error("Credenciales incorrectas")
                    except:
                        st.error("Servidor no disponible")
                else:
                    st.warning("Completa los campos")

            st.markdown(f'''
                <div class="register-container">
                    <a href="/Login" target="_self" class="register-link">¿No tienes cuenta? <b>Regístrate aquí</b></a>
                </div>
            ''', unsafe_allow_html=True)

def dashboard():
    # Sidebar
    if st.sidebar.button("Actualizar"):
        st.rerun()

    if st.sidebar.button("👤 Mi Perfil"):
        st.switch_page("pages/Dashboard.py")

    with st.sidebar.expander("🎭 Mis gustos"):
        prefs = _fetch_preferences(st.session_state.token)
        if prefs:
            for p in prefs:
                stars = "★" * round(p["score"]) + "☆" * (5 - round(p["score"]))
                st.markdown(f"**{p['genre_name']}** {stars}")
        else:
            st.caption("No tienes géneros guardados.")

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.authenticated = False
        st.session_state.token = None
        st.rerun()

    # Recomendaciones (HTML/JS)
    recs = _fetch_movies(st.session_state.token)
    movies_data = [_to_card(r) for r in recs]
    movies_json = json.dumps(movies_data, ensure_ascii=False)

    html_code = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background-color: transparent; color: white; font-family: sans-serif; margin: 0; padding-top: 10px; overflow: hidden; }
            .swipe-left { animation: swipe-left 0.6s ease-out forwards; }
            .swipe-right { animation: swipe-right 0.6s ease-out forwards; }
            @keyframes swipe-left { 100% { transform: translateX(-600px) rotate(-35deg); opacity: 0; } }
            @keyframes swipe-right { 100% { transform: translateX(600px) rotate(35deg); opacity: 0; } }
            .perspective-container { perspective: 1200px; }
            .flip-card-inner { position: relative; width: 100%; height: 100%; transition: transform 0.7s cubic-bezier(0.4, 0, 0.2, 1); transform-style: preserve-3d; }
            .flipped { transform: rotateY(180deg); }
            .card-face { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 2.5rem; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); border: 1px solid rgba(255,255,255,0.05); }
            .card-back { transform: rotateY(180deg); background: linear-gradient(145deg, #1e1e1e, #121212); border: 1px solid #333; padding: 2.5rem; display: flex; flex-direction: column; }
            .cinematch-title {
                font-size: 3.5rem; font-weight: 900; font-style: italic; letter-spacing: -0.05em;
                background: linear-gradient(to right, #C7AD93, #FAD9B9);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                width: 100%; text-align: center; display: block; margin-bottom: 0;
            }
            .info-label { color: #A08B77; font-weight: bold; text-transform: uppercase; font-size: 10px; letter-spacing: 0.1em; }
            .no-poster { background: linear-gradient(145deg, #2a2a2a, #1a1a1a); display: flex; align-items: center; justify-content: center; color: #555; font-size: 4rem; }

            /* Estrellas — definidas aquí dentro para que funcionen en el iframe */
            .rating-stars {
                display: flex;
                justify-content: center;
                gap: 10px;
                margin-bottom: 12px;
            }
            .rating-stars i {
                cursor: pointer;
                font-size: 1.6rem;
                transition: transform 0.15s, color 0.15s;
                color: #444;
            }
            .rating-stars i:hover {
                color: #fbbf24;
                transform: scale(1.25);
            }
            .rating-stars i.active {
                color: #fbbf24;
                transform: scale(1.1);
            }
        </style>
    </head>
    <body class="flex items-center justify-center">
        <div class="flex flex-col items-center w-full max-w-lg px-4">
            <header class="mb-6 w-full text-center">
                <h1 class="cinematch-title">CINEMATCH</h1>
                <p class="text-gray-500 text-[10px] uppercase tracking-[0.3em] font-bold">Tus recomendaciones</p>
            </header>

            <div id="card-wrapper" class="perspective-container w-full aspect-[2/3] max-w-[340px]">
                <div id="flip-inner" class="flip-card-inner"></div>
            </div>

            <!-- Estrellas justo encima de los botones -->
            <div class="rating-stars mt-6" id="star-rating-container">
                <i class="fa-solid fa-star" onclick="setStarRating(1)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(2)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(3)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(4)"></i>
                <i class="fa-solid fa-star" onclick="setStarRating(5)"></i>
            </div>

            <!-- Solo dos botones: dislike (X) y like (corazón) -->
            <div class="flex items-center justify-center gap-12 w-full max-w-[300px] mt-4">
                <button onclick="handleAction('dislike')" class="w-16 h-16 bg-gray-900 border border-white/10 text-red-500 rounded-full hover:bg-red-500 hover:text-white transition-all shadow-xl flex items-center justify-center">
                    <i class="fa-solid fa-xmark text-2xl"></i>
                </button>
                <button onclick="handleAction('like')" class="w-16 h-16 bg-gray-900 border border-white/10 text-emerald-400 rounded-full hover:bg-emerald-500 hover:text-white transition-all shadow-xl flex items-center justify-center">
                    <i class="fa-solid fa-heart text-2xl"></i>
                </button>
            </div>

            <p class="mt-6 text-gray-700 text-[10px] uppercase font-bold tracking-widest">Toca la 'i' para ver detalles</p>
        </div>

        <script>
            const movies = __MOVIES_DATA__;
            const AUTH_TOKEN = "__AUTH_TOKEN__";
            const API_URL    = "__API_URL__";
            let currentIndex = 0;
            let currentStarRating = 0;

            function setStarRating(rating) {
                currentStarRating = rating;
                const stars = document.querySelectorAll('#star-rating-container i');
                stars.forEach((star, index) => {
                    if (index < rating) {
                        star.classList.add('active');
                    } else {
                        star.classList.remove('active');
                    }
                });
                const movie = movies[currentIndex];
                if (movie) saveRating(movie.movie_id, rating);
            }

            function resetStars() {
                currentStarRating = 0;
                document.querySelectorAll('#star-rating-container i').forEach(s => s.classList.remove('active'));
            }

            function renderCard() {
                const inner = document.getElementById('flip-inner');
                const movie = movies[currentIndex];
                if (!movie) {
                    document.getElementById('card-wrapper').innerHTML = "<div class='text-center text-gray-500 mt-20 italic'>Has visto todas las recomendaciones</div>";
                    return;
                }
                let stars = "";
                for(let i=1; i<=5; i++) stars += `<i class="fa-solid fa-star ${i <= movie.rating ? 'text-yellow-500' : 'text-gray-800'} text-xs"></i> `;

                const imgContent = movie.image
                    ? `<img src="${movie.image}" class="w-full h-full object-cover">`
                    : `<div class="w-full h-full no-poster"><i class="fa-solid fa-film"></i></div>`;

                inner.innerHTML = `
                    <div class="card-face">
                        ${imgContent}
                        <button onclick="toggleFlip(event)" class="absolute top-6 right-6 w-12 h-12 bg-black/40 backdrop-blur-xl rounded-full flex items-center justify-center border border-white/20 text-white z-50 hover:scale-110 transition-transform"><i class="fa-solid fa-info"></i></button>
                        <div class="absolute bottom-0 left-0 right-0 p-8 bg-gradient-to-t from-black via-black/80 to-transparent">
                            <h2 class="text-3xl font-extrabold leading-tight">${movie.title}</h2>
                            <div class="flex items-center gap-3 mt-2 text-gray-400 font-medium">
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
                    method:  'POST',
                    headers: {
                        'Content-Type':  'application/json',
                        'Authorization': `Bearer ${AUTH_TOKEN}`,
                    },
                    body: JSON.stringify({ movie_id: movieId, rating: rating }),
                }).catch(() => {});
            }

            function toggleFlip(e) { e.stopPropagation(); document.getElementById('flip-inner').classList.toggle('flipped'); }

            function handleAction(type) {
                const movie   = movies[currentIndex];
                const wrapper = document.getElementById('card-wrapper');
                document.getElementById('flip-inner').classList.remove('flipped');

                if (type === 'like')    saveRating(movie.movie_id, 5.0);
                if (type === 'dislike') saveRating(movie.movie_id, 1.0);

                setTimeout(() => {
                    wrapper.classList.add(type === 'dislike' ? 'swipe-left' : 'swipe-right');
                    setTimeout(() => {
                        currentIndex++;
                        wrapper.classList.remove('swipe-left', 'swipe-right');
                        resetStars();
                        renderCard();
                    }, 600);
                }, 100);
            }
            renderCard();
        </script>
    </body>
    </html>
    """

    html_code = html_code.replace("__MOVIES_DATA__", movies_json)
    html_code = html_code.replace("__AUTH_TOKEN__", st.session_state.token or "")
    html_code = html_code.replace("__API_URL__", API_URL)
    components.html(html_code, height=920)

# --- Lógica de arranque ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None

if not st.session_state.authenticated:
    login_screen()
else:
    dashboard()