import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET } from "./route";

describe("family parent API proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards the current session to the super-admin-only listing endpoint", async () => {
    const fetchMock = vi.fn(async () => Response.json([]));
    vi.stubGlobal("fetch", fetchMock);

    await GET(
      new NextRequest("http://localhost/api/auth/family-parents", {
        headers: { cookie: "study_session=test" },
      }),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/family-parents"),
      expect.objectContaining({ headers: { cookie: "study_session=test" } }),
    );
  });
});
