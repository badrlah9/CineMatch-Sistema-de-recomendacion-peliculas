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

Por su tamaño, se descarga en el siguiente enlace, descarga los tres archivos y colócalos en `artifacts/tensorflow/`:
https://drive.google.com/drive/folders/1Tq14PoZZq4UTBxqIZz-2jcanA9PMf5xx?usp=drive_link

```
artifacts/tensorflow/
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

---

## Trazabilidad de módulos

Esta tabla mapea cada módulo descrito en la documentación (`docs/fase1/`) a su ubicación exacta en el repositorio.

### Pipeline de datos

| Módulo (PDF) | Archivo | Descripción |
|---|---|---|
| Ingesta y limpieza | [src/pipeline/ingest.py](src/pipeline/ingest.py) | Lee MovieLens 32M de `data/raw/`, filtra y genera CSVs limpios en `data/processed/` |
| Carga a PostgreSQL | [src/backend/scripts/load_data.py](src/backend/scripts/load_data.py) | Inserta los CSVs procesados en la base de datos; soporta `--sample` (100k ratings) |
| Schema de la base de datos | [src/backend/cinematch_schema.sql](src/backend/cinematch_schema.sql) | DDL completo: tablas, índices, constraints (PostgreSQL) |
| Exploración de datos | [src/pipeline/notebooks/eda.ipynb](src/pipeline/notebooks/eda.ipynb) | Jupyter con estadísticas, distribuciones y calidad de datos |

### Backend (FastAPI · puerto 8000)

| Módulo (PDF) | Archivo | Descripción |
|---|---|---|
| Punto de entrada API | [src/backend/app/main.py](src/backend/app/main.py) | Crea la app FastAPI, CORS, monta todos los routers |
| Configuración | [src/backend/app/config.py](src/backend/app/config.py) | Variables de entorno: `DATABASE_URL`, JWT, `TMDB_API_KEY`, `ML_SERVICE_URL` |
| Conexión a base de datos | [src/backend/app/database.py](src/backend/app/database.py) | Engine SQLAlchemy + `get_db()` como dependency de FastAPI |
| Modelos ORM | [src/backend/app/models.py](src/backend/app/models.py) | Tablas: `Genre`, `Movie`, `Link`, `Rating`, `User`, `UserGenrePreference` |
| Esquemas de validación | [src/backend/app/schemas.py](src/backend/app/schemas.py) | Pydantic: `UserRegister`, `Token`, `MovieOut`, `RecommendationsOut`, etc. |
| Autenticación JWT | [src/backend/app/routers/auth.py](src/backend/app/routers/auth.py) | `POST /auth/register` (bcrypt) y `POST /auth/login` (JWT) |
| Validación de token | [src/backend/app/dependencies.py](src/backend/app/dependencies.py) | `get_current_user()` — valida JWT y devuelve el usuario autenticado |
| Búsqueda de películas | [src/backend/app/routers/movies.py](src/backend/app/routers/movies.py) | `GET /movies/search` (pg\_trgm), `GET /movies/{id}` con enriquecimiento TMDB |
| Preferencias de género | [src/backend/app/routers/preferences.py](src/backend/app/routers/preferences.py) | CRUD `GET/POST/PUT /users/me/preferences` |
| Valoraciones | [src/backend/app/routers/ratings.py](src/backend/app/routers/ratings.py) | `POST /ratings` — guarda like/dislike del usuario autenticado |
| Endpoint de recomendaciones | [src/backend/app/routers/recommendations.py](src/backend/app/routers/recommendations.py) | `GET /recommendations/me` — orquesta las 3 capas de fallback |
| Lógica de recomendaciones | [src/backend/app/services/recommendations.py](src/backend/app/services/recommendations.py) | Llama al servicio ML, fallback a géneros, fallback a popularidad bayesiana |
| Integración TMDB | [src/backend/app/services/tmdb.py](src/backend/app/services/tmdb.py) | Enriquece cada película con póster, sinopsis y fecha desde la API de TMDB |

### Servicio ML (TensorFlow · puerto 8001)

| Módulo (PDF) | Archivo | Descripción |
|---|---|---|
| Punto de entrada ML | [src/ml/fastapi_app.py](src/ml/fastapi_app.py) | API FastAPI del servicio ML: `GET /health`, `POST /v1/recommendations` |
| Servicio de alto nivel | [src/ml/cinematch/service.py](src/ml/cinematch/service.py) | `CineMatchService`: carga datos y modelos, expone `get_recommendations()` |
| Orquestador híbrido | [src/ml/cinematch/hybrid_orchestrator.py](src/ml/cinematch/hybrid_orchestrator.py) | Mezcla señales colaborativo + contenido + vecinos; gestiona rotación sin repetir |
| Filtrado colaborativo | [src/ml/cinematch/collaborative_tf.py](src/ml/cinematch/collaborative_tf.py) | `TensorFlowCollaborativeRecommender`: inferencia sobre el modelo Keras entrenado |
| Filtrado por contenido | [src/ml/cinematch/content_based.py](src/ml/cinematch/content_based.py) | Scoring por género + popularidad bayesiana (fallback sin historial) |
| Usuarios similares | [src/ml/cinematch/neighbor_embeddings.py](src/ml/cinematch/neighbor_embeddings.py) | Cosine similarity sobre embeddings históricos para encontrar vecinos cercanos |
| Configuración ML | [src/ml/cinematch/config.py](src/ml/cinematch/config.py) | Rutas a artefactos e hiperparámetros (`top_n`, `min_catalog_votes`, etc.) |
| Esquemas ML | [src/ml/cinematch/schemas.py](src/ml/cinematch/schemas.py) | Pydantic: `RecommendationRequest`, `RecommendationResponse`, `MovieRecommendation` |
| I/O de artefactos | [src/ml/cinematch/io_utils.py](src/ml/cinematch/io_utils.py) | Carga CSV/Parquet, JSON y Pickle de forma resiliente |
| Entrenamiento del modelo | [src/ml/cinematch/training/train_tensorflow_model.py](src/ml/cinematch/training/train_tensorflow_model.py) | Entrena Matrix Factorization en Keras; genera `.keras`, `mappings.pkl` y `model_metadata.json` |
| Migración PyTorch → Keras | [src/ml/cinematch/training/convert_pytorch_to_keras.py](src/ml/cinematch/training/convert_pytorch_to_keras.py) | Convierte checkpoints `.pth` a formato Keras preservando pesos y mappings |

### Frontend (Streamlit · puerto 8501)

| Módulo (PDF) | Archivo | Descripción |
|---|---|---|
| Dashboard principal | [src/front/app.py](src/front/app.py) | Muestra recomendaciones, like/dislike, botón actualizar y sidebar de gustos |
| Login y registro | [src/front/pages/Login.py](src/front/pages/Login.py) | Formulario de login/registro; almacena JWT en `session_state` |

---

## Decisiones técnicas y deuda pendiente

### Decisiones técnicas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| TensorFlow/Keras para Matrix Factorization | PyTorch | TF tiene soporte nativo para `.keras` con serialización de capas custom; se migró desde un checkpoint PyTorch inicial |
| FastAPI en dos servicios separados (backend + ML) | Un único servicio monolítico | Permite escalar el servicio ML de forma independiente y reiniciarlo sin afectar la API principal |
| PostgreSQL con pg\_trgm para búsqueda | Elasticsearch / búsqueda en memoria | Simplicidad operacional; pg\_trgm es suficiente para el volumen del catálogo (~87k películas) |
| Fallback en 3 capas (ML → género → popularidad) | Devolver error si ML no responde | Garantiza que el usuario siempre recibe recomendaciones aunque el servicio ML esté caído |
| Popularidad bayesiana como último fallback | Popularidad simple por número de ratings | Evita sesgo hacia películas con muchos pero malos ratings; balancea votos y media |
| Streamlit para el frontend | React / Next.js | Reduce tiempo de desarrollo al ser Python puro; suficiente para una demo funcional |
| `.env` por servicio (backend y ML) | Configuración centralizada | Permite desplegar cada servicio en entornos distintos sin acoplar sus configuraciones |
| Artefactos ML fuera del repositorio (Google Drive) | Git LFS | El modelo pesa >200 MB; Git LFS tiene costes en repositorios públicos |

### Deuda técnica pendiente

| Área | Descripción | Prioridad |
|---|---|---|
| Tests | No hay tests automatizados (unitarios ni de integración) en ninguno de los tres servicios | Alta |
| Docker Compose completo | Existe `docker-compose.yml` en el ML service pero no orquesta los tres servicios juntos | Alta |
| Reentrenamiento incremental | El modelo se entrena una sola vez; no hay pipeline para actualizar con nuevos ratings de usuarios | Media |
| Autenticación en el servicio ML | El endpoint `POST /v1/recommendations` no requiere autenticación; cualquiera en la red puede llamarlo | Media |
| Paginación en recomendaciones | La API devuelve siempre un bloque fijo de N películas; no hay cursor ni offset | Baja |
| Caché de respuestas TMDB | Cada llamada a `/recommendations/me` consulta TMDB en tiempo real; sin caché local | Baja |
| Variables de entorno en el frontend | Las URLs del backend están hardcodeadas en `app.py`; deberían venir de variables de entorno | Baja |
