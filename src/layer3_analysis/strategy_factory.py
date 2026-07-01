"""Layer 3 – Strategy factory: 8 selection strategies with independent weights."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..layer2_data.models import AnalysisContext, FullReport


class Strategy(str, Enum):
    VALUE_GROWTH = "价值成长"
    HIGH_DIVIDEND = "高股息防御"
    GROWTH_CYCLE = "景气成长"
    TURNAROUND = "困境反转"
    SECTOR_LEADER = "赛道龙头"
    TREND_ACCELERATION = "趋势加速"
    LOW_REBOUND = "低位补涨"
    EVENT_DRIVEN = "事件驱动"


@dataclass
class StrategyWeights:
    """Relative weight multipliers for each strategy (sum need not equal 1)."""
    financial_quality: float = 1.0
    valuation_safety: float = 1.0
    growth_path: float = 1.0
    dividend_quality: float = 1.0
    moat: float = 1.0
    technical: float = 1.0
    capital_flow: float = 1.0
    execution: float = 1.0
    catalyst: float = 1.0
    sentiment: float = 1.0
    risk_event: float = 1.0
    industry_cycle: float = 1.0


_STRATEGY_PROFILES: dict[Strategy, StrategyWeights] = {
    Strategy.VALUE_GROWTH: StrategyWeights(
        financial_quality=1.3, valuation_safety=1.3, moat=1.2,
    ),
    Strategy.HIGH_DIVIDEND: StrategyWeights(
        dividend_quality=1.5, financial_quality=1.2, valuation_safety=1.1,
    ),
    Strategy.GROWTH_CYCLE: StrategyWeights(
        industry_cycle=1.4, growth_path=1.4, technical=1.1,
    ),
    Strategy.TURNAROUND: StrategyWeights(
        financial_quality=1.3, risk_event=1.3, valuation_safety=1.2,
        industry_cycle=1.2,
    ),
    Strategy.SECTOR_LEADER: StrategyWeights(
        moat=1.4, valuation_safety=1.2, industry_cycle=1.2,
    ),
    Strategy.TREND_ACCELERATION: StrategyWeights(
        technical=1.4, capital_flow=1.3, execution=1.3,
    ),
    Strategy.LOW_REBOUND: StrategyWeights(
        valuation_safety=1.4, sentiment=1.2, technical=1.2,
    ),
    Strategy.EVENT_DRIVEN: StrategyWeights(
        catalyst=1.5, execution=1.3,
    ),
}


class StrategyFactory:
    """Adjust scoring weights according to the selected investment strategy."""

    def get_weights(self, strategy: Strategy) -> StrategyWeights:
        return _STRATEGY_PROFILES.get(strategy, StrategyWeights())

    def rank_strategy_fit(self, report: FullReport) -> list[tuple[Strategy, float]]:
        """Score each strategy's fit for the current stock and sort by relevance."""
        sa = report.score_a.total_score if report.score_a else 50.0
        sb = report.score_b.total_score if report.score_b else 50.0
        sc = report.score_c.total_score if report.score_c else 50.0

        fin = report.context.financial

        scores: list[tuple[Strategy, float]] = []

        # Simple heuristic fitness per strategy
        scores.append((Strategy.VALUE_GROWTH, sa * 0.6 + sb * 0.2 + sc * 0.2))
        scores.append((Strategy.HIGH_DIVIDEND, (
            (fin.dividend_yield or 0) * 5 + sa * 0.4 if fin else sa * 0.4
        )))
        scores.append((Strategy.GROWTH_CYCLE, sa * 0.4 + sb * 0.3 + sc * 0.3))
        scores.append((Strategy.TURNAROUND, sa * 0.3 + sb * 0.4 + sc * 0.3))
        scores.append((Strategy.SECTOR_LEADER, sa * 0.5 + sc * 0.5))
        scores.append((Strategy.TREND_ACCELERATION, sb * 0.4 + sc * 0.6))
        scores.append((Strategy.LOW_REBOUND, sb * 0.7 + sc * 0.3))
        scores.append((Strategy.EVENT_DRIVEN, sc * 0.6 + sb * 0.4))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores
