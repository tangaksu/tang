"""Layer 3 – Joint Decision Matrix: 三评分联合解读与仓位映射."""
from __future__ import annotations

from dataclasses import dataclass

from ...layer2_data.models import ScoreResult


@dataclass
class JointDecision:
    scenario_name: str
    position_advice: str
    short_term_action: str
    mid_term_action: str
    long_term_action: str


class JointDecisionMatrix:
    """按规范稿第七章8大场景矩阵输出标准化仓位建议."""

    def decide(
        self,
        score_a: ScoreResult,
        score_b: ScoreResult,
        score_c: ScoreResult,
    ) -> JointDecision:
        sa = score_a.total_score
        sb = score_b.total_score
        sc = score_c.total_score

        # Scenario 1: 黄金配置机会
        if sa >= 80 and sb >= 80 and sc >= 80:
            return JointDecision(
                scenario_name="场景1：黄金配置机会",
                position_advice="允许中高仓位布局50%–80%，底仓+波段仓同步配置",
                short_term_action="可进攻，短线仓位30%-50%",
                mid_term_action="中线底仓配置30%-50%",
                long_term_action="长线价值配置，可持续持有",
            )
        # Scenario 2: 优质资产等待更优点
        if sa >= 80 and 60 <= sb < 80 and 60 <= sc < 80:
            return JointDecision(
                scenario_name="场景2：优质资产等待更优买点",
                position_advice="长线分批低吸20%-40%底仓，短线等待确认",
                short_term_action="短线观望或极轻仓10%",
                mid_term_action="分批低吸建立底仓",
                long_term_action="优质资产长线配置价值高",
            )
        # Scenario 3: 好公司坏位置
        if sa >= 80 and sb < 60 and sc < 70:
            return JointDecision(
                scenario_name="场景3：好公司坏位置",
                position_advice="禁止追高，持仓逢高调仓，等候回调",
                short_term_action="只减不买",
                mid_term_action="等待充分回调后再建仓",
                long_term_action="长线价值存在但需要等待更好买点",
            )
        # Scenario 4: 交易型机会
        if 60 <= sa < 80 and sb >= 80 and sc >= 80:
            return JointDecision(
                scenario_name="场景4：交易型机会",
                position_advice="仅适合短中线策略，仓位10%-25%，严禁恋战",
                short_term_action="可积极参与短线，但严格止损",
                mid_term_action="中线需结合基本面改善信号",
                long_term_action="基本面中性，不适合长线持有",
            )
        # Scenario 5: 研究可看、执行不可做
        if sa >= 70 and sb >= 70 and sc < 60:
            return JointDecision(
                scenario_name="场景5：研究可看、执行不可做",
                position_advice="等待执行信号清晰后再参与，暂观望",
                short_term_action="暂不参与",
                mid_term_action="等待信号确认",
                long_term_action="逻辑存在，持续跟踪",
            )
        # Scenario 6: 高风险投机博弈
        if sa < 60:
            return JointDecision(
                scenario_name="场景6：高风险投机博弈",
                position_advice="基本面存在硬伤，仅允许极小仓位<5%超短博弈，严禁重仓",
                short_term_action="超短博弈仓位<5%，随时止损",
                mid_term_action="不适合中线持有",
                long_term_action="不适合长线配置",
            )
        # Scenario 7: 全维度回避
        if sb < 60 and sc < 60:
            return JointDecision(
                scenario_name="场景7：全维度回避",
                position_advice="当前风险高，不新开仓，持仓择机减仓",
                short_term_action="只减不买",
                mid_term_action="等待风险释放",
                long_term_action="暂时回避",
            )
        # Scenario 8: 左侧预埋型机会
        if 70 <= sa <= 85 and 65 <= sb <= 80 and 60 <= sc <= 75:
            return JointDecision(
                scenario_name="场景8：左侧预埋型机会",
                position_advice="长线可底仓潜伏10%-20%，短线不激进，严格控制节奏",
                short_term_action="可低吸，仓位<15%",
                mid_term_action="底仓潜伏，等待景气拐点",
                long_term_action="长线逻辑成立，分批布局",
            )
        # Default balanced
        return JointDecision(
            scenario_name="综合研判",
            position_advice=f"综合评分A={sa:.0f}/B={sb:.0f}/C={sc:.0f}，建议仓位20%-30%，严格止损",
            short_term_action="可轻仓参与",
            mid_term_action="中线需持续跟踪基本面",
            long_term_action="长线价值待进一步确认",
        )

    @staticmethod
    def position_size_advice(score_a: float, score_b: float, score_c: float) -> str:
        if score_a >= 85 and score_b >= 85 and score_c >= 85:
            return "50%–80% 计划仓位"
        if score_a >= 80 and (score_b < 80 or score_c < 80):
            return "20%–40% 底仓，等确认后加仓"
        if score_b >= 80 and score_c >= 80 and score_a < 80:
            return "10%–25% 交易仓，严禁恋战"
        if min(score_a, score_b, score_c) < 60:
            return "原则上不建议新增仓位"
        if sum(1 for s in [score_a, score_b, score_c] if s < 60) >= 2:
            return "禁止开仓，以减仓或退出为主"
        return "20%–30% 轻仓参与，严格止损"
