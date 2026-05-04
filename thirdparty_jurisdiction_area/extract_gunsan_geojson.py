"""
해경상세관할구역 shapefile에서 속성 텍스트에 '군산'이 포함된 피처만 GeoJSON으로 추출합니다.
출력 좌표계: EPSG:4326 (GeoJSON 관례).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd


def find_detail_shapefile(directory: Path) -> Path:
    """컬럼 dist_nm이 있으면 해경상세관할구역으로 간주."""
    for shp in sorted(directory.glob("*.shp")):
        try:
            gdf = gpd.read_file(shp, rows=1)
        except Exception:
            continue
        if "dist_nm" in gdf.columns:
            return shp
    raise FileNotFoundError(
        f"'dist_nm' 컬럼이 있는 shapefile을 찾지 못했습니다: {directory}"
    )


def row_contains_needle(row: gpd.GeoSeries, needle: str) -> bool:
    for col, val in row.items():
        if col == "geometry":
            continue
        if val is None or (isinstance(val, float) and val != val):  # NaN
            continue
        if needle in str(val):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help="입력 .shp 경로 (미지정 시 폴더에서 해경상세관할구역 자동 탐색)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="출력 GeoJSON 경로 (기본: 입력 폴더/해경상세관할구역_군산.geojson)",
    )
    parser.add_argument(
        "-k",
        "--keyword",
        default="군산",
        help="속성에서 검색할 부분 문자열 (기본: 군산)",
    )
    parser.add_argument(
        "--crs-out",
        default="EPSG:4326",
        help="출력 좌표계 (기본: EPSG:4326)",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    shp_path = args.input or find_detail_shapefile(base_dir)
    out_path = args.output or (shp_path.parent / "해경상세관할구역_군산.geojson")

    gdf = gpd.read_file(shp_path)
    mask = gdf.apply(lambda r: row_contains_needle(r, args.keyword), axis=1)
    sub = gdf.loc[mask].copy()

    if sub.empty:
        print(
            f"경고: '{args.keyword}'가 포함된 레코드가 없습니다. ({shp_path.name})",
            file=sys.stderr,
        )
    else:
        print(f"선택된 피처: {len(sub)}건 (원본 {len(gdf)}건 중)")

    if sub.crs is None:
        sub = sub.set_crs("EPSG:3857")
    sub = sub.to_crs(args.crs_out)

    sub.to_file(out_path, driver="GeoJSON", encoding="utf-8")

    # 일부 환경에서 to_file GeoJSON이 ASCII 이스케이프할 수 있어 UTF-8로 재저장
    data = json.loads(out_path.read_text(encoding="utf-8"))
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"저장 완료: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
