import pandas as pd
import ast


def compute_genre_score(genres: list, user_prefs: dict) -> float:
    """
    Calcula la afinidad entre una película y el usuario en base a sus géneros.

    Args:
        genres: lista de géneros de la película
        user_prefs: diccionario {género: peso}

    Returns:
        Score medio (0-1)
    """
    if not genres:
        return 0.0

    scores = [float(user_prefs.get(g, 0)) for g in genres]
    return sum(scores) / len(genres)


def recommend_movies(
    movies_df: pd.DataFrame,
    ratings_df: pd.DataFrame,
    user_preferences: dict,
    top_n: int = 10,
    min_votes: int = 50
) -> pd.DataFrame:
    """
    Sistema de recomendación baseline:
    combina preferencias del usuario (géneros) + calidad global (rating).

    Args:
        movies_df: ['movieId', 'title', 'genres']
        ratings_df: ['movieId', 'rating']
        user_preferences: {genre: score}
        top_n: número de recomendaciones
        min_votes: mínimo de votos por película

    Returns:
        DataFrame con recomendaciones ordenadas
    """

    # 1. Normalizar formato de géneros (string -> list)
    movies_df = movies_df.copy()
    movies_df["genres"] = movies_df["genres"].apply(
        lambda x: ast.literal_eval(x) if isinstance(x, str) else x
    )

    # 2. Calcular métricas de rating
    ratings_stats = (
        ratings_df.groupby("movieId")["rating"]
        .agg(rating="mean", votes="count")
        .reset_index()
    )

    # 3. Filtrar películas con suficiente información
    ratings_stats = ratings_stats[ratings_stats["votes"] >= min_votes]

    # 4. Unir datasets
    df = movies_df.merge(ratings_stats, on="movieId", how="inner")

    # 5. Limpiar filas sin géneros válidos
    df = df[df["genres"].apply(lambda g: isinstance(g, list) and len(g) > 0)]

    # 6. Calcular afinidad por géneros
    df["genre_score"] = df["genres"].apply(
        lambda g: compute_genre_score(g, user_preferences)
    ).astype(float)

    # 7. Normalizar rating (0-1)
    df["rating_norm"] = df["rating"] / 5.0

    # 8. Score final (balance simple)
    df["final_score"] = (
        0.5 * df["genre_score"] +
        0.5 * df["rating_norm"]
    )

    # 9. Ranking final
    result = (
        df.sort_values("final_score", ascending=False)
        .head(top_n)[["movieId", "title", "genres", "rating"]]
    )

    return result