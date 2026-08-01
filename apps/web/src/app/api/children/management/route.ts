import { NextRequest } from "next/server";
import { currentHouseholdId } from "../../../../lib/current-household";

export async function GET(request: NextRequest) {
  return forward(request, "GET");
}

export async function POST(request: NextRequest) {
  return forward(request, "POST");
}

async function forward(request: NextRequest, method: "GET" | "POST") {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  const headers: Record<string, string> =
    method === "POST" ? { "content-type": "application/json" } : {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const key = request.headers.get("idempotency-key");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  if (key) headers["idempotency-key"] = key;

  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/management`,
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
