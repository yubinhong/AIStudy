import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

async function forward(
  request: NextRequest,
  method: "PATCH" | "DELETE",
  childId: string,
) {
  const headers: Record<string, string> =
    method === "PATCH" ? { "content-type": "application/json" } : {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const key = request.headers.get("idempotency-key");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  if (key) headers["idempotency-key"] = key;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}`,
    {
      method,
      headers,
      body: method === "PATCH" ? await request.text() : undefined,
      cache: "no-store",
    },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ childId: string }> },
) {
  return forward(request, "PATCH", (await context.params).childId);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ childId: string }> },
) {
  return forward(request, "DELETE", (await context.params).childId);
}
