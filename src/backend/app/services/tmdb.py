import httpx
from typing import Optional
from app.config import get_settings

settings = get_settings()


async def fetch_tmdb_data(tmdb_id: int) -> dict:
    """
    Llama a la API de TMDB y devuelve poster_url, overview y release_date.
    Si la API no está disponible o el ID no existe, devuelve un dict vacío
    (el backend nunca falla por culpa de TMDB).
    """
    if not settings.TMDB_API_KEY or not tmdb_id:
        return {}

    url = f"{settings.TMDB_BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": settings.TMDB_API_KEY, "language": "es-ES"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return {}
            data = response.json()
            poster_path = data.get("poster_path")
            return {
                "poster_url":   f"{settings.TMDB_IMAGE_BASE}{poster_path}"
                                if poster_path else None,
                "overview":     data.get("overview"),
                "release_date": data.get("release_date"),
            }
    except Exception:
        # Cualquier error de red → devolver vacío, no romper la respuesta
        return {}
