"""
配置模块
========
统一管理项目中所有可配置的参数，通过 .env 文件或环境变量注入。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 优先加载 .env；若不存在，再回退加载 .env.example
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
env_example_path = project_root / ".env.example"
if env_path.exists():
    load_dotenv(env_path)
elif env_example_path.exists():
    load_dotenv(env_example_path)


class Settings:
    """项目全局配置类"""

    # ---------- LLM 配置 ----------
    # 可选值：gemini / chatglm / deepseek / vllm
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()

    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")

    # ChatGLM / ZhipuAI
    CHATGLM_API_KEY: str = os.getenv("CHATGLM_API_KEY", "")
    CHATGLM_MODEL: str = os.getenv("CHATGLM_MODEL", "glm-4-flash")

    # DeepSeek（官方 API，兼容 OpenAI 协议）
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # vLLM 本地推理服务（兼容 OpenAI /v1/chat/completions 协议）
    VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    VLLM_MODEL: str = os.getenv("VLLM_MODEL", "default")
    VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "EMPTY")

    # ---------- 外汇 API 配置 ----------
    # 实时查询数据源优先级（从左到右依次降级）
    FOREX_PROVIDER_PRIORITY: str = os.getenv(
        "FOREX_PROVIDER_PRIORITY",
        "exchangerate_api,floatrates,fawazahmed,frankfurter",
    )
    # 历史查询数据源优先级（从左到右依次降级）
    FOREX_HISTORY_PROVIDER_PRIORITY: str = os.getenv(
        "FOREX_HISTORY_PROVIDER_PRIORITY",
        "fawazahmed,ecb,frankfurter",
    )
    # Frankfurter（ECB 数据，第三方托管，偶尔不稳定）
    FOREX_API_BASE_URL: str = "https://api.frankfurter.app"
    # Fawazahmed0 Currency API（首选推荐，CDN 加速）
    FOREX_FAWAZAHMED_BASE_URL: str = os.getenv(
        "FOREX_FAWAZAHMED_BASE_URL",
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1",
    )
    # ExchangeRate-API 公开免 Key 端点（仅实时）
    FOREX_EXCHANGERATE_API_BASE_URL: str = os.getenv(
        "FOREX_EXCHANGERATE_API_BASE_URL",
        "https://open.er-api.com/v6",
    )
    # FloatRates 公开端点（仅实时）
    FOREX_FLOATRATES_BASE_URL: str = os.getenv(
        "FOREX_FLOATRATES_BASE_URL",
        "https://www.floatrates.com",
    )
    # ECB SDW 官方数据 API（欧洲中央银行统计数据仓库，稳定可靠，支持历史区间）
    FOREX_ECB_SDW_BASE_URL: str = os.getenv(
        "FOREX_ECB_SDW_BASE_URL",
        "https://data-api.ecb.europa.eu/service/data/EXR",
    )
    FOREX_API_TIMEOUT: int = 20  # 请求超时时间（秒）
    FOREX_API_CONNECT_TIMEOUT: float = float(os.getenv("FOREX_API_CONNECT_TIMEOUT", "5"))
    FOREX_API_READ_TIMEOUT: float = float(os.getenv("FOREX_API_READ_TIMEOUT", str(FOREX_API_TIMEOUT)))
    FOREX_API_RETRIES: int = int(os.getenv("FOREX_API_RETRIES", "2"))
    FOREX_API_RETRY_BACKOFF: float = float(os.getenv("FOREX_API_RETRY_BACKOFF", "0.8"))
    FOREX_HISTORY_CHUNK_DAYS: int = int(os.getenv("FOREX_HISTORY_CHUNK_DAYS", "30"))
    FOREX_API_USER_AGENT: str = os.getenv(
        "FOREX_API_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    )

    # ---------- 数据分析配置 ----------
    DEFAULT_HISTORY_DAYS: int = 60        # 默认获取最近 60 天历史数据
    DEFAULT_FORECAST_DAYS: int = 15       # 默认预测未来 15 天
    MA_SHORT_WINDOW: int = 7              # 短期移动平均窗口（天）
    MA_LONG_WINDOW: int = 30             # 长期移动平均窗口（天）

    # ---------- 可视化配置 ----------
    CHARTS_DIR: str = os.getenv("CHARTS_DIR", "./charts")
    CHART_DPI: int = 150
    CHART_FIGSIZE: tuple = (12, 6)

    # ---------- 实时刷新配置 ----------
    # ECB 数据源工作日更新一次，轮询间隔无需太短，默认 3600s，避免浪费请求/token
    REALTIME_REFRESH_INTERVAL_MS: int = int(os.getenv("REALTIME_REFRESH_MS", "3600000"))

    # ---------- 日志配置 ----------
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "./logs")
    LOG_FILE_NAME: str = os.getenv("LOG_FILE_NAME", "forex_agent.log")

    # ---------- 跨工程协作 API ----------
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8100"))
    COLLAB_API_BASE_URL: str = os.getenv("COLLAB_API_BASE_URL", f"http://127.0.0.1:{API_PORT}")

    # ---------- 支持货币（代码）----------
    MAJOR_CURRENCIES: list[str] = [
        "USD", "EUR", "GBP", "JPY", "CHF",
        "CNY", "HKD", "AUD", "CAD", "SGD",
        "KRW", "NZD", "SEK", "NOK", "DKK",
        "PLN", "CZK", "HUF", "RON", "BGN",
        "TRY", "RUB", "INR", "IDR", "THB",
        "MYR", "PHP", "VND", "ZAR", "BRL",
        "MXN", "ARS", "CLP", "COP", "PEN",
        "AED", "SAR", "ILS", "EGP", "QAR",
    ]

    # ---------- 货币中文名映射（用于展示）----------
    CURRENCY_NAME_MAP: dict[str, str] = {
        "USD": "美元",
        "EUR": "欧元",
        "GBP": "英镑",
        "JPY": "日元",
        "CHF": "瑞士法郎",
        "CNY": "人民币",
        "HKD": "港元",
        "AUD": "澳元",
        "CAD": "加元",
        "SGD": "新加坡元",
        "KRW": "韩元",
        "NZD": "新西兰元",
        "SEK": "瑞典克朗",
        "NOK": "挪威克朗",
        "DKK": "丹麦克朗",
        "PLN": "波兰兹罗提",
        "CZK": "捷克克朗",
        "HUF": "匈牙利福林",
        "RON": "罗马尼亚列伊",
        "BGN": "保加利亚列弗",
        "TRY": "土耳其里拉",
        "RUB": "俄罗斯卢布",
        "INR": "印度卢比",
        "IDR": "印尼盾",
        "THB": "泰铢",
        "MYR": "马来西亚林吉特",
        "PHP": "菲律宾比索",
        "VND": "越南盾",
        "ZAR": "南非兰特",
        "BRL": "巴西雷亚尔",
        "MXN": "墨西哥比索",
        "ARS": "阿根廷比索",
        "CLP": "智利比索",
        "COP": "哥伦比亚比索",
        "PEN": "秘鲁索尔",
        "AED": "阿联酋迪拉姆",
        "SAR": "沙特里亚尔",
        "ILS": "以色列新谢克尔",
        "EGP": "埃及镑",
        "QAR": "卡塔尔里亚尔",
    }


settings = Settings()
