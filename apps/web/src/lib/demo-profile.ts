const demoHouseholdId = "00000000-0000-0000-0000-000000000001";
const apiBaseUrl = process.env.STUDY_API_URL ?? "http://localhost:8000";
const apiToken = process.env.STUDY_API_TOKEN;

export const DEMO_HOUSEHOLD_ID = demoHouseholdId;

type DemoResource = "children" | "tasks" | "devices";

async function loadDemoResource(resource: DemoResource): Promise<unknown[]> {
  try {
    const response = await fetch(
      `${apiBaseUrl}/households/${demoHouseholdId}/${resource}`,
      {
        headers: apiToken
          ? { Authorization: `Bearer ${apiToken}` }
          : {
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

export async function loadDemoChildren(): Promise<unknown[]> {
  return loadDemoResource("children");
}

export async function loadDemoTasks(): Promise<unknown[]> {
  return loadDemoResource("tasks");
}

export async function loadDemoDevices(): Promise<unknown[]> {
  return loadDemoResource("devices");
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
