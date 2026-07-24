import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET } from "./route";

describe("private curriculum page-image proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("streams the authenticated JPEG and never redirects to MinIO", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(new Uint8Array([0xff, 0xd8, 0xff]), {
          headers: { "content-type": "image/jpeg" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const childId = "00000000-0000-0000-0000-000000000101";
    const snapshotId = "00000000-0000-0000-0000-000000000201";
    const response = await GET(
      new NextRequest(
        `http://localhost/api/curriculum/${childId}/snapshots/${snapshotId}/pages/14/image`,
        { headers: { cookie: "study_session=test" } },
      ),
      {
        params: Promise.resolve({
          childId,
          snapshotId,
          pageNumber: "14",
        }),
      },
    );

    expect(response.headers.get("content-type")).toBe("image/jpeg");
    expect(response.headers.get("location")).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/pages/14/image"),
      expect.objectContaining({
        method: "GET",
        headers: { cookie: "study_session=test" },
      }),
    );
  });
});
