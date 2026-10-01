import { fmtNum, monthName } from "@/lib/format";
import { USD, type Money } from "@/lib/money";

export interface DraftNumbers {
  value: number;
  lowPct: number;
  highPct: number;
  /** Net price in USD per KS; the input shows and accepts the display currency. */
  price: number | null;
}

export function EntryPanel({
  month,
  planMonth,
  planNetPrice,
  draft,
  onChange,
  money = USD,
  committedInIbp,
}: {
  month: number;
  planMonth: number;
  planNetPrice: number;
  draft: DraftNumbers;
  onChange: (next: DraftNumbers) => void;
  money?: Money;
  /** IBP mode: the number box becomes a what-if; the committed number lives in IBP. */
  committedInIbp?: number | null;
}) {
  const shownPrice = draft.price == null ? "" : Number(money.fromUsd(draft.price).toFixed(2));
  const low = draft.value * (1 - draft.lowPct);
  const high = draft.value * (1 + draft.highPct);
  return (
    <div className="grid gap-4 md:grid-cols-[1.2fr_1fr_0.8fr]">
      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-muted">
          {committedInIbp === undefined
            ? `${monthName(month)} demand (thousand seeds) · plan ${fmtNum(planMonth)}`
            : `What if (not submitted) · ${committedInIbp === null ? "no IBP number yet" : `IBP ${fmtNum(committedInIbp)}`} · plan ${fmtNum(planMonth)}`}
        </span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          data-testid="demand-input"
          value={Number.isFinite(draft.value) ? draft.value : ""}
          onChange={(e) => onChange({ ...draft, value: Math.max(0, Number(e.target.value)) })}
          className="tabular h-14 rounded-xl border border-line bg-surface px-4 text-3xl font-semibold outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        />
      </label>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium text-muted">
          How sure? Range {fmtNum(low)} to {fmtNum(high)}
        </span>
        <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface px-3 py-2">
          <RangeRow
            label="Low"
            value={draft.lowPct}
            onChange={(v) => onChange({ ...draft, lowPct: v })}
            testId="range-low"
          />
          <RangeRow
            label="High"
            value={draft.highPct}
            onChange={(v) => onChange({ ...draft, highPct: v })}
            testId="range-high"
          />
        </div>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-muted">Net price {money.code}/KS (optional)</span>
        <input
          type="number"
          min={0}
          placeholder={`plan ${fmtNum(money.fromUsd(planNetPrice))}`}
          data-testid="price-input"
          value={shownPrice}
          onChange={(e) =>
            onChange({ ...draft, price: e.target.value === "" ? null : money.toUsd(Number(e.target.value)) })
          }
          className="tabular h-14 rounded-xl border border-line bg-surface px-4 text-lg outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        />
      </label>
    </div>
  );
}

function RangeRow({
  label,
  value,
  onChange,
  testId,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  testId: string;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      <span className="w-8">{label}</span>
      <input
        type="range"
        min={0}
        max={0.5}
        step={0.01}
        value={value}
        data-testid={testId}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 accent-brand-600"
      />
      <span className="tabular w-10 text-right">{label === "Low" ? "-" : "+"}{Math.round(value * 100)}%</span>
    </label>
  );
}
