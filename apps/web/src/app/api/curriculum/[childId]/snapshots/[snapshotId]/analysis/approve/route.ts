import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ childId: string; snapshotId: string }> },
) {
  const { childId, snapshotId } = await context.params;
  const headers: Record<string, string> = {};
  for (const name of ["cookie", "x-csrf-token", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/curriculum/snapshots/${snapshotId}/analysis/approve`,
    { method: "POST", headers, cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
