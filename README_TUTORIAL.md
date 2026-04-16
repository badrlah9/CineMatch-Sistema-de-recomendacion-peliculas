## 1. Estructura recomendada del proyecto

Copia los ficheros así:

```text
tu_proyecto/
├── fastapi_app.py
├── README_TUTORIAL.md
├── examples/
│   └── payload_example.json
├── src/
│   └── cinematch/
│       ├── __init__.py
│       ├── collaborative_tf.py
│       ├── config.py
│       ├── content_based.py
│       ├── hybrid_orchestrator.py
│       ├── io_utils.py
│       ├── neighbor_embeddings.py
│       ├── schemas.py
│       ├── service.py
│       └── simulate_service.py
├── data/
│   └── processed/
│       ├── movies_clean.csv
│       └── ratings_clean.csv
└── artifacts/
    └── tf_model/
        ├── collaborative_model.keras
        ├── mappings.pkl
        └── model_metadata.json
```

---

## 2. Artefactos necesarios

Necesitas tener ya entrenado el modelo y estos tres ficheros:

- `artifacts/tf_model/collaborative_model.keras`
- `artifacts/tf_model/mappings.pkl`
- `artifacts/tf_model/model_metadata.json`

Y además:

- `data/processed/movies_clean.csv`
- `data/processed/ratings_clean.csv`

---

## 3. Comportamiento importante del sistema

### Qué NO hace
- no trata al usuario real como usuario conocido del train
- no usa el `user_id` para sacar su embedding directamente
- no depende de que el usuario exista en MovieLens

### Qué SÍ hace
- usa los ratings reales del usuario actual
- construye un perfil temporal en el espacio de embeddings
- busca usuarios históricos parecidos
- mezcla:
  - contenido
  - colaborativo temporal
  - vecinos similares
- rota resultados entre llamadas para no repetir siempre el mismo top

---

## 4. Ejecutar en local sin FastAPI

Desde la raíz del proyecto:

```bash
PYTHONPATH=src python -m cinematch.simulate_service --mode local
```

También puedes usar tu propio payload:

```bash
PYTHONPATH=src python -m cinematch.simulate_service   --mode local   --payload-file examples/payload_example.json
```

Si quieres cambiar `top_n` o `shortlist_size`:

```bash
PYTHONPATH=src python -m cinematch.simulate_service   --mode local   --top-n 5   --shortlist-size 200
```

### Ficheros que guarda
Por defecto el simulador guarda:

- `recommendation_state.json`
- `last_response.json`

Eso te permite probar la rotación entre llamadas.

---

## 5. Ejecutar FastAPI

Desde la raíz del proyecto:

```bash
PYTHONPATH=src uvicorn fastapi_app:app --reload
```

Endpoints:

- `GET /health`
- `GET /ready`
- `POST /v1/recommendations`

---

## 6. Probar el endpoint HTTP

Con curl:

```bash
curl -X POST "http://127.0.0.1:8000/v1/recommendations"   -H "Content-Type: application/json"   -d @examples/payload_example.json
```

O con el simulador en modo HTTP:

```bash
PYTHONPATH=src python -m cinematch.simulate_service   --mode http   --payload-file examples/payload_example.json
```

---

## 7. Estructura de entrada esperada

El servicio espera un JSON como este:

```json
{
  "user_id": 999002,
  "user_preferences": {
    "Sci-Fi": 5,
    "Thriller": 4,
    "Drama": 2
  },
  "ratings": [
    { "movieId": 296, "rating": 5.0 },
    { "movieId": 318, "rating": 4.5 },
    { "movieId": 593, "rating": 4.0 },
    { "movieId": 2571, "rating": 5.0 }
  ],
  "top_n": 10,
  "shortlist_size": 300,
  "recommendation_state": null,
  "apply_rotation": true,
  "include_debug_scores": true
}
```

### Significado de cada campo

