import { useState } from "react";
import { ArrowUp } from "lucide-react";
import { DemandField } from "@/components/capture/DemandField";
import { fmtNum, monthName } from "@/lib/format";
import { USD, type Money } from "@/lib/money";
import { cn } from "@/lib/utils";

export interface DraftNumbers {
  value: number;
  lowPct: number;
  highPct: number;
  /** Net price in USD per KS; the input shows and accepts the display currency. */
  price: number | null;
}

const parsePrice = (text: string) => {
  const n = Number(text.replace(/,/g, ""));
  return text.trim() === "" || !Number.isFinite(n) ? null : Math.max(0, n);
};

const INPUT = "tabular h-11 w-full min-w-0 rounded-md border border-line bg-surface px-3";

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
  const [priceText, setPriceText] = useState("");
  const displayPrice = draft.price == null ? null : Number(money.fromUsd(draft.price).toFixed(2));
  const priceShown = parsePrice(priceText) === displayPrice ? priceText : (displayPrice?.toString() ?? "");
  const low = draft.value * (1 - draft.lowPct);
  const high = draft.value * (1 + draft.highPct);
  const demandLabel =
    committedInIbp === undefined
      ? `${monthName(month)} demand · thousand seeds · plan ${fmtNum(planMonth)}`
      : `What if (not submitted) · ${committedInIbp === null ? "no IBP number yet" : `IBP ${fmtNum(committedInIbp)}`} · plan ${fmtNum(planMonth)}`;

  return (
    <div className="grid gap-x-8 gap-y-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.8fr)] md:items-start">
      <div className="flex flex-col gap-1">
        <label className="flex flex-col gap-1">
          <span className="eyebrow">{demandLabel}</span>
          <DemandField value={draft.value} onChange={(value) => onChange({ ...draft, value })} testId="demand-input" />
        </label>
        <span
          className={cn(
            "flex items-center gap-1.5 text-sm font-semibold",
            committedInIbp === undefined ? "text-brand-700" : "text-warn-700",
          )}
        >
          <ArrowUp aria-hidden className="size-4 shrink-0" />
          {committedInIbp === undefined
            ? "Type your number in thousand seeds (KS)"
            : "Try a number to see its effect; it is not submitted"}
        </span>
      </div>

      <div className="flex flex-col gap-1" role="group" aria-label="Range">
        <span className="eyebrow tabular">
          How sure? {fmtNum(low)}–{fmtNum(high)}
        </span>
        <div className="flex flex-col gap-2 rounded-md border border-line bg-surface px-3 py-2">
          <RangeRow label="Low" value={draft.lowPct} onChange={(v) => onChange({ ...draft, lowPct: v })} testId="range-low" />
          <RangeRow label="High" value={draft.highPct} onChange={(v) => onChange({ ...draft, highPct: v })} testId="range-high" />
        </div>
      </div>

      <label className="flex flex-col gap-1">
        <span className="eyebrow">Net price {money.code}/KS · optional</span>
        <input
          type="text"
          inputMode="decimal"
          name="net-price"
          autoComplete="off"
          spellCheck={false}
          placeholder={`plan ${fmtNum(money.fromUsd(planNetPrice))}…`}
          data-testid="price-input"
          value={priceShown}
          onChange={(e) => {
            setPriceText(e.target.value);
            const parsed = parsePrice(e.target.value);
            onChange({ ...draft, price: parsed == null ? null : money.toUsd(parsed) });
          }}
          className={`${INPUT} text-lg`}
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
      <span className="tabular w-10 text-right">
        {label === "Low" ? "−" : "+"}
        {Math.round(value * 100)}%
      </span>
    </label>
  );
}
