import json
import re

import requests
import streamlit as st
import streamlit.components.v1 as components

API_URL = "http://localhost:8000"

# 1. Configuración de página
st.set_page_config(page_title="Cinematch - TFM", page_icon="🎬", layout="centered")

# 2. Estilos
st.markdown("""
    <style>
    .stApp { background-color: #161614; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #3B443F !important;
        border-radius: 20px !important;
        padding: 30px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
        border: 1px solid #3F2B1F !important;
    }

    h2, p, label { color: #A08B77 !important; text-align: center; }
    input { background-color: #161614 !important; color: #A08B77 !important; border: 1px solid #3F2B1F !important; }

    .stButton>button {
        background-color: #78444A !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        height: 3.5em !important;
        width: 100% !important;
        border: none !important;
        font-weight: bold !important;
    }

    .register-link {
        color: #A08B77;
        text-decoration: none;
        font-size: 0.9em;
        font-weight: 500;
        transition: all 0.3s;
    }
    .register-link:hover {
        color: #78444A;
        text-decoration: underline;
    }
    .register-container { text-align: center; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None


# Helpers

def _extract_year(title: str) -> str:
    m = re.search(r'\((\d{4})\)', title)
    return m.group(1) if m else ""

def _clean_title(title: str) -> str:
    return re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()

def _fetch_movies(token: str) -> list[dict]:
    """Obtiene recomendaciones personalizadas; si falla, usa las más populares."""
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
    except requests.RequestException:
        pass

    # Fallback: películas populares (no requiere auth)
    try:
        resp = requests.get(
            f"{API_URL}/recommendations/popular",
            params={"k": 10, "enrich_tmdb": True},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("recommendations", [])
    except requests.RequestException:
        pass

    return []

def _to_card(rec: dict) -> dict:
    title = rec.get("title", "")
    return {
        "title":    _clean_title(title),
        "year":     _extract_year(title),
        "genre":    ", ".join(rec.get("genres", [])),
        "image":    rec.get("poster_url") or "",
        "rating":   min(5, max(1, round(rec.get("score", 3)))),
        "synopsis": rec.get("overview") or "Sin sinopsis disponible.",
    }


# Pantallas

def login_screen():
    _, col_card, _ = st.columns([0.5, 2, 0.5])
    with col_card:
        with st.container(border=True):
            st.markdown("<h1 style='text-align:center;'>🎬</h1>", unsafe_allow_html=True)
            st.markdown("<h2>Login</h2>", unsafe_allow_html=True)
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.button("Iniciar Sesión"):
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
                except requests.RequestException:
                    st.error("No se puede conectar con el servidor. ¿Está el backend en marcha?")

        st.markdown('''
            <div class="register-container">
                <a href="/Login" target="_self" class="register-link">¿No tienes cuenta? Regístrate aquí</a>
            </div>
        ''', unsafe_allow_html=True)


def dashboard():
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.authenticated = False
        st.session_state.token = None
        st.rerun()

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
            body { background-color: #161614; color: white; font-family: sans-serif; margin: 0; padding-top: 10px; overflow: hidden; }
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

            <div class="flex items-center justify-between w-full max-w-[300px] mt-8">
                <button onclick="handleAction('dislike')" class="w-16 h-16 bg-gray-900 border border-white/10 text-red-500 rounded-full hover:bg-red-500 hover:text-white transition-all shadow-xl flex items-center justify-center">
                    <i class="fa-solid fa-xmark text-2xl"></i>
                </button>
                <button onclick="handleAction('watchlist')" class="w-14 h-14 bg-gray-900 border border-white/10 text-blue-400 rounded-full hover:bg-blue-500 hover:text-white transition-all shadow-xl flex items-center justify-center">
                    <i class="fa-solid fa-bookmark text-lg"></i>
                </button>
                <button onclick="handleAction('like')" class="w-16 h-16 bg-gray-900 border border-white/10 text-emerald-400 rounded-full hover:bg-emerald-500 hover:text-white transition-all shadow-xl flex items-center justify-center">
                    <i class="fa-solid fa-heart text-2xl"></i>
                </button>
            </div>
            <p class="mt-8 text-gray-700 text-[10px] uppercase font-bold tracking-widest">Toca la 'i' para ver detalles</p>
        </div>

        <script>
            const movies = __MOVIES_DATA__;
            let currentIndex = 0;

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

            function toggleFlip(e) { e.stopPropagation(); document.getElementById('flip-inner').classList.toggle('flipped'); }
            function handleAction(type) {
                const wrapper = document.getElementById('card-wrapper');
                document.getElementById('flip-inner').classList.remove('flipped');
                setTimeout(() => {
                    wrapper.classList.add(type === 'dislike' ? 'swipe-left' : 'swipe-right');
                    setTimeout(() => {
                        currentIndex++;
                        wrapper.classList.remove('swipe-left', 'swipe-right');
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
    components.html(html_code, height=920)


if not st.session_state.authenticated:
    login_screen()
else:
    dashboard()
