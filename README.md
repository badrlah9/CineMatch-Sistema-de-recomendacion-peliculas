# CineMatch — Sistema de Recomendación de Películas

## Equipo — Grupo E-12

| Rol | Nombre |
|-----|--------|
| Data Engineer & Coordinador Técnico | Badr Lahrarti |
| Machine Learning Engineer | Alejandro Miguel González Mateos |
| Backend & API Developer | Daniel Ruiz González |
| Frontend & Visualización | Francisco López Fenoll |

---

## Qué es CineMatch

Sistema de recomendación de películas personalizado. El usuario se registra, indica sus géneros favoritos y recibe recomendaciones generadas por un modelo híbrido (filtrado colaborativo + contenido). Las valoraciones (like/dislike) que da a las películas se guardan y mejoran las recomendaciones futuras.

**Stack:** Python · FastAPI · PostgreSQL · TensorFlow/Keras · Streamlit

---

## Requisitos previos

Instala esto antes de empezar:

- **Python 3.10 o superior** — [python.org/downloads](https://www.python.org/downloads/)
- **PostgreSQL 14 o superior** — [postgresql.org/download](https://www.postgresql.org/download/)
- **Git** — [git-scm.com](https://git-scm.com/)

Verifica que están instalados:
```bash
python --version
psql --version
git --version
```

---

## Estructura del proyecto

```
CineMatch/
├── data/
│   ├── raw/                        ← datos originales de MovieLens (NO en git)
│   └── processed/                  ← CSVs limpios generados por ingest.py (NO en git)
├── artifacts/
│   └── tf_model/                   ← modelo entrenado (NO en git, pedir al equipo)
│       ├── collaborative_model.keras
│       ├── mappings.pkl
│       └── model_metadata.json
├── src/
│   ├── pipeline/
│   │   └── ingest.py               ← limpia los datos de MovieLens
│   ├── backend/                    ← API FastAPI (puerto 8000)
│   │   ├── app/
│   │   ├── scripts/load_data.py    ← carga los CSVs en PostgreSQL
│   │   ├── cinematch_schema.sql    ← schema de la base de datos
│   │   ├── requirements.txt
│   │   └── .env                    ← configuración local (NO en git)
│   ├── ml/                         ← servicio ML FastAPI (puerto 8001)
│   │   ├── cinematch/
│   │   ├── fastapi_app.py
│   │   ├── requirements.txt
│   │   └── .env                    ← configuración local (NO en git)
│   └── front/                      ← interfaz Streamlit (puerto 8501)
│       ├── app.py
│       ├── pages/Login.py
│       └── requirements.txt
└── docs/
```

---

## Instalación paso a paso

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/badrlah9/CineMatch-Sistema-de-recomendacion-peliculas.git
cd CineMatch-Sistema-de-recomendacion-peliculas
```

---

### Paso 2 — Preparar la base de datos PostgreSQL

Abre una terminal y conéctate a PostgreSQL como superusuario:

```bash
psql -U postgres
```

Crea el usuario y la base de datos:

```sql
CREATE USER cinematch_user WITH PASSWORD 'cinematch_pass';
CREATE DATABASE cinematch OWNER cinematch_user;
GRANT ALL PRIVILEGES ON DATABASE cinematch TO cinematch_user;
\q
```

Aplica el schema (tablas, vistas, índices):

```bash
psql -U cinematch_user -d cinematch -f src/backend/cinematch_schema.sql
```

---

### Paso 3 — Instalar todas las dependencias

Desde la raíz del proyecto, crea un único entorno virtual e instala todo de una vez:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> TensorFlow (incluido en `requirements.txt`) requiere al menos 2 GB libres en disco y ~4 GB de RAM.

---

### Paso 4 — Configurar el backend

Crea el archivo `src/backend/.env` con este contenido:

```
DATABASE_URL=postgresql://cinematch_user:cinematch_pass@localhost:5432/cinematch
SECRET_KEY=cambia_esto_por_una_clave_larga_y_aleatoria
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
TMDB_API_KEY=tu_clave_de_tmdb
ML_SERVICE_URL=http://localhost:8001
```

> **TMDB_API_KEY** es opcional pero necesaria para ver pósters y sinopsis.
> Consíguela gratis en [themoviedb.org](https://www.themoviedb.org/) → Configuración → API.

---

### Paso 5 — Obtener los datos de MovieLens

Los datos NO están en el repositorio por su tamaño (~1 GB). Hay dos opciones:

**Opción A — Pedir los CSVs ya procesados al equipo (recomendado)**

Solicita a Badr los archivos procesados y colócalos en `data/processed/`:

```
data/processed/
├── movies_clean.csv
├── ratings_sample.csv
├── ratings_clean.csv
├── links_clean.csv
└── tags_clean.csv
```

Salta al Paso 6.

**Opción B — Procesar desde cero**

Descarga `ml-32m.zip` desde [grouplens.org/datasets/movielens/32m](https://grouplens.org/datasets/movielens/32m/), descomprímelo y copia los CSV en `data/raw/`. Luego ejecuta:

```bash
python src/pipeline/ingest.py
```

---

### Paso 6 — Cargar los datos en PostgreSQL

Con el entorno activado, desde la raíz del proyecto:

```bash
python src/backend/scripts/load_data.py --data-dir data/processed --sample
```

> `--sample` carga 100.000 ratings (rápido, recomendado para desarrollo).
> Sin `--sample` carga el dataset completo (~32 millones de ratings, tarda varios minutos).

Deberías ver algo como:
```
Cargados 87585 películas
Cargados 87585 links
Cargados 100000 ratings
```

---

### Paso 7 — Obtener el modelo entrenado

Por su tamaño, se descarga en el siguiente enlace, descarga los tres archivos y colócalos en `artifacts/tf_model/`:
https://drive.google.com/drive/folders/1Tq14PoZZq4UTBxqIZz-2jcanA9PMf5xx?usp=drive_link

```
artifacts/tf_model/
├── collaborative_model.keras
├── mappings.pkl
└── model_metadata.json
```

---

### Paso 8 — Configurar el servicio ML

Crea el archivo `src/ml/.env` con este contenido:

```
CINEMATCH_MOVIES_PATH=../../data/processed/movies_clean.csv
CINEMATCH_RATINGS_PATH=../../data/processed/ratings_sample.csv
CINEMATCH_MODEL_PATH=../../artifacts/tf_model/collaborative_model.keras
CINEMATCH_MAPPINGS_PATH=../../artifacts/tf_model/mappings.pkl
CINEMATCH_METADATA_PATH=../../artifacts/tf_model/model_metadata.json
```

---

## Arrancar la aplicación

Necesitas **tres terminales** abiertas en la raíz del proyecto.  
En cada una, activa primero el entorno virtual:

```bash
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate
```

### Terminal 1 — Backend (puerto 8000)

```bash
cd src/backend
python -m uvicorn app.main:app --port 8000 --reload
```

Verifica: [http://localhost:8000/health](http://localhost:8000/health)

### Terminal 2 — Servicio ML (puerto 8001)

```bash
cd src/ml
python -m uvicorn fastapi_app:app --port 8001
```

Verifica: [http://localhost:8001/health](http://localhost:8001/health)

> El primer arranque tarda ~30 segundos mientras carga el modelo en memoria.

### Terminal 3 — Frontend (puerto 8501)

```bash
cd src/front
streamlit run app.py
```

Verifica: [http://localhost:8501](http://localhost:8501)

---

## Uso de la aplicación

1. Abre [http://localhost:8501](http://localhost:8501) en el navegador
2. Haz clic en **"¿No tienes cuenta? Regístrate aquí"**
3. Elige un usuario y contraseña, y puntúa tus géneros favoritos
4. En el dashboard verás 10 películas recomendadas con póster, sinopsis y géneros
5. Pulsa **❤️** (like) o **❌** (dislike) para valorar cada película — se guarda en la BD
6. Pulsa la **ℹ** de una carta para ver la sinopsis
7. Pulsa **Actualizar** en el sidebar para obtener nuevas recomendaciones basadas en tus valoraciones
8. Despliega **"Mis gustos"** en el sidebar para ver tus preferencias de género guardadas

---

## Lógica de recomendaciones

El sistema usa tres capas en cascada:

| Prioridad | Fuente | Cuándo se usa |
|-----------|--------|---------------|
| 1 | Modelo híbrido ML (Alejandro) | Siempre que el servicio ML esté disponible |
| 2 | Preferencias de género | Si el servicio ML falla |
| 3 | Popularidad bayesiana | Si el usuario no tiene preferencias guardadas |

El campo `source` en la respuesta de la API indica qué capa se usó.

---

## Documentación de la API

Con el backend en marcha:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Notas importantes

- Los archivos `.env` **nunca** se suben al repositorio (están en `.gitignore`)
- Los datos de `data/` y los artefactos de `artifacts/tf_model/` tampoco se suben por su tamaño
- Si cambias el código del backend o del ML service, reinicia el servidor correspondiente (no tienen `--reload` por defecto excepto el backend en desarrollo)
