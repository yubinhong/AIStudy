import { NextRequest } from "next/server";

const householdId = "00000000-0000-0000-0000-000000000001";

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ accountId: string }> },
) {
  const { accountId } = await context.params;
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/auth/households/${householdId}/accounts/${accountId}/status`,
    { method: "PATCH", headers, body: await request.text(), cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
