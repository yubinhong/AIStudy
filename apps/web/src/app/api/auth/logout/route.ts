import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  if (cookie) headers.cookie = cookie;
  if (csrf) headers["x-csrf-token"] = csrf;
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/auth/logout`,
    {
      method: "POST",
      headers,
      cache: "no-store",
    },
  );
  const response = new Response(null, { status: upstream.status });
  for (const cookieValue of upstream.headers.getSetCookie?.() ?? []) {
    response.headers.append("set-cookie", cookieValue);
  }
  return response;
}
