# Maritime Patrol AI - 사용 방법

Q-Learning 기반 해양 경비순찰 경로 최적화 시스템의 설치, 실행, 사용 방법을 정리합니다.

---

## 목차

1. [사전 요구사항](#사전-요구사항)
2. [설치](#설치)
3. [실행 방법](#실행-방법)
4. [단축 실행 (Shortcut)](#단축-실행-shortcut)
5. [지도 뷰어 사용법](#지도-뷰어-사용법)
6. [API 사용법](#api-사용법)
7. [설정](#설정)
8. [문제 해결](#문제-해결)

---

## 사전 요구사항

- **Python 3.10 이상**
- **pip** (Python 패키지 관리자)

---

## 설치

### 1. 저장소 클론 및 이동

```bash
git clone https://github.com/YOUR_USERNAME/Maritime-Patrol-AI.git
cd Maritime-Patrol-AI
```

### 2. 가상환경 생성 (권장)

```bash
# 가상환경 생성
python -m venv .venv

# Windows 활성화
.venv\Scripts\activate

# Linux/Mac 활성화
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
# 프로젝트 루트 의존성
pip install -r requirements.txt

# 지도 뷰어 의존성 (별도 실행 시)
cd map-viewer
pip install -r requirements.txt
cd ..
```

---

## 실행 방법

### 기본 구성

이 프로젝트는 **두 개의 서버**를 동시에 실행해야 합니다.

| 서버 | 포트 | 용도 |
|------|------|------|
| **API 서버** | 8000 | 추론 API (경로·순찰 지역 생성) |
| **Map Viewer** | 8502 | 웹 지도 뷰어 (API 테스트용) |

### 수동 실행 (터미널 2개)

**터미널 1 - API 서버:**
```bash
cd Maritime-Patrol-AI
python api.py
```
→ http://127.0.0.1:8000

**터미널 2 - Map Viewer:**
```bash
cd Maritime-Patrol-AI/map-viewer
python run.py
```
→ http://127.0.0.1:8502

### uvicorn으로 직접 실행

```bash
# API 서버
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Map Viewer (map-viewer 폴더에서)
cd map-viewer
uvicorn main:app --reload --host 127.0.0.1 --port 8502
```

---

## 단축 실행 (Shortcut)

### 1. `start_servers.bat` (Windows)

**위치:** 프로젝트 루트

**사용법:** 파일을 더블클릭하거나, 명령 프롬프트에서 실행

```bash
start_servers.bat
```

**동작:**
- API 서버와 Map Viewer를 **각각 새 cmd 창**에서 실행
- 두 창이 열리며 서버가 백그라운드로 동작
- 창을 닫으면 해당 서버가 종료됨

**주의:** `start_servers.bat` 내부에 프로젝트 경로가 하드코딩되어 있습니다.  
다른 경로에 프로젝트를 둔 경우, 파일을 열어 `D:\Git\Maritime-Patrol-AI-master` 부분을 실제 경로로 수정하세요.

---

### 2. `restart_servers.ps1` (PowerShell)

**위치:** 프로젝트 루트

**사용법:** PowerShell에서 실행

```powershell
.\restart_servers.ps1
```

**동작:**
- 포트 8000, 8502를 사용 중인 프로세스를 **종료**
- 포트 해제 여부 확인
- 서버를 **직접 시작하지는 않음** → 수동으로 다시 실행해야 함

**실행 후:** 아래 명령을 각각 새 터미널에서 실행

```bash
# 1) API 서버
cd Maritime-Patrol-AI
python api.py

# 2) Map Viewer
cd Maritime-Patrol-AI/map-viewer
python run.py
```

---

## 지도 뷰어 사용법

### 접속

브라우저에서 **http://127.0.0.1:8502** 접속

### 좌측 설정 패널

| 항목 | 설명 |
|------|------|
| **순찰 출발지** | `군산항` 또는 `없음(격자 기준)` |
| **순찰 시작·종료 시간** | filter.startTime / endTime 으로 API에 전달 (시간대별 순찰 구역 반영) |
| **경로 표시** | 체크 시 경로 polyline 표시 (체크 해제 시 즉시 숨김) |
| **순찰 지역 표시** | 체크 시 순찰 필요 지역(빨간 원) 표시. 클릭 시 상세 팝업 |
| **라벨 표시** | 체크 시 라벨 마커 표시 |
| **격자 표시** | 체크 시 영향도 색상 격자 표시 |

※ 경로는 **안전 + 단시간** 기준으로만 생성됩니다. 전략(안전/효율/광역) 선택 UI는 제거된 상태입니다.

### 경로 생성

1. 설정을 선택한 뒤 **「경로 생성」** 버튼 클릭
2. API 호출 후 학습·경로 생성 (수십 초 소요 가능)
3. 지도에 경로, 순찰 지역, 격자가 표시됨

### 체크박스

체크박스는 **즉시 반영**됩니다. 경로 생성 없이 표시/숨김이 바로 적용됩니다.

---

## API 사용법

### Swagger UI

http://127.0.0.1:8000/docs 에서 대화형 API 문서 확인 및 테스트 가능

### ReDoc

http://127.0.0.1:8000/redoc 에서 API 문서 확인

### cURL 예시

```bash
curl -X POST http://127.0.0.1:8000/inference \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "REQ-001",
    "filter": {
      "startTime": "2026-03-01T00:00:00Z",
      "endTime": "2026-03-09T23:59:59Z"
    },
    "port": "gunsan"
  }'
```

### 상세 API 명세

→ [docs/API_SPEC.md](API_SPEC.md) 참고

---

## AIS 순찰/경비선 탐지 (search_patrol)

부두에서 출발하는 궤적·과도 기동을 탐지해 순찰·경비선 후보를 뽑고, CSV·KML로 내보냅니다.

- **실행**: `data/AIS/search_patrol/` 에서 `python search_patrol.py` (테스트: `--limit-files 1`)
- **입력**: 상위 폴더 `data/AIS/` 의 `Dynamic_YYYYMMDD.csv`, `Static.csv`
- **출력**: `patrol_candidates.csv`, `patrol_tracks.kml`, `candidate_Dynamic_YYYYMMDD.csv`
- **상세**: [docs/search_patrol.md](search_patrol.md) 참고

---

## 설정

### Map Viewer API 주소 변경

Map Viewer가 API를 다른 주소에서 호출해야 할 때:

**방법 1 - 환경변수:**
```bash
set MARITIME_API_URL=http://localhost:8000
python run.py
```

**방법 2 - config.py 수정:**
`map-viewer/config.py`의 `API_BASE_URL` 수정

### 프로젝트 설정 상수

`src/config.py`에서 학습 에피소드 수, 보상 가중치, POI 임계값 등 조정 가능

---

## 문제 해결

### 포트가 이미 사용 중일 때

1. **PowerShell:** `restart_servers.ps1` 실행 후 서버 재시작
2. **작업 관리자:** `python.exe` 프로세스 종료 후 재시작
3. **수동 종료 (PowerShell):**
   ```powershell
   Get-NetTCPConnection -LocalPort 8000,8502 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```

### API 연결 실패 (Map Viewer)

- API 서버가 http://127.0.0.1:8000 에서 실행 중인지 확인
- `map-viewer/config.py`의 `API_BASE_URL` 확인

### 경로 생성 시간이 오래 걸릴 때

- 학습에 30초~1분 이상 소요될 수 있음
- `src/config.py`의 `DEFAULT_TRAINING_EPISODES`를 줄이면 빨라지지만 경로 품질이 떨어질 수 있음

### 지도가 갱신되지 않을 때

- **Ctrl+Shift+R** (강력 새로고침) 시도
- 주소창에 http://127.0.0.1:8502 직접 입력 후 접속

---

## 프로젝트 구조 요약

```
Maritime-Patrol-AI/
├── api.py                 # REST API 진입점 (포트 8000)
├── start_servers.bat      # [단축] 서버 일괄 시작 (Windows)
├── restart_servers.ps1    # [단축] 서버 프로세스 종료 (PowerShell)
├── requirements.txt
├── docs/
│   ├── README.md          # 문서·구현 복기용 개요 (먼저 읽기)
│   ├── API_SPEC.md        # API JSON 명세서
│   ├── HOW_TO_USE.md      # 사용 방법 (본 문서)
│   ├── algorithm.md       # 목표 알고리즘
│   ├── TASKS.md           # 할 일 목록
│   └── search_patrol.md   # AIS 순찰선 탐지 도구
├── map-viewer/            # 지도 뷰어 (포트 8502)
│   ├── run.py
│   ├── config.py
│   └── requirements.txt
├── src/
│   ├── api/               # REST API (inference 등)
│   ├── core/              # learning_map, 환경, 트레이너
│   └── config.py
├── models/                # patrol_learning_map.npz (추론용 학습 맵)
└── data/AIS/search_patrol # 순찰선 탐지 스크립트·결과(CSV/KML)
```

---

## 버전 정보

- 문서 작성일: 2026-03-13
