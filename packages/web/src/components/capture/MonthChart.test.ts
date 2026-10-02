import { describe, expect, it } from "vitest";
import { compact, niceMax, vsPlanText } from "@/components/capture/MonthChart";

describe("niceMax", () => {
  it("rounds the axis top up to a clean step", () => {
    expect(niceMax(14_066 * 1.08)).toBe(20_000);
    expect(niceMax(4_181)).toBe(5_000);
    expect(niceMax(1_900)).toBe(2_000);
    expect(niceMax(2_300)).toBe(2_500);
    expect(niceMax(0)).toBe(1);
  });
});

describe("axis and plan labels", () => {
  it("keeps half-thousand ticks distinct", () => {
    expect([0, 500, 1000, 1500, 2000].map(compact)).toEqual(["0", "500", "1k", "1.5k", "2k"]);
    expect(compact(7500)).toBe("7.5k");
  });

  it("says on plan, a percent, or a multiple", () => {
    expect(vsPlanText(0.2)).toBe("on plan");
    expect(vsPlanText(18.4)).toBe("+18%");
    expect(vsPlanText(-5, " vs plan")).toBe("-5% vs plan");
    expect(vsPlanText(899_900, " vs plan")).toBe("9,000× plan");
  });
});
