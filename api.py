"""Maritime Patrol AI - REST API 진입점.

추론 API 서버 실행:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

또는:
    python api.py
"""

from __future__ import annotations

import uvicorn

from src.api.main import app

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
