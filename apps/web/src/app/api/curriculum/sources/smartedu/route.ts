import { NextRequest } from "next/server";

import { currentHouseholdId } from "../../../../../lib/current-household";

export async function GET(request: NextRequest) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });
  const cookie = request.headers.get("cookie");
  const headers: Record<string, string> = {};
  if (cookie) headers.cookie = cookie;
  const query = request.nextUrl.searchParams.toString();
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/curriculum/sources/smartedu/catalog${query ? `?${query}` : ""}`,
    { headers, cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
