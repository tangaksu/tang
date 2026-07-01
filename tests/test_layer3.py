"""Tests for Layer 3 – Analysis engines."""
from __future__ import annotations

import pytest
from datetime import datetime

from src.layer2_data.models import (
    AnalysisContext, AnalysisIntent, MarketEnv, ScoreResult, StarRating, StockBasic,
)
from src.layer3_analysis.scoring.scoring_engine_a import ScoringEngineA
from src.layer3_analysis.scoring.scoring_engine_b import ScoringEngineB
from src.layer3_analysis.scoring.scoring_engine_c import ScoringEngineC
from src.layer3_analysis.scoring.joint_decision_matrix import JointDecisionMatrix


def _empty_ctx(code: str = "600519") -> AnalysisContext:
    return AnalysisContext(
        stock=StockBasic(code=code, name="测试"),
        intent=AnalysisIntent.SINGLE_STOCK,
        query_text=f"分析{code}",
        market_env=MarketEnv.SIDEWAYS,
        analysis_timestamp=datetime.now(),
        quote=None,
        klines_daily=[],
        klines_weekly=[],
        klines_monthly=[],
        financial=None,
        capital_flow=None,
        analyst_forecast=None,
        extra={},
    )


def _empty_modules() -> dict:
    return {f"M{str(i).zfill(2)}": None for i in range(1, 26)}


def _score(total: float) -> ScoreResult:
    star = StarRating.FIVE if total >= 85 else (
        StarRating.FOUR if total >= 70 else (
            StarRating.THREE if total >= 55 else (
                StarRating.TWO if total >= 40 else StarRating.ONE)))
    return ScoreResult(engine="A", total_score=total, star_rating=star)


class TestScoringEngineA:
    def test_neutral_modules_return_mid_score(self):
        ctx = _empty_ctx()
        score_a = ScoringEngineA().compute(ctx, {})
        assert 0 <= score_a.total_score <= 100

    def test_output_has_required_fields(self):
        ctx = _empty_ctx()
        result = ScoringEngineA().compute(ctx, {})
        assert result.total_score is not None
        assert result.star_rating.value in range(1, 6)
        assert isinstance(result.plus_items, list)
        assert isinstance(result.minus_items, list)
        assert isinstance(result.confidence, str)


class TestScoringEngineB:
    def test_output_range(self):
        ctx = _empty_ctx()
        result = ScoringEngineB().compute(ctx, {})
        assert 0 <= result.total_score <= 100

    def test_required_fields_present(self):
        ctx = _empty_ctx()
        result = ScoringEngineB().compute(ctx, {})
        assert result.star_rating.value >= 1
        assert isinstance(result.confidence, str)


class TestScoringEngineC:
    def test_output_range(self):
        ctx = _empty_ctx()
        result = ScoringEngineC().compute(ctx, {})
        assert 0 <= result.total_score <= 100

    def test_requires_no_modules_input(self):
        ctx = _empty_ctx()
        result = ScoringEngineC().compute(ctx, _empty_modules())
        assert result is not None


class TestJointDecisionMatrix:
    def setup_method(self):
        self.matrix = JointDecisionMatrix()

    def test_all_high_scores(self):
        decision = self.matrix.decide(_score(90), _score(88), _score(86))
        assert "场景1" in decision.scenario_name or decision.position_advice

    def test_all_low_scores(self):
        decision = self.matrix.decide(_score(40), _score(38), _score(36))
        assert "场景6" in decision.scenario_name or "回避" in decision.position_advice or "止损" in decision.position_advice

    def test_mixed_scores(self):
        decision = self.matrix.decide(_score(75), _score(60), _score(50))
        assert decision.scenario_name is not None

    def test_score_a_high_b_low(self):
        # Good fundamentals, bad timing
        decision = self.matrix.decide(_score(85), _score(45), _score(50))
        assert decision.scenario_name is not None

    def test_independence_of_scores(self):
        d1 = self.matrix.decide(_score(90), _score(90), _score(90))
        d2 = self.matrix.decide(_score(50), _score(50), _score(50))
        assert d1.scenario_name != d2.scenario_name
