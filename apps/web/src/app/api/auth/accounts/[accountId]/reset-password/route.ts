import { NextRequest } from "next/server";
import { currentHouseholdId } from "../../../../../../lib/current-household";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ accountId: string }> },
) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  const { accountId } = await context.params;
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/auth/households/${householdId}/accounts/${accountId}/reset-password`,
    { method: "POST", headers, body: await request.text(), cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
