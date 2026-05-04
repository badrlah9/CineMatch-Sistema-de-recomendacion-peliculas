from __future__ import annotations

"""
Señal basada en contenido.

Este módulo no intenta "adivinar" todo él solo.
Su objetivo es generar una buena base:
- respetar gustos por género
- favorecer películas bien valoradas
- penalizar títulos con muy pocos votos
"""

import ast
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd


REQUIRED_MOVIE_COLUMNS = {"movieId", "title", "genres", "rating", "num_ratings"}


def normalize_user_preferences(
    user_prefs: Optional[Mapping[str, float]],
    *,
    input_scale_max: float = 5.0,
) -> dict[str, float]:
    """
    Pasa las preferencias del usuario a una escala 0-1.

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
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue

        numeric_value = max(0.0, min(numeric_value, input_scale_max))
        normalized[key] = numeric_value / input_scale_max if input_scale_max else 0.0

    return normalized


def normalize_genres(genres: object) -> list[str]:
    """
    Convierte cualquier formato de géneros a lista normalizada.

    Soporta:
    - listas reales
    - tuplas / sets
    - strings tipo "Action|Comedy"
    - strings serializados tipo "['Action', 'Comedy']"
    """
    if genres is None:
        return []

    if isinstance(genres, list):
        return [str(item).strip().lower() for item in genres if str(item).strip()]

    if isinstance(genres, (tuple, set)):
        return [str(item).strip().lower() for item in genres if str(item).strip()]

    if isinstance(genres, str):
        raw = genres.strip()
        if not raw:
            return []

        if "|" in raw:
            return [item.strip().lower() for item in raw.split("|") if item.strip()]

        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple, set)):
                return [str(item).strip().lower() for item in parsed if str(item).strip()]
        except (ValueError, SyntaxError):
            pass

        return [raw.lower()]

    return []


def enrich_movies_with_stats(
    movies_df: pd.DataFrame,
    ratings_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Recalcula rating medio y número de ratings por película.

    Esto es útil si `movies_df` solo trae:
    - movieId
    - title
    - genres

    y quieres enriquecerlo usando `ratings_df`.
    """
    if "movieId" not in movies_df.columns:
        raise ValueError("movies_df debe tener la columna 'movieId'")

    required_ratings = {"movieId", "rating"}
    missing = required_ratings - set(ratings_df.columns)
    if missing:
        raise ValueError(
            f"ratings_df no tiene columnas necesarias: {sorted(missing)}"
        )

    result = movies_df.copy()

    drop_cols = ["rating", "num_ratings", "rating_x", "rating_y"]
    existing_drop_cols = [column for column in drop_cols if column in result.columns]
    if existing_drop_cols:
        result = result.drop(columns=existing_drop_cols)

    movie_stats = (
        ratings_df.groupby("movieId")["rating"]
        .agg(rating="mean", num_ratings="count")
        .reset_index()
    )

    result = result.merge(movie_stats, on="movieId", how="left")
    result["rating"] = result["rating"].fillna(0.0).astype(float)
    result["num_ratings"] = result["num_ratings"].fillna(0).astype(int)

    return result


