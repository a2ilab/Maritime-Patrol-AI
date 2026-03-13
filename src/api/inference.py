"""추론 서비스: 학습된 모델로 경로·사고구역·라벨 생성."""

from __future__ import annotations

import hashlib
import math

import numpy as np

from src.api.coordinates import (
    BoundingBox,
    create_grid_from_bbox,
    latlng_to_grid,
    path_to_latlng_path,
    polygon_to_bbox,
    GridSpec,
)
from src.api.schemas import (
    GridBbox,
    GridInfo,
    GridLine,
    InferenceRequest,
    InferenceResponse,
    Label,
    LatLngPoint,
    PatrolZone,
    Route,
    Summary,
)
from src.config import SEED_RANGE
from src.core.environment import MaritimePatrolEnv
from src.core.random_gen import RandomGenerator
from src.core.trainer import PatrolTrainer, RewardWeights

STRATEGY_PARAMS: dict[str, tuple[float, float, float]] = {
    "safety": (60.0, 0.15, 8.0),  # alpha↑ 순찰필요 고도 우선, beta↓ 이동 부담 감소
    "efficiency": (5.0, 1.0, 2.0),
    "surveillance": (15.0, 0.1, 15.0),  # 고영향도 탐색 강화
}

# 고위험군: 0.75 이상
ACCIDENT_INFLUENCE_THRESHOLD: float = 0.75

# WGS84: 1도 위도 ≈ 111.32km, 1도 경도 ≈ 111.32 * cos(lat) km
METERS_PER_DEG_LAT: float = 111_320.0


def _cell_radius_m(spec: GridSpec, influence: float = 1.0) -> float:
    """순찰 필요성 기반 원 반경(미터).

    최대 크기 = 셀의 좌우/상하 중 짧은 길이를 지름으로 (반지름 = 짧은 길이/2).
    75 이상만 원 표시. 75→최대의 50% 반지름, 100→최대 반지름.
    """
    box = spec.bbox
    lat_center = (box.lat_max + box.lat_min) / 2
    d_lat = (box.lat_max - box.lat_min) / spec.rows
    d_lng = (box.lng_max - box.lng_min) / spec.cols
    cell_height_m = d_lat * METERS_PER_DEG_LAT
    cell_width_m = d_lng * METERS_PER_DEG_LAT * math.cos(math.radians(lat_center))
    # 최대 반지름 = 짧은 쪽 / 2 (셀에 내접하는 원)
    max_radius = min(cell_height_m, cell_width_m) / 2
    # 75→50%, 100→100%: (influence - 0.5) / 0.5
    scale = max(0.5, min(1.0, (influence - 0.5) / 0.5))
    return max_radius * scale


def _compute_seed(request_id: str, map_seed: int | None) -> int:
    """시드 생성. map_seed 있으면 그대로, 없으면 RandomGenerator로 변동 시드."""
    if map_seed is not None:
        return map_seed
    base = int(hashlib.sha256(request_id.encode()).hexdigest()[:8], 16) % (
        SEED_RANGE[1] - SEED_RANGE[0] + 1
    )
    rng = RandomGenerator(seed_range=SEED_RANGE, base=base)
    return rng.get_seed()


def _extract_patrol_zones_and_labels(
    env: MaritimePatrolEnv,
    spec: GridSpec,
    include_zones: bool,
    include_labels: bool,
) -> tuple[list[PatrolZone], list[Label]]:
    """influence_map에서 75 이상(순찰 가능성 높은 곳)만 원으로 표시.

    원 크기: (value - 50) / 50 * 100 %. 3요소 점수(정적/동적/환경) 포함.
    """
    zones: list[PatrolZone] = []
    labels: list[Label] = []

    if not include_zones and not include_labels:
        return zones, labels

    box = spec.bbox
    influence_map = env.influence_map
    static_map = env.static_influence
    dynamic_map = env.dynamic_influence
    weather_map = env.weather_condition
    # 정규화: influence_map → 0~1
    r_min = float(np.min(influence_map))
    r_max = float(np.max(influence_map))
    r_span = max(r_max - r_min, 1e-6)

    for row in range(spec.rows):
        for col in range(spec.cols):
            raw = float(influence_map[row, col])
            # 0~1 정규화된 순찰 필요성
            nec = min(1.0, max(0.0, (raw - r_min) / r_span))
            if nec < ACCIDENT_INFLUENCE_THRESHOLD:
                continue

            s = float(static_map[row, col])
            d = float(dynamic_map[row, col])
            w = float(weather_map[row, col])

            lat = box.lat_max - (row + 0.5) * (box.lat_max - box.lat_min) / spec.rows
            lng = box.lng_max - (col + 0.5) * (box.lng_max - box.lng_min) / spec.cols
            lat, lng = round(lat, 5), round(lng, 5)

            zid = f"Z{len(zones)+1:03d}"
            label_text = "순찰필요 고도" if nec >= 0.9 else "순찰필요"
            acc_type = "고위험" if nec >= 0.75 else "위험"

            if include_zones:
                radius_m = _cell_radius_m(spec, nec)
                zones.append(
                    PatrolZone(
                        id=zid,
                        type=acc_type,
                        label=label_text,
                        center=LatLngPoint(lat=lat, lng=lng),
                        radius=radius_m,
                        count=int(nec * 20),
                        patrolNecessity=round(nec, 4),
                        staticScore=round(s, 4),
                        dynamicScore=round(d, 4),
                        environmentScore=round(w, 4),
                    )
                )
            if include_labels:
                labels.append(Label(text=label_text, lat=lat, lng=lng))

    return zones, labels


