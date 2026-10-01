import { render, screen } from "@testing-library/react";
import { IbpPanel } from "./IbpPanel";

describe("IbpPanel", () => {
  it("shows the committed IBP number with its variety breakdown", () => {
    render(
      <IbpPanel
        month={10}
        ibp={{
          month: 10,
          snapshot: "2026-09-28",
          qtyKs: 3871,
          varieties: [
            { variety: "Leontes", qtyKs: 2000 },
            { variety: "Hokkaido", qtyKs: 1871 },
          ],
          entryId: "e1",
          entryStatus: "needs_justification",
        }}
      />,
    );
    expect(screen.getByTestId("ibp-panel")).toHaveTextContent("Committed in IBP: 3,871 KS");
    expect(screen.getByTestId("ibp-panel")).toHaveTextContent("snapshot 2026-09-28");
    expect(screen.getByTestId("ibp-varieties")).toHaveTextContent("Leontes2,000 KS");
    expect(screen.getByText("needs justification")).toBeInTheDocument();
  });

  it("explains when the month has no IBP number yet", () => {
    render(<IbpPanel month={11} ibp={undefined} />);
    expect(screen.getByTestId("ibp-panel")).toHaveTextContent("No IBP number for Nov yet");
  });
});
