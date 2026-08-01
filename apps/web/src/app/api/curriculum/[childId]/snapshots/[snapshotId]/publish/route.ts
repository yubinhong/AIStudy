import { NextRequest } from "next/server";
import { currentHouseholdId } from "../../../../../../../lib/current-household";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ childId: string; snapshotId: string }> },
) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  const { childId, snapshotId } = await context.params;
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const key = request.headers.get("idempotency-key");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  if (key) headers["idempotency-key"] = key;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/curriculum/snapshots/${snapshotId}/publish`,
    { method: "POST", headers, cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
