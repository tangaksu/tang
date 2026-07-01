"""M02 – 财务质量深度核验."""
from __future__ import annotations

from ...layer2_data.models import AnalysisContext, EvidenceStrength, ModuleOutput
from ..base_analyzer import BaseAnalyzer


class FinancialAnalyzer(BaseAnalyzer):
    MODULE_ID = "M02"
    MODULE_TITLE = "财务质量深度核验"
    MODULE_POSITIONING = "识别利润质量、现金流质量和财务安全性，重点排雷。"
    MAX_SCORE = 10.0

    # Red flag labels
    _RED_FLAGS = [
        "利润增速显著高于收入增速",
        "经营现金流长期弱于净利润",
        "应收/存货增速明显快于收入",
        "商誉占比过高",
        "存贷双高",
        "资本化研发异常",
        "关联交易依赖度高",
    ]

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        fin = ctx.financial
        if fin is None:
            return self._neutral_output("财务数据未获取")

        # ------ Heuristic scoring ------
        score = 0.0
        red_flags: list[str] = []
        tags: list[str] = []

        # 1. 盈利成长性 (2分)
        if fin.net_profit_yoy is not None:
            if fin.net_profit_yoy > 20:
                score += 2.0
                tags.append("高速成长")
            elif fin.net_profit_yoy > 5:
                score += 1.2
                tags.append("稳健增长")
            else:
                score += 0.5
                tags.append("增长偏弱")
        else:
            score += 1.0  # neutral
            tags.append("成长数据缺失")

        # 2. 盈利质量 (2分)
        if fin.deducted_profit is not None and fin.net_profit is not None:
            ratio = fin.deducted_profit / max(fin.net_profit, 1e-9)
            if ratio >= 0.85:
                score += 2.0
                tags.append("高质量报表")
            elif ratio >= 0.6:
                score += 1.2
                tags.append("盈利质量中性")
            else:
                score += 0.3
                tags.append("存在财务红旗")
                red_flags.append("扣非弱于归母，利润质量存疑")
        else:
            score += 1.0

        # 3. 现金流健康度 (2分)
        if fin.operating_cashflow is not None and fin.net_profit is not None:
            ratio = fin.operating_cashflow / max(fin.net_profit, 1e-9)
            if ratio >= 1.0:
                score += 2.0
                tags.append("现金流改善")
            elif ratio >= 0.7:
                score += 1.2
            else:
                score += 0.3
                red_flags.append("经营现金流明显弱于净利润")
        else:
            score += 1.0

        # 4. 财务安全性 (2分)
        if fin.debt_ratio is not None:
            if fin.debt_ratio < 40:
                score += 2.0
            elif fin.debt_ratio < 60:
                score += 1.2
            else:
                score += 0.3
                red_flags.append(f"资产负债率偏高：{fin.debt_ratio:.1f}%")
        else:
            score += 1.0

        # 5. 股东回报 (2分)
        if fin.dividend_yield is not None and fin.dividend_yield > 3:
            score += 2.0
            tags.append("高股息")
        elif fin.roe is not None and fin.roe > 15:
            score += 1.5
            tags.append("ROE优秀")
        else:
            score += 0.8

        out = self._base_output(score)
        out.core_conclusion = (
            f"财务质量综合评分 {score:.1f}/{self.MAX_SCORE}。"
            + (f" 发现{len(red_flags)}项财务红旗，需警惕。" if red_flags else " 暂无明显财务红旗。")
        )
        out.key_tags = tags
        out.risk_deductions = red_flags
        out.evidence_chain = [
            self._evidence(
                conclusion=f"净利润同比增速：{fin.net_profit_yoy}%",
                evidence_type="财务证据",
                strength=EvidenceStrength.STRONG if fin.net_profit_yoy is not None else EvidenceStrength.WEAK,
                source="AKShare财务摘要",
            ),
            self._evidence(
                conclusion=f"ROE：{fin.roe}%，资产负债率：{fin.debt_ratio}%",
                evidence_type="财务证据",
                strength=EvidenceStrength.MEDIUM,
                source="AKShare财务摘要",
            ),
        ]
        out.factor_tree.facts = [
            f"报告期：{fin.period}",
            f"营收同比：{fin.revenue_yoy}%",
            f"净利润同比：{fin.net_profit_yoy}%",
            f"毛利率：{fin.gross_margin}%",
            f"ROE：{fin.roe}%",
            f"资产负债率：{fin.debt_ratio}%",
        ]
        out.factor_tree.explanations = [
            f"利润含金量{'较高' if not red_flags else '存疑，需核对现金流与非经常性损益'}",
        ]
        out.factor_tree.judgements = [
            f"财务质量：{'高质量' if score >= 7 else '中性' if score >= 5 else '存在风险'}",
        ]
        out.factor_tree.scores_summary = f"总分 {score:.1f}/{self.MAX_SCORE}"
        out.factor_tree.actions = [
            "持续跟踪季报现金流与扣非利润变化",
            "关注商誉、应收账款规模变化",
        ]
        return out
