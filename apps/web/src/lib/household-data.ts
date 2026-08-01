import { cookies } from "next/headers";

const apiBaseUrl = process.env.STUDY_API_URL ?? "http://localhost:8000";

type HouseholdResource = "children" | "tasks" | "devices";

async function loadHouseholdResource(
  resource: HouseholdResource,
  childId?: string,
): Promise<unknown[]> {
  try {
    const cookieStore = await cookies();
    const session = cookieStore.get("study_session");
    if (!session) return [];
    const household = await loadCurrentHousehold(session.value);
    if (!household) return [];
    const query =
      resource === "tasks" && childId
        ? `?child_id=${encodeURIComponent(childId)}`
        : "";
    const response = await fetch(
      `${apiBaseUrl}/households/${household}/${resource}${query}`,
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

async function loadCurrentHousehold(session: string): Promise<string | null> {
  const response = await fetch(`${apiBaseUrl}/auth/me`, {
    headers: { Cookie: `study_session=${session}` },
    cache: "no-store",
  });
  if (!response.ok) return null;
  const payload: unknown = await response.json();
  if (typeof payload !== "object" || payload === null) return null;
  const householdId = (payload as Record<string, unknown>).household_id;
  return typeof householdId === "string" ? householdId : null;
}

export async function loadChildren(): Promise<unknown[]> {
  return loadHouseholdResource("children");
}

export async function loadTasks(childId?: string): Promise<unknown[]> {
  return loadHouseholdResource("tasks", childId);
}

export async function loadDevices(): Promise<unknown[]> {
  return loadHouseholdResource("devices");
}

export async function loadMistakes(
  childId: string,
  dueOnly = false,
): Promise<unknown[]> {
  try {
    const cookieStore = await cookies();
    const session = cookieStore.get("study_session");
    if (!session) return [];
    const householdId = await loadCurrentHousehold(session.value);
    if (!householdId) return [];
    const query = dueOnly ? "?due_only=true" : "";
    const response = await fetch(
      `${apiBaseUrl}/households/${householdId}/children/${encodeURIComponent(childId)}/mistakes${query}`,
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

export async function loadWeeklyReport(
  childId: string,
): Promise<unknown | null> {
  try {
    const cookieStore = await cookies();
    const session = cookieStore.get("study_session");
    if (!session) return null;
    const householdId = await loadCurrentHousehold(session.value);
    if (!householdId) return null;
    const today = new Date();
    const monday = new Date(today);
    const day = today.getDay() || 7;
    monday.setDate(today.getDate() - day + 1);
    const weekStart = monday.toISOString().slice(0, 10);
    const query = new URLSearchParams({
      child_id: childId,
      week_start: weekStart,
    });
    const response = await fetch(
      `${apiBaseUrl}/households/${householdId}/reports/weekly?${query}`,
      {
        headers: { Cookie: `study_session=${session.value}` },
        cache: "no-store",
      },
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export type LearningDetailsQuery = {
  fromAt: string;
  limit?: number;
  toAt: string;
};

export async function loadLearningDetails(
  childId: string,
  query: LearningDetailsQuery,
): Promise<unknown[]> {
  try {
    const cookieStore = await cookies();
    const session = cookieStore.get("study_session");
    if (!session) return [];
    const householdId = await loadCurrentHousehold(session.value);
    if (!householdId) return [];
    const search = new URLSearchParams({
      from_at: query.fromAt,
      limit: String(query.limit ?? 200),
      to_at: query.toAt,
    });
    const response = await fetch(
      `${apiBaseUrl}/households/${householdId}/children/${encodeURIComponent(childId)}/learning-details?${search}`,
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

export function readArray(record: unknown, key: string): unknown[] {
  if (typeof record !== "object" || record === null || !(key in record))
    return [];
  const value = (record as Record<string, unknown>)[key];
  return Array.isArray(value) ? value : [];
}

export function readObject(record: unknown, key: string): unknown | null {
  if (typeof record !== "object" || record === null || !(key in record))
    return null;
  const value = (record as Record<string, unknown>)[key];
  return typeof value === "object" && value !== null ? value : null;
}

export function readDateLabel(record: unknown, key: string): string | null {
  const value = readString(record, key);
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}
