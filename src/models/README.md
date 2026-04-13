
# CineMatch refactor híbrido

## Ficheros incluidos

- `collaborative_svd.py`
- `content_based.py`
- `user_based_embeddings.py`
- `hybrid_recommender.py`
- `demo_modelo_hibrido.py`
- `02_hybrid_recommender_system_demo.ipynb`

## Cambios principales

### 1) Ya no depende de que el usuario exista en MovieLens
El flujo principal del híbrido ya no usa `user_exists` para decidir si puede haber colaborativo.

Ahora:
- si el usuario trae ratings, se infiere un **perfil colaborativo temporal**
- ese perfil vive en el mismo espacio latente del SVD entrenado
- con ese perfil se puntúan candidatas y se buscan usuarios parecidos

### 2) Híbrido real para usuarios externos
El modelo combina:
- contenido
- SVD temporal a partir de ratings del usuario actual
- vecinos similares en embeddings
- fallback de cold start

### 3) Rotación / diversidad
Si pides exactamente lo mismo:
- no devuelve siempre exactamente el mismo top
- no elimina para siempre las películas ya recomendadas
- aplica una penalización suave que decae con el tiempo

Para APIs stateless:
- se devuelve `recommendation_state`
- el cliente puede reenviarlo en la siguiente petición

### 4) Notebook de pruebas mejorado
Incluye:
- explicación del flujo completo
- pruebas de cold start
- pruebas con usuario externo con ratings
- comparación entre señales
- métricas sencillas
- simulación local de petición tipo HTTP
- prueba de rotación entre llamadas

## Interfaz recomendada del híbrido

```python
result = hybrid.recommend_payload(
    user_id=424242,
    user_preferences={"Action": 5, "Drama": 4},
    user_ratings_df=user_ratings_df,
    top_n=10,
    shortlist_size=300,
    recommendation_state=None,
    include_metadata=True,
)
```

Devuelve:

```python
{
    "recommendations": [...],
    "metadata": {...},
    "recommendation_state": {...}
}
```
