from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, field_validator

from app.database    import get_db
from app.dependencies import get_current_user
from app.models      import User
from app.schemas     import RatingOut

router = APIRouter(prefix="/ratings", tags=["Ratings"])


@router.get("/me", response_model=list[RatingOut], summary="Ver mis valoraciones")
def get_my_ratings(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    rows = db.execute(
        text("""
            SELECT r.movie_id, m.title, r.rating::float AS rating, r.rated_at
            FROM   cinematch_ratings r
            JOIN   movies m ON m.movie_id = r.movie_id
            WHERE  r.user_id = :uid
            ORDER  BY r.rated_at DESC
        """),
        {"uid": current_user.user_id},
    ).fetchall()
    return [
        RatingOut(
            movie_id=row.movie_id,
            title=row.title,
            rating=row.rating,
            rated_at=row.rated_at,
        )
        for row in rows
    ]


class RatingIn(BaseModel):
    movie_id: int
    rating:   float   # 1.0 = dislike, 5.0 = like

    @field_validator("rating")
    def rating_range(cls, v):
        if not (0.5 <= v <= 5.0):
            raise ValueError("El rating debe estar entre 0.5 y 5.0")
        return round(v, 1)


@router.post("", status_code=201, summary="Guardar o actualizar un rating de película")
def rate_movie(
    body:         RatingIn,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Guarda la valoración del usuario para una película (upsert).
    - ❤️  like    → rating 5.0
    - ❌  dislike → rating 1.0
    Si el usuario ya había valorado esa película, actualiza el valor.
    """
    # Verificar que la película existe
    exists = db.execute(
        text("SELECT 1 FROM movies WHERE movie_id = :mid"),
        {"mid": body.movie_id},
    ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Película no encontrada")

    # Upsert manual: actualiza si ya existe, inserta si no
    existing = db.execute(
        text("SELECT rating_id FROM cinematch_ratings WHERE user_id = :uid AND movie_id = :mid"),
        {"uid": current_user.user_id, "mid": body.movie_id},
    ).fetchone()

    if existing:
        db.execute(
            text("UPDATE cinematch_ratings SET rating = :rating, rated_at = NOW() WHERE rating_id = :rid"),
            {"rating": body.rating, "rid": existing.rating_id},
        )
    else:
        db.execute(
            text("INSERT INTO cinematch_ratings (user_id, movie_id, rating, rated_at) VALUES (:uid, :mid, :rating, NOW())"),
            {"uid": current_user.user_id, "mid": body.movie_id, "rating": body.rating},
        )
    db.commit()
    return {"ok": True, "user_id": current_user.user_id, "movie_id": body.movie_id, "rating": body.rating}
