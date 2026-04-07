import pandas as pd

from baseline import recommend_movies


def main():
    # -----------------------------
    # 1. Cargar datos
    # -----------------------------
    movies_df = pd.read_csv("data/processed/movies_clean.csv")
    ratings_df = pd.read_csv("data/processed/ratings_sample.csv")

    # -----------------------------
    # 3. Definir preferencias usuario
    # -----------------------------
    user_preferences = {
        "Action": 1.0,
        "Comedy": 0.5,
        "Sci-Fi": 0.8,
        "Drama": 0.5
    }

    # -----------------------------
    # 4. Generar recomendaciones
    # -----------------------------
    recs = recommend_movies(
        movies_df=movies_df,
        ratings_df=ratings_df,
        user_preferences=user_preferences,
        top_n=10
    )

    # -----------------------------
    # 5. Mostrar resultados
    # -----------------------------
    print("\n🎬 Recomendaciones:\n")
    print(recs.to_string(index=False))


if __name__ == "__main__":
    main()