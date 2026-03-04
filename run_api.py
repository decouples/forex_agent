"""
FastAPI 服务启动入口
====================
用于跨工程智能体协作场景。
"""
from __future__ import annotations
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import uvicorn
from src.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "src.api_server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
    )

