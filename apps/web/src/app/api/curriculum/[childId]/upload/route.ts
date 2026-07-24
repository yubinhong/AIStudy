import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ childId: string }> },
) {
  const childId = (await context.params).childId;
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const key = request.headers.get("idempotency-key");
  const contentType = request.headers.get("content-type");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  if (key) headers["idempotency-key"] = key;
  if (contentType) headers["content-type"] = contentType;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/children/${childId}/curriculum/imports/files`,
    {
      method: "POST",
      headers,
      body: await request.arrayBuffer(),
      cache: "no-store",
    },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
