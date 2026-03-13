"""FastAPI 앱: 추론 REST API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.inference import run_inference
from src.api.schemas import InferenceRequest, InferenceResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기."""
    yield


app = FastAPI(
    title="Maritime Patrol AI - Inference API",
    description="AI 기반 해양 경비순찰 경로분석 추론 API. 학습은 기존 방식 유지, 추론만 REST로 제공.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """헬스 체크."""
    return {"status": "ok", "service": "maritime-patrol-inference"}


@app.get("/health")
def health() -> dict:
    """헬스 체크."""
    return {"status": "healthy"}


@app.get("/debug-grid")
def debug_grid() -> dict:
    """격자 응답 구조 확인용 (최소 요청으로 추론 실행)."""
    from src.api.schemas import FilterRequest, InferenceRequest, LatLngPointInput, OptionsRequest

    req = InferenceRequest(
        requestId="DEBUG-001",
        filter=FilterRequest(
            startTime="2026-03-01T00:00:00Z",
            endTime="2026-03-09T23:59:59Z",
        ),
        options=OptionsRequest(
            includeRoute=False,
            includeAccidentZone=False,
            includeLabels=False,
            includeGrid=True,
        ),
        port="gunsan",
        polygon=[
            LatLngPointInput(lat=35.98, lng=126.5),
            LatLngPointInput(lat=36.0, lng=126.3),
        ],
    )
    result = run_inference(req)
    grid = result.grid
    if grid:
        d = grid.model_dump()
        return {
            "grid_keys": list(d.keys()),
            "influence_len": len(d.get("influence", [])),
            "influence_sample": d.get("influence", [])[:5],
        }
    return {"grid": None}


@app.post("/inference")
def inference(request: InferenceRequest) -> JSONResponse:
    """추론: 경로·사고구역·라벨 생성.

    입력 JSON (opinion.pptx 스펙):
    - requestId, filter, options
    - strategy, map_seed, grid_size (선택)

    출력 JSON:
    - requestId, summary, routes, accidents, labels, grid (influence 포함)
    """
    try:
        result = run_inference(request)
        content = result.model_dump(mode="json")
        # 하위 호환: accidents = patrolZones
        content["accidents"] = content.get("patrolZones", [])
        # model_dump 시 grid 필드 명시적 포함
        if result.grid is not None:
            grid_dict = content.get("grid") or {}
            grid_dict["influence"] = result.grid.influence
            grid_dict["staticInfluence"] = getattr(result.grid, "staticInfluence", [])
            grid_dict["dynamicInfluence"] = getattr(result.grid, "dynamicInfluence", [])
            grid_dict["environmentInfluence"] = getattr(result.grid, "environmentInfluence", [])
            content["grid"] = grid_dict
        return JSONResponse(content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
