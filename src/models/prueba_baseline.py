import pandas as pd
from baseline import recommend_movies


def main():
    # -------------------------------
    # 1. Cargar datos
    # -------------------------------
    movies_df = pd.read_csv("data/processed/movies_clean.csv")
    ratings_df = pd.read_csv("data/processed/ratings_sample.csv")

    # -------------------------------
    # 2. PREPROCESADO
    # -------------------------------
    ratings_stats = (
        ratings_df.groupby("movieId")["rating"]
        .agg(rating="mean", votes="count")
        .reset_index()
    )

    # filtrar ruido
    ratings_stats = ratings_stats[ratings_stats["votes"] >= 50]

    # unir con películas
    movies_df = movies_df.merge(ratings_stats, on="movieId", how="inner")

    # -------------------------------
    # 3. Preferencias usuario
    # -------------------------------
    user_preferences = {
        "Action": 1.0,
        "Sci-Fi": 0.8,
        "Drama": 0.3
    }

    # -------------------------------
    # 4. Recomendaciones
    # -------------------------------
    recs = recommend_movies(
        movies_df=movies_df,
        user_preferences=user_preferences,
        top_n=10
    )

    print(recs)


if __name__ == "__main__":
    main()