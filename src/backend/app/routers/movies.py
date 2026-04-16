from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database     import get_db
from app.schemas      import MovieOut
from app.services.tmdb import fetch_tmdb_data

router = APIRouter(prefix="/movies", tags=["Películas"])


def _build_movie_out(row, genres: list[str], tmdb_data: dict) -> MovieOut:
    return MovieOut(
        movie_id      = row.movie_id,
        title         = row.title,
        genres        = genres,
        avg_rating    = float(row.avg_rating)    if row.avg_rating    else None,
        total_ratings = int(row.total_ratings)   if row.total_ratings else None,
        tmdb_id       = row.tmdb_id,
        poster_url    = tmdb_data.get("poster_url"),
        overview      = tmdb_data.get("overview"),
        release_date  = tmdb_data.get("release_date"),
    )


@router.get(
    "/search",
    response_model=list[MovieOut],
    summary="Buscar películas por título o género (HU-06)",
    description="Búsqueda parcial de título usando trigramas (pg_trgm). "
                "Opcionalmente filtra por género. Devuelve hasta `limit` resultados.",
)
async def search_movies(
    q:           str  = Query(default="",  description="Texto de búsqueda (título parcial)"),
    genre:       str  = Query(default="",  description="Filtrar por género (nombre exacto)"),
    limit:       int  = Query(default=20, ge=1, le=100),
    enrich_tmdb: bool = Query(default=False,
                               description="Enriquecer con TMDB (más lento, úsalo con limit pequeño)"),
    db:          Session = Depends(get_db),
):
    # Construir query dinámica según parámetros recibidos
    conditions = ["1=1"]
    params: dict = {"limit": limit}

    if q:
        conditions.append("m.title ILIKE :q")
        params["q"] = f"%{q}%"

    if genre:
        conditions.append("""
            m.movie_id IN (
                SELECT mg.movie_id FROM movie_genres mg
                JOIN   genres g ON g.genre_id = mg.genre_id
                WHERE  g.name ILIKE :genre
            )
        """)
        params["genre"] = genre

    where = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            m.movie_id,
            m.title,
            l.tmdb_id,
            ROUND(AVG(r.rating)::numeric, 2) AS avg_rating,
            COUNT(r.rating_id)               AS total_ratings
        FROM movies m
        LEFT JOIN links   l ON l.movie_id = m.movie_id
        LEFT JOIN ratings r ON r.movie_id = m.movie_id
        WHERE {where}
        GROUP BY m.movie_id, m.title, l.tmdb_id
        ORDER BY total_ratings DESC NULLS LAST, m.title
        LIMIT :limit
    """)

    rows = db.execute(sql, params).fetchall()

    if not rows:
        return []

    # Géneros en bulk para todos los resultados
    movie_ids = [r.movie_id for r in rows]
    genre_sql = text("""
        SELECT mg.movie_id, g.name
        FROM   movie_genres mg
        JOIN   genres g ON g.genre_id = mg.genre_id
        WHERE  mg.movie_id = ANY(:ids)
    """)
    genre_rows  = db.execute(genre_sql, {"ids": movie_ids}).fetchall()
    genres_map: dict[int, list[str]] = {}
    for gr in genre_rows:
        genres_map.setdefault(gr.movie_id, []).append(gr.name)

    results = []
    for row in rows:
        tmdb_data = {}
        if enrich_tmdb and row.tmdb_id:
            tmdb_data = await fetch_tmdb_data(row.tmdb_id)
        results.append(_build_movie_out(row, genres_map.get(row.movie_id, []), tmdb_data))

    return results


@router.get(
    "/{movie_id}",
    response_model=MovieOut,
    summary="Detalle de una película (HU-07)",
    description="Devuelve información completa de una película, incluyendo "
                "sinopsis y póster desde TMDB si está disponible.",
)
async def movie_detail(
    movie_id:    int,
    enrich_tmdb: bool = Query(default=True),
    db:          Session = Depends(get_db),
):
    sql = text("""
        SELECT
            m.movie_id,
            m.title,
            l.tmdb_id,
            ROUND(AVG(r.rating)::numeric, 2) AS avg_rating,
            COUNT(r.rating_id)               AS total_ratings
        FROM movies m
        LEFT JOIN links   l ON l.movie_id = m.movie_id
        LEFT JOIN ratings r ON r.movie_id = m.movie_id
        WHERE m.movie_id = :movie_id
        GROUP BY m.movie_id, m.title, l.tmdb_id
    """)
    row = db.execute(sql, {"movie_id": movie_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Película no encontrada")

    genre_sql  = text("""
        SELECT g.name FROM movie_genres mg
        JOIN genres g ON g.genre_id = mg.genre_id
        WHERE mg.movie_id = :movie_id
    """)
    genre_rows = db.execute(genre_sql, {"movie_id": movie_id}).fetchall()
    genres     = [r.name for r in genre_rows]

    tmdb_data = {}
    if enrich_tmdb and row.tmdb_id:
        tmdb_data = await fetch_tmdb_data(row.tmdb_id)

    return _build_movie_out(row, genres, tmdb_data)
