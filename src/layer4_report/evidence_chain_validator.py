"""Layer 4 – Evidence chain validator."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..layer2_data.models import EvidenceItem, EvidenceStrength, ModuleOutput

logger = logging.getLogger(__name__)

# Keywords that require strong evidence backing
_STRONG_CLAIM_KEYWORDS = [
    "低估", "高估", "资金认可", "盈利改善", "景气持续", "确定性高",
    "安全边际充足", "护城河深厚",
]


@dataclass
class EvidenceReport:
    unsupported_claims: list[str] = field(default_factory=list)
    weak_evidence_claims: list[str] = field(default_factory=list)
    is_valid: bool = True


class EvidenceChainValidator:
    """Verify that key conclusions in each module are backed by evidence.

    Rules from V5.0 spec Section 15:
    - "低估" → requires historical percentile or industry comparison
    - "资金认可" → requires net-inflow or position-change data
    - "盈利改善" → requires at least two of: revenue / profit / cashflow
    """

    def validate_module(self, module: ModuleOutput) -> EvidenceReport:
        report = EvidenceReport()
        conclusion = module.core_conclusion

        for keyword in _STRONG_CLAIM_KEYWORDS:
            if keyword in conclusion:
                # Check if there is supporting evidence of at least MEDIUM strength
                has_support = any(
                    e.strength in (EvidenceStrength.STRONG, EvidenceStrength.MEDIUM)
                    for e in module.evidence_chain
                )
                if not has_support:
                    report.unsupported_claims.append(
                        f"[{module.module_id}] 结论含'{keyword}'但缺少足够证据支撑"
                    )
                    report.is_valid = False

        # Flag weak-only evidence
        for ev in module.evidence_chain:
            if ev.strength == EvidenceStrength.WEAK:
                report.weak_evidence_claims.append(
                    f"[{module.module_id}] '{ev.conclusion}' 仅弱证据支撑"
                )

        return report

    def validate_all(
        self, modules: dict[str, ModuleOutput]
    ) -> tuple[bool, list[str]]:
        all_issues: list[str] = []
        overall_valid = True
        for mod in modules.values():
            rep = self.validate_module(mod)
            if not rep.is_valid:
                overall_valid = False
            all_issues.extend(rep.unsupported_claims)
            all_issues.extend(rep.weak_evidence_claims)
        if all_issues:
            for issue in all_issues:
                logger.info("[EvidenceChain] %s", issue)
        return overall_valid, all_issues
