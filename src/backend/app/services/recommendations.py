# Lógica de recomendaciones con fallback en 3 capas:
# 1. Modelo ML (ML_SERVICE_URL cuando Alejandro lo despliegue)
# 2. Por preferencias de género del usuario
# 3. Popularidad bayesiana (siempre disponible)

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

from app.config  import get_settings
from app.schemas import RecommendationItem, RecommendationsOut

settings = get_settings()

TOP_K = 10   # número de recomendaciones a devolver


# 1. ML externo

async def _fetch_from_ml_service(user_id: int, k: int) -> Optional[list[dict]]:
    # Llama a POST {ML_SERVICE_URL}/recommend → {"recommendations": [{"movie_id": int, "score": float}]}
    # Devuelve None si el servicio no está disponible.
    if not settings.ML_SERVICE_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{settings.ML_SERVICE_URL}/recommend",
                json={"user_id": user_id, "k": k}
            )
            if resp.status_code == 200:
                return resp.json().get("recommendations")
    except Exception:
        pass
    return None


# 2. Por preferencias de género

def _recommend_by_genre(db: Session, user_id: int, k: int) -> list[dict]:
    # Películas de los géneros favoritos del usuario, ordenadas por score bayesiano.
    sql = text("""
        SELECT
            m.movie_id,
            m.title,
            l.tmdb_id,
            ROUND(AVG(r.rating)::numeric, 2) AS avg_rating,
            COUNT(r.rating_id)               AS total_ratings,
            ROUND(
                (COUNT(r.rating_id)::numeric / (COUNT(r.rating_id) + 500))
                * AVG(r.rating)
                + (500.0 / (COUNT(r.rating_id) + 500)) * 3.5
            , 4) AS score
        FROM movies m
        JOIN movie_genres mg ON mg.movie_id = m.movie_id
        JOIN ratings r       ON r.movie_id  = m.movie_id
        LEFT JOIN links l    ON l.movie_id  = m.movie_id
        WHERE mg.genre_id IN (
            SELECT genre_id FROM user_genre_preferences
            WHERE user_id = :user_id
            ORDER BY score DESC
            LIMIT 5
        )
        GROUP BY m.movie_id, m.title, l.tmdb_id
        HAVING COUNT(r.rating_id) >= 50
        ORDER BY score DESC
        LIMIT :k
    """)
    rows = db.execute(sql, {"user_id": user_id, "k": k}).fetchall()
    return [row._asdict() for row in rows]


# 3. Popularidad (fallback final)

def _recommend_by_popularity(db: Session, k: int) -> list[dict]:
    sql = text("""
        SELECT movie_id, title, tmdb_id, total_ratings,
               avg_rating, bayesian_score AS score
        FROM   vw_top_popular
        LIMIT  :k
    """)
    rows = db.execute(sql, {"k": k}).fetchall()
    return [row._asdict() for row in rows]


# Géneros de una película

def _get_genres_for_movies(db: Session, movie_ids: list[int]) -> dict[int, list[str]]:
    if not movie_ids:
        return {}
    sql = text("""
        SELECT mg.movie_id, g.name
        FROM   movie_genres mg
        JOIN   genres       g ON g.genre_id = mg.genre_id
        WHERE  mg.movie_id = ANY(:ids)
    """)
    rows = db.execute(sql, {"ids": movie_ids}).fetchall()
    result: dict[int, list[str]] = {}
    for row in rows:
        result.setdefault(row.movie_id, []).append(row.name)
    return result


# Función principal

async def get_recommendations(
    user_id: int,
    db: Session,
    k: int = TOP_K,
) -> RecommendationsOut:
    source = "model"
    raw: list[dict] = []

    # 1. Modelo ML externo
    ml_result = await _fetch_from_ml_service(user_id, k)
    if ml_result:
        # El modelo devuelve movie_id + score; enriquecemos desde la BD
        movie_ids = [r["movie_id"] for r in ml_result]
        id_to_score = {r["movie_id"]: r["score"] for r in ml_result}
        sql = text("""
            SELECT m.movie_id, m.title, l.tmdb_id
            FROM   movies m
            LEFT JOIN links l ON l.movie_id = m.movie_id
            WHERE  m.movie_id = ANY(:ids)
        """)
        rows = db.execute(sql, {"ids": movie_ids}).fetchall()
        raw = [{"movie_id": r.movie_id, "title": r.title,
                "tmdb_id": r.tmdb_id,
                "score": id_to_score.get(r.movie_id, 0.0)} for r in rows]
        source = "model"

    # 2. Preferencias de género
    if not raw:
        raw = _recommend_by_genre(db, user_id, k)
        source = "genre_based"

    # 3. Popularidad (fallback final)
    if not raw:
        raw = _recommend_by_popularity(db, k)
        source = "popularity"

    # Enriquecer con géneros
    movie_ids = [r["movie_id"] for r in raw]
    genres_map = _get_genres_for_movies(db, movie_ids)

    items = [
        RecommendationItem(
            movie_id  = r["movie_id"],
            title     = r["title"],
            genres    = genres_map.get(r["movie_id"], []),
            score     = float(r["score"] if r.get("score") is not None else (r.get("bayesian_score") or 0.0)),
            tmdb_id   = r.get("tmdb_id"),
            source    = source,
        )
        for r in raw
    ]

    return RecommendationsOut(
        user_id         = user_id,
        total           = len(items),
        source          = source,
        recommendations = items,
    )
