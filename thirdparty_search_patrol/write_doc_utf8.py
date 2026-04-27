# -*- coding: utf-8 -*-
"""docs/search_patrol.md 를 UTF-8 BOM으로 저장. 인코딩 깨짐 방지."""
from pathlib import Path

CONTENT = r"""# 순찰/경비선 탐지 (search_patrol)

AIS 데이터에서 **군산해양경찰서 경비함정전용부두에서 출발하는** 궤적을 찾고, **출발 시 과도한 회전·속도 변화**가 있는 선박만 **순찰·경비선 후보**로 추출하는 도구입니다.

---

## 1. 용도

- **출발 궤적만 대상**: "부두 근처에 AIS가 있다"가 아니라 **부두에서 출발한** 궤적만 후보로 둡니다.
- **과도 기동 탐지**: 출발 시 흔히 나타나는 **과도한 회전(COG/Heading 변화)** 또는 **과도한 속도(SOG) 변화**를 탐지해, 해당 조건을 만족하는 MMSI만 최종 후보로 남깁니다.
- **MMSI·AIS 정보 추출**:
  - **Dynamic**: 궤적 포인트 수, 부두 이탈(출발) 횟수, 부두 인근 정박 비율, 왕복 여부, 첫/마지막 시각.
  - **Static**: 선박명, 선종코드, IMO, 호출부호, 선체 치수(DimA~D), 흘수, 추정톤수.

---

## 2. 사용법

### 2.1 실행 위치

스크립트는 **data/AIS/search_patrol/** 폴더에서 실행합니다. 입력 데이터(`Dynamic_*.csv`, `Static.csv`)는 상위 폴더 `data/AIS/`에 있어야 합니다.

```bash
cd data/AIS/search_patrol
python search_patrol.py
```

### 2.2 옵션

| 옵션 | 설명 |
|------|------|
| (없음) | 전체 `Dynamic_*.csv`를 스캔. 파일 수에 따라 수 분 걸릴 수 있음. |
| `--limit-files N` | 테스트용. Dynamic 파일을 **N개만** 사용 (예: `--limit-files 1`). |

**예시**

```bash
# 전체 기간 스캔
python search_patrol.py

# 1일치만 사용해 빠르게 테스트
python search_patrol.py --limit-files 1
```

### 2.3 출력

- **콘솔**: 부두 좌표·반경, 1/2차 스캔 진행, "출발·과도기동" 조건 통과 인원, 결과 파일 경로, 상위 10개 후보 요약(선박명, 출발 횟수, 부두 인근 횟수, 왕복 여부).
- **파일**
  - `data/AIS/search_patrol/patrol_candidates.csv` (UTF-8 BOM): **출발 + 과도 기동** 조건을 만족하는 후보만 포함. MMSI, Static 항목, 동적 요약(출발 횟수 등).
  - `data/AIS/search_patrol/candidate_Dynamic_(날짜).csv` (날짜=YYYYMMDD): 해당 날짜 Dynamic에서 **1차 후보(부두 근처 한 번이라도 있는 선박)** 궤적. 형식은 원본과 동일(메타 2줄 + 헤더 + MMSI,일시,위도,경도,SOG,COG,Heading). 최종 후보만 보려면 이 CSV를 `patrol_candidates.csv`의 MMSI로 필터하면 됩니다.

---

## 3. 입력 데이터

- **Dynamic_(DATE).csv**
  - 파일 이름 규칙: `Dynamic_YYYYMMDD.csv` (DATE는 8자리). 이 규칙에 맞는 **모든** 파일이 스캔 대상입니다.
  - 상단 2줄 메타(조회 기간, 조회선박 척수) 다음에 CSV 본문.
  - 컬럼: `MMSI`, `일시`, `위도`, `경도`, `SOG`, `COG`, `Heading`.
  - 인코딩: UTF-8 / CP949 / UTF-8-sig 자동 시도.

- **Static.csv**
  - 컬럼: `MMSI`, `선박명`, `선종코드`, `IMO`, `호출부호`, `DimA`~`DimD`, `흘수`, `추정톤수`.

---

## 4. 탐지 방식(알고리즘)

1. **부두 정의**
   - 중심: **PIER_LAT**, **PIER_LNG** (스크립트 상단, 기본값 군산해양경찰서).
   - 반경: **PIER_RADIUS_M** (미터). 거리는 haversine으로 계산.

2. **1차 스캔**
   - 모든 `Dynamic_*.csv`를 읽으며, **(위도, 경도)가 부두 반경 안에 한 번이라도 들어온 MMSI**를 1차 후보로 수집 (후보 풀).

3. **2차 스캔**
   - 1차 후보 MMSI에 대해서만 **(일시, 위도, 경도, SOG, COG, Heading)** 궤적을 수집·시간순 정렬.

4. **출발 구간 탐지**
   - 궤적에서 **부두 안 → 부두 밖**으로 나가는 시점(이탈 인덱스)을 찾습니다. 이탈 직전·직후 구간을 "출발 구간"으로 둡니다.

5. **과도 기동 판정 (최종 후보 필터)**
   - 이탈 시점을 포함해 **연속 30포인트** 구간을 잡습니다 (`MANEUVER_POINT_WINDOW`). 궤적 전체가 30포인트 미만이면 해당 이탈에 대해 과도 기동 판정을 하지 않습니다.
   - 그 구간에서 **인접 포인트쌍**마다 COG/Heading 변화량(절댓값, 도)을 더합니다. AIS 무효값(511 등)이면 위경도 bearing으로 보정 (`get_heading_at`).
   - **회전 조건**: 위 합계 ≥ `MANEUVER_HEADING_SUM_MIN_DEG`(기본 180°).
   - **속도 조건**: 구간 내 **min(SOG) ≤ `MANEUVER_SOG_LOW_MAX_KN`(4 kn)** 이고 **max(SOG) ≥ `MANEUVER_SOG_HIGH_MIN_KN`(8 kn)** (저속 구간과 가속 구간이 같은 창 안에 함께 있음).
   - **과도 기동**: 회전 조건 **그리고** 속도 조건을 **동시에** 만족할 때.
   - **최종 후보**: 1차 후보 중 **부두 이탈이 한 번이라도 있고, 그 이탈에 대해 위 과도 기동이 성립하는** MMSI만 남깁니다.

6. **참고 지표 (출력용)**
   - **정박 비율**: 부두 인근(PIER_RADIUS_M 이내) 이면서 SOG < 1 kn 인 포인트 수·비율.
   - **왕복 여부**: "부두 인근 → 이탈 → 다시 부두 인근" 패턴 존재 여부.
   - **출발 횟수**: 부두 안→밖 이탈 횟수 (`departure_count`).

7. **Static 연동**
   - 최종 후보 MMSI 목록으로 `Static.csv`에서 해당 행만 조인해 선박명·선종·IMO 등 정적 정보를 채웁니다.

---

## 5. 출력 CSV (patrol_candidates.csv) 컬럼

| 컬럼 | 설명 |
|------|------|
| MMSI | 선박 식별자 |
| 선박명 | Static |
| 선종코드 | Static |
| IMO | Static |
| 호출부호 | Static |
| DimA, DimB, DimC, DimD | Static (선체 치수) |
| 흘수 | Static |
| 추정톤수 | Static |
| point_count | 해당 MMSI의 Dynamic 궤적 포인트 총 개수 |
| points_near_pier | 부두 반경 이내이면서 SOG < 1kn 인 포인트 수 |
| berthed_ratio_near_pier | points_near_pier / point_count (0~1) |
| departure_count | 부두 안→밖 이탈(출발) 횟수 |
| round_trip_detected | 부두 출발 → 이탈 → 부두 복귀 패턴 존재 여부 |
| first_ts | 해당 MMSI 궤적의 첫 시각 |
| last_ts | 해당 MMSI 궤적의 마지막 시각 |

---

## 6. 파일 위치

- **스크립트**: `data/AIS/search_patrol/search_patrol.py`
- **입력 데이터**: `data/AIS/` (Dynamic_*.csv, Static.csv)
- **결과 파일**
  - `data/AIS/search_patrol/patrol_candidates.csv` (실행 시 덮어씀)
  - `data/AIS/search_patrol/candidate_Dynamic_YYYYMMDD.csv` (날짜별 1개, 1차 후보 궤적)

---

## 7. 참고

- 부두 중심·반경: 스크립트 상단 `PIER_LAT`, `PIER_LNG`, `PIER_RADIUS_M`. 과도 기동 기준: `MANEUVER_POINT_WINDOW`, `MANEUVER_HEADING_SUM_MIN_DEG`, `MANEUVER_SOG_LOW_MAX_KN`, `MANEUVER_SOG_HIGH_MIN_KN`.
- **해경은 AIS를 끄고 다니는 경우가 많아** 부두 근처 AIS 기록이 적고, **후보 0명이 나오는 것도 흔한 결과**입니다. 후보 0명일 때 `[진단]` 메시지로 "부두에서 가장 가까운 위치"만 참고용으로 확인할 수 있습니다.
- 최종 후보는 "부두에서 출발 + 출발 시 과도한 회전/속도 변화"만 통과하므로, 단순 통과선은 걸리지 않습니다. 다만 어선·민원선 등이 부두에서 기동하며 출발할 수 있으므로, `departure_count`·`round_trip_detected`·선종코드 등을 함께 보며 순찰/경비선을 가려 쓰는 것이 좋습니다.
"""

def main():
    root = Path(__file__).resolve().parent.parent.parent.parent
    out = root / "docs" / "search_patrol.md"
    out.write_text(CONTENT, encoding="utf-8-sig")
    print("Written:", out)

if __name__ == "__main__":
    main()
