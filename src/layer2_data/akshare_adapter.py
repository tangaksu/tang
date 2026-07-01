"""Layer 2 – AKShare adapter (primary data source, pinned to 1.18.64)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

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
            # stock_analyst_forecast_em was removed in AKShare 1.18.x;
            # use stock_profit_forecast_ths (同花顺盈利预测) which accepts a
            # single stock symbol and returns institutional EPS forecasts.
            df = ak.stock_profit_forecast_ths(symbol=code, indicator="业绩预测详表-机构")
            if df is None or df.empty:
                return AnalystForecast(code=code)
            # Column names vary; extract target price if present
            tp_col = next((c for c in df.columns if "目标价" in c), None)
            tp_series = df[tp_col].apply(_safe_float) if tp_col else pd.Series(dtype=float)
            forecast = AnalystForecast(
                code=code,
                target_price_avg=_safe_float(tp_series.mean()) if not tp_series.empty else None,
                target_price_high=_safe_float(tp_series.max()) if not tp_series.empty else None,
                target_price_low=_safe_float(tp_series.min()) if not tp_series.empty else None,
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

    # ------------------------------------------------------------------
    # Index realtime spot
    # ------------------------------------------------------------------

    def get_index_spot(self) -> list[dict[str, Any]]:
        """Return realtime quotes for major A-share indices.

        Tries Sina first (lower latency), falls back to East-Money.
        """
        key = "akshare:index_spot"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            try:
                df = ak.stock_zh_index_spot_sina()
                source = "sina"
            except Exception:
                df = ak.stock_zh_index_spot_em()
                source = "em"
            if df is None or df.empty:
                return []
            records = df.head(50).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_index_spot failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Intraday (minute-level)
    # ------------------------------------------------------------------

    def get_intraday(
        self,
        code: str,
        period: str = "1",
        limit: int = 120,
    ) -> list[KLineBar]:
        """Return intraday minute-level bars (period: '1','5','15','30','60')."""
        period = period if period in {"1", "5", "15", "30", "60"} else "1"
        key = f"akshare:intraday:{code}:{period}:{limit}"
        cached = self._cache.get_sync(key)
        if cached:
            return [KLineBar(**b) for b in cached]
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            try:
                df = ak.stock_zh_a_minute(symbol=code, period=period, adjust="")
            except Exception:
                df = ak.stock_intraday_em(symbol=code)
            if df is None or df.empty:
                return []
            bars: list[KLineBar] = []
            date_cols = [c for c in df.columns if "时间" in c or "日期" in c or c == "datetime"]
            date_col = date_cols[0] if date_cols else df.columns[0]
            for _, row in df.tail(limit).iterrows():
                try:
                    dt = pd.to_datetime(row[date_col])
                    bars.append(
                        KLineBar(
                            date=dt.date(),
                            open=_safe_float(row.get("开盘", row.get("open", 0)), 0.0) or 0.0,
                            high=_safe_float(row.get("最高", row.get("high", 0)), 0.0) or 0.0,
                            low=_safe_float(row.get("最低", row.get("low", 0)), 0.0) or 0.0,
                            close=_safe_float(row.get("收盘", row.get("close", 0)), 0.0) or 0.0,
                            volume=_safe_float(row.get("成交量", row.get("volume", 0)), 0.0) or 0.0,
                            amount=_safe_float(row.get("成交额", row.get("amount", 0)), 0.0) or 0.0,
                            change_pct=_safe_float(row.get("涨跌幅", 0), 0.0) or 0.0,
                        )
                    )
                except Exception:
                    continue
            self._cache.set_sync(key, [b.model_dump() for b in bars], TTL_REALTIME)
            return bars
        except Exception as exc:
            logger.warning("AKShare get_intraday(%s, %s) failed: %s", code, period, exc)
            return []

    # ------------------------------------------------------------------
    # Limit-up / limit-down pool
    # ------------------------------------------------------------------

    def get_limit_pool(
        self,
        trade_date: str | None = None,
        top_n: int = 50,
    ) -> dict[str, Any]:
        """Return today's limit-up and limit-down stock pools."""
        if not trade_date:
            trade_date = datetime.now().strftime("%Y%m%d")
        else:
            trade_date = trade_date.replace("-", "").replace("/", "")
        key = f"akshare:limit_pool:{trade_date}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            up_df = ak.stock_zt_pool_em(date=trade_date)
            up_items = up_df.head(top_n).to_dict(orient="records") if up_df is not None and not up_df.empty else []
            down_items: list[dict] = []
            for fn in ("stock_zt_pool_dtgc_em", "stock_dt_pool_em"):
                func = getattr(ak, fn, None)
                if func is None:
                    continue
                try:
                    d_df = func(date=trade_date)
                    if d_df is not None and not d_df.empty:
                        down_items = d_df.head(top_n).to_dict(orient="records")
                        break
                except Exception:
                    continue
            result: dict[str, Any] = {
                "date": trade_date,
                "up_count": len(up_items),
                "down_count": len(down_items),
                "up_items": up_items,
                "down_items": down_items,
            }
            self._cache.set_sync(key, result, TTL_REALTIME)
            return result
        except Exception as exc:
            logger.warning("AKShare get_limit_pool(%s) failed: %s", trade_date, exc)
            return {"date": trade_date, "up_count": 0, "down_count": 0, "up_items": [], "down_items": []}

    # ------------------------------------------------------------------
    # Financial news
    # ------------------------------------------------------------------

    def get_news(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Return latest financial news headlines."""
        key = f"akshare:news:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            try:
                df = ak.stock_news_em(symbol="")
            except Exception:
                df = ak.stock_news_em()
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_news failed: %s", exc)
            return []

    def get_stock_news(self, code: str, top_n: int = 10) -> list[dict[str, Any]]:
        """Return latest news for a specific stock."""
        key = f"akshare:stock_news:{code}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_news_em(symbol=code)
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_stock_news(%s) failed: %s", code, exc)
            return []

    # ------------------------------------------------------------------
    # Research reports
    # ------------------------------------------------------------------

    def get_research_reports(self, code: str, top_n: int = 10) -> list[dict[str, Any]]:
        """Return latest analyst research reports for a stock."""
        key = f"akshare:research:{code}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_research_report_em(symbol=code)
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_RESEARCH)
            return records
        except Exception as exc:
            logger.warning("AKShare get_research_reports(%s) failed: %s", code, exc)
            return []

    # ------------------------------------------------------------------
    # Market-level capital flow (north-bound + aggregate)
    # ------------------------------------------------------------------

    def get_market_money_flow(
        self,
        top_n: int = 20,
        trade_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return aggregate market capital flow / north-bound data."""
        if not trade_date:
            trade_date = datetime.now().strftime("%Y%m%d")
        else:
            trade_date = trade_date.replace("-", "").replace("/", "")
        key = f"akshare:market_flow:{trade_date}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            candidates = [
                ("stock_market_fund_flow", {}),
                ("stock_hsgt_fund_flow_summary_em", {}),
                ("stock_hsgt_north_net_flow_in_em", {}),
            ]
            df = None
            for fn_name, kwargs in candidates:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                try:
                    df = func(**kwargs)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_market_money_flow failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Sector-level capital flow
    # ------------------------------------------------------------------

    def get_sector_money_flow(self, top_n: int = 20) -> list[dict[str, Any]]:
        """Return sector/industry capital flow ranking."""
        key = f"akshare:sector_flow:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            candidates = [
                ("stock_sector_fund_flow_rank", {"indicator": "今日", "sector_type": "行业资金流"}),
                ("stock_sector_fund_flow_rank", {"sector_type": "行业资金流"}),
                ("stock_fund_flow_industry", {"symbol": "今日"}),
                ("stock_fund_flow_industry", {}),
            ]
            df = None
            for fn_name, kwargs in candidates:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                try:
                    df = func(**kwargs)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_sector_money_flow failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Sector analysis (industry / concept ranking)
    # ------------------------------------------------------------------

    def get_sector_analysis(
        self,
        sector_type: str = "industry",
        top_n: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return top-gaining and top-dropping sectors.

        sector_type: 'industry' or 'concept'
        Returns {'top_gain': [...], 'top_drop': [...]}
        """
        normalized = "概念" if sector_type in {"concept", "概念"} else "行业"
        key = f"akshare:sector_analysis:{normalized}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            spot_indicator = "概念" if normalized == "概念" else "新浪行业"
            candidates = [
                ("stock_sector_name_code", {"indicator": "今日涨跌幅", "sector_type": normalized}),
                ("stock_sector_name_code", {"sector_type": normalized}),
                ("stock_sector_spot", {"indicator": spot_indicator}),
            ]
            df = None
            for fn_name, kwargs in candidates:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                try:
                    df = func(**kwargs)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                return {"top_gain": [], "top_drop": []}
            records = df.to_dict(orient="records")

            def _pct(row: dict) -> float:
                for col in ("涨跌幅", "今日涨跌幅", "涨跌幅%", "涨跌"):
                    v = _safe_float(row.get(col))
                    if v is not None:
                        return v
                return 0.0

            records_sorted = sorted(records, key=_pct, reverse=True)
            result: dict[str, list[dict[str, Any]]] = {
                "top_gain": records_sorted[:top_n],
                "top_drop": records_sorted[-top_n:][::-1],
            }
            self._cache.set_sync(key, result, TTL_INDUSTRY)
            return result
        except Exception as exc:
            logger.warning("AKShare get_sector_analysis(%s) failed: %s", sector_type, exc)
            return {"top_gain": [], "top_drop": []}

    # ------------------------------------------------------------------
    # Margin trading + Dragon-Tiger board
    # ------------------------------------------------------------------

    def get_margin_lhb(
        self,
        code: Optional[str] = None,
        trade_date: str | None = None,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """Return margin trading details and dragon-tiger board entries."""
        if not trade_date:
            trade_date = datetime.now().strftime("%Y%m%d")
        else:
            trade_date = trade_date.replace("-", "").replace("/", "")
        key = f"akshare:margin_lhb:{code or 'all'}:{trade_date}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            # Margin
            margin_items: list[dict] = []
            for fn_name, kwargs_list in [
                ("stock_margin_detail_em", [{"date": trade_date}, {}]),
                ("stock_margin_detail", [{"date": trade_date}]),
            ]:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                for kw in kwargs_list:
                    try:
                        df = func(**kw)
                        if df is not None and not df.empty:
                            margin_items = df.head(top_n * 5).to_dict(orient="records")
                            if code:
                                margin_items = [
                                    r for r in margin_items
                                    if isinstance(r, dict)
                                    and any(code in str(r.get(c, "")) for c in ("代码", "股票代码", "证券代码"))
                                ]
                            margin_items = margin_items[:top_n]
                            break
                    except Exception:
                        continue
                if margin_items:
                    break
            # LHB dragon-tiger
            lhb_items: list[dict] = []
            for fn_name, kwargs_list in [
                ("stock_lhb_detail_em", [{"start_date": trade_date, "end_date": trade_date}, {}]),
                ("stock_lhb_ggtj_sina", [{"symbol": "5"}, {}]),
            ]:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                for kw in kwargs_list:
                    try:
                        df = func(**kw)
                        if df is not None and not df.empty:
                            lhb_items = df.head(top_n * 5).to_dict(orient="records")
                            if code:
                                lhb_items = [
                                    r for r in lhb_items
                                    if isinstance(r, dict)
                                    and any(code in str(r.get(c, "")) for c in ("代码", "股票代码", "证券代码"))
                                ]
                            lhb_items = lhb_items[:top_n]
                            break
                    except Exception:
                        continue
                if lhb_items:
                    break
            result: dict[str, Any] = {
                "date": trade_date,
                "code": code,
                "margin_items": margin_items,
                "lhb_items": lhb_items,
            }
            self._cache.set_sync(key, result, TTL_REALTIME)
            return result
        except Exception as exc:
            logger.warning("AKShare get_margin_lhb failed: %s", exc)
            return {"date": trade_date, "code": code, "margin_items": [], "lhb_items": []}

    # ------------------------------------------------------------------
    # Fund / ETF
    # ------------------------------------------------------------------

    def get_fund_etf(
        self,
        symbol: str = "159915",
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """Return ETF spot data or open fund daily NAV list."""
        key = f"akshare:fund_etf:{symbol}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            candidates = [
                ("fund_etf_spot_em", {}),
                ("fund_open_fund_daily_em", {}),
            ]
            df = None
            for fn_name, kwargs in candidates:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                try:
                    df = func(**kwargs)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_FINANCIAL)
            return records
        except Exception as exc:
            logger.warning("AKShare get_fund_etf(%s) failed: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------
    # Convertible bond
    # ------------------------------------------------------------------

    def get_convertible_bond(self, top_n: int = 50) -> list[dict[str, Any]]:
        """Return convertible bond realtime spot data."""
        key = f"akshare:cb_spot:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            candidates = [
                ("bond_zh_hs_cov_spot", {}),
                ("bond_cov_jsl", {}),
            ]
            df = None
            for fn_name, kwargs in candidates:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                try:
                    df = func(**kwargs)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_convertible_bond failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # HK market
    # ------------------------------------------------------------------

    def get_hk_quote(
        self,
        symbol: Optional[str] = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """Return Hong Kong stock market quotes."""
        key = f"akshare:hk_quote:{symbol or 'all'}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_hk_spot_em()
            if df is None or df.empty:
                return []
            records = df.to_dict(orient="records")
            if symbol:
                records = [
                    r for r in records
                    if isinstance(r, dict)
                    and any(symbol in str(r.get(c, "")) for c in ("代码", "名称", "symbol"))
                ]
            records = records[:top_n]
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_hk_quote failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # US market
    # ------------------------------------------------------------------

    def get_us_quote(
        self,
        symbol: Optional[str] = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """Return US stock market quotes."""
        key = f"akshare:us_quote:{symbol or 'all'}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            df = ak.stock_us_spot_em()
            if df is None or df.empty:
                return []
            records = df.to_dict(orient="records")
            if symbol:
                records = [
                    r for r in records
                    if isinstance(r, dict)
                    and any(symbol.lower() in str(r.get(c, "")).lower() for c in ("代码", "名称", "symbol"))
                ]
            records = records[:top_n]
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_us_quote failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Futures
    # ------------------------------------------------------------------

    def get_futures(
        self,
        symbol: Optional[str] = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """Return futures main-contract realtime data."""
        key = f"akshare:futures:{symbol or 'all'}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            candidates = [
                ("futures_display_main_sina", {}),
                ("futures_main_sina", {"symbol": symbol or "IF0"}),
            ]
            df = None
            for fn_name, kwargs in candidates:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                try:
                    df = func(**kwargs)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                return []
            records = df.to_dict(orient="records")
            if symbol:
                records = [
                    r for r in records
                    if isinstance(r, dict)
                    and any(symbol.upper() in str(r.get(c, "")).upper() for c in ("代码", "symbol", "品种"))
                ]
            records = records[:top_n]
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_futures(%s) failed: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------

    def get_options(
        self,
        symbol: Optional[str] = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """Return options realtime data."""
        key = f"akshare:options:{symbol or 'all'}:{top_n}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            import akshare as ak
            akshare_limiter.acquire_sync()
            candidates = [
                ("option_current_em", {}),
                ("option_cffex_hs300_spot_sina", {}),
                ("option_finance_board", {"symbol": symbol or "华夏上证50ETF期权"}),
            ]
            df = None
            for fn_name, kwargs in candidates:
                func = getattr(ak, fn_name, None)
                if func is None:
                    continue
                try:
                    df = func(**kwargs)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                return []
            records = df.head(top_n).to_dict(orient="records")
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("AKShare get_options(%s) failed: %s", symbol, exc)
            return []
