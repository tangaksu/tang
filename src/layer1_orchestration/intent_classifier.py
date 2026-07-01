"""Layer 1 – Intent classifier: identify the analysis scenario from user input."""
from __future__ import annotations

import re

from ..layer2_data.models import AnalysisIntent


# Keywords per intent (ordered by specificity)
_INTENT_RULES: list[tuple[AnalysisIntent, list[str]]] = [
    (AnalysisIntent.MULTI_STOCK_COMPARE, [
        "对比", "比较", "哪个更好", "哪只更好", "vs", "VS", "versus",
        "换股", "替代", "选哪个", "优先哪个",
    ]),
    (AnalysisIntent.STOCK_SELECTION, [
        "选股", "推荐几只", "筛选", "有哪些", "哪些股票", "给我推荐",
        "策略工厂", "高股息", "低估值股", "成长股推荐",
    ]),
    (AnalysisIntent.POSITION_REVIEW, [
        "我持有", "我买了", "我现在持仓", "已经建仓", "成本价",
        "解套", "亏损", "浮盈", "加不加仓", "要不要减仓",
    ]),
    (AnalysisIntent.ST_STOCK, [
        "ST", "*ST", "风险警示", "退市风险", "暂停上市",
    ]),
    (AnalysisIntent.NEW_STOCK, [
        "新股", "次新股", "上市首日", "打新", "刚上市",
    ]),
    (AnalysisIntent.INDEX, [
        "指数", "沪深300", "创业板指", "科创50", "上证", "深证",
        "大盘", "A股整体", "ETF",
    ]),
]

_DEFAULT_INTENT = AnalysisIntent.SINGLE_STOCK

# ST pattern
_ST_PATTERN = re.compile(r"\b\*?ST[^\s]{1,4}", re.IGNORECASE)


class IntentClassifier:
    """Classify user query into one of the AnalysisIntent categories."""

    def classify(self, query: str, codes: list[str] | None = None) -> AnalysisIntent:
        # ST stock check via code pattern or keyword
        if _ST_PATTERN.search(query):
            return AnalysisIntent.ST_STOCK

        # Multiple codes → compare intent
        if codes and len(codes) >= 2:
            return AnalysisIntent.MULTI_STOCK_COMPARE

        # Keyword matching (first match wins in priority order)
        for intent, keywords in _INTENT_RULES:
            for kw in keywords:
                if kw in query:
                    return intent

        return _DEFAULT_INTENT
