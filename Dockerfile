# ============================================================
# 外汇智能体 Docker 镜像（多阶段构建）
# ============================================================
#
# 本文件包含 3 个构建 target，每个 target 产出一个独立镜像：
#
#   docker build --target api -t forex-agent-api .
#   docker build --target ui  -t forex-agent-ui  .
#   docker build --target mcp -t forex-agent-mcp .
#
# 也可以直接用 docker compose，它会自动选 target：
#
#   docker compose build        # 构建全部
#   docker compose up -d        # 启动 api + ui
#
# ============================================================

# ==================== 阶段 1: 公共依赖层 ====================
# 所有服务共享此层，安装依赖 + 拷贝源码，避免重复构建
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY main.py run_api.py run_mcp.py streamlit_app.py ./
COPY .env.example .env.example

# ==================== 阶段 2a: API 服务镜像 ====================
# 构建命令：docker build --target api -t forex-agent-api .
# 运行命令：docker run -d --env-file .env -p 8000:8000 forex-agent-api
FROM base AS api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=3).raise_for_status()" || exit 1

CMD ["python", "run_api.py"]

# ==================== 阶段 2b: Streamlit UI 镜像 ====================
# 构建命令：docker build --target ui -t forex-agent-ui .
# 运行命令：docker run -d --env-file .env -p 8501:8501 forex-agent-ui
FROM base AS ui

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8501/_stcore/health', timeout=3).raise_for_status()" || exit 1

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]

# ==================== 阶段 2c: MCP 服务镜像（可选） ====================
# 构建命令：docker build --target mcp -t forex-agent-mcp .
# 运行命令：docker run -d --env-file .env -p 8080:8080 forex-agent-mcp
FROM base AS mcp

EXPOSE 8080

CMD ["python", "run_mcp.py"]
