import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

function forwardHeaders(request: NextRequest, mutating: boolean) {
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const idempotency = request.headers.get("idempotency-key");
  if (cookie) headers.cookie = cookie;
  if (mutating && csrf) headers["x-csrf-token"] = csrf;
  if (mutating && idempotency) headers["idempotency-key"] = idempotency;
  return headers;
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ childId: string; snapshotId: string }> },
  method: "GET" | "POST",
) {
  const { childId, snapshotId } = await context.params;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/curriculum/snapshots/${snapshotId}/analysis`,
    {
      method,
      headers: forwardHeaders(request, method === "POST"),
      cache: "no-store",
    },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ childId: string; snapshotId: string }> },
) {
  return proxy(request, context, "GET");
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ childId: string; snapshotId: string }> },
) {
  return proxy(request, context, "POST");
}
