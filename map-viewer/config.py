"""Map Viewer 설정."""

import os

# Maritime Patrol API 기본 URL (별도 실행 시)
# 환경변수 MARITIME_API_URL 로 오버라이드 가능 (예: http://localhost:8000)
API_BASE_URL: str = os.environ.get("MARITIME_API_URL", "http://127.0.0.1:8000")
API_INFERENCE_PATH: str = "/inference"

# 서버 설정
HOST: str = "127.0.0.1"
PORT: int = 8502
