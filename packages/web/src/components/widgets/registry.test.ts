import { describe, expect, it } from "vitest";
import { CAPTURE_WIDGETS, visibleIn, widgetsFor } from "@/components/widgets/registry";

describe("capture widget registry", () => {
  it("keeps ids unique and shaped like the server expects", () => {
    const ids = CAPTURE_WIDGETS.map((w) => w.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z][a-z0-9_]{0,39}$/);
  });

  it("shows nothing until the user adds it", () => {
    expect(visibleIn("impact", [], "rep")).toEqual([]);
  });

  it("keeps the order the user added widgets in, per slot", () => {
    const visible = ["ytg", "baseline", "share"];
    expect(visibleIn("impact", visible, "rep").map((w) => w.id)).toEqual(["ytg", "share"]);
    expect(visibleIn("context", visible, "rep").map((w) => w.id)).toEqual(["baseline"]);
  });

  it("drops unknown ids and widgets the role cannot use", () => {
    expect(visibleIn("aside", ["track_record", "gone"], "lead")).toEqual([]);
    expect(visibleIn("aside", ["track_record"], "rep").map((w) => w.id)).toEqual(["track_record"]);
    expect(widgetsFor("lead").some((w) => w.id === "track_record")).toBe(false);
  });
});
