"""Inputs and outputs of the live demand math. Mirrored in packages/web/src/lib/types.ts."""

from app.schemas.common import CamelModel


class MarketPoint(CamelModel):
    year: int
    hectares: float
    qty_ks: float
    # Labels only (the math ignores it): "actual" or "plan" for Syngenta history points.
    basis: str | None = None


class Competitor(CamelModel):
    name: str
    share_pct: float


class YearMonthly(CamelModel):
    year: int
    basis: str
    qty_ks: list[float]


class MegaContext(CamelModel):
    name: str = ""
    market_value_usd: float
    syngenta_value_usd: float
    syngenta_share_pct: float
    competitors: list[Competitor]
    implied_ha_baseline: float
    grower_ceiling_ha: float


class SegmentContext(CamelModel):
    year: int
    clock_month: int
    market_hectares: float
    market_qty_ks: float
    density: float
    price_exseed: float
    plan_qty_ks: float
    plan_value_usd: float
    plan_net_price: float
    last_year_qty_ks: float
    last_year_value_usd: float
    market_history: list[MarketPoint]
    plan_qty_history: list[MarketPoint]
    net_price_history: list[float]
    monthly_plan: list[float]
    monthly_actual: list[float | None]
    monthly_actual_value: list[float | None]
    last_year_monthly: list[float]
    monthly_history: list[YearMonthly] = []
    submitted: dict[str, float]
    market_trend_note: str | None = None
    mega: MegaContext


class EntryInput(CamelModel):
    month: int
    value: float
    low: float
    high: float
    price: float | None = None


class CompetitorImpact(CamelModel):
    name: str
    baseline_pct: float
    new_pct: float
    delta_pts: float


class RevenueSplit(CamelModel):
    last_year: float
    estimate: float
    change: float
    volume_effect: float
    price_effect: float
    price_share_of_change: float
    avg_price: float
    last_year_price: float


class Impact(CamelModel):
    actuals_to_date: float
    months_remaining: int
    fy_estimate: float
    fy_low: float
    fy_high: float
    plan_fy: float
    gap_to_plan: float
    ytg_remaining: float
    required_monthly_rate: float
    entered_monthly_rate: float
    historical_monthly_rate: float
    volume_share: float
    volume_share_low: float
    volume_share_high: float
    plan_volume_share: float
    last_year_volume_share: float
    max_historical_share: float
    avg_historical_share: float
    baseline_share: float
    share_jump_pts: float
    month_history_avg: float
    month_history_years: list[int]
    month_vs_avg_pct: float
    fy_value: float
    value_share: float
    plan_value_share: float
    mega_share_baseline: float
    mega_share: float
    competitors: list[CompetitorImpact]
    implied_ha: float
    implied_ha_low: float
    implied_ha_high: float
    market_ha: float
    mega_implied_ha: float
    revenue: RevenueSplit
    month_expected: float
    month_last_year: float
    month_sigma: float
    month_z: float


class Flag(CamelModel):
    code: str
    severity: str
    message: str


class LeadRuleSpec(CamelModel):
    id: int
    segment_ids: list[int] | None = None
    months: list[int] | None = None
    metric: str
    comparator: str
    threshold: float
    required_driver: str | None = None
    severity: str
    description: str
    author: str


class Thresholds(CamelModel):
    share_history_margin_pts: float = 10.0
    share_jump_pts: float = 10.0
    month_sigma_multiplier: float = 2.0
    min_month_sigma_pct: float = 0.15
    min_month_sigma_abs: float = 50.0
    price_carrying_share: float = 0.7
    range_width_pct: float = 0.3
    price_band_pct: float = 0.1
    market_trend_pct: float = 0.03
