"""Layer 4 – Vagueness filter: intercept forbidden ambiguous phrases."""
from __future__ import annotations

import re

# Phrases explicitly forbidden by V5.0 spec Section 15.2
_FORBIDDEN_PATTERNS = [
    r"谨慎关注(?!.*(?:条件|价位|仓位|止损))",
    r"逢低布局(?!.*(?:\d+|条件|价位|仓位|止损))",
    r"谨慎乐观(?!.*(?:条件|价位|仓位|止损))",
    r"可适当参与(?!.*(?:条件|价位|仓位|止损))",
    r"建议观察(?!.*(?:条件|价位|仓位|止损))",
    r"值得关注(?!.*(?:条件|价位|仓位|止损))",
]

_COMPILED = [re.compile(p) for p in _FORBIDDEN_PATTERNS]


class VaguenessFilter:
    """Detect and flag vague, non-actionable phrases in report text."""

    def scan(self, text: str) -> list[str]:
        """Return list of forbidden phrases found in *text*."""
        found: list[str] = []
        for pattern in _COMPILED:
            if pattern.search(text):
                found.append(pattern.pattern.split("(?!")[0])
        return found

    def enforce(self, text: str) -> str:
        """Replace forbidden bare phrases with placeholder prompts."""
        result = text
        replacements = {
            "谨慎关注": "谨慎关注（需补充：关注条件/价位/仓位/止损）",
            "逢低布局": "逢低布局（需补充：低位区间/仓位比例/止损位）",
            "谨慎乐观": "谨慎乐观（需补充：乐观触发条件/目标位）",
            "可适当参与": "可适当参与（需补充：参与条件/仓位上限/止损位）",
            "建议观察": "建议观察（需补充：观察条件/触发信号/时间窗口）",
            "值得关注": "值得关注（需补充：关注条件/买入触发信号）",
        }
        issues = self.scan(text)
        for issue in issues:
            bare = issue.replace("(?!.*(?:条件|价位|仓位|止损))", "")
            if bare in replacements:
                result = result.replace(bare, replacements[bare], 1)
        return result
