"""M03–M25: Remaining analysis modules."""
# Each module follows the same pattern as M01/M02.
# They provide a structured ModuleOutput with rule-based scoring heuristics.
# In production, richer data feeds and LLM-assisted text generation
# would enhance each module's output quality.

from __future__ import annotations

from ...layer2_data.models import AnalysisContext, EvidenceStrength, ModuleOutput
from ..base_analyzer import BaseAnalyzer


# ---------------------------------------------------------------------------
# M03 – 股权治理与股东行为评估
# ---------------------------------------------------------------------------
class GovernanceAnalyzer(BaseAnalyzer):
    MODULE_ID = "M03"
    MODULE_TITLE = "股权治理与股东行为评估"
    MODULE_POSITIONING = "判断谁在控制公司、稳不稳，股东行为是加分还是减分。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        extra = ctx.extra
        score = 5.5  # neutral default
        tags = ["治理数据待补充"]
        risks: list[str] = []

        pledge_ratio: float | None = extra.get("pledge_ratio")
        if pledge_ratio is not None:
            if pledge_ratio > 50:
                score -= 2.0
                risks.append(f"股权质押率偏高：{pledge_ratio:.1f}%，存在平仓风险")
                tags.append("质押风险")
            elif pledge_ratio > 30:
                score -= 1.0
                tags.append("质押中等")
            else:
                score += 0.5
                tags.append("质押风险低")

        out = self._base_output(max(0.0, min(score, self.MAX_SCORE)))
        out.core_conclusion = f"股权治理评分 {score:.1f}/{self.MAX_SCORE}。"
        out.key_tags = tags
        out.risk_deductions = risks
        out.data_missing_fields = ["解禁时间表", "大股东增减持", "机构持仓变化"]
        return out


# ---------------------------------------------------------------------------
# M04 – 行业周期与产业链景气度分析
# ---------------------------------------------------------------------------
class IndustryAnalyzer(BaseAnalyzer):
    MODULE_ID = "M04"
    MODULE_TITLE = "行业周期与产业链景气度分析"
    MODULE_POSITIONING = "判断公司所在行业是不是顺风赛道、景气周期位置。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 5.0
        tags = ["待补充行业景气数据"]
        out = self._base_output(score)
        out.core_conclusion = "行业景气度数据待进一步获取，当前评分取中性值。"
        out.key_tags = tags
        out.data_missing_fields = ["行业景气指数", "库存周期位置", "供需格局数据"]
        return out


# ---------------------------------------------------------------------------
# M05 – 估值定价与护城河壁垒分析
# ---------------------------------------------------------------------------
class ValuationAnalyzer(BaseAnalyzer):
    MODULE_ID = "M05"
    MODULE_TITLE = "估值定价与护城河壁垒分析"
    MODULE_POSITIONING = "判断公司值多少钱、当前贵不贵、贵得是否合理。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        quote = ctx.quote
        score = 5.0
        tags: list[str] = []

        if quote and quote.pe_ttm is not None:
            pe = quote.pe_ttm
            if pe < 0:
                score = 2.0
                tags.append("亏损无法用PE估值")
            elif pe < 15:
                score = 8.0
                tags.append("低估值")
            elif pe < 25:
                score = 6.0
                tags.append("估值合理")
            elif pe < 40:
                score = 4.0
                tags.append("轻度高估")
            else:
                score = 2.0
                tags.append("明显高估")

        out = self._base_output(score)
        out.core_conclusion = (
            f"PE-TTM: {quote.pe_ttm if quote else 'N/A'}，"
            f"PB: {quote.pb if quote else 'N/A'}，"
            f"初步估值判断：{'，'.join(tags) or '数据不足'}。"
        )
        out.key_tags = tags
        out.data_missing_fields = ["历史PE分位", "行业均值PE", "PEG", "EV/EBITDA"]
        return out


