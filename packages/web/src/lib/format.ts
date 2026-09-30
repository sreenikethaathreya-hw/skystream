export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const monthName = (month: number) => MONTHS[month - 1] ?? String(month);

export const fmtKs = (value: number) => `${Math.round(value).toLocaleString("en-US")} KS`;

export const fmtNum = (value: number) => Math.round(value).toLocaleString("en-US");

export const fmtPct = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;

export const fmtPts = (value: number, digits = 1) =>
  `${value >= 0 ? "+" : ""}${value.toFixed(digits)} pts`;

export function fmtEur(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}EUR ${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}EUR ${(abs / 1_000).toFixed(0)}k`;
  return `${sign}EUR ${abs.toFixed(0)}`;
}

export const fmtSigned = (value: number, formatter: (v: number) => string) =>
  `${value >= 0 ? "+" : "-"}${formatter(Math.abs(value))}`;

export const humanize = (code: string) =>
  code.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
