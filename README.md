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

CineMatch es un sistema inteligente de recomendación de películas donde el usuario se registra, selecciona sus gustos y recibe recomendaciones personalizadas mediante un sistema híbrido basado en Machine Learning.

El usuario puede puntuar películas con like/dislike y el sistema aprende progresivamente de su comportamiento.

**Tecnologías utilizadas:** Python · FastAPI · PostgreSQL · TensorFlow/Keras · Streamlit · Docker Compose

---

## Instalación rápida con Docker

### Requisitos previos

Solo necesitas instalar:

- Docker
- Docker Compose
- Git

Comprueba que están disponibles:

```bash
docker --version
docker compose version
git --version
```

No necesitas instalar Python, PostgreSQL ni TensorFlow manualmente.

---

### 1. Clonar el repositorio

```bash
git clone https://github.com/badrlah9/CineMatch-Sistema-de-recomendacion-peliculas.git
cd CineMatch-Sistema-de-recomendacion-peliculas
```

---

### 2. Crear archivos `.env`

Los archivos `.env` no se suben a GitHub por seguridad.

Ejecuta:

```bash
chmod +x scripts/create_envs.sh
./scripts/create_envs.sh
```

O también:

```bash
bash scripts/create_envs.sh
```

Esto generará:

```text
src/backend/.env
src/ml/.env
```

---

### 3. Descargar dataset MovieLens

Descarga MovieLens 32M:

```text
https://grouplens.org/datasets/movielens/32m/
```

Coloca los archivos en:

```text
data/raw/
├── ratings.csv
├── movies.csv
├── links.csv
└── tags.csv
```

---

### 4. Descargar modelo entrenado

Descarga los artefactos del modelo desde:

```text
https://drive.google.com/drive/folders/1Tq14PoZZq4UTBxqIZz-2jcanA9PMf5xx?usp=drive_link
```

Colócalos en:

```text
artifacts/tf_model/
├── collaborative_model.keras
├── mappings.pkl
└── model_metadata.json
```

---

### 5. Ejecutar todo el proyecto

```bash
docker compose up --build
```

Este comando levanta automáticamente:

1. Pipeline de ingesta y limpieza
2. PostgreSQL
3. Carga de datos en la base de datos
4. Servicio ML
5. Backend FastAPI
6. Frontend Streamlit

---

## URLs del proyecto

| Servicio | URL |
|---|---|
| Frontend | http://localhost:8501 |
| Backend Swagger | http://localhost:8000/docs |
| Backend Health | http://localhost:8000/health |
| ML Health | http://localhost:8001/health |

---

## Uso diario

Arrancar el proyecto:

```bash
docker compose up
```

Arrancar en segundo plano:

```bash
docker compose up -d
```

Apagar conservando datos:

```bash
docker compose down
```

---

## Reiniciar desde cero

```bash
docker compose down -v --remove-orphans
rm -rf data/processed/*
docker compose up --build
```

Esto borra la base de datos, los volúmenes Docker y los CSV procesados.

---

## Configuración de PostgreSQL

Docker crea automáticamente:

```text
Usuario: cinematch_user
Contraseña: 1324
Base de datos: cinematch
```

La conexión del backend usa:

```env
DATABASE_URL=postgresql://cinematch_user:1324@db:5432/cinematch
```

---

## Archivos `.env` generados

### `src/backend/.env`

```env
DATABASE_URL=postgresql://cinematch_user:1324@db:5432/cinematch
SECRET_KEY=clave_larga_segura
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
TMDB_API_KEY=tu_api_key
ML_SERVICE_URL=http://ml:8001
```

### `src/ml/.env`

```env
CINEMATCH_MOVIES_PATH=/app/data/processed/movies_clean.csv
CINEMATCH_RATINGS_PATH=/app/data/processed/ratings_sample.csv
CINEMATCH_MODEL_PATH=/app/artifacts/tf_model/collaborative_model.keras
CINEMATCH_MAPPINGS_PATH=/app/artifacts/tf_model/mappings.pkl
CINEMATCH_METADATA_PATH=/app/artifacts/tf_model/model_metadata.json
```

---

## Uso de la aplicación

1. Abrir http://localhost:8501
2. Registrarse
3. Elegir géneros favoritos
4. Ver recomendaciones
5. Dar like o dislike a las películas
6. Actualizar recomendaciones

---

## Arquitectura

```text
Frontend Streamlit
        ↓
Backend FastAPI
        ↓
PostgreSQL
        ↓
ML Service
        ↓
TensorFlow Model
```

---

## Sistema de recomendaciones

| Prioridad | Sistema |
|---|---|
| 1 | Modelo híbrido ML |
| 2 | Preferencias de género |
| 3 | Popularidad bayesiana |

El sistema usa capas de fallback para devolver recomendaciones incluso si el servicio ML no responde.

---

## Comandos útiles

Ver logs:

```bash
docker compose logs
```

Ver logs del backend:

```bash
docker compose logs backend
```

Ver logs del seed:

```bash
docker compose logs seed
```

Ver contenedores activos:

```bash
docker ps
```

Reconstruir imágenes:

```bash
docker compose build
```

---

## Estructura del proyecto

```text
CineMatch/
├── data/
│   ├── raw/
│   └── processed/
├── artifacts/
│   └── tf_model/
├── scripts/
│   └── create_envs.sh
├── src/
│   ├── pipeline/
│   ├── backend/
│   ├── ml/
│   └── front/
├── docker-compose.yml
└── README.md
```

---

## Notas importantes

- Los archivos `.env` no se suben al repositorio.
- Los datos de MovieLens no se suben al repositorio.
- El modelo TensorFlow no se sube al repositorio.
- Docker Compose es el método recomendado para ejecutar el proyecto.
- Si la base de datos ya está cargada, el proceso de seed no vuelve a insertar datos.

---

## Comando final recomendado

```bash
git clone https://github.com/badrlah9/CineMatch-Sistema-de-recomendacion-peliculas.git
cd CineMatch-Sistema-de-recomendacion-peliculas
bash scripts/create_envs.sh
docker compose up --build
```
