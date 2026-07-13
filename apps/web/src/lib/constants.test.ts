import { describe, expect, it } from "vitest";

import { WEB_APP_VERSION } from "./constants";

describe("web shell", () => {
  it("exposes the P0 version", () => {
    expect(WEB_APP_VERSION).toBe("0.1.0");
  });
});
