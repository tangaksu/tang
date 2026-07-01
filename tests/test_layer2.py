"""Tests for Layer 2 – Data layer."""
from __future__ import annotations

import pytest

from src.layer2_data.data_cache import DataCache
from src.layer2_data.data_normalizer import DataNormalizer
from src.layer2_data.multi_source_validator import MultiSourceValidator
from src.layer2_data.rate_limiter import RateLimiter


class TestDataCache:
    def setup_method(self):
        # Use in-memory path
        self.cache = DataCache(db_path=":memory:")

    def test_set_and_get(self):
        self.cache.set_sync("key1", {"price": 100.0}, ttl=60)
        result = self.cache.get_sync("key1")
        assert result == {"price": 100.0}

    def test_get_missing_returns_none(self):
        assert self.cache.get_sync("nonexistent") is None

    def test_expired_entry_returns_none(self):
        import time
        self.cache.set_sync("key_exp", "value", ttl=0.001)
        time.sleep(0.01)
        assert self.cache.get_sync("key_exp") is None

    def test_overwrite(self):
        self.cache.set_sync("key2", "old", ttl=60)
        self.cache.set_sync("key2", "new", ttl=60)
        assert self.cache.get_sync("key2") == "new"


class TestDataNormalizer:
    def setup_method(self):
        self.dn = DataNormalizer()

    def test_normalize_code_with_suffix(self):
        assert DataNormalizer.normalize_code("600519.SH") == "600519"
        assert DataNormalizer.normalize_code("000858SZ") == "000858"

    def test_normalize_code_padding(self):
        assert DataNormalizer.normalize_code("519") == "000519"

    def test_normalize_pct_decimal(self):
        assert DataNormalizer.normalize_pct(0.25, is_decimal=True) == 25.0

    def test_normalize_pct_already_pct(self):
        assert DataNormalizer.normalize_pct(25.0, is_decimal=False) == 25.0

    def test_normalize_amount_yuan_to_yi(self):
        val = DataNormalizer.normalize_amount_to_yi(1e8, source_unit="yuan")
        assert val == pytest.approx(1.0)

    def test_normalize_date_str(self):
        d = DataNormalizer.normalize_date("2024-06-30")
        assert d is not None
        assert d.year == 2024
        assert d.month == 6

    def test_normalize_date_none(self):
        assert DataNormalizer.normalize_date(None) is None


class TestMultiSourceValidator:
    def setup_method(self):
        self.validator = MultiSourceValidator()

    def test_price_no_conflict(self):
        result = self.validator.validate_price({"akshare": 100.0, "em": 100.5})
        assert result.is_valid
        assert result.chosen_value == 100.0

    def test_price_conflict(self):
        result = self.validator.validate_price({"akshare": 100.0, "em": 115.0})
        assert not result.is_valid
        assert len(result.conflicts) >= 1

    def test_all_none(self):
        result = self.validator.validate_price({"akshare": None, "em": None})
        assert not result.is_valid

    def test_pe_missing(self):
        result = self.validator.validate_pe({})
        assert result.is_valid
        assert result.chosen_value is None


class TestRateLimiter:
    def test_sync_no_block_within_limit(self):
        import time
        limiter = RateLimiter(max_calls=100, period=1.0)
        start = time.monotonic()
        for _ in range(10):
            limiter.acquire_sync()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # Should complete quickly

    def test_sync_blocks_when_over_limit(self):
        import time
        limiter = RateLimiter(max_calls=2, period=0.5)
        start = time.monotonic()
        for _ in range(3):
            limiter.acquire_sync()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.3  # Should have waited
