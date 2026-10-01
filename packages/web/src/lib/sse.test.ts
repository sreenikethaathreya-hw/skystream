import { parseSseBlock, splitSse } from "./sse";

describe("server-sent events", () => {
  it("parses an event with JSON data", () => {
    expect(parseSseBlock('event: tool_started\ndata: {"tool":"list_segments"}')).toEqual({
      event: "tool_started",
      data: { tool: "list_segments" },
    });
  });

  it("keeps non-JSON data as text and skips empty blocks", () => {
    expect(parseSseBlock("data: hello")).toEqual({ event: "message", data: "hello" });
    expect(parseSseBlock(": keep-alive")).toBeNull();
  });

  it("splits complete blocks from the unfinished rest", () => {
    const { blocks, rest } = splitSse('event: a\ndata: 1\n\nevent: b\r\ndata: 2\r\n\r\nevent: c\ndata: {"x"');
    expect(blocks).toEqual(["event: a\ndata: 1", "event: b\ndata: 2"]);
    expect(rest).toBe('event: c\ndata: {"x"');
  });
});
