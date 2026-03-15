#!/usr/bin/env python3
"""
군산해양경찰서 경비함정전용부두 순찰/경비선 탐지.

[선박 검출 알고리즘]
- 부두 중심 (PIER_LAT, PIER_LNG), 반경 PIER_RADIUS_M(미터).
- "부두 근처 AIS"가 아니라 **부두에서 출발하는** 궤적만 대상.
- 1차 스캔: 부두 반경 안에 한 번이라도 들어온 MMSI 수집 (후보 풀).
- 2차 스캔: 후보 궤적 수집 후,
  - **출발 구간**: 부두 안 → 부두 밖으로 나가는 시점(들) 탐지.
  - **출발 시 과도 기동**: 해당 구간에서 과도한 회전(COG/Heading 변화) 또는 과도한 속도(SOG) 변화가 있으면
    "부두에서 출발한 선박"으로 판단. 이 조건을 만족하는 MMSI만 최종 후보로 남김.
- 정박 비율·왕복 여부는 참고용으로 유지.
"""

from __future__ import annotations

import csv
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

# Dynamic 파일 이름 규칙: Dynamic_(DATE).csv, DATE = YYYYMMDD (8자리)
DYNAMIC_FILE_PATTERN = re.compile(r"^Dynamic_(\d{8})\.csv$")

# 군산해양경찰서 경비함정전용부두 (대략 중심). 반경을 줄이면 해경정·순찰선 위주로 걸림.
PIER_LAT = 35.974577
PIER_LNG = 126.566007
PIER_RADIUS_M = 500.0  # 부두 실제 정박 구역에 맞춤 (필요 시 150~250 조정)

