# Carga los CSV de data/processed/ (generados por ingest.py) en PostgreSQL.
# Solo carga catálogo (películas, géneros y links).
# NO carga ratings históricos porque el modelo colaborativo ya está entrenado.

import ast
import os
import sys
import argparse

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


# =====================================================
# Conexión
# =====================================================

def get_engine():
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("ERROR: DATABASE_URL no está definida en .env")
        sys.exit(1)

    try:
        engine = create_engine(db_url, pool_pre_ping=True)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        return engine

    except Exception as e:
        print(f"ERROR: No se puede conectar a la base de datos.\n{e}")
        sys.exit(1)


# =====================================================
# Argumentos
# =====================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Carga catálogo CineMatch en PostgreSQL"
    )

    p.add_argument(
        "--data-dir",
        required=True,
        help="Ruta a data/processed/"
    )

    p.add_argument(
        "--truncate",
        action="store_true",
        help="Vaciar tablas antes de cargar"
    )

    return p.parse_args()


# =====================================================
# Helpers
# =====================================================

def _check_file(path):
    if not os.path.isfile(path):
        print(f"ERROR: No existe {path}")
        sys.exit(1)


def _count(conn, table):
    return conn.execute(
        text(f"SELECT COUNT(*) FROM {table}")
    ).scalar()


# =====================================================
# Truncate
# =====================================================

def truncate_tables(engine):
    print("\n[0] Vaciando tablas...")

    with engine.begin() as conn:
        conn.execute(text("""
            TRUNCATE TABLE
                movie_genres,
                links,
                ratings,
                movies
            RESTART IDENTITY CASCADE
        """))

    print("  Tablas vaciadas")


# =====================================================
# Películas + géneros
# =====================================================

def load_movies(engine, data_dir):
    print("\n[1] Cargando películas y géneros...")

    filepath = os.path.join(data_dir, "movies_clean.csv")
    _check_file(filepath)

    df = pd.read_csv(filepath)

    print(f"  Películas CSV: {len(df):,}")

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT genre_id, name FROM genres")
        ).fetchall()

    genre_map = {row.name: row.genre_id for row in rows}

    # ---------------- movies ----------------

    movies_records = [
        {
            "movie_id": int(row["movieId"]),
            "title": str(row["title"])
        }
        for _, row in df.iterrows()
    ]

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO movies (movie_id, title)
            VALUES (:movie_id, :title)
            ON CONFLICT (movie_id) DO NOTHING
        """), movies_records)

    # ---------------- movie_genres ----------------

    mg_records = []

    for _, row in df.iterrows():

        genres_raw = row["genres"]

        if isinstance(genres_raw, str) and genres_raw not in ("[]", ""):
            try:
                genres_list = ast.literal_eval(genres_raw)
            except Exception:
                genres_list = []
        else:
            genres_list = []

        for genre_name in genres_list:
            if genre_name in genre_map:
                mg_records.append({
                    "movie_id": int(row["movieId"]),
                    "genre_id": genre_map[genre_name]
                })

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO movie_genres (movie_id, genre_id)
            VALUES (:movie_id, :genre_id)
            ON CONFLICT DO NOTHING
        """), mg_records)

    print(f"  Géneros relacionados: {len(mg_records):,}")


# =====================================================
# Links
# =====================================================

def load_links(engine, data_dir):
    print("\n[2] Cargando links...")

    filepath = os.path.join(data_dir, "links_clean.csv")
    _check_file(filepath)

    df = pd.read_csv(filepath)

    print(f"  Links CSV: {len(df):,}")

    records = []

    for _, row in df.iterrows():

        tmdb_id = None if pd.isna(row["tmdbId"]) else int(row["tmdbId"])
        imdb_id = None if pd.isna(row["imdbId"]) else str(int(row["imdbId"]))

        records.append({
            "movie_id": int(row["movieId"]),
            "imdb_id": imdb_id,
            "tmdb_id": tmdb_id
        })

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO links (movie_id, imdb_id, tmdb_id)
            VALUES (:movie_id, :imdb_id, :tmdb_id)
            ON CONFLICT (movie_id) DO NOTHING
        """), records)

    print("  Links cargados")


# =====================================================
# Main
# =====================================================

def main():

    args = parse_args()

    if not os.path.isdir(args.data_dir):
        print("ERROR: no existe data-dir")
        sys.exit(1)

    print("CineMatch — Seed catálogo")
    print(f"  data-dir : {args.data_dir}")

    engine = get_engine()

    print("  BD       : conectada")

    with engine.connect() as conn:
        total_movies = _count(conn, "movies")

    if total_movies > 1000 and not args.truncate:
        print("⚠️ Catálogo ya cargado. Saltando seed.")
        return

    if args.truncate:
        truncate_tables(engine)

    load_movies(engine, args.data_dir)
    load_links(engine, args.data_dir)

    print("\n✔ Carga completada")
    print("✔ Ratings históricos NO cargados (innecesarios)")


if __name__ == "__main__":
    main()