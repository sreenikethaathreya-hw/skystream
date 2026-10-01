import { queryKeysFor, toolLabel } from "./chatActions";
import type { ChatAction } from "./types";

const action = (kind: string): ChatAction => ({ kind, targetType: "entry", targetId: "x", summary: "", link: null });

describe("chat action invalidation", () => {
  it("refreshes the entry views after an entry change, once per key", () => {
    const keys = queryKeysFor([action("entry_submitted"), action("entry_approve")]);
    expect(keys).not.toBe("all");
    expect(keys).toEqual([["/entries"], ["/consensus/queue"], ["/segments/cube"], ["/reps"]]);
  });

  it("refreshes rules after a rule change and everything for an unknown kind", () => {
    expect(queryKeysFor([action("rule_activated")])).toEqual([["/rules"], ["/segments/cube"]]);
    expect(queryKeysFor([action("something_new")])).toBe("all");
  });

  it("labels known tools and humanizes unknown ones", () => {
    expect(toolLabel("explain_entry_flags")).toBe("Explaining the flags");
    expect(toolLabel("brand_new_tool")).toBe("brand new tool");
  });
});
