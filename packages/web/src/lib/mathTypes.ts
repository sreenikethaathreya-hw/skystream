// Mirrors backend/app/schemas/demand_math.py.

export interface MarketPoint {
  year: number;
  hectares: number;
  qtyKs: number;
}

export interface Competitor {
  name: string;
  sharePct: number;
}

export interface YearMonthly {
  year: number;
  basis: string;
  qtyKs: number[];
}

export interface MegaContext {
  name?: string;
  marketValueEur: number;
  syngentaValueEur: number;
  syngentaSharePct: number;
  competitors: Competitor[];
  impliedHaBaseline: number;
  growerCeilingHa: number;
}

export interface SegmentContext {
  year: number;
  clockMonth: number;
  marketHectares: number;
  marketQtyKs: number;
  density: number;
  priceExseed: number;
  planQtyKs: number;
  planValueEur: number;
  planNetPrice: number;
  lastYearQtyKs: number;
  lastYearValueEur: number;
  marketHistory: MarketPoint[];
  planQtyHistory: MarketPoint[];
  netPriceHistory: number[];
  monthlyPlan: number[];
  monthlyActual: (number | null)[];
  monthlyActualValue: (number | null)[];
  lastYearMonthly: number[];
  monthlyHistory?: YearMonthly[];
  submitted: Record<string, number>;
  marketTrendNote?: string | null;
  mega: MegaContext;
}

export interface EntryInput {
  month: number;
  value: number;
  low: number;
  high: number;
  price?: number | null;
}

export interface CompetitorImpact {
  name: string;
  baselinePct: number;
  newPct: number;
  deltaPts: number;
}

export interface RevenueSplit {
  lastYear: number;
  estimate: number;
  change: number;
  volumeEffect: number;
  priceEffect: number;
  priceShareOfChange: number;
  avgPrice: number;
  lastYearPrice: number;
}

export interface Impact {
  actualsToDate: number;
  monthsRemaining: number;
  fyEstimate: number;
  fyLow: number;
  fyHigh: number;
  planFy: number;
  gapToPlan: number;
  ytgRemaining: number;
  requiredMonthlyRate: number;
  enteredMonthlyRate: number;
  historicalMonthlyRate: number;
  volumeShare: number;
  volumeShareLow: number;
  volumeShareHigh: number;
  planVolumeShare: number;
  lastYearVolumeShare: number;
  maxHistoricalShare: number;
  avgHistoricalShare: number;
  baselineShare: number;
  shareJumpPts: number;
  monthHistoryAvg: number;
  monthHistoryYears: number[];
  monthVsAvgPct: number;
  fyValue: number;
  valueShare: number;
  planValueShare: number;
  megaShareBaseline: number;
  megaShare: number;
  competitors: CompetitorImpact[];
  impliedHa: number;
  impliedHaLow: number;
  impliedHaHigh: number;
  marketHa: number;
  megaImpliedHa: number;
  revenue: RevenueSplit;
  monthExpected: number;
  monthLastYear: number;
  monthSigma: number;
  monthZ: number;
}

export type FlagSeverity = "warning" | "critical";

export interface Flag {
  code: string;
  severity: FlagSeverity;
  message: string;
}

export interface LeadRuleSpec {
  id: number;
  segmentIds?: number[] | null;
  months?: number[] | null;
  metric: string;
  comparator: "above" | "below";
  threshold: number;
  requiredDriver?: string | null;
  severity: FlagSeverity;
  description: string;
  author: string;
}

export interface Thresholds {
  shareHistoryMarginPts: number;
  shareJumpPts: number;
  monthSigmaMultiplier: number;
  minMonthSigmaPct: number;
  minMonthSigmaAbs: number;
  priceCarryingShare: number;
  rangeWidthPct: number;
  priceBandPct: number;
  marketTrendPct: number;
}

export const DEFAULT_THRESHOLDS: Thresholds = {
  shareHistoryMarginPts: 10,
  shareJumpPts: 10,
  monthSigmaMultiplier: 2,
  minMonthSigmaPct: 0.15,
  minMonthSigmaAbs: 50,
  priceCarryingShare: 0.7,
  rangeWidthPct: 0.3,
  priceBandPct: 0.1,
  marketTrendPct: 0.03,
};
