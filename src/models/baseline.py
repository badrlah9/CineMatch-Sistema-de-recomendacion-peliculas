import pandas as pd


def train_baseline(ratings, movies, min_ratings=20):
    """
    Entrena un modelo baseline basado en popularidad.

    Pasos:
    1. Cuenta cuántos ratings tiene cada película
    2. Filtra aquellas con pocos ratings (ruido)
    3. Calcula la media de rating por película
    4. Ordena de mejor a peor
    5. Añade información de la película (título, géneros)

    Devuelve:
    DataFrame con películas ordenadas por rating medio
    """

    # Contar número de ratings por película
    ratings_count = ratings.groupby("movieId")["rating"].count()

    # Filtrar películas con suficientes valoraciones
    valid_movies = ratings_count[ratings_count >= min_ratings].index

    # Mantener solo ratings de películas válidas
    filtered_ratings = ratings[ratings["movieId"].isin(valid_movies)]

    # Calcular rating medio y ordenar
    top_movies = (
        filtered_ratings.groupby("movieId")["rating"]
        .mean()  # media de rating
        .sort_values(ascending=False)  # ordenar de mayor a menor
        .reset_index()
        .merge(movies, on="movieId")  # añadir info de películas
    )

    return top_movies


def recommend_by_genres(df, input_genres, n=10, min_match=0.75):
    """
    Recomienda películas en función de los géneros proporcionados.

    Parámetros:
    - df: modelo baseline (ranking de películas)
    - input_genres: lista de géneros deseados
    - n: número de recomendaciones a devolver
    - min_match: porcentaje mínimo de coincidencia de géneros

    Pasos:
    1. Calcula coincidencias de géneros (genre_score)
    2. Calcula porcentaje de coincidencia (genre_coverage)
    3. Filtra según el umbral mínimo
    4. Si no hay resultados, aplica fallback
    5. Ordena por rating y devuelve top N
    """

    # Copia para evitar modificar el DataFrame original
    df = df.copy()

    # Calcular número de géneros en común con el input
    df["genre_score"] = df["genres"].apply(
        lambda genres: len(set(genres) & set(input_genres))
    )

    # Calcular porcentaje de coincidencia respecto al input
    df["genre_coverage"] = df["genre_score"] / len(input_genres)

    # Filtrar por mínimo porcentaje de coincidencia
    df_filtered = df[df["genre_coverage"] >= min_match]

    # Fallback: si no hay resultados, relajar condición
    if df_filtered.empty:
        df_filtered = df[df["genre_score"] > 0]

    # Ordenar por rating (mejor valoradas primero)
    return (
        df_filtered
        .sort_values(by="rating", ascending=False)
        .head(n)[["title", "rating", "genres", "genre_score", "genre_coverage"]]
    )


def get_recommendations(model, genres, n=10):
    """
    Función de alto nivel para obtener recomendaciones.

    Recibe:
    - model: resultado de train_baseline (ya entrenado)
    - genres: lista de géneros del usuario
    - n: número de recomendaciones

    Devuelve:
    - Top N películas recomendadas
    """

    return recommend_by_genres(model, genres, n)