"""Layer 2 – Backup HTTP data sources (东财/同花顺/新浪/腾讯)."""
from __future__ import annotations

import logging
import re
from typing import Any

import requests

from .data_cache import DataCache, TTL_REALTIME, get_cache
from .models import QuoteData, FinancialSummary
from .rate_limiter import http_limiter

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 10


class BackupSources:
    """Fallback HTTP scrapers for major A-share data portals."""

    def __init__(self, cache: DataCache | None = None) -> None:
        self._cache = cache or get_cache()

    # ------------------------------------------------------------------
    # 东方财富 – real-time quote
    # ------------------------------------------------------------------

    def _em_market_prefix(self, code: str) -> str:
        """East-Money market prefix: 0=深A, 1=沪A, 3=北交所."""
        if code.startswith("6"):
            return "1"
        if code.startswith("8") or code.startswith("4"):
            return "0"  # BSE handled same way
        return "0"

    def get_quote_em(self, code: str) -> QuoteData | None:
        """Fetch real-time quote from East-Money JSON API."""
        key = f"backup:em_quote:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return QuoteData(**cached)
        try:
            http_limiter.acquire_sync()
            secid = f"{self._em_market_prefix(code)}.{code}"
            url = (
                "https://push2.eastmoney.com/api/qt/stock/get"
                f"?secid={secid}"
                "&fields=f43,f44,f45,f46,f47,f48,f168,f116,f117,f162,f167,f9,f170,f57"
                "&ut=bd1d9ddb04089700cf9c27f6f7426281"
            )
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json().get("data", {})
            if not data:
                return None

            def _v(field: str) -> float | None:
                raw = data.get(field)
                if raw is None or raw == "-":
                    return None
                try:
                    # f43=最新价 (×100 in EM API), f170=涨跌幅 (×100)
                    if field in ("f43",):
                        return float(raw) / 100
                    if field in ("f170",):
                        return float(raw) / 100
                    return float(raw)
                except (TypeError, ValueError):
                    return None

            name = str(data.get("f57", "")) or ""
            quote = QuoteData(
                code=code,
                name=name,
                price=(_v("f43") or 0.0),
                change_pct=(_v("f170") or 0.0),
                volume=(_v("f47") or 0.0),
                amount=(_v("f48") or 0.0),
                turnover_rate=(_v("f168") or 0.0),
                market_cap=(_v("f116") or 0.0),
                circulating_cap=(_v("f117") or 0.0),
                pe_ttm=_v("f162"),
                pb=_v("f167"),
            )
            self._cache.set_sync(key, quote.model_dump(), TTL_REALTIME)
            return quote
        except Exception as exc:
            logger.warning("EM backup quote(%s) failed: %s", code, exc)
            return None

    # ------------------------------------------------------------------
    # 腾讯财经 – real-time quote
    # ------------------------------------------------------------------

    def get_quote_tencent(self, code: str) -> QuoteData | None:
        """Fetch real-time quote from Tencent Finance."""
        key = f"backup:tencent_quote:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return QuoteData(**cached)
        try:
            http_limiter.acquire_sync()
            prefix = "sh" if code.startswith("6") else ("bj" if code.startswith(("8", "4")) else "sz")
            url = f"https://qt.gtimg.cn/q={prefix}{code}"
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            # Format: v_sh600519="1~贵州茅台~600519~1800.00~1790.00~..."
            text = resp.text
            m = re.search(r'"([^"]+)"', text)
            if not m:
                return None
            parts = m.group(1).split("~")
            # Tencent field layout (0-indexed):
            # 1=name, 3=price, 4=close_prev, 32=涨跌幅%, 36=成交量(手), 37=成交额(元)
            # 45=总市值, 46=流通市值
            if len(parts) < 46:
                return None

            def _fp(idx: int) -> float | None:
                try:
                    v = float(parts[idx])
                    return v if v != 0 else None
                except (ValueError, IndexError):
                    return None

            name = parts[1] if len(parts) > 1 else ""
            price = _fp(3) or 0.0
            prev_close = _fp(4) or price
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
            if len(parts) > 32:
                try:
                    change_pct = float(parts[32])
                except (ValueError, IndexError):
                    pass
            quote = QuoteData(
                code=code,
                name=name,
                price=price,
                change_pct=change_pct,
                volume=(_fp(36) or 0.0),
                amount=(_fp(37) or 0.0) / 1e4,  # 元→万元
                turnover_rate=0.0,
                market_cap=(_fp(45) or 0.0) / 1e8,   # 元→亿元
                circulating_cap=(_fp(46) or 0.0) / 1e8,
            )
            self._cache.set_sync(key, quote.model_dump(), TTL_REALTIME)
            return quote
        except Exception as exc:
            logger.warning("Tencent backup quote(%s) failed: %s", code, exc)
            return None

    # ------------------------------------------------------------------
    # 东方财富 – K-line (backup)
    # ------------------------------------------------------------------

    def get_kline_em(
        self,
        code: str,
        period: str = "101",
        limit: int = 60,
    ) -> list[dict[str, Any]]:
        """Fetch K-line data from East-Money secid API.

        period: 101=日线, 102=周线, 103=月线, 5/15/30/60=分钟线
        """
        key = f"backup:em_kline:{code}:{period}:{limit}"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            http_limiter.acquire_sync()
            secid = f"{self._em_market_prefix(code)}.{code}"
            url = (
                "https://push2his.eastmoney.com/api/qt/stock/kline/get"
                f"?secid={secid}"
                f"&fields1=f1,f2,f3,f4,f5,f6"
                f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
                f"&klt={period}&fqt=1&lmt={limit}&end=20500101"
            )
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            klines = resp.json().get("data", {}).get("klines", [])
            records = []
            for line in klines:
                parts = line.split(",")
                if len(parts) < 6:
                    continue
                records.append({
                    "日期": parts[0],
                    "开盘": parts[1],
                    "收盘": parts[2],
                    "最高": parts[3],
                    "最低": parts[4],
                    "成交量": parts[5],
                    "成交额": parts[6] if len(parts) > 6 else "",
                    "涨跌幅": parts[8] if len(parts) > 8 else "",
                })
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("EM backup kline(%s) failed: %s", code, exc)
            return []

    # ------------------------------------------------------------------
    # 新浪财经 – financial summary
    # ------------------------------------------------------------------

    def get_financial_sina(self, code: str) -> FinancialSummary | None:
        """Fetch latest financial summary from Sina Finance."""
        key = f"backup:sina_financial:{code}"
        cached = self._cache.get_sync(key)
        if cached:
            return FinancialSummary(**cached)
        try:
            http_limiter.acquire_sync()
            url = (
                f"https://money.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary"
                f"/stockid/{code}/displaytype/4.phtml"
            )
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            text = resp.text
            summary = FinancialSummary()

            def _find(pattern: str) -> float | None:
                m = re.search(pattern, text)
                if m:
                    try:
                        return float(m.group(1).replace(",", ""))
                    except ValueError:
                        pass
                return None

            # ROE
            roe = _find(r"净资产收益率.*?(\d+\.?\d*)\s*%")
            if roe is None:
                roe = _find(r"ROE.*?(\d+\.?\d*)")
            summary.roe = roe

            # Gross margin
            gm = _find(r"毛利率.*?(\d+\.?\d*)\s*%")
            summary.gross_margin = gm

            # Net profit
            np_ = _find(r"净利润.*?(-?\d+[\d,]*\.?\d*)")
            summary.net_profit = np_

            # Revenue
            rev = _find(r"营业收入.*?(-?\d+[\d,]*\.?\d*)")
            summary.revenue = rev

            self._cache.set_sync(key, summary.model_dump(), TTL_REALTIME)
            return summary
        except Exception as exc:
            logger.warning("Sina backup financial(%s) failed: %s", code, exc)
            return None

    # ------------------------------------------------------------------
    # 东方财富 – index spot (backup)
    # ------------------------------------------------------------------

    def get_index_spot_em(self) -> list[dict[str, Any]]:
        """Fetch A-share index spot data from East-Money."""
        key = "backup:em_index_spot"
        cached = self._cache.get_sync(key)
        if cached:
            return cached
        try:
            http_limiter.acquire_sync()
            url = (
                "https://push2.eastmoney.com/api/qt/ulist.np/get"
                "?fltt=2&invt=2&ut=bd1d9ddb04089700cf9c27f6f7426281"
                "&fields=f12,f13,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18"
                "&secids=1.000001,1.000016,0.399001,0.399006,1.000688,0.399005"
            )
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            diff = resp.json().get("data", {}).get("diff", [])
            records = []
            for item in diff:
                records.append({
                    "代码": item.get("f12", ""),
                    "名称": item.get("f14", ""),
                    "最新价": item.get("f2"),
                    "涨跌幅": item.get("f3"),
                    "涨跌额": item.get("f4"),
                    "成交量": item.get("f5"),
                    "成交额": item.get("f6"),
                    "振幅": item.get("f7"),
                    "最高": item.get("f15"),
                    "最低": item.get("f16"),
                    "开盘": item.get("f17"),
                    "昨收": item.get("f18"),
                })
            self._cache.set_sync(key, records, TTL_REALTIME)
            return records
        except Exception as exc:
            logger.warning("EM backup index spot failed: %s", exc)
            return []


