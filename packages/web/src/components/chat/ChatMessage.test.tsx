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
    actions: [],
    downloads: [],
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
    expect(screen.getByText("2025")).toBeInTheDocument();
    expect(screen.getByText("–")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Capture/ })).toHaveAttribute("href", "/capture");
    expect(screen.queryByRole("link", { name: /Elsewhere/ })).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-redacted")).not.toBeInTheDocument();
  });

  it("shows the redaction note when numbers were removed", () => {
    renderMessage(message({ numbersRedacted: true, text: "Plan is (see table)." }));
    expect(screen.getByTestId("chat-redacted")).toHaveTextContent("could not confirm");
  });

  it("shows a receipt for each change with an internal link only", () => {
    renderMessage(
      message({
        actions: [
          {
            kind: "entry_submitted",
            targetType: "entry",
            targetId: "e1",
            summary: "Submitted 4,000 KS for 2482, Oct",
            link: "/capture?segment=2482&month=10",
          },
          { kind: "note_added", targetType: "entry", targetId: "e2", summary: "Note added", link: "//evil.example" },
        ],
      }),
    );
    const receipts = screen.getAllByTestId("chat-action");
    expect(receipts).toHaveLength(2);
    expect(receipts[0]).toHaveTextContent("Done: Submitted 4,000 KS for 2482, Oct");
    expect(screen.getAllByRole("link", { name: /See it/ })).toHaveLength(1);
    expect(screen.getByRole("link", { name: /See it/ })).toHaveAttribute("href", "/capture?segment=2482&month=10");
  });

  it("offers only export downloads", () => {
    renderMessage(
      message({
        downloads: [
          { label: "Download supply handoff CSV", href: "/export/supply.csv?country=ES&mega=SP01" },
          { label: "Bad", href: "/admin/users" },
        ],
      }),
    );
    expect(screen.getAllByTestId("chat-download")).toHaveLength(1);
    expect(screen.getByTestId("chat-download")).toHaveTextContent("Download supply handoff CSV");
  });

  it("never interprets answer text as HTML", () => {
    const { container } = renderMessage(message({ text: '<img src="x" onerror="alert(1)"><b>bold</b>' }));
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByTestId("chat-text")).toHaveTextContent('<img src="x" onerror="alert(1)"><b>bold</b>');
  });
});
