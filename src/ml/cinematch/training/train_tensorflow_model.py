from __future__ import annotations

import argparse
import json
import pickle
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import tensorflow as tf


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
# Esta dataclass concentra todos los hiperparámetros y ajustes
# del entrenamiento. Así es más fácil:
# - lanzar experimentos
# - guardar metadata
# - reproducir resultados
# ============================================================

@dataclass
class TrainConfig:
    # -----------------------------
    # Rutas de entrada / salida
    # -----------------------------
    ratings_path: str = "data/processed/ratings_clean.csv"
    output_dir: str = "artifacts/tf_model"

    # -----------------------------
    # Reproducibilidad
    # -----------------------------
    seed: int = 42

    # -----------------------------
    # Hiperparámetros principales
    # -----------------------------
    batch_size: int = 8192
    embedding_dim: int = 64
    epochs: int = 30
    learning_rate: float = 1e-3
    min_learning_rate: float = 1e-5
    weight_decay: float = 1e-6
    l2_embeddings: float = 1e-6

    # -----------------------------
    # División de datos
    # -----------------------------
    val_frac: float = 0.10
    test_frac: float = 0.10

    # -----------------------------
    # Pipeline tf.data
    # -----------------------------
    shuffle_buffer: int = 500_000

    # -----------------------------
    # Filtros mínimos de actividad
    # -----------------------------
    min_user_interactions: int = 2
    min_movie_interactions: int = 2

    # -----------------------------
    # Rango esperado del rating
    # -----------------------------
    rating_min: float = 0.5
    rating_max: float = 5.0

    # -----------------------------
    # Runtime
    # -----------------------------
    use_mixed_precision: bool = False
    verbose: int = 1

    # -----------------------------
    # Control del entrenamiento
    # -----------------------------
    patience: int = 5
    min_delta: float = 0.0003
    lr_patience: int = 2


# ============================================================
# UTILIDADES DE RUNTIME
# ============================================================

def set_seed(seed: int) -> None:
    """
    Fija semillas para hacer el entrenamiento lo más reproducible posible.
    """
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def configure_runtime(use_mixed_precision: bool = False) -> None:
    """
    Configura TensorFlow para:
    - detectar GPU
    - activar memory growth
    - opcionalmente usar mixed precision

    En una RTX 4090, mixed precision suele ir muy bien.
    """
    gpus = tf.config.list_physical_devices("GPU")

    if gpus:
        print(f"GPUs detectadas: {len(gpus)}")
        for gpu in gpus:
            try:
                tf.config.experimental.set_memory_growth(gpu, True)
            except Exception as exc:
                print(f"No se pudo activar memory growth en {gpu}: {exc}")

        if use_mixed_precision:
            try:
                from tensorflow.keras import mixed_precision
                mixed_precision.set_global_policy("mixed_float16")
                print("Mixed precision activada: mixed_float16")
            except Exception as exc:
                print(f"No se pudo activar mixed precision: {exc}")
    else:
        print("No se detectó GPU. Entrenamiento en CPU.")


# ============================================================
# CARGA Y PREPARACIÓN DE DATOS
# ============================================================

