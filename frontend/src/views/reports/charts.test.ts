import { describe, expect, it } from "vitest";

import { priorityDistributionChart } from "./charts";

describe("priority report chart", () => {
  const t = (key: string) => key.split(".").slice(-1)[0] ?? key;

  it("plots every positive priority total as a distribution", () => {
    const traces = priorityDistributionChart([
      { priority: "protected", currency: "GBP", total_amount: 154423, transaction_count: 38 },
      { priority: "essential", currency: "GBP", total_amount: 129883, transaction_count: 28 },
      { priority: "optional", currency: "GBP", total_amount: 143517, transaction_count: 38 },
    ], t);

    expect(traces).toHaveLength(1);
    expect(traces[0].type).toBe("pie");
    expect(traces[0].hole).toBe(0.58);
    expect(traces[0].labels).toEqual(["protected", "essential", "optional"]);
    expect(traces[0].values).toEqual([1544.23, 1298.83, 1435.17]);
  });

  it("keeps currencies in separate traces", () => {
    const traces = priorityDistributionChart([
      { priority: "essential", currency: "GBP", total_amount: 10000, transaction_count: 1 },
      { priority: "essential", currency: "EUR", total_amount: 20000, transaction_count: 1 },
    ], t);

    expect(traces.map((trace) => trace.name)).toEqual(["GBP", "EUR"]);
    expect(traces.map((trace) => trace.domain.x)).toEqual([
      [0.055, 0.445],
      [0.555, 0.945],
    ]);
    expect(traces.every((trace) => trace.domain.y[1] === 0.78)).toBe(true);
  });

  it("omits totals that cannot form a pie slice", () => {
    const traces = priorityDistributionChart([
      { priority: "essential", currency: "GBP", total_amount: 0, transaction_count: 1 },
      { priority: "optional", currency: "GBP", total_amount: -2000, transaction_count: 1 },
    ], t);

    expect(traces).toEqual([]);
  });
});

