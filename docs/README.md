# Maritime Patrol AI - 문서 개요 (복기용)

다른 담당자·세션에서 **"docs 폴더를 읽어보라"** 고 할 때, 이 문서부터 보면 전체 구조와 현재 구현 상태를 빠르게 복기할 수 있습니다.

---

## 1. 문서 목록과 역할

| 문서 | 역할 |
|------|------|
| **README.md** (본 문서) | 문서·프로젝트 복기용 개요. 먼저 읽기. |
| **algorithm.md** | **목표 알고리즘** 정의. 학습(그래프+가중치)→추론(시간대별 순찰 필요성·구역)·경로(안전+단시간)·UI 방향. |
| **TASKS.md** | algorithm.md 기준 **할 일 목록**. 관계성 레이어/학습/추론/경로/UI/문서별 진행 상황. |
| **API_SPEC.md** | **추론 REST API** 명세. `POST /inference`, 요청/응답 스키마, 포트 8000. |
| **HOW_TO_USE.md** | **설치·실행·사용법**. API(8000)·Map Viewer(8502), 설정·문제 해결. |
| **search_patrol.md** | **AIS 순찰/경비선 탐지** 도구. 부두 출발 궤적·과도 기동 탐지·CSV/KML 출력. |

---

## 2. 프로젝트 구조 요약

```
Maritime-Patrol-AI/
├── api.py                    # REST API 진입점 (포트 8000)
├── requirements.txt
├── docs/                      # 문서 (본 폴더)
├── map-viewer/                # 웹 지도 뷰어 (포트 8502)
│   ├── run.py
│   ├── config.py
│   └── templates/
├── src/
│   ├── api/                   # API 라우트·스키마
│   │   └── inference.py       # 추론: 학습 맵 + 시간대 데이터 → 순찰 구역·경로
│   ├── core/
│   │   ├── learning_map.py    # InferenceModel (그래프+가중치), 당분간 랜덤 모델
│   │   ├── environment.py     # 격자·POI·보상
│   │   └── ...
│   └── config.py
├── models/
│   └── patrol_learning_map.npz  # 저장/로드되는 학습 맵 (랜덤 생성 후 재사용)
└── data/AIS/
    ├── Dynamic_YYYYMMDD.csv   # AIS 동적 데이터
    ├── Static.csv             # AIS 정적 데이터
    └── search_patrol/          # 순찰선 탐지 스크립트·결과
        ├── search_patrol.py
        ├── patrol_candidates.csv
        ├── patrol_tracks.kml   # 궤적 KML (Google Earth 등)
        └── candidate_Dynamic_*.csv
```

---

## 3. 현재 구현 상태 (복기용)

### 3.1 학습 맵·추론 (algorithm.md 방향)

- **학습**: 아직 **미구현**. 데이터별 "값→순찰 영향" 그래프·그래프별 가중치 학습은 미착수.
- **추론**: **구현됨.**  
  - `src/core/learning_map.py`: `InferenceModel`, `IndicatorGraph`, 랜덤 그래프·가중치 생성, `save`/`load` (npz).  
  - `src/api/inference.py`: 모델 없으면 랜덤 생성 후 `models/patrol_learning_map.npz`에 저장·재사용.  
  - 요청의 `filter.startTime`/`endTime`으로 **1시간 단위 슬롯** 계산(최대 4슬롯).  
  - 각 슬롯: 랜덤 데이터 → `model.apply` → 순찰 필요성 격자 → 구역·웨이포인트 추출.  
  - 순찰 구역은 시간대당 상위 2개로 제한.
- **경로**: 안전+단시간 고정. strategy 파라미터는 API에 남아 있으나 **무시**됨 (TASKS.md 반영).

### 3.2 Map Viewer (웹 UI)

- 포트 **8502**. API(8000) 호출해 경로·순찰 지역·격자 표시.
- **전략(안전/효율/광역) 선택 UI 제거**됨. 시간 입력(순찰 시작·종료) 추가됨.
- 순찰 지역(원) 클릭 시 상세 팝업 동작하도록 수정됨 (`map-viewer/templates/index.html`).

### 3.3 AIS 순찰/경비선 탐지 (search_patrol)

- **위치**: `data/AIS/search_patrol/search_patrol.py`
- **역할**: 군산해양경찰서 경비함정전용부두 **에서 출발하는** 궤적만 대상으로, **출발 시 과도한 회전(COG/Heading)·속도(SOG) 변화**가 있는 선박만 후보로 추출.
- **입력**: `data/AIS/` 의 `Dynamic_YYYYMMDD.csv`, `Static.csv`
- **출력**:
  - `patrol_candidates.csv`: 최종 후보 목록 (MMSI, Static, point_count, departure_count, round_trip_detected 등)
  - `patrol_tracks.kml`: 후보 궤적 (Google Earth 등에서 확인)
  - `candidate_Dynamic_YYYYMMDD.csv`: 1차 후보(부두 근처 한 번이라도 있는 선박) 궤적
- **실행**: `cd data/AIS/search_patrol && python search_patrol.py` (옵션: `--limit-files N`)
- **상세**: `docs/search_patrol.md` 참고. (한글이 깨져 보이면 `data/AIS/search_patrol/write_doc_utf8.py` 실행 후 해당 md 다시 열기.)

---

## 4. 서버·실행 요약

| 대상 | 포트 | 실행 |
|------|------|------|
| Maritime Patrol API | 8000 | `python api.py` |
| Map Viewer | 8502 | `cd map-viewer && python run.py` |

코드 수정 후에는 두 서버 모두 **재구동**하는 것이 좋습니다 (`.cursor/rules` 참고).

---

## 5. 문서 갱신 시 참고

- **algorithm.md**: 목표 알고리즘·UI 방향이 바뀔 때 수정.
- **TASKS.md**: 작업 완료/미착수 반영. search_patrol·KML 등 추가 작업이 있으면 항목 추가.
- **API_SPEC.md**: 요청/응답 필드·동작이 바뀔 때 수정. (현재 strategy는 문서에 "무시" 등으로 표기 가능.)
- **HOW_TO_USE.md**: 설치·실행 경로·UI 설명이 바뀔 때 수정.
- **search_patrol.md**: 탐지 조건·입출력·옵션이 바뀔 때 수정. 인코딩 이슈 시 `write_doc_utf8.py`로 재생성.

이 개요는 구현 상태가 바뀔 때마다 함께 갱신하는 것을 권장합니다.
