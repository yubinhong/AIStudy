import { describe, expect, it } from "vitest";

import { resolveSelectedChildId } from "./child-selection";

const children = [{ id: "child-a" }, { id: "child-b" }];

describe("resolveSelectedChildId", () => {
  it("uses a valid requested child rather than keeping a previous page selection", () => {
    expect(resolveSelectedChildId(children, "child-b")).toBe("child-b");
  });

  it("falls back to the first authorized child when the URL scope is absent or invalid", () => {
    expect(resolveSelectedChildId(children, null)).toBe("child-a");
    expect(resolveSelectedChildId(children, "another-household-child")).toBe(
      "child-a",
    );
  });
});
