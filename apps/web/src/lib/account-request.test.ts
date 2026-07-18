import { describe, expect, it } from "vitest";

import {
  childAccountCreationMessage,
  createChildAccountIdempotencyKey,
  isUuid,
} from "./account-request";

describe("child-account request helpers", () => {
  it("creates an ASCII-only idempotency key for Unicode usernames", () => {
    const key = createChildAccountIdempotencyKey();

    expect(key).toMatch(/^web-child-[a-z0-9-]+$/);
    expect(
      [...key].every((character) => character.codePointAt(0)! <= 0x7f),
    ).toBe(true);
  });

  it("accepts only UUID child profile identifiers", () => {
    expect(isUuid("00000000-0000-0000-0000-000000000101")).toBe(true);
    expect(isUuid("1")).toBe(false);
  });

  it("shows an actionable message when a child username already exists", () => {
    expect(childAccountCreationMessage(409, "username already exists")).toBe(
      "用户名已存在，请在上方账号列表中管理现有账号，或更换用户名。",
    );
    expect(childAccountCreationMessage(500)).toContain("创建失败");
  });
});
