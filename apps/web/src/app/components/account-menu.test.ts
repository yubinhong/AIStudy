import { describe, expect, it } from "vitest";

import { accountRoleLabel } from "./account-menu";

describe("account menu labels", () => {
  it("makes the administrator role recognizable", () => {
    expect(accountRoleLabel("super_admin")).toBe("超级管理员");
    expect(accountRoleLabel("parent")).toBe("家长账号");
    expect(accountRoleLabel("child")).toBe("孩子账号");
  });
});
