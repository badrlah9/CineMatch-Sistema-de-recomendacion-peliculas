import pandas as pd


def compute_genre_score(genres: list, user_prefs: dict) -> float:
    """
    Calcula la afinidad entre una película y el usuario en base a sus géneros.
    """
    if not genres:
        return 0.0

    scores = [float(user_prefs.get(g, 0)) for g in genres]
    return sum(scores) / len(genres)


def recommend_movies(
    movies_df: pd.DataFrame,
    user_preferences: dict,
    top_n: int = 10
) -> pd.DataFrame:
    """
    Sistema de recomendación baseline (INFERENCIA):

    - Usa géneros + rating ya precalculado
    - NO hace cálculos pesados (groupby)

    Args:
        movies_df: ['movieId', 'title', 'genres', 'rating']
        user_preferences: {genre: score}
        top_n: número de recomendaciones

    Returns:
        DataFrame con recomendaciones
    """

    df = movies_df.copy()

    # 1. Calcular afinidad por géneros
    df["genre_score"] = df["genres"].apply(
        lambda g: compute_genre_score(g, user_preferences)
    ).astype(float)

    # 2. Normalizar rating
    df["rating_norm"] = df["rating"] / 5.0

    # 3. Score final
    df["final_score"] = (
        0.5 * df["genre_score"] +
        0.5 * df["rating_norm"]
    )

    # 4. Ranking
    result = (
        df.sort_values("final_score", ascending=False)
        .head(top_n)[["movieId", "title", "genres", "rating"]]
    )

    return result