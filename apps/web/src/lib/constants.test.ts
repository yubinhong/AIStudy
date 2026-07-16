import { describe, expect, it } from "vitest";

import { WEB_APP_VERSION } from "./constants";
import { readDateLabel, readNumber, readString } from "./household-data";

describe("web shell", () => {
  it("exposes the P0 version", () => {
    expect(WEB_APP_VERSION).toBe("0.1.0");
  });

  it("reads only validated primitive dashboard fields", () => {
    const record: unknown = {
      display_name: "小禾",
      grade: 3,
      scheduled_for: "2026-07-15",
    };
    expect(readString(record, "display_name")).toBe("小禾");
    expect(readNumber(record, "grade")).toBe(3);
    expect(readDateLabel(record, "scheduled_for")).toBe("7月15日");
    expect(readNumber({ grade: "3" }, "grade")).toBeNull();
  });
});
