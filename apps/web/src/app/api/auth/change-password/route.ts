import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/auth/change-password`,
    { method: "POST", headers, body: await request.text(), cache: "no-store" },
  );
  const response = new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
  for (const cookieValue of upstream.headers.getSetCookie?.() ?? []) {
    response.headers.append("set-cookie", cookieValue);
  }
  return response;
}
