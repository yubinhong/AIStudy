import { NextRequest } from "next/server";
import { currentHouseholdId } from "../../../../lib/current-household";

async function forward(request: NextRequest, path: string, method: string) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const key = request.headers.get("idempotency-key");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  if (key) headers["idempotency-key"] = key;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}${path}`,
    {
      method,
      headers,
      body: method === "GET" ? undefined : await request.text(),
      cache: "no-store",
    },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function GET(request: NextRequest) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  return forward(request, `/auth/households/${householdId}/accounts`, "GET");
}

export async function POST(request: NextRequest) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  return forward(
    request,
    `/auth/households/${householdId}/accounts/children`,
    "POST",
  );
}