def run_inference(req: InferenceRequest) -> InferenceResponse:
    """추론 실행: Polygon 영역 내 0.0001도 격자 기반 분석."""

    # Polygon → BoundingBox → GridSpec (0.0001도 기준)
    if req.polygon and len(req.polygon) >= 2:
        points = [{"lat": p.lat, "lng": p.lng} for p in req.polygon]
        bbox = polygon_to_bbox(points)
    else:
        bbox = BoundingBox.default()

    spec = create_grid_from_bbox(bbox)

    # 순찰 시작 위치: start_position > port > 없음
    start_row_col: tuple[int, int] | None = None
    if req.start_position is not None:
        start_row_col = latlng_to_grid(
            req.start_position.lat, req.start_position.lng, spec
        )
    elif req.port == "gunsan":
        start_row_col = latlng_to_grid(35.97530, 126.5657, spec)

    if start_row_col is None:
        return InferenceResponse(
            success=False,
            requestId=req.requestId,
            summary=Summary(routeCount=0, patrolZoneCount=0, accidentCount=0),
            routes=[],
            patrolZones=[],
            labels=[],
        )

    # 순찰 종료 위치: end_position > start_position
    end_row_col: tuple[int, int] | None = None
    if req.end_position is not None:
        end_row_col = latlng_to_grid(
            req.end_position.lat, req.end_position.lng, spec
        )
    elif start_row_col is not None:
        end_row_col = start_row_col

    seed = _compute_seed(req.requestId, req.map_seed)
    alpha, beta, gamma = STRATEGY_PARAMS.get(
        req.strategy or "safety",
        STRATEGY_PARAMS["safety"],
    )
    weights = RewardWeights(alpha=alpha, beta=beta, gamma=gamma)

    trainer = PatrolTrainer(
        grid_rows=spec.rows,
        grid_cols=spec.cols,
        weights=weights,
        seed=seed,
        start_position=start_row_col,
        end_position=end_row_col,
    )
    result = trainer.train_and_get_path()

    path_latlng = path_to_latlng_path(result.path, spec)

    routes: list[Route] = []
    if req.options.includeRoute and path_latlng:
        routes.append(
            Route(
                routeId="R001",
                name="AI 순찰 경로",
                path=[LatLngPoint(lat=p["lat"], lng=p["lng"]) for p in path_latlng],
            )
        )

    patrol_zones, labels = _extract_patrol_zones_and_labels(
        result.env,
        spec,
        req.options.includeAccidentZone,
        req.options.includeLabels,
    )

    grid_info: GridInfo | None = None
    if req.options.includeGrid:
        box = spec.bbox
        lat_min, lat_max = box.lat_min, box.lat_max
        lng_min, lng_max = box.lng_min, box.lng_max
        lines: list[GridLine] = []
        for i in range(spec.rows + 1):
            lat = lat_max - i * (lat_max - lat_min) / spec.rows
            lines.append(
                GridLine(
                    start=LatLngPoint(lat=round(lat, 5), lng=lng_min),
                    end=LatLngPoint(lat=round(lat, 5), lng=lng_max),
                )
            )
        for j in range(spec.cols + 1):
            lng = lng_max - j * (lng_max - lng_min) / spec.cols
            lines.append(
                GridLine(
                    start=LatLngPoint(lat=lat_min, lng=round(lng, 5)),
                    end=LatLngPoint(lat=lat_max, lng=round(lng, 5)),
                )
            )
        influence_map = result.env.influence_map
        static_map = result.env.static_influence
        dynamic_map = result.env.dynamic_influence
        weather_map = result.env.weather_condition
        influence_flat: list[float] = []
        static_flat: list[float] = []
        dynamic_flat: list[float] = []
        env_flat: list[float] = []
        r_min, r_max = float(np.min(influence_map)), float(np.max(influence_map))
        r_span = max(r_max - r_min, 1e-6)
        for row in range(spec.rows):
            for col in range(spec.cols):
                r = float(influence_map[row, col])
                r_norm = (r - r_min) / r_span
                influence_flat.append(round(min(1.0, max(0.0, r_norm)), 4))
                static_flat.append(round(float(static_map[row, col]), 4))
                dynamic_flat.append(round(float(dynamic_map[row, col]), 4))
                env_flat.append(round(float(weather_map[row, col]), 4))

        grid_info = GridInfo(
            bbox=GridBbox(
                latMin=lat_min,
                latMax=lat_max,
                lngMin=lng_min,
                lngMax=lng_max,
            ),
            rows=spec.rows,
            cols=spec.cols,
            lines=lines,
            influence=influence_flat,
            staticInfluence=static_flat,
            dynamicInfluence=dynamic_flat,
            environmentInfluence=env_flat,
        )

    n_zones = len(patrol_zones)
    return InferenceResponse(
        success=True,
        requestId=req.requestId,
        summary=Summary(
            routeCount=len(routes),
            patrolZoneCount=n_zones,
            accidentCount=n_zones,
        ),
        routes=routes,
        patrolZones=patrol_zones,
        labels=labels,
        grid=grid_info,
    )