# ---------------------------------------------------------------------------
# M06 – 多周期技术面实时操盘分析
# ---------------------------------------------------------------------------
class TechnicalAnalyzer(BaseAnalyzer):
    MODULE_ID = "M06"
    MODULE_TITLE = "多周期技术面实时操盘分析"
    MODULE_POSITIONING = "判断走势结构是否支持交易，当前位置是强是弱。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        bars = ctx.klines_daily
        if not bars or len(bars) < 20:
            return self._neutral_output("K线数据不足")

        closes = [b.close for b in bars]
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        cur = closes[-1]

        score = 0.0
        tags: list[str] = []

        # Trend structure
        if cur > ma5 > ma10 > ma20:
            score += 4.0
            tags.append("多头排列")
        elif cur < ma5 < ma10 < ma20:
            score += 0.5
            tags.append("空头排列")
        else:
            score += 2.0
            tags.append("震荡整理")

        # Volume trend (last 5 vs prev 15)
        vols = [b.volume for b in bars]
        avg_v5 = sum(vols[-5:]) / 5
        avg_v20 = sum(vols[-20:-5]) / 15 if len(vols) >= 20 else avg_v5
        if avg_v5 > avg_v20 * 1.3 and cur > closes[-2]:
            score += 3.0
            tags.append("放量上涨")
        elif avg_v5 < avg_v20 * 0.7:
            score += 2.0
            tags.append("缩量回踩")
        else:
            score += 1.5

        # Support/resistance proximity
        high_20 = max(b.high for b in bars[-20:])
        low_20 = min(b.low for b in bars[-20:])
        range_20 = max(high_20 - low_20, 1e-9)
        pos_in_range = (cur - low_20) / range_20
        if pos_in_range < 0.25:
            score += 3.0
            tags.append("低位支撑区")
        elif pos_in_range > 0.85:
            score += 0.5
            tags.append("近期高位")
        else:
            score += 1.5

        total = min(score, self.MAX_SCORE)
        out = self._base_output(total)
        out.core_conclusion = (
            f"当前价{cur:.2f}，MA5={ma5:.2f}，MA10={ma10:.2f}，MA20={ma20:.2f}。"
            f"技术形态：{'、'.join(tags)}。"
        )
        out.key_tags = tags
        out.factor_tree.facts = [
            f"收盘价：{cur:.2f}",
            f"MA5：{ma5:.2f}",
            f"MA10：{ma10:.2f}",
            f"MA20：{ma20:.2f}",
            f"5日均量/20日均量比：{avg_v5/max(avg_v20,1e-9):.2f}",
            f"20日区间位置：{pos_in_range:.1%}",
        ]
        return out


# ---------------------------------------------------------------------------
# M07 – 资金筹码深度博弈分析
# ---------------------------------------------------------------------------
class CapitalFlowAnalyzer(BaseAnalyzer):
    MODULE_ID = "M07"
    MODULE_TITLE = "资金筹码深度博弈分析"
    MODULE_POSITIONING = "判断谁在买、谁在卖、筹码稳不稳、主力处于哪个阶段。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        flow = ctx.capital_flow
        if flow is None:
            return self._neutral_output("资金流向数据未获取")

        score = 5.0
        tags: list[str] = []

        if flow.main_net_inflow_5d is not None:
            if flow.main_net_inflow_5d > 0:
                score += 2.0
                tags.append("5日主力净流入")
            else:
                score -= 1.5
                tags.append("5日主力净流出")

        if flow.main_net_inflow_20d is not None:
            if flow.main_net_inflow_20d > 0:
                score += 1.0
                tags.append("20日主力持续净流入")
            else:
                score -= 0.5

        north = ctx.extra.get("north_5d")
        if north is not None:
            if north > 0:
                score += 1.0
                tags.append("北向净买入")
            else:
                score -= 0.5
                tags.append("北向净卖出")

        total = min(max(score, 0.0), self.MAX_SCORE)
        out = self._base_output(total)
        out.core_conclusion = (
            f"主力5日净流入：{flow.main_net_inflow_5d}亿元，"
            f"20日净流入：{flow.main_net_inflow_20d}亿元。"
        )
        out.key_tags = tags
        out.data_missing_fields = ["筹码峰分布", "龙虎榜数据", "主力阶段判断"]
        return out


# ---------------------------------------------------------------------------
# M08 – 题材情绪与市场热度分析
# ---------------------------------------------------------------------------
class SentimentAnalyzer(BaseAnalyzer):
    MODULE_ID = "M08"
    MODULE_TITLE = "题材情绪与市场热度分析"
    MODULE_POSITIONING = "判断标的当前是否有市场关注度、情绪溢价和题材持续性。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 5.0
        tags = ["题材情绪数据待补充"]
        out = self._base_output(score)
        out.core_conclusion = "题材情绪数据暂未获取，评分取中性值。"
        out.key_tags = tags
        out.data_missing_fields = ["连板高度", "炸板率", "板块情绪温度", "题材标签"]
        return out


