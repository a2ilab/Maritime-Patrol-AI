# Maritime Patrol AI

Q-Learning 기반 해양 순찰 경로 최적화 시스템

강화학습을 활용하여 영향력 맵을 기반으로 최적의 순찰 경로를 자동 생성합니다.

## Features

- **Q-Learning Agent**: 환경을 학습하여 최적 경로 도출
- **영향력 기반 경로 생성**: 정적/동적 영향 요소 고려
- **전략 선택**: 안전 우선, 효율 우선, 광역 감시 등 사전 정의된 전략
- **실시간 시각화**: Plotly 기반 인터랙티브 맵
- **Web UI**: Streamlit 대시보드
- **CLI 지원**: 명령줄 인터페이스

## Screenshots

### Web UI (Streamlit)
```
+------------------+--------+
|                  | Report |
|    Influence Map | -------|
|    + Path        | Stats  |
|                  |        |
+------------------+--------+
```

## Installation

### Requirements
- Python 3.10+

### Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/Maritime-Patrol-AI.git
cd Maritime-Patrol-AI

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Web UI (Streamlit)

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

### CLI

```bash
python main.py
```

### REST API (추론)

학습은 기존 방식 유지, **추론만 REST API**로 제공. 다른 시스템(Folium/Mapbox 등)에서 지도 시각화 시 활용.

```bash
# API 서버 실행
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# 또는
python api.py
```

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **엔드포인트**: `POST /inference`

**요청 예시** (`sample_request.json`):
```json
{
  "requestId": "REQ-20260309-001",
  "filter": {
    "startTime": "2026-03-01T00:00:00Z",
    "endTime": "2026-03-09T23:59:59Z",
    "shipId": "ALL",
    "accidentType": "ALL"
  },
  "options": {
    "includeRoute": true,
    "includeAccidentZone": true,
    "includeLabels": true
  },
  "strategy": "safety",
  "grid_size": 10
}
```

**응답**: `routes`(lat/lng 경로), `accidents`(중심점+radius), `labels`(텍스트+좌표)

### 지도 뷰어 (API 테스트용)

별도 폴더 `map-viewer/`에서 Folium 기반 웹 서비스로 API를 시험할 수 있습니다.

**간편 실행 (Windows):**
```bash
# start_servers.bat 더블클릭 또는
start_servers.bat
```

**수동 실행:**
```bash
# 1. API 서버 실행 (프로젝트 루트, 터미널 1)
python api.py
# → http://127.0.0.1:8000 (또는 http://localhost:8000)

# 2. 지도 뷰어 실행 (별도 터미널 2)
cd map-viewer && pip install -r requirements.txt && python run.py
# → http://127.0.0.1:8502
```

**서버 재구동:** `restart_servers.ps1` 실행 후 위 순서대로 다시 시작

## Project Structure

```
Maritime-Patrol-AI/
├── app.py                    # Streamlit 웹 앱 진입점
├── main.py                   # CLI 진입점
├── api.py                    # REST API 진입점
├── sample_request.json       # API 요청 샘플
├── requirements.txt
├── README.md
├── LICENSE
└── src/
    ├── config.py             # 설정 상수
    ├── core/
    │   ├── agent.py          # Q-Learning 에이전트
    │   ├── environment.py    # 순찰 환경
    │   └── trainer.py        # 학습 로직
    ├── api/                  # REST API (추론)
    │   ├── main.py           # FastAPI 앱
    │   ├── schemas.py        # 입출력 JSON 스펙
    │   ├── inference.py      # 추론 서비스
    │   └── coordinates.py   # 격자↔위경도 변환
    └── ui/
        ├── components.py     # Streamlit 컴포넌트
        ├── strategies.py     # 순찰 전략 정의
        └── visualization.py  # 시각화 유틸리티
```

## Strategies

| Strategy | Alpha | Beta | Gamma | Description |
|----------|-------|------|-------|-------------|
| Safety First | 40.0 | 0.2 | 5.0 | 순찰 필요성 지역 우선 순찰 |
| Efficiency First | 5.0 | 1.0 | 2.0 | 최소 이동으로 효율적 순찰 |
| Wide Surveillance | 10.0 | 0.0 | 20.0 | 넓은 영역 커버리지 |

## Algorithm

### Q-Learning Update Formula

```
Q(s,a) ← Q(s,a) + α[r + γ·max Q(s',a') - Q(s,a)]
```

- `α`: Learning rate (0.1)
- `γ`: Discount factor (0.99)
- `ε`: Exploration rate (1.0 → 0.01)

### Reward Function

```
reward = (influence_weight × influence_score + surveillance_effect) - movement_cost + bonus
```

## Build (Optional)

PyInstaller를 사용한 실행 파일 빌드:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed app.py
```

빌드된 파일은 `dist/` 폴더에 생성됩니다.

## License

MIT License - see [LICENSE](LICENSE) file

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
