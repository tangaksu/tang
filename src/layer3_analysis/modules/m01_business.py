"""M01 – 公司基础与业务拆解."""
from __future__ import annotations

from ...layer2_data.models import AnalysisContext, EvidenceStrength, ModuleOutput
from ..base_analyzer import BaseAnalyzer


class BusinessAnalyzer(BaseAnalyzer):
    MODULE_ID = "M01"
    MODULE_TITLE = "公司基础与业务拆解"
    MODULE_POSITIONING = "搭建上市公司业务底座，识别商业模式质量、产业链位置与成长路径。"
    MAX_SCORE = 10.0

    # Sub-dimension weights (total 10)
    _W_CLARITY = 2.0     # 主营业务集中度
    _W_MODEL = 2.0       # 商业模式质量
    _W_POSITION = 2.0    # 产业链卡位优势
    _W_MOAT = 2.0        # 核心壁垒厚度
    _W_GROWTH = 2.0      # 成长路径可验证性

    def analyze(self, ctx: AnalysisContext) -> ModuleOutput:
        stock = ctx.stock
        quote = ctx.quote

        if quote is None:
            return self._neutral_output("行情数据缺失")

        # Infer scores from available data (rule-based heuristics)
        # In production these would use LLM-driven structured extraction
        # from company filings / annual reports.

        # Placeholder: assign mid-level scores, flag missing data
        s_clarity = self._W_CLARITY * 0.6
        s_model = self._W_MODEL * 0.6
        s_position = self._W_POSITION * 0.6
        s_moat = self._W_MOAT * 0.6
        s_growth = self._W_GROWTH * 0.6
        total = s_clarity + s_model + s_position + s_moat + s_growth

        out = self._base_output(total)
        out.core_conclusion = (
            f"{stock.name}（{stock.code}）主营业务信息待详细补充；"
            "当前基于公开行情数据进行初步评估，置信度中等。"
        )
        out.key_tags = [stock.industry or "待确认行业", "待补充业务标签"]
        out.risk_deductions = ["公司详细业务数据尚未获取，评分基于行业中位数估算"]
        out.evidence_chain = [
            self._evidence(
                conclusion=f"标的所属行业：{stock.industry or '未知'}",
                evidence_type="行业证据",
                strength=EvidenceStrength.MEDIUM,
                source="AKShare股票信息",
            )
        ]
        out.factor_tree.facts = [
            f"公司名称：{stock.name}",
            f"股票代码：{stock.code}",
            f"所属行业：{stock.industry or '待确认'}",
            f"上市板块：{stock.market or '待确认'}",
        ]
        out.factor_tree.explanations = [
            "主营业务结构需结合年报进行详细拆解",
            "商业模式质量判断需要更多财务数据支撑",
        ]
        out.factor_tree.judgements = [
            "当前数据不足以做出高置信度业务质量判断",
        ]
        out.factor_tree.scores_summary = (
            f"总分 {total:.1f}/{self.MAX_SCORE}，各子维度均取中性分，数据待补充"
        )
        out.factor_tree.actions = [
            "建议获取完整年报和季报后重新评估业务质量",
        ]
        out.data_missing_fields = ["主营业务拆解", "产品结构", "客户集中度", "产能数据"]
        return out
