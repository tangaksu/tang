"""Layer 2 – AKShare adapter (primary data source, pinned to 1.18.64)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from .data_cache import DataCache, TTL_REALTIME, TTL_FINANCIAL, TTL_RESEARCH, TTL_INDUSTRY, get_cache
from .models import (
    AnalystForecast,
    CapitalFlowData,
    FinancialSummary,
    KLineBar,
    QuoteData,
    StockBasic,
)
from .rate_limiter import akshare_limiter

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float | None = None) -> float | None:
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return default


class AKShareAdapter:
    """Thin adapter over AKShare that adds caching and rate-limiting."""

    def __init__(self, cache: DataCache | None = None) -> None:
        self._cache = cache or get_cache()

    # ------------------------------------------------------------------
    # Stock basic info
    # ------------------------------------------------------------------

    def get_stock_basic(self, code: str) -> StockBasic | None:
        key = f"akshare:stock_basic:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return StockBasic(**cached)
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_individual_info_em(symbol=code)
            if df is None or df.empty:
                return None
            info: dict[str, str] = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
            basic = StockBasic(
                code=code,
                name=info.get("股票简称", ""),
                market=info.get("上市板块", ""),
                industry=info.get("行业", ""),
            )
            self._cache.set_sync(key, basic.model_dump(), TTL_INDUSTRY)
            return basic
        except Exception as exc:
            logger.warning("AKShare get_stock_basic(%s) failed: %s", code, exc)
            return None

    # ------------------------------------------------------------------
    # Real-time quote
    # ------------------------------------------------------------------

    def get_quote(self, code: str) -> QuoteData | None:
        key = f"akshare:quote:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return QuoteData(**cached)
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code]
            if row.empty:
                return None
            r = row.iloc[0]
            quote = QuoteData(
                code=code,
                name=str(r.get("名称", "")),
                price=_safe_float(r.get("最新价"), 0.0) or 0.0,
                change_pct=_safe_float(r.get("涨跌幅"), 0.0) or 0.0,
                volume=_safe_float(r.get("成交量"), 0.0) or 0.0,
                amount=_safe_float(r.get("成交额"), 0.0) or 0.0,
                turnover_rate=_safe_float(r.get("换手率"), 0.0) or 0.0,
                market_cap=_safe_float(r.get("总市值"), 0.0) or 0.0,
                circulating_cap=_safe_float(r.get("流通市值"), 0.0) or 0.0,
                pe_ttm=_safe_float(r.get("市盈率-动态")),
                pb=_safe_float(r.get("市净率")),
                date=date.today(),
            )
            self._cache.set_sync(key, quote.model_dump(), TTL_REALTIME)
            return quote
        except Exception as exc:
            logger.warning("AKShare get_quote(%s) failed: %s", code, exc)
            return None

    # ------------------------------------------------------------------
    # K-Lines
    # ------------------------------------------------------------------

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        adjust: str = "qfq",
        limit: int = 250,
    ) -> list[KLineBar]:
        key = f"akshare:kline:{code}:{period}:{adjust}:{limit}"
        cached = self._cache.get_sync(key)
        if cached:
            return [KLineBar(**bar) for bar in cached]
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            start = (datetime.today() - timedelta(days=limit * 2)).strftime("%Y%m%d")
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start,
                adjust=adjust,
            )
            if df is None or df.empty:
                return []
            bars: list[KLineBar] = []
            for _, row in df.tail(limit).iterrows():
                bars.append(
                    KLineBar(
                        date=pd.to_datetime(row["日期"]).date(),
                        open=_safe_float(row["开盘"], 0.0) or 0.0,
                        high=_safe_float(row["最高"], 0.0) or 0.0,
                        low=_safe_float(row["最低"], 0.0) or 0.0,
                        close=_safe_float(row["收盘"], 0.0) or 0.0,
                        volume=_safe_float(row["成交量"], 0.0) or 0.0,
                        amount=_safe_float(row["成交额"], 0.0) or 0.0,
                        change_pct=_safe_float(row["涨跌幅"], 0.0) or 0.0,
                    )
                )
            self._cache.set_sync(key, [b.model_dump() for b in bars], TTL_REALTIME)
            return bars
        except Exception as exc:
            logger.warning("AKShare get_klines(%s, %s) failed: %s", code, period, exc)
            return []

    # ------------------------------------------------------------------
    # Financial summary
    # ------------------------------------------------------------------

    def get_financial_summary(self, code: str) -> FinancialSummary | None:
        key = f"akshare:financial:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return FinancialSummary(**cached)
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
            if df is None or df.empty:
                return None
            row = df.iloc[0]
            summary = FinancialSummary(
                period=str(row.get("报告期", "")),
                revenue=_safe_float(row.get("营业总收入")),
                net_profit=_safe_float(row.get("净利润")),
                gross_margin=_safe_float(row.get("毛利率")),
                roe=_safe_float(row.get("ROE")),
            )
            self._cache.set_sync(key, summary.model_dump(), TTL_FINANCIAL)
            return summary
        except Exception as exc:
            logger.warning("AKShare get_financial_summary(%s) failed: %s", code, exc)
            return None

    # ------------------------------------------------------------------
    # Capital flow
    # ------------------------------------------------------------------

    def get_capital_flow(self, code: str) -> CapitalFlowData | None:
        key = f"akshare:capital_flow:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return CapitalFlowData(**cached)
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
            if df is None or df.empty:
                return CapitalFlowData(code=code)
            recent = df.tail(20)
            main_20 = _safe_float(recent["主力净流入-净额"].sum() / 1e8)
            main_10 = _safe_float(recent.tail(10)["主力净流入-净额"].sum() / 1e8)
            main_5 = _safe_float(recent.tail(5)["主力净流入-净额"].sum() / 1e8)
            flow = CapitalFlowData(
                code=code,
                main_net_inflow_5d=main_5,
                main_net_inflow_10d=main_10,
                main_net_inflow_20d=main_20,
            )
            self._cache.set_sync(key, flow.model_dump(), TTL_REALTIME)
            return flow
        except Exception as exc:
            logger.warning("AKShare get_capital_flow(%s) failed: %s", code, exc)
            return CapitalFlowData(code=code)

    # ------------------------------------------------------------------
    # Analyst forecast
    # ------------------------------------------------------------------

    def get_analyst_forecast(self, code: str) -> AnalystForecast | None:
        key = f"akshare:forecast:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return AnalystForecast(**cached)
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_analyst_forecast_em(symbol=code)
            if df is None or df.empty:
                return AnalystForecast(code=code)
            # Aggregate rating counts
            counts: dict[str, int] = {}
            for _, row in df.iterrows():
                rating = str(row.get("评级", ""))
                counts[rating] = counts.get(rating, 0) + 1
            forecast = AnalystForecast(
                code=code,
                rating_buy=counts.get("买入", 0),
                rating_overweight=counts.get("增持", 0),
                rating_neutral=counts.get("中性", 0),
                rating_underweight=counts.get("减持", 0),
                rating_sell=counts.get("卖出", 0),
                target_price_avg=_safe_float(df.get("目标价", pd.Series()).mean()),
                target_price_high=_safe_float(df.get("目标价", pd.Series()).max()),
                target_price_low=_safe_float(df.get("目标价", pd.Series()).min()),
            )
            self._cache.set_sync(key, forecast.model_dump(), TTL_RESEARCH)
            return forecast
        except Exception as exc:
            logger.warning("AKShare get_analyst_forecast(%s) failed: %s", code, exc)
            return AnalystForecast(code=code)

    # ------------------------------------------------------------------
    # North-bound flows (aggregate market level)
    # ------------------------------------------------------------------

    def get_north_flow(self, code: str) -> dict[str, float]:
        """Return north-bound 5/10/20-day net buy for individual stock."""
        key = f"akshare:north_flow:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_hsgt_individual_em(symbol=code)
            if df is None or df.empty:
                return {}
            result = {
                "north_5d": _safe_float(df.tail(5)["净买入"].sum() / 1e8),
                "north_10d": _safe_float(df.tail(10)["净买入"].sum() / 1e8),
                "north_20d": _safe_float(df.tail(20)["净买入"].sum() / 1e8),
            }
            self._cache.set_sync(key, result, TTL_REALTIME)
            return result
        except Exception as exc:
            logger.warning("AKShare get_north_flow(%s) failed: %s", code, exc)
            return {}