def load_ratings(path: str) -> pd.DataFrame:
    """
    Carga ratings desde CSV o Parquet.

    Columnas esperadas:
    - userId
    - movieId
    - rating
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"No existe el fichero de ratings: {file_path}")

    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path, usecols=["userId", "movieId", "rating"])
    elif file_path.suffix.lower() == ".parquet":
        df = pd.read_parquet(file_path, columns=["userId", "movieId", "rating"])
    else:
        raise ValueError("El fichero de ratings debe ser CSV o Parquet.")

    required = {"userId", "movieId", "rating"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas necesarias en ratings_df: {sorted(missing)}")

    df = df.dropna(subset=["userId", "movieId", "rating"]).copy()
    df["userId"] = df["userId"].astype(np.int64)
    df["movieId"] = df["movieId"].astype(np.int64)
    df["rating"] = df["rating"].astype(np.float32)

    return df


def filter_sparse_entities(
    df: pd.DataFrame,
    min_user_interactions: int,
    min_movie_interactions: int,
) -> pd.DataFrame:
    """
    Filtra usuarios y películas con muy pocas interacciones.

    Esto ayuda a:
    - reducir ruido
    - evitar ejemplos extremos muy poco informativos
    - estabilizar algo el entrenamiento
    """
    result = df.copy()

    if min_user_interactions > 1:
        user_counts = result["userId"].value_counts()
        valid_users = user_counts[user_counts >= min_user_interactions].index
        result = result[result["userId"].isin(valid_users)]

    if min_movie_interactions > 1:
        movie_counts = result["movieId"].value_counts()
        valid_movies = movie_counts[movie_counts >= min_movie_interactions].index
        result = result[result["movieId"].isin(valid_movies)]

    return result.reset_index(drop=True)


def split_ratings(
    df: pd.DataFrame,
    val_frac: float,
    test_frac: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Divide el dataset en train / val / test.

    Además, filtra validación y test para que no contengan usuarios o películas
    que no aparezcan en train. Esto evita problemas al mapear IDs.
    """
    if val_frac < 0 or test_frac < 0 or (val_frac + test_frac) >= 1.0:
        raise ValueError("val_frac + test_frac debe ser < 1.0")

    shuffled = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    n_total = len(shuffled)
    n_test = int(n_total * test_frac)
    n_val = int(n_total * val_frac)

    test_df = shuffled.iloc[:n_test].copy()
    val_df = shuffled.iloc[n_test:n_test + n_val].copy()
    train_df = shuffled.iloc[n_test + n_val:].copy()

    # Evitamos usuarios y películas desconocidos fuera de train.
    train_users = set(train_df["userId"].unique())
    train_movies = set(train_df["movieId"].unique())

    val_df = val_df[
        val_df["userId"].isin(train_users) &
        val_df["movieId"].isin(train_movies)
    ].copy()

    test_df = test_df[
        test_df["userId"].isin(train_users) &
        test_df["movieId"].isin(train_movies)
    ].copy()

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def build_index_mapping(values: pd.Series) -> dict[int, int]:
    """
    Convierte IDs originales a índices consecutivos [0..N-1].

    Esto es necesario porque las capas Embedding esperan índices densos.
    """
    uniques = pd.Index(values.unique()).sort_values()
    return {int(original): int(idx) for idx, original in enumerate(uniques)}


