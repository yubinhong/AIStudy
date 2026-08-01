import { NextRequest } from "next/server";

const apiBaseUrl = process.env.STUDY_API_URL ?? "http://api:8000";

export async function DELETE(
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
    `${apiBaseUrl}/auth/family-parents/${accountId}`,
    {
      method: "DELETE",
      headers,
      body: await request.text(),
      cache: "no-store",
    },
  );
  const body = upstream.status === 204 ? null : await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers:
      upstream.status === 204
        ? undefined
        : { "content-type": "application/json" },
  });
}
