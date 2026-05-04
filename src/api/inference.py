"""추론 서비스: 학습 맵(그래프+가중치) + 시간대별 랜덤 데이터 → 순찰 필요성·경로·구역."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone

import numpy as np
from numpy.typing import NDArray

from src.api.coordinates import (
    BoundingBox,
    create_grid_from_bbox,
    create_polygon_mask,
    grid_to_latlng,
    latlng_to_grid,
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
    RoutePointWithTime,
    Summary,
    TimeSlot,
    WaypointWithTime,
)
from src.config import SEED_RANGE
from src.core.learning_map import (
    InferenceModel,
    generate_random_data,
)
from src.core.path_planner import plan_full_route
from src.core.random_gen import RandomGenerator

# 추천지점 선별 임계값: 0.75 이상
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


def _parse_iso(s: str) -> datetime:
    """ISO 8601 문자열을 datetime으로 (Z → UTC)."""
    n = s.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(n)


def _compute_slot_count(start_iso: str, end_iso: str) -> int:
    """순찰 구간을 1시간 단위로 나눈 슬롯 수. 1~4. 4시간 초과 시 4로 제한."""
    try:
        start_dt = _parse_iso(start_iso)
        end_dt = _parse_iso(end_iso)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        delta = end_dt - start_dt
        hours = max(0.0, delta.total_seconds() / 3600.0)
        if hours <= 0:
            return 1
        if hours >= 4:
            return 4
        return max(1, int(round(hours)))
    except Exception:
        return 1


def _clamp_end_time(start_iso: str, end_iso: str, max_hours: float = 4.0) -> str:
    """종료 시각을 시작 시각 + max_hours 이내로 제한."""
    try:
        start_dt = _parse_iso(start_iso)
        end_dt = _parse_iso(end_iso)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        cap = start_dt + timedelta(hours=max_hours)
        if end_dt > cap:
            end_dt = cap
        return end_dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return end_iso


def _compute_seed(request_id: str, map_seed: int | None) -> int:
    """시드 생성. map_seed 있으면 그대로, 없으면 RandomGenerator로 변동 시드."""
    if map_seed is not None:
        return map_seed
    base = int(hashlib.sha256(request_id.encode()).hexdigest()[:8], 16) % (
        SEED_RANGE[1] - SEED_RANGE[0] + 1
    )
    rng = RandomGenerator(seed_range=SEED_RANGE, base=base)
    return rng.get_seed()


def _zones_and_waypoints_from_grid(
    spec: GridSpec,
    influence_map: NDArray[np.float64],
    static_map: NDArray[np.float64],
    dynamic_map: NDArray[np.float64],
    weather_map: NDArray[np.float64],
    include_zones: bool,
    slot_seed: int = 0,
) -> tuple[list[PatrolZone], list[tuple[int, int]]]:
    """순찰 필요성 격자에서 threshold 이상 후보군 → 랜덤 2개 추천지점 선별."""
    zones: list[PatrolZone] = []
    r_min = float(np.min(influence_map))
    r_max = float(np.max(influence_map))
    r_span = max(r_max - r_min, 1e-6)
    box = spec.bbox

    candidates: list[tuple[int, int, float]] = []
    for row in range(spec.rows):
        for col in range(spec.cols):
            raw = float(influence_map[row, col])
            nec = min(1.0, max(0.0, (raw - r_min) / r_span))
            if nec >= ACCIDENT_INFLUENCE_THRESHOLD:
                candidates.append((row, col, nec))

    # 후보군에서 랜덤 2개 선택 (시드 기반으로 재현성 유지)
    rng = np.random.default_rng(slot_seed)
    if len(candidates) > 2:
        indices = rng.choice(len(candidates), size=2, replace=False)
        selected = [candidates[i] for i in indices]
    else:
        selected = list(candidates)

    for row, col, nec in selected:
        s = float(static_map[row, col])
        d = float(dynamic_map[row, col])
        w = float(weather_map[row, col])
        lat = box.lat_max - (row + 0.5) * (box.lat_max - box.lat_min) / spec.rows
        lng = box.lng_max - (col + 0.5) * (box.lng_max - box.lng_min) / spec.cols
        lat, lng = round(lat, 5), round(lng, 5)
        zid = f"Z{len(zones)+1:03d}"
        label_text = "추천지점 (최우선)" if nec >= 0.9 else "추천지점"
        acc_type = "추천지점"
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

    waypoint_rc = [(r, c) for r, c, _ in selected]
    if len(waypoint_rc) < 2 and waypoint_rc:
        waypoint_rc.append(waypoint_rc[0])
    if not waypoint_rc:
        cr, cc = spec.rows // 2, spec.cols // 2
        waypoint_rc = [(cr, cc), (cr, cc)]

    return zones, waypoint_rc


def run_inference(req: InferenceRequest) -> InferenceResponse:
    """추론 실행: Polygon 영역 내 0.0001도 격자 기반 분석."""

    # Polygon → BoundingBox → GridSpec (0.0001도 기준)
    if req.polygon and len(req.polygon) >= 2:
        points = [{"lat": p.lat, "lng": p.lng} for p in req.polygon]
        bbox = polygon_to_bbox(points)
    else:
        bbox = BoundingBox.default()

    spec = create_grid_from_bbox(bbox)

    # Polygon 마스크: bbox 안이지만 polygon 바깥인 셀은 영향도 0 처리
    polygon_points = [{"lat": p.lat, "lng": p.lng} for p in req.polygon] if req.polygon and len(req.polygon) >= 3 else None
    poly_mask: np.ndarray | None = None
    if polygon_points:
        mask_list = create_polygon_mask(spec, polygon_points)
        poly_mask = np.array(mask_list, dtype=bool)

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
            summary=Summary(routeCount=0, patrolZoneCount=0, accidentCount=0, timeSlotCount=0),
            routes=[],
            patrolZones=[],
            labels=[],
            timeSlots=[],
            routeSchedule=[],
        )

    # 순찰 종료 위치: end_position > start_position
    end_row_col: tuple[int, int] | None = None
    if req.end_position is not None:
        end_row_col = latlng_to_grid(
            req.end_position.lat, req.end_position.lng, spec
        )
    elif start_row_col is not None:
        end_row_col = start_row_col

    start_iso = req.filter.startTime.strip().replace("Z", "+00:00")
    end_iso = _clamp_end_time(req.filter.startTime, req.filter.endTime, max_hours=4.0).replace("Z", "+00:00")
    num_slots = _compute_slot_count(req.filter.startTime, end_iso)
    start_dt = _parse_iso(req.filter.startTime)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    base_seed = _compute_seed(req.requestId, req.map_seed)
    fallback_center = {
        "lat": spec.bbox.lat_min + (spec.bbox.lat_max - spec.bbox.lat_min) / 2,
        "lng": spec.bbox.lng_min + (spec.bbox.lng_max - spec.bbox.lng_min) / 2,
    }

    # 학습 맵: 저장된 모델 로드, 없으면 랜덤 생성 후 저장·재활용
    model = InferenceModel.load()
    if model is None:
        model = InferenceModel.random_from_seed(base_seed)
        model.save()

    waypoints_raw: list[dict[str, float]] = []
    waypoints_rc: list[tuple[int, int]] = []
    waypoint_slot_idx: list[int] = []
    all_patrol_zones: list[PatrolZone] = []
    slot_influence_maps: list[NDArray[np.float64]] = []
    first_influence: NDArray[np.float64] | None = None
    first_static: NDArray[np.float64] | None = None
    first_dynamic: NDArray[np.float64] | None = None
    first_weather: NDArray[np.float64] | None = None

    for i in range(num_slots):
        slot_seed = base_seed + (i + 1) * 9999
        data_grid = generate_random_data(
            spec.rows, spec.cols, model.indicators, slot_seed
        )
        influence_map, static_map, dynamic_map, weather_map = model.apply(data_grid)

        if poly_mask is not None:
            influence_map[~poly_mask] = 0.0
            static_map[~poly_mask] = 0.0
            dynamic_map[~poly_mask] = 0.0
            weather_map[~poly_mask] = 0.0

        slot_influence_maps.append(influence_map.copy())

        if first_influence is None:
            first_influence = influence_map
            first_static = static_map
            first_dynamic = dynamic_map
            first_weather = weather_map

        zones_i, waypoint_rc = _zones_and_waypoints_from_grid(
            spec, influence_map, static_map, dynamic_map, weather_map,
            req.options.includeAccidentZone,
            slot_seed=slot_seed,
        )
        for z in zones_i:
            all_patrol_zones.append(z.model_copy(update={"timeSlotIndex": i + 1}))

        if len(waypoint_rc) >= 2:
            wp0 = grid_to_latlng(waypoint_rc[0][0], waypoint_rc[0][1], spec)
            wp1 = grid_to_latlng(waypoint_rc[1][0], waypoint_rc[1][1], spec)
            waypoints_raw.append({"lat": float(wp0[0]), "lng": float(wp0[1])})
            waypoints_raw.append({"lat": float(wp1[0]), "lng": float(wp1[1])})
            waypoints_rc.extend([waypoint_rc[0], waypoint_rc[1]])
            waypoint_slot_idx.extend([i, i])
        elif len(waypoint_rc) == 1:
            wp0 = grid_to_latlng(waypoint_rc[0][0], waypoint_rc[0][1], spec)
            waypoints_raw.append({"lat": float(wp0[0]), "lng": float(wp0[1])})
            waypoints_raw.append({"lat": float(wp0[0]), "lng": float(wp0[1])})
            waypoints_rc.extend([waypoint_rc[0], waypoint_rc[0]])
            waypoint_slot_idx.extend([i, i])
        else:
            cr, cc = spec.rows // 2, spec.cols // 2
            waypoints_raw.append(fallback_center.copy())
            waypoints_raw.append(fallback_center.copy())
            waypoints_rc.extend([(cr, cc), (cr, cc)])
            waypoint_slot_idx.extend([i, i])

    end_dt = start_dt + timedelta(hours=num_slots)
    start_lat, start_lng = grid_to_latlng(start_row_col[0], start_row_col[1], spec)
    end_lat, end_lng = grid_to_latlng(end_row_col[0], end_row_col[1], spec)

    # --- Q-Learning 기반 경로 계획 ---
    ordered_wp = [start_row_col] + waypoints_rc + [end_row_col]
    wp_slots = [0] + waypoint_slot_idx + [num_slots - 1]

    ql_path_rc = plan_full_route(
        influence_maps=slot_influence_maps,
        ordered_waypoints=ordered_wp,
        waypoint_slot_indices=wp_slots,
        poly_mask=poly_mask,
    )

    ql_path_latlng = [grid_to_latlng(r, c, spec) for r, c in ql_path_rc]

    time_slots: list[TimeSlot] = []
    route_schedule: list[RoutePointWithTime] = []
    for i in range(num_slots):
        slot_start = start_dt + timedelta(hours=i)
        slot_end = slot_start + timedelta(hours=1)
        t0 = (slot_start + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
        t1 = (slot_start + timedelta(minutes=45)).isoformat().replace("+00:00", "Z")
        slot_label = i + 1
        w0 = WaypointWithTime(
            lat=waypoints_raw[2 * i]["lat"],
            lng=waypoints_raw[2 * i]["lng"],
            scheduledTime=t0,
            orderInSlot=0,
            timeSlotIndex=slot_label,
        )
        w1 = WaypointWithTime(
            lat=waypoints_raw[2 * i + 1]["lat"],
            lng=waypoints_raw[2 * i + 1]["lng"],
            scheduledTime=t1,
            orderInSlot=1,
            timeSlotIndex=slot_label,
        )
        time_slots.append(
            TimeSlot(
                startTime=slot_start.isoformat().replace("+00:00", "Z"),
                endTime=slot_end.isoformat().replace("+00:00", "Z"),
                waypoints=[w0, w1],
            )
        )
        route_schedule.append(RoutePointWithTime(lat=w0.lat, lng=w0.lng, scheduledTime=t0))
        route_schedule.append(RoutePointWithTime(lat=w1.lat, lng=w1.lng, scheduledTime=t1))

    start_time_iso = start_dt.isoformat().replace("+00:00", "Z")
    end_time_iso = end_dt.isoformat().replace("+00:00", "Z")

    # Q-Learning 경로를 시간 균등 배분하여 RoutePointWithTime 생성
    n_points = len(ql_path_latlng)
    total_seconds = num_slots * 3600.0
    full_route_schedule: list[RoutePointWithTime] = []
    for idx, (lat, lng) in enumerate(ql_path_latlng):
        frac = idx / max(1, n_points - 1)
        point_dt = start_dt + timedelta(seconds=frac * total_seconds)
        full_route_schedule.append(
            RoutePointWithTime(
                lat=float(lat),
                lng=float(lng),
                scheduledTime=point_dt.isoformat().replace("+00:00", "Z"),
            )
        )

    routes: list[Route] = []
    if req.options.includeRoute and full_route_schedule:
        routes.append(
            Route(
                routeId="R001",
                name="AI 순찰 경로 (Q-Learning)",
                path=[LatLngPoint(lat=p.lat, lng=p.lng) for p in full_route_schedule],
            )
        )

    patrol_zones = all_patrol_zones
    labels = []

    for idx, pt in enumerate(route_schedule):
        slot_idx = idx // 2
        slot_label = slot_idx + 1
        st = pt.scheduledTime
        best_i = -1
        best_d = 1e9
        for zi, z in enumerate(patrol_zones):
            d = (z.center.lat - pt.lat) ** 2 + (z.center.lng - pt.lng) ** 2
            if d < best_d:
                best_d = d
                best_i = zi
        if best_i >= 0:
            z = patrol_zones[best_i]
            patrol_zones[best_i] = z.model_copy(update={"scheduledTime": st, "timeSlotIndex": slot_label})

    grid_info: GridInfo | None = None
    if req.options.includeGrid and first_influence is not None and first_static is not None and first_dynamic is not None and first_weather is not None:
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
        mask_flat = poly_mask.flatten().tolist() if poly_mask is not None else None
        influence_flat = first_influence.flatten().tolist()
        static_flat = first_static.flatten().tolist()
        dynamic_flat = first_dynamic.flatten().tolist()
        env_flat = first_weather.flatten().tolist()
        r_min, r_max = float(np.min(first_influence)), float(np.max(first_influence))
        r_span = max(r_max - r_min, 1e-6)
        influence_flat = [
            round(min(1.0, max(0.0, (float(x) - r_min) / r_span)), 4) if (mask_flat is None or mask_flat[i]) else 0.0
            for i, x in enumerate(influence_flat)
        ]
        static_flat = [round(float(x), 4) if (mask_flat is None or mask_flat[i]) else 0.0 for i, x in enumerate(static_flat)]
        dynamic_flat = [round(float(x), 4) if (mask_flat is None or mask_flat[i]) else 0.0 for i, x in enumerate(dynamic_flat)]
        env_flat = [round(float(x), 4) if (mask_flat is None or mask_flat[i]) else 0.0 for i, x in enumerate(env_flat)]

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
            timeSlotCount=num_slots,
        ),
        routes=routes,
        patrolZones=patrol_zones,
        labels=labels,
        grid=grid_info,
        timeSlots=time_slots,
        routeSchedule=full_route_schedule,
    )
