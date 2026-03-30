import pandas as pd

def train_baseline(ratings, movies, min_ratings=20):
    """
    Entrena el modelo baseline por popularidad
    """

    ratings_count = ratings.groupby("movieId")["rating"].count()

    valid_movies = ratings_count[ratings_count >= min_ratings].index

    filtered_ratings = ratings[ratings["movieId"].isin(valid_movies)]

    top_movies = (
        filtered_ratings.groupby("movieId")["rating"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
        .merge(movies, on="movieId")
    )

    return top_movies


def recommend_top_movies(df, n=10):
    return df.head(n)[["title", "rating"]]