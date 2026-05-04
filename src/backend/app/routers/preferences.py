from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database     import get_db
from app.dependencies import get_current_user
from app.models       import User, UserGenrePreference, Genre
from app.schemas      import PreferenceIn, PreferenceOut

router = APIRouter(prefix="/users/me/preferences", tags=["Preferencias de usuario"])


@router.get(
    "",
    response_model=list[PreferenceOut],
    summary="Ver mis preferencias de género (HU-08)",
)
def get_my_preferences(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    sql = text("""
        SELECT ugp.genre_id, g.name AS genre_name, ugp.score::float
        FROM   user_genre_preferences ugp
        JOIN   genres g ON g.genre_id = ugp.genre_id
        WHERE  ugp.user_id = :user_id
        ORDER  BY ugp.score DESC
    """)
    rows = db.execute(sql, {"user_id": current_user.user_id}).fetchall()
    return [PreferenceOut(genre_id=r.genre_id, genre_name=r.genre_name, score=r.score)
            for r in rows]


@router.put(
    "",
    response_model=list[PreferenceOut],
    summary="Establecer preferencias de género (HU-09)",
    description="Reemplaza todas las preferencias de género del usuario. "
                "Envía la lista completa de géneros con sus scores [0.0 – 5.0].",
)
def set_my_preferences(
    preferences:  list[PreferenceIn],
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    genre_ids = [p.genre_id for p in preferences]

    # Detectar duplicados en la petición antes de tocar la BD
    if len(genre_ids) != len(set(genre_ids)):
        raise HTTPException(status_code=400, detail="Se enviaron genre_id duplicados")

    # Validar que todos los genre_id existen
    existing = db.query(Genre).filter(Genre.genre_id.in_(genre_ids)).all()
    if len(existing) != len(set(genre_ids)):
        raise HTTPException(status_code=400, detail="Uno o más genre_id no son válidos")

    # Eliminar preferencias actuales y reemplazar
    db.query(UserGenrePreference).filter(
        UserGenrePreference.user_id == current_user.user_id
    ).delete()

    for pref in preferences:
        db.add(UserGenrePreference(
            user_id  = current_user.user_id,
            genre_id = pref.genre_id,
            score    = pref.score,
        ))

    db.commit()
    return get_my_preferences(current_user=current_user, db=db)


@router.delete(
    "",
    status_code=204,
    summary="Eliminar todas mis preferencias de género",
)
def delete_my_preferences(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    db.query(UserGenrePreference).filter(
        UserGenrePreference.user_id == current_user.user_id
    ).delete()
    db.commit()
