export interface SseEvent {
  event: string;
  data: unknown;
}

/** Parses one server-sent event block ("event: x\ndata: {...}"). Returns null for comments or empty blocks. */
export function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  const raw = data.join("\n");
  try {
    return { event, data: JSON.parse(raw) };
  } catch {
    return { event, data: raw };
  }
}

/** Splits a growing text buffer into complete event blocks and the unfinished remainder. */
export function splitSse(buffer: string): { blocks: string[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  return { blocks: parts.filter((p) => p.trim()), rest };
}