def compute_genre_score(
    genres: object,
    user_preferences: Optional[Mapping[str, float]],
) -> float:
    """
    Mide afinidad de géneros entre película y usuario.

    La fórmula está pensada para ser:
    - simple
    - interpretable
    - menos sesgada hacia películas de un solo género
    """
    # Las preferencias llegan ya normalizadas a escala 0-1 desde compute_baseline_scores.
    # Solo bajamos las claves a minúsculas; no volver a normalizar los valores.
    if not user_preferences:
        return 0.0
    preferences_norm = {str(k).strip().lower(): float(v) for k, v in user_preferences.items()}

    normalized_genres = normalize_genres(genres)
    if not preferences_norm or not normalized_genres:
        return 0.0

    # Géneros con < 2 estrellas (0.4 en escala 0-1) se ignoran: el usuario no los quiere.
    active_preferences = {k: v for k, v in preferences_norm.items() if v >= 0.4}
    if not active_preferences:
        return 0.0

    values = np.array(
        [active_preferences.get(genre, 0.0) for genre in normalized_genres],
        dtype=float,
    )
    matched_values = values[values > 0]

    if matched_values.size == 0:
        return 0.0

    max_score = float(np.max(matched_values))
    mean_score = float(np.mean(matched_values))
    coverage_in_movie = float(len(matched_values) / len(normalized_genres))
    coverage_in_preferences = float(len(matched_values) / max(len(active_preferences), 1))
    multi_match_bonus = min(len(matched_values) / 3.0, 1.0)

    score = (
        0.35 * max_score
        + 0.30 * mean_score
        + 0.20 * coverage_in_movie
        + 0.10 * coverage_in_preferences
        + 0.05 * multi_match_bonus
    )

    # Penalización suave para evitar recomendar siempre películas
    # con un único género dominante.
    if len(normalized_genres) == 1:
        score *= 0.84
    elif len(matched_values) >= 2:
        score *= 1.04

    return float(min(score, 1.0))


def compute_weighted_rating(df: pd.DataFrame, m: int = 100) -> pd.Series:
    """
    Rating ponderado estilo IMDb.

    Penaliza de forma suave las películas con pocos votos.
    """
    if "rating" not in df.columns:
        raise ValueError("Falta la columna 'rating' en movies_df")

    if "num_ratings" not in df.columns:
        return df["rating"].astype(float)

    rating = df["rating"].fillna(0.0).astype(float)
    num_ratings = df["num_ratings"].fillna(0).astype(float)
    global_mean = float(rating.mean()) if len(rating) else 0.0

    weighted = (
        (num_ratings / (num_ratings + m)) * rating
        + (m / (num_ratings + m)) * global_mean
    )
    return weighted.astype(float)


def normalize_series(series: pd.Series) -> pd.Series:
    """
    Normaliza una serie a rango 0-1.
    """
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
    Calcula la señal base de contenido.

    Devuelve un DataFrame ya ordenado con:
    - baseline_score
    - genre_score
    - rating_score
    - popularity_score
    """
    missing = REQUIRED_MOVIE_COLUMNS - set(movies_df.columns)
    if missing:
        raise ValueError(
            f"movies_df no tiene columnas necesarias: {sorted(missing)}"
        )

    movie_ids = list(movie_ids)
    empty_columns = [
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

    if not movie_ids:
        return pd.DataFrame(columns=empty_columns)

    df = movies_df[movies_df["movieId"].isin(movie_ids)].copy()
    if df.empty:
        return pd.DataFrame(columns=empty_columns)

    if min_votes > 0:
        filtered = df[df["num_ratings"].fillna(0).astype(int) >= int(min_votes)].copy()
        if not filtered.empty:
            df = filtered

    # Las preferencias llegan ya normalizadas a 0-1 desde el orquestador.
    # Solo normalizar si vienen en escala cruda (> 1.0); de lo contrario usar directamente.
    if user_preferences and any(float(v) > 1.0 for v in user_preferences.values()):
        preferences = normalize_user_preferences(user_preferences)
    else:
        preferences = {str(k).strip().lower(): float(v) for k, v in (user_preferences or {}).items()}

    if preferences:
        df["genre_score"] = df["genres"].apply(
            lambda genres: compute_genre_score(genres, preferences)
        ).astype(float)
    else:
        df["genre_score"] = 0.0

    df["rating_score"] = compute_weighted_rating(df, m=100)
    df["rating_score"] = normalize_series(df["rating_score"]).astype(float)

    popularity = np.log1p(df["num_ratings"].fillna(0).astype(float))
    df["popularity_score"] = normalize_series(popularity).astype(float)

    if preferences:
        df["baseline_score"] = (
            0.65 * df["genre_score"]
            + 0.25 * df["rating_score"]
            + 0.10 * df["popularity_score"]
        )
    else:
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
