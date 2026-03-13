"""Map Viewer 실행 진입점.

별도 실행:
    cd map-viewer
    pip install -r requirements.txt
    python run.py

또는:
    uvicorn main:app --reload --host 127.0.0.1 --port 8502
"""

from __future__ import annotations

import os
import sys

import uvicorn

# run.py가 있는 디렉터리를 작업 디렉터리로 설정 (경로 문제 방지)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_SCRIPT_DIR)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )
