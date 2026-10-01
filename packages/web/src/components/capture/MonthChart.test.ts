import { describe, expect, it } from "vitest";
import { niceMax } from "@/components/capture/MonthChart";

describe("niceMax", () => {
  it("rounds the axis top up to a clean step", () => {
    expect(niceMax(14_066 * 1.08)).toBe(20_000);
    expect(niceMax(4_181)).toBe(5_000);
    expect(niceMax(1_900)).toBe(2_000);
    expect(niceMax(2_300)).toBe(2_500);
    expect(niceMax(0)).toBe(1);
  });
});
