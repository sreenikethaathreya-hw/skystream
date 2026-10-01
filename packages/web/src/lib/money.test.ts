import { fmtMoney, fmtPrice, moneyFor } from "./money";

const fx = { budgetYear: 2026, rates: { USD: 1, EUR: 0.85, MXN: 18.9 } };

describe("money", () => {
  it("shows USD figures in the chosen currency at the budget rate", () => {
    const eur = moneyFor("EUR", fx, "MXN");
    expect(eur.code).toBe("EUR");
    expect(fmtMoney(2_000_000, eur)).toBe("EUR 1.70M");
    expect(fmtPrice(500, eur)).toBe("EUR 425/KS");
    expect(eur.toUsd(425)).toBeCloseTo(500);
  });

  it("uses the scope's local currency for LOCAL", () => {
    const local = moneyFor("LOCAL", fx, "MXN");
    expect(local.code).toBe("MXN");
    expect(fmtMoney(1000, local)).toBe("MXN 19k");
  });

  it("falls back to USD when there is no budget rate", () => {
    const missing = moneyFor("LOCAL", fx, "BRL");
    expect(missing.code).toBe("USD");
    expect(missing.fallback).toBe(true);
    expect(fmtMoney(-1500, missing)).toBe("-USD 2k");
  });
});
