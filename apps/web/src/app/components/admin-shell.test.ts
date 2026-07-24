import { describe, expect, it } from "vitest";

import { adminNavigationGroups, childScopedHref } from "./admin-shell";

describe("admin shell information architecture", () => {
  it("keeps only top-level destinations in the sidebar", () => {
    expect(
      adminNavigationGroups.flatMap((group) =>
        group.items.map((item) => item.label),
      ),
    ).toEqual(["家长工作台", "教材与任务", "孩子管理"]);
  });

  it("preserves the selected child while navigating top-level pages", () => {
    expect(childScopedHref("/curriculum", "child / 小汤圆")).toBe(
      "/curriculum?child=child%20%2F%20%E5%B0%8F%E6%B1%A4%E5%9C%86",
    );
    expect(childScopedHref("/accounts")).toBe("/accounts");
  });
});
