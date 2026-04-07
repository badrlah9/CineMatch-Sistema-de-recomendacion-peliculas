import pandas as pd
import ast

# Importar funciones del modelo
from baseline import train_baseline, recommend_by_genres

def main():
    ratings = pd.read_csv("data/processed/ratings_sample.csv")
    movies = pd.read_csv("data/processed/movies_clean.csv")

    movies["genres"] = movies["genres"].apply(ast.literal_eval)

    model = train_baseline(ratings, movies)

    genres = ['Drama']
    recs = recommend_by_genres(model, genres)

    print("\nRecomendaciones:\n")
    print(recs)


if __name__ == "__main__":
    main()