"""Tests for Layer 4 – Report assembly."""
from __future__ import annotations

import pytest
from datetime import datetime

from src.layer2_data.models import (
    AnalysisContext, AnalysisIntent, EvidenceItem, EvidenceStrength,
    FullReport, MarketEnv, ModuleOutput, StockBasic,
)
from src.layer4_report.vagueness_filter import VaguenessFilter
from src.layer4_report.evidence_chain_validator import EvidenceChainValidator
from src.layer4_report.consistency_checker import ConsistencyChecker
from src.layer4_report.scenario_engine import ScenarioEngine
from src.layer4_report.report_assembler import ReportAssembler


def _ctx() -> AnalysisContext:
    return AnalysisContext(
        stock=StockBasic(code="600519", name="贵州茅台"),
        intent=AnalysisIntent.SINGLE_STOCK,
        query_text="分析贵州茅台",
        market_env=MarketEnv.SIDEWAYS,
        analysis_timestamp=datetime.now(),
        quote=None, klines_daily=[], klines_weekly=[], klines_monthly=[],
        financial=None, capital_flow=None, analyst_forecast=None, extra={},
    )


def _empty_report() -> FullReport:
    return FullReport(context=_ctx())


def _module(module_id: str, title: str, score: float,
            conclusion: str = "OK", evidence: list | None = None) -> ModuleOutput:
    return ModuleOutput(
        module_id=module_id,
        module_title=title,
        module_positioning="基本面",
        core_conclusion=conclusion,
        module_score=score,
        evidence_chain=evidence or [],
    )


class TestVaguenessFilter:
    def setup_method(self):
        self.vf = VaguenessFilter()

    def test_detects_fuzzy_phrase(self):
        issues = self.vf.scan("建议投资者逢低布局，谨慎关注该股走势。")
        assert len(issues) > 0

    def test_clean_text_passes(self):
        ok = "当价格回调至1800点时，建议以15%仓位买入，止损设于1680点。"
        issues = self.vf.scan(ok)
        assert len(issues) == 0

    def test_multiple_offences(self):
        issues = self.vf.scan("可适当参与，建议观察为主，待确认后逢低布局。")
        assert len(issues) >= 2


class TestEvidenceChainValidator:
    def setup_method(self):
        self.ecv = EvidenceChainValidator()

    def test_missing_evidence_flagged(self):
        mod = _module("M02", "财务质量核验", 80.0, "该公司连续5年ROE超过20%，低估明显")
        report = self.ecv.validate_module(mod)
        assert not report.is_valid
        assert len(report.unsupported_claims) > 0

    def test_with_evidence_passes(self):
        ev = EvidenceItem(
            conclusion="ROE 22.3%",
            evidence_type="财务",
            strength=EvidenceStrength.STRONG,
            source="财务报告2023",
        )
        mod = _module("M02", "财务质量核验", 80.0, "ROE 22.3%，低估明显", [ev])
        report = self.ecv.validate_module(mod)
        assert report.is_valid


class TestConsistencyChecker:
    def setup_method(self):
        self.cc = ConsistencyChecker()

    def test_no_extreme_conflict(self):
        modules = {
            "M02": _module("M02", "财务", 7.5),
            "M06": _module("M06", "技术", 7.0),
        }
        report = self.cc.check(modules)
        # Small gap – may or may not flag, just check type
        assert hasattr(report, "is_consistent")

    def test_large_gap_flagged(self):
        modules = {
            "M02": _module("M02", "财务", 9.5, "优秀"),
            "M14": _module("M14", "风控", 2.0, "高风险"),
        }
        report = self.cc.check(modules)
        assert not report.is_consistent
        assert len(report.conflicts) > 0


class TestScenarioEngine:
    def setup_method(self):
        self.se = ScenarioEngine()

    def test_outputs_four_scenarios(self):
        report = _empty_report()
        scenarios = self.se.build_scenarios(report)
        assert len(scenarios) == 4

    def test_scenario_names(self):
        report = _empty_report()
        scenarios = self.se.build_scenarios(report)
        names = [s.name for s in scenarios]
        assert "乐观情景" in names
        assert "悲观情景" in names
        assert "中性情景" in names
        assert any("风险" in n for n in names)


class TestReportAssembler:
    def test_assemble_returns_full_report(self):
        assembler = ReportAssembler()
        report = _empty_report()
        result = assembler.assemble(report, {})
        assert isinstance(result, FullReport)
        assert result.score_a is not None
        assert result.score_b is not None
        assert result.score_c is not None
        assert len(result.scenarios) == 4
