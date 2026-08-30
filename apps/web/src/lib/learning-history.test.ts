import { describe, expect, it } from "vitest";

import {
  filterItemsForShanghaiCalendarDay,
  isShanghaiCalendarDay,
  learningHistoryBounds,
  learningHistoryRange,
  selectedLearningDay,
  shiftDateKey,
} from "./learning-history";

const NOW = new Date("2026-07-30T08:00:00Z");

describe("learning history calendar ranges", () => {
  it("matches only the same Shanghai calendar day", () => {
    const reference = new Date("2026-08-30T00:30:00Z");

    expect(isShanghaiCalendarDay("2026-08-29T15:59:59Z", reference)).toBe(
      false,
    );
    expect(isShanghaiCalendarDay("2026-08-29T16:00:00Z", reference)).toBe(true);
    expect(isShanghaiCalendarDay("2026-08-30T15:59:59Z", reference)).toBe(true);
    expect(isShanghaiCalendarDay("2026-08-30T16:00:00Z", reference)).toBe(
      false,
    );
    expect(isShanghaiCalendarDay("not-a-date", reference)).toBe(false);
    expect(isShanghaiCalendarDay(null, reference)).toBe(false);
  });

  it("filters overdue and future items out of today's attention list", () => {
    const reference = new Date("2026-08-30T08:00:00Z");
    const items = [
      { id: "overdue", dueAt: "2026-08-29T15:59:59Z" },
      { id: "today", dueAt: "2026-08-30T08:00:00Z" },
      { id: "future", dueAt: "2026-08-31T08:00:00Z" },
    ];

    expect(
      filterItemsForShanghaiCalendarDay(items, (item) => item.dueAt, reference),
    ).toEqual([{ id: "today", dueAt: "2026-08-30T08:00:00Z" }]);
  });

  it("builds the latest 30 Shanghai calendar days by default", () => {
    expect(learningHistoryRange(null, NOW)).toEqual({
      fromAt: "2026-06-30T16:00:00.000Z",
      toAt: "2026-07-30T16:00:00.000Z",
    });
  });

  it("builds one selected Shanghai day", () => {
    expect(learningHistoryRange("2026-07-29", NOW)).toEqual({
      fromAt: "2026-07-28T16:00:00.000Z",
      toAt: "2026-07-29T16:00:00.000Z",
    });
  });

  it("rejects invalid, future and expired selections", () => {
    const bounds = learningHistoryBounds(NOW);
    expect(bounds).toEqual({ minDate: "2026-02-01", maxDate: "2026-07-30" });
    expect(selectedLearningDay("2026-02-01", NOW)).toBe("2026-02-01");
    expect(selectedLearningDay("2026-01-31", NOW)).toBeNull();
    expect(selectedLearningDay("2026-07-31", NOW)).toBeNull();
    expect(selectedLearningDay("2026-02-30", NOW)).toBeNull();
    expect(shiftDateKey("bad", 1)).toBeNull();
  });
});
