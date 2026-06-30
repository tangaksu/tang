"""Layer 4 – Consistency checker: resolve conflicts between module conclusions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..layer2_data.models import ModuleOutput

logger = logging.getLogger(__name__)

# Priority order for conflict resolution (from V5.0 spec Section 3.8)
_PRIORITY_ORDER = [
    "基本面证伪",
    "财务安全与现金流",
    "风险事件",
    "股东行为",
    "行业景气",
    "估值约束",
    "资金结构",
    "技术形态",
    "情绪热度",
]

# Map module IDs to their logical category
_MODULE_CATEGORY = {
    "M02": "财务安全与现金流",
    "M03": "股东行为",
    "M04": "行业景气",
    "M05": "估值约束",
    "M06": "技术形态",
    "M07": "资金结构",
    "M08": "情绪热度",
    "M01": "基本面证伪",
}


@dataclass
class ConflictItem:
    module_a: str
    module_b: str
    description: str
    resolution: str
    winning_module: str


@dataclass
class ConsistencyReport:
    conflicts: list[ConflictItem] = field(default_factory=list)
    is_consistent: bool = True


class ConsistencyChecker:
    """Detect and resolve contradictions between module conclusions.

    Strategy:
    - A module with a higher-priority category "wins" when conclusions diverge
      significantly (>25% score gap when normalised).
    """

    def check(self, modules: dict[str, ModuleOutput]) -> ConsistencyReport:
        report = ConsistencyReport()

        items = [
            (mid, m, _MODULE_CATEGORY.get(mid, "情绪热度"))
            for mid, m in modules.items()
        ]

        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                mid_a, mod_a, cat_a = items[i]
                mid_b, mod_b, cat_b = items[j]

                norm_a = mod_a.module_score / max(mod_a.module_max_score, 1e-9)
                norm_b = mod_b.module_score / max(mod_b.module_max_score, 1e-9)

                if abs(norm_a - norm_b) < 0.25:
                    continue  # Not a significant conflict

                pri_a = _PRIORITY_ORDER.index(cat_a) if cat_a in _PRIORITY_ORDER else 99
                pri_b = _PRIORITY_ORDER.index(cat_b) if cat_b in _PRIORITY_ORDER else 99
                winner = mid_a if pri_a <= pri_b else mid_b

                conflict = ConflictItem(
                    module_a=mid_a,
                    module_b=mid_b,
                    description=(
                        f"{mid_a}({cat_a})评分{norm_a:.0%} vs "
                        f"{mid_b}({cat_b})评分{norm_b:.0%}，差距超过25%"
                    ),
                    resolution=f"按优先级裁决，{winner}（优先级更高）结论主导综合判断",
                    winning_module=winner,
                )
                report.conflicts.append(conflict)
                report.is_consistent = False
                logger.debug("[ConsistencyChecker] %s", conflict.description)

        return report
