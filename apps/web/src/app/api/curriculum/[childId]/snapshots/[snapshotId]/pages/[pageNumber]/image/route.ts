import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

export async function GET(
  request: NextRequest,
  context: {
    params: Promise<{
      childId: string;
      snapshotId: string;
      pageNumber: string;
    }>;
  },
) {
  const { childId, snapshotId, pageNumber } = await context.params;
  if (!/^[1-9]\d{0,2}$/.test(pageNumber)) {
    return Response.json({ message: "invalid page number" }, { status: 400 });
  }
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/curriculum/snapshots/${snapshotId}/pages/${pageNumber}/image`,
    { method: "GET", headers, cache: "no-store" },
  );
  const responseHeaders = new Headers();
  responseHeaders.set(
    "content-type",
    upstream.headers.get("content-type") ?? "application/octet-stream",
  );
  responseHeaders.set("cache-control", "private, max-age=300");
  responseHeaders.set("x-content-type-options", "nosniff");
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
