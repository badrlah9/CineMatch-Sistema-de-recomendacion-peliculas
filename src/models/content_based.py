
"""
Módulo de contenido para CineMatch.

Este fichero se encarga de:
- normalizar preferencias del usuario
- limpiar y normalizar géneros
- calcular un score de contenido menos sesgado
- enriquecer películas con rating medio y número de votos
"""

from __future__ import annotations

import ast
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd


# ============================================================
# UTILIDADES DE NORMALIZACIÓN
# ============================================================


def normalize_user_preferences(
    user_prefs: Optional[Mapping[str, float]],
    *,
    input_scale_max: float = 5.0,
) -> dict[str, float]:
    """
    Convierte preferencias del usuario a escala 0-1
    y unifica géneros en minúsculas.

    Ejemplo:
        {"Action": 5, "Drama": 2} -> {"action": 1.0, "drama": 0.4}
    """
    if not user_prefs:
        return {}

    normalized: dict[str, float] = {}

    for genre, value in user_prefs.items():
        key = str(genre).strip().lower()
        if not key:
            continue

        try:
            score = float(value)
        except (TypeError, ValueError):
            continue

        score = max(0.0, min(score, input_scale_max))
        normalized[key] = score / input_scale_max if input_scale_max else 0.0

    return normalized


def normalize_genres(genres: object) -> list[str]:
    """
    Normaliza la columna genres a una lista de strings en minúsculas.

    Soporta:
    - listas reales
    - tuplas / sets
    - strings MovieLens: "Action|Comedy"
    - strings serializados: "['Action', 'Comedy']"
    """
    if genres is None:
        return []

    if isinstance(genres, list):
        return [str(g).strip().lower() for g in genres if str(g).strip()]

    if isinstance(genres, (tuple, set)):
        return [str(g).strip().lower() for g in genres if str(g).strip()]

    if isinstance(genres, str):
        raw = genres.strip()
        if not raw:
            return []

        if "|" in raw:
            return [g.strip().lower() for g in raw.split("|") if g.strip()]

        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple, set)):
                return [str(g).strip().lower() for g in parsed if str(g).strip()]
        except (ValueError, SyntaxError):
            pass

        return [raw.lower()]

    return []


# ============================================================
# UTILIDADES DE ENRIQUECIMIENTO DE DATOS
# ============================================================


