import { describe, expect, it } from "vitest";

import {
  formatUkDate,
  formatUkDateTime,
  formatUkMonth,
  inclusiveCycleEnd,
} from "./date";

describe("UK date formatting", () => {
  it("formats stored ISO dates and months without timezone conversion", () => {
    expect(formatUkDate("2026-07-25")).toBe("25/07/2026");
    expect(formatUkMonth("2026-07")).toBe("07/2026");
  });

  it("leaves unrecognised date values unchanged", () => {
    expect(formatUkDate("25/07/2026")).toBe("25/07/2026");
    expect(formatUkMonth("July 2026")).toBe("July 2026");
  });

  it("formats timestamps in the Europe/London timezone", () => {
    expect(formatUkDateTime("2026-07-25T12:30:00Z")).toBe("25/07/2026, 13:30");
    expect(formatUkDateTime("not-a-date")).toBe("not-a-date");
  });

  it("converts an exclusive cycle boundary to its inclusive calendar end", () => {
    expect(inclusiveCycleEnd("2026-08-01")).toBe("2026-07-31");
    expect(inclusiveCycleEnd("2026-03-01")).toBe("2026-02-28");
    expect(inclusiveCycleEnd("not-a-date")).toBe("not-a-date");
  });
});

