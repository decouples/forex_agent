"""
FastAPI 服务启动入口
====================
用于跨工程智能体协作场景。
"""
from __future__ import annotations
import uvicorn
from src.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "src.api_server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
    )

