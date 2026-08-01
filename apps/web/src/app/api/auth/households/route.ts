import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  for (const name of ["cookie", "x-csrf-token", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }

  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/auth/households`,
    { method: "POST", headers, body: await request.text(), cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
