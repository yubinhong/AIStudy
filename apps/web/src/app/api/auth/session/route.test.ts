import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

describe("current session API proxy", () => {
  afterEach(() => vi.restoreAllMocks());

  it("forwards the browser session without exposing the upstream path", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ username: "admin", role: "super_admin" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const response = await GET(
      new NextRequest("http://localhost/api/auth/session", {
        headers: { cookie: "study_session=test" },
      }),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/me"),
      expect.objectContaining({ headers: { cookie: "study_session=test" } }),
    );
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      role: "super_admin",
    });
  });
});
