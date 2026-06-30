"""Layer 2 – Data layer: Pydantic models shared across all layers."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MarketEnv(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"


class AnalysisIntent(str, Enum):
    SINGLE_STOCK = "single_stock"
    INDEX = "index"
    POSITION_REVIEW = "position_review"
    MULTI_STOCK_COMPARE = "multi_stock_compare"
    STOCK_SELECTION = "stock_selection"
    NEW_STOCK = "new_stock"
    ST_STOCK = "st_stock"


class EvidenceStrength(str, Enum):
    STRONG = "strong"    # 多源数据直接验证
    MEDIUM = "medium"    # 部分数据支持 + 合理逻辑推演
    WEAK = "weak"        # 缺少直接证据，仅作假设


class StarRating(int, Enum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class TradeStatus(str, Enum):
    ATTACK = "可进攻"
    LOW_BUY = "可低吸"
    T_TRADE = "可做T"
    REDUCE_ONLY = "只减不买"
    AVOID = "暂不参与"


class ValuationZone(str, Enum):
    DEEP_UNDERVALUE = "深度低估"
    MILD_UNDERVALUE = "合理低估"
    FAIR = "估值合理"
    MILD_OVERVALUE = "轻度高估"
    BUBBLE = "明显泡沫"


class MainDriver(str, Enum):
    EARNINGS = "业绩驱动"
    VALUATION_REPAIR = "估值修复"
    FUND_CLUSTER = "资金抱团"
    THEME = "题材催化"
    INDUSTRY_BETA = "行业β"
    STYLE_SWITCH = "风格切换"


# ---------------------------------------------------------------------------
# Stock / Quote models
# ---------------------------------------------------------------------------

class StockBasic(BaseModel):
    code: str = Field(..., description="6位A股代码，如 600519")
    name: str = Field(..., description="股票简称")
    market: str = Field("", description="上市板块，如 上交所主板")
    industry: str = Field("", description="所属行业")
    sub_industry: str = Field("", description="细分赛道")
    is_st: bool = False
    is_new_stock: bool = False


class QuoteData(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float          # 涨跌幅 %
    volume: float              # 成交量（手）
    amount: float              # 成交额（万元）
    turnover_rate: float       # 换手率 %
    market_cap: float          # 总市值（亿元）
    circulating_cap: float     # 流通市值（亿元）
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    date: Optional[date] = None


class KLineBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    change_pct: float


# ---------------------------------------------------------------------------
# Financial data
# ---------------------------------------------------------------------------

class FinancialSummary(BaseModel):
    """Simplified P&L + cashflow + balance indicators (latest period)."""
    period: str = ""                      # e.g. "2024Q3"
    revenue: Optional[float] = None          # 营收（亿元）
    revenue_yoy: Optional[float] = None      # 营收同比 %
    net_profit: Optional[float] = None       # 归母净利润（亿元）
    net_profit_yoy: Optional[float] = None
    deducted_profit: Optional[float] = None  # 扣非净利润
    deducted_profit_yoy: Optional[float] = None
    gross_margin: Optional[float] = None     # 毛利率 %
    net_margin: Optional[float] = None       # 净利率 %
    roe: Optional[float] = None              # ROE %
    operating_cashflow: Optional[float] = None   # 经营现金流（亿元）
    debt_ratio: Optional[float] = None       # 资产负债率 %
    goodwill: Optional[float] = None         # 商誉（亿元）
    dividend_yield: Optional[float] = None   # 股息率 %


# ---------------------------------------------------------------------------
# Capital flow
# ---------------------------------------------------------------------------

class CapitalFlowData(BaseModel):
    code: str
    main_net_inflow_5d: Optional[float] = None   # 主力5日净流入（亿元）
    main_net_inflow_10d: Optional[float] = None
    main_net_inflow_20d: Optional[float] = None
    north_net_5d: Optional[float] = None         # 北向5日净买入（亿元）
    north_net_10d: Optional[float] = None
    north_net_20d: Optional[float] = None


# ---------------------------------------------------------------------------
# Analyst / forecast
# ---------------------------------------------------------------------------

class AnalystForecast(BaseModel):
    code: str
    rating_buy: int = 0
    rating_overweight: int = 0
    rating_neutral: int = 0
    rating_underweight: int = 0
    rating_sell: int = 0
    target_price_avg: Optional[float] = None
    target_price_high: Optional[float] = None
    target_price_low: Optional[float] = None
    eps_forecast_1y: Optional[float] = None
    eps_forecast_2y: Optional[float] = None


# ---------------------------------------------------------------------------
# Scoring output
# ---------------------------------------------------------------------------

class ScoringSubItem(BaseModel):
    name: str
    score: float
    max_score: float
    note: str = ""


class ScoringDimension(BaseModel):
    name: str
    score: float
    max_score: float
    sub_items: list[ScoringSubItem] = Field(default_factory=list)


class ScoreResult(BaseModel):
    """Output of one of the three scoring engines."""
    engine: str                            # A / B / C
    total_score: float
    star_rating: StarRating
    one_line_conclusion: str = ""
    plus_items: list[str] = Field(default_factory=list)   # 加分项（≥3条）
    minus_items: list[str] = Field(default_factory=list)  # 扣分项（≥3条）
    confidence: str = ""                   # 评分置信度说明
    dimensions: list[ScoringDimension] = Field(default_factory=list)
    action_suggestion: str = ""


# ---------------------------------------------------------------------------
# Module analysis output
# ---------------------------------------------------------------------------

class FactorTree(BaseModel):
    """五层因子树."""
    facts: list[str] = Field(default_factory=list)        # 第1层：事实
    explanations: list[str] = Field(default_factory=list) # 第2层：解释
    judgements: list[str] = Field(default_factory=list)   # 第3层：判断
    scores_summary: str = ""                               # 第4层：评分摘要
    actions: list[str] = Field(default_factory=list)      # 第5层：动作


class EvidenceItem(BaseModel):
    conclusion: str
    evidence_type: str    # 财务/行业/估值/技术/资金/事件/市场风格
    strength: EvidenceStrength
    source: str = ""


class ModuleOutput(BaseModel):
    module_id: str                         # e.g. "M01"
    module_title: str
    module_positioning: str = ""
    core_conclusion: str = ""
    key_tags: list[str] = Field(default_factory=list)
    risk_deductions: list[str] = Field(default_factory=list)
    module_score: float = 0.0
    module_max_score: float = 10.0
    star_rating: StarRating = StarRating.THREE
    evidence_chain: list[EvidenceItem] = Field(default_factory=list)
    factor_tree: FactorTree = Field(default_factory=FactorTree)
    short_term_suggestion: str = ""
    mid_term_suggestion: str = ""
    long_term_suggestion: str = ""
    raw_data: dict[str, Any] = Field(default_factory=dict)
    data_missing_fields: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

class Scenario(BaseModel):
    name: str                              # 乐观/中性/悲观/风险触发
    trigger_conditions: list[str] = Field(default_factory=list)
    price_target_range: str = ""
    probability: str = ""
    time_horizon: str = ""
    strategy: str = ""


# ---------------------------------------------------------------------------
# Trade action plan
# ---------------------------------------------------------------------------

class TradeAction(BaseModel):
    one_line_verdict: str = ""
    entry_zone: str = ""
    entry_ratio: str = ""
    add_position_condition: str = ""
    hold_bottom: bool = True
    do_t_trade: bool = False
    reduce_to_lock_profit: bool = False
    hard_stop_loss: str = ""
    logic_stop_condition: str = ""
    event_stop_condition: str = ""
    target_1: str = ""
    target_2: str = ""
    event_tp_strategy: str = ""
    forbid_chase_conditions: list[str] = Field(default_factory=list)
    forbid_bottom_fish_conditions: list[str] = Field(default_factory=list)
    forbid_leverage_conditions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Investor profile
# ---------------------------------------------------------------------------

class InvestorProfile(BaseModel):
    investor_type: str
    suitable: str                          # 适合/一般/不适合
    position_limit: str
    recommended_period: str
    max_drawdown_tolerance: str


# ---------------------------------------------------------------------------
# Full analysis context (passed between layers)
# ---------------------------------------------------------------------------

class AnalysisContext(BaseModel):
    stock: StockBasic
    intent: AnalysisIntent = AnalysisIntent.SINGLE_STOCK
    query_text: str = ""
    market_env: MarketEnv = MarketEnv.SIDEWAYS
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    # populated during execution
    quote: Optional[QuoteData] = None
    klines_daily: list[KLineBar] = Field(default_factory=list)
    klines_weekly: list[KLineBar] = Field(default_factory=list)
    klines_monthly: list[KLineBar] = Field(default_factory=list)
    financial: Optional[FinancialSummary] = None
    capital_flow: Optional[CapitalFlowData] = None
    analyst_forecast: Optional[AnalystForecast] = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Final report model
# ---------------------------------------------------------------------------

class FullReport(BaseModel):
    context: AnalysisContext
    module_outputs: dict[str, ModuleOutput] = Field(default_factory=dict)
    score_a: Optional[ScoreResult] = None    # 综合投资价值
    score_b: Optional[ScoreResult] = None    # 现价买入性价比
    score_c: Optional[ScoreResult] = None    # 交易执行确定性
    joint_scenario: str = ""              # 联合场景描述（8大场景之一）
    position_advice: str = ""
    valuation_zone: ValuationZone = ValuationZone.FAIR
    main_driver: MainDriver = MainDriver.EARNINGS
    key_failure_condition: str = ""
    trade_status: TradeStatus = TradeStatus.AVOID
    scenarios: list[Scenario] = Field(default_factory=list)
    trade_action: TradeAction = Field(default_factory=TradeAction)
    investor_profiles: list[InvestorProfile] = Field(default_factory=list)
    invalidation_checklist: list[str] = Field(default_factory=list)
    tracking_checklist: list[str] = Field(default_factory=list)
    html_report: str = ""