def enrich_movies_with_stats(
    movies_df: pd.DataFrame,
    ratings_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Añade o recalcula `rating` y `num_ratings` en movies_df a partir de ratings_df.

    Muy útil para notebooks o pipelines donde esas columnas no estén limpias.
    """
    if "movieId" not in movies_df.columns:
        raise ValueError("movies_df debe tener la columna 'movieId'")

    required = {"movieId", "rating"}
    missing = required - set(ratings_df.columns)
    if missing:
        raise ValueError(f"ratings_df no tiene columnas necesarias: {sorted(missing)}")

    result = movies_df.copy()

    drop_cols = ["rating", "num_ratings", "rating_x", "rating_y"]
    drop_existing = [col for col in drop_cols if col in result.columns]
    if drop_existing:
        result = result.drop(columns=drop_existing)

    movie_stats = (
        ratings_df.groupby("movieId")["rating"]
        .agg(rating="mean", num_ratings="count")
        .reset_index()
    )

    result = result.merge(movie_stats, on="movieId", how="left")
    result["rating"] = result["rating"].fillna(0.0).astype(float)
    result["num_ratings"] = result["num_ratings"].fillna(0).astype(int)

    return result


# ============================================================
# SCORES DE CONTENIDO
# ============================================================


def compute_genre_score(
    genres: object,
    user_prefs: Optional[Mapping[str, float]],
) -> float:
    """
    Calcula afinidad entre géneros de la película y preferencias del usuario.

    Mejoras:
    - menos sesgo hacia películas de un solo género
    - algo más de premio a mezclas con varios géneros relevantes
    - si no hay preferencias, devuelve 0
    """
    prefs = normalize_user_preferences(user_prefs)
    normalized_genres = normalize_genres(genres)

    if not prefs or not normalized_genres:
        return 0.0

    values = np.array([prefs.get(g, 0.0) for g in normalized_genres], dtype=float)
    matched = values[values > 0]

    if matched.size == 0:
        return 0.0

    max_score = float(np.max(matched))
    mean_positive = float(np.mean(matched))
    coverage_in_movie = float(len(matched) / len(normalized_genres))
    coverage_in_prefs = float(len(matched) / max(len(prefs), 1))
    multi_match_bonus = min(len(matched) / 3.0, 1.0)

    base = (
        0.35 * max_score
        + 0.30 * mean_positive
        + 0.20 * coverage_in_movie
        + 0.10 * coverage_in_prefs
        + 0.05 * multi_match_bonus
    )

    # Penalización suave para evitar que el sistema se obsesione con
    # películas de un solo género muy dominante.
    if len(normalized_genres) == 1:
        base *= 0.84
    elif len(matched) >= 2:
        base *= 1.04

    return float(min(base, 1.0))


def compute_weighted_rating(df: pd.DataFrame, m: int = 100) -> pd.Series:
    """
    Rating ponderado tipo IMDb.
    """
    if "rating" not in df.columns:
        raise ValueError("Falta la columna 'rating' en movies_df")

    if "num_ratings" not in df.columns:
        return df["rating"].astype(float)

    rating = df["rating"].fillna(0.0).astype(float)
    num_ratings = df["num_ratings"].fillna(0).astype(float)
    c_global = float(rating.mean()) if len(rating) else 0.0

    weighted = (
        (num_ratings / (num_ratings + m)) * rating
        + (m / (num_ratings + m)) * c_global
    )
    return weighted.astype(float)


def _normalize_series(series: pd.Series) -> pd.Series:
    min_value = float(series.min()) if len(series) else 0.0
    max_value = float(series.max()) if len(series) else 0.0

    if max_value == min_value:
        return pd.Series([0.0] * len(series), index=series.index)

    return (series - min_value) / (max_value - min_value)


def compute_baseline_scores(
    movie_ids: Iterable[int],
    movies_df: pd.DataFrame,
    user_preferences: Optional[Mapping[str, float]],
    min_votes: int = 20,
) -> pd.DataFrame:
    """
    Calcula un score base de contenido sobre un subconjunto de películas.

    Devuelve:
        movieId, baseline_score, title, genres, rating, num_ratings
    """
    required_cols = {"movieId", "title", "genres", "rating", "num_ratings"}
    missing = required_cols - set(movies_df.columns)
    if missing:
        raise ValueError(f"movies_df no tiene columnas necesarias: {sorted(missing)}")

    movie_ids = list(movie_ids)
    if not movie_ids:
        return pd.DataFrame(
            columns=[
                "movieId",
                "baseline_score",
                "title",
                "genres",
                "rating",
                "num_ratings",
                "genre_score",
                "rating_score",
                "popularity_score",
            ]
        )

    df = movies_df[movies_df["movieId"].isin(movie_ids)].copy()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "movieId",
                "baseline_score",
                "title",
                "genres",
                "rating",
                "num_ratings",
                "genre_score",
                "rating_score",
                "popularity_score",
            ]
        )

    if min_votes > 0:
        filtered = df[df["num_ratings"].fillna(0).astype(int) >= int(min_votes)].copy()
        if not filtered.empty:
            df = filtered

    prefs = normalize_user_preferences(user_preferences)

    if prefs:
        df["genre_score"] = df["genres"].apply(
            lambda g: compute_genre_score(g, prefs)
        ).astype(float)
    else:
        df["genre_score"] = 0.0

    df["rating_score"] = compute_weighted_rating(df, m=100)
    df["rating_score"] = _normalize_series(df["rating_score"]).astype(float)

    popularity = np.log1p(df["num_ratings"].fillna(0).astype(float))
    df["popularity_score"] = _normalize_series(popularity).astype(float)

    if prefs:
        # Balance más conservador para evitar sesgo de género extremo.
        df["baseline_score"] = (
            0.45 * df["genre_score"]
            + 0.35 * df["rating_score"]
            + 0.20 * df["popularity_score"]
        )
    else:
        # Si no hay gustos, prioriza calidad y popularidad.
        df["baseline_score"] = (
            0.65 * df["rating_score"]
            + 0.35 * df["popularity_score"]
        )

    return df[
        [
            "movieId",
            "baseline_score",
            "title",
            "genres",
            "rating",
            "num_ratings",
            "genre_score",
            "rating_score",
            "popularity_score",
        ]
    ].sort_values("baseline_score", ascending=False).reset_index(drop=True)
