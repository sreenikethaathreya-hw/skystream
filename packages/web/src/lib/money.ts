import type { DisplayCurrency, Fx } from "./types";

/** Money is stored and computed in USD; this only converts for display and for prices the rep types. */
export interface Money {
  code: string;
  perUsd: number;
  /** True when the chosen currency has no budget rate, so figures are shown in USD instead. */
  fallback: boolean;
  fromUsd: (usd: number) => number;
  toUsd: (amount: number) => number;
}

export function moneyFor(choice: DisplayCurrency, fx: Fx | undefined, localCurrency: string | undefined): Money {
  const wanted = choice === "LOCAL" ? (localCurrency ?? "USD") : choice;
  const rate = wanted === "USD" ? 1 : fx?.rates[wanted];
  const code = rate ? wanted : "USD";
  const perUsd = rate ?? 1;
  return {
    code,
    perUsd,
    fallback: !rate,
    fromUsd: (usd) => usd * perUsd,
    toUsd: (amount) => amount / perUsd,
  };
}

export const USD: Money = moneyFor("USD", undefined, undefined);

export function fmtMoney(usd: number, money: Money = USD): string {
  const value = money.fromUsd(usd);
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}${money.code} ${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}${money.code} ${(abs / 1_000).toFixed(0)}k`;
  return `${sign}${money.code} ${abs.toFixed(0)}`;
}

export const fmtPrice = (usdPerKs: number, money: Money = USD) =>
  `${money.code} ${Math.round(money.fromUsd(usdPerKs)).toLocaleString("en-US")}/KS`;
