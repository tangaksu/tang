"""Layer 3 – Scoring Engine A: 综合投资价值评分 (满分100)."""
from __future__ import annotations

from ...layer2_data.models import (
    AnalysisContext,
    ModuleOutput,
    ScoreResult,
    ScoringDimension,
    ScoringSubItem,
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


class ScoringEngineA:
    """综合投资价值评分 – 7维度，满分100分.

    维度权重:
        公司质量   15
        财务质量   20
        股权治理   10
        行业景气   15
        估值护城河 20
        资本配置   10
        风险折扣   10
    """

    def compute(
        self,
        ctx: AnalysisContext,
        modules: dict[str, ModuleOutput],
    ) -> ScoreResult:
        dims: list[ScoringDimension] = []

        # ---------- D1: 公司基础质量 (15分) ----------
        m01 = modules.get("M01")
        d1_raw = (m01.module_score / m01.module_max_score) * 15 if m01 else 7.5
        dims.append(ScoringDimension(
            name="公司基础质量",
            score=round(d1_raw, 2),
            max_score=15,
        ))

        # ---------- D2: 财务质量 (20分) ----------
        m02 = modules.get("M02")
        d2_raw = (m02.module_score / m02.module_max_score) * 20 if m02 else 10.0
        dims.append(ScoringDimension(
            name="财务质量",
            score=round(d2_raw, 2),
            max_score=20,
        ))

        # ---------- D3: 股权治理 (10分) ----------
        m03 = modules.get("M03")
        d3_raw = (m03.module_score / m03.module_max_score) * 10 if m03 else 5.0
        dims.append(ScoringDimension(
            name="股权治理质量",
            score=round(d3_raw, 2),
            max_score=10,
        ))

        # ---------- D4: 行业景气 (15分) ----------
        m04 = modules.get("M04")
        d4_raw = (m04.module_score / m04.module_max_score) * 15 if m04 else 7.5
        dims.append(ScoringDimension(
            name="行业景气与产业周期",
            score=round(d4_raw, 2),
            max_score=15,
        ))

        # ---------- D5: 估值护城河 (20分) ----------
        m05 = modules.get("M05")
        d5_raw = (m05.module_score / m05.module_max_score) * 20 if m05 else 10.0
        dims.append(ScoringDimension(
            name="估值与护城河",
            score=round(d5_raw, 2),
            max_score=20,
        ))

        # ---------- D6: 资本配置 (10分) ----------
        m21 = modules.get("M21")
        d6_raw = (m21.module_score / m21.module_max_score) * 10 if m21 else 5.0
        dims.append(ScoringDimension(
            name="资本配置与股东回报能力",
            score=round(d6_raw, 2),
            max_score=10,
        ))

        # ---------- D7: 风险折扣 (10分) ----------
        # Derived from governance + financial red flags
        risk_deduction = 0.0
        if m02:
            risk_deduction += len(m02.risk_deductions) * 0.5
        if m03:
            risk_deduction += len(m03.risk_deductions) * 0.5
        d7_raw = max(0.0, 10.0 - risk_deduction)
        dims.append(ScoringDimension(
            name="风险折扣项",
            score=round(d7_raw, 2),
            max_score=10,
        ))

        total = sum(d.score for d in dims)
        star = _star(total)

        # Build plus/minus items
        plus_items = [
            f"{d.name}得分较高（{d.score:.1f}/{d.max_score}）"
            for d in sorted(dims, key=lambda x: x.score / x.max_score, reverse=True)[:3]
        ]
        minus_items = [
            f"{d.name}得分偏低（{d.score:.1f}/{d.max_score}）"
            for d in sorted(dims, key=lambda x: x.score / x.max_score)[:3]
        ]

        # Confidence
        missing = sum(1 for m in [m01, m02, m03, m04, m05, m21] if m and m.data_missing_fields)
        confidence = "高" if missing <= 1 else "中" if missing <= 3 else "低（多项数据缺失）"

        desc_map = {
            StarRating.FIVE: "极具长期投资价值",
            StarRating.FOUR: "优质配置标的",
            StarRating.THREE: "中性偏优",
            StarRating.TWO: "偏弱谨慎",
            StarRating.ONE: "规避或仅跟踪",
        }

        return ScoreResult(
            engine="A",
            total_score=round(total, 1),
            star_rating=star,
            one_line_conclusion=f"{star.value}星 · {desc_map[star]}",
            plus_items=plus_items,
            minus_items=minus_items,
            confidence=confidence,
            dimensions=dims,
            action_suggestion=(
                "可考虑中长线配置" if total >= 80
                else "等待更多数据支撑" if total >= 65
                else "谨慎评估，严格止损"
            ),
        )
