import { useEffect } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { AskButton } from "./AskButton";
import { ChatProvider, describeContext, useChat } from "@/hooks/useChat";

function Probe() {
  const { open, request, setEnabled } = useChat();
  useEffect(() => setEnabled(true), [setEnabled]);
  return (
    <p data-testid="probe">
      {open ? "open" : "closed"}|{request?.question ?? ""}|{request?.context?.entryId ?? ""}|{String(request?.send)}
    </p>
  );
}

describe("AskButton", () => {
  it("is hidden outside the chat provider", () => {
    render(<AskButton question="Why?" />);
    expect(screen.queryByTestId("ask-button")).not.toBeInTheDocument();
  });

  it("opens the chat with its question and context", () => {
    render(
      <ChatProvider>
        <Probe />
        <AskButton question="Why is this flagged?" context={{ page: "capture", entryId: "e1" }} />
      </ChatProvider>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("closed|||undefined");
    fireEvent.click(screen.getByTestId("ask-button"));
    expect(screen.getByTestId("probe")).toHaveTextContent("open|Why is this flagged?|e1|true");
  });
});

describe("describeContext", () => {
  it("names the segment, month and entry", () => {
    const label = (id: number) => (id === 2482 ? "2482 · Autumn late Red" : undefined);
    expect(describeContext({ page: "capture", segmentId: 2482, month: 10, entryId: "e1" }, label)).toBe(
      "2482 · Autumn late Red, Oct, this entry",
    );
    expect(describeContext({ page: "consensus" })).toBe("Consensus");
    expect(describeContext(null)).toBe("");
  });
});
