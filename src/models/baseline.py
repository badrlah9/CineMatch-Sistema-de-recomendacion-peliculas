"""
======================================================
BASELINE RECOMMENDER - CINE MATCH
======================================================

Este módulo implementa un sistema de recomendación simple
(baseline) basado en popularidad y filtrado por géneros.

Funcionamiento general:
1. Se calculan las películas mejor valoradas (media de ratings)
   filtrando aquellas con pocas valoraciones (ruido).
2. Se permite filtrar recomendaciones en función de los géneros
   deseados por el usuario.
3. Se calcula un score de coincidencia de géneros para priorizar
   las películas más relevantes.

Este modelo NO utiliza machine learning avanzado, pero sirve como:
- Punto de partida (baseline)
- Referencia para comparar modelos más complejos
- Sistema rápido y eficiente para recomendaciones iniciales

Entradas:
- ratings: DataFrame con valoraciones de usuarios
- movies: DataFrame con información de películas (incluyendo géneros)

Salida:
- DataFrame con recomendaciones ordenadas por relevancia

Nota:
Se asume que la columna 'genres' ya está preprocesada como lista
(no string). La limpieza de datos debe hacerse fuera de este módulo.
======================================================
"""


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

    # --------------------------------------------------
    # 1. Número de ratings por película
    # --------------------------------------------------
    ratings_count = ratings.groupby("movieId")["rating"].count()

    # --------------------------------------------------
    # 2. Filtrar películas con suficientes valoraciones
    # --------------------------------------------------
    valid_movies = ratings_count[ratings_count >= min_ratings].index

    filtered_ratings = ratings[ratings["movieId"].isin(valid_movies)]

    # --------------------------------------------------
    # 3. Calcular rating medio
    # --------------------------------------------------
    top_movies = (
        filtered_ratings.groupby("movieId")["rating"]
        .mean()
        .reset_index()
        .rename(columns={"rating": "rating"})  # opcional, claridad
    )

    # --------------------------------------------------
    # 4. Ordenar + añadir info de películas
    # --------------------------------------------------
    top_movies = (
        top_movies
        .sort_values(by="rating", ascending=False)
        .merge(movies, on="movieId")
    )

    return top_movies


def recommend_by_genres(df, input_genres, n=10, min_match=0.75):
    """
    Recomienda películas en función de los géneros proporcionados.

    Parámetros:
    - df: modelo baseline (ranking de películas)
    - input_genres: lista de géneros deseados
    - n: número de recomendaciones a devolver
    - min_match: porcentaje mínimo de coincidencia

    Devuelve:
    DataFrame con recomendaciones (incluyendo movieId)
    """

    # --------------------------------------------------
    # 1. Copia para no modificar el original
    # --------------------------------------------------
    df = df.copy()

    # --------------------------------------------------
    # 2. Score de coincidencia de géneros
    # --------------------------------------------------
    df["genre_score"] = df["genres"].apply(
        lambda genres: len(set(genres) & set(input_genres))
    )

    # --------------------------------------------------
    # 3. Porcentaje de coincidencia
    # --------------------------------------------------
    df["genre_coverage"] = df["genre_score"] / len(input_genres)

    # --------------------------------------------------
    # 4. Filtrado por umbral
    # --------------------------------------------------
    df_filtered = df[df["genre_coverage"] >= min_match]

    # Fallback si no hay resultados
    if df_filtered.empty:
        df_filtered = df[df["genre_score"] > 0]

    # --------------------------------------------------
    # 5. Ordenar y devolver columnas clave
    # --------------------------------------------------
    return (
        df_filtered
        .sort_values(by="rating", ascending=False)
        .head(n)[
            ["movieId", "title", "rating", "genres"]
        ]
    )


def get_recommendations(model, genres, n=10):
    """
    Wrapper de alto nivel para obtener recomendaciones.
    """
    return recommend_by_genres(model, genres, n)