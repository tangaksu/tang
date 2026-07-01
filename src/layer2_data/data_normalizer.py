"""Layer 2 – Data normalizer: unify field names, units, and date formats."""
from __future__ import annotations

from datetime import date

import pandas as pd


class DataNormalizer:
    """Convert raw API responses into standardized internal models."""

    @staticmethod
    def normalize_amount_to_yi(value: float | None, source_unit: str = "yuan") -> float | None:
        """Convert monetary value to 亿元."""
        if value is None:
            return None
        divisors = {"yuan": 1e8, "wan": 1e4, "yi": 1.0, "wan_yuan": 1e4}
        divisor = divisors.get(source_unit, 1e8)
        return value / divisor

    @staticmethod
    def normalize_pct(value: float | None, is_decimal: bool = False) -> float | None:
        """Ensure percentage is in 0-100 scale."""
        if value is None:
            return None
        return value * 100 if is_decimal and abs(value) <= 1.0 else value

    @staticmethod
    def normalize_date(raw: str | date | None) -> date | None:
        if raw is None:
            return None
        if isinstance(raw, date):
            return raw
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
            try:
                return pd.to_datetime(raw, format=fmt).date()
            except Exception:
                continue
        try:
            return pd.to_datetime(raw).date()
        except Exception:
            return None

    @staticmethod
    def normalize_code(raw: str) -> str:
        """Strip exchange suffix and pad to 6 digits."""
        code = raw.strip().upper()
        for suffix in (".SH", ".SZ", ".BJ", "SH", "SZ"):
            if code.endswith(suffix):
                code = code[: -len(suffix)]
        return code.zfill(6)
