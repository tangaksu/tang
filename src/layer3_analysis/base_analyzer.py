"""Layer 3 – Base analyzer class that all 25 module analyzers inherit."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..layer2_data.models import (
    AnalysisContext,
    EvidenceItem,
    EvidenceStrength,
    FactorTree,
    ModuleOutput,
    StarRating,
)

logger = logging.getLogger(__name__)

_STAR_THRESHOLDS = [
    (0.9, StarRating.FIVE),
    (0.75, StarRating.FOUR),
    (0.6, StarRating.THREE),
    (0.45, StarRating.TWO),
    (0.0, StarRating.ONE),
]


def score_to_star(score: float, max_score: float) -> StarRating:
    ratio = score / max(max_score, 1e-9)
    for threshold, star in _STAR_THRESHOLDS:
        if ratio >= threshold:
            return star
    return StarRating.ONE


class BaseAnalyzer(ABC):
    """Abstract base for all 25 analysis modules.

    Subclasses must implement :meth:`analyze` and define :attr:`MODULE_ID`,
    :attr:`MODULE_TITLE`, :attr:`MAX_SCORE`.
    """

    MODULE_ID: str = "M00"
    MODULE_TITLE: str = "未命名模块"
    MODULE_POSITIONING: str = ""
    MAX_SCORE: float = 10.0

    def __init__(self) -> None:
        self._logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    @abstractmethod
    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        """Run analysis and return structured output."""

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------

    def _base_output(self, score: float, *, conclusion: str = "") -> ModuleOutput:
        star = score_to_star(score, self.MAX_SCORE)
        return ModuleOutput(
            module_id=self.MODULE_ID,
            module_title=self.MODULE_TITLE,
            module_positioning=self.MODULE_POSITIONING,
            core_conclusion=conclusion,
            module_score=score,
            module_max_score=self.MAX_SCORE,
            star_rating=star,
        )

    def _evidence(
        self,
        conclusion: str,
        evidence_type: str,
        strength: EvidenceStrength,
        source: str = "",
    ) -> EvidenceItem:
        return EvidenceItem(
            conclusion=conclusion,
            evidence_type=evidence_type,
            strength=strength,
            source=source,
        )

    def _neutral_output(self, reason: str = "数据不足") -> ModuleOutput:
        """Return a neutral mid-score output when data is unavailable."""
        score = self.MAX_SCORE * 0.5
        out = self._base_output(score, conclusion=f"【数据不足】{reason}，评分取中性值，置信度低")
        out.data_missing_fields.append(reason)
        return out

    def safe_analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        """Wrapper that catches exceptions and returns neutral output."""
        try:
            return self.analyze(ctx)
        except Exception as exc:
            self._logger.exception(
                "Module %s analysis failed for %s: %s",
                self.MODULE_ID,
                ctx.stock.code,
                exc,
            )
            return self._neutral_output(f"分析异常: {exc}")
