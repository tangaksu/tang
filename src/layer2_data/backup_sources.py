"""Layer 2 – Backup HTTP data sources (东财/同花顺/新浪/腾讯)."""
from __future__ import annotations

import logging
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
                "&fields=f43,f44,f45,f46,f47,f48,f168,f116,f117,f162,f167,f9"
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
                    return float(raw) / 100 if field in ("f43",) else float(raw)
                except (TypeError, ValueError):
                    return None

            quote = QuoteData(
                code=code,
                name="",
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
            prefix = "sh" if code.startswith("6") else "sz"
            url = (
                f"https://money.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary"
                f"/stockid/{code}/displaytype/4.phtml"
            )
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            # Sina returns HTML; basic extraction
            text = resp.text
            summary = FinancialSummary()
            # Minimal parsing – real implementation would use BeautifulSoup
            if "每股收益" in text:
                pass  # placeholder for table parsing
            self._cache.set_sync(key, summary.model_dump(), TTL_REALTIME)
            return summary
        except Exception as exc:
            logger.warning("Sina backup financial(%s) failed: %s", code, exc)
            return None


class FallbackChain:
    """Try primary source first; fall back to backup sources in order."""

    def __init__(self, cache: DataCache | None = None) -> None:
        self._backup = BackupSources(cache)

    def get_quote(self, code: str, primary_result: QuoteData | None) -> QuoteData | None:
        if primary_result is not None:
            return primary_result
        logger.info("Falling back to East-Money quote for %s", code)
        return self._backup.get_quote_em(code)

    def get_financial(
        self, code: str, primary_result: FinancialSummary | None
    ) -> FinancialSummary | None:
        if primary_result is not None:
            return primary_result
        logger.info("Falling back to Sina financial for %s", code)
        return self._backup.get_financial_sina(code)
