"""Layer 4 – Scenario engine: 四情景推演框架."""
from __future__ import annotations

from ..layer2_data.models import AnalysisContext, FullReport, Scenario, ScoreResult


class ScenarioEngine:
    """Generate four mandatory scenarios (乐观/中性/悲观/风险触发).

    Each scenario includes:
    - trigger_conditions
    - price_target_range
    - probability
    - time_horizon
    - strategy
    """

    def build_scenarios(self, report: FullReport) -> list[Scenario]:
        ctx = report.context
        quote = ctx.quote
        sa = report.score_a.total_score if report.score_a else 50.0
        sb = report.score_b.total_score if report.score_b else 50.0
        sc = report.score_c.total_score if report.score_c else 50.0

        cur_price = quote.price if quote else 0.0

        def fmt_price(pct: float) -> str:
            if cur_price <= 0:
                return "待确认"
            return f"{cur_price * (1 + pct):.2f}"

        # Probability hints based on combined scores
        avg = (sa + sb + sc) / 3
        p_bull = "30%-45%" if avg >= 75 else "15%-25%"
        p_neutral = "35%-50%"
        p_bear = "20%-30%" if avg >= 70 else "30%-40%"
        p_tail = "5%-15%"

        scenarios = [
            Scenario(
                name="乐观情景",
                trigger_conditions=[
                    "业绩超预期，季报净利润同比增速超过30%",
                    "行业政策超预期利好落地",
                    "北向及机构持续净买入，资金共振",
                ],
                price_target_range=f"{fmt_price(0.15)}–{fmt_price(0.30)}",
                probability=p_bull,
                time_horizon="1–3个月",
                strategy="持仓不动，分批止盈，第一止盈位为+15%",
            ),
            Scenario(
                name="中性情景",
                trigger_conditions=[
                    "业绩符合预期，无明显超预期",
                    "行业景气维持现有水平",
                    "资金面中性，无明显异动",
                ],
                price_target_range=f"{fmt_price(-0.08)}–{fmt_price(0.08)}",
                probability=p_neutral,
                time_horizon="1–2个月",
                strategy="区间震荡做T，降低持仓波动",
            ),
            Scenario(
                name="悲观情景",
                trigger_conditions=[
                    "业绩低于预期，归母净利润同比下滑",
                    "行业景气下行，上游成本压力增大",
                    "大盘系统性回调拖累",
                ],
                price_target_range=f"{fmt_price(-0.20)}–{fmt_price(-0.10)}",
                probability=p_bear,
                time_horizon="1–2个月",
                strategy=(
                    "止盈减仓50%，保留底仓等待企稳；"
                    f"硬止损位：{fmt_price(-0.15)}"
                ),
            ),
            Scenario(
                name="风险触发情景",
                trigger_conditions=[
                    "季报出现业绩雷（净利润同比下滑>30%）",
                    "大股东公告清仓式减持",
                    "行业监管出现重大政策转向",
                    "关键技术支撑位（20日低点）失守且连续收于下方",
                ],
                price_target_range=f"≤{fmt_price(-0.25)}",
                probability=p_tail,
                time_horizon="触发后立即",
                strategy=(
                    "立即清仓止损，不等反弹；"
                    "复盘逻辑失效原因后重新评估是否再参与"
                ),
            ),
        ]
        return scenarios
