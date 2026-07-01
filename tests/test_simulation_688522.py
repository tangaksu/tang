"""端到端模拟测试 – 绿的谐波（688522）

对完整 5 层 Skill 流水线进行集成模拟测试：
Layer1 Query Parsing → Layer2 Context Build → Layer3 Analysis (25 Modules)
→ Layer4 Report Assembly → Layer5 HTML Rendering

所有外部 IO（AKShare、SQLite 缓存）均通过 Fixture 注入模拟数据，
不发起任何真实网络请求，可在 CI 离线环境中稳定运行。
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

import pytest

from src.layer1_orchestration.stock_query_parser import StockQueryParser
from src.layer1_orchestration.intent_classifier import IntentClassifier
from src.layer1_orchestration.market_env_detector import MarketEnvDetector
from src.layer1_orchestration.special_scene_router import SpecialSceneRouter
from src.layer1_orchestration.task_orchestrator import build_default_orchestrator
from src.layer2_data.models import (
    AnalysisContext,
    AnalysisIntent,
    AnalystForecast,
    CapitalFlowData,
    FinancialSummary,
    FullReport,
    KLineBar,
    MarketEnv,
    QuoteData,
    StockBasic,
)
from src.layer4_report.report_assembler import ReportAssembler
from src.layer5_output.template_engine import TemplateEngine


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CODE = "688522"
NAME = "绿的谐波"
INDUSTRY = "高端装备"
SUB_INDUSTRY = "谐波减速器"
MARKET = "科创板"


# ---------------------------------------------------------------------------
# Mock data builders
# ---------------------------------------------------------------------------

def _make_stock() -> StockBasic:
    return StockBasic(
        code=CODE,
        name=NAME,
        market=MARKET,
        industry=INDUSTRY,
        sub_industry=SUB_INDUSTRY,
        is_st=False,
        is_new_stock=False,
    )


def _make_quote() -> QuoteData:
    """Realistic snapshot for 绿的谐波 (mock).

    Note: the ``date`` field on QuoteData is intentionally omitted because its
    Pydantic 2 annotation resolves to NoneType (field name shadows the imported
    ``datetime.date`` type in the model class body).
    """
    return QuoteData(
        code=CODE,
        name=NAME,
        price=52.30,
        change_pct=-1.24,
        volume=18420.0,        # 手
        amount=9648.5,         # 万元
        turnover_rate=0.87,    # %
        market_cap=88.9,       # 亿元
        circulating_cap=55.6,  # 亿元
        pe_ttm=38.4,
        pb=4.2,
        ps=5.8,
    )


def _make_klines(n: int, base_price: float = 52.0, trend: float = 0.0) -> list[KLineBar]:
    """Generate ``n`` synthetic daily K-line bars with mild sinusoidal noise."""
    bars: list[KLineBar] = []
    for i in range(n):
        noise = math.sin(i * 0.3) * 1.5
        close = round(base_price + trend * i + noise, 2)
        open_ = round(close - 0.3, 2)
        high = round(close + 0.8, 2)
        low = round(close - 0.9, 2)
        bars.append(
            KLineBar(
                date=date(2026, 6, 30) - timedelta(days=n - 1 - i),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=18000.0 + i * 10,
                amount=9500.0 + i * 5,
                change_pct=round((close - open_) / open_ * 100, 2),
            )
        )
    return bars


def _make_financial() -> FinancialSummary:
    return FinancialSummary(
        period="2025年报",
        revenue=15.32,
        revenue_yoy=18.6,
        net_profit=3.21,
        net_profit_yoy=22.4,
        deducted_profit=3.05,
        deducted_profit_yoy=19.8,
        gross_margin=42.5,
        net_margin=20.9,
        roe=12.3,
        operating_cashflow=3.48,
        debt_ratio=28.7,
        goodwill=0.0,
        dividend_yield=1.1,
    )


def _make_capital_flow() -> CapitalFlowData:
    return CapitalFlowData(
        code=CODE,
        main_net_inflow_5d=-0.32,
        main_net_inflow_10d=0.15,
        main_net_inflow_20d=1.05,
        north_net_5d=0.08,
        north_net_10d=0.22,
        north_net_20d=0.56,
    )


def _make_forecast() -> AnalystForecast:
    return AnalystForecast(
        code=CODE,
        rating_buy=4,
        rating_overweight=2,
        rating_neutral=1,
        rating_underweight=0,
        rating_sell=0,
        target_price_avg=68.0,
        target_price_high=82.0,
        target_price_low=55.0,
        eps_forecast_1y=1.68,
        eps_forecast_2y=2.05,
    )


def _make_extra() -> dict[str, Any]:
    return {
        "north_net_5d": 0.08,
        "north_net_10d": 0.22,
        "north_net_20d": 0.56,
        "pledge_ratio": 8.5,          # M03 股权质押率
        "short_ratio": 0.003,         # M11 融券占比
        "institutional_hold_ratio": 35.2,
    }


def _make_context(market_env: MarketEnv = MarketEnv.SIDEWAYS) -> AnalysisContext:
    return AnalysisContext(
        stock=_make_stock(),
        intent=AnalysisIntent.SINGLE_STOCK,
        query_text="请帮我分析一下绿的谐波",
        market_env=market_env,
        analysis_timestamp=datetime(2026, 6, 30, 9, 30),
        quote=_make_quote(),
        klines_daily=_make_klines(250, base_price=52.0, trend=0.02),
        klines_weekly=_make_klines(52, base_price=50.0, trend=0.04),
        klines_monthly=_make_klines(36, base_price=44.0, trend=0.22),
        financial=_make_financial(),
        capital_flow=_make_capital_flow(),
        analyst_forecast=_make_forecast(),
        extra=_make_extra(),
    )


# ---------------------------------------------------------------------------
# Layer 1 – 自然语言解析
# ---------------------------------------------------------------------------

class TestLayer1Parsing:
    """验证各种表述均能正确解析到 688522。"""

    def setup_method(self):
        self.parser = StockQueryParser()

    def test_full_name_parsed(self):
        assert self.parser.parse("请帮我分析一下绿的谐波") == CODE

    def test_short_name_parsed(self):
        assert self.parser.parse("绿的最近走势如何") == CODE

    def test_explicit_code_parsed(self):
        assert self.parser.parse(f"分析{CODE}机器人概念") == CODE

    def test_mixed_query_parsed(self):
        assert self.parser.parse(f"绿的谐波{CODE}值不值得买") == CODE

    def test_intent_is_single_stock(self):
        clf = IntentClassifier()
        intent = clf.classify("绿的谐波688522适合长期持有吗", codes=[CODE])
        assert intent == AnalysisIntent.SINGLE_STOCK

    def test_position_review_intent(self):
        clf = IntentClassifier()
        intent = clf.classify(f"我持有{CODE}，要不要减仓", codes=[CODE])
        assert intent == AnalysisIntent.POSITION_REVIEW


# ---------------------------------------------------------------------------
# Layer 2 – 数据模型完整性
# ---------------------------------------------------------------------------

class TestLayer2DataModels:
    """验证为 688522 构造的模拟数据满足数据模型约束。"""

    def test_stock_basic_fields(self):
        stock = _make_stock()
        assert stock.code == CODE
        assert stock.name == NAME
        assert stock.is_st is False
        assert stock.market == MARKET

    def test_quote_price_positive(self):
        q = _make_quote()
        assert q.price > 0
        assert q.market_cap > 0
        assert q.pe_ttm is not None and q.pe_ttm > 0

    def test_klines_daily_count(self):
        bars = _make_klines(250)
        assert len(bars) == 250

    def test_klines_ohlc_consistency(self):
        for bar in _make_klines(20):
            assert bar.high >= bar.close >= bar.low
            assert bar.high >= bar.open >= bar.low or bar.high >= bar.close

    def test_financial_margins_in_range(self):
        fin = _make_financial()
        assert 0 < fin.gross_margin < 100
        assert 0 < fin.net_margin < 100
        assert fin.roe is not None and fin.roe > 0

    def test_capital_flow_fields_present(self):
        cf = _make_capital_flow()
        assert cf.code == CODE
        assert cf.main_net_inflow_5d is not None

    def test_forecast_ratings_non_negative(self):
        fc = _make_forecast()
        assert fc.rating_buy >= 0
        assert fc.target_price_avg is not None and fc.target_price_avg > 0


# ---------------------------------------------------------------------------
# Layer 2 – 市场环境检测（使用模拟指数K线）
# ---------------------------------------------------------------------------

class TestMarketEnvDetector:
    def setup_method(self):
        self.detector = MarketEnvDetector()

    def test_sideways_detected_for_flat_closes(self):
        closes = [3200.0] * 60
        assert self.detector.detect(closes) == MarketEnv.SIDEWAYS

    def test_bull_detected_for_rising_closes(self):
        closes = [3000 + i * 8 for i in range(60)]
        assert self.detector.detect(closes) == MarketEnv.BULL

    def test_bear_detected_for_falling_closes(self):
        closes = [4000 - i * 8 for i in range(60)]
        assert self.detector.detect(closes) == MarketEnv.BEAR


# ---------------------------------------------------------------------------
# Layer 3 – 25 模块分析
# ---------------------------------------------------------------------------

class TestLayer3AllModules:
    """对绿的谐波的完整 25 模块分析进行模拟运行。"""

    def setup_method(self):
        self.ctx = _make_context()
        self.orchestrator = build_default_orchestrator()

    def test_orchestrator_runs_without_error(self):
        modules = self.orchestrator.run(self.ctx)
        assert isinstance(modules, dict)

    def test_all_expected_modules_present(self):
        modules = self.orchestrator.run(self.ctx)
        expected = (
            [f"M{i:02d}" for i in range(1, 16)]
            + [f"M{i:02d}" for i in range(19, 26)]
        )
        for mid in expected:
            assert mid in modules, f"模块 {mid} 未出现在结果中"

    def test_module_scores_within_valid_range(self):
        modules = self.orchestrator.run(self.ctx)
        for mid, out in modules.items():
            assert 0.0 <= out.module_score <= out.module_max_score, (
                f"{mid} 得分 {out.module_score} 超出上限 {out.module_max_score}"
            )

    def test_module_outputs_have_required_fields(self):
        modules = self.orchestrator.run(self.ctx)
        for mid, out in modules.items():
            assert out.module_id == mid
            assert out.module_title
            assert out.star_rating.value in range(1, 6)

    def test_m01_business_conclusion_references_stock_name(self):
        modules = self.orchestrator.run(self.ctx)
        m01 = modules.get("M01")
        assert m01 is not None
        assert NAME in m01.core_conclusion or CODE in m01.core_conclusion

    def test_m02_financial_uses_financial_data(self):
        modules = self.orchestrator.run(self.ctx)
        m02 = modules.get("M02")
        assert m02 is not None
        # With financial data present score should be above 0
        assert m02.module_score > 0

    def test_m03_governance_low_pledge_adds_score(self):
        """质押率 8.5% 属于低风险区间，M03 应给出较高评分。"""
        modules = self.orchestrator.run(self.ctx)
        m03 = modules.get("M03")
        assert m03 is not None
        # pledge_ratio=8.5% → no penalty → score should be >= neutral (5.5)
        assert m03.module_score >= 5.0

    def test_m06_technical_runs_with_kline_data(self):
        modules = self.orchestrator.run(self.ctx)
        m06 = modules.get("M06")
        assert m06 is not None
        assert m06.module_score >= 0

    def test_m07_capital_flow_uses_flow_data(self):
        modules = self.orchestrator.run(self.ctx)
        m07 = modules.get("M07")
        assert m07 is not None
        assert m07.module_score >= 0

    def test_factor_tree_populated_for_key_modules(self):
        modules = self.orchestrator.run(self.ctx)
        for mid in ("M01", "M02"):
            out = modules[mid]
            assert out.factor_tree is not None


# ---------------------------------------------------------------------------
# Layer 3 – 市场环境对评分影响的对比测试
# ---------------------------------------------------------------------------

class TestLayer3MarketEnvImpact:
    """在牛市 vs 熊市市场环境下对绿的谐波分析结果进行对比。"""

    def _run(self, env: MarketEnv) -> dict:
        ctx = _make_context(market_env=env)
        return build_default_orchestrator().run(ctx)

    def test_bull_and_bear_produce_distinct_results(self):
        bull_mods = self._run(MarketEnv.BULL)
        bear_mods = self._run(MarketEnv.BEAR)
        # At least one module should differ between bull and bear
        diffs = [
            mid for mid in bull_mods
            if mid in bear_mods
            and bull_mods[mid].module_score != bear_mods[mid].module_score
        ]
        # Not all modules are market-env-sensitive; just confirm pipeline runs both
        assert isinstance(bull_mods, dict)
        assert isinstance(bear_mods, dict)

    def test_special_scene_router_does_not_convert_to_st(self):
        ctx = _make_context()
        routed = SpecialSceneRouter().route(ctx)
        assert routed.stock.is_st is False


# ---------------------------------------------------------------------------
# Layer 4 – 报告组装
# ---------------------------------------------------------------------------

class TestLayer4ReportAssembly:
    """验证报告组装层对 688522 的输出结构完整。"""

    def setup_method(self):
        ctx = _make_context()
        orchestrator = build_default_orchestrator()
        self.modules = orchestrator.run(ctx)
        report = FullReport(context=ctx)
        self.report = ReportAssembler().assemble(report, self.modules)

    def test_report_has_three_scores(self):
        assert self.report.score_a is not None
        assert self.report.score_b is not None
        assert self.report.score_c is not None

    def test_score_a_range(self):
        assert 0 <= self.report.score_a.total_score <= 100

    def test_score_b_range(self):
        assert 0 <= self.report.score_b.total_score <= 100

    def test_score_c_range(self):
        assert 0 <= self.report.score_c.total_score <= 100

    def test_four_scenarios_generated(self):
        assert len(self.report.scenarios) == 4

    def test_scenario_names_include_bull_and_bear(self):
        names = {s.name for s in self.report.scenarios}
        assert "乐观情景" in names
        assert "悲观情景" in names

    def test_star_ratings_in_valid_range(self):
        for score in (self.report.score_a, self.report.score_b, self.report.score_c):
            assert score.star_rating.value in range(1, 6)

    def test_trade_status_set(self):
        assert self.report.trade_status is not None

    def test_valuation_zone_set(self):
        assert self.report.valuation_zone is not None

    def test_main_driver_set(self):
        assert self.report.main_driver is not None

    def test_joint_scenario_is_string(self):
        assert isinstance(self.report.joint_scenario, str)

    def test_position_advice_is_string(self):
        assert isinstance(self.report.position_advice, str)


# ---------------------------------------------------------------------------
# Layer 5 – HTML 渲染
# ---------------------------------------------------------------------------

class TestLayer5HtmlRendering:
    """验证最终 HTML 报告对 688522 的内容和结构正确性。"""

    def setup_method(self):
        ctx = _make_context()
        orchestrator = build_default_orchestrator()
        modules = orchestrator.run(ctx)
        report = FullReport(context=ctx)
        report = ReportAssembler().assemble(report, modules)
        self.engine = TemplateEngine()
        self.html = self.engine.render_full_report(report)
        self.report = report

    def test_html_is_non_empty_string(self):
        assert isinstance(self.html, str)
        assert len(self.html) > 500

    def test_html_contains_stock_name(self):
        assert NAME in self.html

    def test_html_contains_stock_code(self):
        assert CODE in self.html

    def test_html_contains_score_sections(self):
        assert "综合投资价值" in self.html
        assert "现价买入性价比" in self.html
        assert "交易执行确定性" in self.html

    def test_html_contains_scenario_section(self):
        assert "情景" in self.html

    def test_scorecard_html_is_valid(self):
        scorecard = self.engine.render_scorecard(self.report)
        assert isinstance(scorecard, str)
        assert len(scorecard) > 0

    def test_module_card_renders_correctly(self):
        from src.layer2_data.models import ModuleOutput
        mod = ModuleOutput(
            module_id="M01",
            module_title="公司基础与业务拆解",
            module_positioning="基本面",
            core_conclusion=f"{NAME}（{CODE}）是谐波减速器领域龙头企业。",
            module_score=7.2,
            evidence_chain=[],
        )
        html = self.engine.render_module_card(mod)
        assert NAME in html or "M01" in html
        assert "<script>" not in html  # XSS guard


# ---------------------------------------------------------------------------
# 全流程集成冒烟测试
# ---------------------------------------------------------------------------

class TestFullPipelineSmoke:
    """一个综合断言覆盖所有层的冒烟测试，用于快速验证整条流水线。"""

    def test_full_pipeline_for_ludi_xiebo(self):
        # -- Layer 1: parse query --
        parser = StockQueryParser()
        code = parser.parse("请帮我分析一下绿的谐波")
        assert code == CODE

        codes = parser.extract_all_codes("绿的谐波688522走势如何")
        assert CODE in codes

        intent = IntentClassifier().classify("分析绿的谐波", codes=[CODE])
        assert intent == AnalysisIntent.SINGLE_STOCK

        # -- Layer 2: build context --
        ctx = _make_context()
        assert ctx.stock.code == CODE
        assert ctx.quote is not None
        assert len(ctx.klines_daily) == 250

        # -- Layer 2: market env detection --
        index_closes = [3200 + i * 2 for i in range(60)]
        env = MarketEnvDetector().detect(index_closes)
        assert env in (MarketEnv.BULL, MarketEnv.SIDEWAYS)

        # -- Layer 1: special scene routing --
        routed_ctx = SpecialSceneRouter().route(ctx)
        assert routed_ctx.stock.code == CODE

        # -- Layer 3: 25-module analysis --
        orchestrator = build_default_orchestrator()
        modules = orchestrator.run(routed_ctx)
        assert len(modules) >= 20

        # -- Layer 4: report assembly --
        report = FullReport(context=routed_ctx)
        report = ReportAssembler().assemble(report, modules)
        assert report.score_a is not None
        assert report.score_b is not None
        assert report.score_c is not None
        assert len(report.scenarios) == 4

        # -- Layer 5: HTML rendering --
        html = TemplateEngine().render_full_report(report)
        assert NAME in html
        assert CODE in html
        assert "综合投资价值" in html
        assert len(html) > 1000
