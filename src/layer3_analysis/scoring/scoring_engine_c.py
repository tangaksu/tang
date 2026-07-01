"""Layer 3 – Scoring Engine C: 交易执行确定性评分 (满分100)."""
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


class ScoringEngineC:
    """交易执行确定性评分 – 7维度，满分100分.

    维度权重:
        信号一致性         20
        技术结构清晰度     15
        流动性与仓位容量   15
        市场风格适配度     15
        风险事件干扰度     15
        止损可执行性       10
        情绪拥挤度惩罚     10
    """

    def compute(
        self,
        ctx: AnalysisContext,
        modules: dict[str, ModuleOutput],
    ) -> ScoreResult:
        dims: list[ScoringDimension] = []

        # ---------- D1: 信号一致性 (20分) ----------
        m06 = modules.get("M06")
        m02 = modules.get("M02")
        m07 = modules.get("M07")
        raw_tech = (m06.module_score / m06.module_max_score) if m06 else 0.5
        raw_fin = (m02.module_score / m02.module_max_score) if m02 else 0.5
        raw_cap = (m07.module_score / m07.module_max_score) if m07 else 0.5
        d1 = ((raw_tech + raw_fin + raw_cap) / 3) * 20
        dims.append(ScoringDimension(name="信号一致性", score=round(d1, 2), max_score=20))

        # ---------- D2: 技术结构清晰度 (15分) ----------
        d2 = raw_tech * 15
        dims.append(ScoringDimension(name="技术结构清晰度", score=round(d2, 2), max_score=15))

        # ---------- D3: 流动性与仓位容量 (15分) ----------
        m11 = modules.get("M11")
        d3 = (m11.module_score / m11.module_max_score) * 15 if m11 else 7.5
        dims.append(ScoringDimension(name="流动性与仓位容量", score=round(d3, 2), max_score=15))

        # ---------- D4: 市场风格适配度 (15分) ----------
        m10 = modules.get("M10")
        d4 = (m10.module_score / m10.module_max_score) * 15 if m10 else 7.5
        dims.append(ScoringDimension(name="市场风格适配度", score=round(d4, 2), max_score=15))

        # ---------- D5: 风险事件干扰度 (15分) ----------
        m03 = modules.get("M03")
        m12 = modules.get("M12")
        raw_gov = (m03.module_score / m03.module_max_score) if m03 else 0.5
        raw_cat = (m12.module_score / m12.module_max_score) if m12 else 0.5
        d5 = ((raw_gov + raw_cat) / 2) * 15
        dims.append(ScoringDimension(name="风险事件干扰度", score=round(d5, 2), max_score=15))

        # ---------- D6: 止损可执行性 (10分) ----------
        m14 = modules.get("M14")
        d6 = (m14.module_score / m14.module_max_score) * 10 if m14 else 5.0
        dims.append(ScoringDimension(name="止损可执行性", score=round(d6, 2), max_score=10))

        # ---------- D7: 情绪拥挤度惩罚 (10分) ----------
        m08 = modules.get("M08")
        d7 = (m08.module_score / m08.module_max_score) * 10 if m08 else 5.0
        dims.append(ScoringDimension(name="情绪拥挤度惩罚", score=round(d7, 2), max_score=10))

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

        exec_map = {
            StarRating.FIVE: "高确定性执行窗口，可直接执行",
            StarRating.FOUR: "信号较清晰，确认后可执行",
            StarRating.THREE: "可执行但需进一步确认信号",
            StarRating.TWO: "结构不清晰，等待更明确信号",
            StarRating.ONE: "不宜贸然执行，暂观望",
        }
        allow_map = {
            StarRating.FIVE: "允许开仓/追涨/加仓",
            StarRating.FOUR: "允许开仓，不追涨",
            StarRating.THREE: "仅允许低吸，不追涨",
            StarRating.TWO: "不允许新增仓位",
            StarRating.ONE: "禁止新增仓位",
        }

        desc_map = {
            StarRating.FIVE: "高确定性执行窗口",
            StarRating.FOUR: "较高确定性可执行",
            StarRating.THREE: "可执行但需确认",
            StarRating.TWO: "结构不清晰",
            StarRating.ONE: "不宜贸然执行",
        }

        return ScoreResult(
            engine="C",
            total_score=round(total, 1),
            star_rating=star,
            one_line_conclusion=f"{star.value}星 · {desc_map[star]}",
            plus_items=plus_items,
            minus_items=minus_items,
            confidence="中",
            dimensions=dims,
            action_suggestion=f"{exec_map[star]}；{allow_map[star]}",
        )