# ---------------------------------------------------------------------------
# M09 – 市场分歧与机构预期统计
# ---------------------------------------------------------------------------
class ExpectationAnalyzer(BaseAnalyzer):
    MODULE_ID = "M09"
    MODULE_TITLE = "市场分歧与机构预期统计"
    MODULE_POSITIONING = "判断市场对标的的预期是否一致，是否存在预期差机会。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        forecast = ctx.analyst_forecast
        if forecast is None:
            return self._neutral_output("机构研报数据未获取")

        total_ratings = (
            forecast.rating_buy + forecast.rating_overweight
            + forecast.rating_neutral + forecast.rating_underweight
            + forecast.rating_sell
        )
        if total_ratings == 0:
            return self._neutral_output("无机构评级数据")

        positive = forecast.rating_buy + forecast.rating_overweight
        positive_ratio = positive / total_ratings

        score = 3.0 + positive_ratio * 7.0  # linear mapping
        tags = ["机构看多" if positive_ratio > 0.7 else "机构分歧" if positive_ratio > 0.4 else "机构看空"]

        target_upside = None
        if forecast.target_price_avg and ctx.quote:
            target_upside = (forecast.target_price_avg - ctx.quote.price) / max(ctx.quote.price, 1e-9) * 100

        out = self._base_output(score)
        out.core_conclusion = (
            f"共{total_ratings}家评级：买入{forecast.rating_buy}，增持{forecast.rating_overweight}，"
            f"中性{forecast.rating_neutral}，减持{forecast.rating_underweight}，卖出{forecast.rating_sell}。"
            + (f" 均值目标价上行空间：{target_upside:.1f}%" if target_upside else "")
        )
        out.key_tags = tags
        return out


# ---------------------------------------------------------------------------
# M10 – 大盘联动与市场风格适配分析
# ---------------------------------------------------------------------------
class MarketStyleAnalyzer(BaseAnalyzer):
    MODULE_ID = "M10"
    MODULE_TITLE = "大盘联动与市场风格适配分析"
    MODULE_POSITIONING = "判断个股与当前市场风格是否匹配，避免逆风格硬做。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        from ...layer2_data.models import MarketEnv
        env = ctx.market_env
        score = 5.5
        if env == MarketEnv.BULL:
            score = 7.0
        elif env == MarketEnv.BEAR:
            score = 3.5
        tags = [f"当前市场环境：{env.value}"]
        out = self._base_output(score)
        out.core_conclusion = f"当前市场环境为{env.value}，风格适配度初步评分{score:.1f}。"
        out.key_tags = tags
        out.data_missing_fields = ["指数Beta系数", "风格因子暴露", "行业轮动位置"]
        return out


# ---------------------------------------------------------------------------
# M11 – 量能换手与流动性专项分析
# ---------------------------------------------------------------------------
class LiquidityAnalyzer(BaseAnalyzer):
    MODULE_ID = "M11"
    MODULE_TITLE = "量能换手与流动性专项分析"
    MODULE_POSITIONING = "判断个股流动性是否安全、能否承接仓位。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        quote = ctx.quote
        bars = ctx.klines_daily
        score = 5.0
        tags: list[str] = []

        if quote:
            # Roughly classify by daily turnover
            if quote.amount >= 10:   # >10亿
                score = 8.0
                tags.append("流动性充足")
            elif quote.amount >= 3:
                score = 6.0
                tags.append("中性流动性")
            else:
                score = 3.0
                tags.append("流动性偏弱")

        if bars and len(bars) >= 5:
            avg_amount = sum(b.amount for b in bars[-5:]) / 5
            if avg_amount < 1:   # <1亿
                score = min(score, 3.0)
                tags.append("成交额偏低")

        out = self._base_output(score)
        out.core_conclusion = (
            f"日成交额约{quote.amount:.1f}万元。"
            f"流动性判断：{'、'.join(tags) or '待补充'}。"
            if quote else "流动性数据待获取。"
        )
        out.key_tags = tags
        return out


# ---------------------------------------------------------------------------
# M12 – 催化事件与前瞻预期分析
# ---------------------------------------------------------------------------
class CatalystAnalyzer(BaseAnalyzer):
    MODULE_ID = "M12"
    MODULE_TITLE = "催化事件与前瞻预期分析"
    MODULE_POSITIONING = "识别未来1–3个月能改变股价路径的关键事件窗口。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 5.0
        tags = ["催化事件数据待补充"]
        out = self._base_output(score)
        out.core_conclusion = "催化事件日历数据待进一步获取，评分取中性值。"
        out.key_tags = tags
        out.data_missing_fields = ["业绩披露窗口", "政策落地时间表", "重大订单", "解禁日期"]
        return out


