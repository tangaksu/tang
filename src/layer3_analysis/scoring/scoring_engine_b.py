"""Layer 3 – Scoring Engine B: 现价买入性价比评分 (满分100)."""
from __future__ import annotations

from ...layer2_data.models import (
    AnalysisContext,
    ModuleOutput,
    ScoreResult,
    ScoringDimension,
    StarRating,
)


def _star(score: float) -> StarRating:
    if score >= 90:
        return StarRating.FIVE
    if score >= 80:
        return StarRating.FOUR
    if score >= 70:
        return StarRating.THREE
    if score >= 60:
        return StarRating.TWO
    return StarRating.ONE


class ScoringEngineB:
    """现价买入性价比评分 – 6维度，满分100分.

    维度权重:
        多周期技术择时     25
        现价估值安全边际   20
        主力资金与筹码     20
        题材情绪与催化     15
        交易盈亏比         10
        短期风险事件干扰   10
    """

    def compute(
        self,
        ctx: AnalysisContext,
        modules: dict[str, ModuleOutput],
    ) -> ScoreResult:
        dims: list[ScoringDimension] = []

        # ---------- D1: 多周期技术择时 (25分) ----------
        m06 = modules.get("M06")
        d1 = (m06.module_score / m06.module_max_score) * 25 if m06 else 12.5
        dims.append(ScoringDimension(name="多周期技术择时状态", score=round(d1, 2), max_score=25))

        # ---------- D2: 现价估值安全边际 (20分) ----------
        m05 = modules.get("M05")
        d2 = (m05.module_score / m05.module_max_score) * 20 if m05 else 10.0
        dims.append(ScoringDimension(name="现价估值安全边际", score=round(d2, 2), max_score=20))

        # ---------- D3: 主力资金与筹码 (20分) ----------
        m07 = modules.get("M07")
        d3 = (m07.module_score / m07.module_max_score) * 20 if m07 else 10.0
        dims.append(ScoringDimension(name="主力资金与筹码结构", score=round(d3, 2), max_score=20))

        # ---------- D4: 题材情绪与催化 (15分) ----------
        m08 = modules.get("M08")
        m12 = modules.get("M12")
        raw08 = (m08.module_score / m08.module_max_score) if m08 else 0.5
        raw12 = (m12.module_score / m12.module_max_score) if m12 else 0.5
        d4 = ((raw08 + raw12) / 2) * 15
        dims.append(ScoringDimension(name="题材情绪与催化窗口", score=round(d4, 2), max_score=15))

        # ---------- D5: 交易盈亏比 (10分) ----------
        m14 = modules.get("M14")
        d5 = (m14.module_score / m14.module_max_score) * 10 if m14 else 5.0
        dims.append(ScoringDimension(name="交易盈亏比", score=round(d5, 2), max_score=10))

        # ---------- D6: 短期风险事件干扰 (10分) ----------
        m03 = modules.get("M03")
        risk_pen = len(m03.risk_deductions) * 1.0 if m03 else 0.0
        d6 = max(0.0, 10.0 - risk_pen)
        dims.append(ScoringDimension(name="短期风险事件干扰", score=round(d6, 2), max_score=10))

        total = sum(d.score for d in dims)
        star = _star(total)

        plus_items = [
            f"{d.name}（{d.score:.1f}/{d.max_score}）"
            for d in sorted(dims, key=lambda x: x.score / x.max_score, reverse=True)[:3]
        ]
        minus_items = [
            f"{d.name}（{d.score:.1f}/{d.max_score}）"
            for d in sorted(dims, key=lambda x: x.score / x.max_score)[:3]
        ]

        entry_map = {
            StarRating.FIVE: "直接买入建仓",
            StarRating.FOUR: "分批低吸布局",
            StarRating.THREE: "可轻仓试错",
            StarRating.TWO: "等待更优位置",
            StarRating.ONE: "不建议追高/回避",
        }
        position_map = {
            StarRating.FIVE: "短线仓位30%-50%",
            StarRating.FOUR: "短线仓位20%-30%",
            StarRating.THREE: "短线仓位10%-20%",
            StarRating.TWO: "短线仓位<10%",
            StarRating.ONE: "0%，不新开仓",
        }

        desc_map = {
            StarRating.FIVE: "极佳重仓买点",
            StarRating.FOUR: "良好布局区",
            StarRating.THREE: "可轻仓试错",
            StarRating.TWO: "等待更优位置",
            StarRating.ONE: "回避追高",
        }

        return ScoreResult(
            engine="B",
            total_score=round(total, 1),
            star_rating=star,
            one_line_conclusion=f"{star.value}星 · {desc_map[star]}",
            plus_items=plus_items,
            minus_items=minus_items,
            confidence="中",
            dimensions=dims,
            action_suggestion=f"{entry_map[star]}；{position_map[star]}",
        )
