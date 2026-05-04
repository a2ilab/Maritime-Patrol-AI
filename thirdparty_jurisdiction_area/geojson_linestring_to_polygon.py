"""
LineString GeoJSON을 Polygon으로 변환합니다.
- 이미 닫힌 링(시점≈종점)은 그대로 외곽 링으로 사용합니다.
- 열린 선은 종점에서 시점으로 이어 닫은 뒤 Polygon으로 만듭니다.
- 기본: 모든 피처를 unary_union으로 하나의 영역으로 통합합니다.
- --per-feature: LineString별 Polygon을 나누어 유지합니다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union


def _ring_closed(coords: list[tuple], tol: float) -> bool:
    if len(coords) < 2:
        return False
    x0, y0 = coords[0][0], coords[0][1]
    x1, y1 = coords[-1][0], coords[-1][1]
    return abs(x0 - x1) <= tol and abs(y0 - y1) <= tol


def linestring_to_polygon(
    geom: LineString, *, close_tol: float, make_valid: bool
) -> Polygon:
    coords = list(geom.coords)
    if len(coords) < 3:
        raise ValueError("LineString 정점이 3개 미만이면 Polygon을 만들 수 없습니다.")
    if not _ring_closed(coords, close_tol):
        coords = coords + [coords[0]]
    poly = Polygon(coords)
    if make_valid and not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon":
        raise ValueError("유효한 Polygon을 만들지 못했습니다.")
    return poly


def any_line_to_polygon(geom, *, close_tol: float, make_valid: bool) -> Polygon:
    if isinstance(geom, LineString):
        return linestring_to_polygon(geom, close_tol=close_tol, make_valid=make_valid)
    if isinstance(geom, MultiLineString):
        merged = unary_union(geom)
        if merged.geom_type != "LineString":
            raise ValueError(f"MultiLineString 병합 결과가 LineString이 아닙니다: {merged.geom_type}")
        return linestring_to_polygon(
            merged, close_tol=close_tol, make_valid=make_valid
        )
    raise ValueError(f"지원하지 않는 유형: {geom.geom_type}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path(__file__).resolve().parent / "해경상세관할구역_군산.geojson",
        help="입력 GeoJSON",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="출력 GeoJSON (기본: 입력명_merged.geojson 또는 _polygon.geojson)",
    )
    parser.add_argument(
        "--per-feature",
        action="store_true",
        help="통합하지 않고 각 LineString을 개별 Polygon으로 둡니다.",
    )
    parser.add_argument(
        "--close-tol",
        type=float,
        default=1e-8,
        help="시점·종점이 같은 링으로 볼 각도 허용 오차(도).",
    )
    parser.add_argument(
        "--no-make-valid",
        action="store_true",
        help="buffer(0) 보정을 하지 않습니다.",
    )
    args = parser.parse_args()
    merge = not args.per_feature

    inp = args.input
    if not inp.is_file():
        print(f"입력 파일 없음: {inp}", file=sys.stderr)
        return 1

    out = args.output
    if out is None:
        stem = inp.stem
        out = inp.with_name(f"{stem}_merged.geojson" if merge else f"{stem}_polygon.geojson")

    gdf = gpd.read_file(inp)
    make_valid = not args.no_make_valid

    polys: list[Polygon] = []
    meta: list[dict] = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        poly = any_line_to_polygon(geom, close_tol=args.close_tol, make_valid=make_valid)
        polys.append(poly)
        meta.append(row.drop(labels=["geometry"]).to_dict())

    if merge:
        u = unary_union(polys)
        names = sorted(
            {
                str(m.get("dist_nm") or "")
                for m in meta
                if m.get("dist_nm") is not None and str(m.get("dist_nm")).strip()
            }
        )
        ward = next(
            (str(m.get("ward_nm")) for m in meta if m.get("ward_nm")), ""
        )
        props = {
            "ward_nm": ward,
            "n_source_features": len(polys),
            "dist_nm_merged": ";".join(names),
        }
        out_gdf = gpd.GeoDataFrame([props], geometry=[u], crs=gdf.crs)
    else:
        out_gdf = gpd.GeoDataFrame(meta, geometry=polys, crs=gdf.crs)

    out_gdf.to_file(out, driver="GeoJSON", encoding="utf-8")
    data = json.loads(out.read_text(encoding="utf-8"))
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"저장: {out.resolve()}  (피처 {len(out_gdf)}개, merge={merge})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
