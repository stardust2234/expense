import { describe, expect, it } from "vitest";

import { formatMoney, toMajorUnits, toMinorUnits } from "./money";

describe("money formatting", () => {
  it("converts minor units using each currency exponent", () => {
    expect(toMajorUnits(12345, "GBP")).toBe(123.45);
    expect(toMajorUnits(12345, "JPY")).toBe(12345);
    expect(toMajorUnits(12345, "KWD")).toBe(12.345);
  });

  it("formats values using UK locale conventions", () => {
    expect(formatMoney(12345, "GBP")).toBe("£123.45");
  });

  it("converts entered major-unit amounts back to integer minor units", () => {
    expect(toMinorUnits(123.45, "GBP")).toBe(12345);
    expect(toMinorUnits(12.345, "KWD")).toBe(12345);
  });
});

