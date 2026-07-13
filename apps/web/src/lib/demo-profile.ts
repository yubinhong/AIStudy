const demoHouseholdId = "00000000-0000-0000-0000-000000000001";
const apiBaseUrl = process.env.STUDY_API_URL ?? "http://localhost:8000";

export async function loadDemoChildren(): Promise<unknown[]> {
  try {
    const response = await fetch(
      `${apiBaseUrl}/households/${demoHouseholdId}/children`,
      {
        headers: {
          "X-Demo-Household-Id": demoHouseholdId,
          "X-Demo-Role": "parent",
        },
        cache: "no-store",
      },
    );

    if (!response.ok) return [];
    const payload: unknown = await response.json();
    return Array.isArray(payload) ? payload : [];
  } catch {
    return [];
  }
}

export function readString(record: unknown, key: string): string | null {
  if (typeof record !== "object" || record === null || !(key in record))
    return null;
  const value = (record as Record<string, unknown>)[key];
  return typeof value === "string" ? value : null;
}
