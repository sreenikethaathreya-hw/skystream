export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Fixed to en-US so the numbers match the flag messages, which are compared word for word with the backend.
const LOCALE = "en-US";
const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 2 });
const eur = (maximumFractionDigits: number) =>
  new Intl.NumberFormat(LOCALE, { style: "currency", currency: "EUR", currencyDisplay: "code", notation: "compact", maximumFractionDigits });
const eurMillions = eur(2);
const eurSmall = eur(0);
const dateFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium" });
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short" });

export const monthName = (month: number) => MONTHS[month - 1] ?? String(month);

export const fmtNum = (value: number) => integer.format(Math.round(value));

export const fmtDecimal = (value: number) => decimal.format(value);

export const fmtKs = (value: number) => `${fmtNum(value)} KS`;

export const fmtPct = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;

export const fmtPts = (value: number, digits = 1) =>
  `${value >= 0 ? "+" : ""}${value.toFixed(digits)} pts`;

export const fmtEur = (value: number) => (Math.abs(value) >= 1_000_000 ? eurMillions : eurSmall).format(value);

export const fmtDate = (iso: string) => dateFormat.format(new Date(iso));

export const fmtDateTime = (iso: string) => dateTimeFormat.format(new Date(iso));

/** Digits only, so "14,500" and "14500" both read as 14500; empty reads as 0. */
export const parseWhole = (text: string) => Number(text.replace(/[^\d]/g, "")) || 0;

export const fmtSigned = (value: number, formatter: (v: number) => string) =>
  `${value >= 0 ? "+" : "-"}${formatter(Math.abs(value))}`;

export const humanize = (code: string) =>
  code.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
