import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET, POST } from "./route";

describe("child management API proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lists aggregates with the household session", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json([]),
    );
    vi.stubGlobal("fetch", fetchMock);

    await GET(
      new NextRequest("http://localhost/api/children/management", {
        headers: { cookie: "study_session=test" },
      }),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/children/management"),
      expect.objectContaining({
        method: "GET",
        headers: { cookie: "study_session=test" },
      }),
    );
  });

  it("forwards aggregate creation and idempotency headers", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json({ child: {} }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest(
      "http://localhost/api/children/management",
      {
        method: "POST",
        headers: {
          cookie: "study_session=test",
          "idempotency-key": "web-management-test",
          "x-csrf-token": "csrf",
        },
        body: JSON.stringify({ display_name: "小汤圆" }),
      },
    );

    await POST(request);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/children/management"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "content-type": "application/json",
          cookie: "study_session=test",
          "idempotency-key": "web-management-test",
          "x-csrf-token": "csrf",
        }),
      }),
    );
  });
});
