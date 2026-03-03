"""
历史分析与趋势预测
==================
包含统计分析（均值、波动率、涨跌幅）和线性回归趋势预测。
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from src.config import settings
from src.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    mean_rate: float
    std_rate: float
    latest_rate: float
    return_pct: float
    ma_short: float
    ma_long: float
    trend_label: str


class AnalysisService:
    """分析与预测服务。"""

    @staticmethod
    def to_dataframe(history_records: list[dict[str, float | str]]) -> pd.DataFrame:
        df = pd.DataFrame(history_records)
        if df.empty:
            raise ValueError("历史数据为空，无法分析。")

        df["date"] = pd.to_datetime(df["date"])
        df["rate"] = pd.to_numeric(df["rate"])
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def analyze(self, history_records: list[dict[str, float | str]]) -> AnalysisResult:
        df = self.to_dataframe(history_records)

        mean_rate = float(df["rate"].mean())
        std_rate = float(df["rate"].std(ddof=0))
        latest_rate = float(df["rate"].iloc[-1])
        first_rate = float(df["rate"].iloc[0])
        return_pct = float((latest_rate - first_rate) / first_rate * 100)

        ma_short = float(df["rate"].tail(settings.MA_SHORT_WINDOW).mean())
        ma_long = float(df["rate"].tail(settings.MA_LONG_WINDOW).mean())
        trend_label = "上升" if ma_short > ma_long else "下降/震荡"

        result = AnalysisResult(
            mean_rate=mean_rate,
            std_rate=std_rate,
            latest_rate=latest_rate,
            return_pct=return_pct,
            ma_short=ma_short,
            ma_long=ma_long,
            trend_label=trend_label,
        )
        logger.info(
            "analyze_result | points=%s | mean=%.6f | std=%.6f | return_pct=%.3f | trend=%s",
            len(df),
            result.mean_rate,
            result.std_rate,
            result.return_pct,
            result.trend_label,
        )
        return result

    def _forecast_linear(self, history_records: list[dict[str, float | str]], days: int) -> dict[str, float | list]:
        """线性趋势模型。"""
        df = self.to_dataframe(history_records)
        y = df["rate"].values
        x = np.arange(len(df)).reshape(-1, 1)

        model = LinearRegression()
        model.fit(x, y)

        future_x = np.arange(len(df), len(df) + days).reshape(-1, 1)
        future_y = model.predict(future_x)

        return {
            "forecast_days": days,
            "predicted_rates": [float(v) for v in future_y],
            "slope": float(model.coef_[0]),
            "intercept": float(model.intercept_),
        }

    def _forecast_oscillation(self, history_records: list[dict[str, float | str]], days: int) -> dict[str, float | list]:
        """
        震荡模型：围绕近期均值做平稳振荡（确定性）。
        """
        df = self.to_dataframe(history_records)
        rates = df["rate"].values
        latest = float(rates[-1])
        recent = rates[-20:] if len(rates) >= 20 else rates
        center = float(np.mean(recent))
        amp = max(float(np.std(recent) * 0.5), 1e-6)

        preds: list[float] = []
        for i in range(1, days + 1):
            # 确定性的微振荡，首日向最新价靠拢
            val = center + amp * np.sin(i * np.pi / 3.0)
            if i == 1:
                val = 0.7 * latest + 0.3 * val
            preds.append(float(max(val, 1e-6)))

        return {
            "forecast_days": days,
            "predicted_rates": preds,
            "slope": 0.0,
            "intercept": center,
        }

    def _forecast_cycle(self, history_records: list[dict[str, float | str]], days: int) -> dict[str, float | list]:
        """
        周期模型：复用近期周期片段（确定性）。
        """
        df = self.to_dataframe(history_records)
        rates = [float(v) for v in df["rate"].values]
        latest = rates[-1]
        cycle_window = min(max(7, len(rates) // 4), len(rates))
        cycle = rates[-cycle_window:]
        preds: list[float] = []
        for i in range(days):
            val = cycle[i % cycle_window]
            if i == 0:
                val = 0.6 * latest + 0.4 * val
            preds.append(float(max(val, 1e-6)))

        return {
            "forecast_days": days,
            "predicted_rates": preds,
            "slope": 0.0,
            "intercept": float(np.mean(cycle)),
        }

    def forecast(
        self,
        history_records: list[dict[str, float | str]],
        days: int,
        model_type: str = "linear",
    ) -> dict[str, float | list]:
        """
        统一预测入口：根据 model_type 选择确定性的预测模型。
        - linear: 线性趋势
        - oscillation: 震荡均值回复
        - cycle: 周期复用
        """
        if model_type == "oscillation":
            result = self._forecast_oscillation(history_records, days)
        elif model_type == "cycle":
            result = self._forecast_cycle(history_records, days)
        else:
            result = self._forecast_linear(history_records, days)

        logger.info(
            "quant_forecast_result | model=%s | points=%s | days=%s | slope=%.8f | first=%.6f | last=%.6f",
            model_type,
            len(history_records),
            days,
            result["slope"],
            result["predicted_rates"][0] if result["predicted_rates"] else -1,
            result["predicted_rates"][-1] if result["predicted_rates"] else -1,
        )
        return result
