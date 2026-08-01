import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { POST } from "./route";

describe("curriculum knowledge-analysis proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards session, CSRF and idempotency without exposing storage data", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ household_id: "00000000-0000-0000-0000-000000000001" }),
      )
      .mockResolvedValueOnce(
        Response.json(
          { status: "queued", knowledge_points: [] },
          { status: 202 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const childId = "00000000-0000-0000-0000-000000000101";
    const snapshotId = "00000000-0000-0000-0000-000000000201";
    const response = await POST(
      new NextRequest(
        `http://localhost/api/curriculum/${childId}/snapshots/${snapshotId}/analysis`,
        {
          method: "POST",
          headers: {
            cookie: "study_session=test",
            "x-csrf-token": "csrf",
            "idempotency-key": "curriculum-analysis-test",
          },
        },
      ),
      { params: Promise.resolve({ childId, snapshotId }) },
    );

    expect(response.status).toBe(202);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        `/children/${childId}/curriculum/snapshots/${snapshotId}/analysis`,
      ),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          cookie: "study_session=test",
          "x-csrf-token": "csrf",
          "idempotency-key": "curriculum-analysis-test",
        }),
      }),
    );
  });
});
