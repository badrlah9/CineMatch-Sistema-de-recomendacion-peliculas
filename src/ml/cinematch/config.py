from __future__ import annotations

"""
Configuración central del servicio.

La idea es que todas las rutas importantes vivan aquí para evitar:
- imports con rutas frágiles
- rutas repetidas en varios ficheros
- problemas al mover el proyecto a Docker o a otro servidor
"""

import os
from dataclasses import dataclass
from pathlib import Path


# Si el paquete vive en `src/cinematch`, la raíz del proyecto suele estar
# dos niveles por encima del paquete (`.../src/cinematch` -> `.../`).
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ServiceSettings:
    project_root: Path
    movies_path: Path
    ratings_path: Path
    model_path: Path
    mappings_path: Path
    metadata_path: Path

    # Ajustes del recomendador
    default_top_n: int = 10
    default_shortlist_size: int = 300
    min_catalog_votes: int = 10
    min_neighbor_votes: int = 15

    # Ajustes de rotación / diversidad
    rotation_memory_decay: float = 0.80
    max_history_signatures: int = 200

    # Metadatos del servicio
    service_name: str = "CineMatch"
    model_version: str = "cinematch-hybrid-keras-external-2.0.0"


def build_settings() -> ServiceSettings:
    """
    Construye la configuración a partir de variables de entorno.

    Variables soportadas:
    - CINEMATCH_PROJECT_ROOT
    - CINEMATCH_MOVIES_PATH
    - CINEMATCH_RATINGS_PATH
    - CINEMATCH_MODEL_PATH
    - CINEMATCH_MAPPINGS_PATH
    - CINEMATCH_METADATA_PATH
    - CINEMATCH_DEFAULT_TOP_N
    - CINEMATCH_DEFAULT_SHORTLIST_SIZE
    - CINEMATCH_MIN_CATALOG_VOTES
    - CINEMATCH_MIN_NEIGHBOR_VOTES
    - CINEMATCH_ROTATION_MEMORY_DECAY
    - CINEMATCH_MAX_HISTORY_SIGNATURES
    - CINEMATCH_SERVICE_NAME
    - CINEMATCH_MODEL_VERSION
    """
    project_root = Path(
        os.getenv("CINEMATCH_PROJECT_ROOT", str(DEFAULT_PROJECT_ROOT))
    ).resolve()

    movies_path = Path(
        os.getenv(
            "CINEMATCH_MOVIES_PATH",
            str(project_root / "data" / "processed" / "movies_clean.csv"),
        )
    ).resolve()

    ratings_path = Path(
        os.getenv(
            "CINEMATCH_RATINGS_PATH",
            str(project_root / "data" / "processed" / "ratings_clean.csv"),
        )
    ).resolve()

    model_path = Path(
        os.getenv(
            "CINEMATCH_MODEL_PATH",
            str(project_root / "artifacts" / "tf_model" / "collaborative_model.keras"),
        )
    ).resolve()

    mappings_path = Path(
        os.getenv(
            "CINEMATCH_MAPPINGS_PATH",
            str(project_root / "artifacts" / "tf_model" / "mappings.pkl"),
        )
    ).resolve()

    metadata_path = Path(
        os.getenv(
            "CINEMATCH_METADATA_PATH",
            str(project_root / "artifacts" / "tf_model" / "model_metadata.json"),
        )
    ).resolve()

    return ServiceSettings(
        project_root=project_root,
        movies_path=movies_path,
        ratings_path=ratings_path,
        model_path=model_path,
        mappings_path=mappings_path,
        metadata_path=metadata_path,
        default_top_n=int(os.getenv("CINEMATCH_DEFAULT_TOP_N", "10")),
        default_shortlist_size=int(os.getenv("CINEMATCH_DEFAULT_SHORTLIST_SIZE", "300")),
        min_catalog_votes=int(os.getenv("CINEMATCH_MIN_CATALOG_VOTES", "10")),
        min_neighbor_votes=int(os.getenv("CINEMATCH_MIN_NEIGHBOR_VOTES", "15")),
        rotation_memory_decay=float(os.getenv("CINEMATCH_ROTATION_MEMORY_DECAY", "0.80")),
        max_history_signatures=int(os.getenv("CINEMATCH_MAX_HISTORY_SIGNATURES", "200")),
        service_name=os.getenv("CINEMATCH_SERVICE_NAME", "CineMatch"),
        model_version=os.getenv("CINEMATCH_MODEL_VERSION", "cinematch-hybrid-keras-external-2.0.0"),
    )
