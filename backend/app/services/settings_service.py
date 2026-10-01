from datetime import date
from typing import Literal

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AppSetting, DemoClock
from app.schemas.common import CamelModel
from app.schemas.demand_math import Thresholds

SETTINGS_KEY = "app"


DisplayCurrency = Literal["USD", "EUR", "LOCAL"]
PriceSource = Literal["value_over_qty", "avg_net_price"]
MarketZeroMeans = Literal["no_market", "missing"]
FxRateYearRule = Literal["same_year", "current_budget"]
ClaimBaseline = Literal["plan", "rep_number"]
DemandSource = Literal["ibp", "manual"]


class AppSettings(CamelModel):
    current_year: int
    thresholds: Thresholds = Field(default_factory=Thresholds)
    jev_confidence_threshold: float = Field(ge=0, le=1)
    jev_score_confidence_threshold: float = Field(ge=0, le=1)
    grower_ha_cap: float = Field(gt=0)
    external_ai_allowed: bool
    chat_writes_allowed: bool = False
    # Money is stored as net USD at the Syngenta budget rate; other currencies are display-only.
    reporting_currency: Literal["USD"] = "USD"
    default_display_currency: DisplayCurrency = "USD"
    # Assumptions awaiting SME confirmation (see README "Open data assumptions").
    price_source: PriceSource = "value_over_qty"
    market_zero_means: MarketZeroMeans = "no_market"
    actuals_hold_days: int = Field(default=0, ge=0, le=120)
    fx_rate_year_rule: FxRateYearRule = "same_year"
    claim_baseline: ClaimBaseline = "plan"
    claim_neutral_tolerance_pct: float = Field(default=5.0, ge=0, le=50)
    demand_source: DemandSource = "manual"


class AppSettingsPatch(CamelModel):
    current_year: int | None = Field(default=None, ge=2000, le=2100)
    thresholds: Thresholds | None = None
    jev_confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    jev_score_confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    grower_ha_cap: float | None = Field(default=None, gt=0)
    external_ai_allowed: bool | None = None
    chat_writes_allowed: bool | None = None
    default_display_currency: DisplayCurrency | None = None
    price_source: PriceSource | None = None
    market_zero_means: MarketZeroMeans | None = None
    actuals_hold_days: int | None = Field(default=None, ge=0, le=120)
    fx_rate_year_rule: FxRateYearRule | None = None
    claim_baseline: ClaimBaseline | None = None
    claim_neutral_tolerance_pct: float | None = Field(default=None, ge=0, le=50)
    demand_source: DemandSource | None = None


async def _default_year(db: AsyncSession) -> int:
    settings = get_settings()
    if settings.is_demo:
        clock = await db.get(DemoClock, 1)
        if clock is not None:
            return clock.year
    return settings.current_year or date.today().year


async def get_app_settings(db: AsyncSession) -> AppSettings:
    env = get_settings()
    base = AppSettings(
        current_year=await _default_year(db),
        jev_confidence_threshold=env.jev_confidence_threshold,
        jev_score_confidence_threshold=env.jev_score_confidence_threshold,
        grower_ha_cap=env.grower_ha_cap,
        # Demo data is synthetic, so the external-AI gate only applies to real figures.
        external_ai_allowed=env.external_ai_allowed or env.is_demo,
        chat_writes_allowed=env.chat_writes_allowed or env.is_demo,
        default_display_currency=env.default_display_currency,
        # Real reps commit demand in IBP; the demo keeps typed entry so the demo script still works.
        demand_source="manual" if env.is_demo else "ibp",
    )
    row = await db.get(AppSetting, SETTINGS_KEY)
    if row is None:
        return base
    overrides = AppSettingsPatch.model_validate(row.value).model_dump(exclude_none=True)
    return AppSettings.model_validate({**base.model_dump(), **overrides})


async def update_app_settings(db: AsyncSession, patch: AppSettingsPatch, user_id: str) -> AppSettings:
    row = await db.get(AppSetting, SETTINGS_KEY)
    stored = AppSettingsPatch.model_validate(row.value).model_dump(exclude_none=True) if row else {}
    merged = AppSettingsPatch.model_validate({**stored, **patch.model_dump(exclude_none=True)})
    value = merged.model_dump(mode="json", by_alias=True, exclude_none=True)
    if row is None:
        db.add(AppSetting(key=SETTINGS_KEY, value=value, updated_by=user_id))
    else:
        row.value, row.updated_by = value, user_id
    await db.commit()
    return await get_app_settings(db)
