import { render, screen } from "@testing-library/react";
import cases from "@fixtures/demand_math_cases.json";
import { computeImpact } from "@/lib/demandMath";
import { evaluateFlags } from "@/lib/flags";
import type { EntryInput, SegmentContext } from "@/lib/mathTypes";
import { FlagsTile, HectaresTile, ShareTile, YtgTile } from "./ImpactTiles";

const golden = cases as unknown as { name: string; context: SegmentContext; entry: EntryInput }[];

function live(name: string) {
  const c = golden.find((g) => g.name === name)!;
  const impact = computeImpact(c.context, c.entry);
  return { impact, flags: evaluateFlags(c.context, c.entry, impact) };
}

describe("impact tiles", () => {
  it("shows share, year-to-go and hectares for a plausible number", () => {
    const { impact, flags } = live("2482 at plan");
    render(
      <>
        <ShareTile impact={impact} />
        <YtgTile impact={impact} />
        <HectaresTile impact={impact} />
        <FlagsTile flags={flags} />
      </>,
    );
    expect(screen.getByTestId("share-value")).toHaveTextContent(`${(impact.volumeShare * 100).toFixed(1)}%`);
    expect(screen.getByTestId("ytg-gap").textContent).toMatch(/^[+-][\d,]+$/);
    expect(screen.getByText(/No flags/)).toBeInTheDocument();
  });

  it("floors competitors at 0% and says so when Syngenta exceeds the mega-segment", () => {
    const { impact } = live("2482 beyond the whole mega-segment");
    render(<ShareTile impact={impact} />);
    expect(screen.getByTestId("mega-overflow")).toBeInTheDocument();
    expect(impact.competitors.every((c) => c.newPct === 0)).toBe(true);
  });

  it("lists every flag for an implausible number", () => {
    const { flags } = live("2482 unrealistic");
    render(<FlagsTile flags={flags} />);
    expect(screen.getByTestId("flag-share_over_100")).toBeInTheDocument();
    expect(screen.getByTestId("flag-implied_ha_over_market")).toBeInTheDocument();
    expect(screen.getByText(/justification required/)).toBeInTheDocument();
  });
});
