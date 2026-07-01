"""Layer 2 – Multi-source validator: cross-check data and flag conflicts."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_PRICE_TOLERANCE = 0.02   # 2% relative tolerance for price comparison


@dataclass
class ValidationResult:
    is_valid: bool = True
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    chosen_value: Any = None


class MultiSourceValidator:
    """Compare values from multiple data sources and resolve conflicts.

    Conflict resolution priority (from the V5.0 spec):
    基本面证伪 > 财务安全与现金流 > 风险事件 > 股东行为 >
    行业景气 > 估值约束 > 资金结构 > 技术形态 > 情绪热度
    """

    def validate_price(
        self, values: dict[str, float | None]
    ) -> ValidationResult:
        """Validate price across sources; flag if divergence > tolerance."""
        clean = {src: v for src, v in values.items() if v is not None and v > 0}
        if not clean:
            return ValidationResult(is_valid=False, chosen_value=None,
                                    warnings=["All price sources returned None"])
        vals = list(clean.values())
        ref = vals[0]
        conflicts = []
        for src, v in clean.items():
            if abs(v - ref) / max(ref, 1e-9) > _PRICE_TOLERANCE:
                conflicts.append(
                    f"Price conflict: {src}={v:.2f} vs reference={ref:.2f}"
                )
        # Choose the value from the highest-priority source (first key)
        primary_src = next(iter(clean))
        chosen = clean[primary_src]
        return ValidationResult(
            is_valid=len(conflicts) == 0,
            conflicts=conflicts,
            chosen_value=chosen,
        )

    def validate_pe(
        self, values: dict[str, float | None]
    ) -> ValidationResult:
        """Validate PE-TTM across sources; tolerate 5% divergence."""
        clean = {src: v for src, v in values.items() if v is not None and v > 0}
        if not clean:
            return ValidationResult(is_valid=True, chosen_value=None,
                                    warnings=["PE data unavailable"])
        vals = list(clean.values())
        ref = vals[0]
        conflicts = []
        for src, v in clean.items():
            if abs(v - ref) / max(ref, 1e-9) > 0.05:
                conflicts.append(
                    f"PE conflict: {src}={v:.1f} vs reference={ref:.1f}"
                )
        chosen = list(clean.values())[0]
        return ValidationResult(
            is_valid=len(conflicts) == 0,
            conflicts=conflicts,
            chosen_value=chosen,
        )

    def log_conflicts(self, results: list[ValidationResult]) -> None:
        for r in results:
            for conflict in r.conflicts:
                logger.warning("[DATA CONFLICT] %s", conflict)
            for warning in r.warnings:
                logger.info("[DATA WARNING] %s", warning)
