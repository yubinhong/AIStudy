import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET, PUT } from "./route";

const context = {
  params: Promise.resolve({
    childId: "00000000-0000-0000-0000-000000000101",
  }),
};

describe("English practice settings API proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards reads with the session cookie and household scope", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json({ enabled: false }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await GET(
      new NextRequest(
        "http://localhost/api/children/child/english-practice/settings",
        {
          headers: { cookie: "study_session=test" },
        },
      ),
      context,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/english-practice/settings"),
      expect.objectContaining({
        method: "GET",
        headers: { cookie: "study_session=test" },
      }),
    );
  });

  it("forwards writes with Cookie, CSRF and idempotency", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json({ enabled: true }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest(
      "http://localhost/api/children/child/english-practice/settings",
      {
        method: "PUT",
        headers: {
          cookie: "study_session=test",
          "x-csrf-token": "csrf",
          "idempotency-key": "english-settings-web-001",
        },
        body: JSON.stringify({ enabled: true }),
      },
    );

    await PUT(request, context);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/english-practice/settings"),
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({
          cookie: "study_session=test",
          "x-csrf-token": "csrf",
          "idempotency-key": "english-settings-web-001",
        }),
      }),
    );
  });
});
