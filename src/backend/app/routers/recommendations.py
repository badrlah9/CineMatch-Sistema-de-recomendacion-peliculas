import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database        import get_db
from app.dependencies    import get_current_user
from app.models          import User
from app.schemas         import RecommendationItem, RecommendationsOut
from app.services.recommendations import (
    get_recommendations,
    _recommend_by_popularity,
    _get_genres_for_movies,
)
from app.services.tmdb import fetch_tmdb_data

router = APIRouter(prefix="/recommendations", tags=["Recomendaciones"])


@router.get(
    "/me",
    response_model=RecommendationsOut,
    summary="Obtener recomendaciones para el usuario autenticado",
    description="""
Devuelve un Top-K de películas recomendadas usando la siguiente estrategia en cascada:

1. **Modelo ML** — si el servicio ML está disponible (ML_SERVICE_URL)
2. **Por género** — si el usuario tiene preferencias definidas (formulario onboarding)
3. **Popularidad** — fallback siempre disponible (score bayesiano)

El campo `source` de la respuesta indica qué estrategia se usó.
Los pósters y sinopsis se enriquecen desde TMDB si `TMDB_API_KEY` está configurada.
    """,
)
async def my_recommendations(
    k:            int     = Query(default=10, ge=1, le=50,
                                  description="Número de recomendaciones a devolver"),
    enrich_tmdb:  bool    = Query(default=True,
                                  description="Enriquecer con pósters y sinopsis de TMDB"),
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    result = await get_recommendations(
        user_id = current_user.user_id,
        db      = db,
        k       = k,
    )

    if enrich_tmdb:
        async def _enrich(item):
            if item.tmdb_id:
                tmdb_data = await fetch_tmdb_data(item.tmdb_id)
                item.poster_url = tmdb_data.get("poster_url")
                item.overview   = tmdb_data.get("overview")

        await asyncio.gather(*[_enrich(item) for item in result.recommendations])

    return result


@router.get(
    "/popular",
    response_model=RecommendationsOut,
    summary="Top películas más populares (sin autenticación)",
    description="Devuelve el top de películas por score bayesiano. "
                "Útil para la pantalla de bienvenida o como fallback de cold-start.",
)
async def popular_movies(
    k:           int  = Query(default=10, ge=1, le=50),
    enrich_tmdb: bool = Query(default=True),
    db:          Session = Depends(get_db),
):
    raw        = _recommend_by_popularity(db, k)
    movie_ids  = [r["movie_id"] for r in raw]
    genres_map = _get_genres_for_movies(db, movie_ids)

    items = [
        RecommendationItem(
            movie_id = r["movie_id"],
            title    = r["title"],
            genres   = genres_map.get(r["movie_id"], []),
            score    = float(r["score"] if r.get("score") is not None else (r.get("bayesian_score") or 0.0)),
            tmdb_id  = r.get("tmdb_id"),
            source   = "popularity",
        )
        for r in raw
    ]

    if enrich_tmdb:
        async def _enrich_pop(item):
            if item.tmdb_id:
                tmdb_data = await fetch_tmdb_data(item.tmdb_id)
                item.poster_url = tmdb_data.get("poster_url")
                item.overview   = tmdb_data.get("overview")

        await asyncio.gather(*[_enrich_pop(item) for item in items])

    return RecommendationsOut(
        user_id         = 0,
        total           = len(items),
        source          = "popularity",
        recommendations = items,
    )
