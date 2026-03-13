# Maritime Patrol - 지도 뷰어

Maritime Patrol API를 테스트하기 위한 **표준 웹 기반** 지도 뷰어입니다.  
Folium(Leaflet.js) + **OpenStreetMap**을 사용하며, **API 키 등록 없이** 무료로 사용 가능합니다.

> **지도 API 키**: 현재 OpenStreetMap 사용 → 키 불필요. Mapbox 등 다른 타일을 쓰려면 해당 서비스에서 키 발급 후 `map_builder.py`의 tiles URL을 변경하면 됩니다.

## 기능

- **Folium 지도**: OpenStreetMap 기반, 표준 웹 기술
- **경로 표시**: API 응답의 `routes` → 파란색 Polyline
- **사고 구역**: `accidents` → 빨간색 원(Circle, 중심점+radius)
- **라벨**: `labels` → 마커
- **전략 선택**: 안전 우선 / 효율 우선 / 광역 감시
- **설정**: 격자 크기, 맵 시드, 출력 옵션

## 실행 방법

### 1. Maritime Patrol API 먼저 실행

```bash
# 프로젝트 루트에서
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

### 2. 지도 뷰어 실행

```bash
cd map-viewer
pip install -r requirements.txt
python run.py
```

또는:

```bash
cd map-viewer
uvicorn main:app --reload --host 127.0.0.1 --port 8502
```

### 3. 브라우저 접속

- http://127.0.0.1:8502

## 폴더 구조

```
map-viewer/
├── run.py              # 실행 진입점
├── main.py             # FastAPI 앱
├── config.py           # API URL, 서버 설정
├── api_client.py       # API 호출
├── map_builder.py      # Folium 지도 생성
├── requirements.txt
├── README.md
└── templates/
    └── index.html      # 메인 페이지
```

## API URL 변경

`config.py`에서 `API_BASE_URL`을 수정하면 다른 주소의 API를 사용할 수 있습니다.

```python
API_BASE_URL: str = "http://127.0.0.1:8000"
```

## 의존성

- folium: 지도 생성 (Leaflet.js)
- requests: API 호출
- fastapi, uvicorn: 웹 서버
- jinja2: HTML 템플릿
