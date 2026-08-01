import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { DELETE } from "./route";

describe("curriculum snapshot delete proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards authenticated, idempotent deletion to the API", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ household_id: "00000000-0000-0000-0000-000000000001" }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const childId = "00000000-0000-0000-0000-000000000101";
    const snapshotId = "00000000-0000-0000-0000-000000000201";

    const response = await DELETE(
      new NextRequest(
        `http://localhost/api/curriculum/${childId}/snapshots/${snapshotId}`,
        {
          method: "DELETE",
          headers: {
            cookie: "study_session=test",
            "idempotency-key": "web-curriculum-delete-test",
            "x-csrf-token": "csrf",
          },
        },
      ),
      { params: Promise.resolve({ childId, snapshotId }) },
    );

    expect(response.status).toBe(204);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        `/children/${childId}/curriculum/snapshots/${snapshotId}`,
      ),
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({
          cookie: "study_session=test",
          "idempotency-key": "web-curriculum-delete-test",
          "x-csrf-token": "csrf",
        }),
      }),
    );
  });
});
