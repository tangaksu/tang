"""Layer 4 – Report assembler: orchestrate the full report construction."""
from __future__ import annotations

import logging
from datetime import datetime

from ..layer2_data.models import (
    FullReport,
    InvestorProfile,
    MainDriver,
    ModuleOutput,
    ScoreResult,
    TradeAction,
    TradeStatus,
    ValuationZone,
)
from ..layer3_analysis.scoring import JointDecisionMatrix, ScoringEngineA, ScoringEngineB, ScoringEngineC
from .consistency_checker import ConsistencyChecker
from .evidence_chain_validator import EvidenceChainValidator
from .scenario_engine import ScenarioEngine
from .vagueness_filter import VaguenessFilter

logger = logging.getLogger(__name__)


class ReportAssembler:
    """Collect all module outputs and build the final FullReport."""

    def __init__(self) -> None:
        self._engine_a = ScoringEngineA()
        self._engine_b = ScoringEngineB()
        self._engine_c = ScoringEngineC()
        self._decision_matrix = JointDecisionMatrix()
        self._evidence_validator = EvidenceChainValidator()
        self._consistency_checker = ConsistencyChecker()
        self._scenario_engine = ScenarioEngine()
        self._vagueness_filter = VaguenessFilter()

    def assemble(
        self,
        report: FullReport,
        modules: dict[str, ModuleOutput],
    ) -> FullReport:
        """Build final report from module outputs.

        Steps:
        1. Collect module outputs
        2. Run three scoring engines
        3. Evidence chain validation
        4. Consistency check
        5. Scenario generation
        6. Trade action assembly
        7. Investor profile table
        8. Vagueness filter pass
        """
        report.module_outputs = modules

        # -- Step 2: Three scoring engines --
        ctx = report.context
        report.score_a = self._engine_a.compute(ctx, modules)
        report.score_b = self._engine_b.compute(ctx, modules)
        report.score_c = self._engine_c.compute(ctx, modules)

        sa = report.score_a.total_score
        sb = report.score_b.total_score
        sc = report.score_c.total_score

        # -- Step 3: Evidence chain validation --
        ev_valid, ev_issues = self._evidence_validator.validate_all(modules)
        if not ev_valid:
            logger.info("[Assembler] %d evidence issues found", len(ev_issues))

        # -- Step 4: Consistency check --
        consistency_rep = self._consistency_checker.check(modules)
        if not consistency_rep.is_consistent:
            logger.info(
                "[Assembler] %d consistency conflicts found",
                len(consistency_rep.conflicts),
            )

        # -- Joint decision --
        decision = self._decision_matrix.decide(report.score_a, report.score_b, report.score_c)
        report.joint_scenario = decision.scenario_name
        report.position_advice = decision.position_advice

        # -- Valuation zone --
        m05 = modules.get("M05")
        report.valuation_zone = _infer_valuation_zone(m05, report.score_a)

        # -- Main driver --
        report.main_driver = _infer_main_driver(modules, ctx)

        # -- Trade status --
        report.trade_status = _infer_trade_status(sa, sb, sc)

        # -- Key failure condition --
        m25 = modules.get("M25")
        if m25 and m25.raw_data.get("invalidation_conditions"):
            report.key_failure_condition = m25.raw_data["invalidation_conditions"][0]
        else:
            report.key_failure_condition = "季报业绩大幅低于预期（净利润同比下滑>20%）"

        # -- Step 5: Scenarios --
        report.scenarios = self._scenario_engine.build_scenarios(report)

        # -- Step 6: Trade action --
        report.trade_action = _build_trade_action(report, decision, modules)

        # -- Step 7: Investor profiles --
        report.investor_profiles = _build_investor_profiles(sa, sb, sc)

        # -- Invalidation & tracking checklists --
        if m25:
            conds = m25.raw_data.get("invalidation_conditions", [])
            report.invalidation_checklist = conds
        report.tracking_checklist = [
            "每周核查主力净流入金额变化方向",
            "每季跟踪扣非净利润与经营现金流匹配度",
            "实时关注大股东增减持公告",
            "关注技术面关键支撑是否失守",
            "跟踪行业景气高频指标（如价格指数、开工率）",
        ]

        # -- Step 8: Vagueness filter on action text --
        report.trade_action.one_line_verdict = self._vagueness_filter.enforce(
            report.trade_action.one_line_verdict
        )

        return report


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _infer_valuation_zone(
    m05: ModuleOutput | None, score_a: ScoreResult | None
) -> ValuationZone:
    if m05 is None:
        return ValuationZone.FAIR
    ratio = m05.module_score / max(m05.module_max_score, 1e-9)
    if ratio >= 0.80:
        return ValuationZone.DEEP_UNDERVALUE
    if ratio >= 0.65:
        return ValuationZone.MILD_UNDERVALUE
    if ratio >= 0.45:
        return ValuationZone.FAIR
    if ratio >= 0.30:
        return ValuationZone.MILD_OVERVALUE
    return ValuationZone.BUBBLE


def _infer_main_driver(
    modules: dict[str, ModuleOutput], ctx: object
) -> MainDriver:
    m02 = modules.get("M02")
    m07 = modules.get("M07")
    m08 = modules.get("M08")

    if m02 and m02.module_score / max(m02.module_max_score, 1e-9) >= 0.75:
        return MainDriver.EARNINGS
    if m07 and m07.module_score / max(m07.module_max_score, 1e-9) >= 0.75:
        return MainDriver.FUND_CLUSTER
    if m08 and m08.module_score / max(m08.module_max_score, 1e-9) >= 0.70:
        return MainDriver.THEME
    return MainDriver.VALUATION_REPAIR


