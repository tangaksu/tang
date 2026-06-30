"""Layer 5 – Template engine: render FullReport → HTML."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..layer2_data.models import FullReport, ModuleOutput, StarRating

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_STAR_SYMBOLS = {
    StarRating.ONE: "★☆☆☆☆",
    StarRating.TWO: "★★☆☆☆",
    StarRating.THREE: "★★★☆☆",
    StarRating.FOUR: "★★★★☆",
    StarRating.FIVE: "★★★★★",
}

_SCORE_COLOR_MAP = [
    (90, "c-deep-green"),
    (80, "c-light-green"),
    (70, "c-yellow"),
    (60, "c-orange"),
    (0, "c-red"),
]

_TRADE_STATUS_COLOR = {
    "可进攻": "green",
    "可低吸": "blue",
    "可做T": "yellow",
    "只减不买": "red",
    "暂不参与": "red",
}


def _score_color(score: float) -> str:
    for threshold, cls in _SCORE_COLOR_MAP:
        if score >= threshold:
            return cls
    return "c-red"


def _stars(rating: StarRating) -> str:
    return _STAR_SYMBOLS.get(rating, "★★★☆☆")


def _pct_fmt(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


class TemplateEngine:
    """Jinja2-based HTML renderer for the full investment report."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,  # enable for all templates (*.j2 files contain HTML)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_scorecard(self, report: FullReport) -> str:
        """Render only the first-screen three-score HTML dashboard."""
        tmpl = self._env.get_template("scorecard.html.j2")
        return tmpl.render(**self._scorecard_context(report))

    def render_module_card(self, module: ModuleOutput) -> str:
        """Render a single module card."""
        tmpl = self._env.get_template("module_card.html.j2")
        score_color = _score_color(
            module.module_score / max(module.module_max_score, 1e-9) * 100
        )
        return tmpl.render(
            module_id=module.module_id,
            module_title=module.module_title,
            core_conclusion=module.core_conclusion,
            module_score=f"{module.module_score:.1f}",
            module_max_score=f"{module.module_max_score:.0f}",
            score_color=score_color.replace("c-", "#"),
            star_line=_stars(module.star_rating),
            key_tags=module.key_tags,
            risk_deductions=module.risk_deductions,
            evidence_chain=[
                {
                    "conclusion": e.conclusion,
                    "evidence_type": e.evidence_type,
                    "strength": e.strength.value,
                    "source": e.source,
                }
                for e in module.evidence_chain
            ],
            short_term_suggestion=module.short_term_suggestion,
            mid_term_suggestion=module.mid_term_suggestion,
            long_term_suggestion=module.long_term_suggestion,
            data_missing_fields=module.data_missing_fields,
        )

    def render_full_report(self, report: FullReport) -> str:
        """Render the complete HTML report."""
        tmpl = self._env.get_template("full_report.html.j2")
        modules = report.module_outputs

        def _card(mid: str) -> str:
            m = modules.get(mid)
            if m is None:
                return f'<div class="module-card"><div class="mc-body" style="opacity:0.4">{mid} 数据未获取</div></div>'
            return self.render_module_card(m)

        sc = self._scorecard_context(report)
        ctx: dict = {
            **sc,
            "scorecard_html": self.render_scorecard(report),
            **{f"module_{mid.lower()}": _card(mid) for mid in [
                "M01", "M02", "M03", "M04", "M05",
                "M06", "M07", "M08", "M09", "M10", "M11",
                "M12", "M13", "M19", "M20", "M21", "M22",
                "M14", "M15", "M23", "M24", "M25",
            ]},
            "scenarios": [
                {
                    "name": s.name,
                    "trigger_conditions": s.trigger_conditions,
                    "price_target_range": s.price_target_range,
                    "probability": s.probability,
                    "time_horizon": s.time_horizon,
                    "strategy": s.strategy,
                }
                for s in report.scenarios
            ],
            "trade_action": report.trade_action,
            "investor_profiles": [
                {
                    "investor_type": p.investor_type,
                    "suitable": p.suitable,
                    "position_limit": p.position_limit,
                    "recommended_period": p.recommended_period,
                    "max_drawdown_tolerance": p.max_drawdown_tolerance,
                }
                for p in report.investor_profiles
            ],
            "invalidation_checklist": report.invalidation_checklist,
            "tracking_checklist": report.tracking_checklist,
        }
        return tmpl.render(**ctx)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scorecard_context(self, report: FullReport) -> dict:
        ctx = report.context
        quote = ctx.quote

        sa = report.score_a
        sb = report.score_b
        sc = report.score_c

        # Extract top risk items from modules
        key_risks: list[str] = []
        for mid in ["M02", "M03", "M05"]:
            m = report.module_outputs.get(mid)
            if m:
                key_risks.extend(m.risk_deductions[:1])
        key_risks = key_risks[:3]

        return {
            "stock_name": ctx.stock.name or ctx.stock.code,
            "stock_code": ctx.stock.code,
            "current_price": f"{quote.price:.2f}" if quote else "—",
            "change_pct": _pct_fmt(quote.change_pct if quote else None),
            "analysis_time": ctx.analysis_timestamp.strftime("%Y-%m-%d %H:%M"),
            "industry": ctx.stock.industry or "—",
            "sub_industry": ctx.stock.sub_industry or "—",
            "market_style_tag": ctx.market_env.value,
            "trade_status": report.trade_status.value,
            "trade_status_color": _TRADE_STATUS_COLOR.get(report.trade_status.value, "yellow"),
            "joint_scenario": report.joint_scenario,
            "position_advice": report.position_advice,
            "valuation_zone": report.valuation_zone.value,
            "main_driver": report.main_driver.value,
            "key_failure_condition": report.key_failure_condition,
            "key_risks": key_risks,
            # Score A
            "score_a_total": f"{sa.total_score:.0f}" if sa else "—",
            "score_a_color": _score_color(sa.total_score if sa else 50),
            "score_a_stars": _stars(sa.star_rating) if sa else "—",
            "score_a_conclusion": sa.one_line_conclusion if sa else "—",
            "score_a_plus": sa.plus_items if sa else [],
            "score_a_minus": sa.minus_items if sa else [],
            "score_a_action": sa.action_suggestion if sa else "—",
            # Score B
            "score_b_total": f"{sb.total_score:.0f}" if sb else "—",
            "score_b_color": _score_color(sb.total_score if sb else 50),
            "score_b_stars": _stars(sb.star_rating) if sb else "—",
            "score_b_conclusion": sb.one_line_conclusion if sb else "—",
            "score_b_plus": sb.plus_items if sb else [],
            "score_b_minus": sb.minus_items if sb else [],
            "score_b_action": sb.action_suggestion if sb else "—",
            # Score C
            "score_c_total": f"{sc.total_score:.0f}" if sc else "—",
            "score_c_color": _score_color(sc.total_score if sc else 50),
            "score_c_stars": _stars(sc.star_rating) if sc else "—",
            "score_c_conclusion": sc.one_line_conclusion if sc else "—",
            "score_c_plus": sc.plus_items if sc else [],
            "score_c_minus": sc.minus_items if sc else [],
            "score_c_action": sc.action_suggestion if sc else "—",
        }