# ---------------------------------------------------------------------------
# M13 – 历史走势规律与周期复盘
# ---------------------------------------------------------------------------
class HistoryAnalyzer(BaseAnalyzer):
    MODULE_ID = "M13"
    MODULE_TITLE = "历史走势规律与周期复盘"
    MODULE_POSITIONING = "从过去3年走势中提炼行为规律，辅助判断当下位置。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        bars = ctx.klines_daily
        if len(bars) < 60:
            return self._neutral_output("历史K线数据不足60日")

        closes = [b.close for b in bars]
        high_all = max(b.high for b in bars)
        low_all = min(b.low for b in bars)
        cur = closes[-1]
        drawdown_from_high = (high_all - cur) / max(high_all, 1e-9) * 100

        score = 5.0
        tags: list[str] = []
        if drawdown_from_high > 40:
            score = 7.0
            tags.append("已大幅回调")
        elif drawdown_from_high > 20:
            score = 6.0
            tags.append("中幅回调")
        else:
            score = 4.0
            tags.append("接近历史高位")

        out = self._base_output(score)
        out.core_conclusion = (
            f"历史最高价：{high_all:.2f}，当前价：{cur:.2f}，"
            f"距高点回撤：{drawdown_from_high:.1f}%。"
        )
        out.key_tags = tags
        return out


# ---------------------------------------------------------------------------
# M14 – 交易纪律与风控体系
# ---------------------------------------------------------------------------
class RiskControlAnalyzer(BaseAnalyzer):
    MODULE_ID = "M14"
    MODULE_TITLE = "交易纪律与风控体系"
    MODULE_POSITIONING = "将研究结论转化为有纪律的交易计划，避免情绪化操作。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        quote = ctx.quote
        bars = ctx.klines_daily
        score = 6.0
        tags = ["风控体系建立中"]

        stop_loss = ""
        target_1 = ""
        if quote and bars and len(bars) >= 20:
            cur = quote.price
            low_20 = min(b.low for b in bars[-20:])
            high_20 = max(b.high for b in bars[-20:])
            stop_loss = f"{low_20 * 0.97:.2f}（20日低点下方3%）"
            target_1 = f"{high_20 * 1.03:.2f}（20日高点上方3%）"

        out = self._base_output(score)
        out.core_conclusion = (
            f"参考止损位：{stop_loss or '待确认'}；参考第一目标：{target_1 or '待确认'}。"
        )
        out.key_tags = tags
        out.raw_data = {"stop_loss": stop_loss, "target_1": target_1}
        return out


# ---------------------------------------------------------------------------
# M15 – 同业对标与智能选股参考
# ---------------------------------------------------------------------------
class PeerComparisonAnalyzer(BaseAnalyzer):
    MODULE_ID = "M15"
    MODULE_TITLE = "同业对标与智能选股参考"
    MODULE_POSITIONING = "通过同行比较判断公司在行业中的梯队位置。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 5.0
        tags = ["同业对标数据待补充"]
        out = self._base_output(score)
        out.core_conclusion = "同业对标需要补充行业内可比公司数据。"
        out.key_tags = tags
        out.data_missing_fields = ["同行业3-5家可比公司估值与增速对比"]
        return out


# ---------------------------------------------------------------------------
# M19 – 盈利预测可信度评估
# ---------------------------------------------------------------------------
class EarningsForecastAnalyzer(BaseAnalyzer):
    MODULE_ID = "M19"
    MODULE_TITLE = "盈利预测可信度评估"
    MODULE_POSITIONING = "判断市场和公司当前业绩预测到底靠不靠谱。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 5.0
        tags = ["预测可信度数据待补充"]
        out = self._base_output(score)
        out.core_conclusion = "盈利预测可信度评估需要历史预告偏差率和管理层指引数据。"
        out.key_tags = tags
        out.data_missing_fields = ["历史业绩预告偏差率", "管理层指引", "订单验证度"]
        return out


# ---------------------------------------------------------------------------
# M20 – 业绩敏感性与利润弹性测算
# ---------------------------------------------------------------------------
class ProfitElasticityAnalyzer(BaseAnalyzer):
    MODULE_ID = "M20"
    MODULE_TITLE = "业绩敏感性与利润弹性测算"
    MODULE_POSITIONING = "判断公司利润对各变量的敏感度。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        fin = ctx.financial
        score = 5.0
        tags: list[str] = []

        if fin and fin.gross_margin is not None:
            if fin.gross_margin > 40:
                score = 7.0
                tags.append("高毛利高弹性")
            elif fin.gross_margin > 20:
                score = 5.5
                tags.append("中弹性")
            else:
                score = 4.0
                tags.append("低毛利低弹性")

        out = self._base_output(score)
        out.core_conclusion = f"利润弹性评分{score:.1f}，毛利率：{fin.gross_margin if fin else 'N/A'}%。"
        out.key_tags = tags or ["利润弹性数据待补充"]
        return out


