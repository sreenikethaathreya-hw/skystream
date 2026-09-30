import cases from "@fixtures/demand_math_cases.json";
import { computeImpact } from "./demandMath";
import { evaluateFlags } from "./flags";
import type { EntryInput, Impact, SegmentContext } from "./mathTypes";

interface GoldenCase {
  name: string;
  context: SegmentContext;
  entry: EntryInput;
  expected: Impact;
  expectedFlags: string[];
}

function expectClose(actual: unknown, expected: unknown, path: string): void {
  if (typeof expected === "number") {
    expect(typeof actual, path).toBe("number");
    expect(Math.abs((actual as number) - expected), path).toBeLessThan(1e-6 * Math.max(1, Math.abs(expected)));
  } else if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true);
    expect((actual as unknown[]).length, path).toBe(expected.length);
    expected.forEach((item, i) => expectClose((actual as unknown[])[i], item, `${path}[${i}]`));
  } else if (expected && typeof expected === "object") {
    for (const [key, value] of Object.entries(expected)) {
      expectClose((actual as Record<string, unknown>)[key], value, `${path}.${key}`);
    }
  } else {
    expect(actual, path).toEqual(expected);
  }
}

describe.each(cases as unknown as GoldenCase[])("golden case: $name", (golden) => {
  it("matches the Python impact", () => {
    expectClose(computeImpact(golden.context, golden.entry), golden.expected, "impact");
  });

  it("raises the same flags as Python", () => {
    const impact = computeImpact(golden.context, golden.entry);
    expect(evaluateFlags(golden.context, golden.entry, impact).map((f) => f.code)).toEqual(
      golden.expectedFlags,
    );
  });
});

describe("computeImpact", () => {
  const golden = (cases as unknown as GoldenCase[])[0];

  it("moves share linearly with the entered number", () => {
    const base = computeImpact(golden.context, golden.entry);
    const raised = computeImpact(golden.context, { ...golden.entry, value: golden.entry.value + 1000 });
    expect(raised.fyEstimate - base.fyEstimate).toBeCloseTo(1000);
    expect(raised.volumeShare - base.volumeShare).toBeCloseTo(1000 / golden.context.marketQtyKs);
  });

  it("keeps competitor shares and Syngenta near 100 after a big raise", () => {
    const impact = computeImpact(golden.context, { ...golden.entry, value: golden.entry.value * 2 });
    const others = impact.competitors.reduce((a, c) => a + c.newPct, 0);
    expect(Math.abs(others + impact.megaShare * 100 - 100)).toBeLessThan(0.5);
    expect(impact.competitors.every((c) => c.deltaPts < 0)).toBe(true);
  });
});
