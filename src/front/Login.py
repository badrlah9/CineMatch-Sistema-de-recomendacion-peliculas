import streamlit as st

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

def registro_total():
    st.markdown("<h1 style='text-align: center;'>🎬 Registro Cinematch</h1>", unsafe_allow_html=True)
    
    with st.container(border=True):
        # --- SECCIÓN 1: LOGIN ---
        st.subheader("1. Crear Cuenta")
        c1, c2 = st.columns(2)
        user = c1.text_input("Usuario", placeholder="usuario123")
        password = c2.text_input("Contraseña", type="password")

        st.divider()

        # --- SECCIÓN 2: ESTRELLAS (Géneros Principales) ---
        st.subheader("2. Tus Imprescindibles")
        st.write("Puntúa estos géneros base:")
        
        generos_top = ["Acción", "Comedia", "Drama", "Terror", "Ciencia Ficción", "Romance"]
        votos_estrellas = {}
        
        for i in range(0, len(generos_top), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(generos_top):
                    gen = generos_top[i + j]
                    with cols[j]:
                        rating = st.feedback("stars", key=f"star_{gen}")
                        st.markdown(f"<p class='genre-label'>{gen}</p>", unsafe_allow_html=True)
                        votos_estrellas[gen] = rating if rating is not None else 0

        # --- SECCIÓN 3: SELECTOR (Géneros Extra) ---
        st.subheader("3. Otros intereses")
        st.write("¿Te gusta algo más específico?")
        
        otros_generos = ["Animación", "Aventura", "Bélica", "Crimen", "Documental", "Fantasía", "Musical", "Misterio", "Western", "Cine Negro"]
        
        generos_extra = st.multiselect(
            "Busca y añade otros géneros:",
            options=otros_generos,
            placeholder="Ej: Documental, Misterio..."
        )

        st.divider()

        if st.button("Finalizar Registro"):
            if user and password:
                st.success(f"¡Perfil creado con éxito para {user}!")
                # Aquí tendrías:
                # - votos_estrellas: Diccionario con puntuaciones del 1-5
                # - generos_extra: Lista con los nombres de los géneros del buscador
                st.balloons()
            else:
                st.error("Faltan datos por rellenar.")

if __name__ == "__main__":
    registro_total()