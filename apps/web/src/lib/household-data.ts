import { cookies } from "next/headers";

const householdId = "00000000-0000-0000-0000-000000000001";
const apiBaseUrl = process.env.STUDY_API_URL ?? "http://localhost:8000";

type HouseholdResource = "children" | "tasks" | "devices";

async function loadHouseholdResource(
  resource: HouseholdResource,
): Promise<unknown[]> {
  try {
    const cookieStore = await cookies();
    const session = cookieStore.get("study_session");
    if (!session) return [];
    const response = await fetch(
      `${apiBaseUrl}/households/${householdId}/${resource}`,
      {
        headers: { Cookie: `study_session=${session.value}` },
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

export async function loadChildren(): Promise<unknown[]> {
  return loadHouseholdResource("children");
}

export async function loadTasks(): Promise<unknown[]> {
  return loadHouseholdResource("tasks");
}

export async function loadDevices(): Promise<unknown[]> {
  return loadHouseholdResource("devices");
}

export function readString(record: unknown, key: string): string | null {
  if (typeof record !== "object" || record === null || !(key in record))
    return null;
  const value = (record as Record<string, unknown>)[key];
  return typeof value === "string" ? value : null;
}

export function readNumber(record: unknown, key: string): number | null {
  if (typeof record !== "object" || record === null || !(key in record))
    return null;
  const value = (record as Record<string, unknown>)[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function readDateLabel(record: unknown, key: string): string | null {
  const value = readString(record, key);
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}
