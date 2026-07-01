"""Tests for Layer 1 – Orchestration."""
from __future__ import annotations

import pytest

from src.layer1_orchestration.stock_query_parser import StockQueryParser
from src.layer1_orchestration.intent_classifier import IntentClassifier
from src.layer1_orchestration.market_env_detector import MarketEnvDetector
from src.layer2_data.models import AnalysisIntent, MarketEnv


class TestStockQueryParser:
    def setup_method(self):
        self.parser = StockQueryParser()

    def test_parse_explicit_code(self):
        assert self.parser.parse("分析600519走势") == "600519"

    def test_parse_maotai_by_name(self):
        assert self.parser.parse("贵州茅台现在能买吗") == "600519"

    def test_parse_byd(self):
        assert self.parser.parse("比亚迪002594最近怎么样") == "002594"

    def test_parse_ludi_xiebo(self):
        assert self.parser.parse("请帮我分析一下绿的谐波") == "688522"

    def test_parse_ludi_xiebo_short(self):
        assert self.parser.parse("绿的最近走势如何") == "688522"

    def test_parse_no_match(self):
        assert self.parser.parse("今天天气不错") is None

    def test_extract_multiple_codes(self):
        codes = self.parser.extract_all_codes("对比600519和000858")
        assert "600519" in codes
        assert "000858" in codes


class TestIntentClassifier:
    def setup_method(self):
        self.clf = IntentClassifier()

    def test_single_stock(self):
        assert self.clf.classify("分析贵州茅台") == AnalysisIntent.SINGLE_STOCK

    def test_position_review(self):
        assert self.clf.classify("我持有300750，要不要减仓") == AnalysisIntent.POSITION_REVIEW

    def test_compare(self):
        intent = self.clf.classify("600519和000858对比", codes=["600519", "000858"])
        assert intent == AnalysisIntent.MULTI_STOCK_COMPARE

    def test_st_stock(self):
        assert self.clf.classify("分析*ST长油") == AnalysisIntent.ST_STOCK

    def test_stock_selection(self):
        assert self.clf.classify("帮我选股，高股息防御型") == AnalysisIntent.STOCK_SELECTION

    def test_index(self):
        assert self.clf.classify("沪深300最近走势如何") == AnalysisIntent.INDEX


class TestMarketEnvDetector:
    def setup_method(self):
        self.detector = MarketEnvDetector()

    def test_no_data_returns_sideways(self):
        assert self.detector.detect(None) == MarketEnv.SIDEWAYS

    def test_insufficient_data_returns_sideways(self):
        assert self.detector.detect([3000.0] * 10) == MarketEnv.SIDEWAYS

    def test_bull_market(self):
        # Rising trend: start low, end high
        closes = [3000 + i * 10 for i in range(60)]  # +50% over 60 days
        result = self.detector.detect(closes)
        assert result == MarketEnv.BULL

    def test_bear_market(self):
        closes = [4000 - i * 10 for i in range(60)]  # -37.5% over 60 days
        result = self.detector.detect(closes)
        assert result == MarketEnv.BEAR

    def test_sideways_market(self):
        # Flat
        closes = [3300.0] * 60
        result = self.detector.detect(closes)
        assert result == MarketEnv.SIDEWAYS
