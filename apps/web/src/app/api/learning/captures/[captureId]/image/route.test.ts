import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET } from "./route";

describe("private capture-image proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards the parent session and streams the private image", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ household_id: "00000000-0000-0000-0000-000000000001" }),
      )
      .mockResolvedValueOnce(
        new Response(new Uint8Array([137, 80, 78, 71]), {
          headers: {
            "cache-control": "private, max-age=300",
            "content-type": "image/png",
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const captureId = "00000000-0000-0000-0000-000000000301";

    const response = await GET(
      new NextRequest(
        `http://localhost/api/learning/captures/${captureId}/image`,
        { headers: { cookie: "study_session=test" } },
      ),
      { params: Promise.resolve({ captureId }) },
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/png");
    expect(response.headers.get("location")).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/captures/${captureId}/media`),
      expect.objectContaining({
        method: "GET",
        headers: { cookie: "study_session=test" },
      }),
    );
  });
});
