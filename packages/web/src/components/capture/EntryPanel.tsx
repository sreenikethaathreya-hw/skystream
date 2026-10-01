import { useState } from "react";
import { fmtNum, monthName, parseWhole } from "@/lib/format";

export interface DraftNumbers {
  value: number;
  lowPct: number;
  highPct: number;
  price: number | null;
}

const parsePrice = (text: string) => {
  const n = Number(text.replace(/,/g, ""));
  return text.trim() === "" || !Number.isFinite(n) ? null : Math.max(0, n);
};

const INPUT = "tabular h-11 rounded-md border border-line bg-surface px-3";

export function EntryPanel({
  month,
  planMonth,
  planNetPrice,
  draft,
  onChange,
}: {
  month: number;
  planMonth: number;
  planNetPrice: number;
  draft: DraftNumbers;
  onChange: (next: DraftNumbers) => void;
}) {
  const [demandText, setDemandText] = useState("");
  const [priceText, setPriceText] = useState("");
  // Show what the rep typed while it still matches the draft; otherwise the draft changed elsewhere (new cell).
  const demandShown = parseWhole(demandText) === draft.value ? demandText : fmtNum(draft.value);
  const priceShown = parsePrice(priceText) === draft.price ? priceText : (draft.price?.toString() ?? "");
  const low = draft.value * (1 - draft.lowPct);
  const high = draft.value * (1 + draft.highPct);

  return (
    <div className="grid gap-x-8 gap-y-4 md:grid-cols-[1.4fr_1fr_0.8fr] md:items-end">
      <label className="flex flex-col gap-1">
        <span className="eyebrow">
          {monthName(month)} demand · thousand seeds · plan {fmtNum(planMonth)}
        </span>
        <input
          type="text"
          inputMode="numeric"
          name="demand"
          autoComplete="off"
          spellCheck={false}
          placeholder="0"
          data-testid="demand-input"
          value={demandShown}
          onChange={(e) => {
            setDemandText(e.target.value);
            onChange({ ...draft, value: parseWhole(e.target.value) });
          }}
          onBlur={() => setDemandText(draft.value ? fmtNum(draft.value) : "")}
          className="font-num tabular w-full border-0 border-b-2 border-ink bg-transparent px-0 pb-1 text-6xl font-semibold leading-tight tracking-tight placeholder:text-line focus-visible:border-brand-600 focus-visible:outline-none"
        />
      </label>

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
        <span className="eyebrow">Net price EUR/KS · optional</span>
        <input
          type="text"
          inputMode="decimal"
          name="net-price"
          autoComplete="off"
          spellCheck={false}
          placeholder={`plan ${fmtNum(planNetPrice)}…`}
          data-testid="price-input"
          value={priceShown}
          onChange={(e) => {
            setPriceText(e.target.value);
            onChange({ ...draft, price: parsePrice(e.target.value) });
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