- `user_id`: identificador externo de tu producto
- `user_preferences`: gustos por género
- `ratings`: ratings reales del usuario actual
- `top_n`: número de películas a devolver
- `shortlist_size`: tamaño de la shortlist por contenido
- `recommendation_state`: estado para rotación entre llamadas
- `apply_rotation`: activa o desactiva rotación
- `include_debug_scores`: si quieres ver scores internos o una respuesta más ligera

---

## 8. Estructura de salida del servicio

La respuesta tiene esta forma general:

```json
{
  "ok": true,
  "service": "CineMatch",
  "model_version": "cinematch-hybrid-keras-external-2.0.0",
  "recommendations": [
    {
      "movieId": 79132,
      "title": "Inception (2010)",
      "genres": ["action", "crime", "drama", "mystery", "sci-fi", "thriller", "imax"],
      "matched_genres": ["sci-fi", "thriller", "drama"],
      "catalog_rating": 4.1572,
      "num_ratings": 57930,
      "scores": {
        "final": 0.716682,
        "content": 0.630479,
        "collaborative": 0.946256,
        "neighbors": 0.913132
      },
      "reason": "Encaja con tus gustos en sci-fi, thriller, drama; tu patrón de ratings la deja muy arriba."
    }
  ],
  "metadata": {
    "path": "hybrid_content_plus_temp_profile_plus_neighbors",
    "weights": {
      "svd": 0.25,
      "embedding": 0.2,
      "content": 0.55
    },
    "num_user_ratings": 4,
    "num_preferences": 3,
    "candidate_pool_size": 87581,
    "shortlist_size": 300,
    "external_user_only": true,
    "used_temp_profile": true,
    "svd_candidates_scored": 300,
    "embedding_candidates_scored": 147,
    "rotation": {
      "signature": "....",
      "request_count": 3,
      "tracked_movies": 25
    },
    "latency_ms": 123.45
  },
  "recommendation_state": {
    "signatures": {
      "...": {
        "request_count": 3,
        "exposures": {
          "79132": 1.64
        }
      }
    }
  }
}
```

---

## 9. Cómo funciona la rotación

### Primera llamada
Manda:

```json
"recommendation_state": null
```

### Segunda llamada
Reenvía el `recommendation_state` que devolvió el servicio.

Así el sistema:
- recuerda parcialmente lo ya mostrado
- baja un poco el peso de lo muy repetido
- no elimina para siempre esas películas
- mezcla variedad de forma gradual

---

## 10. Variables de entorno opcionales

Puedes sobrescribir rutas y ajustes sin tocar código:

- `CINEMATCH_PROJECT_ROOT`
- `CINEMATCH_MOVIES_PATH`
- `CINEMATCH_RATINGS_PATH`
- `CINEMATCH_MODEL_PATH`
- `CINEMATCH_MAPPINGS_PATH`
- `CINEMATCH_METADATA_PATH`
- `CINEMATCH_DEFAULT_TOP_N`
- `CINEMATCH_DEFAULT_SHORTLIST_SIZE`
- `CINEMATCH_MIN_CATALOG_VOTES`
- `CINEMATCH_MIN_NEIGHBOR_VOTES`
- `CINEMATCH_ROTATION_MEMORY_DECAY`
- `CINEMATCH_MAX_HISTORY_SIGNATURES`
- `CINEMATCH_SERVICE_NAME`
- `CINEMATCH_MODEL_VERSION`

Ejemplo:

```bash
export CINEMATCH_MODEL_PATH=artifacts/tf_model/collaborative_model.keras
export CINEMATCH_MAPPINGS_PATH=artifacts/tf_model/mappings.pkl
export CINEMATCH_METADATA_PATH=artifacts/tf_model/model_metadata.json
```

---

## 11. Flujo completo del sistema

### Si el usuario NO tiene ratings
- contenido puro
- popularidad
- géneros
- cold start

### Si el usuario SÍ tiene ratings
- shortlist por contenido
- perfil temporal colaborativo desde ratings
- vecinos similares históricos
- mezcla final
- rotación

---

## 12. Resumen corto

Esta integración ya está preparada para tu caso real:
- usuarios externos
- Keras entrenado
- lógica híbrida completa
- servicio API
- simulador local y HTTP
