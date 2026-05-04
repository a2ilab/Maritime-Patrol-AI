"""Grid to lat/lng coordinate conversion for maritime region.

WGS84 기준 0.0001도(약 11m) 셀 크기로 격자 생성.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

Position: TypeAlias = tuple[int, int]
LatLng: TypeAlias = tuple[float, float]

# WGS84 격자 셀 크기 (도)
CELL_SIZE_DEG: float = 0.0001

# 격자 최대 차원 (성능 제한, 초과 시 cell_size 확대)
MAX_GRID_DIM: int = 100

# 기본 영역 (35.97530,126.5657)-(36.0528187,126.1917131)
DEFAULT_LAT_MIN: float = 35.97530
DEFAULT_LAT_MAX: float = 36.0528187
DEFAULT_LNG_MIN: float = 126.1917131
DEFAULT_LNG_MAX: float = 126.5657


@dataclass(frozen=True)
class BoundingBox:
    """해역 경계 상자."""

    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float

    @classmethod
    def default(cls) -> BoundingBox:
        """기본 해역 경계."""
        return cls(
            lat_min=DEFAULT_LAT_MIN,
            lat_max=DEFAULT_LAT_MAX,
            lng_min=DEFAULT_LNG_MIN,
            lng_max=DEFAULT_LNG_MAX,
        )


@dataclass
class GridSpec:
    """0.0001도 기준 격자 스펙."""

    rows: int
    cols: int
    bbox: BoundingBox
    cell_size_deg: float


def polygon_to_bbox(points: list[dict]) -> BoundingBox:
    """Polygon 좌표 리스트 → BoundingBox."""
    if not points or len(points) < 2:
        return BoundingBox.default()
    lats = [p["lat"] for p in points]
    lngs = [p["lng"] for p in points]
    return BoundingBox(
        lat_min=min(lats),
        lat_max=max(lats),
        lng_min=min(lngs),
        lng_max=max(lngs),
    )


def create_grid_from_bbox(bbox: BoundingBox) -> GridSpec:
    """BoundingBox로 0.0001도 기준 격자 생성.

    영역이 크면 cell_size를 확대해 MAX_GRID_DIM 이하로 제한.
    """
    lat_span = bbox.lat_max - bbox.lat_min
    lng_span = bbox.lng_max - bbox.lng_min
    if lat_span <= 0 or lng_span <= 0:
        return GridSpec(rows=10, cols=10, bbox=BoundingBox.default(), cell_size_deg=CELL_SIZE_DEG)

    cell_size = CELL_SIZE_DEG
    rows = max(1, round(lat_span / cell_size))
    cols = max(1, round(lng_span / cell_size))

    if rows > MAX_GRID_DIM or cols > MAX_GRID_DIM:
        scale = max(rows / MAX_GRID_DIM, cols / MAX_GRID_DIM)
        cell_size = cell_size * scale
        rows = max(1, round(lat_span / cell_size))
        cols = max(1, round(lng_span / cell_size))

    return GridSpec(rows=rows, cols=cols, bbox=bbox, cell_size_deg=cell_size)


def grid_to_latlng(
    row: int,
    col: int,
    spec: GridSpec,
) -> LatLng:
    """격자 좌표 → 위도·경도.

    row 0=북, col 0=동(항구), col 증가=서(바다).
    """
    box = spec.bbox
    lat = box.lat_max - (row + 0.5) * (box.lat_max - box.lat_min) / spec.rows
    lng = box.lng_max - (col + 0.5) * (box.lng_max - box.lng_min) / spec.cols
    return (round(lat, 5), round(lng, 5))


def latlng_to_grid(lat: float, lng: float, spec: GridSpec) -> tuple[int, int]:
    """위도·경도 → 격자 (row, col)."""
    box = spec.bbox
    row = int((box.lat_max - lat) * spec.rows / (box.lat_max - box.lat_min) - 0.5)
    col = int((box.lng_max - lng) * spec.cols / (box.lng_max - box.lng_min) - 0.5)
    row = max(0, min(spec.rows - 1, row))
    col = max(0, min(spec.cols - 1, col))
    return (row, col)


def _point_in_polygon(lat: float, lng: float, polygon: list[dict]) -> bool:
    """Ray-casting point-in-polygon test. polygon: [{lat, lng}, ...]."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]["lat"], polygon[i]["lng"]
        yj, xj = polygon[j]["lat"], polygon[j]["lng"]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def create_polygon_mask(
    spec: GridSpec,
    polygon: list[dict],
) -> list[list[bool]]:
    """격자 셀 중심이 polygon 내부에 있는지 여부. mask[row][col] = True면 내부."""
    box = spec.bbox
    mask: list[list[bool]] = []
    for row in range(spec.rows):
        row_mask: list[bool] = []
        lat = box.lat_max - (row + 0.5) * (box.lat_max - box.lat_min) / spec.rows
        for col in range(spec.cols):
            lng = box.lng_max - (col + 0.5) * (box.lng_max - box.lng_min) / spec.cols
            row_mask.append(_point_in_polygon(lat, lng, polygon))
        mask.append(row_mask)
    return mask


def path_to_latlng_path(path: list[Position], spec: GridSpec) -> list[dict[str, float]]:
    """격자 경로 → lat/lng 리스트."""
    return [
        {"lat": lat, "lng": lng}
        for (row, col) in path
        for lat, lng in [grid_to_latlng(row, col, spec)]
    ]
