import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { PATCH } from "./[childId]/route";
import { POST as EXPORT } from "./[childId]/export/route";
import { POST } from "./route";
import { POST as CREATE_TASK } from "../tasks/route";

describe("child profile API proxy", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards create requests as JSON", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json({ child_id: "00000000-0000-0000-0000-000000000102" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/children", {
      method: "POST",
      headers: {
        cookie: "study_session=test",
        "idempotency-key": "web-profile-test",
        "x-csrf-token": "test-csrf",
      },
      body: JSON.stringify({ display_name: "小汤圆", grade_band: "grade_2" }),
    });

    await POST(request);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/households/00000000-0000-0000-0000-000000000001/children",
      ),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "content-type": "application/json",
        }),
      }),
    );
  });

  it("forwards update requests as JSON", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json({ display_name: "小汤圆" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const childId = "00000000-0000-0000-0000-000000000101";
    const request = new NextRequest(
      `http://localhost/api/children/${childId}`,
      {
        method: "PATCH",
        headers: {
          cookie: "study_session=test",
          "idempotency-key": "web-profile-update-test",
          "x-csrf-token": "test-csrf",
        },
        body: JSON.stringify({ display_name: "小汤圆", grade_band: "grade_3" }),
      },
    );

    await PATCH(request, { params: Promise.resolve({ childId }) });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/children/${childId}`),
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({
          "content-type": "application/json",
        }),
      }),
    );
  });

  it("forwards child data export with session, csrf and idempotency", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json({ schema_version: "v1" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const childId = "00000000-0000-0000-0000-000000000101";
    const request = new NextRequest(
      `http://localhost/api/children/${childId}/export`,
      {
        method: "POST",
        headers: {
          cookie: "study_session=test",
          "idempotency-key": "web-profile-export-test",
          "x-csrf-token": "test-csrf",
        },
      },
    );

    await EXPORT(request, { params: Promise.resolve({ childId }) });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/children/${childId}/exports`),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          cookie: "study_session=test",
          "idempotency-key": "web-profile-export-test",
          "x-csrf-token": "test-csrf",
        }),
      }),
    );
  });

  it("forwards task creation as JSON", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? Response.json({
            household_id: "00000000-0000-0000-0000-000000000001",
          })
        : Response.json({ id: "task-id" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/tasks", {
      method: "POST",
      headers: {
        cookie: "study_session=test",
        "content-type": "application/json",
        "idempotency-key": "web-task-create-test",
        "x-csrf-token": "test-csrf",
      },
      body: JSON.stringify({ title: "今日分数练习" }),
    });

    await CREATE_TASK(request);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/households/00000000-0000-0000-0000-000000000001/tasks",
      ),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "content-type": "application/json",
        }),
      }),
    );
  });
});