class FallbackChain:
    """Try primary source first; fall back to backup sources in order."""

    def __init__(self, cache: DataCache | None = None) -> None:
        self._backup = BackupSources(cache)

    def get_quote(self, code: str, primary_result: QuoteData | None) -> QuoteData | None:
        if primary_result is not None:
            return primary_result
        logger.info("Falling back to East-Money quote for %s", code)
        result = self._backup.get_quote_em(code)
        if result is not None:
            return result
        logger.info("Falling back to Tencent quote for %s", code)
        return self._backup.get_quote_tencent(code)

    def get_financial(
        self, code: str, primary_result: FinancialSummary | None
    ) -> FinancialSummary | None:
        if primary_result is not None:
            return primary_result
        logger.info("Falling back to Sina financial for %s", code)
        return self._backup.get_financial_sina(code)

    def get_index_spot(
        self, primary_result: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        if primary_result:
            return primary_result
        logger.info("Falling back to EM index spot")
        return self._backup.get_index_spot_em()

    def get_kline(
        self,
        code: str,
        primary_result: list[Any] | None,
        period: str = "101",
        limit: int = 60,
    ) -> list[dict[str, Any]]:
        """Return primary kline bars if available; otherwise use EM backup."""
        if primary_result:
            return primary_result  # type: ignore[return-value]
        logger.info("Falling back to EM kline for %s", code)
        return self._backup.get_kline_em(code, period=period, limit=limit)
