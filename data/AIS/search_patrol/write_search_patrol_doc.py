# -*- coding: utf-8 -*-
"""docs/search_patrol.md 를 UTF-8(BOM)으로 씀. 실행 후 이 파일은 삭제해도 됨."""
from pathlib import Path

CONTENT = r"""# 순찰/경비선 탐지 (search_patrol)

AIS 데이터에서 **군산해양경찰서 경비함정전용부두** 인근에 정박하거나 부두를 기점으로 왕복하는 **순찰·경비선 후보**를 찾고, MMSI 및 AIS Dynamic/Static 정보를 추출하는 도구입니다.

---

## 1. 용도

- **순찰·경비선 후보 식별**: 해당 부두(반경 **PIER_RADIUS_M**, 기본 200m)에 한 번이라도 위치한 선박을 후보로 수집합니다. 반경을 줄이면 해경정·순찰선 위주로 걸립니다.
- **MMSI 추출**: 후보 선박의 MMSI 목록을 냅니다.
- **AIS 정보 추출**:
  - **Dynamic**: 궤적 포인트 수, 부두 인근 저속(정박) 포인트 수·비율, 부두 출발 후 귀항(왕복) 여부, 첫/마지막 시각.
  - **Static**: 선박명, 선종코드, IMO, 호출부호, 선체 치수(DimA~D), 흘수, 추정톤수.

탐지 기준은 "군산해양경찰서 경비함정전용부두에서 순찰/경비선이 정박하거나, 그 부두에서 출발해 순찰 후 다시 부두로 돌아온다"는 가정에 맞춰져 있습니다.

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

- **콘솔**: 부두 좌표·반경, 1/2차 스캔 진행, 후보 MMSI 수, 결과 파일 경로, 상위 10개 후보 요약(선박명, 부두 인근 횟수, 왕복 여부).
- **파일**
  - `data/AIS/search_patrol/patrol_candidates.csv` (UTF-8 BOM): 후보별 MMSI, Static 항목, 동적 요약.
  - `data/AIS/search_patrol/candidate_Dynamic_(날짜).csv` (날짜=YYYYMMDD): 해당 날짜 Dynamic에서 **후보 선박만** 추출한 궤적. 형식은 원본 `Dynamic_(날짜).csv`와 동일(메타 2줄 + 헤더 + MMSI,일시,위도,경도,SOG,COG,Heading).

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
   - 반경: **PIER_RADIUS_M** (미터). 스크립트 상단에서 조정. 거리는 haversine으로 계산.

2. **1차 스캔**
   - 모든 `Dynamic_*.csv`를 읽으며, **(위도, 경도)가 부두 반경 안에 한 번이라도 들어온 MMSI**만 후보로 수집.
   - 즉 "부두 원 안에 AIS 위치가 한 번이라도 기록된 선박"만 후보. (이후 정박 비율·왕복 여부는 2차에서만 사용.)

3. **2차 스캔**
   - 1차에서 수집한 MMSI에 대해서만, Dynamic에서 해당 MMSI의 **(일시, 위도, 경도, SOG)** 궤적만 수집·시간순 정렬.

4. **지표 계산**
   - **정박 비율**
     - "부두 인근(PIER_RADIUS_M 이내)" 이면서 **SOG < 1 kn** 인 포인트만 정박으로 간주.
     - `points_near_pier`: 그런 포인트 개수.
     - `berthed_ratio_near_pier`: (해당 개수) / (해당 MMSI 전체 궤적 포인트 수).
   - **왕복 여부**
     - 궤적 상에서 "부두 인근 → 부두 이탈 → 다시 부두 인근" 순서가 한 번이라도 있으면 `round_trip_detected = True`.

5. **Static 연동**
   - 후보 MMSI 목록으로 `Static.csv`에서 해당 행만 조인해 선박명·선종·IMO 등 정적 정보를 채웁니다.

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
| round_trip_detected | 부두 출발 → 이탈 → 부두 복귀 패턴 존재 여부 |
| first_ts | 해당 MMSI 궤적의 첫 시각 |
| last_ts | 해당 MMSI 궤적의 마지막 시각 |

---

## 6. 파일 위치

- **스크립트**: `data/AIS/search_patrol/search_patrol.py`
- **입력 데이터**: `data/AIS/` (Dynamic_*.csv, Static.csv)
- **결과 파일**
  - `data/AIS/search_patrol/patrol_candidates.csv` (실행 시 덮어씀)
  - `data/AIS/search_patrol/candidate_Dynamic_YYYYMMDD.csv` (날짜별 1개, 후보 선박 궤적만)

---

## 7. 참고

- 부두 중심·반경은 스크립트 상단 `PIER_LAT`, `PIER_LNG`, `PIER_RADIUS_M`에서 조정합니다. 후보가 너무 많으면 `PIER_RADIUS_M`을 줄이세요.
- **해경은 AIS를 끄고 다니는 경우가 많아** 부두 근처 AIS 기록이 적고, "나갔다 돌아옴" 패턴도 잘 안 나옵니다. **후보 0명이 나오는 것도 흔한 결과**이며, 실수로 AIS를 켠 데이터를 찾는 용도에 가깝습니다. 반경을 무작정 늘리면 다른 선박이 섞이므로, 부두 실제 크기에 맞춰 두는 것이 좋습니다. 후보 0명일 때 `[진단]` 메시지로 "부두에서 가장 가까운 위치"만 참고용으로 확인할 수 있습니다.
- 후보에는 어선·민원선 등 부두 인근을 지나간 다른 선박도 포함될 수 있으므로, `berthed_ratio_near_pier`·`round_trip_detected`·선종코드 등을 함께 보며 순찰/경비선을 가려 쓰는 것이 좋습니다.
"""

def main():
    # .../data/AIS/search_patrol/write_... -> project root = parent x 4
    root = Path(__file__).resolve().parent.parent.parent.parent
    out = root / "docs" / "search_patrol.md"
    out.write_text(CONTENT, encoding="utf-8-sig")
    print("Written:", out)

if __name__ == "__main__":
    main()
