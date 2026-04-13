
"""
Herramientas de demo y simulación HTTP para el modelo híbrido.

Incluye dos modos:
1. Construcción de payload para tu API
2. Simulación local, muy útil en notebook o scripts de prueba
"""

from __future__ import annotations

import json
from typing import Any, Optional

import pandas as pd
import requests


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

API_URL = "http://127.0.0.1:8000/recommend"
TIMEOUT = 30

DEFAULT_CONFIG = {
    "user_id": 999999999,
    "user_preferences": {
        "Action": 5,
        "Drama": 3,
        "Comedy": 1,
    },
    "ratings": [
        {"movieId": 1, "rating": 4.0},
        {"movieId": 2, "rating": 5.0},
        {"movieId": 3, "rating": 3.0},
    ],
    "top_n": 5,
    "shortlist_size": 300,
    "recommendation_state": None,
}


# ============================================================
# CONSTRUCTOR DE PAYLOAD
# ============================================================


def build_payload(
    user_id: Optional[int] = None,
    user_preferences: Optional[dict[str, float]] = None,
    ratings: Optional[list[dict[str, Any]]] = None,
    top_n: Optional[int] = None,
    shortlist_size: Optional[int] = None,
    recommendation_state: Optional[dict] = None,
    base_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Construye el payload final mezclando una config base con overrides.
    """
    config = dict(base_config or DEFAULT_CONFIG)

    if user_id is not None:
        config["user_id"] = user_id

    if user_preferences is not None:
        config["user_preferences"] = user_preferences

    if ratings is not None:
        config["ratings"] = ratings

    if top_n is not None:
        config["top_n"] = top_n

    if shortlist_size is not None:
        config["shortlist_size"] = shortlist_size

    if recommendation_state is not None:
        config["recommendation_state"] = recommendation_state

    return config


# ============================================================
# CONVERSIÓN DE INPUTS
# ============================================================


def ratings_to_dataframe(ratings: Optional[list[dict[str, Any]]]) -> pd.DataFrame:
    """
    Convierte la lista de ratings del payload a DataFrame.
    """
    if not ratings:
        return pd.DataFrame(columns=["movieId", "rating"])

    df = pd.DataFrame(ratings)
    required = {"movieId", "rating"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Cada rating debe tener columnas {sorted(required)}. "
            f"Faltan: {sorted(missing)}"
        )

    df["movieId"] = df["movieId"].astype(int)
    df["rating"] = df["rating"].astype(float)
    return df


# ============================================================
# SIMULACIÓN LOCAL (sin levantar API)
# ============================================================


def simulate_local_request(
    hybrid,
    payload: dict[str, Any],
    *,
    show_request: bool = True,
) -> dict[str, Any]:
    """
    Simula la lógica de la API localmente usando una instancia de HybridRecommender.
    """
    if show_request:
        print("=" * 70)
        print("PAYLOAD LOCAL")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("=" * 70)

    user_ratings_df = ratings_to_dataframe(payload.get("ratings"))

    result = hybrid.recommend_payload(
        user_id=payload.get("user_id"),
        user_preferences=payload.get("user_preferences"),
        user_ratings_df=user_ratings_df,
        top_n=int(payload.get("top_n", 10)),
        shortlist_size=int(payload.get("shortlist_size", 300)),
        recommendation_state=payload.get("recommendation_state"),
        include_metadata=True,
    )

    return {
        "ok": True,
        "json": result,
        "dataframe": pd.DataFrame(result["recommendations"]),
    }


# ============================================================
# SIMULADOR HTTP REAL
# ============================================================


def simulate_http_request(
    payload: dict[str, Any],
    api_url: str = API_URL,
    timeout: int = TIMEOUT,
    show_request: bool = True,
    show_response: bool = True,
    return_dataframe: bool = True,
) -> dict[str, Any]:
    """
    Envía una petición POST al endpoint de recomendación.
    """
    headers = {"Content-Type": "application/json"}

    if show_request:
        print("=" * 70)
        print("REQUEST URL")
        print(api_url)
        print("\nREQUEST PAYLOAD")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("=" * 70)

    response = None

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )

        if show_response:
            print(f"STATUS CODE: {response.status_code}")
            print("-" * 70)

        response.raise_for_status()
        data = response.json()

        if show_response:
            print("RESPONSE JSON")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("=" * 70)

        if return_dataframe:
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict) and "recommendations" in data:
                df = pd.DataFrame(data["recommendations"])
            else:
                df = pd.DataFrame()

            return {
                "ok": True,
                "status_code": response.status_code,
                "json": data,
                "dataframe": df,
            }

        return {
            "ok": True,
            "status_code": response.status_code,
            "json": data,
        }

    except requests.exceptions.HTTPError as exc:
        error_json = None
        try:
            error_json = response.json() if response is not None else None
        except Exception:
            error_json = None

        return {
            "ok": False,
            "status_code": getattr(response, "status_code", None),
            "error": str(exc),
            "response_json": error_json,
            "response_text": getattr(response, "text", None),
        }

    except requests.exceptions.ConnectionError as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": f"ConnectionError: {exc}",
        }

    except requests.exceptions.Timeout as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": f"Timeout: {exc}",
        }

    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": str(exc),
        }