# 출발 시 과도 기동 판정 (부두 이탈 직전·직후 구간)
DEPARTURE_WINDOW_BEFORE = 2   # 이탈 시점 이전 포인트 수
DEPARTURE_WINDOW_AFTER = 6    # 이탈 시점 이후 포인트 수
MIN_HEADING_CHANGE_DEG = 20.0   # 연속 두 포인트 간 최소 회전(도), 이하면 회전 미탐지
MIN_SOG_CHANGE_KN = 1.2        # 연속 두 포인트 간 최소 속도 변화(kn), 이하면 속도변화 미탐지
# AIS 무효값
COG_HEADING_INVALID = 511
COG_HEADING_INVALID_360 = 360


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 간 거리(미터)."""
    r = 6_371_000  # Earth radius meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def is_near_pier(lat: float, lon: float, radius_m: float = PIER_RADIUS_M) -> bool:
    return haversine_m(PIER_LAT, PIER_LNG, lat, lon) <= radius_m


def _parse_angle(s: str) -> float | None:
    """COG/Heading 파싱. 511, 360, 빈값은 None."""
    if not s or not s.strip():
        return None
    try:
        v = float(s.strip())
        if v == COG_HEADING_INVALID or v == COG_HEADING_INVALID_360:
            return None
        return v
    except ValueError:
        return None


def parse_dynamic_row(row: list[str]) -> tuple[int, str, float, float, float, float | None, float | None] | None:
    """MMSI, 일시, 위도, 경도, SOG, COG, Heading 반환. 파싱 실패 시 None."""
    if len(row) < 6:
        return None
    try:
        mmsi = int(row[0].strip())
        if mmsi <= 0:
            return None
        dt_str = row[1].strip()
        lat = float(row[2].strip())
        lon = float(row[3].strip())
        sog = float(row[4].strip()) if row[4].strip() else 0.0
        cog = _parse_angle(row[5]) if len(row) > 5 else None
        heading = _parse_angle(row[6]) if len(row) > 6 else None
        return (mmsi, dt_str, lat, lon, sog, cog, heading)
    except (ValueError, IndexError):
        return None


# 궤적 1포인트: (일시, 위도, 경도, SOG, COG, Heading) — COG/Heading은 None 가능
PointT = tuple[str, float, float, float, float | None, float | None]


def read_dynamic_csv(path: Path) -> list[tuple[int, str, float, float, float, float | None, float | None]]:
    """Dynamic CSV에서 (MMSI, 일시, 위도, 경도, SOG, COG, Heading) 리스트 반환. 첫 2줄 메타 스킵."""
    rows: list[tuple[int, str, float, float, float, float | None, float | None]] = []
    for encoding in ("utf-8", "cp949", "utf-8-sig"):
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                next(reader, None)  # 조회 기간
                next(reader, None)  # 조회선박 척수
                header = next(reader, None)
                if not header:
                    continue
                for row in reader:
                    parsed = parse_dynamic_row(row)
                    if parsed:
                        rows.append(parsed)
            return rows
        except UnicodeDecodeError:
            continue
    return rows


def collect_by_mmsi(
    dynamic_rows: list[tuple[int, str, float, float, float, float | None, float | None]],
) -> dict[int, list[PointT]]:
    """MMSI별 (일시, 위도, 경도, SOG, COG, Heading) 리스트 (시간순)."""
    by_mmsi: dict[int, list[PointT]] = defaultdict(list)
    for mmsi, dt_str, lat, lon, sog, cog, heading in dynamic_rows:
        by_mmsi[mmsi].append((dt_str, lat, lon, sog, cog, heading))
    for mmsi in by_mmsi:
        by_mmsi[mmsi].sort(key=lambda x: x[0])
    return dict(by_mmsi)


def normalize_angle_deg(d: float) -> float:
    """각도 차이를 -180..180 도로."""
    while d > 180:
        d -= 360
    while d < -180:
        d += 360
    return d


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 사이 방위(도, 0~360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def get_heading_at(points: list[PointT], i: int) -> float | None:
    """i번째 포인트의 방향(도). COG/Heading 우선, 없으면 이전/다음 포인트와의 bearing."""
    _, lat, lon, _, cog, heading = points[i]
    if heading is not None:
        return heading
    if cog is not None:
        return cog
    if i > 0:
        return bearing_deg(points[i - 1][1], points[i - 1][2], lat, lon)
    if i + 1 < len(points):
        return bearing_deg(lat, lon, points[i + 1][1], points[i + 1][2])
    return None


def find_departure_indices(points: list[PointT]) -> list[int]:
    """부두 안 → 밖으로 나가는 시점 인덱스 목록 (나가는 그 시점의 인덱스)."""
    if len(points) < 2:
        return []
    in_pier = [is_near_pier(p[1], p[2]) for p in points]
    out: list[int] = []
    for i in range(1, len(in_pier)):
        if in_pier[i - 1] and not in_pier[i]:
            out.append(i)
    return out


def detect_excessive_maneuver_at_departure(
    points: list[PointT],
    departure_idx: int,
    window_before: int = DEPARTURE_WINDOW_BEFORE,
    window_after: int = DEPARTURE_WINDOW_AFTER,
) -> tuple[float, float, bool]:
    """출발(이탈) 구간 전후에서 최대 회전(도)·최대 SOG 변화(kn) 계산. 과도 기동 여부 반환."""
    start = max(0, departure_idx - window_before)
    end = min(len(points), departure_idx + window_after)
    max_heading_deg = 0.0
    max_sog_kn = 0.0
    for i in range(start + 1, end):
        h1 = get_heading_at(points, i - 1)
        h2 = get_heading_at(points, i)
        if h1 is not None and h2 is not None:
            d = abs(normalize_angle_deg(h2 - h1))
            if d > max_heading_deg:
                max_heading_deg = d
        d_sog = abs(points[i][3] - points[i - 1][3])
        if d_sog > max_sog_kn:
            max_sog_kn = d_sog
    excessive = (
        max_heading_deg >= MIN_HEADING_CHANGE_DEG or max_sog_kn >= MIN_SOG_CHANGE_KN
    )
    return max_heading_deg, max_sog_kn, excessive


def has_departure_with_excessive_maneuver(points: list[PointT]) -> bool:
    """부두 이탈 구간이 하나라도 있고, 그 구간에서 과도한 회전 또는 속도 변화가 있으면 True."""
    for idx in find_departure_indices(points):
        _, _, exc = detect_excessive_maneuver_at_departure(points, idx)
        if exc:
            return True
    return False


def detect_berthed_near_pier(
    points: list[PointT],
    sog_threshold_kn: float = 1.0,
) -> tuple[int, float]:
    """부두 인근(PIER_RADIUS_M) 저속(정박) 포인트 수, 비율 반환."""
    near = [p for p in points if is_near_pier(p[1], p[2]) and p[3] < sog_threshold_kn]
    n_near = len(near)
    n_total = len(points)
    ratio = n_near / n_total if n_total else 0.0
    return n_near, ratio


def detect_round_trip(
    points: list[PointT],
) -> bool:
    """부두 출발 → 이탈 → 부두 복귀 패턴이 있으면 True."""
    if len(points) < 3:
        return False
    in_pier = [is_near_pier(p[1], p[2]) for p in points]
    left_pier = False
    for i in range(1, len(in_pier)):
        if in_pier[i - 1] and not in_pier[i]:
            left_pier = True
        if left_pier and not in_pier[i - 1] and in_pier[i]:
            return True
    return False


def _stream_dynamic_rows(path: Path):
    """Dynamic CSV를 한 행씩 yield. (MMSI, 일시, 위도, 경도, SOG, COG, Heading)."""
    for encoding in ("utf-8", "cp949", "utf-8-sig"):
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                next(reader, None)
                next(reader, None)
                next(reader, None)  # header
                for row in reader:
                    parsed = parse_dynamic_row(row)
                    if parsed:
                        yield parsed
            return
        except UnicodeDecodeError:
            continue


def _stream_dynamic_rows_with_raw(path: Path):
    """Dynamic CSV를 한 행씩 yield. 첫 항목은 (_meta, meta1, meta2, header), 이후 (mmsi, dt_str, lat, lon, sog, cog, heading, raw_row)."""
    for encoding in ("utf-8", "cp949", "utf-8-sig"):
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                meta1 = next(reader, None)
                meta2 = next(reader, None)
                header = next(reader, None)
                if not header:
                    continue
                yield ("_meta", meta1, meta2, header)
                for row in reader:
                    parsed = parse_dynamic_row(row)
                    if parsed:
                        mmsi, dt_str, lat, lon, sog, cog, heading = parsed
                        yield (mmsi, dt_str, lat, lon, sog, cog, heading, row)
            return
        except UnicodeDecodeError:
            continue


def get_dynamic_csv_files(data_dir: Path) -> list[Path]:
    """data_dir 내 Dynamic_(DATE).csv 규칙에 맞는 모든 파일을 날짜순 정렬해 반환."""
    candidates = [
        f
        for f in data_dir.glob("Dynamic_*.csv")
        if f.is_file() and DYNAMIC_FILE_PATTERN.match(f.name)
    ]
    return sorted(candidates, key=lambda p: p.name)


def _date_from_dynamic_path(path: Path) -> str | None:
    """Dynamic_YYYYMMDD.csv -> YYYYMMDD."""
    m = DYNAMIC_FILE_PATTERN.match(path.name)
    return m.group(1) if m else None


def _diagnose_no_candidates(dynamic_files: list[Path]) -> None:
    """후보 0명일 때: 해경은 AIS를 자주 끄므로 0명도 흔함. 참고용으로 가장 가까운 거리만 출력."""
    if not dynamic_files:
        return
    min_dist_m = float("inf")
    sample_lat, sample_lon = None, None
    for path in dynamic_files[:3]:
        for _mmsi, _dt, lat, lon, _sog, _cog, _heading in _stream_dynamic_rows(path):
            d = haversine_m(PIER_LAT, PIER_LNG, lat, lon)
            if d < min_dist_m:
                min_dist_m = d
                sample_lat, sample_lon = lat, lon
    print("  [진단] 후보 0명: 부두 반경 안에 AIS 기록이 없습니다.")
    print("         해경은 AIS를 끄고 다니는 경우가 많아, 0명이 나오는 것도 흔한 결과입니다.")
    print("         부두 중심: ({}, {}), 반경: {} m".format(PIER_LAT, PIER_LNG, PIER_RADIUS_M))
    if sample_lat is not None:
        print("         참고: 데이터 상 부두에서 가장 가까운 위치 약 {:.0f} m (위도 {}, 경도 {})".format(
            min_dist_m, sample_lat, sample_lon))


def find_patrol_candidates(
    data_dir: Path,
    limit_files: int | None = None,
    output_dir: Path | None = None,
) -> tuple[dict[int, dict], dict[int, list[PointT]]]:
    """Dynamic CSV들을 스캔해 부두 인근 순찰/경비선 후보 반환.
    반환: (candidates, tracks). tracks[mmsi] = 해당 MMSI 궤적(시간순).
    output_dir 지정 시 후보 선박 궤적만 candidate_Dynamic_(날짜).csv 로 저장 (Dynamic과 동일 형식).
    """
    dynamic_files = get_dynamic_csv_files(data_dir)
    if limit_files is not None:
        dynamic_files = dynamic_files[:limit_files]
    if not dynamic_files:
        return ({}, {})

    # 1) 1차 스캔: 부두 인근 한 번이라도 있는 MMSI만 수집 (후보 풀)
    candidate_mmsi: set[int] = set()
    for fi, path in enumerate(dynamic_files):
        for mmsi, _dt, lat, lon, _sog, _cog, _heading in _stream_dynamic_rows(path):
            if is_near_pier(lat, lon):
                candidate_mmsi.add(mmsi)
        if (fi + 1) % 5 == 0 or fi == 0:
            print(f"  1차 스캔 {fi + 1}/{len(dynamic_files)} 파일, 후보 MMSI 수: {len(candidate_mmsi)}")

    if not candidate_mmsi:
        _diagnose_no_candidates(dynamic_files)
        return ({}, {})

    print("  (최종 후보는 '부두 출발 + 출발 시 과도한 회전/속도 변화' 조건으로 필터링합니다)")

    # 2) 2차 스캔: 후보 궤적 수집 (COG, Heading 포함) + candidate_Dynamic_(날짜).csv 저장
    by_mmsi: dict[int, list[PointT]] = defaultdict(list)
    for fi, path in enumerate(dynamic_files):
        date_str = _date_from_dynamic_path(path)
        candidate_path = (output_dir / f"candidate_Dynamic_{date_str}.csv") if (output_dir and date_str) else None
        out_file = None
        out_writer = None
        row_count = 0
        meta1, meta2, header = None, None, None
        try:
            stream = _stream_dynamic_rows_with_raw(path)
            first = next(stream, None)
            if first is None:
                continue
            if first[0] == "_meta":
                _, meta1, meta2, header = first
            for item in stream:
                mmsi, dt_str, lat, lon, sog, cog, heading, raw_row = item
                if mmsi not in candidate_mmsi:
                    continue
                by_mmsi[mmsi].append((dt_str, lat, lon, sog, cog, heading))
                if candidate_path is not None and meta1 is not None:
                    if out_file is None:
                        out_file = open(candidate_path, "w", encoding="utf-8-sig", newline="")
                        out_file.write((",".join(meta1) if isinstance(meta1, list) else meta1) + "\n")
                        out_file.write((",".join(meta2) if isinstance(meta2, list) else meta2) + "\n")
                        out_writer = csv.writer(out_file)
                        out_writer.writerow(header)
                    out_writer.writerow(raw_row)
                    row_count += 1
        finally:
            if out_file is not None:
                out_file.close()
        if candidate_path is not None and row_count > 0:
            with open(candidate_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
            if len(lines) >= 2:
                lines[1] = "조회선박 척수 : {}\n".format(row_count)
            with open(candidate_path, "w", encoding="utf-8-sig", newline="") as f:
                f.writelines(lines)
        if (fi + 1) % 5 == 0 or fi == 0:
            print(f"  2차 스캔 {fi + 1}/{len(dynamic_files)} 파일")

    for mmsi in by_mmsi:
        by_mmsi[mmsi].sort(key=lambda x: x[0])

    # 3) 후보 필터: "부두에서 출발 + 출발 시 과도한 회전/속도 변화" 있는 MMSI만 최종 후보
    n_before_filter = len(by_mmsi)
    candidates: dict[int, dict] = {}
    for mmsi, points in by_mmsi.items():
        if not has_departure_with_excessive_maneuver(points):
            continue
        n_near, berthed_ratio = detect_berthed_near_pier(points)
        round_trip = detect_round_trip(points)
        departure_count = len(find_departure_indices(points))
        candidates[mmsi] = {
            "mmsi": mmsi,
            "point_count": len(points),
            "points_near_pier": n_near,
            "berthed_ratio_near_pier": round(berthed_ratio, 4),
            "round_trip_detected": round_trip,
            "departure_count": departure_count,
            "first_ts": points[0][0] if points else "",
            "last_ts": points[-1][0] if points else "",
        }
    if n_before_filter and len(candidates) < n_before_filter:
        print("  1차 후보 {}명 → 출발·과도기동 조건 통과 {}명".format(n_before_filter, len(candidates)))
    tracks = {mmsi: by_mmsi[mmsi] for mmsi in candidates}
    return (candidates, tracks)


def _kml_escape(s: str) -> str:
    """XML/KML 내 사용 시 특수문자 이스케이프."""
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def export_patrol_tracks_kml(
    candidates: dict[int, dict],
    tracks: dict[int, list[PointT]],
    static_info: dict[int, dict],
    out_path: Path,
) -> None:
    """최종 후보 궤적을 KML로 저장. 선박별 Placemark + LineString (lon,lat,0)."""
    ns = {"gx": "http://www.google.com/kml/ext/2.2", "kml": "http://www.opengis.net/kml/2.2"}
    ET.register_namespace("gx", ns["gx"])
    root = ET.Element("kml", attrib={"xmlns": ns["kml"]})
    doc = ET.SubElement(root, "Document")
    ET.SubElement(doc, "name").text = "순찰/경비선 후보 궤적"
    ET.SubElement(doc, "description").text = "군산해양경찰서 경비함정전용부두 출발 후보 선박 궤적"

    for mmsi in sorted(candidates.keys()):
        points = tracks.get(mmsi, [])
        if not points:
            continue
        s = static_info.get(mmsi, {})
        name = s.get("선박명", "") or str(mmsi)
        desc_parts = [
            "MMSI: {}".format(mmsi),
            "선박명: {}".format(name),
            "출발 횟수: {}".format(candidates[mmsi].get("departure_count", 0)),
            "왕복: {}".format(candidates[mmsi].get("round_trip_detected", False)),
        ]
        description = "<br />".join(_kml_escape(p) for p in desc_parts)

        pm = ET.SubElement(doc, "Placemark")
        ET.SubElement(pm, "name").text = _kml_escape("{} (MMSI {})".format(name, mmsi))
        ET.SubElement(pm, "description").text = description
        coords = " ".join("{},{},0".format(p[2], p[1]) for p in points)  # lon, lat, alt=0
        ls = ET.SubElement(pm, "LineString")
        ET.SubElement(ls, "coordinates").text = coords

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with open(out_path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False, default_namespace=None)
    return None


def load_static_for_mmsi(data_dir: Path, mmsi_set: set[int]) -> dict[int, dict]:
    """Static.csv에서 해당 MMSI들의 정적 정보 로드."""
    static_path = data_dir / "Static.csv"
    if not static_path.exists():
        return {m: {} for m in mmsi_set}
    result: dict[int, dict] = {m: {} for m in mmsi_set}
    for encoding in ("utf-8", "cp949", "utf-8-sig"):
        try:
            with open(static_path, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        mmsi = int(row.get("MMSI", "").strip())
                    except (ValueError, TypeError):
                        continue
                    if mmsi not in mmsi_set:
                        continue
                    result[mmsi] = {
                        "MMSI": mmsi,
                        "선박명": row.get("선박명", "").strip(),
                        "선종코드": row.get("선종코드", "").strip(),
                        "IMO": row.get("IMO", "").strip(),
                        "호출부호": row.get("호출부호", "").strip(),
                        "DimA": row.get("DimA", "").strip(),
                        "DimB": row.get("DimB", "").strip(),
                        "DimC": row.get("DimC", "").strip(),
                        "DimD": row.get("DimD", "").strip(),
                        "흘수": row.get("흘수", "").strip(),
                        "추정톤수": row.get("추정톤수", "").strip(),
                    }
            return result
        except UnicodeDecodeError:
            continue
    return result


def main() -> None:
    import sys
    # 입력: data/AIS/ (Dynamic_*.csv, Static.csv) | 출력: data/AIS/search_patrol/
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir.parent
    if not data_dir.exists():
        print("AIS 데이터 폴더가 없습니다:", data_dir)
        return

    limit_files: int | None = None
    if "--limit-files" in sys.argv:
        i = sys.argv.index("--limit-files")
        if i + 1 < len(sys.argv):
            limit_files = int(sys.argv[i + 1])
    if limit_files:
        print("(테스트 모드: Dynamic 파일", limit_files, "개만 사용)")

    print("군산해양경찰서 경비함정전용부두 순찰/경비선 탐지")
    print("부두 중심:", PIER_LAT, PIER_LNG, "반경", PIER_RADIUS_M, "m")
    all_dynamic = get_dynamic_csv_files(data_dir)
    print("Dynamic 파일 규칙: Dynamic_(DATE).csv, DATE=YYYYMMDD")
    print("대상 파일 수:", len(all_dynamic))
    if not all_dynamic:
        print("data/AIS/ 에 Dynamic_YYYYMMDD.csv 형식 파일이 없습니다.")
        return
    print("Dynamic CSV 스캔 중...")

    candidates, tracks = find_patrol_candidates(data_dir, limit_files=limit_files, output_dir=script_dir)
    if not candidates:
        print("조건을 만족하는 후보가 없습니다. (부두 출발 + 출발 시 과도한 회전/속도 변화)")
        return

    mmsi_set = set(candidates.keys())
    static_info = load_static_for_mmsi(data_dir, mmsi_set)

    # 결과: data/AIS/search_patrol/patrol_candidates.csv
    out_path = script_dir / "patrol_candidates.csv"
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "MMSI", "선박명", "선종코드", "IMO", "호출부호",
            "DimA", "DimB", "DimC", "DimD", "흘수", "추정톤수",
            "point_count", "points_near_pier", "berthed_ratio_near_pier",
            "departure_count", "round_trip_detected", "first_ts", "last_ts",
        ])
        for mmsi in sorted(candidates.keys()):
            c = candidates[mmsi]
            s = static_info.get(mmsi, {})
            writer.writerow([
                mmsi,
                s.get("선박명", ""),
                s.get("선종코드", ""),
                s.get("IMO", ""),
                s.get("호출부호", ""),
                s.get("DimA", ""),
                s.get("DimB", ""),
                s.get("DimC", ""),
                s.get("DimD", ""),
                s.get("흘수", ""),
                s.get("추정톤수", ""),
                c.get("point_count", 0),
                c.get("points_near_pier", 0),
                c.get("berthed_ratio_near_pier", 0),
                c.get("departure_count", 0),
                c.get("round_trip_detected", False),
                c.get("first_ts", ""),
                c.get("last_ts", ""),
            ])

    # KML 내보내기 (Google Earth 등에서 궤적 확인)
    kml_path = script_dir / "patrol_tracks.kml"
    export_patrol_tracks_kml(candidates, tracks, static_info, kml_path)
    print("후보 MMSI 수:", len(candidates))
    print("결과 저장:", out_path)
    print("KML 저장:", kml_path)
    for mmsi in sorted(candidates.keys())[:10]:
        c = candidates[mmsi]
        s = static_info.get(mmsi, {})
        name = s.get("선박명", "") or "-"
        print("  MMSI {}: {} (출발 {}회, 부두인근 {}회, 왕복={})".format(
            mmsi, name, c.get("departure_count", 0), c["points_near_pier"], c["round_trip_detected"]))


if __name__ == "__main__":
    # 전체 스캔: python search_patrol.py  (수 분 소요 가능)
    # 테스트:   python search_patrol.py --limit-files 1
    main()
