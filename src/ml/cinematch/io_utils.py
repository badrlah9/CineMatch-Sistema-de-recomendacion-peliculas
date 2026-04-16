from __future__ import annotations

"""
Utilidades pequeñas de entrada / salida.

Separarlas aquí deja los módulos de recomendación más limpios y
más fáciles de entender.
"""

import json
import pickle
from pathlib import Path
from typing import Any

import pandas as pd


def ensure_file_exists(path: Path) -> Path:
    """
    Valida que un fichero exista antes de usarlo.
    """
    if not path.exists():
        raise FileNotFoundError(f"No existe el fichero requerido: {path}")
    return path


def load_table(path: Path) -> pd.DataFrame:
    """
    Carga CSV o Parquet a DataFrame.
    """
    path = ensure_file_exists(path)

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)

    raise ValueError(
        f"Formato no soportado para {path.name}. Solo CSV o Parquet."
    )


def save_json(path: Path, data: Any) -> None:
    """
    Guarda JSON creando la carpeta destino si hace falta.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def load_json(path: Path) -> Any:
    """
    Carga un JSON desde disco.
    """
    path = ensure_file_exists(path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_pickle(path: Path, data: Any) -> None:
    """
    Guarda un objeto pickle creando la carpeta si hace falta.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        pickle.dump(data, file)


def load_pickle(path: Path) -> Any:
    """
    Carga un objeto pickle desde disco.
    """
    path = ensure_file_exists(path)
    with path.open("rb") as file:
        return pickle.load(file)
