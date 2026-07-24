import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ childId: string }> },
) {
  return forward(request, (await context.params).childId, "GET");
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ childId: string }> },
) {
  return forward(request, (await context.params).childId, "POST");
}

async function forward(
  request: NextRequest,
  childId: string,
  method: "GET" | "POST",
) {
  const headers: Record<string, string> =
    method === "POST" ? { "content-type": "application/json" } : {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const key = request.headers.get("idempotency-key");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  if (key) headers["idempotency-key"] = key;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/task-recommendations`,
    {
      method,
      headers,
      body: method === "POST" ? await request.text() : undefined,
      cache: "no-store",
    },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
