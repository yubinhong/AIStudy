import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ childId: string; snapshotId: string }> },
) {
  const { childId, snapshotId } = await context.params;
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const key = request.headers.get("idempotency-key");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  if (key) headers["idempotency-key"] = key;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/curriculum/snapshots/${snapshotId}`,
    { method: "DELETE", headers, cache: "no-store" },
  );
  const body = upstream.status === 204 ? null : await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
