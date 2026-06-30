"""Layer 1 – Task orchestrator: coordinate all 25 analysis modules in batches."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from ..layer2_data.models import AnalysisContext, ModuleOutput
from ..layer3_analysis.base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

# Batch definitions (processing order; batches within same group can run in parallel)
_BATCH_A = ["M01", "M02", "M03", "M04", "M05"]          # 基本面
_BATCH_B = ["M06", "M07", "M08", "M09", "M10", "M11"]   # 市场面
_BATCH_C = ["M12", "M13", "M19", "M20", "M21", "M22"]   # 深度分析
_BATCH_D = ["M14", "M15", "M23", "M24", "M25"]           # 综合决策


class TaskOrchestrator:
    """Run analysis modules in four dependency-ordered batches.

    Modules within each batch are executed concurrently using a thread pool
    (necessary because AKShare calls are synchronous / blocking I/O).
    """

    def __init__(
        self,
        analyzers: dict[str, BaseAnalyzer],
        max_workers: int = 8,
    ) -> None:
        self._analyzers = analyzers
        self._max_workers = max_workers

    def run(self, ctx: AnalysisContext) -> dict[str, ModuleOutput]:
        """Execute all batches and return all module outputs keyed by module ID."""
        results: dict[str, ModuleOutput] = {}

        for batch_name, batch_ids in [
            ("A-基本面", _BATCH_A),
            ("B-市场面", _BATCH_B),
            ("C-深度分析", _BATCH_C),
            ("D-综合决策", _BATCH_D),
        ]:
            logger.info("[Orchestrator] Running batch %s: %s", batch_name, batch_ids)
            batch_results = self._run_batch(ctx, batch_ids)
            results.update(batch_results)

        return results

    def _run_batch(
        self, ctx: AnalysisContext, module_ids: list[str]
    ) -> dict[str, ModuleOutput]:
        outputs: dict[str, ModuleOutput] = {}
        ids_to_run = [mid for mid in module_ids if mid in self._analyzers]

        if not ids_to_run:
            return outputs

        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(ids_to_run))) as pool:
            future_to_id = {
                pool.submit(self._analyzers[mid].safe_analyze, ctx): mid
                for mid in ids_to_run
            }
            for future in as_completed(future_to_id):
                mid = future_to_id[future]
                try:
                    outputs[mid] = future.result()
                    logger.debug("[Orchestrator] %s completed: score=%.1f",
                                 mid, outputs[mid].module_score)
                except Exception as exc:
                    logger.error("[Orchestrator] %s raised unexpected error: %s", mid, exc)
        return outputs


def build_default_orchestrator() -> TaskOrchestrator:
    """Construct an orchestrator with all 25 analyzers registered."""
    from ..layer3_analysis.modules import (
        BusinessAnalyzer, FinancialAnalyzer, GovernanceAnalyzer,
        IndustryAnalyzer, ValuationAnalyzer, TechnicalAnalyzer,
        CapitalFlowAnalyzer, SentimentAnalyzer, ExpectationAnalyzer,
        MarketStyleAnalyzer, LiquidityAnalyzer, CatalystAnalyzer,
        HistoryAnalyzer, RiskControlAnalyzer, PeerComparisonAnalyzer,
        EarningsForecastAnalyzer, ProfitElasticityAnalyzer,
        CapitalAllocationAnalyzer, DriverAttributionAnalyzer,
        StressTestAnalyzer, PositionFitAnalyzer, ExitMechanismAnalyzer,
    )

    analyzers: dict[str, BaseAnalyzer] = {
        "M01": BusinessAnalyzer(),
        "M02": FinancialAnalyzer(),
        "M03": GovernanceAnalyzer(),
        "M04": IndustryAnalyzer(),
        "M05": ValuationAnalyzer(),
        "M06": TechnicalAnalyzer(),
        "M07": CapitalFlowAnalyzer(),
        "M08": SentimentAnalyzer(),
        "M09": ExpectationAnalyzer(),
        "M10": MarketStyleAnalyzer(),
        "M11": LiquidityAnalyzer(),
        "M12": CatalystAnalyzer(),
        "M13": HistoryAnalyzer(),
        "M14": RiskControlAnalyzer(),
        "M15": PeerComparisonAnalyzer(),
        # M16/M17/M18 are score engine wrappers, handled by ReportAssembler
        "M19": EarningsForecastAnalyzer(),
        "M20": ProfitElasticityAnalyzer(),
        "M21": CapitalAllocationAnalyzer(),
        "M22": DriverAttributionAnalyzer(),
        "M23": StressTestAnalyzer(),
        "M24": PositionFitAnalyzer(),
        "M25": ExitMechanismAnalyzer(),
    }
    return TaskOrchestrator(analyzers=analyzers)
