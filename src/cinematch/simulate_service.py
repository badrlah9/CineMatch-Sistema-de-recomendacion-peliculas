from __future__ import annotations

"""
Simulador local / HTTP para probar el servicio ML.

Importante:
- el backend debería consumir la respuesta real del endpoint
- este script añade un envoltorio útil para depurar localmente
- sirve tanto para probar sin levantar FastAPI como para probar contra la API real
"""

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from cinematch.config import build_settings
from cinematch.io_utils import load_json, save_json
from cinematch.schemas import RecommendationRequest
from cinematch.service import CineMatchService


DEFAULT_API_URL = "http://127.0.0.1:8000/v1/recommendations"
DEFAULT_TIMEOUT = 30

DEFAULT_PAYLOAD: dict[str, Any] = {
    "user_id": 999002,
    "user_preferences": {
        "Sci-Fi": 5,
        "Thriller": 4,
        "Drama": 2,
    },
    "ratings": [
        {"movieId": 296, "rating": 5.0},
        {"movieId": 318, "rating": 4.5},
        {"movieId": 593, "rating": 4.0},
        {"movieId": 2571, "rating": 5.0},
    ],
    "top_n": 10,
    "shortlist_size": 300,
    "recommendation_state": None,
    "apply_rotation": True,
    "include_debug_scores": True,
}


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_pretty_json(title: str, data: Any) -> None:
    print_header(title)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def build_payload(
    payload_file: Path | None = None,
    state_file: Path | None = None,
    top_n: int | None = None,
    shortlist_size: int | None = None,
) -> dict[str, Any]:
    """
    Construye el payload final combinando:
    - payload por defecto
    - overrides opcionales desde JSON
    - recommendation_state persistido
    """
    payload = dict(DEFAULT_PAYLOAD)

    if payload_file is not None:
        file_payload = load_json(payload_file)
        if not isinstance(file_payload, dict):
            raise ValueError("El payload JSON debe ser un objeto JSON.")
        payload.update(file_payload)

    if top_n is not None:
        payload["top_n"] = int(top_n)

    if shortlist_size is not None:
        payload["shortlist_size"] = int(shortlist_size)

    if state_file is not None and state_file.exists():
        payload["recommendation_state"] = load_json(state_file)

    return payload


def simulate_local(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Ejecuta la recomendación sin levantar API.
    """
    settings = build_settings()
    service = CineMatchService(settings)
    request = RecommendationRequest(**payload)
    response = service.recommend(request)

    return {
        "ok": True,
        "mode": "local",
        "request": payload,
        "response": response.model_dump(),
        "resources": {
            "movies_path": str(settings.movies_path),
            "ratings_path": str(settings.ratings_path),
            "model_path": str(settings.model_path),
            "mappings_path": str(settings.mappings_path),
        },
    }


def simulate_http(payload: dict[str, Any], api_url: str, timeout: int) -> dict[str, Any]:
    """
    Ejecuta la recomendación llamando al endpoint FastAPI real.
    """
    if requests is None:
        raise RuntimeError(
            "La librería 'requests' no está disponible. Instálala o usa --mode local."
        )

    response = requests.post(
        api_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()

    return {
        "ok": True,
        "mode": "http",
        "request": payload,
        "response": response.json(),
        "resources": {"api_url": api_url},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulador del servicio CineMatch.")
    parser.add_argument("--mode", choices=["local", "http"], default="local")
    parser.add_argument("--payload-file", type=str, default=None)
    parser.add_argument("--state-file", type=str, default="recommendation_state.json")
    parser.add_argument("--response-file", type=str, default="last_response.json")
    parser.add_argument("--no-save-state", action="store_true")
    parser.add_argument("--no-save-response", action="store_true")
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument("--shortlist-size", type=int, default=None)
    parser.add_argument("--api-url", type=str, default=DEFAULT_API_URL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    payload_file = Path(args.payload_file).resolve() if args.payload_file else None
    state_file = Path(args.state_file).resolve() if args.state_file else None
    response_file = Path(args.response_file).resolve() if args.response_file else None

    payload = build_payload(
        payload_file=payload_file,
        state_file=state_file,
        top_n=args.top_n,
        shortlist_size=args.shortlist_size,
    )

    print_pretty_json("PAYLOAD ENVIADO", payload)

    if args.mode == "local":
        result = simulate_local(payload)
    else:
        result = simulate_http(payload, api_url=args.api_url, timeout=args.timeout)

    print_pretty_json("RESPUESTA", result)

    response_payload = result.get("response", {})
    if not args.no_save_state and state_file is not None:
        recommendation_state = response_payload.get("recommendation_state")
        if recommendation_state is not None:
            save_json(state_file, recommendation_state)
            print_header("ESTADO GUARDADO")
            print(f"recommendation_state guardado en: {state_file}")

    if not args.no_save_response and response_file is not None:
        save_json(response_file, result)
        print_header("RESPUESTA GUARDADA")
        print(f"respuesta guardada en: {response_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
