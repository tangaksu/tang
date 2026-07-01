"""Layer 1 – Market environment detector."""
from __future__ import annotations

import logging

from ..layer2_data.models import MarketEnv

logger = logging.getLogger(__name__)

# Index code for CSI 300 (沪深300)
_INDEX_CODE = "000300"


class MarketEnvDetector:
    """Detect current market environment (bull/bear/sideways) using index data.

    Uses the 60-day trend of the CSI 300 index as a proxy for overall market.
    """

    def detect(self, index_closes: list[float] | None = None) -> MarketEnv:
        """Return market environment based on recent index price action.

        Parameters
        ----------
        index_closes:
            Recent daily close prices of the broad market index (oldest first).
            If *None*, returns SIDEWAYS as default.
        """
        if not index_closes or len(index_closes) < 20:
            logger.info("[MarketEnv] Insufficient data, defaulting to SIDEWAYS")
            return MarketEnv.SIDEWAYS

        closes = index_closes[-60:] if len(index_closes) >= 60 else index_closes
        n = len(closes)
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes) / n

        cur = closes[-1]
        change_60d = (cur - closes[0]) / max(closes[0], 1e-9)

        if cur > ma20 > ma60 and change_60d > 0.08:
            env = MarketEnv.BULL
        elif cur < ma20 < ma60 and change_60d < -0.08:
            env = MarketEnv.BEAR
        else:
            env = MarketEnv.SIDEWAYS

        logger.info(
            "[MarketEnv] cur=%.2f ma20=%.2f ma60=%.2f 60d_chg=%.1f%% → %s",
            cur, ma20, ma60, change_60d * 100, env.value,
        )
        return env
