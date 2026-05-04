"""Maritime Patrol AI - REST API 진입점.

추론 API 서버 실행:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

또는:
    python api.py

자동 재시작(개발용): 세션 전체에 다음을 설정 후 실행합니다.
    $env:MARITIME_UVICORN_RELOAD = "1"
"""

from __future__ import annotations

import os

import uvicorn

from src.api.main import app

if __name__ == "__main__":
    _reload = os.environ.get("MARITIME_UVICORN_RELOAD", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=_reload,
    )
