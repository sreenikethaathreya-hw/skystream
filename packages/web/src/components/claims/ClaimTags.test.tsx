import { render, screen } from "@testing-library/react";
import { ClaimTags } from "./ClaimTags";

describe("ClaimTags", () => {
  it("shows a coin-flip yes/no answer as Uncertain", () => {
    render(
      <ClaimTags
        provider="jev"
        decisions={{
          consistent_with_market_notes: { type: "noul", noul: 0.5 },
          addresses_flags: { type: "noul", noul: 0.07 },
          verifiable: { type: "noul", noul: 0.72 },
        }}
      />,
    );
    expect(screen.getByTestId("tag-consistent_with_market_notes")).toHaveTextContent("Uncertain");
    expect(screen.getByTestId("tag-consistent_with_market_notes")).toHaveTextContent("too close to call");
    expect(screen.getByTestId("tag-addresses_flags")).toHaveTextContent("No93% probability");
    expect(screen.getByTestId("tag-verifiable")).toHaveTextContent("Yes72% probability");
  });
});
