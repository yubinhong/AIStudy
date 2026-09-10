import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET } from "./route";

describe("SmartEdu catalog proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards the household session and catalog filters", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ household_id: "00000000-0000-0000-0000-000000000001" }),
      )
      .mockResolvedValueOnce(Response.json([]));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest(
        "http://localhost/api/curriculum/sources/smartedu?grade=3&subject=math&q=%E4%BA%BA%E6%95%99%E7%89%88",
        { headers: { cookie: "study_session=test" } },
      ),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/curriculum/sources/smartedu/catalog?grade=3&subject=math&q=%E4%BA%BA%E6%95%99%E7%89%88",
      ),
      expect.objectContaining({
        headers: { cookie: "study_session=test" },
        cache: "no-store",
      }),
    );
  });
});
