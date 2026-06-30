"""Layer 1 – Stock query parser: extract stock code/name from natural language."""
from __future__ import annotations

import re

# Patterns for 6-digit A-share codes.
# Use digit lookahead/lookbehind instead of \b because CJK characters are \w
# in Python's Unicode regex, so \b doesn't fire between CJK chars and digits.
_CODE_PATTERNS = [
    re.compile(r"(?<![0-9])(6[0-9]{5})(?![0-9])"),    # 沪主板 600xxx / 601xxx / 603xxx / 605xxx
    re.compile(r"(?<![0-9])(0[0-9]{5})(?![0-9])"),    # 深主板 000xxx / 001xxx / 002xxx / 003xxx
    re.compile(r"(?<![0-9])(3[0-9]{5})(?![0-9])"),    # 创业板 300xxx / 301xxx
    re.compile(r"(?<![0-9])(68[0-9]{4})(?![0-9])"),   # 科创板 688xxx
    re.compile(r"(?<![0-9])(8[0-9]{5})(?![0-9])"),    # 北交所 830xxx-839xxx / 87xxxx / 88xxxx
    re.compile(r"(?<![0-9])(43[0-9]{4})(?![0-9])"),   # 北交所 43xxxx
]

# Commonly queried stock name → code mappings (seed list; production would query DB)
_KNOWN_STOCKS: dict[str, str] = {
    "茅台": "600519",
    "贵州茅台": "600519",
    "五粮液": "000858",
    "比亚迪": "002594",
    "宁德时代": "300750",
    "中芯国际": "688981",
    "招商银行": "600036",
    "腾讯": "000001",  # placeholder – H-share only; A-share proxy
    "平安": "601318",
    "中国平安": "601318",
    "宁王": "300750",
    "迈瑞医疗": "300760",
    "药明康德": "603259",
    "海天味业": "603288",
    "东方财富": "300059",
    "万科": "000002",
    "格力电器": "000651",
    "美的集团": "000333",
    "隆基绿能": "601012",
    "中联重科": "000157",
}


class StockQueryParser:
    """Extract a stock code from free-form user input."""

    def parse(self, query: str) -> str | None:
        """Return a 6-digit A-share code or *None* if not found."""
        # 1. Try explicit 6-digit code
        for pattern in _CODE_PATTERNS:
            m = pattern.search(query)
            if m:
                return m.group(1).zfill(6)

        # 2. Try known stock name lookup (longest match wins)
        best_match: tuple[str, str] | None = None
        for name, code in _KNOWN_STOCKS.items():
            if name in query:
                if best_match is None or len(name) > len(best_match[0]):
                    best_match = (name, code)
        if best_match:
            return best_match[1]

        return None

    def extract_all_codes(self, query: str) -> list[str]:
        """Extract all mentioned stock codes (for multi-stock compare)."""
        codes: list[str] = []
        for pattern in _CODE_PATTERNS:
            codes.extend(m.group(1).zfill(6) for m in pattern.finditer(query))
        for name, code in _KNOWN_STOCKS.items():
            if name in query and code not in codes:
                codes.append(code)
        return list(dict.fromkeys(codes))  # deduplicate while preserving order