def encode_ratings(
    df: pd.DataFrame,
    user_to_index: dict[int, int],
    movie_to_index: dict[int, int],
    rating_min: float,
    rating_max: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convierte un dataframe de ratings a arrays numpy listos para TensorFlow:
    - users: índices de usuario
    - movies: índices de película
    - ratings: target
    """
    encoded = df.copy()

    encoded = encoded[
        encoded["userId"].isin(user_to_index) &
        encoded["movieId"].isin(movie_to_index)
    ].copy()

    users = encoded["userId"].map(user_to_index).astype(np.int32).to_numpy()
    movies = encoded["movieId"].map(movie_to_index).astype(np.int32).to_numpy()
    ratings = encoded["rating"].clip(rating_min, rating_max).astype(np.float32).to_numpy()

    return users, movies, ratings


def make_tf_dataset(
    users: np.ndarray,
    movies: np.ndarray,
    ratings: np.ndarray,
    batch_size: int,
    shuffle: bool,
    shuffle_buffer: int,
) -> tf.data.Dataset:
    """
    Construye un tf.data.Dataset eficiente.

    - En train: shuffle + batch + prefetch
    - En val/test: batch + prefetch
    """
    ds = tf.data.Dataset.from_tensor_slices(((users, movies), ratings))

    if shuffle:
        effective_buffer = min(len(users), shuffle_buffer)
        ds = ds.shuffle(
            buffer_size=max(effective_buffer, batch_size * 4),
            seed=42,
            reshuffle_each_iteration=True,
        )

    ds = ds.batch(batch_size, drop_remainder=False)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    return ds


# ============================================================
# MODELO DE FACTORIZACIÓN MATRICIAL
# ============================================================
# Este modelo aprende:
# - embedding de usuario
# - embedding de película
# - bias de usuario
# - bias de película
#
# Predicción aproximada:
#   rating ≈ media_global + dot(user_vec, movie_vec) + user_bias + movie_bias
#
# Además, implementa get_config / from_config para que Keras pueda guardarlo
# correctamente como .keras.
# ============================================================

@tf.keras.utils.register_keras_serializable(package="CineMatch")
class MatrixFactorizationModel(tf.keras.Model):
    def __init__(
        self,
        num_users: int,
        num_movies: int,
        embedding_dim: int,
        global_mean: float,
        l2_embeddings: float = 1e-6,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        # Guardamos atributos serializables para poder salvar y recargar el modelo.
        self.num_users = int(num_users)
        self.num_movies = int(num_movies)
        self.embedding_dim = int(embedding_dim)
        self.global_mean_value = float(global_mean)
        self.l2_embeddings = float(l2_embeddings)

        reg = tf.keras.regularizers.l2(self.l2_embeddings)

        # Media global del rating en train.
        self.global_mean = tf.constant(self.global_mean_value, dtype=tf.float32)

        # Embeddings de usuario y película.
        self.user_embedding = tf.keras.layers.Embedding(
            input_dim=self.num_users,
            output_dim=self.embedding_dim,
            embeddings_initializer="he_normal",
            embeddings_regularizer=reg,
            name="user_embedding",
        )
        self.movie_embedding = tf.keras.layers.Embedding(
            input_dim=self.num_movies,
            output_dim=self.embedding_dim,
            embeddings_initializer="he_normal",
            embeddings_regularizer=reg,
            name="movie_embedding",
        )

        # Biases por usuario y por película.
        self.user_bias = tf.keras.layers.Embedding(
            input_dim=self.num_users,
            output_dim=1,
            embeddings_initializer="zeros",
            embeddings_regularizer=reg,
            name="user_bias",
        )
        self.movie_bias = tf.keras.layers.Embedding(
            input_dim=self.num_movies,
            output_dim=1,
            embeddings_initializer="zeros",
            embeddings_regularizer=reg,
            name="movie_bias",
        )

        # Operaciones auxiliares del forward.
        self.dot = tf.keras.layers.Dot(axes=1, name="dot_product")
        self.add = tf.keras.layers.Add(name="sum_scores")

    def call(self, inputs: tuple[tf.Tensor, tf.Tensor], training: bool = False) -> tf.Tensor:
        """
        Forward del modelo.

        Inputs:
        - user_ids: tensor con índices de usuario
        - movie_ids: tensor con índices de película

        Output:
        - predicción de rating
        """
        user_ids, movie_ids = inputs

        user_vec = self.user_embedding(user_ids)
        movie_vec = self.movie_embedding(movie_ids)

        user_b = self.user_bias(user_ids)
        movie_b = self.movie_bias(movie_ids)

        interaction = self.dot([user_vec, movie_vec])
        output = self.add([interaction, user_b, movie_b])

        # Convertimos a float32 por estabilidad numérica.
        output = tf.cast(output, tf.float32)
        output = tf.squeeze(output, axis=-1) + self.global_mean

        return output

    def get_config(self) -> dict:
        """
        Config necesaria para serializar el modelo custom.
        """
        config = super().get_config()
        config.update(
            {
                "num_users": self.num_users,
                "num_movies": self.num_movies,
                "embedding_dim": self.embedding_dim,
                "global_mean": self.global_mean_value,
                "l2_embeddings": self.l2_embeddings,
            }
        )
        return config

    @classmethod
    def from_config(cls, config: dict):
        """
        Reconstruye el modelo a partir de su config serializada.
        """
        return cls(**config)


# ============================================================
# CONSTRUCCIÓN Y COMPILACIÓN DEL MODELO
# ============================================================

def build_model(
    num_users: int,
    num_movies: int,
    embedding_dim: int,
    global_mean: float,
    learning_rate: float,
    weight_decay: float,
    l2_embeddings: float,
) -> tf.keras.Model:
    """
    Crea y compila el modelo.

    - Usa AdamW si está disponible
    - Si no, cae a Adam normal
    - Usa Huber loss, que suele ser más robusta que MSE puro
    """
    model = MatrixFactorizationModel(
        num_users=num_users,
        num_movies=num_movies,
        embedding_dim=embedding_dim,
        global_mean=global_mean,
        l2_embeddings=l2_embeddings,
    )

    try:
        optimizer = tf.keras.optimizers.AdamW(
            learning_rate=learning_rate,
            weight_decay=weight_decay,
        )
    except Exception:
        optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)

    model.compile(
        optimizer=optimizer,
        loss=tf.keras.losses.Huber(delta=1.0),
        metrics=[
            tf.keras.metrics.RootMeanSquaredError(name="rmse"),
            tf.keras.metrics.MeanAbsoluteError(name="mae"),
        ],
    )

    return model


# ============================================================
# UTILIDADES AUXILIARES
# ============================================================

def ensure_dir(path: str | Path) -> Path:
    """
    Crea una carpeta si no existe y devuelve el Path resultante.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_float(value: Any) -> float:
    """
    Convierte valores numéricos a float para serialización en JSON.
    """
    return float(value) if value is not None else float("nan")


# ============================================================
# PIPELINE DE ENTRENAMIENTO
# ============================================================

def train_pipeline(config: TrainConfig) -> None:
    """
    Orquestador completo del entrenamiento.

    Flujo:
    1. fija seeds y runtime
    2. carga ratings
    3. filtra sparse entities
    4. divide train / val / test
    5. indexa IDs
    6. crea datasets tf.data
    7. entrena con callbacks
    8. recarga el mejor checkpoint
    9. evalúa en test
    10. guarda modelo, mappings y metadata
    """
    set_seed(config.seed)
    configure_runtime(config.use_mixed_precision)

    print("\nCargando ratings...")
    ratings_df = load_ratings(config.ratings_path)
    print(f"Ratings cargados: {len(ratings_df):,}")

    ratings_df = filter_sparse_entities(
        ratings_df,
        min_user_interactions=config.min_user_interactions,
        min_movie_interactions=config.min_movie_interactions,
    )
    print(f"Ratings tras filtrar sparse entities: {len(ratings_df):,}")

    train_df, val_df, test_df = split_ratings(
        ratings_df,
        val_frac=config.val_frac,
        test_frac=config.test_frac,
        seed=config.seed,
    )

    print(f"Train: {len(train_df):,}")
    print(f"Val  : {len(val_df):,}")
    print(f"Test : {len(test_df):,}")

    user_to_index = build_index_mapping(train_df["userId"])
    movie_to_index = build_index_mapping(train_df["movieId"])

    num_users = len(user_to_index)
    num_movies = len(movie_to_index)
    global_mean = float(train_df["rating"].mean())

    print(f"Usuarios únicos train : {num_users:,}")
    print(f"Películas únicas train: {num_movies:,}")
    print(f"Media global train    : {global_mean:.4f}")

    # Codificación a índices densos
    x_train_user, x_train_movie, y_train = encode_ratings(
        train_df,
        user_to_index,
        movie_to_index,
        config.rating_min,
        config.rating_max,
    )
    x_val_user, x_val_movie, y_val = encode_ratings(
        val_df,
        user_to_index,
        movie_to_index,
        config.rating_min,
        config.rating_max,
    )
    x_test_user, x_test_movie, y_test = encode_ratings(
        test_df,
        user_to_index,
        movie_to_index,
        config.rating_min,
        config.rating_max,
    )

    # Datasets TensorFlow
    train_ds = make_tf_dataset(
        x_train_user,
        x_train_movie,
        y_train,
        batch_size=config.batch_size,
        shuffle=True,
        shuffle_buffer=config.shuffle_buffer,
    )
    val_ds = make_tf_dataset(
        x_val_user,
        x_val_movie,
        y_val,
        batch_size=config.batch_size,
        shuffle=False,
        shuffle_buffer=config.shuffle_buffer,
    )
    test_ds = make_tf_dataset(
        x_test_user,
        x_test_movie,
        y_test,
        batch_size=config.batch_size,
        shuffle=False,
        shuffle_buffer=config.shuffle_buffer,
    )

    # Paths de artefactos
    output_dir = ensure_dir(config.output_dir)
    best_model_path = output_dir / "best_collaborative_model.keras"
    final_model_path = output_dir / "collaborative_model.keras"
    mappings_path = output_dir / "mappings.pkl"
    metadata_path = output_dir / "model_metadata.json"
    history_csv_path = output_dir / "training_history.csv"

    # Construcción del modelo
    model = build_model(
        num_users=num_users,
        num_movies=num_movies,
        embedding_dim=config.embedding_dim,
        global_mean=global_mean,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        l2_embeddings=config.l2_embeddings,
    )

    # --------------------------------------------------------
    # Callbacks importantes:
    # - EarlyStopping: para si deja de mejorar
    # - ReduceLROnPlateau: baja LR si se estanca
    # - ModelCheckpoint: guarda el mejor modelo
    # --------------------------------------------------------
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_rmse",
            mode="min",
            patience=config.patience,
            min_delta=config.min_delta,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_rmse",
            mode="min",
            factor=0.5,
            patience=config.lr_patience,
            min_delta=config.min_delta,
            min_lr=config.min_learning_rate,
            verbose=1,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(best_model_path),
            monitor="val_rmse",
            mode="min",
            save_best_only=True,
            verbose=1,
        ),
        tf.keras.callbacks.CSVLogger(str(history_csv_path)),
        tf.keras.callbacks.TerminateOnNaN(),
    ]

    print("\nIniciando entrenamiento...")
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=config.epochs,
        callbacks=callbacks,
        verbose=config.verbose,
    )

    # Cargamos el mejor modelo guardado durante training
    print("\nCargando mejor checkpoint...")
    best_model = tf.keras.models.load_model(
        best_model_path,
        custom_objects={"MatrixFactorizationModel": MatrixFactorizationModel},
    )

    # Evaluación final en test
    print("\nEvaluando en test...")
    test_metrics = best_model.evaluate(test_ds, return_dict=True, verbose=1)

    # Guardamos también el modelo final "limpio"
    print("\nGuardando modelo final...")
    best_model.save(final_model_path)

    # Mapeos necesarios para inferencia
    mappings = {
        "user_to_index": user_to_index,
        "movie_to_index": movie_to_index,
        "global_mean": global_mean,
        "embedding_dim": config.embedding_dim,
        "rating_min": config.rating_min,
        "rating_max": config.rating_max,
        "num_users": num_users,
        "num_movies": num_movies,
    }

    with mappings_path.open("wb") as f:
        pickle.dump(mappings, f)

    # Historial serializable
    history_dict = {
        k: [float(v) for v in values]
        for k, values in history.history.items()
    }

    best_val_rmse = min(history_dict.get("val_rmse", [np.nan]))
    best_val_mae = min(history_dict.get("val_mae", [np.nan]))

    # Metadata del experimento
    metadata = {
        "config": asdict(config),
        "dataset": {
            "ratings_total": int(len(ratings_df)),
            "train_size": int(len(train_df)),
            "val_size": int(len(val_df)),
            "test_size": int(len(test_df)),
            "num_users": int(num_users),
            "num_movies": int(num_movies),
            "global_mean": float(global_mean),
        },
        "metrics": {
            "best_val_rmse": float(best_val_rmse),
            "best_val_mae": float(best_val_mae),
            "test_loss": to_float(test_metrics.get("loss")),
            "test_rmse": to_float(test_metrics.get("rmse")),
            "test_mae": to_float(test_metrics.get("mae")),
        },
        "artifacts": {
            "best_model_path": str(best_model_path.resolve()),
            "final_model_path": str(final_model_path.resolve()),
            "mappings_path": str(mappings_path.resolve()),
            "history_csv_path": str(history_csv_path.resolve()),
        },
        "history": history_dict,
    }

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("\nEntrenamiento finalizado.")
    print(f"Best val RMSE: {metadata['metrics']['best_val_rmse']:.4f}")
    print(f"Best val MAE : {metadata['metrics']['best_val_mae']:.4f}")
    print(f"Test RMSE    : {metadata['metrics']['test_rmse']:.4f}")
    print(f"Test MAE     : {metadata['metrics']['test_mae']:.4f}")
    print(f"Modelo guardado en   : {final_model_path.resolve()}")
    print(f"Mapeos guardados en  : {mappings_path.resolve()}")
    print(f"Metadata guardada en : {metadata_path.resolve()}")


