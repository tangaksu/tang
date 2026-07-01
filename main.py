"""OpenClaw A股机构级全维度股票投资分析报告生成技能 V5.0.0

Entry point (main.py) – Layer 1 Orchestration entry.

Usage
-----
    python main.py "分析贵州茅台600519"
    python main.py "600519"
    python main.py "比亚迪现在能买吗"
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("openclaw")


def run(query: str, output_html: str | None = None) -> str:
    """Full pipeline: parse → classify → fetch data → analyze → render report.

    Parameters
    ----------
    query:
        Free-form user question, e.g. "分析贵州茅台600519".
    output_html:
        Optional file path to write the HTML report to.

    Returns
    -------
    str
        The rendered HTML report.
    """
    from src.layer1_orchestration import (
        IntentClassifier,
        MarketEnvDetector,
        SpecialSceneRouter,
        StockQueryParser,
        build_default_orchestrator,
    )
    from src.layer2_data import (
        AKShareAdapter,
        AnalysisContext,
        FallbackChain,
        StockBasic,
        get_cache,
    )
    from src.layer4_report import ReportAssembler
    from src.layer5_output import TemplateEngine
    from src.layer2_data.models import FullReport

    # -- Step 1: Parse query --
    parser = StockQueryParser()
    code = parser.parse(query)
    if code is None:
        logger.error("无法从问题中识别股票代码或名称：%s", query)
        return "<p>无法识别股票，请提供6位A股代码或公司名称。</p>"

    codes = parser.extract_all_codes(query)
    intent = IntentClassifier().classify(query, codes)
    logger.info("代码识别：%s，意图：%s", code, intent.value)

    # -- Step 2: Build context --
    ak = AKShareAdapter(get_cache())
    fallback = FallbackChain(get_cache())

    basic = ak.get_stock_basic(code) or StockBasic(code=code, name=code)
    quote_primary = ak.get_quote(code)
    quote = fallback.get_quote(code, quote_primary)

    klines_d = ak.get_klines(code, period="daily", limit=250)
    klines_w = ak.get_klines(code, period="weekly", limit=52)
    klines_m = ak.get_klines(code, period="monthly", limit=36)

    fin_primary = ak.get_financial_summary(code)
    fin = fallback.get_financial(code, fin_primary)

    capital_flow = ak.get_capital_flow(code)
    forecast = ak.get_analyst_forecast(code)
    north = ak.get_north_flow(code)

    # -- Step 3: Detect market environment --
    index_klines = ak.get_klines("000300", period="daily", limit=60)
    index_closes = [b.close for b in index_klines]
    market_env = MarketEnvDetector().detect(index_closes)

    ctx = AnalysisContext(
        stock=basic,
        intent=intent,
        query_text=query,
        market_env=market_env,
        analysis_timestamp=datetime.now(),
        quote=quote,
        klines_daily=klines_d,
        klines_weekly=klines_w,
        klines_monthly=klines_m,
        financial=fin,
        capital_flow=capital_flow,
        analyst_forecast=forecast,
        extra=dict(north),
    )

    # -- Step 4: Apply special scene routing --
    ctx = SpecialSceneRouter().route(ctx)

    # -- Step 5: Run 25-module analysis --
    orchestrator = build_default_orchestrator()
    modules = orchestrator.run(ctx)
    logger.info("模块分析完成，共 %d 个模块", len(modules))

    # -- Step 6: Assemble report --
    report = FullReport(context=ctx)
    assembler = ReportAssembler()
    report = assembler.assemble(report, modules)

    # -- Step 7: Apply ST score cap --
    if ctx.stock.is_st and report.score_b:
        cap = ctx.extra.get("score_b_cap", 80.0)
        if report.score_b.total_score > cap:
            report.score_b.total_score = cap
            logger.info("[ST场景] 现价买入性价比评分已上调为上限 %.0f 分", cap)

    # -- Step 8: Render HTML --
    engine = TemplateEngine()
    html = engine.render_full_report(report)
    report.html_report = html

    if output_html:
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("HTML报告已写入：%s", output_html)

    return html


def main() -> None:
    ap = argparse.ArgumentParser(
        description="OpenClaw A股机构级全维度投资分析报告生成技能 V5.0.0"
    )
    ap.add_argument("query", help="用户问题，如 '分析贵州茅台600519' 或 '600519'")
    ap.add_argument(
        "--output", "-o", default=None,
        help="HTML报告输出路径，如 report.html"
    )
    ap.add_argument("--debug", action="store_true", help="启用调试日志")
    args = ap.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    html = run(args.query, output_html=args.output)

    if not args.output:
        # Print to stdout for piping / integration
        print(html)


if __name__ == "__main__":
    main()
