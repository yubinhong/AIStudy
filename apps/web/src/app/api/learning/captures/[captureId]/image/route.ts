import { NextRequest } from "next/server";

import { currentHouseholdId } from "../../../../../../lib/current-household";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ captureId: string }> },
) {
  const householdId = await currentHouseholdId(request);
  if (!householdId) return new Response(null, { status: 401 });

  const { captureId } = await context.params;
  const cookie = request.headers.get("cookie");
  const upstream = await fetch(
    `${process.env.STUDY_API_URL ?? "http://api:8000"}/households/${householdId}/captures/${captureId}/media`,
    {
      method: "GET",
      headers: cookie ? { cookie } : undefined,
      cache: "no-store",
    },
  );
  const responseHeaders = new Headers();
  responseHeaders.set(
    "content-type",
    upstream.headers.get("content-type") ?? "application/octet-stream",
  );
  responseHeaders.set(
    "cache-control",
    upstream.headers.get("cache-control") ?? "private, max-age=300",
  );
  responseHeaders.set("x-content-type-options", "nosniff");
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
