import { NextRequest } from "next/server";

const apiBaseUrl = process.env.STUDY_API_URL ?? "http://api:8000";

/** Resolve the scope from the signed session, never from a browser parameter. */
export async function currentHouseholdId(
  request: NextRequest,
): Promise<string | null> {
  const cookie = request.headers.get("cookie");
  if (!cookie) return null;
  const response = await fetch(`${apiBaseUrl}/auth/me`, {
    headers: { cookie },
    cache: "no-store",
  });
  if (!response.ok) return null;
  const payload: unknown = await response.json();
  if (typeof payload !== "object" || payload === null) return null;
  const value = (payload as Record<string, unknown>).household_id;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function studyApiUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}
