import { describe, expect, it } from "vitest";
import { idempotencyKey } from "./idempotency-key";

describe("idempotencyKey", () => {
  it("creates an ASCII key without depending on randomUUID", () => {
    const value = idempotencyKey("web-upload");

    expect(value).toMatch(/^web-upload-[a-z0-9-]+$/);
    expect(value.length).toBeGreaterThan(20);
  });
});
