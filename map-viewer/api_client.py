"""Maritime Patrol API 클라이언트."""

from __future__ import annotations

import json
from pathlib import Path

import requests

from config import API_BASE_URL, API_INFERENCE_PATH

_GEOJSON_PATH = Path(__file__).resolve().parent.parent / "jurisdiction-area" / "gunsan_area.geojson"


def _load_polygon_from_geojson(path: Path = _GEOJSON_PATH) -> list[dict]:
    """GeoJSON FeatureCollection → [{lat, lng}, …] 좌표 리스트."""
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    coords = gj["features"][0]["geometry"]["coordinates"][0]
    return [{"lat": c[1], "lng": c[0]} for c in coords]


def get_default_polygon() -> list[dict]:
    """GeoJSON 파일을 디스크에서 매번 로드한다. 재시작 없이 좌표 변경 반영."""
    return _load_polygon_from_geojson()


DEFAULT_POLYGON: list[dict] = _load_polygon_from_geojson()


def call_inference(
    request_id: str = "REQ-MAP-VIEWER-001",
    start_time: str = "2026-03-01T00:00:00Z",
    end_time: str = "2026-03-01T03:59:59Z",
    polygon: list[dict] | None = None,
    port: str | None = "gunsan",
    include_route: bool = True,
    include_accident_zone: bool = True,
    include_labels: bool = True,
    include_grid: bool = True,
    map_seed: int | None = None,
) -> dict:
    """추론 API 호출.

    Returns:
        API 응답 JSON (dict).

    Raises:
        requests.RequestException: API 호출 실패 시.
    """
    url = f"{API_BASE_URL.rstrip('/')}{API_INFERENCE_PATH}"
    payload = {
        "requestId": request_id,
        "filter": {
            "startTime": start_time,
            "endTime": end_time,
            "shipId": "ALL",
            "accidentType": "ALL",
        },
        "options": {
            "includeRoute": include_route,
            "includeAccidentZone": include_accident_zone,
            "includeLabels": include_labels,
            "includeGrid": include_grid,
        },
        "polygon": polygon if polygon is not None else get_default_polygon(),
    }
    if port and str(port).strip() == "gunsan":
        payload["port"] = "gunsan"
    else:
        payload["port"] = None
    if map_seed is not None:
        payload["map_seed"] = map_seed

    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()
