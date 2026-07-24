import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ childId: string; snapshotId: string }> },
) {
  const { childId, snapshotId } = await context.params;
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/curriculum/snapshots/${snapshotId}/pages`,
    { method: "GET", headers, cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
