"""Layer 1 – Special scene router: apply intent-specific adjustments."""
from __future__ import annotations

import logging

from ..layer2_data.models import AnalysisContext, AnalysisIntent, StockBasic

logger = logging.getLogger(__name__)


class SpecialSceneRouter:
    """Adjust AnalysisContext settings based on the detected intent.

    Rules from V5.0 spec Section 13:
    - ST: 现价买入性价比评分上限80分，仓位上限15%，弱化正面建议
    - 新股/次新股: 弱化历史财务和长期估值对比，提高题材稀缺性/资金情绪权重
    - 持仓分析: 新增成本与现价比较，输出解套/锁盈/做T路径
    - 多股对比: 强制调用同业对标模块
    - 指数: 剔除个股财务/股权治理，替换为板块估值/景气/拥挤度
    """

    def route(self, ctx: AnalysisContext) -> AnalysisContext:
        intent = ctx.intent

        if intent == AnalysisIntent.ST_STOCK:
            logger.info("[Router] ST股场景：评分上限80分，仓位上限15%%")
            ctx.stock.is_st = True
            ctx.extra["score_b_cap"] = 80.0
            ctx.extra["position_limit"] = "15%"
            ctx.extra["disable_long_term_positive"] = True

        elif intent == AnalysisIntent.NEW_STOCK:
            logger.info("[Router] 新股/次新股场景：弱化长期估值，提升情绪权重")
            ctx.stock.is_new_stock = True
            ctx.extra["weight_sentiment_boost"] = 1.4
            ctx.extra["weight_valuation_penalty"] = 0.6
            ctx.extra["disable_historical_valuation"] = True

        elif intent == AnalysisIntent.POSITION_REVIEW:
            logger.info("[Router] 持仓分析场景")
            ctx.extra["is_position_review"] = True

        elif intent == AnalysisIntent.MULTI_STOCK_COMPARE:
            logger.info("[Router] 多股对比场景：强制调用M15同业对标")
            ctx.extra["force_peer_comparison"] = True

        elif intent == AnalysisIntent.INDEX:
            logger.info("[Router] 指数/板块分析场景")
            ctx.extra["is_index_analysis"] = True
            ctx.extra["disable_financial_modules"] = ["M02", "M03"]

        return ctx
