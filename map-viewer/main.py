"""Map Viewer - Maritime Patrol API 테스트용 웹 서비스."""

from __future__ import annotations

import json
from pathlib import Path

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api_client import call_inference
from config import HOST, PORT

app = FastAPI(title="Maritime Patrol Map Viewer")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.middleware("http")
async def no_cache_middleware(request, call_next):
    """브라우저 캐시 방지 - 새로고침 시 항상 서버에서 최신 데이터 로드."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# 현재 지도 데이터 (Leaflet 클라이언트용)
_last_map_data: dict = {"routes": [], "patrolZones": [], "labels": []}


def _to_map_data(data: dict | None) -> dict:
    """API 응답 → 지도 표시용 데이터."""
    if not data:
        return {"routes": [], "patrolZones": [], "labels": [], "grid": None}
    grid = data.get("grid")
    if grid and isinstance(grid, dict):
        grid = grid  # pass through
    else:
        grid = None
    zones = data.get("patrolZones", data.get("accidents", []))
    return {
        "routes": data.get("routes", []),
        "patrolZones": zones,
        "labels": data.get("labels", []),
        "grid": grid,
    }


@app.get("/map-test", response_class=HTMLResponse)
async def map_test() -> HTMLResponse:
    """지도 단독 테스트 (템플릿 없이)."""
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css" crossorigin="">
    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
    <style>body{margin:0;} #map{width:100vw;height:100vh;}</style>
</head>
<body>
    <div id="map"></div>
    <script>
        var m = L.map('map').setView([36.014, 126.38], 10);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(m);
    </script>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """메인 페이지."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "strategy": "safety",
            "port": "gunsan",
            "include_route": True,
            "include_accident_zone": True,
            "include_labels": True,
            "include_grid": True,
            "include_accident_zone": True,
            "include_labels": True,
            "include_grid": True,
            "map_data": json.dumps(_last_map_data),
            "error": None,
            "summary": None,
            "request_id": None,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    strategy: str = Form("safety"),
    port: str = Form("gunsan"),
    include_route: str = Form("0"),
    include_accident_zone: str = Form("0"),
    include_labels: str = Form("0"),
    include_grid: str | None = Form(None),
) -> HTMLResponse:
    """API 호출 후 지도 생성. 기존 데이터는 항상 초기화 후 새 결과만 사용."""
    global _last_map_data
    _last_map_data = {"routes": [], "patrolZones": [], "labels": [], "grid": None}

    ctx = {
        "request": request,
        "strategy": strategy,
        "port": port if port and port.strip() else None,
        "include_route": include_route == "1",
        "include_accident_zone": include_accident_zone == "1",
        "include_labels": include_labels == "1",
        "include_grid": (include_grid == "1") if include_grid is not None else True,
        "error": None,
        "summary": None,
        "request_id": None,
    }

    try:
        data = call_inference(
            strategy=strategy,
            port=ctx["port"],
            include_route=True,
            include_accident_zone=True,
            include_labels=True,
            include_grid=True,
        )
        if not data.get("success", True):
            ctx["error"] = "시작 지점이 지정되지 않아 서비스를 실행할 수 없습니다. 순찰 출발지를 선택해 주세요."
            _last_map_data = _to_map_data(data)
        else:
            _last_map_data = _to_map_data(data)
        ctx["map_data"] = json.dumps(_last_map_data)
        ctx["summary"] = data.get("summary", {})
        ctx["request_id"] = data.get("requestId")
    except requests.ConnectionError:
        ctx["map_data"] = json.dumps(_last_map_data)
        ctx["error"] = "Maritime Patrol API에 연결할 수 없습니다. API가 http://127.0.0.1:8000 에서 실행 중인지 확인하세요."
    except requests.Timeout:
        ctx["map_data"] = json.dumps(_last_map_data)
        ctx["error"] = "API 요청 시간 초과 (학습에 1분 이상 소요될 수 있음)"
    except requests.HTTPError as e:
        ctx["map_data"] = json.dumps(_last_map_data)
        ctx["error"] = f"API 오류: {e.response.status_code} - {e.response.text[:200]}"
    except Exception as e:
        ctx["map_data"] = json.dumps(_last_map_data)
        ctx["error"] = str(e)

    return templates.TemplateResponse(request=request, name="index.html", context=ctx)


def run() -> None:
    """서버 실행."""
    import uvicorn

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )


if __name__ == "__main__":
    run()