# ---------------------------------------------------------------------------
# M21 – 资产质量与资本配置能力
# ---------------------------------------------------------------------------
class CapitalAllocationAnalyzer(BaseAnalyzer):
    MODULE_ID = "M21"
    MODULE_TITLE = "资产质量与资本配置能力"
    MODULE_POSITIONING = "判断公司是否会用好钱，资本配置是否高效。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        fin = ctx.financial
        score = 5.0
        tags: list[str] = []

        if fin and fin.roe is not None:
            if fin.roe > 20:
                score = 8.0
                tags.append("资本配置优秀")
            elif fin.roe > 12:
                score = 6.0
                tags.append("资本配置中性")
            else:
                score = 3.5
                tags.append("资本回报偏低")

        out = self._base_output(score)
        out.core_conclusion = f"ROE：{fin.roe if fin else 'N/A'}%，资本配置能力评分{score:.1f}。"
        out.key_tags = tags or ["资本配置数据待补充"]
        return out


# ---------------------------------------------------------------------------
# M22 – 股价驱动因子归因
# ---------------------------------------------------------------------------
class DriverAttributionAnalyzer(BaseAnalyzer):
    MODULE_ID = "M22"
    MODULE_TITLE = "股价驱动因子归因"
    MODULE_POSITIONING = "明确股价涨跌最核心的主驱动力是什么。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 5.0
        tags = ["驱动归因数据待补充"]
        out = self._base_output(score)
        out.core_conclusion = "股价驱动因子归因需要综合前序模块结论，待汇总分析。"
        out.key_tags = tags
        return out


# ---------------------------------------------------------------------------
# M23 – 风险情景压力测试
# ---------------------------------------------------------------------------
class StressTestAnalyzer(BaseAnalyzer):
    MODULE_ID = "M23"
    MODULE_TITLE = "风险情景压力测试"
    MODULE_POSITIONING = "模拟不利场景下标的可能的回撤、失效和应对路径。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        quote = ctx.quote
        score = 5.0
        tags: list[str] = []

        if quote:
            # Rough stress: 20% / 30% / 40% drawdown scenarios
            p = quote.price
            stress_mild = p * 0.80
            stress_mod = p * 0.70
            stress_severe = p * 0.60
            tags = [
                f"温和压力（-20%）：{stress_mild:.2f}",
                f"中度压力（-30%）：{stress_mod:.2f}",
                f"严重压力（-40%）：{stress_severe:.2f}",
            ]

        out = self._base_output(score)
        out.core_conclusion = "压力测试情景已初步建立，详细触发条件待完善。"
        out.key_tags = tags or ["压力测试数据待补充"]
        return out


# ---------------------------------------------------------------------------
# M24 – 持仓适配度分析
# ---------------------------------------------------------------------------
class PositionFitAnalyzer(BaseAnalyzer):
    MODULE_ID = "M24"
    MODULE_TITLE = "持仓适配度分析"
    MODULE_POSITIONING = "判断标的适合什么类型仓位，而不只是判断能不能买。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 5.0
        tags = ["持仓适配度待综合评估"]
        out = self._base_output(score)
        out.core_conclusion = "持仓适配度需综合三评分结果后输出，待三评分汇总完成。"
        out.key_tags = tags
        return out


# ---------------------------------------------------------------------------
# M25 – 退出机制、失效条件与动态跟踪清单
# ---------------------------------------------------------------------------
class ExitMechanismAnalyzer(BaseAnalyzer):
    MODULE_ID = "M25"
    MODULE_TITLE = "退出机制、失效条件与动态跟踪清单"
    MODULE_POSITIONING = "给出什么时候该卖、什么情况下逻辑失效、后续盯什么。"
    MAX_SCORE = 10.0

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        score = 6.0
        tags = ["退出机制待完善"]

        # Build invalidation list from available context
        invalidation = [
            "季报净利润同比大幅低于预期（超过-20%）",
            "行业政策出现明显利空转向",
            "技术面关键支撑（20日低点）跌破且未快速收复",
            "主力连续5日净流出超过成交额10%",
            "大股东公告清仓式减持",
        ]

        out = self._base_output(score)
        out.core_conclusion = "已建立基础退出逻辑失效条件清单，详细动态跟踪清单待结合具体分析完善。"
        out.key_tags = tags
        out.raw_data = {"invalidation_conditions": invalidation}
        return out
