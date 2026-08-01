import { NextRequest } from "next/server";
import { currentHouseholdId } from "../../../../../../lib/current-household";

async function forward(
  request: NextRequest,
  method: "GET" | "PUT",
  childId: string,
) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  const headers: Record<string, string> =
    method === "PUT" ? { "content-type": "application/json" } : {};
  for (const name of ["cookie", "x-csrf-token", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/english-practice/settings`,
    {
      method,
      headers,
      body: method === "PUT" ? await request.text() : undefined,
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
  context: { params: Promise<{ childId: string }> },
) {
  return forward(request, "GET", (await context.params).childId);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ childId: string }> },
) {
  return forward(request, "PUT", (await context.params).childId);
}
