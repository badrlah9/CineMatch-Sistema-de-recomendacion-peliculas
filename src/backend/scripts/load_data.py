# Carga los CSV de data/processed/ (generados por ingest.py) en PostgreSQL.
# Requiere el schema aplicado (cinematch_schema.sql) y DATABASE_URL en .env.
#
# Uso:
#   python scripts/load_data.py --data-dir /ruta/a/data/processed --sample
#   python scripts/load_data.py --data-dir /ruta/a/data/processed           # dataset completo
#   python scripts/load_data.py --data-dir /ruta/a/data/processed --truncate # recargar de cero

import ast
import os
import sys
import argparse

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

CHUNK_SIZE = 10_000   # filas por lote al insertar ratings


# Conexión

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
        print(f"ERROR: No se puede conectar a la base de datos.\n  {e}")
        sys.exit(1)


# Argumentos

def parse_args():
    p = argparse.ArgumentParser(
        description="Carga los CSV del pipeline en la base de datos CineMatch"
    )
    p.add_argument(
        "--data-dir", required=True,
        help="Ruta a la carpeta data/processed/ generada por el pipeline"
    )
    p.add_argument(
        "--sample", action="store_true",
        help="Usar ratings_sample.csv (100k filas) en vez del dataset completo"
    )
    p.add_argument(
        "--truncate", action="store_true",
        help="Vaciar las tablas antes de cargar (útil para recargar de cero)"
    )
    return p.parse_args()


# Helpers

def _check_file(path: str) -> None:
    if not os.path.isfile(path):
        print(f"ERROR: No se encuentra el fichero '{path}'")
        print("       ¿Has ejecutado el pipeline? → python src/pipeline/ingest.py")
        sys.exit(1)


def _count(conn, table: str) -> int:
    return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


# Paso 0: truncar (opcional)

def truncate_tables(engine) -> None:
    print("\n[0] Vaciando tablas...")
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE TABLE ratings, movie_genres, links, movies RESTART IDENTITY CASCADE"
        ))
    print("  Tablas vaciadas: ratings, movie_genres, links, movies")


# Paso 1: películas y géneros

def load_movies(engine, data_dir: str) -> None:
    print("\n[1] Cargando películas y géneros...")
    filepath = os.path.join(data_dir, "movies_clean.csv")
    _check_file(filepath)

    df = pd.read_csv(filepath)
    print(f"  Películas en CSV : {len(df):,}")

    # Obtener el mapa genre_name → genre_id (ya seedeado por el schema)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT genre_id, name FROM genres")).fetchall()
    genre_map: dict[str, int] = {row.name: row.genre_id for row in rows}
    print(f"  Géneros en BD    : {len(genre_map)}")

    # --- movies ---
    movies_records = [
        {"movie_id": int(row["movieId"]), "title": str(row["title"])}
        for _, row in df.iterrows()
    ]
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO movies (movie_id, title)
            VALUES (:movie_id, :title)
            ON CONFLICT (movie_id) DO NOTHING
        """), movies_records)
    print(f"  Películas insertadas (nuevas): {_count_inserted(engine, 'movies', len(movies_records))}")

    # --- movie_genres ---
    # La columna genres en movies_clean.csv está guardada como string de lista Python
    # Ej: "['Action', 'Comedy']" → ast.literal_eval → ['Action', 'Comedy']
    mg_records: list[dict] = []
    for _, row in df.iterrows():
        genres_raw = row["genres"]
        if isinstance(genres_raw, str) and genres_raw not in ("[]", ""):
            try:
                genres_list: list[str] = ast.literal_eval(genres_raw)
            except (ValueError, SyntaxError):
                genres_list = []
        else:
            genres_list = []

        for genre_name in genres_list:
            if genre_name in genre_map:
                mg_records.append({
                    "movie_id": int(row["movieId"]),
                    "genre_id": genre_map[genre_name],
                })

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO movie_genres (movie_id, genre_id)
            VALUES (:movie_id, :genre_id)
            ON CONFLICT DO NOTHING
        """), mg_records)
    print(f"  Relaciones película-género   : {len(mg_records):,}")


def _count_inserted(engine, table: str, attempted: int) -> str:
    with engine.connect() as conn:
        total = _count(conn, table)
    return f"{total:,} en BD"


# Paso 2: links

def load_links(engine, data_dir: str) -> None:
    print("\n[2] Cargando links...")
    filepath = os.path.join(data_dir, "links_clean.csv")
    _check_file(filepath)

    df = pd.read_csv(filepath)
    print(f"  Links en CSV : {len(df):,}")

    links_records = []
    for _, row in df.iterrows():
        tmdb_id = None if pd.isna(row["tmdbId"]) else int(row["tmdbId"])
        imdb_id = None if pd.isna(row["imdbId"]) else str(int(row["imdbId"]))
        links_records.append({
            "movie_id": int(row["movieId"]),
            "imdb_id":  imdb_id,
            "tmdb_id":  tmdb_id,
        })

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO links (movie_id, imdb_id, tmdb_id)
            VALUES (:movie_id, :imdb_id, :tmdb_id)
            ON CONFLICT (movie_id) DO NOTHING
        """), links_records)

    with engine.connect() as conn:
        total = _count(conn, "links")
    print(f"  Links en BD  : {total:,}")


# Paso 3: ratings

def load_ratings(engine, data_dir: str, use_sample: bool) -> None:
    filename = "ratings_sample.csv" if use_sample else "ratings_clean.csv"
    print(f"\n[3] Cargando ratings ({filename})...")
    filepath = os.path.join(data_dir, filename)
    _check_file(filepath)

    total_inserted = 0

    for chunk in pd.read_csv(filepath, chunksize=CHUNK_SIZE):
        # Convertir timestamp Unix epoch (segundos) → datetime ISO 8601 con UTC
        chunk["rated_at"] = pd.to_datetime(
            chunk["timestamp"], unit="s", utc=True
        ).dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        records = [
            {
                "user_id":  int(r.userId),
                "movie_id": int(r.movieId),
                "rating":   float(r.rating),
                "rated_at": r.rated_at,
            }
            for r in chunk.itertuples(index=False)
        ]

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO ratings (user_id, movie_id, rating, rated_at)
                VALUES (:user_id, :movie_id, :rating, :rated_at)
                ON CONFLICT (user_id, movie_id) DO NOTHING
            """), records)

        total_inserted += len(records)
        print(f"  Procesados: {total_inserted:,} ratings...", end="\r")

    print(f"  Ratings cargados: {total_inserted:,}              ")


# Main

def main() -> None:
    args = parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"ERROR: La carpeta '{args.data_dir}' no existe.")
        sys.exit(1)

    print("CineMatch — Carga de datos en PostgreSQL")
    print(f"  data-dir : {args.data_dir}")
    print(f"  modo     : {'muestra (100k ratings)' if args.sample else 'completo (~32M ratings)'}")
    print(f"  truncate : {'sí' if args.truncate else 'no'}")

    engine = get_engine()
    print("  BD       : conectada")

    if args.truncate:
        truncate_tables(engine)

    load_movies(engine, args.data_dir)
    load_links(engine, args.data_dir)
    load_ratings(engine, args.data_dir, args.sample)

    print("\nCarga completada.")


if __name__ == "__main__":
    main()
