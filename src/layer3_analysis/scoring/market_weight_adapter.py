"""Layer 3 – Market weight adapter: dynamic weight adjustment by market env."""
from __future__ import annotations

from dataclasses import dataclass

from ...layer2_data.models import MarketEnv


@dataclass
class WeightProfile:
    """Multipliers applied to module scores before aggregating."""
    technical: float = 1.0
    capital_flow: float = 1.0
    sentiment: float = 1.0
    financial: float = 1.0
    valuation_safety: float = 1.0
    liquidity: float = 1.0
    range_structure: float = 1.0
    execution_certainty: float = 1.0


class MarketWeightAdapter:
    """Return weight multipliers based on the current market environment.

    Rules (from V5.0 spec Section 3.11):
    - 弱市/熊市: raise financial, valuation_safety, liquidity; lower sentiment
    - 强市/牛市: raise technical, capital_flow, sentiment; loosen valuation tolerance
    - 震荡市:    raise range_structure, execution_certainty, T-trade weight
    """

    _PROFILES: dict[MarketEnv, WeightProfile] = {
        MarketEnv.BULL: WeightProfile(
            technical=1.20,
            capital_flow=1.15,
            sentiment=1.20,
            financial=0.85,
            valuation_safety=0.80,
            liquidity=1.00,
            range_structure=0.90,
            execution_certainty=1.00,
        ),
        MarketEnv.BEAR: WeightProfile(
            technical=0.85,
            capital_flow=0.90,
            sentiment=0.70,
            financial=1.20,
            valuation_safety=1.25,
            liquidity=1.20,
            range_structure=1.00,
            execution_certainty=1.10,
        ),
        MarketEnv.SIDEWAYS: WeightProfile(
            technical=1.00,
            capital_flow=1.00,
            sentiment=0.90,
            financial=1.00,
            valuation_safety=1.00,
            liquidity=1.00,
            range_structure=1.20,
            execution_certainty=1.20,
        ),
    }

    def get_profile(self, env: MarketEnv) -> WeightProfile:
        return self._PROFILES.get(env, WeightProfile())

    def apply(self, raw_score: float, multiplier: float, max_score: float) -> float:
        """Apply multiplier and clamp to [0, max_score]."""
        return min(max(raw_score * multiplier, 0.0), max_score)
