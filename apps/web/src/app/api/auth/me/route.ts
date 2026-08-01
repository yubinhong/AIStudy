import { NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const cookie = request.headers.get("cookie");
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/auth/me`,
    { headers: cookie ? { cookie } : {}, cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
