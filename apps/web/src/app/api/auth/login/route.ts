import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/auth/login`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    },
  );
  const response = new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
  for (const cookie of upstream.headers.getSetCookie?.() ?? []) {
    response.headers.append("set-cookie", cookie);
  }
  return response;
}
