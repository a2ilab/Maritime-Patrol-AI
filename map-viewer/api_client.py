"""Maritime Patrol API 클라이언트."""

from __future__ import annotations

import requests

from config import API_BASE_URL, API_INFERENCE_PATH

# 기본 순찰 영역 (35.97530,126.5657)-(36.0528187,126.1917131)
DEFAULT_POLYGON = [
    {"lat": 35.97530, "lng": 126.5657},
    {"lat": 36.0528187, "lng": 126.1917131},
]


def call_inference(
    request_id: str = "REQ-MAP-VIEWER-001",
    start_time: str = "2026-03-01T00:00:00Z",
    end_time: str = "2026-03-09T23:59:59Z",
    polygon: list[dict] | None = None,
    port: str | None = "gunsan",
    include_route: bool = True,
    include_accident_zone: bool = True,
    include_labels: bool = True,
    include_grid: bool = True,
    map_seed: int | None = None,
) -> dict:
    """추론 API 호출. 경로는 안전+단시간 기준으로만 생성됨(전략 옵션 없음).

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
        "polygon": polygon or DEFAULT_POLYGON,
    }
    if port and str(port).strip() == "gunsan":
        payload["port"] = "gunsan"
    else:
        payload["port"] = None  # 격자 (0,0) 기준
    if map_seed is not None:
        payload["map_seed"] = map_seed

    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()
