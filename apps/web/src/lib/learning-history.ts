export const SHANGHAI_TIME_ZONE = "Asia/Shanghai";
export const LEARNING_HISTORY_RETENTION_DAYS = 180;

export type LearningHistoryRange = {
  fromAt: string;
  toAt: string;
};

function dateParts(date: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "2-digit",
    timeZone: SHANGHAI_TIME_ZONE,
    year: "numeric",
  }).formatToParts(date);
  const read = (type: "day" | "month" | "year") =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${read("year")}-${read("month")}-${read("day")}`;
}

export function shiftDateKey(dateKey: string, days: number) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateKey);
  if (!match) return null;
  const shifted = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + days),
  );
  const result = shifted.toISOString().slice(0, 10);
  const [year, month, day] = result.split("-").map(Number);
  const original = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  );
  if (
    original.getUTCFullYear() !== Number(match[1]) ||
    original.getUTCMonth() !== Number(match[2]) - 1 ||
    original.getUTCDate() !== Number(match[3]) ||
    !year ||
    !month ||
    !day
  ) {
    return null;
  }
  return result;
}

export function learningHistoryBounds(now = new Date()) {
  const today = dateParts(now);
  return {
    maxDate: today,
    minDate: shiftDateKey(today, -(LEARNING_HISTORY_RETENTION_DAYS - 1))!,
  };
}

export function selectedLearningDay(
  requestedDate: string | undefined,
  now = new Date(),
) {
  if (!requestedDate || !shiftDateKey(requestedDate, 0)) return null;
  const { minDate, maxDate } = learningHistoryBounds(now);
  if (requestedDate < minDate || requestedDate > maxDate) return null;
  return requestedDate;
}

function shanghaiDayRange(dateKey: string): LearningHistoryRange {
  const nextDate = shiftDateKey(dateKey, 1)!;
  return {
    fromAt: new Date(`${dateKey}T00:00:00+08:00`).toISOString(),
    toAt: new Date(`${nextDate}T00:00:00+08:00`).toISOString(),
  };
}

export function learningHistoryRange(
  selectedDate: string | null,
  now = new Date(),
  recentDays = 30,
): LearningHistoryRange {
  if (selectedDate) return shanghaiDayRange(selectedDate);
  const today = dateParts(now);
  const firstDate = shiftDateKey(today, -(recentDays - 1))!;
  const lastDate = shiftDateKey(today, 1)!;
  return {
    fromAt: new Date(`${firstDate}T00:00:00+08:00`).toISOString(),
    toAt: new Date(`${lastDate}T00:00:00+08:00`).toISOString(),
  };
}
