import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { POST } from "./route";

describe("household provisioning API proxy", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards an authenticated administrator request without a household path", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        household_id: "00000000-0000-0000-0000-000000000111",
        username: "relative_admin",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/auth/households", {
      method: "POST",
      headers: {
        cookie: "study_session=test",
        "idempotency-key": "web-provision-family-test",
        "x-csrf-token": "test-csrf",
      },
      body: JSON.stringify({
        parent_username: "relative_parent",
        parent_password: "an-initial-parent-password",
      }),
    });

    await POST(request);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/households"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          cookie: "study_session=test",
          "idempotency-key": "web-provision-family-test",
          "x-csrf-token": "test-csrf",
        }),
      }),
    );
  });
});