# ============================================================
# CLI
# ============================================================

def parse_args() -> TrainConfig:
    """
    Parseo de argumentos por línea de comandos.
    """
    parser = argparse.ArgumentParser(
        description="Entrenamiento mejorado del modelo colaborativo en TensorFlow/Keras."
    )

    # Rutas
    parser.add_argument("--ratings-path", type=str, default="data/processed/ratings_clean.csv")
    parser.add_argument("--output-dir", type=str, default="artifacts/tf_model")

    # Hiperparámetros
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=8192)
    parser.add_argument("--embedding-dim", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--min-learning-rate", type=float, default=1e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-6)
    parser.add_argument("--l2-embeddings", type=float, default=1e-6)

    # Split
    parser.add_argument("--val-frac", type=float, default=0.10)
    parser.add_argument("--test-frac", type=float, default=0.10)

    # Dataset pipeline
    parser.add_argument("--shuffle-buffer", type=int, default=500_000)
    parser.add_argument("--min-user-interactions", type=int, default=2)
    parser.add_argument("--min-movie-interactions", type=int, default=2)

    # Rango de ratings
    parser.add_argument("--rating-min", type=float, default=0.5)
    parser.add_argument("--rating-max", type=float, default=5.0)

    # Runtime
    parser.add_argument("--use-mixed-precision", action="store_true")
    parser.add_argument("--verbose", type=int, default=1)

    # Early stopping / scheduler
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--min-delta", type=float, default=0.0003)
    parser.add_argument("--lr-patience", type=int, default=2)

    args = parser.parse_args()

    return TrainConfig(
        ratings_path=args.ratings_path,
        output_dir=args.output_dir,
        seed=args.seed,
        batch_size=args.batch_size,
        embedding_dim=args.embedding_dim,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        min_learning_rate=args.min_learning_rate,
        weight_decay=args.weight_decay,
        l2_embeddings=args.l2_embeddings,
        val_frac=args.val_frac,
        test_frac=args.test_frac,
        shuffle_buffer=args.shuffle_buffer,
        min_user_interactions=args.min_user_interactions,
        min_movie_interactions=args.min_movie_interactions,
        rating_min=args.rating_min,
        rating_max=args.rating_max,
        use_mixed_precision=args.use_mixed_precision,
        verbose=args.verbose,
        patience=args.patience,
        min_delta=args.min_delta,
        lr_patience=args.lr_patience,
    )


if __name__ == "__main__":
    config = parse_args()
    train_pipeline(config)