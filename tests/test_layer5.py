"""Tests for Layer 5 – Template rendering."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.layer2_data.models import (
    AnalysisContext,
    AnalysisIntent,
    FullReport,
    MarketEnv,
    ModuleOutput,
    ScoreResult,
    StockBasic,
)
from src.layer4_report.report_assembler import ReportAssembler
from src.layer5_output.template_engine import TemplateEngine


def _ctx() -> AnalysisContext:
    return AnalysisContext(
        stock=StockBasic(code="600519", name="贵州茅台"),
        intent=AnalysisIntent.SINGLE_STOCK,
        query_text="分析贵州茅台",
        market_env=MarketEnv.SIDEWAYS,
        analysis_timestamp=datetime.now(),
        quote=None,
        klines_daily=[], klines_weekly=[], klines_monthly=[],
        financial=None, capital_flow=None, analyst_forecast=None,
        extra={},
    )


def _sample_report() -> FullReport:
    report = FullReport(context=_ctx())
    assembler = ReportAssembler()
    return assembler.assemble(report, {})


class TestTemplateEngine:
    def setup_method(self):
        self.engine = TemplateEngine()

    def test_render_scorecard_returns_html(self):
        report = _sample_report()
        html = self.engine.render_scorecard(report)
        assert "<html" in html or "<!DOCTYPE" in html or "<div" in html
        assert "综合投资价值" in html

    def test_render_module_card(self):
        mod = ModuleOutput(
            module_id="M01",
            module_title="公司业务拆解",
            module_positioning="基本面",
            core_conclusion="消费品龙头，护城河深厚",
            module_score=85.0,
            evidence_chain=[],
        )
        html = self.engine.render_module_card(mod)
        assert "公司业务拆解" in html
        assert "M01" in html


        report = _sample_report()
        html = self.engine.render_full_report(report)
        assert "贵州茅台" in html
        assert "综合投资价值" in html
        assert "现价买入性价比" in html
        assert "交易执行确定性" in html
        assert "情景分析" in html or "情景" in html

    def test_render_full_report_no_script_injection(self):
        """Basic XSS guard – module content is rendered with autoescape."""
        mod = ModuleOutput(
            module_id="M99",
            module_title="<script>alert(1)</script>",
            module_positioning="基本面",
            core_conclusion="<b>injection</b>",
            module_score=50.0,
            evidence_chain=[],
        )
        html = self.engine.render_module_card(mod)
        assert "<script>" not in html

    def test_render_full_report_is_string(self):
        report = _sample_report()
        html = self.engine.render_full_report(report)
        assert isinstance(html, str)
        assert len(html) > 1000
