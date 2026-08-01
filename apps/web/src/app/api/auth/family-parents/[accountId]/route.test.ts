import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { DELETE } from "./route";

describe("family parent deletion API proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards the CSRF-protected deletion request", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const accountId = "00000000-0000-0000-0000-000000000111";

    await DELETE(
      new NextRequest(`http://localhost/api/auth/family-parents/${accountId}`, {
        method: "DELETE",
        headers: {
          cookie: "study_session=test",
          "x-csrf-token": "csrf",
        },
        body: JSON.stringify({ current_password: "super-admin-password" }),
      }),
      { params: Promise.resolve({ accountId }) },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/auth/family-parents/${accountId}`),
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({
          cookie: "study_session=test",
          "x-csrf-token": "csrf",
        }),
      }),
    );
  });
});