def _infer_trade_status(sa: float, sb: float, sc: float) -> TradeStatus:
    if sa >= 75 and sb >= 80 and sc >= 75:
        return TradeStatus.ATTACK
    if sb >= 70 and sc >= 70:
        return TradeStatus.LOW_BUY
    if sb >= 65 and sc >= 65:
        return TradeStatus.T_TRADE
    if sb < 60 or sc < 60:
        return TradeStatus.REDUCE_ONLY
    return TradeStatus.AVOID


def _build_trade_action(
    report: FullReport,
    decision: object,
    modules: dict[str, ModuleOutput],
) -> TradeAction:
    quote = report.context.quote
    m14 = modules.get("M14")
    stop_loss = m14.raw_data.get("stop_loss", "待确认") if m14 else "待确认"
    target_1 = m14.raw_data.get("target_1", "待确认") if m14 else "待确认"
    cur_price = f"{quote.price:.2f}" if quote else "待确认"

    sa = report.score_a.total_score if report.score_a else 50.0
    sb = report.score_b.total_score if report.score_b else 50.0
    sc = report.score_c.total_score if report.score_c else 50.0

    verdict_map = {
        TradeStatus.ATTACK: f"当前处于进攻区间，三评分共振向好（A={sa:.0f}/B={sb:.0f}/C={sc:.0f}），可积极布局",
        TradeStatus.LOW_BUY: f"可在回踩支撑后分批低吸（A={sa:.0f}/B={sb:.0f}/C={sc:.0f}）",
        TradeStatus.T_TRADE: f"适合区间做T降低持仓成本（A={sa:.0f}/B={sb:.0f}/C={sc:.0f}）",
        TradeStatus.REDUCE_ONLY: f"现价性价比低，只减不买（A={sa:.0f}/B={sb:.0f}/C={sc:.0f}）",
        TradeStatus.AVOID: f"信号不明，暂不参与（A={sa:.0f}/B={sb:.0f}/C={sc:.0f}）",
    }

    return TradeAction(
        one_line_verdict=verdict_map.get(report.trade_status, "待确认"),
        entry_zone=f"回踩至{stop_loss}附近时分批建仓" if stop_loss != "待确认" else "等待技术面明确支撑后建仓",
        entry_ratio=JointDecisionMatrix.position_size_advice(sa, sb, sc),
        add_position_condition=f"突破{target_1}且量价配合后加仓",
        hold_bottom=sa >= 70,
        do_t_trade=report.trade_status == TradeStatus.T_TRADE,
        reduce_to_lock_profit=sb < 70,
        hard_stop_loss=stop_loss,
        logic_stop_condition="季报净利润同比下滑超20%或行业政策出现重大负面转向",
        event_stop_condition="大股东公告减持超过总股本1%",
        target_1=target_1,
        target_2=f"{'待确认' if not quote else f'{quote.price * 1.25:.2f}'}（+25%参考位）",
        event_tp_strategy="业绩超预期兑现后减仓30%–50%，剩余持仓移动止盈",
        forbid_chase_conditions=[
            "单日涨幅超过9%后不追涨",
            "连续3日上涨总幅度超过20%不追高",
        ],
        forbid_bottom_fish_conditions=[
            "股价跌破止损位后不抄底",
            "出现业绩雷公告后不抄底",
        ],
        forbid_leverage_conditions=[
            "交易执行确定性评分低于70分时禁止使用杠杆",
            f"仓位已超过{JointDecisionMatrix.position_size_advice(sa, sb, sc)}时禁止加杠杆",
        ],
    )


def _build_investor_profiles(sa: float, sb: float, sc: float) -> list[InvestorProfile]:
    profiles = [
        InvestorProfile(
            investor_type="保守型",
            suitable="适合" if sa >= 80 else "不适合",
            position_limit="10%" if sa >= 80 else "0%",
            recommended_period="长线" if sa >= 80 else "不推荐",
            max_drawdown_tolerance="10%",
        ),
        InvestorProfile(
            investor_type="稳健型",
            suitable="适合" if sa >= 70 else "一般",
            position_limit="20%" if sa >= 70 else "5%",
            recommended_period="中/长线",
            max_drawdown_tolerance="15%",
        ),
        InvestorProfile(
            investor_type="平衡型",
            suitable="适合" if sa >= 65 and sb >= 65 else "一般",
            position_limit="30%",
            recommended_period="中线",
            max_drawdown_tolerance="20%",
        ),
        InvestorProfile(
            investor_type="进取型",
            suitable="适合" if sb >= 70 and sc >= 70 else "一般",
            position_limit="40%",
            recommended_period="短/中线",
            max_drawdown_tolerance="25%",
        ),
        InvestorProfile(
            investor_type="短线博弈型",
            suitable="适合" if sb >= 75 and sc >= 75 else "不适合",
            position_limit="30%" if sb >= 75 and sc >= 75 else "0%",
            recommended_period="短线（1-7日）",
            max_drawdown_tolerance="8%",
        ),
    ]
    return profiles
