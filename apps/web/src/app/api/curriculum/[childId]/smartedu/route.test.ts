import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { POST } from "./route";

describe("SmartEdu curriculum import proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards the selected resource with session, CSRF and idempotency", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ household_id: "00000000-0000-0000-0000-000000000001" }),
      )
      .mockResolvedValueOnce(
        Response.json({ material: {}, snapshot: {} }, { status: 201 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const childId = "00000000-0000-0000-0000-000000000101";
    const request = new NextRequest(
      `http://localhost/api/curriculum/${childId}/smartedu`,
      {
        method: "POST",
        headers: {
          cookie: "study_session=test",
          "x-csrf-token": "csrf",
          "idempotency-key": "web-smartedu-import-test",
        },
        body: JSON.stringify({ resource_id: "resource-1" }),
      },
    );

    const response = await POST(request, {
      params: Promise.resolve({ childId }),
    });

    expect(response.status).toBe(201);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        `/children/${childId}/curriculum/imports/smartedu`,
      ),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          cookie: "study_session=test",
          "x-csrf-token": "csrf",
          "idempotency-key": "web-smartedu-import-test",
          "content-type": "application/json",
        }),
        body: JSON.stringify({ resource_id: "resource-1" }),
      }),
    );
  });
});
