from __future__ import annotations

"""
Conversión opcional de un checkpoint PyTorch (.pth) a Keras (.keras).

Esto es útil si quieres:
- aprovechar tu modelo ya entrenado
- migrar una sola vez a TensorFlow
- mantener predicciones muy parecidas a las actuales
"""

import argparse
from pathlib import Path

import torch
import tensorflow as tf

from cinematch.collaborative_tf import build_matrix_factorization_model
from cinematch.io_utils import save_json, save_pickle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convierte un checkpoint .pth a .keras")
    parser.add_argument("--pytorch-checkpoint", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    checkpoint_path = Path(args.pytorch_checkpoint).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

    user_to_index = checkpoint["user_to_index"]
    movie_to_index = checkpoint["movie_to_index"]
    embedding_dim = int(checkpoint["embedding_dim"])
    state_dict = checkpoint["model_state_dict"]

    model = build_matrix_factorization_model(
        num_users=len(user_to_index),
        num_movies=len(movie_to_index),
        embedding_dim=embedding_dim,
        l2_strength=0.0,
    )

    model.get_layer("user_embedding").set_weights([
        state_dict["user_embedding.weight"].detach().cpu().numpy()
    ])
    model.get_layer("movie_embedding").set_weights([
        state_dict["movie_embedding.weight"].detach().cpu().numpy()
    ])
    model.get_layer("user_bias").set_weights([
        state_dict["user_bias.weight"].detach().cpu().numpy()
    ])
    model.get_layer("movie_bias").set_weights([
        state_dict["movie_bias.weight"].detach().cpu().numpy()
    ])

    model_path = output_dir / "collaborative_model.keras"
    mappings_path = output_dir / "mappings.pkl"
    metadata_path = output_dir / "model_metadata.json"

    model.save(model_path)
    save_pickle(
        mappings_path,
        {
            "user_to_index": user_to_index,
            "movie_to_index": movie_to_index,
            "embedding_dim": embedding_dim,
        },
    )
    save_json(
        metadata_path,
        {
            "framework": "tensorflow-keras",
            "source": "legacy_pytorch_checkpoint",
            "source_checkpoint": str(checkpoint_path),
            "embedding_dim": embedding_dim,
            "num_users": len(user_to_index),
            "num_movies": len(movie_to_index),
        },
    )

    print("Conversión completada correctamente.")
    print(f"Modelo guardado en   : {model_path}")
    print(f"Mapeos guardados en  : {mappings_path}")
    print(f"Metadata guardada en : {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
