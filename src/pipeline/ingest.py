"""
ingest.py — Pipeline de ingesta y limpieza de datos
CineMatch — Grupo E-12

Uso:
    python src/pipeline/ingest.py

Transforma los datos crudos de MovieLens 32M en datos limpios y listos
para el entrenamiento del modelo de recomendación.

Entrada  : data/raw/
Salida   : data/processed/
"""

import os
import sys
import pandas as pd

# ── Rutas ────────────────────────────────────────────────────────────────────
RAW_DIR       = "data/raw"
PROCESSED_DIR = "data/processed"

# ── Parámetros de limpieza ───────────────────────────────────────────────────
MIN_RATINGS_PELICULA = 5        # umbral mínimo de ratings por película
MAX_RATINGS_USUARIO  = 10_000   # umbral máximo de ratings por usuario
SAMPLE_SIZE          = 100_000  # tamaño del subconjunto para desarrollo
RANDOM_STATE         = 42       # semilla para reproducibilidad

# ── Archivos esperados en data/processed/ ────────────────────────────────────
ARCHIVOS_ESPERADOS = [
    "ratings_clean.csv",
    "ratings_sample.csv",
    "movies_clean.csv",
    "links_clean.csv",
    "tags_clean.csv"
]



def cargar_datos(raw_dir):
    """Carga los 4 ficheros CSV del dataset MovieLens 32M."""
    print("── 1. Cargando datos ───────────────────────────────────────")
    ratings = pd.read_csv(os.path.join(raw_dir, "ratings.csv"))
    movies  = pd.read_csv(os.path.join(raw_dir, "movies.csv"))
    links   = pd.read_csv(os.path.join(raw_dir, "links.csv"))
    tags    = pd.read_csv(os.path.join(raw_dir, "tags.csv"))

    print(f"  ratings : {ratings.shape}")
    print(f"  movies  : {movies.shape}")
    print(f"  links   : {links.shape}")
    print(f"  tags    : {tags.shape}")
    return ratings, movies, links, tags


def validar_datos(ratings, movies, links, tags):
    """Valida que no hay nulos en los campos clave."""
    print("\n── 2. Validando calidad ────────────────────────────────────")
    for nombre, df in [("ratings", ratings), ("movies", movies),
                       ("links", links), ("tags", tags)]:
        nulos = df.isnull().sum().sum()
        print(f"  {nombre:10s} → {nulos} nulos totales")


def limpiar_datos(ratings, movies, links, tags):
    """Aplica todas las transformaciones de limpieza."""
    print("\n── 3. Limpiando datos ──────────────────────────────────────")

    # 1. Eliminar tags vacíos
    tags_clean = tags.dropna(subset=["tag"])
    print(f"  Tags     : {len(tags)} → {len(tags_clean)}")

    # 2. Umbral mínimo de 5 ratings por película
    ratings_por_pelicula = ratings.groupby("movieId")["rating"].count()
    peliculas_validas    = ratings_por_pelicula[
        ratings_por_pelicula >= MIN_RATINGS_PELICULA
    ].index
    ratings_clean = ratings[ratings["movieId"].isin(peliculas_validas)]
    print(f"  Ratings (umbral película) : {len(ratings)} → {len(ratings_clean)}")

    # 3. Umbral máximo de 10.000 ratings por usuario
    ratings_por_usuario = ratings_clean.groupby("userId")["rating"].count()
    usuarios_validos    = ratings_por_usuario[
        ratings_por_usuario <= MAX_RATINGS_USUARIO
    ].index
    ratings_clean = ratings_clean[ratings_clean["userId"].isin(usuarios_validos)]
    print(f"  Ratings (umbral usuario)  : → {len(ratings_clean)}")

    # 4. Normalizar géneros de string a lista
    movies_clean = movies.copy()
    movies_clean["genres"] = movies_clean["genres"].apply(
        lambda x: x.split("|") if x != "(no genres listed)" else []
    )

    # 5. Convertir tmdbId a Int64
    links_clean = links.copy()
    links_clean["tmdbId"] = links_clean["tmdbId"].astype("Int64")

    return ratings_clean, movies_clean, links_clean, tags_clean


def submuestrear(ratings_clean):
    """Genera un subconjunto de 100k ratings para desarrollo del modelo."""
    print("\n── 4. Submuestreando ───────────────────────────────────────")
    ratings_sample = ratings_clean.sample(n=SAMPLE_SIZE, random_state=RANDOM_STATE)
    print(f"  Subconjunto : {len(ratings_sample)} ratings")
    print(f"  Usuarios    : {ratings_sample['userId'].nunique()}")
    print(f"  Películas   : {ratings_sample['movieId'].nunique()}")
    return ratings_sample


def exportar_datos(ratings_clean, ratings_sample, movies_clean,
                   links_clean, tags_clean, processed_dir):
    """Guarda los datos limpios en data/processed/."""
    print("\n── 5. Exportando datos ─────────────────────────────────────")
    os.makedirs(processed_dir, exist_ok=True)

    ratings_clean.to_csv(os.path.join(processed_dir, "ratings_clean.csv"),  index=False)
    ratings_sample.to_csv(os.path.join(processed_dir, "ratings_sample.csv"), index=False)
    movies_clean.to_csv(os.path.join(processed_dir, "movies_clean.csv"),   index=False)
    links_clean.to_csv(os.path.join(processed_dir, "links_clean.csv"),    index=False)
    tags_clean.to_csv(os.path.join(processed_dir, "tags_clean.csv"),     index=False)

    for archivo in sorted(os.listdir(processed_dir)):
        ruta    = os.path.join(processed_dir, archivo)
        tamanio = os.path.getsize(ruta) / (1024 * 1024)
        print(f"  {archivo:40s} → {tamanio:.1f} MB")


def main():
    print("═" * 55)
    print("  CineMatch — Pipeline de ingesta y limpieza")
    print("═" * 55)

    # ── Verificamos si los datos procesados ya existen ───────────────────────
    archivos_existentes = [
        f for f in ARCHIVOS_ESPERADOS
        if os.path.exists(os.path.join(PROCESSED_DIR, f))
    ]

    if len(archivos_existentes) == len(ARCHIVOS_ESPERADOS) and "--force" not in sys.argv:
        print("\n⚠️  Los datos procesados ya existen en data/processed/")
        print("   Usa --force para reprocesar de cero")
        print("═" * 55)
        return


    ratings, movies, links, tags = cargar_datos(RAW_DIR)
    validar_datos(ratings, movies, links, tags)
    ratings_clean, movies_clean, links_clean, tags_clean = limpiar_datos(
        ratings, movies, links, tags
    )
    ratings_sample = submuestrear(ratings_clean)
    exportar_datos(
        ratings_clean, ratings_sample, movies_clean,
        links_clean, tags_clean, PROCESSED_DIR
    )

    print("\n Pipeline completado")
    print("═" * 55)


if __name__ == "__main__":
    main()