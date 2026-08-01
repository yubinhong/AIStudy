import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET } from "./route";

describe("curriculum parsed-page proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards the parent session to the page-scoped review endpoint", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ household_id: "00000000-0000-0000-0000-000000000001" }),
      )
      .mockResolvedValueOnce(
        Response.json([
          {
            page_number: 1,
            title: "第一单元",
            text: "数一数。",
            confidence: 1,
          },
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);
    const childId = "00000000-0000-0000-0000-000000000101";
    const snapshotId = "00000000-0000-0000-0000-000000000201";

    const response = await GET(
      new NextRequest(
        `http://localhost/api/curriculum/${childId}/snapshots/${snapshotId}/pages`,
        { headers: { cookie: "study_session=test" } },
      ),
      { params: Promise.resolve({ childId, snapshotId }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        `/children/${childId}/curriculum/snapshots/${snapshotId}/pages`,
      ),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ cookie: "study_session=test" }),
      }),
    );
  });
});
