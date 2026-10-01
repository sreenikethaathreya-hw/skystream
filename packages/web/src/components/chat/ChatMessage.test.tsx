import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessage as ChatMessageData } from "@/lib/types";

function message(overrides: Partial<ChatMessageData> = {}): ChatMessageData {
  return {
    role: "assistant",
    text: "2482 is at 20.2% share.",
    createdAt: "2026-10-01T10:00:00Z",
    numbersRedacted: false,
    provider: "template",
    sources: [
      {
        tool: "get_segment_baseline",
        label: "Baseline for 2482",
        columns: ["Year", "Share (%)"],
        rows: [
          [2025, 18.4],
          [2026, null],
        ],
      },
    ],
    links: [
      { label: "Open in Capture", to: "/capture" },
      { label: "Elsewhere", to: "https://example.com" },
    ],
    ...overrides,
  };
}

function renderMessage(data: ChatMessageData) {
  return render(
    <MemoryRouter>
      <ChatMessage message={data} />
    </MemoryRouter>,
  );
}

describe("ChatMessage", () => {
  it("renders the source table and only internal links", () => {
    renderMessage(message());
    expect(screen.getByTestId("chat-source")).toHaveTextContent("Baseline for 2482");
    expect(screen.getByText("18.4")).toBeInTheDocument();
    expect(screen.getByText("–")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Capture/ })).toHaveAttribute("href", "/capture");
    expect(screen.queryByRole("link", { name: /Elsewhere/ })).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-redacted")).not.toBeInTheDocument();
  });

  it("shows the redaction note when numbers were removed", () => {
    renderMessage(message({ numbersRedacted: true, text: "Plan is (see table)." }));
    expect(screen.getByTestId("chat-redacted")).toHaveTextContent("could not confirm");
  });

  it("never interprets answer text as HTML", () => {
    const { container } = renderMessage(message({ text: '<img src="x" onerror="alert(1)"><b>bold</b>' }));
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByTestId("chat-text")).toHaveTextContent('<img src="x" onerror="alert(1)"><b>bold</b>');
  });
});
